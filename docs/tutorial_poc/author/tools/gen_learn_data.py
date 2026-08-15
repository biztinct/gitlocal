#!/usr/bin/env python3
"""Generate pb_learn's data files from the authoring source in docs/tutorial_poc/author/.

    python3 docs/tutorial_poc/author/tools/gen_learn_data.py            # write
    python3 docs/tutorial_poc/author/tools/gen_learn_data.py --check    # fail if writing would change anything

WHY A GENERATOR AND NOT HAND-TRANSCRIPTION
------------------------------------------
The authoring source is where content is edited: both languages side by side,
`check_contract.py` guarding every product fact it asserts, and a diff that
reads like prose. The module is the delivery surface. Two surfaces means a
pipeline or a fork, and a fork is what kills content systems — twelve months
later nobody knows which copy is true.

So: content is edited in docs/tutorial_poc/author/, generated into pb_learn,
and `--check` runs beside the tests. Hand-editing a generated file is a build
failure rather than a silent divergence.

WHAT GOES WHERE  (LEARNOS PHASE 1a — CONTENT LEFT THE DATABASE)
---------------------------------------------------------------
Learning CONTENT — stations, lessons, steps, quizzes, missions, glossary, UI
chrome, coach intents, screens and the column micro-glossary — is emitted as
ONE static bilingual asset, `pb_learn/static/content/learn_content.json`. Every
prose leaf in it is `{"en": ..., "vi": ...}` BY CONSTRUCTION, because both
languages are in hand at every emission site below. There is no ORM record and
no `.po` round-trip in that path at all: identical bytes on an empty tenant, on
the demo and on the apex, with nothing for an upgrade to half-apply.

That leaf shape is not a new invention. It is exactly what the server used to
build at runtime by reading the same records twice under two language contexts
and zipping the trees (`learn_station._zip_bilingual`, now deleted): a raw
scalar stays a raw scalar, an EMPTY translatable stays `''` rather than
becoming a truthy `{"en": "", "vi": ""}`, and everything else becomes a pair.
`tools/parity_check.py` re-derives the old payload from the previously
generated XML and diffs it against this file, leaf by leaf.

What STILL travels the Odoo translation path is the handful of values that are
genuinely ORM records: the tenant override slots and the sidebar
section/leaf names. English lands in the XML (the msgid), Vietnamese in
i18n/vi_VN.po (the msgstr).

WHAT THIS GENERATOR OWNS, AND WHAT IT DOES NOT
----------------------------------------------
Owns: pb_learn/static/content/learn_content.json, pb_learn/data/
learn_tenant_slots.xml, pb_learn/data/learn_sidebar_item.xml, i18n/vi_VN.po,
static/src/engine/fixture.js, and the `practice` block of
static/src/anchors.json.

Does NOT own: the `product`, `pattern`, `foreign` and `scan` blocks of that
registry. Those describe real templates in other modules — pb_payrun_wizard,
pb_payruns, pb_payslip_review, pb_import, pb_import_wizard, pb_payrun_ledgers —
and are curated by hand against those files. Generating a claim about somebody
else's template from our own content would let the registry agree with itself
while disagreeing with the product.
"""
import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

# The Phase 2 language gate. Imported rather than reimplemented, because the
# jargon table is also the hovercard's match index — one authored table, one
# set of rules, and no way for the gate and the card to disagree about which
# terms a learner can reach a definition for.
import jargon

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHOR = os.path.dirname(HERE)                       # docs/tutorial_poc/author
# Three levels, not two: the authoring source sits one directory deeper than
# health19's did (docs/tutorial_poc/author/ rather than docs/tutorial_crm/), and
# getting this wrong writes the module into docs/ without complaining.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(AUTHOR)))
ADDON = os.path.join(REPO, 'pb_learn')
assert os.path.isdir(ADDON), 'pb_learn not found at %s — check REPO' % ADDON
MODULE = 'pb_learn'

# No "--" anywhere in this string: it is emitted inside an XML comment, where a
# double hyphen is illegal. (Caught the first time by parsing every generated
# file — see the ledger.)
BANNER = ("GENERATED FILE. Do not edit.\n"
          "         Source: docs/tutorial_poc/author/ · Regenerate: "
          "python3 docs/tutorial_poc/author/tools/gen_learn_data.py\n"
          "         Hand edits are erased on the next run and fail the CI check.")

# station / screen key -> the pb.sidebar.item xml-id it teaches.
# Verified against pb_sidebar/data/pb_sidebar_data.xml; contract.json re-checks
# that each of these records still exists, and tests/test_bundle.py fails on a
# station whose leaf has gone.
SIDEBAR_KEYS = {
    'runpayroll': 'pb_sidebar.item_run_payroll',
    'payruns':    'pb_sidebar.item_pay_runs',
    'payslips':   'pb_sidebar.item_payslips',
    'import':     'pb_sidebar.item_import',
    'fullfinal':  'pb_sidebar.item_full_final',
    'proration':  'pb_sidebar.item_proration',
    'retro':      'pb_sidebar.item_retro',
    # Setup (Phase B). All four leaves carry an action_TAG and an EMPTY
    # action_xmlid (pb_sidebar_data.xml:150-199) — they are OWL client actions,
    # not act_windows. learn.screen._primary() reads the tag, so each still
    # resolves to itself; contract.json::setup-sidebar-leaves pins the ids and
    # ::setup-client-action-tags pins the tags they name.
    'formula':      'pb_sidebar.item_formula',
    'structures':   'pb_sidebar.item_structures',
    'statutory':    'pb_sidebar.item_statutory',
    'integrations': 'pb_sidebar.item_integrations',
    # Overview / People / Insights / Compliance (Phase C1). All eight are OWL
    # client actions; only Dashboard and Government Reports also carry an
    # action_xmlid, so for the other six the TAG is what identifies the screen.
    # contract.json::c1-sidebar-leaves pins the ids and ::c1-client-action-tags
    # pins the tags.
    'dashboard':    'pb_sidebar.item_dashboard',
    'approvals':    'pb_sidebar.item_approvals',
    'employees':    'pb_sidebar.item_employees',
    'contracts':    'pb_sidebar.item_contracts',
    'insights':     'pb_sidebar.item_analytics',
    'explorer':     'pb_sidebar.item_explorer',
    'workforcean':  'pb_sidebar.item_workforce_insights',
    'govreports':   'pb_sidebar.item_govt_reports',
}

# The ONE screen with no leaf. The import wizard is a flow, not a destination:
# it opens over Import Data and has no sidebar item of its own, so its client
# action tag is the only way to know it is showing. Everything else reads its
# matchers from the leaf named above, at bundle time, so the Coach and the
# sidebar can never disagree about which screen is on display.
SCREEN_ACTION_TAGS = {
    'importwizard': 'pb_import_wizard',
}


# --------------------------------------------------------------------- helpers
class Trans:
    """Collects msgid -> msgstr with their source references.

    gettext allows one entry per msgid, so identical English in two places must
    merge. A merge where the two Vietnamese strings DIFFER is a real content
    bug — the same sentence cannot mean two things — so it is reported rather
    than silently resolved.
    """

    def __init__(self):
        self.entries = {}   # msgid -> {'msgstr': str, 'refs': [str]}
        self.conflicts = []
        self.untranslated = []   # (ref, en) where no Vietnamese was written

    def add(self, model, field, xmlid, en, vi):
        en = (en or '').strip()
        vi = (vi or '').strip()
        if not en:
            return
        ref = 'model:%s,%s:%s.%s' % (model, field, MODULE, xmlid)
        if not vi:
            self.untranslated.append((ref, en))
        e = self.entries.setdefault(en, {'msgstr': vi, 'refs': []})
        e['refs'].append(ref)
        if vi and e['msgstr'] and vi != e['msgstr']:
            self.conflicts.append((en, e['msgstr'], vi, ref))
        elif vi and not e['msgstr']:
            e['msgstr'] = vi

    def render(self):
        out = [
            '# Translation of Odoo Server.',
            '# This file contains the translation of the following modules:',
            '# \t* %s' % MODULE,
            '#',
            '# GENERATED — see docs/tutorial_poc/author/tools/gen_learn_data.py',
            '# Every translatable in this module ships a complete Vietnamese value;',
            '# the generator refuses to write this file if one is missing.',
            'msgid ""',
            'msgstr ""',
            '"Project-Id-Version: Odoo Server 19.0\\n"',
            '"Report-Msgid-Bugs-To: \\n"',
            '"Last-Translator: \\n"',
            '"Language-Team: \\n"',
            '"Language: vi\\n"',
            '"MIME-Version: 1.0\\n"',
            '"Content-Type: text/plain; charset=UTF-8\\n"',
            '"Content-Transfer-Encoding: 8bit\\n"',
            '"Plural-Forms: nplurals=1; plural=0;\\n"',
            '',
        ]
        for msgid in sorted(self.entries):
            e = self.entries[msgid]
            out.append('#. module: %s' % MODULE)
            for ref in sorted(set(e['refs'])):
                out.append('#: %s' % ref)
            out.append(_po_str('msgid', msgid))
            out.append(_po_str('msgstr', e['msgstr']))
            out.append('')
        return '\n'.join(out)


