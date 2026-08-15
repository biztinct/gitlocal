#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove that the static content plane says EXACTLY what the ORM records said.

WHY THIS EXISTS
---------------
LEARNOS Phase 1a moved every piece of learning content out of the database and
into one generated asset, `pb_learn/static/content/learn_content.json`. The
whole value of that move rests on a claim nobody can eyeball across 1,260
bilingual leaves: that the PAYLOAD did not change. A learner must not be able
to tell, and neither must a Vietnamese one.

WHAT IT COMPARES, AND WHY NOT THE COMMITTED XML
-----------------------------------------------
Generator against generator, over the SAME authoring source:

  * the OLD emitter is read out of a git revision (`git show <rev>:…
    gen_learn_data.py`) and executed in memory. Its `gen_stations`,
    `gen_lessons`, `gen_intents`, `gen_screens`, `gen_columns`, `gen_missions`,
    `gen_glossary` and `gen_strings` produce the same XML text they always did,
    and its `Trans.render()` produces the matching `vi_VN.po`;
  * those records are parsed back and re-assembled into the payload the server
    used to serve, with the Vietnamese resolved the way Odoo resolves a
    translation (msgid = the source English, fall back to the source when there
    is no msgstr) and with a VERBATIM copy of `_zip_bilingual` / `_zip_prose`;
  * the result is diffed, leaf by leaf, against the new JSON.

Diffing against the COMMITTED `pb_learn/data/*.xml` was the obvious approach
and it is the wrong one: those files were already stale at the revision this
phase started from (`data.js` said "Legacy Odoo salary structures", the
committed `learn_columns.xml` still said "Legacy salary structures"), so a
green run would have been proving that the new pipeline reproduces a file
nobody had regenerated. Same input, two emitters, is the claim that matters.

    python3 docs/tutorial_poc/author/tools/parity_check.py
    python3 docs/tutorial_poc/author/tools/parity_check.py --rev <sha>
    python3 docs/tutorial_poc/author/tools/parity_check.py -v      # 40 diffs

Exit 0 = zero differences outside the documented allowlist · 1 = drift · 2 =
cannot run (the revision no longer carries an emitter with the old entry
points).

KEEP THIS FILE. It is not a one-off: the next time the emission shape is
touched this is what says whether the frontend is still handed what it was
handed before. Point `--rev` at the last revision whose generator still emitted
the XML and it keeps working.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHOR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(AUTHOR)))
ADDON = os.path.join(REPO, 'pb_learn')
assert os.path.isdir(ADDON), 'pb_learn not found at %s' % ADDON

GEN_REL = 'docs/tutorial_poc/author/tools/gen_learn_data.py'

# ---------------------------------------------------------------------------
# DOCUMENTED ALLOWLIST — differences that are correct and intended.
#
# Empty, and that is the claim: Phase 1a is a change of DELIVERY, not of
# payload. Anything added here has to name WHY, because an allowlist is where a
# parity check goes to stop meaning anything.
# ---------------------------------------------------------------------------
ALLOWED = {
    # 'stations[3].outline.why': 'reason the divergence is correct',
}


# =========================================================== the server's zip
# LIFTED VERBATIM from pb_learn/models/learn_station.py as it stood before this
# phase deleted it. Copied rather than imported because the file is gone: this
# is the DEFINITION of the payload being compared against, so it is frozen here
# on purpose and must not be "kept in sync" with anything.
_RAW_KEYS = frozenset({
    'key', 'id', 'icon', 'line', 'section', 'kind', 'anchor', 'screen', 'visual',
    'role', 'value', 'sidebar_key', 'sequence', 'duration_min', 'required',
    'star', 'after', 'visible', 'lesson_key', 'station_key', 'correct',
    'moment_kind', 'moment_chain', 'moment_which', 'moment_from', 'moment_to',
    'capability', 'action_tags', 'action_xmlids', 'models',
    'own_tag', 'own_xmlid',
    'show_me', 'practice_key', 'matched',
    'nav', 'target', 'is_decision', 'is_consequence', 'is_undo',
    'confidence_key', 'confidence_gain',
    'check_key',
})


def _zip_bilingual(en, vi, key=None):
    if isinstance(en, dict) and isinstance(vi, dict):
        return {k: _zip_bilingual(v, vi.get(k), k) for k, v in en.items()}
    if isinstance(en, list) and isinstance(vi, list):
        return [_zip_bilingual(a, vi[i] if i < len(vi) else a, key)
                for i, a in enumerate(en)]
    if isinstance(en, str) and key not in _RAW_KEYS:
        if not en:
            return ''
        return {'en': en, 'vi': vi if isinstance(vi, str) and vi else en}
    return en


