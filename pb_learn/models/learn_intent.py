# -*- coding: utf-8 -*-
"""The Payobook Coach's content and its resolver.

The Coach answers ONLY from stored blocks. There is no path from a question to
the screen that does not pass through a record an author wrote — which is what
lets it promise never to invent a rate, a threshold or a tax figure.

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

NOTE TO THE NEXT READER: `contract.json::coach-answers-from-records-only`
greps this file whole, prose included, for the tokens that must never appear
here — a product model name, raw SQL, or another module's provider registry.
Say "a product model" rather than naming one, as everything below does.
"""
import logging
import re
import unicodedata

from odoo import api, fields, models, tools

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


def _is_advice(question):
    nq = _norm(question)
    return any(m in nq for m in _ADVICE_MARKERS)


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
# the mark is left stranded beside the placeholder ("[amount] ₫"), which reads
# like a redaction that missed.
_CURRENCY_AMOUNT = re.compile(
    r'\b\d[\d.,]*\s*(?:₫|vnd|vnđ|đ)\b', re.IGNORECASE)

# Anything that looks like it identifies a person or a record, scrubbed from
# the question before it leaves this server. These four are health_learn's,
# unchanged; the two payroll-grade ones above are new here.
_SCRUB = (
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b'), '[email]'),
    (re.compile(r'(?:\+?84|0)\d[\d\s.-]{7,}\d'), '[phone]'),
    (re.compile(r'#\d{2,}'), '[record]'),
    (re.compile(r'\b\d{6,}\b'), '[number]'),
)