def _po_str(kw, s):
    """A .po literal. Multi-line strings use the empty-first-line form so the
    file stays readable and diffable at 100+ character lesson bodies."""
    esc = (s.replace('\\', '\\\\').replace('"', '\\"'))
    if '\n' not in esc and len(esc) < 90:
        return '%s "%s"' % (kw, esc)
    parts = esc.split('\n')
    lines = ['%s ""' % kw]
    for i, p in enumerate(parts):
        lines.append('"%s%s"' % (p, '\\n' if i < len(parts) - 1 else ''))
    return '\n'.join(lines)


def x(s):
    """XML-escape a field value."""
    return html.escape(s or '', quote=False)


def slug(s, prefix=''):
    return prefix + re.sub(r'[^a-z0-9]+', '_', (s or '').lower()).strip('_')


def is_pair(v):
    return isinstance(v, dict) and set(v.keys()) == {'en', 'vi'}


def en_of(v):
    return v['en'] if is_pair(v) else (v if isinstance(v, str) else '')


def vi_of(v):
    return v['vi'] if is_pair(v) else (v if isinstance(v, str) else '')


LIVE_TOKEN_RE = re.compile(r'\{\{live:([a-z_]+)\}\}')

# The six keys models/learn_live.py implements. A token naming anything else
# renders the authored fallback forever and says nothing about why, so it is
# caught here instead — at authoring time, by name.
LIVE_KEYS = {
    'june_net_total', 'june_run_state', 'active_policy_rates',
    'pit_relief', 'flagged_count', 'division_name',
}


class Live:
    """Every {{live:key}} the content writes, and whether it can degrade.

    TWO rules, and the second is the one that matters:
      · the key must exist, or the sentence can never resolve;
      · the body must carry a `live_fallback` IN BOTH LANGUAGES, because on
        every tenant but the demo world that fallback IS the answer. A live
        token with no fallback renders an empty paragraph to twelve tenants out
        of twelve and a fact to none.
    """

    def __init__(self):
        self.problems = []
        self.sites = []

    def check(self, where, body, fallback):
        for lang, text in (('en', en_of(body)), ('vi', vi_of(body))):
            keys = LIVE_TOKEN_RE.findall(text or '')
            if not keys:
                continue
            self.sites.append((where, lang, keys))
            unknown = [k for k in keys if k not in LIVE_KEYS]
            if unknown:
                self.problems.append(
                    '%s [%s] names live keys nothing implements: %s'
                    % (where, lang, ', '.join(unknown)))
            for flang, ftext in (('en', en_of(fallback)), ('vi', vi_of(fallback))):
                if not (ftext or '').strip():
                    self.problems.append(
                        '%s [%s] uses {{live:}} with no %s live_fallback'
                        % (where, lang, flang))
                elif LIVE_TOKEN_RE.search(ftext):
                    self.problems.append(
                        '%s [%s] fallback contains a live token of its own'
                        % (where, flang))


class Bi:
    """The bilingual leaf rule, and the guard that no leaf ships half-written.

    Reproduces `learn_station._zip_bilingual`'s leaf semantics exactly, because
    the frontend has been reading that shape since Phase A and Phase 1a is a
    change of DELIVERY, not of payload:

      * an empty English value stays the empty STRING. Wrapping it as
        `{"en": "", "vi": ""}` would make it truthy and every
        `field ? render : ""` in the engine would draw an empty card — which is
        how a step with no consequence once showed a blank "Before you do this"
        panel.
      * anything else is `{"en": ..., "vi": ...}`.

    The Vietnamese is `.strip()`ped because that is what the `.po` writer did
    to it, and the English is NOT, because that is what the XML field carried.
    Reproducing both is the difference between a parity check that passes and
    one that argues about whitespace.

    A translatable with no Vietnamese is an ERROR, exactly as it was when the
    same omission would have written an empty msgstr: it would reach a
    Vietnamese reader in English, and failing at generation is that discovery
    three minutes earlier.
    """

    def __init__(self):
        self.untranslated = []   # (where, en)
        self.leaves = 0

    def p(self, where, value):
        en = en_of(value) or ''
        vi = (vi_of(value) or '').strip()
        if not en:
            return ''
        if not en.strip():
            # Whitespace only. It never earned a .po entry, so at runtime the
            # zip fell back to English on both sides; say so explicitly.
            return {'en': en, 'vi': en}
        self.leaves += 1
        if not vi:
            self.untranslated.append((where, en))
            vi = en
        return {'en': en, 'vi': vi}

    def each(self, where, values):
        """A LIST of prose leaves — a debrief, a mistakes list."""
        return [self.p('%s[%d]' % (where, i), v) for i, v in enumerate(values or [])]


class Xml:
    def __init__(self, title, note=None):
        self.lines = ['<?xml version="1.0" encoding="utf-8"?>',
                      '<!-- %s -->' % BANNER,
                      '<!-- %s -->' % title]
        if note:
            # No "--" allowed inside an XML comment; asserted rather than
            # trusted, because the failure is a module that will not install.
            assert '--' not in note, 'XML comment cannot contain a double hyphen'
            self.lines.append('<!-- %s -->' % note)
        self.lines += ['<odoo>', '']

    def rec(self, model, xmlid, fields):
        self.lines.append('    <record id="%s" model="%s">' % (xmlid, model))
        for name, val in fields:
            if val is None or val == '':
                continue
            if isinstance(val, bool):
                self.lines.append('        <field name="%s" eval="%s"/>' % (name, val))
            elif isinstance(val, int):
                self.lines.append('        <field name="%s">%d</field>' % (name, val))
            elif isinstance(val, tuple) and val[0] == 'ref':
                self.lines.append('        <field name="%s" ref="%s"/>' % (name, val[1]))
            elif isinstance(val, tuple) and val[0] == 'eval':
                self.lines.append('        <field name="%s" eval="%s"/>' % (name, val[1]))
            else:
                self.lines.append('        <field name="%s">%s</field>' % (name, x(val)))
        self.lines.append('    </record>')
        self.lines.append('')

    def render(self):
        return '\n'.join(self.lines + ['</odoo>', ''])


# ---------------------------------------------------------------- flatteners
def flatten_chrome(en_tree, vi_tree, prefix=''):
    """I18N -> {dotted key: (en, vi)}."""
    out = {}
    for k, v in en_tree.items():
        key = '%s%s' % (prefix, k)
        w = (vi_tree or {}).get(k)
        if is_pair(v):
            out[key] = (en_of(v), vi_of(w) if is_pair(w) else en_of(v))
        elif isinstance(v, dict):
            out.update(flatten_chrome(v, w if isinstance(w, dict) else {}, key + '.'))
        elif isinstance(v, str):
            out[key] = (v, w if isinstance(w, str) else '')
    return out


# ============================================================================
# THE CONTENT TREE — static/content/learn_content.json
# ============================================================================
# One artifact, two consumers: the browser fetches it directly
# (static/src/content/content_loader.js) and the server reads it through
# `learn.content` (models/learn_content.py) for the ask() resolver, the
# capstone predicates and the runtime bootstrap.
#
# Each builder below mirrors, key for key, the `_*_dict()` method that used to
# serialise the matching ORM record — including the keys that are always empty
# (a step line's `note`) and the ORM's own `_order`, because the frontend has
# been reading those orders since Phase A. tools/parity_check.py is what proves
# it rather than this paragraph.
GENERATED_BANNER = (
    'GENERATED FILE. Do not edit. Source: docs/tutorial_poc/author/ · '
    'Regenerate: python3 docs/tutorial_poc/author/tools/gen_learn_data.py'
)


