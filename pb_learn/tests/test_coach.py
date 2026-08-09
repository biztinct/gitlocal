# -*- coding: utf-8 -*-
"""The Payobook Coach: precision, capability, and the honesty rules.

The honesty rules are the point of this file. They are not conventions to be
remembered — each is asserted, because "the Coach never invents a rate" is only
true for as long as nothing has quietly made it false.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

# Questions a payroll officer or an owner might genuinely type into a help box
# on a payroll system, and that this system must never help with. Every one of
# them must come back as the `compliance` refusal and nothing else — a
# retrieval score is a guess, and a guess about how to reduce a statutory
# obligation reads as instruction.
#
# These are not hard to mis-match: "làm sao để giảm đóng BHXH" shares real
# topic words with the `bhxh` glossary intent, which explains what the 8% is.
# Scored rather than denied, the Coach answers "how do I under-declare" with
# the contribution rates.
OUT_OF_SCOPE = [
    "how do we pay less tax on salaries",
    "is there a way to avoid tax on the bonus",
    "how do we under declare the insurance base",
    "làm sao để giảm đóng bhxh",
    "có cách nào lách phần thuế này không",
    "khai thấp lương đóng bảo hiểm được không",
]
# NOT out of scope: "what is BHXH" or "why did the net change". Those are the
# questions the Coach exists for, and refusing them would be its own failure.

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")


@tagged('post_install', '-at_install')
class TestCoach(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intent = cls.env['learn.intent']
        cls.Screen = cls.env['learn.screen']

    # ------------------------------------------------------------ precision
    def test_01_out_of_scope_questions_resolve_to_nothing(self):
        """A wrong answer costs more than no answer.

        Especially here: the Coach sits on a payroll system, and a confident
        product answer to "how do we pay less" is worse than silence.
        """
        leaked = []
        for q in OUT_OF_SCOPE:
            for screen in (None, 'payruns', 'payslips'):
                key = self.Intent.resolve(q, screen)
                # `compliance` is the RIGHT answer: an explicit refusal that
                # then points at where the rates live and who owns the policy.
                # Anything else is the Coach answering a tax-advice question
                # with product content.
                if key and key != 'compliance':
                    leaked.append('%r on %s -> %s' % (q, screen, key))
        self.assertFalse(leaked, "Out-of-scope questions the Coach answered:\n  "
                                 + "\n  ".join(leaked))

    def test_01b_advice_questions_are_refused_and_routed(self):
        """Refusing is half of it. A dead end leaves the person exactly where
        they started, so the refusal must name who owns the policy and where
        the numbers actually come from."""
        for q in OUT_OF_SCOPE:
            res = self.Intent.ask(q, 'payslips')
            self.assertTrue(res['matched'], "no refusal offered for %r" % q)
            kinds = {b['kind'] for b in res['blocks']}
            self.assertIn('refusal', kinds, "%r was not refused" % q)
            self.assertIn('who', kinds, "%r refused with no route to a decision owner" % q)
            self.assertIn('how', kinds, "%r refused with nothing to do instead" % q)

    def test_02_the_refusal_actually_says_something(self):
        """A refusal that renders empty is indistinguishable from a crash.

        Refusing on purpose beats matching nothing and falling through to a
        generic list, but only if the refusal has words in it.
        """
        answer = self.Intent._answer('compliance', 'payslips')
        self.assertTrue(answer, "the compliance refusal is missing entirely")
        text = " ".join(b['body']['en'] for b in answer['blocks']
                        if isinstance(b.get('body'), dict))
        self.assertTrue(text.strip(), "the compliance refusal says nothing at all")

    # --------------------------------------------------------------- recall
    def test_03_every_intent_is_reachable_by_its_own_label(self):
        """If the Coach offers a question as a suggestion, asking it must work.

        The suggestion buttons submit the label verbatim, so a label that does
        not resolve to its own intent is a dead button.
        """
        misses = []
        for intent in self.Intent.search([]):
            for lang in ('en_US', 'vi_VN'):
                label = intent.with_context(lang=lang).label
                got = self.Intent.resolve(label, None)
                if got != intent.key:
                    misses.append('%s [%s] %r -> %s' % (intent.key, lang, label[:50], got))
        self.assertFalse(misses, "Intents unreachable by their own label:\n  "
                                 + "\n  ".join(misses))

    def test_04_every_suggested_question_resolves(self):
        misses = []
        for screen in self.Screen.search([]):
            for intent in screen.suggest_ids:
                got = self.Intent.resolve(intent.label, screen.key)
                if got != intent.key:
                    misses.append('%s on %s -> %s' % (intent.key, screen.key, got))
        self.assertFalse(misses, "Suggested questions that do not resolve:\n  "
                                 + "\n  ".join(misses))

    # ----------------------------------------------------------- capability
    def test_05_capability_is_read_from_the_real_gate(self):
        """Not from a role name the tutorial keeps its own copy of."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        base = self.env.ref('base.group_user').id
        officer = self.env.ref('pb_hr_payroll_base.group_payroll_base_officer').id
        manager = self.env.ref('pb_hr_payroll_base.group_payroll_base_manager').id

        plain = Users.create({'name': 'Coach Plain', 'login': 'coach_plain_test',
                              'group_ids': [(6, 0, [base])]})
        clerk = Users.create({'name': 'Coach Clerk', 'login': 'coach_clerk_test',
                              'group_ids': [(6, 0, [base, officer])]})
        boss = Users.create({'name': 'Coach Boss', 'login': 'coach_boss_test',
                             'group_ids': [(6, 0, [base, manager])]})

        # With no screen in play, the group is the only thing that decides.
        # A signed-in user with NO payroll group is 'no_access', not
        # 'operator': telling someone who holds nothing that they can run a
        # payroll is the confidently-wrong answer this gate exists to prevent.
        self.assertEqual(self.env(user=plain)['learn.intent']._capability(None), 'no_access')
        self.assertEqual(self.env(user=clerk)['learn.intent']._capability(None), 'operator')
        self.assertEqual(self.env(user=boss)['learn.intent']._capability(None), 'manager')

        # A final approver is 'manager' too. They are not in the manager group,
        # and the honest answer to "can I approve this run" from them is still
        # yes — the capability follows the GATE, not the group's name.
        approver = Users.create({
            'name': 'Coach Approver', 'login': 'coach_approver_test',
            'group_ids': [(6, 0, [
                base, self.env.ref('pb_hr_payroll_base.group_payroll_final_approver').id])],
        })
        self.assertEqual(self.env(user=approver)['learn.intent']._capability(None), 'manager')

        # VISIBILITY WINS, and the ordering is deliberate. Run Payroll's leaf
        # is group-gated in pb_sidebar, so a user without those groups does not
        # have it in their sidebar — and the honest answer to "how do I compute
        # July" is then "you cannot even see that screen", not a lecture about
        # a permission they also do not have.
        self.assertEqual(
            self.env(user=plain)['learn.intent']._capability('runpayroll'), 'no_access')

    def test_06_the_capability_answer_differs(self):
        """`approve` is the intent whose answer depends on permission.

        Every capability must get an answer, and the answer for someone who
        cannot approve must actually refuse — not quietly show the affirmative
        and leave them to discover the greyed-out button themselves.

        (The `approve` intent is Run A2 content; this test is what tells A2 it
        is not finished until every reader gets a true answer.)
        """
        blocks_by_cap = {}
        intent = self.Intent.search([('key', '=', 'approve')], limit=1)
        self.assertTrue(intent, "the approve intent is missing")
        for block in intent.block_ids:
            blocks_by_cap.setdefault(block.capability, []).append(block.kind)
        for cap in ('no_access', 'operator', 'manager'):
            self.assertIn(cap, blocks_by_cap, "no answer for capability %s" % cap)
        self.assertIn('refusal', blocks_by_cap['no_access'],
                      "someone without the screen is not told so")
        self.assertIn('ok', blocks_by_cap['manager'],
                      "a manager is not told they can approve")

    def test_07_a_refusal_always_says_who_can_and_how_to_ask(self):
        """A refusal that stops at "you can't" leaves the person stuck, which
        is the exact state the Coach exists to get them out of."""
        bad = []
        for intent in self.Intent.search([]):
            caps = {b.capability for b in intent.block_ids if b.kind == 'refusal'}
            for cap in caps:
                kinds = {b.kind for b in intent.block_ids if b.capability == cap}
                if not ({'who', 'how'} & kinds):
                    bad.append('%s [%s]' % (intent.key, cap))
        self.assertFalse(bad, "Refusals with no route forward:\n  " + "\n  ".join(bad))

    # -------------------------------------------------------------- honesty
    def test_08_the_coach_can_never_act(self):
        """No control an answer renders may reach a product method.

        Asserted against the source: every `data-act` the Coach emits must be
        in COACH_ACTIONS, which contains only its own controls.
        """
        path = os.path.join(get_module_path('pb_learn'), 'static/src/coach/coach.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        declared = set(re.findall(r'"(c-[a-z-]+)"',
                                  src.split('COACH_ACTIONS = new Set([')[1].split('])')[0]))
        emitted = set(re.findall(r'data-act="(c-[a-z-]+)"', src))
        self.assertTrue(declared, "COACH_ACTIONS could not be read")
        rogue = emitted - declared
        self.assertFalse(rogue, "The Coach renders actions outside its own set: %s" % rogue)
        # And nothing in the answer path calls the action service directly.
        answer_src = src.split('_answerHTML(')[1].split('\n    }')[0]
        self.assertNotIn('doAction', answer_src,
                         "an answer block calls doAction — the Coach must never act")

    def test_09_every_factual_intent_cites_a_source(self):
        """Anything that makes a claim about the product says where it comes
        from. An answer with no provenance is indistinguishable from a guess."""
        FACTUAL = {'p', 'steps', 'calc', 'calc_kpi', 'ok', 'warn'}
        missing = []
        for intent in self.Intent.search([]):
            if intent.dynamic != 'none':
                continue   # a screen blurb cites the screen it is on
            by_cap = {}
            for b in intent.block_ids:
                by_cap.setdefault(b.capability, set()).add(b.kind)
            for cap, kinds in by_cap.items():
                if (kinds & FACTUAL) and 'source' not in kinds:
                    missing.append('%s [%s]' % (intent.key, cap))
        self.assertFalse(missing, "Factual answers with no 'grounded in' line:\n  "
                                  + "\n  ".join(missing))

    def test_10_a_miss_names_what_it_can_answer(self):
        """Never a bare "I don't know"."""
        # Genuinely unmatched, and NOT a tax-advice question — that now has its
        # own deliberate refusal, so it would exercise the wrong path.
        for screen in ('payruns', 'payslips', 'import'):
            res = self.Intent.ask("how do I change the office wifi password", screen)
            self.assertFalse(res['matched'], "matched a question it has no content for")
            self.assertTrue(res['suggest'],
                            "no suggestions offered after a miss on %s" % screen)
            for s in res['suggest']:
                self.assertTrue(s['label']['en'] and s['label']['vi'])

    def test_11_an_uncovered_screen_is_admitted_not_guessed(self):
        """Off the Pay Run map the Coach must say so, not answer about Pay Run."""
        res = self.Intent.ask("what does this screen do", 'not_a_real_screen')
        # `whatpage` is screens='*', so it resolves — but with no screen record
        # its dynamic blurb is empty rather than a borrowed one.
        if res['matched']:
            bodies = [b['body'] for b in res['blocks']]
            for b in bodies:
                if isinstance(b, dict):
                    self.assertNotIn('Run Payroll', b.get('en') or '',
                                     "answered about another screen entirely")

    # -------------------------------------------------------------- content
    def test_12_no_unresolved_tokens_in_any_answer(self):
        tokens = self.env['learn.tenant.override'].resolved_tokens()
        leaked = []
        for intent in self.Intent.search([]):
            for screen in [None] + self.Screen.search([]).mapped('key'):
                answer = self.Intent._answer(intent.key, screen)
                for block in answer['blocks']:
                    for value in (block.get('body'), ):
                        if not isinstance(value, dict):
                            continue
                        for lang in ('en', 'vi'):
                            for key in TOKEN_RE.findall(value.get(lang) or ''):
                                if key not in tokens:
                                    leaked.append('%s -> {{%s}}' % (intent.key, key))
        self.assertFalse(leaked, "Undeclared tenant slots in answers:\n  "
                                 + "\n  ".join(sorted(set(leaked))))

    def test_13_show_me_anchors_are_registered(self):
        """Extends the Phase-1 anchor lint to the Coach.

        A `show_me` anchor nobody registers means the point-at button scrolls to
        nothing, which is exactly the "confidently wrong" failure this whole
        registry exists to prevent.
        """
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/anchors.json'), encoding='utf-8') as fh:
            reg = json.load(fh)
        declared = set(reg['product']) | set(reg['practice'])
        patterns = tuple(reg['pattern'])

        def known(key):
            return key in declared or key.startswith(patterns)

        unknown = []
        for intent in self.Intent.search([]):
            for a in (intent.show_me or '').split(','):
                a = a.strip()
                if a and not known(a):
                    unknown.append('%s show_me=%s' % (intent.key, a))
        for step in self.env['learn.intent.step'].search([]):
            if step.anchor and not known(step.anchor):
                unknown.append('step %s anchor=%s' % (step.id, step.anchor))
        self.assertFalse(unknown, "Coach anchors nothing registers:\n  "
                                  + "\n  ".join(sorted(set(unknown))))

    def test_14_every_screen_can_actually_be_detected(self):
        """A screen the Coach cannot recognise is a whole screen's content,
        silently unreachable — and it fails in the most misleading way: the
        Coach says "I don't have lessons for this screen yet" while sitting on
        a screen that has a full lesson.

        Asserts a matcher of ANY kind, because only three of the eight CRM
        leaves are client actions with a tag; the rest are act_windows found by
        xml-id or model.
        """
        blind = []
        for screen in self.Screen.search([]):
            tags, xmlids, models_ = screen._matchers()
            if not (tags or xmlids or models_):
                blind.append(screen.key)
        self.assertFalse(blind, "Screens the Coach can never detect: %s" % blind)

    def test_14b_matchers_come_from_the_real_sidebar_leaf(self):
        """Not from a copy. If the leaf's action changes, the Coach follows."""
        checked = 0
        for screen in self.Screen.search([]):
            if not screen.sidebar_key:
                continue
            item = self.env.ref(screen.sidebar_key, raise_if_not_found=False)
            if not item:
                continue
            checked += 1
            tags, xmlids, models_ = screen._matchers()
            declared = {(item.sudo().action_xmlid or '').strip()}
            self.assertTrue(
                declared & set(xmlids) or (item.sudo().action_tag or '') in tags,
                "%s does not inherit its leaf's own action" % screen.key)
        # Seven of the eight Phase A screens name a leaf. The import wizard is
        # a flow, not a destination — it has none, and is resolved by its tag.
        self.assertGreaterEqual(checked, 7,
                                "expected every Pay Run leaf screen to name its leaf")

    def test_15_refusals_are_reachable_but_never_advertised(self):
        """Offering "ask me how to pay less tax" invites the exact question the
        Coach exists to decline. It must resolve; it must not be suggested."""
        compliance = self.Intent.search([('key', '=', 'compliance')], limit=1)
        self.assertTrue(compliance, "the compliance refusal is missing")
        self.assertFalse(compliance.offer, "the compliance refusal is advertised")
        self.assertEqual(self.Intent.resolve("làm sao để giảm đóng bhxh", 'payslips'),
                         'compliance', "the compliance refusal is not reachable")
        for screen in self.Screen.search([]):
            self.assertNotIn(compliance, screen.suggest_ids,
                             "%s suggests the compliance refusal" % screen.key)

    def _resolve_screen(self, tag, xmlid, model):
        """Server-side mirror of the frontend's two-pass resolution."""
        screens = self.Screen.search([])
        matchers = {s.key: s._matchers() for s in screens}
        for s in screens:                      # pass 0: the leaf's OWN action
            own_tag, own_xmlid = s._primary()
            if (tag and own_tag and tag == own_tag) or (xmlid and own_xmlid and xmlid == own_xmlid):
                return s.key
        for s in screens:                      # pass 1: any exact matcher
            tags, xmlids, _models = matchers[s.key]
            if (tag and tag in tags) or (xmlid and xmlid in xmlids):
                return s.key
        for s in screens:                      # pass 2: broad model
            _tags, _xmlids, models_ = matchers[s.key]
            if model and model in models_:
                return s.key
        return None

    def test_16_each_screen_resolves_to_ITSELF_from_its_own_leaf(self):
        """The bug this replaces was the worst kind: confidently wrong.

        In health_learn a single-pass matcher let a broad model rule shadow an
        exact one, and the Coach grounded on the wrong screen — offering one
        screen's questions to someone reading another. Exact matches must win
        across ALL screens before any model match is considered.
        """
        wrong = []
        for screen in self.Screen.search([]):
            if not screen.sidebar_key:
                continue
            item = self.env.ref(screen.sidebar_key, raise_if_not_found=False)
            if not item:
                continue
            item = item.sudo()
            got = self._resolve_screen(item.action_tag, item.action_xmlid, None)
            if got != screen.key:
                wrong.append('%s (its own action) -> %s' % (screen.key, got))
        self.assertFalse(wrong, "Screens that do not resolve to themselves:\n  "
                                + "\n  ".join(wrong))

    def test_17_a_broad_model_rule_never_shadows_an_exact_one(self):
        """hr.payslip.run is claimed by Pay Runs and hr.payslip by Payslips.

        If two screens ever claim the same model the broad pass picks one
        arbitrarily, and the Coach grounds on whichever the search happened to
        return first — wrong, and wrong differently on different databases."""
        model_owners = {}
        for screen in self.Screen.search([]):
            _t, _x, models_ = screen._matchers()
            for m in models_:
                model_owners.setdefault(m, []).append(screen.key)
        for model, owners in model_owners.items():
            self.assertEqual(len(owners), 1,
                             "%s is claimed by more than one screen: %s — the "
                             "broad pass would pick one arbitrarily"
                             % (model, owners))

    # ---------------------------------------------------- column glossary
    def test_18_a_column_question_gets_a_column_answer(self):
        """A question about a TILE, not a procedure.

        "What does Need review mean here?" is the most common question a
        payroll reviewer actually asks, and no curated intent covers it. It is
        deterministic — a written definition, looked up — so missing it would
        be a miss the Coach had no excuse for.
        """
        res = self.Intent.ask("what does need review mean", 'payslips')
        self.assertTrue(res['matched'], "still cannot answer a column question")
        self.assertEqual(res.get('source_kind'), 'column')
        body = res['blocks'][0]['body']
        self.assertIn('flag', body['en'].lower())
        self.assertTrue(body['vi'] and body['vi'] != body['en'],
                        "the column answer is not translated")

    def test_19_column_matching_is_narrow(self):
        """A loose match would answer "what is the status of this run" with a
        column definition, which is worse than missing."""
        Column = self.env['learn.column']
        self.assertIsNotNone(Column.match("what does in pipeline count", 'payruns'))
        # Wrong screen: the board's columns must not answer on Payslips.
        self.assertIsNone(Column.match("what does in pipeline count", 'payslips'))
        # No screen at all: nothing to scope by, so no answer.
        self.assertIsNone(Column.match("what does in pipeline count", None))

    def test_20_every_column_is_written_in_both_languages(self):
        thin = []
        for col in self.env['learn.column'].search([]):
            for lang in ('en_US', 'vi_VN'):
                body = col.with_context(lang=lang).body
                if not body or len(body) < 40:
                    thin.append('%s/%s [%s]' % (col.screen, col.key, lang))
            if col.with_context(lang='vi_VN').body == col.with_context(lang='en_US').body:
                thin.append('%s/%s untranslated' % (col.screen, col.key))
        self.assertFalse(thin, "Columns with thin or untranslated definitions:\n  "
                               + "\n  ".join(thin))

    # ------------------------------------------------------- NO composer
    # health_learn ends its answer chain with a composer: an LLM over its own
    # corpus, used when no single intent covers the question. Payobook Phase A
    # deliberately does not have one, and these tests are how that stays true.
    #
    # This is not squeamishness about models. It is that the failure mode here
    # is a fluent sentence about a contribution rate that nobody wrote and no
    # test can check, read by someone who is about to approve a month of
    # salaries. An honest miss is always an acceptable outcome on this system.

    def test_21_there_is_no_composer_and_no_provider_seam(self):
        """Asserted by reflection, not by reading the file.

        A future port of health_learn's composer would arrive as exactly these
        method names, and it must not arrive quietly.
        """
        for name in ('_compose', '_provider', '_corpus', '_scrub'):
            self.assertFalse(hasattr(self.Intent, name),
                             "learn.intent grew %s — Phase A ships no LLM path, and "
                             "adding one is a design decision, not a refactor" % name)

    def test_21b_no_provider_is_imported_anywhere_in_the_module(self):
        """The seam is an import as much as a method.

        Scanned as source rather than by reflection: an import inside a
        function body is invisible to hasattr and would still ship the
        dependency.
        """
        base = get_module_path('pb_learn')
        banned = ('hr.ai.provider.config', 'hr_development_ai', 'ai_providers',
                  'generate_text')
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(base, 'models')):
            for name in files:
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(root, name), encoding='utf-8') as fh:
                    src = fh.read()
                for token in banned:
                    if token in src:
                        offenders.append('%s -> %s' % (name, token))
        self.assertFalse(offenders,
                         "An AI provider reached the answer path:\n  " + "\n  ".join(offenders))

    def test_22_an_unanswerable_question_falls_back_honestly(self):
        """With no composer there is exactly one fallback left, and it must
        never break and never invent."""
        res = self.Intent.ask("how do I change the office wifi password", 'payslips')
        self.assertFalse(res['matched'], "matched a question it has no content for")
        self.assertTrue(res['suggest'], "an honest miss offered nothing to ask instead")
        self.assertNotIn('source_kind', res,
                         "a miss is claiming a source it does not have")
