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
    # the ambiguous-word rule (deploy-round fix), now applied to the shared
    # SET so that BOTH overlap tiers count discriminating words only
    # (Phase 4 review: two ambiguous words bought the 55 tier)
    'def _ambiguous_words',
    'strong = (qw & _topic_words(phrase)) - ambiguous',
    'if len(strong) >= 2:',
    'elif len(strong) == 1:',
    'len(word) >= 6',
    # a tie AT the floor is a miss, not an alphabetical coin toss
    'if len(scored) > 1 and scored[0][0] == floor and scored[1][0] == floor:',
    # the four scoring tiers
    'best = max(best, 100)',
    'best = max(best, 80)',
    'best = max(best, 60)',
    'best = max(best, 55)',
    'best = max(best, 40)',
    # the on-screen bonus and the two floors (LEARNOS Phase 4 raised the
    # screenless one; mirroring only the constant would let the module go back
    # to one floor while this file kept reporting green)
    'best += _ON_SCREEN_BONUS',
    '_SCREENLESS_FLOOR = 55',
    'floor = _SCORE_FLOOR if screen_key else _SCREENLESS_FLOOR',
    's[0] >= floor',
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
SCREENLESS_FLOOR = G['_SCREENLESS_FLOOR']


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
            # Discriminating words only, for BOTH tiers — Phase 4 review.
            strong = (qw & _topic_words(phrase)) - AMBIGUOUS
            if len(strong) >= 2:
                best = max(best, 55)
            elif len(strong) == 1:
                word = next(iter(strong))
                if len(word) >= 6:
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
    # LEARNOS Phase 4: off the map the bar is the two-shared-word tier, so a
    # single shared word can no longer buy a badged answer.
    floor = FLOOR if screen_key else SCREENLESS_FLOOR
    scored = [s for s in scored if s[0] >= floor]
    if not scored:
        return None
    scored.sort(key=lambda s: (-s[0], s[1]))
    # A tie AT the floor is the weakest hit accepted, twice, with nothing to
    # choose between them — an alphabetical coin toss, badged. Above the floor
    # a tie is two real matches and the sort may keep it.
    if len(scored) > 1 and scored[0][0] == floor and scored[1][0] == floor:
        return None
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

# ------------------------------------------------------ the screenless pair
# LEARNOS PHASE 4. The Coach is mounted everywhere, and on the surfaces the
# content plane does not cover — the Journey itself, an ordinary list view —
# `screen_key` is None. The live validation found that a single shared topic
# word (score 40) then cleared the floor of 20 and produced a "Grounded in"
# badge over a wrong-topic answer. Both halves of that finding are probed
# here, because a floor that only stops wrong answers is one somebody will
# raise until it stops right ones too.
#
# 1. THE WRONG-TOPIC MATCHES. EVERY ONE OF THESE MUST BE DECIDED BY A RULE
#    THIS FILE IS TESTING — a probe that misses anyway is not a probe, it is a
#    line that makes the count look bigger. The Phase 4 review caught one of
#    those here ("the office wifi password" missed at BOTH floors, because it
#    shares no long word with anything) and it has been replaced. The score
#    each one reaches with the rules OFF is written beside it.
#
#    Payobook has no content about any of these and never will; they are not
#    corpus gaps, they are questions for somebody in HR.
SCREENLESS_MUST_MISS = [
    # 40 against `whichpolicy` on `policy` alone. Stopped ONLY by the
    # screenless floor: at 20 it resolves and is badged "Grounded in".
    "what is the overtime policy for interns",
    # 40 against BOTH `whichpolicy` and `whichfilings`. Stopped by the floor,
    # and by the tie rule if the floor were ever lowered to 40.
    "what is the company holiday policy",
    # 55 against BOTH `howrun` and `whydiff` BEFORE the ambiguous filter was
    # applied to the two-word tier; it is the probe that fix was written for.
    # It now scores ZERO, because `pay`, `run` and `month` are all ambiguous —
    # so it no longer exercises TIE-AT-FLOOR, which is what the next entry is
    # for. (Recorded rather than quietly re-labelled: the first draft of this
    # list claimed it was the tie probe, which was the MINOR-3 mistake the
    # review had just corrected, made again one layer down.)
    "what is the pay run for this month",
    # THE TIE PROBE, and it is a question somebody actually asks on a Setup
    # screen. `insurance`/`base`/`ceiling` are two strong words of `ceiling`;
    # `safe`/`edit`/`live` are two strong words of `editlive`. Both reach 55,
    # neither reaches higher, and the sort's second key is the intent KEY — so
    # without TIE-AT-FLOOR the answer is `ceiling`, chosen alphabetically over
    # `editlive`, for a question that is honestly BOTH. Off the map there is
    # no screen to break the tie and no screen for the reader to check the
    # answer against, so the honest miss names what the Coach can answer.
    "is the insurance base and ceiling safe to edit live",
    # `pay` + `month`, both ambiguous. Before the Phase 4 review the 55 tier
    # topic words {pay, staff}: `pay` is ambiguous, `staff` is not in any
    # howrun phrase's topic set as a pair with it — with the ambiguous filter
    # DISABLED this resolves to `howrun` on the weak overlap (verified by
    # executing the control, re-review round 2). Stopped by the ambiguous
    # filter on the two-word tier. (The neighbouring "how do i pay my staff"
    # is a legitimate HIT, because `howrun` gained that exact phrase.)
    "when do i pay my staff",
]