def content_chrome(data, bi):
    """The flat UI-chrome map, in both languages.

    Zipped WITHOUT key exceptions, exactly as `_zip_prose` did. The keys here
    are content names chosen by the author, and three of them — required,
    correct, after — collide with structural keys in the old `_RAW_KEYS` set;
    running chrome through the structural zipper left those three as bare
    English and a Vietnamese learner read "Required" beside "Tùy chọn".
    """
    flat = flatten_chrome(data['i18n']['en'], data['i18n']['vi'])
    out = {}
    for key in sorted(flat):
        en, vi = flat[key]
        if not en:
            # gen_strings skipped these, so no record existed and the map had
            # no entry. Keep the absence rather than inventing an empty pair.
            continue
        out[key] = bi.p('chrome %s' % key, {'en': en, 'vi': vi})
    return out


def content_glossary(data, bi):
    """Glossary entries, plus the phrase table the hovercard matches on.

    `aliases` is NOT prose and is deliberately not a bilingual pair: it is a
    per-language LIST of spellings, and a translator has nothing to do to it.
    Emitting it here rather than deriving it in the browser keeps one rule —
    the jargon gate and the hovercard read the same authored table, so a term
    the gate demands is a term the card can actually reach.
    """
    out = []
    for i, (key, val) in enumerate(data['glossary'].items()):
        aliases = val.get('aliases') or {}
        out.append({
            'key': key,
            '_seq': (i + 1) * 10,
            'term': bi.p('glossary %s term' % key, val['term']),
            'definition': bi.p('glossary %s definition' % key, val['def']),
            # Lowercased and de-duplicated at generation time, sorted longest
            # first, so the renderer never has to think about match order —
            # a shorter phrase can then never steal a longer one's text.
            # `matchTerm: {vi: false}` keeps a DISPLAY term out of the match
            # table for one language. Vietnamese needs it: the product state is
            # called "Nháp", which is the right thing to print on the card and
            # the wrong thing to match, because it is a syllable of "bản nháp"
            # and of "phiếu lương nháp". Display and matching are two jobs, and
            # this is the one entry where they disagree.
            'match': {
                lang: sorted(
                    {(p or '').strip().lower()
                     for p in ((([en_of(val['term']) if lang == 'en'
                                  else vi_of(val['term'])]
                                 if (val.get('matchTerm') or {}).get(lang, True)
                                 else [])
                                + list(aliases.get(lang) or [])))
                     if (p or '').strip()},
                    key=lambda p: (-len(p), p))
                for lang in ('en', 'vi')
            },
        })
    # learn.glossary.term._order = 'sequence, key'
    out.sort(key=lambda g: (g['_seq'], g['key']))
    for g in out:
        del g['_seq']
    return out


def _step_lines(step, data):
    """The rows a visual needs, as (role, label_pair, value) triples.

    ONLY morph. The calc breakdown and the lifecycle stepper are also drawn by
    the practice screens themselves, straight from the fixture — emitting them
    here as well would put one product fact under two owners, and the one that
    drifted would be the one nobody was watching. The fixture is where product
    facts live and where check_contract.py guards them; a lesson step just
    names which chain or which morph to show.

    Morph captions are different: they exist only inside a lesson, and they are
    consequence prose ("insurance did not move") rather than a product fact.
    """
    moment = step.get('moment') or {}
    rows = []
    if moment.get('kind') == 'morph':
        m = data['morphs'][moment['which']]
        # `value` carries an explicit kind marker rather than being inferred
        # from position or emptiness. A row shape you have to reconstruct from
        # ordering is one reorder away from rendering the delta as a heading.
        for role, side in (('morph_before', m['before']), ('morph_after', m['after'])):
            rows.append((role, side['h'], 'head|%s' % side['big']))
            rows.append((role, side['d'], 'detail'))
            if side.get('delta'):
                rows.append((role, side['delta'], 'delta'))
    return rows


def content_lesson(lkey, lesson, data, bi):
    where = 'lesson %s' % lkey
    node = {
        # A lesson carries its OWN name and goal. health_learn reused the
        # station's, which is wrong the moment a lesson is called something
        # more useful than the screen it teaches — "The board and the gates"
        # is not "Pay Runs".
        'key': lkey,
        'name': bi.p('%s name' % where, lesson['title']),
        'goal': bi.p('%s goal' % where, lesson.get('goal')),
        'duration_min': lesson.get('mins') or 5,
        'steps': [],
        'quizzes': [],
    }
    for i, step in enumerate(lesson['steps']):
        sw = '%s step %d' % (where, i)
        moment = step.get('moment') or {}
        node['steps'].append({
            'kicker': bi.p('%s kicker' % sw, step.get('kicker')),
            'title': bi.p('%s title' % sw, step['title']),
            'body': bi.p('%s body' % sw, step['body']),
            'tip': bi.p('%s tip' % sw, step.get('tip')),
            'consequence': bi.p('%s consequence' % sw, step.get('consequence')),
            'screen': step['screen'],
            'anchor': step.get('anchor') or '',
            'visual': moment.get('kind') or 'none',
            'moment_from': moment.get('from') or '',
            'moment_to': moment.get('to') or '',
            'moment_chain': moment.get('chain') or '',
            'moment_which': moment.get('which') or '',
            'lines': [{
                'role': role,
                'label': bi.p('%s line %d label' % (sw, j), label),
                'value': value,
                # learn.step.line.note was never written by the generator and
                # `_line_dict` shipped it as ''. Kept so the payload does not
                # change shape while the delivery does.
                'note': '',
            } for j, (role, label, value) in enumerate(_step_lines(step, data))],
        })
    quiz = lesson.get('quiz')
    if quiz:
        node['quizzes'].append({
            'kind': 'choice',
            'prompt': bi.p('%s quiz prompt' % where, quiz['question']),
            'options': [{
                'label': bi.p('%s quiz opt %d label' % (where, k), opt['text']),
                'correct': bool(opt.get('correct')),
                'feedback': bi.p('%s quiz opt %d feedback' % (where, k),
                                 opt['explanation']),
            } for k, opt in enumerate(quiz['options'])],
        })
    return node


def content_stations(data, bi):
    """Stations — the nodes on the Guided Journey map — with their lessons
    nested exactly as `_station_dict` nested them."""
    lesson_of = {}
    for lkey in sorted(data['lessons']):
        lesson_of.setdefault(data['lessons'][lkey]['station'], lkey)

    out, seq = [], 0
    for line_key, line in data['stations'].items():
        for st in line['stations']:
            seq += 10
            sid = st['id']
            where = 'station %s' % sid
            outline = st.get('outline') or {}
            lkey = lesson_of.get(sid)
            out.append({
                'key': sid,
                'name': bi.p('%s name' % where, st['title']),
                'line': line_key,
                # Phase A is one section. When People or Insights arrive they
                # add ROWS here, not a second map.
                'section': 'payroll',
                'sequence': seq,
                'summary': bi.p('%s summary' % where, st.get('desc')),
                'icon': st.get('icon') or 'circle',
                'kind': 'lesson' if lkey else 'outline',
                'sidebar_key': SIDEBAR_KEYS.get(sid, ''),
                'duration_min': st.get('mins') or 5,
                'required': bool(st.get('required')),
                'star': bool(st.get('star')),
                'after': st.get('after') or '',
                'outline': {
                    'what': bi.p('%s outline what' % where, outline.get('what')),
                    'why': bi.p('%s outline why' % where, outline.get('why')),
                    'when': bi.p('%s outline when' % where, outline.get('when')),
                    'prereq': bi.p('%s outline prereq' % where, outline.get('prereq')),
                    'mistakes': bi.each('%s mistake' % where, outline.get('mistakes')),
                },
                'lessons': ([content_lesson(lkey, data['lessons'][lkey], data, bi)]
                            if lkey else []),
            })
    # learn.station._order = 'line, sequence, id' — the LINE sorts first, and
    # alphabetically, which is not the order the sections were written in.
    # journey.js holds the reading order (LINE_ORDER); this is storage order and
    # the frontend has always received it.
    out.sort(key=lambda s: (s['line'], s['sequence']))
    return out


