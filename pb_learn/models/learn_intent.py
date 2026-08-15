# -*- coding: utf-8 -*-
"""The Payobook Coach's resolver.

The Coach answers ONLY from written blocks. There is no path from a question to
the screen that does not pass through something an author wrote — which is what
lets it promise never to invent a rate, a threshold or a tax figure.

WHERE THOSE BLOCKS LIVE, SINCE PHASE 1a: the static content plane,
`pb_learn/static/content/learn_content.json`, reached through
`self.env['learn.content']`. The intents, screens and column glossary used to
be ORM records; the promise is unchanged and so is the response contract of
`ask()` — coach.js was not touched. What changed is that the material is now
identical on every tenant and cannot be edited into something an author did not
write.

The resolver is deterministic retrieval. `_resolve_hook` is the one seam where
an LLM could be plugged in later; note its contract, which is the whole point:
it returns an intent KEY chosen from the candidates, never text. A model may
choose what to say; it may not say it.

PHASE D adds ONE exception, and it is fenced: the composer (`_compose`). It is
off unless a system parameter turns it on, it is reached only after curated
retrieval and the column glossary have both missed, the advice deny-list runs
before it, and the only material it is given is this module's own tutorial
text — never a database record. What it writes is badged so the reader knows
which kind of answer they are holding.

PHASE 4 adds a second entry point and no second promise: `explain_screen`
answers "what is this screen" with no question typed, and its DETERMINISTIC
FLOOR — blurb, next step, the screen's own columns — is built and returned
before the composer flag is even read. A provider may rewrite that floor and
can never replace it, under the same gates and the same badge.

NOTE TO THE NEXT READER: `contract.json::coach-answers-from-writing-only`
greps this file whole, prose included, for the tokens that must never appear
here — a product model name, raw SQL, or another module's provider registry.
Say "a product model" rather than naming one, as everything below does.
"""
import logging
import re
import unicodedata

from odoo import api, models

_logger = logging.getLogger(__name__)

# Words that carry no topic. Without this, "what should I do to pay less BHXH"
# matched "what does this page do" on the word "what" alone and the Coach
# answered a compliance question with a UI tour. Vietnamese entries are stored
# diacritic-folded, because that is how they arrive from _norm.
_STOP = {
    # English
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'am', 'do', 'does',
    'did', 'can', 'could', 'should', 'would', 'will', 'shall', 'may', 'might',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its', 'this', 'that',
    'these', 'those', 'what', 'when', 'where', 'which', 'who', 'whom', 'how',
    'why', 'to', 'of', 'in', 'on', 'at', 'for', 'from', 'with', 'and', 'or',
    'not', 'if', 'then', 'so', 'here', 'there', 'get', 'got', 'have', 'has',
    'had', 'about', 'please', 'thing', 'things', 'one',
    # Vietnamese, folded
    'la', 'gi', 'nao', 'sao', 'the', 'nay', 'do', 'co', 'khong', 'toi', 'ban',
    'minh', 'cua', 'va', 'hay', 'thi', 'lam', 'duoc', 'cho', 'voi', 'tren',
    'trong', 'khi', 'nhu', 'de', 'bi', 'se', 'da', 'dang', 'mot', 'nhung',
    'nao', 'ai', 'dau', 'vi', 'ma', 'ra', 'len', 'xuong', 'phai',
    # 'bao nhieu' is Vietnamese for 'how much / how many'. Without it, any
    # quantity question scores against every rate intent on the quantity word
    # alone, and the Coach answers the wrong one confidently.
    'bao', 'nhieu', 'may',
}

# Tax- and law-advice questions, refused BEFORE retrieval rather than scored
# against it.
#
# This is a safety boundary, not a matching problem. "làm sao giảm đóng BHXH"
# (how do I pay less social insurance) shares real topic words with the `bhxh`
# glossary intent, which explains what the 8% is — so retrieval scores it as a
# hit and the Coach answers "how do I under-declare" with the contribution
# rates. On a payroll system that reads as instruction. Confidently off-target
# about a statutory obligation is the one failure mode worth a deny-list.
#
# The refusal is not a dead end: the `compliance` intent teaches where the rates
# live and who owns the policy. It never advises minimising an obligation.
#
# Stored diacritic-folded, matched against the folded question.
_ADVICE_MARKERS = (
    # English. Written in NORMALISED form — _norm has already turned every
    # punctuation mark into a space, so a hyphen here would never match.
    'under declare', 'underdeclare', 'avoid tax', 'evade',
    'reduce bhxh legally', 'tax loophole', 'pay less tax',
    # Vietnamese, folded
    'tron thue', 'khai thap', 'giam dong bhxh', 'lach',
)

# THE MARKER LIST WAS A LIST OF SENTENCES SOMEBODY HAD ALREADY THOUGHT OF, and
# a deny-list of exact phrasings is a deny-list of the phrasings that occurred
# to its author. Five of them were demonstrated in review, every one obviously
# in scope and every one missed:
#
#   "how do I pay less BHXH"          — 'pay less tax' needs the word tax
#   "làm sao giảm BHXH"               — 'giam dong bhxh' needs the word đóng
#   "how do I reduce the BHXH base"   — 'reduce bhxh legally' needs 'legally'
#   "how do I not pay BHXH for probation staff"
#   "tips to lower employer contributions"
#
# So the guard is now a TOKEN PAIR as well: a statutory subject standing beside
# a minimisation verb. Neither half is suspicious alone — "what does BHXH mean"
# is the question this system exists for, and "how do I pay less" without a
# statutory subject is somebody asking about a discount. Together they are a
# request for help reducing a statutory obligation, however it is phrased.
#
# Single-word tokens are matched as WHOLE TOKENS, not as substrings. `ne`
# (Vietnamese for dodge) inside "net", or `bot` inside "bottom", would refuse
# half the payroll questions in the module.
#
# KNOWN AND ACCEPTED OVER-CAPTURE: "why is my insurance contribution lower this
# month" pairs `insurance` with `lower` and is refused. It is a fair question,
# and the refusal is not a dead end — the `compliance` intent explains where
# the rates live and who owns the policy, which is a reasonable answer to it.
# On a statutory obligation, over-refusing is the direction to err in.
_STATUTORY_WORDS = frozenset((
    'bhxh', 'bhyt', 'bhtn', 'pit', 'tncn', 'thue',
    'contribution', 'contributions', 'insurance',
))
_STATUTORY_PHRASES = ('bao hiem',)

_MINIMISE_WORDS = frozenset((
    'less', 'lower', 'reduce', 'cut', 'avoid', 'save', 'skip',
    'giam', 'tranh', 'bot', 'ne',
))
_MINIMISE_PHRASES = ('not pay', 'khong dong')


def _has_token(nq, tokens, words, phrases):
    return bool(tokens & words) or any(p in nq for p in phrases)


def _is_advice(question):
    nq = _norm(question)
    if any(m in nq for m in _ADVICE_MARKERS):
        return True
    tokens = set(nq.split())
    return (_has_token(nq, tokens, _STATUTORY_WORDS, _STATUTORY_PHRASES)
            and _has_token(nq, tokens, _MINIMISE_WORDS, _MINIMISE_PHRASES))