class LearnScreen(models.Model):
    _name = 'learn.screen'
    _description = 'Learn screen'
    _order = 'sequence, key'

    key = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    blurb = fields.Text(translate=True, help="What this screen is, in one sentence.")
    next_step = fields.Text(
        translate=True,
        help="The honest answer to 'what should I do next here'.")
    action_tags = fields.Char(
        help="Optional manual override. Normally EMPTY: the matchers are read "
             "from the sidebar leaf named by sidebar_key, so the Coach and the "
             "sidebar can never disagree about which screen is showing.")
    sidebar_key = fields.Char(help="xml-id of the leaf, for the visibility check.")
    live_fallback = fields.Text(
        translate=True,
        help="The sentence to show when a {{live:...}} token in next_step cannot "
             "be resolved — on a tenant that is not the demo world, which is "
             "every tenant but one.")
    suggest_ids = fields.Many2many('learn.intent', string='Suggested questions')

    def _next_step_live(self):
        """next_step with its live tokens resolved, or the authored fallback.

        The second and last live site. `whatnext` is the most-asked question on
        any screen, and on the demo world the useful answer names the state the
        prospect's OWN June run is actually in — which no static sentence can.
        Everywhere else the authored sentence is shown unchanged.
        """
        self.ensure_one()
        return self.env['learn.live'].render(self.next_step or '',
                                             self.live_fallback or '')

    _sql_constraints = [('key_uniq', 'unique(key)', 'A screen key must be unique.')]

    @staticmethod
    def _split(val):
        return {v.strip() for v in (val or '').split(',') if v.strip()}

    def _raw_models(self):
        """The models this screen's LEAF declares, before any tie-break."""
        self.ensure_one()
        if not self.sidebar_key:
            return set()
        item = self.env.ref(self.sidebar_key, raise_if_not_found=False)
        return self._split(item.sudo().match_models) if item else set()

    @api.model
    @tools.ormcache()
    def _contested_models(self):
        """Models that more than one screen's leaf claims.

        `hr.integration.connector` is claimed by BOTH the Import Data leaf and
        the Integrations leaf (pb_sidebar_data.xml:82 and :196), and BOTH are
        right for the sidebar: a connector form opened from either place should
        leave that leaf lit. It is not right for the Coach. A model two screens
        answer to makes the broad third pass pick whichever the search returned
        first — wrong, and wrong differently on different databases, which is
        the exact 'confidently wrong' failure the three-pass resolver exists to
        prevent.

        So a contested model is not a matcher for EITHER screen. The tags and
        xml-ids still resolve both cockpits exactly (they are distinct client
        actions), and what is lost is only the bare list/form view of the
        contested model — where the honest answer really is "I do not have
        lessons for this screen", not a coin flip between two that both have
        content.

        Computed from the live leaves rather than declared, because the contest
        is a fact about pb_sidebar and a copy of it here would be one more thing
        to keep in step.

        CACHED, because `_matchers` is called once per screen and this walks
        every screen: uncached it turned one bundle build into a quadratic
        sweep of the sidebar. The inputs are two data tables that only change on
        upgrade, and learn.screen's own write path already clears the registry
        cache — the same invalidation learn.station relies on.
        """
        seen, contested = set(), set()
        for screen in self.sudo().search([]):
            for model in screen._raw_models():
                if model in seen:
                    contested.add(model)
                seen.add(model)
        return contested

    # The cached contest above is derived from these records and from the
    # sidebar leaves they name, so a change to either has to drop it. Mirrors
    # learn.station._invalidate_learn_bundle, which clears the same cache for
    # the same reason.
    @api.model_create_multi
    def create(self, vals_list):
        rec = super().create(vals_list)
        self.env.registry.clear_cache()
        return rec

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    def _matchers(self):
        """How to tell that THIS screen is the one on display.

        Read from the sidebar leaf rather than hard-coded here. Not every Pay
        Run leaf is a client action with a tag — Pay Runs is an act_window
        matched by xml-id and by hr.payslip.run — so a tag-only map silently
        fails to detect some screens, and the Coach then tells the learner it
        has no lessons for a screen it has a full lesson for.

        Reusing the leaf's own declaration means the Coach resolves the screen
        exactly the way the sidebar decides which leaf to highlight — with the
        one documented exception in `_contested_models`.
        """
        self.ensure_one()
        tags, xmlids, models_ = set(), set(), set()

        split = self._split
        tags |= split(self.action_tags)
        if self.sidebar_key:
            item = self.env.ref(self.sidebar_key, raise_if_not_found=False)
            if item:
                item = item.sudo()
                tags |= split(item.action_tag) | split(item.match_action_tags)
                xmlids |= split(item.action_xmlid) | split(item.match_action_xmlids)
                models_ |= split(item.match_models)
        return sorted(tags), sorted(xmlids), sorted(models_ - self._contested_models())

    def _primary(self):
        """The leaf's OWN action — the one that IS this screen.

        A parent leaf legitimately lists its children's actions in
        match_action_xmlids so the sidebar highlights the parent while a child
        is open. That is right for the sidebar and wrong for the Coach: opening
        Cash In Transit grounded it on AR Management, because the parent
        matched first. The primary pair breaks that tie without changing what
        the sidebar does.
        """
        self.ensure_one()
        if not self.sidebar_key:
            return None, None
        item = self.env.ref(self.sidebar_key, raise_if_not_found=False)
        if not item:
            return None, None
        item = item.sudo()
        return (item.action_tag or None), (item.action_xmlid or None)