def content_missions(data, bi):
    steps_by_mission = data['missionSteps']
    out = []
    for i, m in enumerate(data['missions']):
        key = m['id']
        where = 'mission %s' % key
        conf = m.get('conf') or {}
        cons = m.get('consequence') or {}
        anom = m.get('anomaly') or {}
        debrief = m.get('debrief') or {}
        node = {
            'key': key,
            '_seq': (i + 1) * 10,
            'line': m.get('group') or 'payrun',
            'icon': m.get('icon') or 'flask',
            'name': bi.p('%s name' % where, m['title']),
            'summary': bi.p('%s summary' % where, m.get('desc')),
            'duration_min': m.get('mins') or 5,
            'kind': m.get('kind') or ('full' if m.get('full') else 'outline'),
            'outline_note': bi.p('%s outline_note' % where, m.get('outlineNote')),
            'screen': m.get('screen') or '',
            'confidence_key': conf.get('key') or '',
            'confidence_gain': conf.get('gain') or 10,
            'consequence': {
                'title': bi.p('%s consequence title' % where, cons.get('title')),
                'scope': bi.p('%s consequence scope' % where, cons.get('scope')),
                'reversible': bi.p('%s consequence reversible' % where,
                                   cons.get('reversible')),
                'verify': bi.p('%s consequence verify' % where, cons.get('verify')),
            },
            'anomaly': {
                'title': bi.p('%s anomaly title' % where, anom.get('title')),
                'body': bi.p('%s anomaly body' % where, anom.get('body')),
            },
            'steps': [],
            # NOT raw: `did` and `check` are LISTS OF PROSE (the debrief), and
            # the old zip treated them as prose for exactly that reason.
            'did': bi.each('%s did' % where, debrief.get('did')),
            'check': bi.each('%s check' % where, debrief.get('checklist')),
        }
        for k, st in enumerate(steps_by_mission.get(key) or []):
            sw = '%s step %s' % (where, st['id'])
            recovery = st.get('recovery') or {}
            options = []
            for opt in st.get('options') or []:
                rec = recovery.get(opt['id'])
                if not opt.get('correct') and not en_of(rec).strip():
                    # The old model refused this at write time; failing here
                    # names the option instead of the record id.
                    raise SystemExit(
                        'mission %s step %s option %s is wrong and offers no '
                        'recovery. A wrong choice must always be met with a way '
                        'back.' % (key, st['id'], opt['id']))
                options.append({
                    'key': opt['id'],
                    'label': bi.p('%s opt %s label' % (sw, opt['id']), opt['label']),
                    'correct': bool(opt.get('correct')),
                    'recovery': bi.p('%s opt %s recovery' % (sw, opt['id']), rec),
                })
            node['steps'].append({
                'key': st['id'],
                'nav': st.get('nav') or '',
                'target': st.get('target') or '',
                'instruction': bi.p('%s instruction' % sw, st['instruction']),
                'detail': bi.p('%s detail' % sw, st.get('detail')),
                'hint': bi.p('%s hint' % sw, st.get('hint')),
                'is_decision': bool(st.get('decision')),
                'is_consequence': bool(st.get('consequence')),
                'is_undo': bool(st.get('undo')),
                # `check_key`, NOT `check`: the mission dict already has a
                # `check` and it is the debrief CHECKLIST, a list of prose.
                # Live capstones only.
                'check_key': st.get('check') or '',
                'is_ack': bool(st.get('ack')),
                'options': options,
            })
        out.append(node)
    # learn.mission._order = 'sequence, key'
    out.sort(key=lambda m: (m['_seq'], m['key']))
    for m in out:
        del m['_seq']
    return out


# The authoring source names capabilities directly. health_learn mapped four
# prototype ROLE names onto them, which was a translation layer with nothing on
# the other side of it — Payobook's capabilities are read from real groups, so
# the content names them and the generator does not guess.
CAPABILITIES = ('any', 'no_access', 'operator', 'manager', 'owner')

BLOCK_KIND = {'calcKpi': 'calc_kpi', 'src': 'source'}

DYNAMIC_KIND = {'screenCtx': 'screen_blurb', 'nextStep': 'next_step'}


def _blocks_of(intent):
    """(capability, blocks) pairs — one for a plain intent, several for a
    capability-aware one. `any` blocks are emitted first so a reader who has no
    specific variant still gets the general answer."""
    if intent.get('roleVariants'):
        rv = intent['roleVariants']
        unknown = [c for c in rv if c not in CAPABILITIES]
        if unknown:
            raise SystemExit('intent %s: unknown capability %s' % (intent['id'], unknown))
        return [(c, rv[c]) for c in CAPABILITIES if c in rv]
    return [('any', intent.get('blocks') or [])]


def _intent_phrases(intent):
    """Trigger phrases, both languages in ONE bag.

    Deliberately not translated: a learner types in whichever language they are
    thinking in, often mid-shift and often without tone marks, and both have to
    hit the same intent. The LABEL is always a trigger too — the suggestion
    buttons submit it verbatim, so a label that does not resolve to its own
    intent is a dead button.
    """
    phrases = list(intent.get('match') or [])
    for lab in (en_of(intent['label']), vi_of(intent['label'])):
        if lab and lab not in phrases:
            phrases.append(lab)
    return phrases


SHOW_ME_SCENARIO_RE = re.compile(r'^scenario:([a-z0-9_]+)(?:#([a-z0-9_]+))?$')


def _check_show_me(key, targets, scenario_steps, problems):
    """A `show_me` target is an ANCHOR or, since Phase 1b, a SCENARIO.

    `scenario:<key>` or `scenario:<key>#<step>`, where the step is a step KEY
    and not an index — an index would silently re-point at a different step the
    first time a walkthrough gained one in the middle, which is the kind of
    breakage nobody notices because the button still opens something.

    Anchors are checked by `check_contract.py::anchor_lint`; only the scenario
    form is checked here, because it names something the generator can see.
    """
    for target in targets:
        if not target.startswith('scenario:'):
            continue
        hit = SHOW_ME_SCENARIO_RE.match(target)
        if not hit:
            problems.append('intent %s: malformed scenario target %r' % (key, target))
            continue
        sc_key, step_key = hit.group(1), hit.group(2)
        if sc_key not in scenario_steps:
            problems.append('intent %s: show_me points at a scenario that does '
                            'not exist: %s' % (key, sc_key))
        elif step_key and step_key not in scenario_steps[sc_key]:
            problems.append('intent %s: show_me points at step %r of %s, which '
                            'has no such step' % (key, step_key, sc_key))


def _check_offer(key, mode, target, scenario_modes, problems):
    """A `watch` / `try` target is a scenario KEY that supports that mode.

    Validated exactly like `show_me` and for the same reason: the button is an
    offer, and an offer the engine cannot keep is worse than no button. The
    MODE half matters as much as the key — `sc_import` is a Watch of the real
    importer with no replica behind it, so a `try` pointing at it would draw a
    control that starts nothing.
    """
    if not target:
        return
    if target not in scenario_modes:
        problems.append('intent %s: %s points at a scenario that does not '
                        'exist: %s' % (key, mode, target))
    elif mode not in scenario_modes[target]:
        problems.append('intent %s: %s points at %s, which does not declare '
                        'that mode (it has: %s)'
                        % (key, mode, target, ', '.join(scenario_modes[target])
                           or 'none'))