_SCORE_FLOOR = 20
_ON_SCREEN_BONUS = 25

# THE SCREENLESS FLOOR (LEARNOS Phase 4).
#
# The Coach is mounted on every screen, and on the ones the content plane does
# not cover — the Journey itself, an ordinary list view, somebody else's
# cockpit — `screen_key` is None. Two things are then true at once: there is no
# on-screen bonus to separate the candidates, and there is no screen for the
# reader to check the answer against. The live validation found what that
# combination does.
#
# "How do I run payroll" had no content at all. It shared exactly one topic
# word with `payrollready` ("payroll", long enough and not ambiguous), scored
# 40, cleared the floor of 20 and was rendered under a "Grounded in" badge.
# WITH a screen the same question honestly missed, because the on-screen bonus
# went to intents that cover that screen and the stray 40 lost. A badged wrong
# answer is worse than a miss: the badge is the Coach saying "I read this
# somewhere", which is exactly the promise the module is built on.
#
# Worse than one wrong answer: "what is the company holiday policy" scored 40
# against BOTH `whichpolicy` and `whichfilings`, and the tie was broken
# alphabetically by key. A coin toss, badged.
#
# So a screenless question needs a REAL hit. 55 is the two-shared-topic-word
# tier, which is the smallest score `_score` gives that cannot come from a
# single word — the handover's "≥2 strong token hits when screen_key is null",
# expressed as the floor rather than as a second rule inside the scorer.
# Everything above it still works screenless: an exact label (100), a phrase
# contained in the question (80) and a question contained in a phrase (60).
#
# The corpus gap and this floor are ONE fix, and neither alone was enough. The
# floor turns a badged wrong answer into an honest miss; `howrun` turns the
# honest miss into an answer.
_SCREENLESS_FLOOR = 55


def _norm(text):
    """Lowercase, strip diacritics, fold đ, drop punctuation.

    Vietnamese is typed with and without tone marks depending on the keyboard
    and the hurry, so a matcher that needs the marks matches nothing when it is
    needed most.
    """
    s = (text or '').lower().replace('đ', 'd')
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9\s]+', ' ', s).strip()


def _topic_words(text):
    return {w for w in _norm(text).split() if w and w not in _STOP and len(w) > 1}


# ======================================================================
# THE COMPOSER'S CONSTANTS — see LearnIntent._compose
# ======================================================================
# Off unless this is explicitly set true. Absent means off, which is what an
# upgraded tenant gets and what every test that does not set it gets.
COMPOSE_FLAG = 'pb_learn.compose_enabled'

# THE CAP, AND WHY IT MOVED (LEARNOS Phase 4).
#
# It was 12,000 characters, the glossary was appended LAST, and the glossary is
# 12,680 characters on its own. On `payslips` the screen block and the intent
# blocks came to 12,559 before the glossary started, so the composer had been
# shipped a corpus in which NO glossary term ever appeared — and every term
# added since Phase C1 (waterfall, drill, cost per head, filing) had never
# reached it at all. Measured, not estimated, and re-measured after this
# phase's six new intents AND after `_wire_leaf` began substituting the
# authored fallback for a live token: the widest screen's full corpus is
# **30,486** characters (payslips, Vietnamese). Every one of the twenty
# screens was over the old cap in both languages.
#
# (An earlier draft of this comment said 30,558 — the figure from a
# scratch script that predated `_wire_leaf`. The number a comment states
# about its own code has to come from that code; `test_04d` computes it.)
#
# 36,000 fits all forty screen-language pairs with about 15% headroom, and
# `test_explain::test_04d` re-measures on every run rather than trusting this
# paragraph — it is what caught this phase's six new intents pushing the
# widest past a first attempt at 30,000. The truncation is what happens when
# content
# outgrows even this: a SECTION is dropped whole, with a log line naming it.
# Never mid-entry — half a glossary definition in a prompt is a definition the
# model completes for itself.
_CORPUS_CAP = 36000
_QUESTION_CAP = 400
_REPLY_CAP = 1500

# Order matters more than the cap does, because the cap only bites at the end
# of this list. Ordered by what actually answers a question about a screen:
# the screen's own material first, then the intents scoped to it, then the
# vocabulary, and columns last because a column definition only helps a
# question that names the column — and a question that names a column never
# reaches the composer, since `_match_column` catches it two steps earlier.
_CORPUS_SECTIONS = ('screen', 'intents', 'glossary', 'columns')


def _ascii(text):
    """Tone marks stripped, đ folded, case PRESERVED.

    `_norm` is for matching and destroys the string. This one is for building
    the second form of a name a learner might type: somebody in a hurry types
    "Nguyen Thi Mai", and a scrub list that only knows the accented spelling
    lets the unaccented one through — which is the spelling most likely to be
    typed on a shop-floor keyboard.
    """
    s = (text or '').replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


# The people in the practice fixture. A learner reading a lesson about Mai's
# payslip and then asking the Coach about it types her name, and that name
# would otherwise travel to a hosted provider.
#
# THIS IS A REDUCTION, NOT A GUARANTEE, and it is important not to oversell
# it: the demo world holds thousands of generated names and this list holds
# six. What makes the composer safe is that the CORPUS contains no records at
# all — the scrub is a second fence around the one free-text field a person
# can type anything into.
#
# `contract.json::composer-scrubs-the-fixture-names` pins these against the
# fixture, so a renamed character breaks the build rather than quietly
# leaving the list stale.
FIXTURE_NAMES = (
    'Nguyễn Thị Mai', 'Trần Văn Hùng', 'Lê Thu Trang', 'Phạm Minh Đức',
    'Bùi Anh Tuấn', 'Đỗ Thị Lan',
)

_NAME_RE = re.compile(
    '|'.join(sorted(
        {re.escape(v) for n in FIXTURE_NAMES for v in (n, _ascii(n))},
        key=len, reverse=True)),
    re.IGNORECASE)

# Digit groups written the way money is written — 4.200.000 or 4,200,000.
# Applied through a callback so that a bare "10,5" (a rate, in Vietnamese
# decimal notation) survives: a rate is not personal data, and scrubbing it
# would make the question meaningless while protecting nobody.
_GROUPED_DIGITS = re.compile(r'\b\d{1,3}(?:[.,]\d{3})+\b')

# A number wearing a currency mark is money whatever its size, so this one runs
# BEFORE the grouped-digit rule — otherwise the digits are replaced first and
# the mark is left stranded beside the placeholder.
#
# THE TRAILING BOUNDARY MUST NOT BE `\b`. `₫` is not a word character, so `\b`
# after it requires a word character to follow — which at the end of a sentence
# there never is. The rule therefore failed on exactly the input it was written
# for ("12.000.000 ₫") and the grouped-digit rule cleaned up the digits behind
# it, producing "[amount] ₫": a redaction that visibly missed. `(?!\w)` asserts
# "not followed by a word character", which is what was meant.
#
# `đồng` is spelled out before `đ` so the longer form wins the alternation
# outright rather than by backtracking.
_CURRENCY_AMOUNT = re.compile(
    r'\b\d[\d.,]*\s*(?:₫|vnđ|vnd|đồng|dong|đ)(?!\w)', re.IGNORECASE)