class LearnIntent(models.Model):
    _name = 'learn.intent'
    _description = 'Learn coach intent'
    _order = 'key'

    key = fields.Char(required=True, index=True)
    label = fields.Char(required=True, translate=True,
                        help="The question as a person would ask it.")
    screens = fields.Char(default='*',
                          help="'*' or a comma-separated list of learn.screen keys.")
    dynamic = fields.Selection(
        selection=lambda self: self._selection_dynamic(), default='none', required=True)
    show_me = fields.Char(help="Comma-separated anchor keys this answer can point at.")
    simpler = fields.Text(translate=True, help="The 'explain more simply' rewrite.")
    practice_key = fields.Char(help="A Phase-3 mission id. Inert until then.")
    active = fields.Boolean(default=True)
    offer = fields.Boolean(
        default=True,
        help="Show this as a suggested question. A refusal must stay REACHABLE "
             "but never advertised: offering 'ask me how to pay less tax' invites "
             "exactly the question the Coach exists to decline.")
    phrase_ids = fields.One2many('learn.intent.phrase', 'intent_id')
    block_ids = fields.One2many('learn.intent.block', 'intent_id')

    _sql_constraints = [('key_uniq', 'unique(key)', 'An intent key must be unique.')]

    @api.model
    def _selection_dynamic(self):
        return [('none', self.env._('Static blocks')),
                ('screen_blurb', self.env._("The screen's own description")),
                ('next_step', self.env._('What to do next here'))]

    # ------------------------------------------------------------------
    def _covers_screen(self, screen_key):
        self.ensure_one()
        raw = (self.screens or '*').strip()
        if raw == '*':
            return True
        return screen_key in [s.strip() for s in raw.split(',') if s.strip()]

    # -------------------------------------------------------- the resolver
    @api.model
    def _score(self, question, intent, screen_key):
        """Exact > substring > reverse-substring > topic overlap."""
        nq = _norm(question)
        if not nq:
            return 0
        best = 0
        for phrase in intent.phrase_ids:
            np = _norm(phrase.text)
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
            qw = _topic_words(question)
            for phrase in intent.phrase_ids:
                shared = qw & _topic_words(phrase.text)
                if len(shared) >= 2:
                    best = max(best, 55)
                elif len(shared) == 1 and len(next(iter(shared))) >= 6:
                    best = max(best, 40)
        if best and screen_key and intent._covers_screen(screen_key) \
                and (intent.screens or '*') != '*':
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
        scored = [(self._score(question, i, screen_key), i.key) for i in candidates]
        scored = [s for s in scored if s[0] >= _SCORE_FLOOR]
        if not scored:
            return None
        scored.sort(key=lambda s: (-s[0], s[1]))
        return scored[0][1]

    @api.model
    def resolve(self, question, screen_key=None):
        # The advice guard runs FIRST and does not go through scoring. A
        # deterministic refusal is the only acceptable behaviour here: a
        # retrieval score is a guess, and a guess about how to reduce a
        # statutory obligation is exactly what this system must never make.
        if _is_advice(question):
            return 'compliance' if self.search_count([('key', '=', 'compliance')]) else None
        candidates = self.search([]).filtered(
            lambda i: not screen_key or i._covers_screen(screen_key))
        return self._resolve_hook(question, screen_key, candidates)


    # ------------------------------------------------------- capability
    @api.model
    def _capability(self, screen_key=None):
        """What this reader can actually do here.

        Read from the REAL gates — the sidebar's own visibility call and the
        real payroll groups — never from a role name the tutorial keeps a copy
        of. If a group is renamed or a leaf is re-gated, the Coach's answer
        changes with it, because it is asking the same question the product
        asks.

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
            screen = self.env['learn.screen'].sudo().search(
                [('key', '=', screen_key)], limit=1)
            if screen and screen.sidebar_key:
                item = self.env.ref(screen.sidebar_key, raise_if_not_found=False)
                visible = self.env['learn.station']._visible_sidebar_item_ids()
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
    def _answer_tree(self, capability, screen):
        """One language's worth of answer. Zipped by _answer below."""
        self.ensure_one()
        blocks = [b for b in self.block_ids
                  if b.capability in ('any', capability)]
        if not blocks and self.block_ids:
            # An intent with capability-specific blocks but none for this
            # reader would otherwise answer with silence. Say the most
            # restrictive thing we hold rather than nothing.
            blocks = [b for b in self.block_ids if b.capability == 'no_access']
        out = [b._block_dict() for b in blocks]
        if self.dynamic == 'screen_blurb' and screen:
            out.insert(0, {'capability': 'any', 'kind': 'p',
                           'body': screen.blurb or '', 'steps': []})
        elif self.dynamic == 'next_step' and screen:
            out.insert(0, {'capability': 'any', 'kind': 'p',
                           'body': screen._next_step_live(), 'steps': []})
        return {
            'key': self.key,
            'label': self.label,
            'simpler': self.simpler or '',
            'blocks': out,
        }

    @api.model
    def _answer(self, intent_key, screen_key):
        """The full bilingual answer payload for one intent."""
        from .learn_station import _zip_bilingual
        capability = self._capability(screen_key)

        def build(lang):
            env = self.with_context(lang=lang)
            intent = env.search([('key', '=', intent_key)], limit=1)
            if not intent:
                return None
            screen = env.env['learn.screen'].sudo().search(
                [('key', '=', screen_key)], limit=1) if screen_key else None
            return intent._answer_tree(capability, screen)

        en, vi = build('en_US'), build('vi_VN')
        if not en:
            return None
        payload = _zip_bilingual(en, vi)
        intent = self.search([('key', '=', intent_key)], limit=1)
        payload.update({
            'capability': capability,
            'show_me': [a.strip() for a in (intent.show_me or '').split(',') if a.strip()],
            'practice_key': intent.practice_key or '',
        })
        return payload

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
        column = self.env['learn.column'].match(question, screen_key)
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
    # payslip, contract or pay-run record. The corpus is built from learn.*
    # tables only, so there is no pay data in the request whatever provider is
    # configured, and `contract.json::composer-corpus-reads-learn-content-only`
    # asserts that against the source rather than trusting this paragraph.
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

        Reads learn.* content tables and nothing else. A join to anything the
        payroll product owns would put pay data in a prompt, which is the one
        thing this method exists not to do.
        """
        env = self.with_context(lang=lang)
        parts = []
        Screen = env.env['learn.screen'].sudo()
        screen = Screen.search([('key', '=', screen_key)], limit=1) if screen_key else None
        if screen:
            parts.append('SCREEN: %s — %s' % (screen.name, screen.blurb or ''))
            if screen.next_step:
                parts.append('NEXT: %s' % screen.next_step)
            station = env.env['learn.station'].sudo().search(
                [('key', '=', screen_key)], limit=1)
            if station:
                parts.append('STATION: %s — %s' % (station.name, station.summary or ''))
                for lesson in station.lesson_ids:
                    for step in lesson.step_ids:
                        parts.append('- %s: %s' % (step.title, step.body or ''))
                for mistake in station.mistake_ids:
                    parts.append('MISTAKE: %s' % mistake.name)
            for col in env.env['learn.column'].sudo().search(
                    [('screen', '=', screen_key)]):
                parts.append('COLUMN %s: %s' % (col.label, col.body))
        for intent in env.search([]).filtered(
                lambda i: not screen_key or i._covers_screen(screen_key)):
            for block in intent.block_ids:
                if block.capability == 'any' and block.body:
                    parts.append('%s: %s' % (intent.label, block.body))
        for term in env.env['learn.glossary.term'].sudo().search([]):
            parts.append('TERM %s: %s' % (term.term, term.definition))
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
        # intent only if that record exists, and returns None if it does not.
        # On a database where the intent is missing or deactivated, an advice
        # question would fall straight past retrieval and the column glossary
        # and reach a language model, which is the single worst destination for
        # "how do I pay less BHXH" on this system. Re-asked here so the guard
        # cannot depend on a record being present.
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

        from .learn_station import _zip_bilingual
        # ONE language, shown in both. A composed answer is whatever the model
        # wrote; translating it here would be a second model call inventing a
        # second chance to be wrong, and shipping an empty Vietnamese side
        # would blank the drawer for the reader who most needs it. The prompt
        # asks for the question's language and the badge says the answer was
        # composed, which is the honest version of this compromise.
        tree = {
            'key': 'composed',
            'label': scrubbed,
            'simpler': '',
            'blocks': [{'capability': 'any', 'kind': 'p', 'body': reply,
                        'steps': []}],
        }
        payload = _zip_bilingual(tree, tree)
        payload.update({
            'matched': True,
            'capability': self._capability(screen_key),
            'show_me': [],
            'practice_key': '',
            # Badged so the drawer can say so. A composed answer is written by
            # a model FROM our material — the reader is entitled to know which
            # kind of answer they are reading, which is the same reason the
            # column glossary carries a badge.
            'source_kind': 'composed',
        })
        return payload

    @api.model
    def _column_answer(self, column, screen_key):
        """A column definition, shaped like any other answer."""
        from .learn_station import _zip_bilingual

        def build(lang):
            col = column.with_context(lang=lang)
            return {
                'key': 'column:%s' % col.key,
                'label': col.label,
                'simpler': '',
                'blocks': [
                    {'capability': 'any', 'kind': 'p', 'body': col.body, 'steps': []},
                    {'capability': 'any', 'kind': 'source', 'steps': [],
                     'body': col.env['learn.screen'].sudo().search(
                         [('key', '=', screen_key)], limit=1).name or screen_key},
                ],
            }

        payload = _zip_bilingual(build('en_US'), build('vi_VN'))
        payload.update({'matched': True, 'capability': self._capability(screen_key),
                        'show_me': [], 'practice_key': '', 'source_kind': 'column'})
        return payload

    @api.model
    def _suggestions(self, screen_key):
        """What the Coach can answer here, named. A bare "I don't know" tells
        the learner nothing about where to go next."""
        from .learn_station import _zip_bilingual
        screen = self.env['learn.screen'].sudo().search(
            [('key', '=', screen_key)], limit=1) if screen_key else None

        def build(lang):
            env = self.with_context(lang=lang)
            if screen:
                intents = env.browse(screen.suggest_ids.ids)
            else:
                intents = env.search(
                    [('screens', '=', '*'), ('offer', '=', True)], limit=6)
            return [{'key': i.key, 'label': i.label} for i in intents]

        return _zip_bilingual(build('en_US'), build('vi_VN'))

    @api.model
    def coach_bundle(self):
        """Screens + suggestions, both languages, fetched once per session so
        the drawer opens instantly rather than after a round-trip."""
        from .learn_station import _zip_bilingual

        def build(lang):
            env = self.env['learn.screen'].with_context(lang=lang).sudo()
            return {
                'screens': [{
                    'key': s.key,
                    'name': s.name,
                    'blurb': s.blurb or '',
                    'next_step': s._next_step_live(),
                    'action_tags': s._matchers()[0],
                    'action_xmlids': s._matchers()[1],
                    'models': s._matchers()[2],
                    'own_tag': s._primary()[0] or '',
                    'own_xmlid': s._primary()[1] or '',
                    'suggest': [{'key': i.key, 'label': i.label} for i in s.suggest_ids],
                } for s in env.search([])],
                # What the Coach can answer ANYWHERE. Without this, a screen it
                # does not cover is a dead end: an honest "no lessons here yet"
                # and then nothing at all, which leaves the stuck person exactly
                # as stuck.
                'global_suggest': [
                    {'key': i.key, 'label': i.label}
                    for i in self.with_context(lang=lang).search(
                        [('screens', '=', '*'), ('offer', '=', True)],
                        order='key', limit=6)
                ],
            }

        bundle = _zip_bilingual(build('en_US'), build('vi_VN'))
        bundle['tokens'] = self.env['learn.tenant.override'].resolved_tokens()
        bundle['chrome'] = self.env['learn.station']._content_bundle()['chrome']
        return bundle


class LearnIntentPhrase(models.Model):
    """A trigger phrase.

    NOT translatable, deliberately: the prototype's match lists mix English and
    Vietnamese in one bag, which is correct. A learner types in whichever
    language they are thinking in — often mid-shift, often without tone marks —
    and both have to hit the same intent.
    """
    _name = 'learn.intent.phrase'
    _description = 'Learn coach trigger phrase'
    _order = 'intent_id, id'

    intent_id = fields.Many2one('learn.intent', required=True, ondelete='cascade')
    text = fields.Char(required=True)


class LearnIntentBlock(models.Model):
    _name = 'learn.intent.block'
    _description = 'Learn coach answer block'
    _order = 'sequence, id'

    intent_id = fields.Many2one('learn.intent', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    capability = fields.Selection(
        selection=lambda self: self._selection_capability(),
        default='any', required=True,
        help="Which reader this block is for. Read from the REAL gates, not "
             "from a role name the tutorial keeps its own copy of.")
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(), required=True, default='p')
    body = fields.Text(translate=True)
    live_fallback = fields.Text(
        translate=True,
        help="The sentence to show when a {{live:...}} token in the body cannot "
             "be resolved. Required by the generator on any body that uses one: "
             "a half-resolved sentence reads as a fact with a hole in it.")
    step_ids = fields.One2many('learn.intent.step', 'block_id')

    @api.model
    def _selection_capability(self):
        return [
            ('any', self.env._('Everyone')),
            ('no_access', self.env._('Cannot see this screen')),
            ('operator', self.env._('Payroll officer')),
            ('manager', self.env._('Payroll manager / final approver')),
            ('owner', self.env._('Payroll super administrator')),
        ]

    @api.model
    def _selection_kind(self):
        return [
            ('p', self.env._('Paragraph')),
            ('steps', self.env._('Numbered steps')),
            ('calc', self.env._('Payslip calculation')),
            ('calc_kpi', self.env._('Period-on-period variance')),
            ('ok', self.env._('Confirmation')),
            ('warn', self.env._('Caution')),
            ('refusal', self.env._('Your role cannot do this')),
            ('who', self.env._('Who can')),
            ('how', self.env._('How to get access')),
            ('source', self.env._('Grounded in')),
        ]

    def _block_dict(self):
        self.ensure_one()
        return {
            'capability': self.capability,
            'kind': self.kind,
            # Live values are resolved HERE, per language, because this runs
            # once inside each of _answer's two language contexts — so a
            # Vietnamese reader gets a Vietnamese division name rather than an
            # English one substituted into a Vietnamese sentence.
            'body': self.env['learn.live'].render(self.body or '',
                                                  self.live_fallback or ''),
            'steps': [{'text': s.text, 'anchor': s.anchor or ''} for s in self.step_ids],
        }


class LearnIntentStep(models.Model):
    _name = 'learn.intent.step'
    _description = 'Learn coach answer step'
    _order = 'sequence, id'

    block_id = fields.Many2one('learn.intent.block', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    text = fields.Text(required=True, translate=True)
    anchor = fields.Char(help="Anchor key to point at. Must be in anchors.json.")


class LearnColumn(models.Model):
    """What a column on a screen actually means.

    WHY THIS IS CURATED AND NOT READ FROM ir.model.fields
    ----------------------------------------------------
    Most of what a learner asks about here is not a field at all. "Need
    review", "In pipeline" and "Awaiting your approval" are COMPUTED tiles on
    an OWL cockpit — there is no ir.model.fields row behind them to read a
    help string from, and the fields that do exist carry Odoo's own
    boilerplate.

    So a schema-driven answer would restate the tile's own caption back at the
    person who just read it. What answers "what does Need review count?" is
    domain knowledge: which flag conditions raise it, that a flag is a question
    rather than an error, and that the fix belongs in the input. That has to be
    written.
    """
    _name = 'learn.column'
    _description = 'Learn screen column'
    _order = 'screen, sequence, id'

    screen = fields.Char(required=True, index=True)
    key = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True, translate=True,
                        help="The column header exactly as it appears on screen.")
    body = fields.Text(required=True, translate=True,
                       help="One honest sentence: what it is for, and what it is not.")

    _sql_constraints = [
        ('screen_key_uniq', 'unique(screen, key)', 'One entry per column per screen.'),
    ]

    @api.model
    def match(self, question, screen_key):
        """Find the column a question is asking about.

        Deliberately narrow: the question must contain the column's label. A
        loose match here would answer "what is the status of this run" with a
        column definition, which is worse than missing.
        """
        if not screen_key:
            return None
        nq = _norm(question)
        if not nq:
            return None
        best, best_len = None, 0
        for col in self.search([('screen', '=', screen_key)]):
            for lang in ('en_US', 'vi_VN'):
                label = _norm(col.with_context(lang=lang).label)
                if label and len(label) > 3 and label in nq and len(label) > best_len:
                    best, best_len = col, len(label)
        return best

    def _column_dict(self):
        self.ensure_one()
        return {'key': self.key, 'label': self.label, 'body': self.body}