def content_intents(data, bi, live, scenarios=None):
    scenario_steps = {sc['key']: {st['key'] for st in sc['steps']}
                      for sc in (scenarios or [])}
    scenario_modes = {sc['key']: list(sc['modes']) for sc in (scenarios or [])}
    problems = []
    out = []
    for intent in data['qa']:
        key = intent['id']
        where = 'intent %s' % key
        screens = intent.get('screens')
        show_me = [a.strip() for a in (intent.get('showMe') or []) if a.strip()]
        _check_show_me(key, show_me, scenario_steps, problems)
        # LEARNOS Phase 4 — "answers that teach". An intent MAY offer to show
        # the same ground as a walkthrough, in either of two ways.
        watch = (intent.get('watch') or '').strip()
        try_ = (intent.get('try') or '').strip()
        _check_offer(key, 'watch', watch, scenario_modes, problems)
        _check_offer(key, 'try', try_, scenario_modes, problems)
        node = {
            'key': key,
            'label': bi.p('%s label' % where, intent['label']),
            'screens': '*' if screens == '*' else ','.join(screens or []),
            'dynamic': DYNAMIC_KIND.get(intent.get('dynamic'), 'none'),
            'show_me': show_me,
            'watch': watch,
            'try': try_,
            'simpler': bi.p('%s simpler' % where, intent.get('simpler')),
            'practice_key': intent.get('practice') or '',
            # A refusal stays reachable but is never advertised.
            'offer': False if intent.get('offer') is False else True,
            'phrases': _intent_phrases(intent),
            'blocks': [],
        }
        seq = 0
        for capability, blocks in _blocks_of(intent):
            for b in blocks:
                seq += 10
                kind = BLOCK_KIND.get(b['k'], b['k'])
                fallback = b.get('liveFallback')
                live.check('intent %s block %d' % (key, seq),
                           b.get('v') if kind != 'steps' else None, fallback)
                node['blocks'].append({
                    'capability': capability,
                    'kind': kind,
                    'body': ('' if kind == 'steps' or b.get('v') is None
                             else bi.p('%s block %d body' % (where, seq), b['v'])),
                    'live_fallback': bi.p('%s block %d live_fallback' % (where, seq),
                                          fallback),
                    'steps': ([{
                        'text': bi.p('%s block %d step %d' % (where, seq, k), st['t']),
                        'anchor': st.get('a') or '',
                    } for k, st in enumerate(b['v'])] if kind == 'steps' else []),
                })
        out.append(node)
    if problems:
        print('INTENTS: %d problem(s). A "Show me" that opens nothing is the '
              'offer made and not kept.' % len(problems))
        for p in problems:
            print('  %s' % p)
        raise SystemExit(7)
    # learn.intent._order = 'key'
    out.sort(key=lambda i: i['key'])
    return out


def content_screens(data, bi, live, intents_by_key):
    station_by_id = {}
    for line in data['stations'].values():
        for s in line['stations']:
            station_by_id[s['id']] = s
    sub = data.get('subScreens') or {}

    out = []
    for i, (key, ctx) in enumerate(data['screenCtx'].items()):
        where = 'screen %s' % key
        station = station_by_id.get(key)
        if station:
            name = station['title']
        elif key in sub:
            name = sub[key]['label']
        else:
            name = {'en': key, 'vi': key}
        live.check('%s next_step' % where, ctx['next'], ctx.get('liveFallback'))
        chips = []
        for ckey in (ctx.get('chips') or []):
            hit = intents_by_key.get(ckey)
            if not hit:
                raise SystemExit('screen %s chips an intent that does not exist: %s'
                                 % (key, ckey))
            chips.append({'key': ckey, 'label': hit['label']})
        out.append({
            'key': key,
            'sequence': (i + 1) * 10,
            'name': bi.p('%s name' % where, name),
            'blurb': bi.p('%s blurb' % where, ctx['blurb']),
            # health_learn collected next_step for the .po and never wrote the
            # FIELD, so the `whatnext` intent rendered an empty English answer.
            # It is the most-asked question on any screen.
            'next_step': bi.p('%s next_step' % where, ctx['next']),
            'live_fallback': bi.p('%s live_fallback' % where, ctx.get('liveFallback')),
            'action_tags': SCREEN_ACTION_TAGS.get(key, ''),
            'sidebar_key': SIDEBAR_KEYS.get(key, ''),
            'suggest': chips,
        })
    # learn.screen._order = 'sequence, key'
    out.sort(key=lambda s: (s['sequence'], s['key']))
    return out


def content_columns(data, bi):
    out = []
    for screen, cols in data['columns'].items():
        for i, (key, label, body) in enumerate(cols):
            where = 'column %s/%s' % (screen, key)
            out.append({
                'screen': screen,
                'key': key,
                'sequence': (i + 1) * 10,
                'label': bi.p('%s label' % where, label),
                'body': bi.p('%s body' % where, body),
            })
    # learn.column._order = 'screen, sequence, id'
    out.sort(key=lambda c: (c['screen'], c['sequence'], c['key']))
    return out


# ============================================================================
# SCENARIOS — one authored story, three ways to take it (LEARNOS Phase 1b)
# ============================================================================
# The engine that plays these is structurally incapable of pressing a guarded
# control (pb_learn/static/src/scenario/scenario_overlay.js). What the GENERATOR
# owns is the other half of that promise: an author cannot ship a click step
# that has not said, out loud, whether pressing it writes.

# Every mode the engine implements. A scenario naming anything else would draw
# a button that starts nothing.
SCENARIO_MODES = ('watch', 'try', 'do')

# The verbs that make a control a WRITE. Matched as whole words against the
# step key, the anchor and the English title — never the body, because a body
# legitimately explains what a button would do without being that button.
#
# This is a SECOND line of defence, not the rule. The rule is that `guard` is
# mandatory on every click step, so the author has already had to decide; this
# list only refuses the decisions that are obviously wrong. A guard list written
# as a list of examples protects against the examples (ledger, Phase D review) —
# what protects here is that there is no default.
WRITING_VERBS = (
    'compute', 'submit', 'approve', 'reject', 'confirm', 'delete', 'send',
    'commit', 'pay', 'post', 'generate', 'activate', 'archive', 'cancel',
    'apply', 'run', 'release', 'issue', 'disburse', 'finalize', 'transfer',
    'remit',
    # LEARNOS Phase 5. THE LIST HAS TO GROW WITH THE VOCABULARY, and this is
    # the round that proved it: Phase 5 shipped the first `Save` click step in
    # the module and the first `Match`, and neither word was here — so the
    # verb list, whose whole job is to refuse a `guard: false` that is
    # obviously wrong, would have waved both through. It is a second line of
    # defence and it is still a LIST OF EXAMPLES (ledger, Phase D review); the
    # rule that does the work is that `guard` is mandatory and has no default.
    # Adding a word here is part of teaching a new control.
    'save', 'match', 'create', 'add',
)

# Real-screen destinations a scenario may navigate to. Every one is an
# `ir.actions.*` record in a module pb_learn already depends on or that ships
# with the product; contract.json::scenario-nav-actions-exist re-reads the
# declaring files, because this map is a promise about somebody else's module.
SCENARIO_NAV = {
    'pb_dashboard.action_pb_dashboard',
    'pb_payrun_wizard.action_pb_payrun_wizard',
    'pb_payruns.action_pb_payruns_kanban',
    'pb_payslip_review.action_pb_payslip_review',
    'pb_formula_studio.action_pb_formula_studio',
    'pb_import.action_pb_import',
    'pb_statutory.action_pb_statutory',
}


def _anchor_registry_keys(data):
    """Every anchor name the registry knows, and its wildcard prefixes.

    Read from `pb_learn/static/src/anchors.json` — all the kinds this module
    does NOT own, because a scenario legitimately points at controls in other
    templates. The six ported tours walk Formula Studio's grid, the multi-sheet
    importer and the PayAI pill; what matters is that the name is DECLARED
    somewhere rather than typed from memory.

    THE `practice` BLOCK COMES FROM THE AUTHORING SOURCE, NOT FROM THE FILE,
    and the difference is a bootstrapping bug that bit on the first run of
    Phase 5. This generator WRITES that block (see `gen_anchors`) at the end of
    the same run in which this reads it — so a newly authored practice anchor
    was refused for not being in a file that had not been written yet, and the
    only way through was to run the generator twice. `data['practiceAnchors']`
    is the same table one step earlier, and it is the one the emitter is about
    to serialise.
    """
    path = os.path.join(ADDON, 'static/src/anchors.json')
    with open(path, encoding='utf-8') as fh:
        reg = json.load(fh)
    literal, prefixes = set(data.get('practiceAnchors') or {}), set()
    for block in ('product', 'pattern', 'foreign'):
        for key in reg.get(block) or {}:
            if key.endswith('*'):
                prefixes.add(key[:-1])
            else:
                literal.add(key)
    return literal, sorted(prefixes)


def _anchor_known(key, literal, prefixes):
    return key in literal or any(key.startswith(p) for p in prefixes)