def _zip_prose(en, vi):
    return {k: ({'en': v, 'vi': vi.get(k) or v} if v else '') for k, v in en.items()}


# ============================================================ the old emitter
def old_emitter(rev):
    """The generator as it stood at `rev`, executed in memory."""
    try:
        src = subprocess.run(['git', 'show', '%s:%s' % (rev, GEN_REL)],
                             cwd=REPO, capture_output=True,
                             check=True).stdout.decode('utf-8')
    except subprocess.CalledProcessError:
        return None
    ns = {'__name__': 'gen_learn_data_old', '__file__': os.path.join(REPO, GEN_REL)}
    exec(compile(src, GEN_REL + '@' + rev, 'exec'), ns)
    return ns


OLD_ENTRY_POINTS = ('gen_strings', 'gen_glossary', 'gen_stations', 'gen_lessons',
                    'gen_intents', 'gen_screens', 'gen_columns', 'gen_missions')


def old_records_and_po(rev, data):
    """Run the old emitter over `data`; return (records-by-model, msgid->msgstr)."""
    ns = old_emitter(rev)
    if ns is None:
        return None, None, '%s carries no %s' % (rev, GEN_REL)
    missing = [n for n in OLD_ENTRY_POINTS if n not in ns]
    if missing:
        return None, None, ('%s no longer defines %s — point --rev at the last '
                            'revision that emitted the XML'
                            % (rev, ', '.join(missing)))
    tr, live = ns['Trans'](), ns['Live']()
    texts = [
        ns['gen_strings'](data, tr),
        ns['gen_glossary'](data, tr),
        ns['gen_stations'](data, tr),
        ns['gen_lessons'](data, tr),
        ns['gen_intents'](data, tr, live),
        ns['gen_screens'](data, tr, live),
        ns['gen_columns'](data, tr),
        ns['gen_missions'](data, tr),
    ]
    return parse_records(texts), po_map(tr.render()), None


def po_map(text):
    """msgid -> msgstr, full gettext continuation form."""
    pairs, cur, buf, mid = {}, None, [], [None]

    def unescape(raw):
        return raw.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')

    def flush(kind, raw):
        value = unescape(raw)
        if kind == 'msgid':
            mid[0] = value
        elif mid[0] is not None:
            pairs.setdefault(mid[0], value)

    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'^(msgid|msgstr) "(.*)"$', line)
        if m:
            if cur:
                flush(cur, ''.join(buf))
            cur, buf = m.group(1), [m.group(2)]
            continue
        m = re.match(r'^"(.*)"$', line)
        if m and cur:
            buf.append(m.group(1))
            continue
        if cur:
            flush(cur, ''.join(buf))
            cur, buf = None, []
    if cur:
        flush(cur, ''.join(buf))
    pairs.pop('', None)
    return pairs


INT_FIELDS = {'sequence', 'duration_min', 'confidence_gain'}
BOOL_FIELDS = {'required', 'star', 'is_correct', 'is_decision', 'is_consequence',
               'is_undo', 'is_ack', 'offer', 'active', 'show_label'}


class Rec(object):
    __slots__ = ('model', 'xmlid', 'f', 'order')

    def __init__(self, model, xmlid, fields, order):
        self.model, self.xmlid, self.f, self.order = model, xmlid, fields, order

    def s(self, name, default=''):
        val = self.f.get(name, default)
        return val if isinstance(val, str) else default

    def i(self, name, default=0):
        return int(self.f.get(name, default) or 0)

    def b(self, name):
        return bool(self.f.get(name, False))


def parse_records(texts):
    by_model, order = {}, [0]
    for text in texts:
        for rec in ET.fromstring(text).iter('record'):
            fields = {}
            for f in rec.findall('field'):
                name = f.get('name')
                if f.get('ref') is not None:
                    fields[name] = ('ref', f.get('ref'))
                elif f.get('eval') is not None:
                    ev = f.get('eval')
                    if name in BOOL_FIELDS or ev in ('True', 'False'):
                        fields[name] = (ev == 'True')
                    else:
                        fields[name] = ('eval', ev)
                else:
                    raw = f.text or ''
                    fields[name] = int(raw) if name in INT_FIELDS else raw
            order[0] += 1
            by_model.setdefault(rec.get('model'), []).append(
                Rec(rec.get('model'), rec.get('id'), fields, order[0]))
    return by_model


