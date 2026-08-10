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
and `--check` runs beside the tests. Hand-editing the generated XML is a build
failure rather than a silent divergence.

WHAT GOES WHERE
---------------
English lands in the XML (the msgid). Vietnamese lands in i18n/vi_VN.po (the
msgstr). That is the standard Odoo path and it is what lets a translator work
without touching a data file — while `translate=True` keeps arithmetic out of
their reach, because numbers live in non-translatable `value` columns.

WHAT THIS GENERATOR OWNS, AND WHAT IT DOES NOT
----------------------------------------------
Owns: pb_learn/data/*.xml, i18n/vi_VN.po, static/src/engine/fixture.js, and the
`practice` block of static/src/anchors.json.

Does NOT own: the `product`, `pattern`, `foreign` and `scan` blocks of that
registry. Those describe real templates in other modules — pb_payrun_wizard,
pb_payruns, pb_payslip_review, pb_import, pb_import_wizard, pb_payrun_ledgers —
and are curated by hand against those files. Generating a claim about somebody
else's template from our own content would let the registry agree with itself
while disagreeing with the product.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

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


# ------------------------------------------------------------------ generators
def gen_strings(data, tr):
    chrome = flatten_chrome(data['i18n']['en'], data['i18n']['vi'])
    doc = Xml('UI chrome. Both languages reach the browser so the learner can '
              'switch live, mid-lesson, without losing their place.')
    for key in sorted(chrome):
        en, vi = chrome[key]
        if not en:
            continue
        xmlid = slug(key, 'str_')
        doc.rec('learn.string', xmlid, [('key', key), ('value', en)])
        tr.add('learn.string', 'value', xmlid, en, vi)
    return doc.render()


def gen_glossary(data, tr):
    doc = Xml('The domain glossary. One entry per payroll word this desk uses '
              'differently from ordinary Vietnamese or English.')
    for i, (key, val) in enumerate(data['glossary'].items()):
        xmlid = slug(key, 'gloss_')
        doc.rec('learn.glossary.term', xmlid, [
            ('key', key), ('sequence', (i + 1) * 10),
            ('term', en_of(val['term'])), ('definition', en_of(val['def'])),
        ])
        tr.add('learn.glossary.term', 'term', xmlid, en_of(val['term']), vi_of(val['term']))
        tr.add('learn.glossary.term', 'definition', xmlid, en_of(val['def']), vi_of(val['def']))
    return doc.render()


def gen_stations(data, tr):
    doc = Xml('Stations — the nodes on the Guided Journey map. One per Pay Run '
              'sidebar leaf.')
    lesson_of = {l['station']: l['id'] for l in data['lessons'].values()}
    seq = 0
    for line_key, line in data['stations'].items():
        for st in line['stations']:
            seq += 10
            sid = st['id']
            xmlid = slug(sid, 'station_')
            outline = st.get('outline') or {}
            doc.rec('learn.station', xmlid, [
                ('key', sid),
                ('name', en_of(st['title'])),
                ('line', line_key),
                # Phase A is one section. When People or Insights arrive they
                # add ROWS here, not a second map.
                ('section', 'payroll'),
                ('sequence', seq),
                ('summary', en_of(st.get('desc'))),
                ('icon', st.get('icon') or 'circle'),
                ('kind', 'lesson' if sid in lesson_of else 'outline'),
                ('sidebar_key', SIDEBAR_KEYS.get(sid, '')),
                ('duration_min', st.get('mins') or 5),
                ('required', bool(st.get('required'))),
                ('star', bool(st.get('star'))),
                ('after_key', st.get('after') or ''),
                ('outline_what', en_of(outline.get('what'))),
                ('outline_why', en_of(outline.get('why'))),
                ('outline_when', en_of(outline.get('when'))),
                ('outline_prereq', en_of(outline.get('prereq'))),
            ])
            tr.add('learn.station', 'name', xmlid, en_of(st['title']), vi_of(st['title']))
            tr.add('learn.station', 'summary', xmlid,
                   en_of(st.get('desc')), vi_of(st.get('desc')))
            for f in ('what', 'why', 'when', 'prereq'):
                tr.add('learn.station', 'outline_' + f, xmlid,
                       en_of(outline.get(f)), vi_of(outline.get(f)))
            for i, m in enumerate(outline.get('mistakes') or []):
                mid = '%s_mistake_%d' % (xmlid, i)
                doc.rec('learn.station.mistake', mid, [
                    ('station_id', ('ref', xmlid)),
                    ('sequence', (i + 1) * 10),
                    ('name', en_of(m)),
                ])
                tr.add('learn.station.mistake', 'name', mid, en_of(m), vi_of(m))
    return doc.render()


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


def gen_lessons(data, tr):
    doc = Xml('Lessons, steps and understanding checks. Every step renders over '
              'the practice replica, never the live app.')
    for lkey in sorted(data['lessons']):
        lesson = data['lessons'][lkey]
        lx = 'lesson_' + lkey.lower()
        station_x = slug(lesson['station'], 'station_')
        # A lesson carries its OWN name and goal. health_learn reused the
        # station's, which is wrong the moment a lesson is called something
        # more useful than the screen it teaches — "The board and the gates"
        # is not "Pay Runs".
        doc.rec('learn.lesson', lx, [
            ('key', lkey),
            ('station_id', ('ref', station_x)),
            ('sequence', 10),
            ('name', en_of(lesson['title'])),
            ('goal', en_of(lesson.get('goal'))),
            ('duration_min', lesson.get('mins') or 5),
        ])
        tr.add('learn.lesson', 'name', lx, en_of(lesson['title']), vi_of(lesson['title']))
        tr.add('learn.lesson', 'goal', lx, en_of(lesson.get('goal')), vi_of(lesson.get('goal')))

        for i, step in enumerate(lesson['steps']):
            sx = '%s_step_%02d' % (lx, i)
            moment = step.get('moment') or {}
            doc.rec('learn.step', sx, [
                ('lesson_id', ('ref', lx)),
                ('sequence', (i + 1) * 10),
                ('kicker', en_of(step.get('kicker'))),
                ('title', en_of(step['title'])),
                ('body', en_of(step['body'])),
                ('tip', en_of(step.get('tip'))),
                ('consequence', en_of(step.get('consequence'))),
                ('screen', step['screen']),
                ('anchor', step.get('anchor') or ''),
                ('visual', moment.get('kind') or 'none'),
                ('moment_from', moment.get('from') or ''),
                ('moment_to', moment.get('to') or ''),
                ('moment_chain', moment.get('chain') or ''),
                ('moment_which', moment.get('which') or ''),
            ])
            for f in ('kicker', 'title', 'body', 'tip', 'consequence'):
                tr.add('learn.step', f, sx, en_of(step.get(f)), vi_of(step.get(f)))

            for j, (role, label, value) in enumerate(_step_lines(step, data)):
                lnx = '%s_line_%02d' % (sx, j)
                doc.rec('learn.step.line', lnx, [
                    ('step_id', ('ref', sx)),
                    ('sequence', (j + 1) * 10),
                    ('role', role),
                    ('label', en_of(label)),
                    ('value', value),
                ])
                tr.add('learn.step.line', 'label', lnx, en_of(label), vi_of(label))

        quiz = lesson.get('quiz')
        if quiz:
            qx = '%s_quiz' % lx
            doc.rec('learn.quiz', qx, [
                ('lesson_id', ('ref', lx)),
                ('sequence', 10),
                ('kind', 'choice'),
                ('prompt', en_of(quiz['question'])),
            ])
            tr.add('learn.quiz', 'prompt', qx,
                   en_of(quiz['question']), vi_of(quiz['question']))
            for k, opt in enumerate(quiz['options']):
                ox = '%s_opt_%d' % (qx, k)
                doc.rec('learn.quiz.option', ox, [
                    ('quiz_id', ('ref', qx)),
                    ('sequence', (k + 1) * 10),
                    ('label', en_of(opt['text'])),
                    ('is_correct', bool(opt.get('correct'))),
                    ('feedback', en_of(opt['explanation'])),
                ])
                tr.add('learn.quiz.option', 'label', ox,
                       en_of(opt['text']), vi_of(opt['text']))
                tr.add('learn.quiz.option', 'feedback', ox,
                       en_of(opt['explanation']), vi_of(opt['explanation']))
    return doc.render()


# The authoring source names capabilities directly. health_learn mapped four
# prototype ROLE names onto them, which was a translation layer with nothing on
# the other side of it — Payobook's capabilities are read from real groups, so
# the content names them and the generator does not guess.
CAPABILITIES = ('any', 'no_access', 'operator', 'manager', 'owner')

BLOCK_KIND = {'calcKpi': 'calc_kpi', 'src': 'source'}


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


def gen_intents(data, tr):
    doc = Xml('Coach intents. Every answer the Coach can give is a block here; '
              'there is no path from a question to the screen that skips this '
              'file, which is what lets it promise never to invent a rate.')
    for intent in data['qa']:
        key = intent['id']
        xmlid = slug(key, 'intent_')
        screens = intent.get('screens')
        screens_csv = '*' if screens == '*' else ','.join(screens or [])
        doc.rec('learn.intent', xmlid, [
            ('key', key),
            ('label', en_of(intent['label'])),
            ('screens', screens_csv),
            ('dynamic', {'screenCtx': 'screen_blurb',
                         'nextStep': 'next_step'}.get(intent.get('dynamic'), 'none')),
            ('show_me', ','.join(intent.get('showMe') or [])),
            ('simpler', en_of(intent.get('simpler'))),
            ('practice_key', intent.get('practice') or ''),
            # A refusal stays reachable but is never advertised.
            ('offer', False if intent.get('offer') is False else True),
        ])
        tr.add('learn.intent', 'label', xmlid,
               en_of(intent['label']), vi_of(intent['label']))
        if intent.get('simpler'):
            tr.add('learn.intent', 'simpler', xmlid,
                   en_of(intent['simpler']), vi_of(intent['simpler']))

        # The label is ALWAYS a trigger phrase, in both languages. The
        # suggestion buttons submit the label verbatim, so a label that does
        # not resolve to its own intent is a dead button — and a hand-written
        # match list does not reliably overlap the question it is offered as.
        phrases = list(intent.get('match') or [])
        for lab in (en_of(intent['label']), vi_of(intent['label'])):
            if lab and lab not in phrases:
                phrases.append(lab)

        for j, phrase in enumerate(phrases):
            doc.rec('learn.intent.phrase', '%s_p%02d' % (xmlid, j), [
                ('intent_id', ('ref', xmlid)),
                ('text', phrase),
            ])

        seq = 0
        for capability, blocks in _blocks_of(intent):
            for b in blocks:
                seq += 10
                bx = '%s_b%03d' % (xmlid, seq)
                kind = BLOCK_KIND.get(b['k'], b['k'])
                body = ''
                if kind != 'steps' and b.get('v') is not None:
                    body = en_of(b['v'])
                doc.rec('learn.intent.block', bx, [
                    ('intent_id', ('ref', xmlid)),
                    ('sequence', seq),
                    ('capability', capability),
                    ('kind', kind),
                    ('body', body),
                ])
                if body:
                    tr.add('learn.intent.block', 'body', bx, body, vi_of(b['v']))
                if kind == 'steps':
                    for k, st in enumerate(b['v']):
                        sx = '%s_s%02d' % (bx, k)
                        doc.rec('learn.intent.step', sx, [
                            ('block_id', ('ref', bx)),
                            ('sequence', (k + 1) * 10),
                            ('text', en_of(st['t'])),
                            ('anchor', st.get('a') or ''),
                        ])
                        tr.add('learn.intent.step', 'text', sx,
                               en_of(st['t']), vi_of(st['t']))
    return doc.render()


def gen_screens(data, tr):
    doc = Xml('The screens the Coach knows, and how it recognises each one. '
              'Matchers are read from the sidebar leaf named by sidebar_key, so '
              'the Coach and the sidebar can never disagree.')
    station_by_id = {}
    for line in data['stations'].values():
        for s in line['stations']:
            station_by_id[s['id']] = s
    sub = data.get('subScreens') or {}

    for i, (key, ctx) in enumerate(data['screenCtx'].items()):
        xmlid = slug(key, 'screen_')
        station = station_by_id.get(key)
        if station:
            name_en, name_vi = en_of(station['title']), vi_of(station['title'])
        elif key in sub:
            name_en, name_vi = en_of(sub[key]['label']), vi_of(sub[key]['label'])
        else:
            name_en = name_vi = key
        doc.rec('learn.screen', xmlid, [
            ('key', key),
            ('sequence', (i + 1) * 10),
            ('name', name_en),
            ('blurb', en_of(ctx['blurb'])),
            # health_learn collected next_step for the .po and never wrote the
            # FIELD, so the `whatnext` intent rendered an empty answer in
            # English. It is the most-asked question on any screen; it ships as
            # a real field here.
            ('next_step', en_of(ctx['next'])),
            ('action_tags', SCREEN_ACTION_TAGS.get(key, '')),
            ('sidebar_key', SIDEBAR_KEYS.get(key, '')),
            ('suggest_ids', ('eval', '[(6, 0, [%s])]' % ', '.join(
                "ref('%s')" % slug(k, 'intent_') for k in (ctx.get('chips') or [])))),
        ])
        tr.add('learn.screen', 'name', xmlid, name_en, name_vi)
        tr.add('learn.screen', 'blurb', xmlid, en_of(ctx['blurb']), vi_of(ctx['blurb']))
        tr.add('learn.screen', 'next_step', xmlid, en_of(ctx['next']), vi_of(ctx['next']))
    return doc.render()


def gen_missions(data, tr):
    doc = Xml('Practice missions. These run on the REPLICA, never a live '
              'screen: a step that says "compute the run" would otherwise write '
              '48 real payslips.')
    steps_by_mission = data['missionSteps']

    for i, m in enumerate(data['missions']):
        key = m['id']
        xmlid = slug(key, 'mission_')
        full = bool(m.get('full'))
        conf = m.get('conf') or {}
        cons = m.get('consequence') or {}
        anom = m.get('anomaly') or {}
        doc.rec('learn.mission', xmlid, [
            ('key', key),
            ('sequence', (i + 1) * 10),
            ('line', m.get('group') or 'payrun'),
            ('icon', m.get('icon') or 'flask'),
            ('name', en_of(m['title'])),
            ('summary', en_of(m.get('desc'))),
            ('duration_min', m.get('mins') or 5),
            # `live` exists in the model for the demo-tenant capstones. Nothing
            # here uses it and the runner refuses to open one.
            ('kind', m.get('kind') or ('full' if full else 'outline')),
            ('outline_note', en_of(m.get('outlineNote'))),
            ('screen', m.get('screen') or ''),
            ('confidence_key', conf.get('key') or ''),
            ('confidence_gain', conf.get('gain') or 10),
            ('consequence_title', en_of(cons.get('title'))),
            ('consequence_scope', en_of(cons.get('scope'))),
            ('consequence_reversible', en_of(cons.get('reversible'))),
            ('consequence_verify', en_of(cons.get('verify'))),
            ('anomaly_title', en_of(anom.get('title'))),
            ('anomaly_body', en_of(anom.get('body'))),
        ])
        tr.add('learn.mission', 'name', xmlid, en_of(m['title']), vi_of(m['title']))
        tr.add('learn.mission', 'summary', xmlid,
               en_of(m.get('desc')), vi_of(m.get('desc')))
        tr.add('learn.mission', 'outline_note', xmlid,
               en_of(m.get('outlineNote')), vi_of(m.get('outlineNote')))
        for f, src in (('consequence_title', cons.get('title')),
                       ('consequence_scope', cons.get('scope')),
                       ('consequence_reversible', cons.get('reversible')),
                       ('consequence_verify', cons.get('verify')),
                       ('anomaly_title', anom.get('title')),
                       ('anomaly_body', anom.get('body'))):
            tr.add('learn.mission', f, xmlid, en_of(src), vi_of(src))

        for src_key, note_kind in (('did', 'did'), ('checklist', 'check')):
            for n, note in enumerate((m.get('debrief') or {}).get(src_key) or []):
                nx = '%s_%s_%02d' % (xmlid, note_kind, n)
                doc.rec('learn.mission.note', nx, [
                    ('mission_id', ('ref', xmlid)),
                    ('sequence', (n + 1) * 10),
                    ('kind', note_kind),
                    ('body', en_of(note)),
                ])
                tr.add('learn.mission.note', 'body', nx, en_of(note), vi_of(note))

        for k, st in enumerate(steps_by_mission.get(key) or []):
            sx = '%s_step_%02d' % (xmlid, k)
            doc.rec('learn.mission.step', sx, [
                ('mission_id', ('ref', xmlid)),
                ('sequence', (k + 1) * 10),
                ('key', st['id']),
                ('nav', st.get('nav') or ''),
                ('target', st.get('target') or ''),
                ('instruction', en_of(st['instruction'])),
                ('detail', en_of(st.get('detail'))),
                ('hint', en_of(st.get('hint'))),
                ('is_decision', bool(st.get('decision'))),
                ('is_consequence', bool(st.get('consequence'))),
                ('is_undo', bool(st.get('undo'))),
            ])
            for f in ('instruction', 'detail', 'hint'):
                tr.add('learn.mission.step', f, sx, en_of(st.get(f)), vi_of(st.get(f)))

            recovery = st.get('recovery') or {}
            for o, opt in enumerate(st.get('options') or []):
                ox = '%s_opt_%s' % (sx, opt['id'])
                rec = recovery.get(opt['id'])
                if not opt.get('correct') and not en_of(rec).strip():
                    # The model would refuse this at write time; failing here
                    # names the option instead of the record id.
                    raise SystemExit(
                        'mission %s step %s option %s is wrong and offers no '
                        'recovery. A wrong choice must always be met with a way '
                        'back.' % (key, st['id'], opt['id']))
                doc.rec('learn.mission.option', ox, [
                    ('step_id', ('ref', sx)),
                    ('sequence', (o + 1) * 10),
                    ('key', opt['id']),
                    ('label', en_of(opt['label'])),
                    ('is_correct', bool(opt.get('correct'))),
                    ('recovery', en_of(rec)),
                ])
                tr.add('learn.mission.option', 'label', ox,
                       en_of(opt['label']), vi_of(opt['label']))
                if rec:
                    tr.add('learn.mission.option', 'recovery', ox,
                           en_of(rec), vi_of(rec))
    return doc.render()


def gen_columns(data, tr):
    doc = Xml('The per-screen micro-glossary: what a KPI tile or a chip counts. '
              'Curated, not read from ir.model.fields — most of these are '
              'computed tiles with no field behind them to read a help string '
              'from.')
    for screen, cols in data['columns'].items():
        for i, (key, label, body) in enumerate(cols):
            xmlid = 'col_%s_%s' % (slug(screen), slug(key))
            doc.rec('learn.column', xmlid, [
                ('screen', screen),
                ('key', key),
                ('sequence', (i + 1) * 10),
                ('label', en_of(label)),
                ('body', en_of(body)),
            ])
            tr.add('learn.column', 'label', xmlid, en_of(label), vi_of(label))
            tr.add('learn.column', 'body', xmlid, en_of(body), vi_of(body))
    return doc.render()


def gen_sidebar_item(data, tr):
    """The Journey's front door.

    Generated, not hand-written, because the leaf's NAME is content and content
    ships in both languages. Everything else on the record is wiring, and the
    wiring is declared beside the name so the two cannot drift apart.
    """
    leaf = data['sidebarLeaf']
    doc = Xml("The Journey's front door: the pb.sidebar.item that opens it.",
              "groups_id is deliberately EMPTY. A gated leaf hides itself from "
              "users who cannot use it, which is right for a working screen and "
              "wrong for a learning one: someone who cannot open Run Payroll is "
              "exactly the person who needs to read what it is before asking "
              "for access. The Journey marks those stations 'not in your menu' "
              "instead of hiding them.")
    doc.rec('pb.sidebar.item', leaf['xmlid'], [
        ('name', en_of(leaf['name'])),
        ('section_id', ('ref', leaf['section'])),
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
               ' SUB_SCREENS, STATUS_LABELS, CHAINS, POLICY, TAX };\n')
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
    args = ap.parse_args()

    data = dump()
    tr = Trans()
    files = {
        'data/learn_strings.xml': gen_strings(data, tr),
        'data/learn_glossary.xml': gen_glossary(data, tr),
        'data/learn_tenant_slots.xml': gen_overrides(data, tr),
        'data/learn_stations.xml': gen_stations(data, tr),
        'data/learn_lessons.xml': gen_lessons(data, tr),
        'data/learn_intents.xml': gen_intents(data, tr),
        'data/learn_screens.xml': gen_screens(data, tr),
        'data/learn_columns.xml': gen_columns(data, tr),
        'data/learn_missions.xml': gen_missions(data, tr),
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

    if tr.untranslated:
        print('UNTRANSLATED: %d translatable value(s) have no Vietnamese. Every '
              'one of these would reach a Vietnamese reader in English.'
              % len(tr.untranslated))
        for ref, en in tr.untranslated[:20]:
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

    if args.check:
        if changed:
            print('STALE: regenerating would change %d file(s):' % len(changed))
            for c in changed:
                print('  %s' % c)
            print('Run: python3 docs/tutorial_poc/author/tools/gen_learn_data.py')
            return 1
        print('✓ generated data is up to date (%d files)' % len(files))
        return 0

    print('wrote %d file(s), %d unchanged' % (len(changed), len(files) - len(changed)))
    for c in changed:
        print('  %s' % c)
    print('  %d translatable string(s) in vi_VN.po' % len(tr.entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