def _replica_anchors():
    """Every anchor the PRACTICE REPLICA actually draws.

    Read as literal `data-coach="…"` attributes out of `engine/screens.js`,
    with comments stripped first — the replica's own header paragraph writes
    the attribute name while explaining it, and a scan that counts prose finds
    an anchor that is not there. (Recurring trap, ledger; this is its seventh
    site.)

    WHY THE GENERATOR NEEDS THIS AND NOT ONLY THE REGISTRY. The registry says a
    name is DECLARED. Try mode needs a stronger fact: that the control is on
    the screen the learner is looking at, because a Try step whose anchor the
    replica does not draw is a step whose only outcome is a centred card and a
    learner clicking at nothing. `tests/test_scenario.py::test_09` has asked
    this of the shipped artifact since Phase 1b; asking it here is the same
    question three minutes earlier, and it is what makes a per-step `modes`
    declaration checkable rather than merely honest.
    """
    path = os.path.join(ADDON, 'static/src/engine/screens.js')
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'(?<!:)//[^\n]*', '', src)
    found = set(re.findall(r'data-coach="([^"{}$]+)"', src))
    # An anchor reaching the attribute through a HELPER ARGUMENT is invisible
    # to the scan above — the same blind spot `test_assets` has with icon
    # names, where `kpiTile("layers", …)` hid a missing sprite symbol. The
    # input fields are all drawn by one helper, so its call sites are read too.
    found |= set(re.findall(r'\binputRow\("([a-z0-9-]+)"', src))
    return found


def _writes(step):
    """Does this step's control write? Word-boundary, lowercase, three fields."""
    blob = ' '.join([
        (step.get('key') or '').replace('_', ' ').replace('-', ' '),
        (step.get('anchor') or '').replace('-', ' '),
        en_of((step.get('say') or {}).get('title')),
    ]).lower()
    words = set(re.findall(r'[a-z]+', blob))
    return sorted(v for v in WRITING_VERBS if v in words)


INPUT_KINDS = ('text', 'number')


def content_scenarios(data, bi):
    scenarios = data.get('scenarios') or []
    screens = set(data['screenCtx'])
    literal, prefixes = _anchor_registry_keys(data)
    input_anchors = data.get('inputAnchors') or {}
    replica = _replica_anchors()
    problems, seen = [], set()
    out = []

    # THE INPUT TABLE ITSELF, before any step is read. A declared field the
    # replica does not draw is worse than a missing one: the generator would
    # then happily accept a step pointed at it, and the learner would type into
    # nothing. Checked once per run rather than per step, so the message names
    # the table rather than whichever scenario reached it first.
    for anchor, spec in sorted(input_anchors.items()):
        kind = (spec or {}).get('kind')
        if kind not in INPUT_KINDS:
            problems.append('INPUT_ANCHORS %s: kind must be one of %s, not %r'
                            % (anchor, '/'.join(INPUT_KINDS), kind))
        if anchor not in replica:
            problems.append('INPUT_ANCHORS %s: the replica draws no control '
                            'with that anchor, so nothing could ever be typed '
                            'into it' % anchor)
        if not _anchor_known(anchor, literal, prefixes):
            problems.append('INPUT_ANCHORS %s: is in no block of anchors.json'
                            % anchor)

    for sc in scenarios:
        key = sc['key']
        where = 'scenario %s' % key
        if key in seen:
            problems.append('%s: duplicate key' % where)
        seen.add(key)

        modes = list(sc.get('modes') or [])
        bad_modes = [m for m in modes if m not in SCENARIO_MODES]
        if bad_modes:
            problems.append('%s: unknown mode(s) %s' % (where, ', '.join(bad_modes)))
        if not modes:
            problems.append('%s: no modes — nothing could ever start it' % where)

        # The screens this scenario is OFFERED on — what the Coach's "Show me
        # how" reads once `screens_runtime` has resolved which cockpit is in
        # front of the learner. Authored rather than derived: two of the six
        # ported tours stand on a wizard that has no replica screen and no
        # sidebar leaf, so a union of the steps' own `screen` values would
        # offer them nowhere at all.
        offered = list(sc.get('screens') or [])
        unknown_screens = [s for s in offered if s not in screens]
        if unknown_screens:
            problems.append('%s: offered on screens that do not exist: %s'
                            % (where, ', '.join(unknown_screens)))
        if not offered:
            problems.append('%s: names no screens, so the Coach can never '
                            'offer it anywhere' % where)

        entry = sc.get('entry') or {}
        entry_nav = entry.get('nav') or ''
        entry_screen = entry.get('screen') or ''
        if entry_nav and entry_nav not in SCENARIO_NAV:
            problems.append('%s: entry nav is not in SCENARIO_NAV: %s' % (where, entry_nav))
        if entry_screen and entry_screen not in screens:
            problems.append('%s: entry screen is not a replica screen: %s'
                            % (where, entry_screen))
        # A Do scenario has to LAND somewhere real; a Try scenario has to open
        # on a replica. Watch is the only mode that may legitimately start
        # wherever the learner already is — two of the six ported tours do
        # exactly that, because their wizard cannot be opened cold.
        if 'do' in modes and not entry_nav:
            problems.append('%s: supports "do" but names no entry nav — a live '
                            'walkthrough must open the screen it walks' % where)
        if 'try' in modes and not entry_screen:
            problems.append('%s: supports "try" but names no entry screen' % where)

        node = {
            'key': key,
            'icon': sc.get('icon') or 'compass',
            'line': sc.get('line') or 'payrun',
            'modes': modes,
            'screens': offered,
            'name': bi.p('%s name' % where, sc['name']),
            'tagline': bi.p('%s tagline' % where, sc.get('tagline')),
            'entry': {'nav': entry_nav, 'screen': entry_screen},
            'steps': [],
        }

        step_keys = set()
        for i, step in enumerate(sc.get('steps') or []):
            sw = '%s step %s' % (where, step.get('key') or i)
            skey = step.get('key') or 'step%d' % i
            if skey in step_keys:
                problems.append('%s: duplicate step key' % sw)
            step_keys.add(skey)

            act = step.get('act') or 'observe'
            if act not in ('observe', 'click', 'input'):
                problems.append('%s: unknown act %r' % (sw, act))

            # PER-STEP MODES (LEARNOS Phase 5). A scenario is one story, and
            # until now every step of it was played in every mode the scenario
            # declared. Two of the Phase 5 flows cannot be: the formula
            # walkthrough visits eleven controls the practice replica does not
            # draw, and the import walkthrough points Watch at the real
            # importer's own anchors while Try stands on the replica.
            #
            # So a step may narrow itself — never widen: a step mode the
            # SCENARIO does not declare is a step nobody can ever reach, and a
            # step with no modes at all is a step that has been deleted without
            # being deleted.
            # ABSENT and EMPTY are different answers and `or` cannot tell them
            # apart: absent means "every mode the scenario has", empty means
            # the author scoped the step to nothing, which is a mistake worth
            # naming rather than a default worth applying.
            raw_modes = step.get('modes')
            step_modes = list(modes if raw_modes is None else raw_modes)
            outside = [m for m in step_modes if m not in modes]
            if outside:
                problems.append('%s: declares mode(s) the scenario does not '
                                'offer: %s' % (sw, ', '.join(outside)))
            if not step_modes:
                problems.append('%s: no modes — it can never be played' % sw)

            anchor = step.get('anchor') or ''
            if anchor and not _anchor_known(anchor, literal, prefixes):
                problems.append('%s: anchor %r is in no block of anchors.json'
                                % (sw, anchor))

            nav = step.get('nav') or ''
            if nav and nav not in SCENARIO_NAV:
                problems.append('%s: nav is not in SCENARIO_NAV: %s' % (sw, nav))

            screen = step.get('screen') or ''
            if screen and screen not in screens:
                problems.append('%s: screen is not a replica screen: %s' % (sw, screen))
            if screen and screen not in offered:
                problems.append('%s: stands on %s, which the scenario does not '
                                'list in `screens`' % (sw, screen))
            # THE TRY CONTRACT, and it is per STEP now rather than per
            # scenario. A step that is playable in Try has to stand on a
            # replica AND point at a control the replica draws; a step that has
            # narrowed itself out of Try is free to point at anything the real
            # product has, because that is the only place it will ever run.
            if 'try' in step_modes:
                if not (screen or entry_screen):
                    problems.append('%s: playable in try, and it stands on no '
                                    'replica screen' % sw)
                if anchor and anchor not in replica:
                    problems.append(
                        '%s: playable in try and points at %r, which the '
                        'practice replica does not draw. Either scope the step '
                        'to the modes that can reach that control, or point it '
                        'at one the replica has.' % (sw, anchor))

            # THE GUARD RULE. `guard` is mandatory on a click step and there is
            # no default: a default is a decision nobody made, and the decision
            # is which controls a tutorial is allowed to press.
            guard = step.get('guard')
            if act == 'click':
                if guard is None:
                    problems.append(
                        '%s: a click step must state guard: true or guard: false. '
                        'True when pressing writes; if in doubt, guard.' % sw)
                elif guard is False:
                    verbs = _writes(step)
                    if verbs:
                        problems.append(
                            '%s: guard: false on a control whose name says it %s. '
                            'A tutorial may not press that for somebody.'
                            % (sw, '/'.join(verbs)))
            elif guard:
                problems.append('%s: guard on a %s step means nothing — guard is '
                                'about a click the engine might make' % (sw, act))

            if act == 'input':
                if 'try' not in modes:
                    problems.append('%s: an input step needs a replica to type '
                                    'into, and this scenario is not try-capable' % sw)
                if not step.get('value'):
                    problems.append('%s: an input step must say what is typed' % sw)
                if 'do' in modes:
                    problems.append('%s: input steps are not playable in "do" — '
                                    'the engine will not type into real records' % sw)
                # THE FIELD HAS TO BE A FIELD. `INPUT_ANCHORS` is the one table
                # that says which replica controls are real <input>s, and the
                # replica draws them from the same table — so an input step
                # pointed anywhere else is a step whose only behaviour is to
                # never advance. It fails silently at runtime, which is exactly
                # the kind of thing that has to fail loudly here.
                if anchor not in input_anchors:
                    problems.append(
                        '%s: an input step points at %r, which is not declared '
                        'in INPUT_ANCHORS. The replica draws a real field only '
                        'at those anchors; anywhere else the learner would type '
                        'into nothing and the step would never advance.'
                        % (sw, anchor or '(no anchor)'))

            say = step.get('say') or {}
            node['steps'].append({
                'key': skey,
                'anchor': anchor,
                'nav': nav,
                'screen': screen,
                'act': act,
                'guard': bool(guard),
                # Always emitted, always the full list — never omitted when it
                # equals the scenario's. A reader of the artifact should not
                # have to know the default to know what a step plays in, and
                # `playableSteps()` in the engine then has one shape to read.
                'modes': step_modes,
                'timeout': int(step.get('timeout') or 0),
                'kicker': bi.p('%s kicker' % sw, say.get('kicker')),
                'title': bi.p('%s title' % sw, say.get('title')),
                'body': bi.p('%s body' % sw, say.get('body')),
                'tip': bi.p('%s tip' % sw, say.get('tip')),
                'value': bi.p('%s value' % sw, step.get('value')),
            })

        if not node['steps']:
            problems.append('%s: no steps' % where)
        out.append(node)

    if problems:
        print('SCENARIOS: %d problem(s).' % len(problems))
        for p in problems:
            print('  %s' % p)
        raise SystemExit(6)

    # Storage order is declaration order; journey.js groups by line and uses its
    # own LINE_ORDER for the page, exactly as it does for stations.
    return out


