#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the Coach's resolver offline, against the GENERATED records.

WHY THIS EXISTS
---------------
Phase D shipped an offline "resolver simulation" that checked two things: that
every intent label still resolves to its own intent, and that no shipped phrase
trips the advice guard. Both passed. The first real-database execution of the
suite then failed five tests, and the simulation had been incapable of seeing
any of them:

  * it never ran a question that should MISS, so it never noticed that
    "how do I change the office wifi password" resolved to "who can change a
    salary" off a single shared six-letter word;
  * it never modelled `learn.column.match`, which consults BOTH languages;
  * it never checked a screen's suggestion chips against that screen, so a
    chip scoped to other screens (`prorata` on contracts / workforcean) looked
    fine.

A mirror that only reflects the cases you already believe in is not a mirror.
This one models the whole of `learn.intent.ask()`'s retrieval order —
advice guard, intent scoring with the ambiguous-word rule, then the column
glossary in both languages — and asserts the same properties the database-bound
tests assert, so the two can only disagree because of something this file does
not model, and that list is written down at the bottom.

Reads: pb_learn/static/content/learn_content.json — the same asset the server
parses and the browser fetches. Not the authoring source, deliberately: what
the server does is decided by what the generator emitted. (Until LEARNOS Phase
1a this read data/learn_{intents,screens,columns}.xml and i18n/vi_VN.po; the
records became one static tree and the Vietnamese arrived beside the English
instead of through a .po lookup, which is the only thing that changed here.)