def children(recs, parent_field, parent_xmlid):
    out = [r for r in recs
           if isinstance(r.f.get(parent_field), tuple)
           and r.f[parent_field][0] == 'ref'
           and r.f[parent_field][1] == parent_xmlid]
    out.sort(key=lambda r: (r.i('sequence', 10), r.order))
    return out


# ======================================================= the old payload trees
class Old(object):
    """The old payload, read out of the emitted records.

    `lang` is 'en' or 'vi' for the sections the SERVER built twice and zipped
    (stations, missions, glossary, chrome). For the Coach's own tables — which
    were never served as a single tree — `lang` is None and `t()` returns the
    bilingual pair directly, because zipping a structure the server never
    zipped would only be a test of this file's copy of _RAW_KEYS.
    """

    def __init__(self, by_model, po, lang):
        self.m = by_model
        self.po = po
        self.lang = lang

    def t(self, rec, name, default=''):
        """A TRANSLATABLE field, resolved the way Odoo resolves one."""
        en = rec.s(name, default)
        if self.lang == 'en':
            return en
        if not en:
            return '' if self.lang is None else en
        vi = self.po.get(en) or en
        return vi if self.lang == 'vi' else {'en': en, 'vi': vi}

    # -- chrome ----------------------------------------------------------
    def chrome(self):
        return {r.s('key'): self.t(r, 'value')
                for r in self.m.get('learn.string', [])}

    # -- glossary --------------------------------------------------------
    def glossary(self):
        recs = sorted(self.m.get('learn.glossary.term', []),
                      key=lambda r: (r.i('sequence', 10), r.s('key')))
        return [{'key': r.s('key'), 'term': self.t(r, 'term'),
                 'definition': self.t(r, 'definition')} for r in recs]

    # -- stations --------------------------------------------------------
    def stations(self):
        recs = sorted(self.m.get('learn.station', []),
                      key=lambda r: (r.s('line'), r.i('sequence', 10), r.order))
        return [self.station(r) for r in recs]

    def station(self, r):
        mistakes = children(self.m.get('learn.station.mistake', []),
                            'station_id', r.xmlid)
        lessons = children(self.m.get('learn.lesson', []), 'station_id', r.xmlid)
        return {
            'key': r.s('key'),
            'name': self.t(r, 'name'),
            'line': r.s('line'),
            'section': r.s('section', 'payroll'),
            'sequence': r.i('sequence', 10),
            'summary': self.t(r, 'summary'),
            'icon': r.s('icon', 'circle') or 'circle',
            'kind': r.s('kind', 'outline'),
            'sidebar_key': r.s('sidebar_key'),
            'duration_min': r.i('duration_min', 5),
            'required': r.b('required'),
            'star': r.b('star'),
            'after': r.s('after_key'),
            'outline': {
                'what': self.t(r, 'outline_what'),
                'why': self.t(r, 'outline_why'),
                'when': self.t(r, 'outline_when'),
                'prereq': self.t(r, 'outline_prereq'),
                'mistakes': [self.t(m, 'name') for m in mistakes],
            },
            'lessons': [self.lesson(x) for x in lessons],
        }

    def lesson(self, r):
        steps = children(self.m.get('learn.step', []), 'lesson_id', r.xmlid)
        quizzes = children(self.m.get('learn.quiz', []), 'lesson_id', r.xmlid)
        return {
            'key': r.s('key'),
            'name': self.t(r, 'name'),
            'goal': self.t(r, 'goal'),
            'duration_min': r.i('duration_min', 5),
            'steps': [self.step(s) for s in steps],
            'quizzes': [self.quiz(q) for q in quizzes],
        }

    def step(self, r):
        lines = children(self.m.get('learn.step.line', []), 'step_id', r.xmlid)
        return {
            'kicker': self.t(r, 'kicker'),
            'title': self.t(r, 'title'),
            'body': self.t(r, 'body'),
            'tip': self.t(r, 'tip'),
            'consequence': self.t(r, 'consequence'),
            'screen': r.s('screen'),
            'anchor': r.s('anchor'),
            'visual': r.s('visual', 'none'),
            'moment_from': r.s('moment_from'),
            'moment_to': r.s('moment_to'),
            'moment_chain': r.s('moment_chain'),
            'moment_which': r.s('moment_which'),
            'lines': [{'role': ln.s('role', 'bullet'),
                       'label': self.t(ln, 'label'),
                       'value': ln.s('value'),
                       'note': self.t(ln, 'note')} for ln in lines],
        }

    def quiz(self, r):
        opts = children(self.m.get('learn.quiz.option', []), 'quiz_id', r.xmlid)
        return {
            'kind': r.s('kind', 'choice'),
            'prompt': self.t(r, 'prompt'),
            'options': [{'label': self.t(o, 'label'),
                         'correct': o.b('is_correct'),
                         'feedback': self.t(o, 'feedback')} for o in opts],
        }

    # -- missions --------------------------------------------------------
    def missions(self):
        recs = sorted(self.m.get('learn.mission', []),
                      key=lambda r: (r.i('sequence', 10), r.s('key')))
        return [self.mission(r) for r in recs]

    def mission(self, r):
        notes = children(self.m.get('learn.mission.note', []), 'mission_id', r.xmlid)
        steps = children(self.m.get('learn.mission.step', []), 'mission_id', r.xmlid)
        return {
            'key': r.s('key'),
            'line': r.s('line', 'payrun'),
            'icon': r.s('icon', 'flask') or 'flask',
            'name': self.t(r, 'name'),
            'summary': self.t(r, 'summary'),
            'duration_min': r.i('duration_min', 5),
            'kind': r.s('kind', 'outline'),
            'outline_note': self.t(r, 'outline_note'),
            'screen': r.s('screen'),
            'confidence_key': r.s('confidence_key'),
            'confidence_gain': r.i('confidence_gain', 10),
            'consequence': {
                'title': self.t(r, 'consequence_title'),
                'scope': self.t(r, 'consequence_scope'),
                'reversible': self.t(r, 'consequence_reversible'),
                'verify': self.t(r, 'consequence_verify'),
            },
            'anomaly': {'title': self.t(r, 'anomaly_title'),
                        'body': self.t(r, 'anomaly_body')},
            'steps': [self.mstep(s) for s in steps],
            'did': [self.t(n, 'body') for n in notes if n.s('kind') == 'did'],
            'check': [self.t(n, 'body') for n in notes if n.s('kind') == 'check'],
        }

    def mstep(self, r):
        opts = children(self.m.get('learn.mission.option', []), 'step_id', r.xmlid)
        return {
            'key': r.s('key'),
            'nav': r.s('nav'),
            'target': r.s('target'),
            'instruction': self.t(r, 'instruction'),
            'detail': self.t(r, 'detail'),
            'hint': self.t(r, 'hint'),
            'is_decision': r.b('is_decision'),
            'is_consequence': r.b('is_consequence'),
            'is_undo': r.b('is_undo'),
            'check_key': r.s('check'),
            'is_ack': r.b('is_ack'),
            'options': [{'key': o.s('key'), 'label': self.t(o, 'label'),
                         'correct': o.b('is_correct'),
                         'recovery': self.t(o, 'recovery')} for o in opts],
        }

    # -- the coach -------------------------------------------------------
    def intents(self):
        recs = sorted(self.m.get('learn.intent', []), key=lambda r: r.s('key'))
        return [self.intent(r) for r in recs]

    def intent(self, r):
        phrases = [p for p in self.m.get('learn.intent.phrase', [])
                   if isinstance(p.f.get('intent_id'), tuple)
                   and p.f['intent_id'][1] == r.xmlid]
        phrases.sort(key=lambda p: p.order)
        blocks = children(self.m.get('learn.intent.block', []), 'intent_id', r.xmlid)
        return {
            'key': r.s('key'),
            'label': self.t(r, 'label'),
            'screens': r.s('screens', '*') or '*',
            'dynamic': r.s('dynamic', 'none'),
            'show_me': [a.strip() for a in r.s('show_me').split(',') if a.strip()],
            'simpler': self.t(r, 'simpler'),
            'practice_key': r.s('practice_key'),
            'offer': bool(r.f.get('offer', True)),
            'phrases': [p.s('text') for p in phrases],
            'blocks': [self.block(b) for b in blocks],
        }

    def block(self, r):
        steps = children(self.m.get('learn.intent.step', []), 'block_id', r.xmlid)
        return {
            'capability': r.s('capability', 'any'),
            'kind': r.s('kind', 'p'),
            'body': self.t(r, 'body'),
            'live_fallback': self.t(r, 'live_fallback'),
            'steps': [{'text': self.t(s, 'text'), 'anchor': s.s('anchor')}
                      for s in steps],
        }

    def screens(self):
        recs = sorted(self.m.get('learn.screen', []),
                      key=lambda r: (r.i('sequence', 10), r.s('key')))
        by_xmlid = {i.xmlid: i for i in self.m.get('learn.intent', [])}
        out = []
        for r in recs:
            chips = []
            raw = r.f.get('suggest_ids')
            if isinstance(raw, tuple) and raw[0] == 'eval':
                for xid in re.findall(r"ref\('(?:pb_learn\.)?([A-Za-z0-9_]+)'\)",
                                      raw[1]):
                    hit = by_xmlid.get(xid)
                    if hit:
                        chips.append({'key': hit.s('key'),
                                      'label': self.t(hit, 'label')})
            out.append({
                'key': r.s('key'),
                'sequence': r.i('sequence', 10),
                'name': self.t(r, 'name'),
                'blurb': self.t(r, 'blurb'),
                'next_step': self.t(r, 'next_step'),
                'live_fallback': self.t(r, 'live_fallback'),
                'action_tags': r.s('action_tags'),
                'sidebar_key': r.s('sidebar_key'),
                'suggest': chips,
            })
        return out

    def columns(self):
        recs = sorted(self.m.get('learn.column', []),
                      key=lambda r: (r.s('screen'), r.i('sequence', 10), r.s('key')))
        return [{'screen': r.s('screen'), 'key': r.s('key'),
                 'sequence': r.i('sequence', 10),
                 'label': self.t(r, 'label'), 'body': self.t(r, 'body')}
                for r in recs]

    def global_suggest(self):
        pool = [r for r in self.m.get('learn.intent', [])
                if (r.s('screens', '*') or '*') == '*' and r.f.get('offer', True)]
        pool.sort(key=lambda r: r.s('key'))
        return [{'key': r.s('key'), 'label': self.t(r, 'label')} for r in pool[:6]]


