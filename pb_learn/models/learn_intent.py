# -*- coding: utf-8 -*-
"""The Payobook Coach's content and its resolver.

The Coach answers ONLY from stored blocks. There is no path from a question to
the screen that does not pass through a record an author wrote — which is what
lets it promise never to invent a rate, a threshold or a tax figure.

The resolver is deterministic retrieval. `_resolve_hook` is the one seam where
an LLM could be plugged in later; note its contract, which is the whole point:
it returns an intent KEY chosen from the candidates, never text. A model may
choose what to say; it may not say it. Phase A ships NO model at all — the hook
is the deterministic scorer and nothing else, and there is no composer.
"""
import re
import unicodedata

from odoo import api, fields, models

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
    suggest_ids = fields.Many2many('learn.intent', string='Suggested questions')

    _sql_constraints = [('key_uniq', 'unique(key)', 'A screen key must be unique.')]

    def _matchers(self):
        """How to tell that THIS screen is the one on display.

        Read from the sidebar leaf rather than hard-coded here. Not every Pay
        Run leaf is a client action with a tag — Pay Runs is an act_window
        matched by xml-id and by hr.payslip.run — so a tag-only map silently
        fails to detect some screens, and the Coach then tells the learner it
        has no lessons for a screen it has a full lesson for.

        Reusing the leaf's own declaration means the Coach resolves the screen
        exactly the way the sidebar decides which leaf to highlight.
        """
        self.ensure_one()
        tags, xmlids, models_ = set(), set(), set()

        def split(val):
            return {v.strip() for v in (val or '').split(',') if v.strip()}

        tags |= split(self.action_tags)
        if self.sidebar_key:
            item = self.env.ref(self.sidebar_key, raise_if_not_found=False)
            if item:
                item = item.sudo()
                tags |= split(item.action_tag) | split(item.match_action_tags)
                xmlids |= split(item.action_xmlid) | split(item.match_action_xmlids)
                models_ |= split(item.match_models)
        return sorted(tags), sorted(xmlids), sorted(models_)

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
                           'body': screen.next_step or '', 'steps': []})
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
    def ask(self, question, screen_key=None):
        """The Coach's one entry point.

        Order matters. Curated intents first, then the column glossary, then an
        honest miss — each fallback is strictly less certain than the one
        before it, so the most reliable answer always wins.

        THERE IS NO THIRD FALLBACK. health_learn has a composer here — an LLM
        over its own corpus — and Phase A deliberately does not port it. The
        honest miss is always an acceptable outcome on a payroll system; a
        fluent invention about a contribution rate is not. Every sentence a
        learner reads is a record someone wrote and a test can check.
        """
        key = self.resolve(question, screen_key)
        if key:
            answer = self._answer(key, screen_key)
            if answer:
                answer['matched'] = True
                return answer

        # "What does Need review mean here?" — a question about a COLUMN, not a
        # procedure. Deterministic: no model needed to look up a written
        # definition.
        column = self.env['learn.column'].match(question, screen_key)
        if column:
            return self._column_answer(column, screen_key)

        return {
            'matched': False,
            'capability': self._capability(screen_key),
            'suggest': self._suggestions(screen_key),
        }


    # NOTE: health_learn has a composer here (_scrub / _provider / _corpus /
    # _compose — an LLM over its own material). It is deliberately NOT ported.
    # See the docstring on ask(): Phase A answers only from stored blocks.
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
                    'next_step': s.next_step or '',
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
            'body': self.body or '',
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