Usage:  python3 docs/tutorial_poc/author/tools/simulate_resolver.py [-v]
Exit 0 = every property holds. Exit 1 = at least one does not.
"""
import argparse
import io
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHOR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(AUTHOR)))
ADDON = os.path.join(REPO, 'pb_learn')
assert os.path.isdir(ADDON), 'pb_learn not found at %s' % ADDON


# --------------------------------------------------- the real, and the copied
# `_norm`, `_topic_words`, `_is_advice` and the two constants are LIFTED from
# the module — executed out of its source, so they cannot drift.
#
# `score()` and `resolve()` below are NOT: they are methods on a model class
# operating over recordsets, and reimplementing them is the price of running
# without Odoo. That copy is this file's one real weakness, and it is a
# demonstrated one — reverting the ambiguous-word rule in the MODULE left this
# simulation reporting green, because the rule also lives here.
#
# `_assert_no_drift` is the mitigation: the structural markers of the algorithm
# being mirrored are asserted present in the module source, so removing one
# there fails HERE, loudly, instead of silently un-mirroring.
MIRRORED_MARKERS = (
    # the ambiguous-word rule (deploy-round fix)
    'def _ambiguous_words',
    'word not in ambiguous',
    'len(word) >= 6',
    # the four scoring tiers
    'best = max(best, 100)',
    'best = max(best, 80)',
    'best = max(best, 60)',
    'best = max(best, 55)',
    'best = max(best, 40)',
    # the on-screen bonus and the floor
    'best += _ON_SCREEN_BONUS',
    's[0] >= _SCORE_FLOOR',
    # retrieval order in ask()
    "self._match_column(question, screen_key)",
    # the column glossary reading BOTH languages
    "for lang in ('en_US', 'vi_VN')",
    # the content plane is the ONLY source the resolver scores over
    "self.env['learn.content'].intents()",
)


def _load_module_globals():
    src = io.open(os.path.join(ADDON, 'models', 'learn_intent.py'),
                  encoding='utf-8').read()
    missing = [m for m in MIRRORED_MARKERS if m not in src]
    if missing:
        sys.stderr.write(
            'MIRROR DRIFT: learn_intent.py no longer contains %d construct(s) '
            'this simulation reproduces, so what it checks is no longer what '
            'the server does:\n%s\n\nUpdate simulate_resolver.py to match the '
            'module, then update this marker list.\n'
            % (len(missing), '\n'.join('  - %s' % m for m in missing)))
        sys.exit(2)
    ns = {'re': re, 'unicodedata': unicodedata}
    exec(src[src.index('_STOP = {'):src.index('class LearnIntent')], ns)
    return ns


G = _load_module_globals()
_norm, _topic_words, _is_advice = G['_norm'], G['_topic_words'], G['_is_advice']
FLOOR, BONUS = G['_SCORE_FLOOR'], G['_ON_SCREEN_BONUS']


def one(pair, lang='en'):
    """One language out of a `{en, vi}` leaf, tolerating '' and a raw string."""
    if not pair:
        return ''
    if isinstance(pair, str):
        return pair
    return pair.get(lang) or pair.get('en') or ''


def load():
    """The static content plane, as the server reads it."""
    path = os.path.join(ADDON, 'static', 'content', 'learn_content.json')
    with io.open(path, encoding='utf-8') as fh:
        tree = json.load(fh)
    intents = [{'key': i['key'],
                'label': i['label'],
                'screens': i.get('screens') or '*',
                'offer': bool(i.get('offer', True)),
                'phrases': list(i.get('phrases') or [])}
               for i in tree.get('intents') or []]
    by_key = {i['key']: i for i in intents}
    screens = [{'key': s['key'],
                'suggest': [c['key'] for c in (s.get('suggest') or [])
                            if c['key'] in by_key]}
               for s in tree.get('screens') or []]
    columns = [{'screen': c['screen'], 'key': c['key'], 'label': c['label']}
               for c in tree.get('columns') or []]
    return intents, screens, columns


INTENTS, SCREENS, COLUMNS = load()


# ------------------------------------------------------- mirrored behaviour
def ambiguous_words():
    """learn.intent._ambiguous_words, over the generated records."""
    owner, ambiguous = {}, set()
    for intent in INTENTS:
        words = set()
        for phrase in intent['phrases']:
            words |= _topic_words(phrase)
        for word in words:
            if owner.setdefault(word, intent['key']) != intent['key']:
                ambiguous.add(word)
    return ambiguous


AMBIGUOUS = ambiguous_words()


def covers(intent, screen_key):
    raw = (intent['screens'] or '*').strip()
    if raw == '*':
        return True
    return screen_key in [s.strip() for s in raw.split(',') if s.strip()]


def score(question, intent, screen_key):
    nq = _norm(question)
    if not nq:
        return 0
    best = 0
    for phrase in intent['phrases']:
        np = _norm(phrase)
        if not np:
            continue
        if nq == np:
            best = max(best, 100)
        elif np in nq:
            best = max(best, 80)
        elif nq in np and len(nq) >= 6:
            best = max(best, 60)
    if best < 60:
        qw = _topic_words(question)
        for phrase in intent['phrases']:
            shared = qw & _topic_words(phrase)
            if len(shared) >= 2:
                best = max(best, 55)
            elif len(shared) == 1:
                word = next(iter(shared))
                if len(word) >= 6 and word not in AMBIGUOUS:
                    best = max(best, 40)
    if best and screen_key and covers(intent, screen_key) \
            and (intent['screens'] or '*') != '*':
        best += BONUS
    return best


def resolve(question, screen_key=None):
    if _is_advice(question):
        return 'compliance' if any(i['key'] == 'compliance' for i in INTENTS) else None
    scored = [(score(question, i, screen_key), i['key']) for i in INTENTS
              if not screen_key or covers(i, screen_key)]
    scored = [s for s in scored if s[0] >= FLOOR]
    if not scored:
        return None
    scored.sort(key=lambda s: (-s[0], s[1]))
    return scored[0][1]


def column_match(question, screen_key):
    """learn.column.match — and it consults BOTH languages, which is the half
    the Phase D simulation never modelled."""
    if not screen_key:
        return None
    nq = _norm(question)
    if not nq:
        return None
    best, best_len = None, 0
    for col in COLUMNS:
        if col['screen'] != screen_key:
            continue
        for lang in ('en', 'vi'):
            nl = _norm(one(col['label'], lang))
            if nl and len(nl) > 3 and nl in nq and len(nl) > best_len:
                best, best_len = col['key'], len(nl)
    return best


def ask(question, screen_key=None):
    """Returns ('intent', key) | ('column', key) | ('miss', None).

    The composer is not modelled: it is off unless a system parameter is set,
    and when it is on it needs a provider. Its ABSENCE is what this mirrors.
    """
    key = resolve(question, screen_key)
    if key:
        return ('intent', key)
    col = column_match(question, screen_key)
    if col:
        return ('column', col)
    return ('miss', None)


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '')


# ------------------------------------------------------------------ probes
# Questions that MUST miss. Every one is taken from a database-bound test, so
# this file and the suite are asserting the same thing.
MUST_MISS = [
    # tests/test_coach.py::test_10, ::test_22 and test_composer::test_02/_02b
    ("how do I change the office wifi password", ('payruns', 'payslips', 'import')),
    ("where do I book the meeting room", ('payruns', 'payslips')),
    ("what is the office coffee budget", ('payslips',)),
]

# Questions that must reach the advice refusal, from the Phase D review.
MUST_REFUSE = [
    "how do I pay less BHXH", "làm sao giảm BHXH", "how do I reduce the BHXH base",
    "how do I not pay BHXH for probation staff", "tips to lower employer contributions",
    "how do we pay less tax on salaries", "how do we under declare the insurance base",
]

# Questions that must NOT be refused — the core use case.
MUST_ANSWER = [
    "what does BHXH mean", "what is BHXH", "bhxh la gi", "who pays BHTN",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()
    problems = []

    # 1. every suggestion chip resolves to itself ON ITS OWN SCREEN.
    #    Mirrors tests/test_coach.py::test_04 — the check that caught the
    #    prorata chips on contracts and workforcean.
    chips = 0
    for screen in SCREENS:
        for key in screen['suggest']:
            intent = next((i for i in INTENTS if i['key'] == key), None)
            if not intent:
                problems.append('chip %s on %s: no such intent' % (key, screen['key']))
                continue
            chips += 1
            got = resolve(strip_html(one(intent['label'])), screen['key'])
            if got != key:
                problems.append('chip %s on %s resolves to %s'
                                % (key, screen['key'], got))

    # 2. every label self-resolves, in both languages.
    labels = 0
    for intent in INTENTS:
        sk = None if intent['screens'] == '*' else intent['screens'].split(',')[0].strip()
        for lang, text in (('en', one(intent['label'], 'en')),
                           ('vi', one(intent['label'], 'vi'))):
            if not text:
                continue
            labels += 1
            got = resolve(strip_html(text), sk)
            if got != intent['key']:
                problems.append('label %s[%s] resolves to %s'
                                % (intent['key'], lang, got))

    # 3. THE MISSES MUST MISS. The property the Phase D mirror never tested.
    misses = 0
    for question, screens in MUST_MISS:
        for sk in screens:
            misses += 1
            kind, key = ask(question, sk)
            if kind != 'miss':
                problems.append('%r on %s matched %s:%s — it has no content'
                                % (question, sk, kind, key))

    # 4. the advice guard, both directions.
    for question in MUST_REFUSE:
        if not _is_advice(question):
            problems.append('advice not refused: %r' % question)
    for question in MUST_ANSWER:
        if _is_advice(question):
            problems.append('legitimate question refused as advice: %r' % question)

    # 5. nothing the module SHIPS trips the guard, except the refusal's own
    #    trigger phrases.
    for intent in INTENTS:
        for phrase in intent['phrases']:
            if _is_advice(phrase) and intent['key'] != 'compliance':
                problems.append('phrase of %s trips the advice guard: %r'
                                % (intent['key'], phrase))

    # A scan that finds nothing passes vacuously, which is how the Phase D
    # simulation reported green over five real failures. Every counter below
    # has to be non-zero or this file is not checking what it says it checks.
    for label, count in (('suggestion chips', chips), ('labels', labels),
                         ('miss probes', misses), ('intents', len(INTENTS)),
                         ('columns', len(COLUMNS)), ('screens', len(SCREENS))):
        if not count:
            problems.append('the scan found ZERO %s — this simulation is '
                            'broken, not passing' % label)

    print('resolver simulation — against the GENERATED content plane')
    print('  %d intents · %d phrases · %d screens · %d columns · %d ambiguous words'
          % (len(INTENTS), sum(len(i['phrases']) for i in INTENTS),
             len(SCREENS), len(COLUMNS), len(AMBIGUOUS)))
    print('  %d suggestion chips · %d labels x lang · %d miss probes · %d advice probes'
          % (chips, labels, misses, len(MUST_REFUSE) + len(MUST_ANSWER)))
    if args.verbose:
        print('  ambiguous words: %s' % ', '.join(sorted(AMBIGUOUS)))
    if problems:
        print('\n%d PROBLEM(S):' % len(problems))
        for p in problems:
            print('  ✗ %s' % p)
        return 1
    print('\n✓ every property holds.')
    return 0


# WHAT THIS FILE DOES NOT MODEL, and therefore cannot catch — keep this list
# honest, it is the only warning the next person gets:
#   * capability gating (_capability reads real groups and the real sidebar);
#   * the composer (off by default, needs a provider);
#   * live tokens ({{live:...}}) and tenant slot overrides;
#   * record rules, and anything that depends on WHICH user is asking;
#   * the file-backed accessors themselves — this reads learn_content.json with
#     json.load, and learn.content reads it with odoo.tools.file_open. If that
#     helper ever resolved to a different copy of the asset the two would agree
#     about a file the server is not serving.
if __name__ == '__main__':
    sys.exit(main())