# 2. THE LEGITIMATE SCREENLESS HITS THAT MUST KEEP WORKING. Raising a floor is
#    only safe if something proves what is still above it. Each of these
#    resolves off a real hit rather than off one shared word: an exact label
#    (100), a phrase contained in the question (80), or a question contained
#    in a phrase (60). `howrun` is in this list deliberately — it is the
#    question the whole fix started from, and the pair of changes has to leave
#    it ANSWERED rather than merely un-badged.
#    THE PAY-FAMILY VARIANTS ARE HERE BECAUSE OF THE REVIEW. Almost nobody
#    asks how to "run payroll"; they ask how to pay their staff. Every one of
#    these was answered by `whydiff` before Phase 4 — a lesson about why one
#    person's salary moved — and tightening the score alone would have turned
#    all five into honest misses, which is better and still not an answer. The
#    scoring fix and the phrases `howrun` gained are one fix, and this list is
#    what stops the next person tightening the floor until they stop working.
SCREENLESS_MUST_HIT = [
    ("how do I correct a mistake in a payslip", 'fixerror'),
    ("how do i run payroll", 'howrun'),
    ("how do i pay my staff this month", 'howrun'),
    ("how do i pay everyone", 'howrun'),
    ("how do i pay people", 'howrun'),
    ("how do we pay everyone this month", 'howrun'),
    ("tra luong cho nhan vien the nao", 'howrun'),
    ("let me practise this safely on the fake company", 'practice'),
    ("what should i do next", 'whatnext'),
    ("sửa lỗi", 'fixerror'),
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

    # 3b. THE SCREENLESS PAIR (Phase 4). Both directions, and the second is
    #     the one that stops the floor being raised until nothing gets through.
    screenless = 0
    for question in SCREENLESS_MUST_MISS:
        screenless += 1
        kind, key = ask(question, None)
        if kind != 'miss':
            problems.append('%r off the map matched %s:%s on a weak score — a '
                            'badged wrong answer is worse than a miss'
                            % (question, kind, key))
    for question, expected in SCREENLESS_MUST_HIT:
        screenless += 1
        kind, key = ask(question, None)
        if (kind, key) != ('intent', expected):
            problems.append('%r off the map should still resolve to %s, got '
                            '%s:%s' % (question, expected, kind, key))

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
                         ('screenless probes', screenless),
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
    print('  %d screenless probes (%d must miss, %d must still hit) · floors %d/%d'
          % (screenless, len(SCREENLESS_MUST_MISS), len(SCREENLESS_MUST_HIT),
             FLOOR, SCREENLESS_FLOOR))
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
