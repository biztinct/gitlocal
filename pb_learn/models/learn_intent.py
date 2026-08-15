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

_CORPUS_CAP = 12000
_QUESTION_CAP = 400
_REPLY_CAP = 1500


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


def _covers_screen(intent, screen_key):
    raw = (intent.get('screens') or '*').strip()
    if raw == '*':
        return True
    return screen_key in [s.strip() for s in raw.split(',') if s.strip()]


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
            # Topic overlap, but never on one shared common word: that is how a
            # tax-advice question ends up answered with a UI tour.
            if ambiguous is None:
                ambiguous = self._ambiguous_words()
            qw = _topic_words(question)
            for phrase in phrases:
                shared = qw & _topic_words(phrase)
                if len(shared) >= 2:
                    best = max(best, 55)
                elif len(shared) == 1:
                    word = next(iter(shared))
                    # Long AND discriminating. Either alone is not enough: the
                    # length test alone let `change` through, and dropping the
                    # length test would let any rare short word through.
                    if len(word) >= 6 and word not in ambiguous:
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
        scored = [s for s in scored if s[0] >= _SCORE_FLOOR]
        if not scored:
            return None
        scored.sort(key=lambda s: (-s[0], s[1]))
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
        """
        content = self.env['learn.content']
        parts = []
        screen = content.screen(screen_key) if screen_key else None
        if screen:
            parts.append('SCREEN: %s — %s' % (_one(screen['name'], lang),
                                              _one(screen.get('blurb'), lang)))
            if screen.get('next_step'):
                parts.append('NEXT: %s' % _one(screen['next_step'], lang))
            station = content.station(screen_key)
            if station:
                parts.append('STATION: %s — %s' % (_one(station['name'], lang),
                                                   _one(station.get('summary'), lang)))
                for lesson in station.get('lessons') or []:
                    for step in lesson.get('steps') or []:
                        parts.append('- %s: %s' % (_one(step['title'], lang),
                                                   _one(step.get('body'), lang)))
                for mistake in (station.get('outline') or {}).get('mistakes') or []:
                    parts.append('MISTAKE: %s' % _one(mistake, lang))
            for col in content.screen_columns(screen_key):
                parts.append('COLUMN %s: %s' % (_one(col['label'], lang),
                                                _one(col['body'], lang)))
        for intent in content.intents():
            if screen_key and not _covers_screen(intent, screen_key):
                continue
            for block in intent.get('blocks') or []:
                if block['capability'] == 'any' and block.get('body'):
                    parts.append('%s: %s' % (_one(intent['label'], lang),
                                             _one(block['body'], lang)))
        for term in content.glossary():
            parts.append('TERM %s: %s' % (_one(term['term'], lang),
                                          _one(term['definition'], lang)))
        return '\n'.join(parts)[:_CORPUS_CAP]

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
        prompt = (
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
            "MATERIAL:\n%s\n\nQUESTION: %s\nANSWER:" % (corpus, scrubbed))
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
            'practice_key': '',
            # Badged so the drawer can say so. A composed answer is written by
            # a model FROM our material — the reader is entitled to know which
            # kind of answer they are reading, which is the same reason the
            # column glossary carries a badge.
            'source_kind': 'composed',
        }

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