# Anything that looks like it identifies a person or a record, scrubbed from
# the question before it leaves this server. These four are health_learn's,
# unchanged; the two payroll-grade ones above are new here.
#
# THERE IS A SECOND COPY OF THIS FAMILY, and it is deliberate:
# `pb_payroll_ai_insights/models/ai_redaction.py` carries `_ascii` and these
# patterns for PayAI's two legacy egress paths. Not imported in either
# direction — pb_learn's dependency on PayAI is soft on purpose, and a
# cross-addon import for four regexes would make each uninstallable without
# the other. If a pattern is fixed here, fix it there; the pointer is written
# on both ends so neither copy can be found without the other.
# A Vietnamese number is written "+84 912 345 678" as often as "+84912345678",
# and health_learn's pattern demanded a digit IMMEDIATELY after the country
# code — so the spaced international form, which is the one people paste out of
# a contact card, walked straight through. One optional separator fixes it.
_SCRUB = (
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b'), '[email]'),
    (re.compile(r'(?:\+?84|0)[\s.-]?\d[\d\s.-]{7,}\d'), '[phone]'),
    (re.compile(r'#\d{2,}'), '[record]'),
    (re.compile(r'\b\d{6,}\b'), '[number]'),
)




# ======================================================================
# BILINGUAL LEAVES
# ======================================================================
# The content plane ships every prose leaf as `{en, vi}` and every raw scalar
# raw, so the old read-twice-and-zip (`learn_station._zip_bilingual`) is gone
# with the records it read. What is left is the two places an answer contains
# something the content could NOT ship: a live value substituted into a
# sentence, and a composed reply. Both are built here, to the same rule the zip
# applied — an empty English side stays the empty STRING, because a truthy
# `{"en": "", "vi": ""}` makes every `field ? render : ""` in the drawer draw an
# empty card.
def _pair(en, vi=None):
    if not en:
        return ''
    return {'en': en, 'vi': vi or en}


def _one(pair, lang='en_US'):
    """One language out of a leaf. Tolerates '' and a raw string."""
    if not pair:
        return ''
    if isinstance(pair, str):
        return pair
    return pair.get('vi' if str(lang or '').startswith('vi') else 'en') \
        or pair.get('en') or ''


def _label_body(label, body):
    """"<b>Label</b> — definition", as a bilingual leaf.

    Both halves are AUTHORED content out of the module's own bundle — the same
    trust class as every other answer body, which is why the label is embedded
    as markup rather than escaped. Nothing a tenant or a learner types reaches
    this function; the one thing that does, a tenant slot value, arrives
    escaped through `gtx` at the point of insertion (LEARNOS Phase 2).
    """
    out = {}
    for tag, lang in (('en', 'en_US'), ('vi', 'vi_VN')):
        lab, txt = _one(label, lang), _one(body, lang)
        out[tag] = ('<b>%s</b> — %s' % (lab, txt)) if lab else txt
    return _pair(out['en'], out['vi'])


def _chrome_pair(content, key):
    """One chrome string as a bilingual leaf, for a payload the drawer draws
    as a heading. `chrome_text` falls back to the KEY rather than to silence,
    which is the behaviour wanted here too."""
    return _pair(content.chrome_text(key, 'en_US'),
                 content.chrome_text(key, 'vi_VN'))


# ======================================================================
# WHAT A PROMPT MAY CARRY (LEARNOS Phase 4)
# ======================================================================
# The content plane holds TWO kinds of placeholder, and they need opposite
# treatment on the way to a provider. Getting that backwards is how a tenant's
# own text ends up on a wire, so it is written out rather than inferred.
#
# `{{gmTierName}}` — a TENANT FACT SLOT. The VALUE is typed by a tenant
#   administrator and lives in `learn.tenant.override`. It is NEVER substituted
#   on this path: the content plane ships the authored sentence with the
#   placeholder still in it, and only the browser resolves one. So what leaves
#   this server is the KEY, which this module wrote, and no tenant text at all.
#   The token is KEPT rather than stripped, for two reasons: stripping it
#   leaves "then , then , then done", which is a worse thing to hand a model
#   than a brace pair; and if the model copies it into its answer, the drawer's
#   `gtx()` resolves it for the reader exactly as it resolves an authored one.
#
# `{{live:june_run_state}}` — a LIVE VALUE, read out of the DATABASE by
#   `learn.live`. Its key is ours, but nothing downstream can resolve one in a
#   composed answer (the browser has no live values; the server renders them
#   only into authored leaves), so a model that echoed it would print a brace
#   pair to the reader. It is replaced by the authored `live_fallback` — the
#   sentence every tenant that is not the demo world already reads, which the
#   generator refuses to let an author omit. Where there is no fallback it is
#   dropped, and the surrounding whitespace tidied.
_LIVE_TOKEN_RE = re.compile(r'\{\{live:[a-z_]+\}\}')


def _wire_leaf(leaf, fallback, lang):
    """One language of an authored leaf, made safe to put in a prompt."""
    text = _one(leaf, lang)
    if not _LIVE_TOKEN_RE.search(text or ''):
        return text
    substitute = _one(fallback, lang)
    if substitute:
        return substitute
    return re.sub(r'[ \t]{2,}', ' ', _LIVE_TOKEN_RE.sub('', text)).strip()


def _covers_screen(intent, screen_key):
    raw = (intent.get('screens') or '*').strip()
    if raw == '*':
        return True
    return screen_key in [s.strip() for s in raw.split(',') if s.strip()]


# ======================================================================
# THE CORPUS, AS A PURE FUNCTION (LEARNOS Phase 4)
# ======================================================================
# It takes the parsed content tree and returns a string. No recordset, no
# registry, no database — which is the point twice over:
#
#   * it is the exact text that goes on the wire, so it can be asserted
#     offline, character for character, by a harness with no Odoo
#     (`tools/replay_tests.py`);
#   * a function whose only input is the content tree cannot reach a payroll
#     table, and that is a property a reader can check by looking at the
#     signature rather than by trusting a paragraph.
#     `contract.json::corpus-builder-is-pure` asserts it anyway.
#
# TREAT THE TREE AS IMMUTABLE. It is one shared dict per worker process (see
# learn_content.py), so nothing below may write to it.
def _corpus_screen_part(tree, screen, lang):
    parts = ['SCREEN: %s — %s' % (_one(screen['name'], lang),
                                  _one(screen.get('blurb'), lang))]
    next_step = _wire_leaf(screen.get('next_step'),
                           screen.get('live_fallback'), lang)
    if next_step:
        parts.append('NEXT: %s' % next_step)
    station = next((s for s in tree.get('stations') or []
                    if s['key'] == screen['key']), None)
    if station:
        parts.append('STATION: %s — %s' % (_one(station['name'], lang),
                                           _one(station.get('summary'), lang)))
        for lesson in station.get('lessons') or []:
            for step in lesson.get('steps') or []:
                parts.append('- %s: %s' % (_one(step['title'], lang),
                                           _one(step.get('body'), lang)))
        for mistake in (station.get('outline') or {}).get('mistakes') or []:
            parts.append('MISTAKE: %s' % _one(mistake, lang))
    return parts