# ==================================================================== diffing
def walk_diff(path, a, b, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(('%s.%s' % (path, k), '<absent>', b[k]))
            elif k not in b:
                out.append(('%s.%s' % (path, k), a[k], '<absent>'))
            else:
                walk_diff('%s.%s' % (path, k), a[k], b[k], out)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(('%s[]' % path, 'len %d' % len(a), 'len %d' % len(b)))
        for i in range(min(len(a), len(b))):
            walk_diff('%s[%d]' % (path, i), a[i], b[i], out)
        return
    if a != b:
        out.append((path, a, b))


def leaves(node):
    if isinstance(node, dict):
        if set(node) == {'en', 'vi'}:
            return 1
        return sum(leaves(v) for v in node.values())
    if isinstance(node, list):
        return sum(leaves(v) for v in node)
    return 1


def _short(v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 150 else s[:150] + '…'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rev', default='HEAD',
                    help='git revision whose generator still emitted the XML')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    data = json.loads(subprocess.run(
        ['node', os.path.join(HERE, 'dump_content.js')],
        capture_output=True, check=True).stdout.decode('utf-8'))

    by_model, po, err = old_records_and_po(args.rev, data)
    if err:
        print('cannot run: %s' % err)
        return 2

    en, vi = Old(by_model, po, 'en'), Old(by_model, po, 'vi')
    bi = Old(by_model, po, None)
    old = {
        # Served as ONE zipped tree by learn.station.get_bundle — rebuilt the
        # same way, twice and zipped.
        'chrome': _zip_prose(en.chrome(), vi.chrome()),
        'stations': _zip_bilingual(en.stations(), vi.stations()),
        'missions': _zip_bilingual(en.missions(), vi.missions()),
        'glossary': _zip_bilingual(en.glossary(), vi.glossary()),
        # The Coach's tables. Never one tree on the wire, so the pairs are
        # built at the leaf instead of zipped over a structure.
        'intents': bi.intents(),
        'screens': bi.screens(),
        'columns': bi.columns(),
        'global_suggest': bi.global_suggest(),
    }

    with io.open(os.path.join(ADDON, 'static/content/learn_content.json'),
                 encoding='utf-8') as fh:
        new = json.load(fh)

    diffs = []
    for section in sorted(old):
        walk_diff(section, old[section], new.get(section), diffs)
    diffs = [d for d in diffs if d[0] not in ALLOWED]

    print('parity — old emitter @%s vs static/content/learn_content.json' % args.rev)
    print('  %s' % ' · '.join(
        '%s %d' % (s, len(old[s])) for s in sorted(old)))
    print('  %d comparable leaves (prose pairs + raw scalars)'
          % sum(leaves(old[s]) for s in old))
    if ALLOWED:
        print('  allowlist: %d documented divergence(s)' % len(ALLOWED))

    if diffs:
        cap = 40 if args.verbose else 10
        print('\n%d DIFFERENCE(S):' % len(diffs))
        for path, a, b in diffs[:cap]:
            print('  ✗ %s\n      old: %s\n      new: %s'
                  % (path, _short(a), _short(b)))
        if len(diffs) > cap:
            print('  … %d more' % (len(diffs) - cap))
        return 1
    print('\n✓ ZERO differences. Every prose leaf and raw scalar is identical.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