GLOBAL_SUGGEST_LIMIT = 6


def content_global_suggest(intents):
    """What the Coach can answer ANYWHERE.

    The old server ran `search([('screens','=','*'), ('offer','=',True)],
    order='key', limit=6)`. Computed here so the browser and the ask() miss
    path cannot disagree about it, and so the list is diffable.

    THE LIMIT IS A SILENT DROP, SO IT IS A BUILD FAILURE. The order is
    alphabetical by KEY, so the seventh global intent somebody writes does not
    push itself off the list — it pushes off whichever key sorts last, which
    today is `whatpage`, the single most useful thing the Coach can answer on a
    screen it does not cover.

    A printed NOTE was the first attempt and the Phase 4 review was right to
    reject it: the pool is EXACTLY at the limit today, so the very next global
    intent silently costs `whatpage`, and a line in generator output is not
    something anybody reads on the run where it first appears. Refusing makes
    the author choose out loud — de-globalize an intent, or raise the limit
    knowing what it costs.
    """
    pool = [i for i in intents if i['screens'] == '*' and i['offer']]
    pool.sort(key=lambda i: i['key'])
    if len(pool) > GLOBAL_SUGGEST_LIMIT:
        kept = [i['key'] for i in pool[:GLOBAL_SUGGEST_LIMIT]]
        dropped = [i['key'] for i in pool[GLOBAL_SUGGEST_LIMIT:]]
        print('GLOBAL SUGGEST: %d intents are scoped to every screen and the '
              'screenless Coach shows %d. The list is sorted by KEY, so these '
              'would be dropped silently: %s'
              % (len(pool), GLOBAL_SUGGEST_LIMIT, ', '.join(dropped)))
        print('  kept: %s' % ', '.join(kept))
        print('  Scope one of them to the screens it belongs on, or raise '
              'GLOBAL_SUGGEST_LIMIT in this file and say why.')
        raise SystemExit(9)
    return [{'key': i['key'], 'label': i['label']} for i in pool]


def gen_content(data, bi, live):
    """The whole static content plane, as one JSON document."""
    # Scenarios FIRST: an intent's `show_me` may now name one, and a target
    # that points at a walkthrough nobody wrote is a button that opens nothing.
    scenarios = content_scenarios(data, bi)
    intents = content_intents(data, bi, live, scenarios)
    by_key = {i['key']: i for i in intents}
    tree = {
        'chrome': content_chrome(data, bi),
        'stations': content_stations(data, bi),
        'missions': content_missions(data, bi),
        'scenarios': scenarios,
        'glossary': content_glossary(data, bi),
        'intents': intents,
        'screens': content_screens(data, bi, live, by_key),
        'columns': content_columns(data, bi),
        'global_suggest': content_global_suggest(intents),
    }
    # The version is a digest of the tree itself. The old `_bundle_version`
    # hashed the module version plus nine `write_date` maxima plus the company
    # id — a value that could change without the content changing and, worse,
    # could stay the same while a half-applied upgrade left the tables
    # disagreeing. A content hash cannot do either.
    digest = hashlib.sha1(
        json.dumps(tree, sort_keys=True, ensure_ascii=False).encode('utf-8')
    ).hexdigest()[:12]
    tree['version'] = digest
    tree['__generated__'] = GENERATED_BANNER
    return json.dumps(tree, indent=2, ensure_ascii=False, sort_keys=True) + '\n'

def gen_sidebar_item(data, tr):
    """The Journey's front door: its own SECTION, and the leaf inside it.

    Generated, not hand-written, because both NAMES are content and content
    ships in both languages. Everything else on the two records is wiring, and
    the wiring is declared beside the names so the two cannot drift apart.

    The section is emitted FIRST because the leaf refs it. Phase C1 moved the
    leaf out of `pb_sidebar.sec_payrun`: the map now teaches Overview, People,
    Insights and Compliance as well, and a learner looking for the People
    lessons would have gone hunting inside Pay Run.
    """
    sec = data['sidebar']['section']
    leaf = data['sidebar']['leaf']
    doc = Xml("The Journey's front door: the pb.sidebar.section it lives in "
              "and the pb.sidebar.item that opens it.",
              "groups_id on the leaf is deliberately EMPTY. A gated leaf hides "
              "itself from users who cannot use it, which is right for a "
              "working screen and wrong for a learning one: someone who cannot "
              "open Run Payroll is exactly the person who needs to read what it "
              "is before asking for access. The Journey marks those stations "
              "'not in your menu' instead of hiding them.")
    # technical_key is REQUIRED on pb.sidebar.section — a section without one
    # does not load at all.
    doc.rec('pb.sidebar.section', sec['xmlid'], [
        ('name', en_of(sec['name'])),
        ('technical_key', sec['technicalKey']),
        ('sequence', sec['sequence']),
        ('show_label', bool(sec['showLabel'])),
    ])
    tr.add('pb.sidebar.section', 'name', sec['xmlid'],
           en_of(sec['name']), vi_of(sec['name']))
    doc.rec('pb.sidebar.item', leaf['xmlid'], [
        ('name', en_of(leaf['name'])),
        ('section_id', ('ref', sec['xmlid'])),
        ('sequence', leaf['sequence']),
        # pb_sidebar renders a FIXED icon set; an unknown name draws a plain
        # circle, so this is one of the names it knows.
        ('icon', leaf['icon']),
        ('action_xmlid', leaf['actionXmlid']),
        ('action_tag', leaf['actionTag']),
        ('match_action_tags', leaf['actionTag']),
    ])
    tr.add('pb.sidebar.item', 'name', leaf['xmlid'],
           en_of(leaf['name']), vi_of(leaf['name']))
    return doc.render()