def corpus_sections(tree, screen_key, lang):
    """{section name: [lines]} — everything WE have written about one screen.

    Read from the static content plane and nothing else. Every value that
    comes out of here was authored in docs/tutorial_poc/author/ and shipped in
    the module; none of it describes a person, a payslip or a pay run that
    exists.
    """
    screen = next((s for s in tree.get('screens') or []
                   if s['key'] == screen_key), None) if screen_key else None
    out = {name: [] for name in _CORPUS_SECTIONS}
    if screen:
        out['screen'] = _corpus_screen_part(tree, screen, lang)
        out['columns'] = [
            'COLUMN %s: %s' % (_one(col['label'], lang),
                               _wire_leaf(col['body'], None, lang))
            for col in tree.get('columns') or [] if col['screen'] == screen_key]
    for intent in tree.get('intents') or []:
        if screen_key and not _covers_screen(intent, screen_key):
            continue
        for block in intent.get('blocks') or []:
            if block['capability'] == 'any' and block.get('body'):
                out['intents'].append(
                    '%s: %s' % (_one(intent['label'], lang),
                                _wire_leaf(block['body'],
                                           block.get('live_fallback'), lang)))
    out['glossary'] = ['TERM %s: %s' % (_one(term['term'], lang),
                                        _one(term['definition'], lang))
                       for term in tree.get('glossary') or []]
    return out


def build_corpus(tree, screen_key, lang, cap=None):
    """The corpus as one string, truncated at a SECTION boundary.

    A slice at `cap` characters cuts through whatever entry happens to be
    there — half a definition, or the first clause of a warning with the
    "never" still to come. Both are worse in a prompt than the entry being
    absent, because a model completes a sentence it was handed. So a section
    that does not fit is dropped whole and said out loud; a later, smaller one
    may still fit, which is why this walks the whole list rather than stopping
    at the first refusal.
    """
    cap = _CORPUS_CAP if cap is None else cap
    kept, dropped, size = [], [], 0
    sections = corpus_sections(tree, screen_key, lang)
    for name in _CORPUS_SECTIONS:
        body = '\n'.join(sections.get(name) or [])
        if not body:
            continue
        extra = len(body) + (1 if kept else 0)
        if size + extra > cap:
            dropped.append('%s (%d chars)' % (name, len(body)))
            continue
        kept.append(body)
        size += extra
    if dropped:
        _logger.warning(
            "Learn composer: the corpus for screen %r [%s] is over the %d "
            "character cap, so these sections were left out whole rather than "
            "cut mid-entry: %s. Raise _CORPUS_CAP or shorten the content.",
            screen_key, lang, cap, ', '.join(dropped))
    return '\n'.join(kept)


# ======================================================================
# THE PROMPTS, AS PURE FUNCTIONS (LEARNOS Phase 4)
# ======================================================================
# The exact bytes that leave this server. Building them here rather than
# inline is what makes "no record data is in the prompt" a testable claim
# instead of a reading exercise: a test hands these two functions their inputs
# and asserts on the whole returned string, with no provider and no network.
#
# Every argument below is either the learner's own scrubbed question or text
# out of the content plane. Neither function can obtain anything else — they
# have no env, no default and nothing to reach with.
def compose_prompt(corpus, question):
    """The composer's prompt: our material, their question, four refusals."""
    return (
        "You are the in-app help assistant for Payobook, a payroll "
        "system. Answer the question USING ONLY the material below, which "
        "is the product's own tutorial content.\n"
        "If the material does not contain the answer, reply with exactly: "
        "NO_ANSWER.\n"
        "Never invent or repeat a contribution rate, a tax threshold, a "
        "relief amount, a deadline or any other number that is not written "
        "in the material. Never give tax, legal or compliance advice. "
        "Never claim to have performed an action: you cannot compute a "
        "run, approve a payslip or change a record.\n"
        "Answer in at most four sentences, plainly, in the same language "
        "as the question.\n\n"
        "MATERIAL:\n%s\n\nQUESTION: %s\nANSWER:" % (corpus, question))


# Four is what fits in a drawer above the fold, and the columns are sequenced
# by the author, so the first four are the ones they put first.
EXPLAIN_COLUMNS = 4


def explain_blocks(tree, screen_key, next_step):
    """The explanation's answer-blocks, as a pure function.

    `next_step` is passed IN rather than looked up, and that is the seam: on
    the server it arrives from `learn.runtime.next_step_live` with its
    `{{live:…}}` tokens resolved against the database, and offline it arrives
    as the authored pair. Everything else here is the content tree, so the
    block SHAPES — which is what the drawer renders and what can go wrong —
    are assertable without Odoo.

    Returns [] for a screen this module does not cover. The caller turns that
    into the ordinary honest miss rather than into an empty card.
    """
    screen = next((s for s in tree.get('screens') or []
                   if s['key'] == screen_key), None) if screen_key else None
    if not screen:
        return []
    blocks = []
    if screen.get('blurb'):
        blocks.append({'capability': 'any', 'kind': 'p',
                       'body': screen['blurb'], 'steps': []})
    if next_step:
        blocks.append({'capability': 'any', 'kind': 'ok',
                       'body': next_step, 'steps': []})
    columns = [c for c in tree.get('columns') or [] if c['screen'] == screen_key]
    for col in columns[:EXPLAIN_COLUMNS]:
        blocks.append({'capability': 'any', 'kind': 'p',
                       'body': _label_body(col['label'], col['body']),
                       'steps': []})
    if not blocks:
        return []
    blocks.append({'capability': 'any', 'kind': 'source',
                   'body': screen['name'], 'steps': []})
    return blocks


def explain_scenario_offer(tree, screen_key):
    """(watch key, try key) for the first walkthrough offered on this screen.

    The scenario is not narrated into a block. A sentence saying "there is a
    walkthrough of this" is a worse version of the button that starts one, and
    the button already exists — Phase 4 gave every answer optional
    `watch` / `try` keys for exactly this shape.
    """
    for scenario in tree.get('scenarios') or []:
        if screen_key not in (scenario.get('screens') or []):
            continue
        modes = scenario.get('modes') or []
        return (scenario['key'] if 'watch' in modes else '',
                scenario['key'] if 'try' in modes else '')
    return '', ''


def explain_prompt(screen_key, floor_text):
    """The explain-this-screen prompt.

    Two inputs and both are ours: the screen KEY (a content identifier, not a
    record id) and the plain text of the deterministic floor this call is
    trying to improve on. There is no learner question here at all — nobody
    typed anything — so there is nothing to scrub and nothing a person could
    have put in it.
    """
    return (
        "You are the in-app help assistant for Payobook, a payroll "
        "system. Below is the product's own tutorial text for one screen.\n"
        "Rewrite it as a short plain-language explanation of that screen: "
        "what it is, what to do next on it, and what its numbers mean.\n"
        "Use ONLY the material below. If it is not enough to explain the "
        "screen, reply with exactly: NO_ANSWER.\n"
        "Never invent or repeat a contribution rate, a tax threshold, a "
        "relief amount, a deadline or any other number that is not written "
        "in the material. Never give tax, legal or compliance advice. "
        "Never claim to have performed an action: you cannot compute a "
        "run, approve a payslip or change a record.\n"
        "Answer in at most six sentences, plainly, in the same language as "
        "the material.\n\n"
        "SCREEN KEY: %s\n\nMATERIAL:\n%s\n\nEXPLANATION:"
        % (screen_key or '', floor_text))