def gen_overrides(data, tr):
    doc = Xml('Tenant slots — the shipped defaults. A key with no row here does '
              'not exist, so this file is also the declaration the override '
              'constraint validates against.')
    for key in sorted(data['tenantDefaults']):
        pair = data['tenantDefaults'][key]
        xmlid = slug(key, 'slot_')
        doc.rec('learn.tenant.override', xmlid, [
            ('key', key), ('value', en_of(pair)),
        ])
        tr.add('learn.tenant.override', 'value', xmlid, en_of(pair), vi_of(pair))
    return doc.render()


def gen_fixture():
    """The practice company, as an ES module.

    Stays a static asset and never becomes ORM rows: a fake employee that
    exists only in a JS file cannot be picked up by a report, included in an
    export, or found by somebody searching for a real person.

    The export list is the CONTRACT with engine/screens.js and engine/visuals.js
    — adding a name here without the fixture defining it is an import error at
    asset build time, which is loud, and removing one that screens.js imports is
    the same. TENANT_DEFAULTS is deliberately NOT exported: in the product those
    arrive resolved per company in the bundle, and exporting the fixture's copy
    would give the engine a second source that is wrong for every tenant that
    set an override.
    """
    src = open(os.path.join(AUTHOR, 'practice-data.js'), encoding='utf-8').read()
    header = ('/* %s */\n' % BANNER.replace('\n', '\n   ')
              + '/** @odoo-module **/\n\n')
    # POLICY_NEXT and RATE_CHANGE are deliberately NOT exported. They are the
    # derivation behind the figures L6 and m4 quote — `payslip()` run twice —
    # and they are checked by running this file, not by rendering it. Exporting
    # a name no screen imports would put a second, unread copy of the rate
    # change in the engine's contract.
    exports = ('\nexport { B, PRACTICE_META, CASE, EMP, RUN, PRACTICE, MENU,'
               ' SUB_SCREENS, INPUT_ANCHORS, STATUS_LABELS, CHAINS, POLICY,'
               ' TAX };\n')
    return header + src.rstrip() + '\n' + exports


def gen_anchors(data):
    """Rewrite ONLY the `practice` block of the anchor registry.

    Everything else in that file describes real templates in other modules and
    is curated by hand. Regenerating those from our own content would let the
    registry agree with itself while disagreeing with the product — which is
    precisely the failure the registry exists to catch.
    """
    path = os.path.join(ADDON, 'static/src/anchors.json')
    with open(path, encoding='utf-8') as fh:
        reg = json.load(fh)
    reg['practice'] = dict(data['practiceAnchors'])
    return json.dumps(reg, indent=2, ensure_ascii=False) + '\n'


# ---------------------------------------------------------------------- driver
def dump():
    out = subprocess.run(
        ['node', os.path.join(HERE, 'dump_content.js')],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if regenerating would change any file')
    ap.add_argument('--warnings', action='store_true',
                    help='list every sentence in the readability warning band')
    args = ap.parse_args()

    data = dump()

    # THE LANGUAGE GATE, before anything is emitted. A sentence nobody can
    # follow is a content bug in exactly the way a missing Vietnamese value is,
    # and it is caught in the same place for the same reason: three minutes
    # earlier than the reader would have caught it.
    lint_fail, lint_warn, readability, lint_stats = jargon.lint(
        data, warnings=args.warnings)
    if lint_fail:
        print('JARGON LINT: %d failure(s). Every one of these reaches a '
              'learner who was promised they could start from zero.'
              % len(lint_fail))
        for f in lint_fail[:40]:
            print('  %s' % f)
        if len(lint_fail) > 40:
            print('  ... and %d more' % (len(lint_fail) - 40))
        return 8

    tr = Trans()
    live = Live()
    bi = Bi()
    files = {
        # The static content plane. Everything a learner reads lives here, in
        # both languages, with no ORM record behind any of it.
        'static/content/learn_content.json': gen_content(data, bi, live),
        # The two things that are genuinely records, and therefore still take
        # the .po path: the tenant slots and the sidebar section/leaf names.
        'data/learn_tenant_slots.xml': gen_overrides(data, tr),
        'data/learn_sidebar_item.xml': gen_sidebar_item(data, tr),
        'static/src/engine/fixture.js': gen_fixture(),
        'static/src/anchors.json': gen_anchors(data),
    }
    files['i18n/vi_VN.po'] = tr.render()

    # Parse everything we are about to write. A generator that can emit
    # malformed XML will eventually emit malformed XML — the "--" inside an XML
    # comment that this caught the first time is exactly the class of bug that
    # otherwise surfaces as a module that will not install.
    for rel, content in files.items():
        if not rel.endswith('.xml'):
            continue
        try:
            ET.fromstring(content)
        except ET.ParseError as exc:
            print('MALFORMED: %s — %s' % (rel, exc))
            return 3

    if live.problems:
        print('LIVE TOKENS: %d problem(s). A {{live:}} token with no fallback is '
              'an empty answer on every tenant that is not the demo world.'
              % len(live.problems))
        for p in live.problems:
            print('  %s' % p)
        return 5

    # The bilingual guard now has TWO halves, because content and records take
    # two different paths. Both refuse to write rather than shipping a sentence
    # that reaches a Vietnamese reader in English.
    untranslated = ([('%s (content)' % w, en) for w, en in bi.untranslated]
                    + [('%s (record)' % ref, en) for ref, en in tr.untranslated])
    if untranslated:
        print('UNTRANSLATED: %d translatable value(s) have no Vietnamese. Every '
              'one of these would reach a Vietnamese reader in English.'
              % len(untranslated))
        for ref, en in untranslated[:20]:
            print('  %s\n    %s' % (ref, en[:90]))
        return 4

    if tr.conflicts:
        print('CONFLICT: the same English text has two Vietnamese translations.')
        for en, a, b, ref in tr.conflicts:
            print('  msgid : %s' % en[:80])
            print('    (a) %s\n    (b) %s\n    at  %s' % (a[:80], b[:80], ref))
        return 2

    changed = []
    for rel, content in files.items():
        path = os.path.join(ADDON, rel)
        old = None
        if os.path.exists(path):
            old = open(path, encoding='utf-8').read()
        if old == content:
            continue
        changed.append(rel)
        if not args.check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)

    def report():
        """The readability report, printed on every run.

        Drift in this table is the only early warning that content is sliding
        back towards the register its authors already speak, so it is printed
        whether or not anything changed — including under --check, where it is
        the number a reviewer reads in CI output.
        """
        print('  jargon: %d curated term(s) — %d glossary, %d banned, %d allowed'
              % (lint_stats['terms'], lint_stats['glossary_terms'],
                 lint_stats['banned'], lint_stats['allow']))
        print('  glossary: %d entries · %d matchable phrases EN · %d VI'
              % (lint_stats['entries'], lint_stats['matchable_en'],
                 lint_stats['matchable_vi']))
        jargon.print_readability(readability)
        if lint_warn:
            print('')
            print('  %d sentence(s) in the %d-%d word warning band:'
                  % (len(lint_warn), jargon.WARN_WORDS, jargon.HARD_WORDS))
            for w in lint_warn:
                print('    %s' % w)

    if args.check:
        if changed:
            print('STALE: regenerating would change %d file(s):' % len(changed))
            for c in changed:
                print('  %s' % c)
            print('Run: python3 docs/tutorial_poc/author/tools/gen_learn_data.py')
            return 1
        print('✓ generated data is up to date (%d files)' % len(files))
        report()
        return 0

    print('wrote %d file(s), %d unchanged' % (len(changed), len(files) - len(changed)))
    for c in changed:
        print('  %s' % c)
    print('  %d bilingual content leaf(s) in learn_content.json' % bi.leaves)
    print('  %d translatable string(s) in vi_VN.po' % len(tr.entries))
    print('  %d live token site(s): %s' % (
        len(live.sites), ', '.join(sorted({w for w, _l, _k in live.sites})) or '-'))
    report()
    return 0


if __name__ == '__main__':
    sys.exit(main())