class LearnIntent(models.AbstractModel):
    """The Coach's resolver. Abstract since Phase 1a: the intents themselves
    are static content, and what is left here is behaviour.

    `ask` is the one public entry point and its response contract is unchanged
    from Phase D — coach.js was not touched for it.
    """
    _name = 'learn.intent'
    _description = 'Learn coach resolver'

    # -------------------------------------------------------- the resolver
    @api.model
    def _ambiguous_words(self):
        """Topic words that appear in MORE THAN ONE intent's phrases.

        Length was standing in for specificity in the single-shared-word rule
        below, and it is a poor proxy. `change` is six characters and appears
        in the phrases of four different intents — "will this change", "what
        happens if i change this rate", "is it safe to change the formula",
        "who can change a salary" — so a question sharing only that word
        scored 40 against all four, cleared the floor, and was answered by
        whichever sorted first. On the live database that made "how do I change
        the office wifi password" resolve to "who can change a salary".

        A word half the corpus uses carries no signal about WHICH intent is
        meant, whatever its length. Derived from the content rather than
        hand-listed, so it stays true as content is added — the same principle
        as `_contested_models`: ambiguity is computed from what ships, not
        declared beside it.
        """
        owner, ambiguous = {}, set()
        for intent in self.env['learn.content'].intents():
            words = set()
            for phrase in intent.get('phrases') or []:
                words |= _topic_words(phrase)
            for word in words:
                if owner.setdefault(word, intent['key']) != intent['key']:
                    ambiguous.add(word)
        return ambiguous

    @api.model
    def _score(self, question, intent, screen_key, ambiguous=None):
        """Exact > substring > reverse-substring > topic overlap.

        `ambiguous` is passed in by `_resolve_hook`, which computes it once per
        question rather than once per candidate — uncached it would otherwise
        walk every phrase in the module for every intent being scored.
        """
        nq = _norm(question)
        if not nq:
            return 0
        phrases = intent.get('phrases') or []
        best = 0
        for phrase in phrases:
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
            # TOPIC OVERLAP IS COUNTED IN DISCRIMINATING WORDS ONLY.
            #
            # The deploy round removed ambiguous words from the ONE-word tier
            # and left the two-word tier counting every shared word, which
            # only looks consistent until you notice that two words carrying
            # no signal carry no more signal than one. Phase 4 review
            # demonstrated it: "how do i pay my staff this month" shares `pay`
            # and `month` with `whydiff` — both of them ambiguous, both of
            # them in half the corpus — scored 55, cleared the screenless
            # floor and was rendered under a "Grounded in" badge.
            #
            # So the filter is applied once, to the shared SET, and both tiers
            # read from the result. `_ambiguous_words` is derived from the
            # content rather than declared beside it, so this stays true as
            # intents are added.
            if ambiguous is None:
                ambiguous = self._ambiguous_words()
            qw = _topic_words(question)
            for phrase in phrases:
                strong = (qw & _topic_words(phrase)) - ambiguous
                if len(strong) >= 2:
                    best = max(best, 55)
                elif len(strong) == 1:
                    word = next(iter(strong))
                    # Long AND discriminating. Either alone is not enough: the
                    # length test alone let `change` through, and dropping the
                    # length test would let any rare short word through.
                    if len(word) >= 6:
                        best = max(best, 40)
        if best and screen_key and _covers_screen(intent, screen_key) \
                and (intent.get('screens') or '*') != '*':
            best += _ON_SCREEN_BONUS
        return best

    @api.model
    def _resolve_hook(self, question, screen_key, candidates):
        """THE SEAM.

        Returns an intent key from `candidates`, or None. An LLM implementation
        replaces the body and keeps the contract: it may CHOOSE from the
        candidates, it may not author a reply. Everything the learner reads
        stays a block someone wrote and a test can check.
        """
        ambiguous = self._ambiguous_words()
        scored = [(self._score(question, i, screen_key, ambiguous), i['key'])
                  for i in candidates]
        # Off the map the bar is higher — see _SCREENLESS_FLOOR. Applied here
        # rather than inside `_score` so that the scores themselves stay
        # comparable between the two cases and only the ACCEPTANCE changes.
        floor = _SCORE_FLOOR if screen_key else _SCREENLESS_FLOOR
        scored = [s for s in scored if s[0] >= floor]
        if not scored:
            return None
        scored.sort(key=lambda s: (-s[0], s[1]))
        # A TIE AT THE FLOOR IS A COIN TOSS WEARING A BADGE.
        #
        # The sort's second key is the intent KEY, so two candidates on the
        # same score are separated ALPHABETICALLY — a rule nobody chose, about
        # a question nobody could answer. Phase 4 review reproduced it: "what
        # is the pay run for this month" scored 55 against both `howrun` and
        # `whydiff`, and `howrun` won for the same reason `whichfilings` beat
        # `whichpolicy` on the holiday-policy probe.
        #
        # At the FLOOR specifically, a tie means the weakest kind of hit the
        # resolver accepts, twice, with nothing to choose between them. That
        # is the definition of a miss, and the honest miss names what the
        # Coach CAN answer here.
        #
        # ABOVE the floor a tie may keep the sort. Two intents both scoring 80
        # or 100 are both real matches — one of them is a good answer, and
        # refusing to pick would throw away an answer rather than a guess.
        if len(scored) > 1 and scored[0][0] == floor and scored[1][0] == floor:
            return None
        return scored[0][1]

    @api.model
    def resolve(self, question, screen_key=None):
        Content = self.env['learn.content']
        # The advice guard runs FIRST and does not go through scoring. A
        # deterministic refusal is the only acceptable behaviour here: a
        # retrieval score is a guess, and a guess about how to reduce a
        # statutory obligation is exactly what this system must never make.
        if _is_advice(question):
            return 'compliance' if Content.intent('compliance') else None
        candidates = [i for i in Content.intents()
                      if not screen_key or _covers_screen(i, screen_key)]
        return self._resolve_hook(question, screen_key, candidates)

    # ------------------------------------------------------- capability
    @api.model
    def _capability(self, screen_key=None):
        """What this reader can actually do here.

        Read from the REAL gates — the sidebar's own visibility call and the
        real payroll groups — never from a role name the tutorial keeps a copy
        of. If a group is renamed or a leaf is re-gated, the Coach's answer
        changes with it, because it is asking the same question the product
        asks. This is the one part of the answer path that MUST stay on the
        server: a browser holding the static content plane still cannot tell
        itself it is a manager.

        The Payobook ladder, in the order it is tested:

          owner      pb_hr_payroll_base.group_payroll_super_admin
          no_access  the leaf for this screen is not in the reader's sidebar
          manager    group_payroll_base_manager OR group_payroll_final_approver
                     — the two groups that own an approval gate. A final
                     approver who is not a "manager" still answers "yes, you
                     can approve", so they cannot be told they cannot.
          operator   group_payroll_base_officer
          no_access  none of those four, or the leaf is not in this reader's
                     sidebar.

        VISIBILITY WINS over the group, deliberately: the honest answer to
        "can I approve this run" from someone who cannot even open Pay Runs is
        "you cannot see that screen", not a lecture about a gate.
        """
        user = self.env.user
        if user.has_group('pb_hr_payroll_base.group_payroll_super_admin'):
            return 'owner'
        if screen_key:
            screen = self.env['learn.content'].screen(screen_key)
            if screen and screen.get('sidebar_key'):
                item = self.env.ref(screen['sidebar_key'], raise_if_not_found=False)
                visible = self.env['learn.runtime']._visible_sidebar_item_ids()
                if not item or item.id not in visible:
                    return 'no_access'
        if user.has_group('pb_hr_payroll_base.group_payroll_base_manager') \
                or user.has_group('pb_hr_payroll_base.group_payroll_final_approver'):
            return 'manager'
        if user.has_group('pb_hr_payroll_base.group_payroll_base_officer'):
            return 'operator'
        # Signed in, but holds no payroll group at all. Saying "operator" here
        # would tell someone with no payroll access that they can run a
        # payroll — the exact confidently-wrong answer this gate exists to
        # prevent.
        return 'no_access'

    # ------------------------------------------------------- answering
    @api.model
    def _render_leaf(self, leaf, fallback=''):
        """A content leaf with its `{{live:…}}` tokens resolved, per language.

        Per language and not once, because a live VALUE is itself
        language-aware: a Vietnamese reader gets a Vietnamese division name
        rather than an English one substituted into a Vietnamese sentence.
        Unchanged in behaviour from `learn.intent.block._block_dict`, which did
        the same thing inside each of `_answer`'s two language contexts.
        """
        if not leaf:
            return ''
        Live = self.env['learn.live']
        if isinstance(leaf, str):
            return Live.render(leaf, fallback if isinstance(fallback, str) else '')
        out = {}
        for tag, lang in (('en', 'en_US'), ('vi', 'vi_VN')):
            out[tag] = Live.with_context(lang=lang).render(
                leaf.get(tag) or '', _one(fallback, lang))
        return _pair(out['en'], out['vi'])

    @api.model
    def _blocks_for(self, intent, capability, screen):
        blocks = [b for b in intent.get('blocks') or []
                  if b['capability'] in ('any', capability)]
        if not blocks and intent.get('blocks'):
            # An intent with capability-specific blocks but none for this
            # reader would otherwise answer with silence. Say the most
            # restrictive thing we hold rather than nothing.
            blocks = [b for b in intent['blocks'] if b['capability'] == 'no_access']
        out = [{
            'capability': b['capability'],
            'kind': b['kind'],
            'body': self._render_leaf(b.get('body'), b.get('live_fallback')),
            'steps': [{'text': s['text'], 'anchor': s.get('anchor') or ''}
                      for s in b.get('steps') or []],
        } for b in blocks]
        dynamic = intent.get('dynamic') or 'none'
        if dynamic == 'screen_blurb' and screen:
            out.insert(0, {'capability': 'any', 'kind': 'p',
                           'body': screen.get('blurb') or '', 'steps': []})
        elif dynamic == 'next_step' and screen:
            out.insert(0, {'capability': 'any', 'kind': 'p',
                           'body': self.env['learn.runtime'].next_step_live(screen),
                           'steps': []})
        return out

    @api.model
    def _answer(self, intent_key, screen_key):
        """The full bilingual answer payload for one intent."""
        Content = self.env['learn.content']
        intent = Content.intent(intent_key)
        if not intent:
            return None
        capability = self._capability(screen_key)
        screen = Content.screen(screen_key)
        return {
            'key': intent['key'],
            'label': intent['label'],
            'simpler': intent.get('simpler') or '',
            'blocks': self._blocks_for(intent, capability, screen),
            'capability': capability,
            'show_me': list(intent.get('show_me') or []),
            # LEARNOS Phase 4 — "answers that teach". Two OPTIONAL scenario
            # keys, added to the payload rather than folded into `show_me`,
            # because they answer a different question: `show_me` says "that
            # control is over there", these say "here is the whole task".
            # An older browser that does not read them is unaffected, which is
            # why this is an addition to the contract and not a change to it.
            # The generator refuses a key that names no scenario, and refuses
            # a `try` on a scenario that has no Try mode.
            'watch': intent.get('watch') or '',
            'try': intent.get('try') or '',
            'practice_key': intent.get('practice_key') or '',
        }

    @api.model
    def ask(self, question, screen_key=None, lang=None):
        """The Coach's one entry point.

        Order matters, and each fallback is strictly less certain than the one
        before it, so the most reliable answer always wins:

          1. curated intents      a record someone wrote
          2. the column glossary  a record someone wrote
          3. the composer         a model, over records someone wrote — and
                                  only when a system parameter says so
          4. the honest miss      what the Coach CAN answer here, by name

        Phases A–C had no step 3 at all, and the honest miss is still always an
        acceptable outcome: a fluent invention about a contribution rate is
        not. What step 3 changes is only the case where several written pieces
        together answer a question no single intent covers. It is off by
        default; with the flag off this method behaves exactly as it did in
        Phase C, because `_compose` returns None before doing anything.

        `lang` is the language the COACH is displaying ('en' / 'vi'), which is
        not necessarily the session language — the drawer has its own toggle.
        It is used only to pick which language of our own material the composer
        is given; nothing else reads it.

        PHASE 1a CHANGED THE DATA SOURCE AND NOTHING ELSE. Every shape below,
        including the zero-blocks downgrade and the two source_kind badges, is
        what Phase D returned.
        """
        key = self.resolve(question, screen_key)
        if key:
            answer = self._answer(key, screen_key)
            # AN ANSWER WITH NO BLOCKS IS NOT AN ANSWER.
            #
            # A dynamic intent builds its only block from the screen record —
            # `whatpage` from the blurb, `whatnext` from next_step — so on a
            # screen the spine does not cover, or before those fields are
            # written, it resolves and then renders NOTHING. What the learner
            # saw was the intent's own heading above an empty card: the Coach
            # appearing to answer while saying nothing at all, which is worse
            # than the miss it should have been, because a miss at least names
            # what it CAN answer.
            if answer and answer.get('blocks'):
                answer['matched'] = True
                return answer

        # "What does Need review mean here?" — a question about a COLUMN, not a
        # procedure. Deterministic: no model needed to look up a written
        # definition.
        column = self._match_column(question, screen_key)
        if column:
            return self._column_answer(column, screen_key)

        composed = self._compose(question, screen_key, lang)
        if composed:
            return composed

        return {
            'matched': False,
            'capability': self._capability(screen_key),
            'suggest': self._suggestions(screen_key),
        }

    # ==================================================================
    # THE COMPOSER — a model over OUR OWN CONTENT, and nothing else
    # ==================================================================
    # WHAT IS AND IS NOT SENT
    # -----------------------
    # Sent: the learner's question (scrubbed — see `_scrub`) and this module's
    # own tutorial text for the screen they are on. NOT sent: any employee,
    # payslip, contract or pay-run record. The corpus is built from the static
    # content plane only, so there is no pay data in the request whatever
    # provider is configured, and
    # `contract.json::composer-corpus-reads-learn-content-only` asserts that
    # against the source rather than trusting this paragraph.
    #
    # The question itself is free text a person typed, so it is scrubbed: a
    # help box on a payroll screen receives "why is <a colleague>'s net only
    # 4.200.000" more often than anybody would like.
    #
    # SOFT DEPENDENCY, on purpose. PayAI owns the provider abstraction. A hard
    # dependency would make pb_learn uninstallable without it and would be a
    # second provider registry to keep in step; if it is absent, or nothing is
    # configured, the composer is simply unavailable and the Coach gives the
    # honest miss it gave in Phase C.

    @api.model
    def _compose_enabled(self):
        """The flag. Absent or falsey means OFF, which is every tenant until
        somebody decides otherwise."""
        raw = self.env['ir.config_parameter'].sudo().get_param(COMPOSE_FLAG)
        return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def _scrub(self, question):
        """Remove person- and record-shaped references before the question
        leaves this server, and bound its length."""
        out = question or ''
        out = _NAME_RE.sub('[name]', out)
        out = _CURRENCY_AMOUNT.sub('[amount]', out)
        out = _GROUPED_DIGITS.sub(
            lambda m: ('[amount]'
                       if sum(c.isdigit() for c in m.group(0)) >= 5
                       else m.group(0)),
            out)
        for pattern, replacement in _SCRUB:
            out = pattern.sub(replacement, out)
        return out[:_QUESTION_CAP]

    @api.model
    def _provider(self):
        """The configured provider, or None. Never raises.

        Resolved through the registry rather than by importing PayAI, so this
        module still installs and still answers on a database without it.

        The method ladder is deliberate: PayAI's own callers ask for
        `get_provider_instance`, which is NOT a method on that model in this
        repo — four call sites over there are silently dead because of it. The
        composer asks for that name first so it works the day somebody adds it,
        and falls back to `get_provider`, which exists.
        """
        if 'payroll.ai.config' not in self.env:
            return None
        try:
            config = self.env['payroll.ai.config'].sudo().get_active_config()
            if not config:
                return None
            for name in ('get_provider_instance', 'get_provider'):
                factory = getattr(config, name, None)
                if factory:
                    return factory() or None
        except Exception:                                     # noqa: BLE001
            _logger.info("Learn coach: no usable provider", exc_info=True)
        return None

    @api.model
    def _corpus(self, screen_key, lang):
        """Everything WE have written about this screen, as plain text.

        Reads the static content plane and nothing else. A join to anything the
        payroll product owns would put pay data in a prompt, which is the one
        thing this method exists not to do — and it is the one method in the
        module whose model scope is checked mechanically rather than read.

        The assembly moved to `build_corpus` in LEARNOS Phase 4 so that the
        exact string on the wire can be asserted without a database. What is
        left here is the one thing that needs a registry: the door onto the
        content plane. The model-scope check still sees exactly one model, and
        `corpus-builder-is-pure` covers the half that moved.
        """
        return build_corpus(self.env['learn.content'].tree(), screen_key, lang)

    @api.model
    def _compose(self, question, screen_key, lang=None):
        """Compose an answer from our own material, or return None.

        Returns None on ANY doubt — flag off, an advice question, no provider,
        no corpus, an empty reply, a NO_ANSWER, a suspiciously long one. The
        honest miss is always an acceptable outcome; a fluent invention is not.
        """
        if not self._compose_enabled():
            return None

        # THE DENY-LIST RUNS BEFORE THE COMPOSER, AND NOT ONLY INSIDE
        # `resolve`. It does run there — but `resolve` returns the `compliance`
        # intent only if that content exists, and returns None if it does not.
        # Where the intent is missing, an advice question would fall straight
        # past retrieval and the column glossary and reach a language model,
        # which is the single worst destination for "how do I pay less BHXH" on
        # this system. Re-asked here so the guard cannot depend on the content
        # being present.
        if _is_advice(question):
            return None

        provider = self._provider()
        if not provider:
            return None
        corpus_lang = 'vi_VN' if (lang or '').lower().startswith('vi') else 'en_US'
        corpus = self._corpus(screen_key, corpus_lang)
        if not corpus.strip():
            return None
        scrubbed = self._scrub(question)
        prompt = compose_prompt(corpus, scrubbed)
        try:
            reply = provider.generate_text(prompt, max_tokens=300, temperature=0.2)
        except Exception:                                     # noqa: BLE001
            _logger.info("Learn coach: composer call failed", exc_info=True)
            return None
        reply = (reply or '').strip()
        if not reply or 'NO_ANSWER' in reply or len(reply) > _REPLY_CAP:
            return None

        # ONE language, shown in both. A composed answer is whatever the model
        # wrote; translating it here would be a second model call inventing a
        # second chance to be wrong, and shipping an empty Vietnamese side
        # would blank the drawer for the reader who most needs it. The prompt
        # asks for the question's language and the badge says the answer was
        # composed, which is the honest version of this compromise.
        return {
            'key': 'composed',
            'label': _pair(scrubbed),
            'simpler': '',
            'blocks': [{'capability': 'any', 'kind': 'p',
                        'body': _pair(reply), 'steps': []}],
            'matched': True,
            'capability': self._capability(screen_key),
            'show_me': [],
            # Explicitly empty, not merely absent. A model chose these words;
            # it does not get to decide that a walkthrough covers them.
            'watch': '',
            'try': '',
            'practice_key': '',
            # Badged so the drawer can say so. A composed answer is written by
            # a model FROM our material — the reader is entitled to know which
            # kind of answer they are reading, which is the same reason the
            # column glossary carries a badge.
            'source_kind': 'composed',
        }

    # ==================================================================
    # EXPLAIN THIS SCREEN — a question nobody has to phrase
    # ==================================================================
    # THE FLOOR IS THE FEATURE. Every screen the content plane covers can
    # explain itself with no provider, no flag, no network and no question:
    # the blurb says what it is, `next_step` says what to do here (with its
    # live token resolved, so on the demo world it names the reader's own run),
    # and the column glossary says what the numbers on it count. All three were
    # already written; what was missing was a control that asked for them
    # together.
    #
    # A provider may then REWRITE that floor and may never replace it. The
    # order in `explain_screen` is the guarantee: the floor is built and
    # returned before the flag is even read, so a database with the composer
    # off runs exactly the code that shipped without one, and a rewrite that
    # comes back empty, refused or too long falls back to the same object.
    #
    # WHAT IS ON THE WIRE IF THE FLAG IS ON: the screen key and the floor text
    # — content-plane strings written in docs/tutorial_poc/author/. No record,
    # no learner question (there is none to ask), no tenant slot value. The
    # last of those is deliberate: `next_step` may carry a tenant-authored live
    # value, so the text handed to `explain_prompt` is the AUTHORED sentence,
    # not the rendered one. See `_explain_wire_text`.

    @api.model
    def _explain_floor(self, screen_key):
        """The offline explanation, in the ordinary answer shape.

        NO `lang` ARGUMENT, deliberately. Every block it returns carries BOTH
        languages and the drawer picks — the same shape every other answer in
        this module has. A language parameter here would have been a dead
        argument that the next reader assumes is doing something.

        Returns None when the screen is not one this module covers — the Coach
        already has an honest sentence for that and does not need a second one.

        The live substitution is the only thing that happens here and not in
        `explain_blocks`: `next_step_live` resolves `{{live:…}}` against the
        database, so on the demo world this names the reader's own run, and
        everywhere else it degrades to the authored fallback.
        """
        Content = self.env['learn.content']
        screen = Content.screen(screen_key)
        if not screen:
            return None
        tree = Content.tree()
        blocks = explain_blocks(
            tree, screen_key, self.env['learn.runtime'].next_step_live(screen))
        if not blocks:
            return None
        watch, try_ = explain_scenario_offer(tree, screen_key)
        return {
            'key': 'screen:%s' % screen_key,
            'label': _chrome_pair(Content, 'explainScreen'),
            'simpler': '',
            'blocks': blocks,
            'matched': True,
            'capability': self._capability(screen_key),
            'show_me': [],
            'watch': watch,
            'try': try_,
            'practice_key': '',
            'source_kind': 'screen',
        }

    @api.model
    def _explain_wire_text(self, screen_key, lang):
        """The floor as plain text, for a prompt — AUTHORED strings only.

        Built from the content plane a second time rather than by flattening
        the floor payload, and the difference is the whole reason this method
        exists: the floor's `next_step` has been through `learn.runtime`, so on
        the demo world it carries a division name and a run state read out of
        the database, and on any tenant it can carry an override slot somebody
        typed. Neither belongs on a wire to a provider. What is sent is the
        sentence as an author wrote it, tokens unresolved.
        """
        Content = self.env['learn.content']
        screen = Content.screen(screen_key)
        if not screen:
            return ''
        parts = ['SCREEN: %s — %s' % (_one(screen['name'], lang),
                                      _one(screen.get('blurb'), lang))]
        next_step = _wire_leaf(screen.get('next_step'),
                               screen.get('live_fallback'), lang)
        if next_step:
            parts.append('NEXT: %s' % next_step)
        for col in Content.screen_columns(screen_key)[:EXPLAIN_COLUMNS]:
            parts.append('COLUMN %s: %s' % (_one(col['label'], lang),
                                            _wire_leaf(col['body'], None, lang)))
        return '\n'.join(parts)

    @api.model
    def _explain_composed(self, floor, screen_key, lang):
        """A model's rewrite of the floor, or None. Never a replacement for it.

        Everything the composer refuses on, this refuses on too, and for the
        same reasons: no provider, no material, an empty reply, a NO_ANSWER, a
        suspiciously long one, a provider that raised.
        """
        provider = self._provider()
        if not provider:
            return None
        wire_lang = 'vi_VN' if (lang or '').lower().startswith('vi') else 'en_US'
        material = self._explain_wire_text(screen_key, wire_lang)
        if not material.strip():
            return None
        prompt = explain_prompt(screen_key, material)
        try:
            reply = provider.generate_text(prompt, max_tokens=300, temperature=0.2)
        except Exception:                                     # noqa: BLE001
            _logger.info("Learn coach: explain rewrite failed", exc_info=True)
            return None
        reply = (reply or '').strip()
        if not reply or 'NO_ANSWER' in reply or len(reply) > _REPLY_CAP:
            return None
        out = dict(floor)
        # One language, shown in both — the same compromise `_compose` makes,
        # for the same reason, and badged the same way so the reader can tell.
        out['blocks'] = [{'capability': 'any', 'kind': 'p',
                          'body': _pair(reply), 'steps': []}]
        out['source_kind'] = 'composed'
        return out

    @api.model
    def explain_screen(self, screen_key, lang=None):
        """"Explain this screen" — the Coach's one button that asks nothing.

        THE ORDER IS THE CONTRACT, and `contract.json::explain-screen-has-
        deterministic-floor` pins it: the floor exists and is returned before
        the flag is read, so the provider branch can only ever be an
        improvement on an answer this tenant already had.
        """
        floor = self._explain_floor(screen_key)
        if not floor:
            # The same honest miss `ask()` gives, built the same way, so an
            # uncovered screen answers with what the Coach CAN do here.
            return {
                'matched': False,
                'capability': self._capability(screen_key),
                'suggest': self._suggestions(screen_key),
            }
        if not self._compose_enabled():
            return floor
        return self._explain_composed(floor, screen_key, lang) or floor

    # ------------------------------------------------------ column glossary
    @api.model
    def _match_column(self, question, screen_key):
        """Find the column a question is asking about.

        Deliberately narrow: the question must contain the column's label. A
        loose match here would answer "what is the status of this run" with a
        column definition, which is worse than missing.

        BOTH languages are consulted, because a Vietnamese reader types the
        Vietnamese header.
        """
        if not screen_key:
            return None
        nq = _norm(question)
        if not nq:
            return None
        best, best_len = None, 0
        for col in self.env['learn.content'].screen_columns(screen_key):
            for lang in ('en_US', 'vi_VN'):
                label = _norm(_one(col['label'], lang))
                if label and len(label) > 3 and label in nq and len(label) > best_len:
                    best, best_len = col, len(label)
        return best

    @api.model
    def _column_answer(self, column, screen_key):
        """A column definition, shaped like any other answer."""
        screen = self.env['learn.content'].screen(screen_key)
        source = (screen or {}).get('name') or screen_key or ''
        return {
            'key': 'column:%s' % column['key'],
            'label': column['label'],
            'simpler': '',
            'blocks': [
                {'capability': 'any', 'kind': 'p', 'body': column['body'],
                 'steps': []},
                {'capability': 'any', 'kind': 'source',
                 'body': source if isinstance(source, dict) else _pair(source),
                 'steps': []},
            ],
            'matched': True,
            'capability': self._capability(screen_key),
            'show_me': [],
            'watch': '',
            'try': '',
            'practice_key': '',
            'source_kind': 'column',
        }

    @api.model
    def _suggestions(self, screen_key):
        """What the Coach can answer here, named. A bare "I don't know" tells
        the learner nothing about where to go next."""
        content = self.env['learn.content']
        screen = content.screen(screen_key)
        if screen:
            return [{'key': s['key'], 'label': s['label']}
                    for s in screen.get('suggest') or []]
        # What the Coach can answer ANYWHERE. Without this, a screen it does
        # not cover is a dead end: an honest "no lessons here yet" and then
        # nothing at all, which leaves the stuck person exactly as stuck.
        return [dict(s) for s in content.global_suggest()]
