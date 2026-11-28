# -*- coding: utf-8 -*-
"""Explain-this-screen: the floor, the order, and what a prompt may carry.

WHAT THIS FILE IS PROTECTING
----------------------------
`explain_screen` is the Coach's one control that asks nothing and answers
anyway. Three promises make that acceptable and each gets a test:

  1. THE FLOOR ALWAYS WORKS. Blurb, next step, the screen's own column
     definitions — all written already, all offline, in both languages, with
     no flag and no provider anywhere in the path.
  2. THE ORDER IS THE GUARANTEE. The floor is built and returned BEFORE the
     composer flag is read, so the provider branch can only ever be an
     improvement on an answer the tenant already had. A `contains` check can
     see that the three statements exist; only a test can see their sequence.
  3. WHAT IS ON THE WIRE IS OUR OWN TEXT. Never a record, never a resolved
     live value, never a tenant slot value — and the last of those is the
     interesting one, because the floor the learner reads DOES carry them.

Most of what follows runs with no database at all: `explain_blocks` and
`explain_prompt` are pure functions over the content tree, which is what lets
`docs/tutorial_poc/author/tools/replay_tests.py` execute the floor for three
screens in both languages on every verification pass. The methods that need an
`env` say so by needing one, and report SKIP rather than passing silently.
"""
import ast
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models.learn_intent import (
    EXPLAIN_COLUMNS, build_corpus, compose_prompt, explain_blocks,
    explain_prompt, explain_scenario_offer,
)

# Three screens, chosen for what they are NOT rather than for being typical:
#   payslips   the widest corpus in the module and a full station behind it
#   payruns    the one screen whose next_step carries LIVE tokens
#   govreports a thin screen with a station and few columns
SCREENS = ('payslips', 'payruns', 'govreports')

# Every block kind the drawer knows how to draw (coach.js::_blockHTML). A floor
# that emitted anything else would render through the `default` branch as a
# bare paragraph, which looks fine and is a silent loss of meaning.
DRAWABLE = {'p', 'ok', 'warn', 'refusal', 'who', 'how', 'source', 'steps',
            'calc', 'calc_kpi'}


def _content():
    base = get_module_path('pb_learn')
    with open(os.path.join(base, 'static', 'content', 'learn_content.json'),
              encoding='utf-8') as fh:
        return json.load(fh)


def _pairs(node, out):
    """Every `{en, vi}` prose leaf under `node`."""
    if isinstance(node, dict):
        if set(node) == {'en', 'vi'} and isinstance(node['en'], str):
            out.append(node)
            return
        for value in node.values():
            _pairs(value, out)
    elif isinstance(node, list):
        for value in node:
            _pairs(value, out)


@tagged('post_install', '-at_install')
class TestExplainScreen(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tree = _content()
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'models', 'learn_intent.py'),
                  encoding='utf-8') as fh:
            cls.src = fh.read()
        cls.screens = {s['key']: s for s in cls.tree['screens']}

    # -- 1. the floor, offline, three screens x two languages -------------
    def test_01_the_floor_is_built_for_every_probe_screen(self):
        for key in SCREENS:
            screen = self.screens[key]
            blocks = explain_blocks(self.tree, key, screen.get('next_step'))
            self.assertTrue(blocks, "no floor for %s" % key)
            kinds = [b['kind'] for b in blocks]
            self.assertEqual(kinds[0], 'p', "%s does not open with the blurb" % key)
            self.assertEqual(kinds[-1], 'source',
                             "%s does not say what it is grounded in" % key)
            self.assertIn('ok', kinds, "%s dropped its next step" % key)
            for kind in kinds:
                self.assertIn(kind, DRAWABLE,
                              "%s emits a block kind the drawer cannot draw: %s"
                              % (key, kind))

    def test_01b_every_block_carries_both_languages(self):
        """The whole module ships bilingual; an explanation that fell back to
        English would do it on the screen a Vietnamese reader is stuck on."""
        for key in SCREENS:
            screen = self.screens[key]
            blocks = explain_blocks(self.tree, key, screen.get('next_step'))
            leaves = []
            _pairs(blocks, leaves)
            self.assertTrue(leaves, "%s has no prose at all" % key)
            for leaf in leaves:
                self.assertTrue(leaf['en'].strip(), "%s: empty English" % key)
                self.assertTrue(leaf['vi'].strip(), "%s: empty Vietnamese" % key)
                self.assertNotEqual(
                    leaf['en'], leaf['vi'],
                    "%s: a leaf reaches a Vietnamese reader in English: %r"
                    % (key, leaf['en'][:50]))

    def test_01c_the_block_shape_is_the_ordinary_answer_shape(self):
        """Zero new UI is the point: the drawer renders this with the code it
        already had, so every block needs the four keys `_blockHTML` reads."""
        blocks = explain_blocks(self.tree, 'payslips',
                                self.screens['payslips'].get('next_step'))
        for block in blocks:
            self.assertEqual(set(block), {'capability', 'kind', 'body', 'steps'})
            self.assertEqual(block['capability'], 'any')
            self.assertEqual(block['steps'], [])

    def test_01d_the_columns_are_capped_and_labelled(self):
        columns = [c for c in self.tree['columns'] if c['screen'] == 'payslips']
        self.assertGreater(len(columns), EXPLAIN_COLUMNS,
                           "this screen no longer tests the cap")
        blocks = explain_blocks(self.tree, 'payslips',
                                self.screens['payslips'].get('next_step'))
        # blurb + next step + N columns + source
        self.assertEqual(len(blocks), 2 + EXPLAIN_COLUMNS + 1)
        first_col = blocks[2]['body']['en']
        self.assertTrue(first_col.startswith('<b>'),
                        "a column definition arrives without its label")
        self.assertIn(columns[0]['label']['en'], first_col)

    def test_01e_an_uncovered_screen_gets_no_floor_at_all(self):
        """Not an empty card. The Coach already has an honest sentence for a
        screen it does not cover, and a second one that says nothing is the
        exact failure `ask()` was fixed for in Phase A2."""
        self.assertEqual(explain_blocks(self.tree, 'not_a_screen', ''), [])
        self.assertEqual(explain_blocks(self.tree, None, ''), [])

    def test_01f_the_live_token_survives_into_the_floor_unresolved(self):
        """The pure builder must not try to resolve `{{live:…}}` — resolving
        it is `learn.runtime`'s job and needs a database. What this pins is
        that the token is carried THROUGH rather than dropped, because a
        dropped token is a sentence with a hole in it that nothing would
        report."""
        raw = self.screens['payruns'].get('next_step')
        self.assertIn('{{live:', raw['en'],
                      "payruns no longer carries a live token — pick another "
                      "probe screen, do not weaken the test")
        blocks = explain_blocks(self.tree, 'payruns', raw)
        body = next(b['body'] for b in blocks if b['kind'] == 'ok')
        self.assertIn('{{live:', body['en'])
        self.assertTrue(self.screens['payruns'].get('live_fallback'),
                        "the live sentence has no authored fallback, so every "
                        "tenant that is not the demo world reads nothing")

    # -- 2. the ORDER -----------------------------------------------------
    def test_02_the_floor_is_returned_before_the_flag_is_read(self):
        """Read off the source, because the guarantee IS the sequence.

        A behavioural test can show that the flag being off returns the floor;
        only this can show that the floor exists independently of the flag
        rather than being reconstructed inside the off-branch.
        """
        body = self.src.split('def explain_screen(')[1].split('\n    # ')[0]
        floor_at = body.index('floor = self._explain_floor(')
        flag_at = body.index('self._compose_enabled()')
        provider_at = body.index('self._explain_composed(')
        self.assertLess(floor_at, flag_at,
                        "the composer flag is read before the floor is built")
        self.assertLess(flag_at, provider_at,
                        "the provider branch is not behind the flag")
        self.assertLess(body.index('return floor'), provider_at,
                        "the flag-off path does not return the floor")

    def test_02a_the_floor_call_is_not_conditional_on_the_flag(self):
        """THE CHECK THAT SURVIVED THE MUTATION, closed.

        `test_02` reads the source as TEXT and compares offsets, and
        `contract.json::explain-screen-has-deterministic-floor` greps for
        literals. Both of them pass on

            floor = self._explain_floor(screen_key) if self._compose_enabled() else None

        — the flag read comes second in the line, every pinned token is
        present, and the deterministic floor has become something a tenant
        only gets when the composer is ON. That is the exact inversion of the
        promise, waved through by two green checks. A fail-open check is worse
        than no check, because it is the one people stop reading.

        So the structure is asserted structurally: find the `_explain_floor`
        call in the AST, walk up, and refuse to find any `if`, conditional
        expression or boolean operator on the way whose TEST mentions the
        flag. Same technique as `test_07` and as `_guarded_env_reads` in
        pb_dashboard (Phase 3 ledger).
        """
        tree = ast.parse(self.src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == 'explain_screen')

        def names_the_flag(node):
            return any(isinstance(x, ast.Attribute) and x.attr == '_compose_enabled'
                       or isinstance(x, ast.Name) and x.id == '_compose_enabled'
                       for x in ast.walk(node))

        # parent links, because ast gives none
        parents = {}
        for node in ast.walk(fn):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        calls = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == '_explain_floor']
        self.assertEqual(len(calls), 1,
                         "explain_screen calls _explain_floor %d times — the "
                         "scan cannot say which one is the floor" % len(calls))
        node = calls[0]
        while node in parents:
            parent = parents[node]
            tests = []
            if isinstance(parent, (ast.If, ast.IfExp)):
                tests = [parent.test]
            elif isinstance(parent, ast.BoolOp):
                tests = list(parent.values)
            for test in tests:
                self.assertFalse(
                    names_the_flag(test),
                    "the floor is built inside a branch that tests the "
                    "composer flag — a tenant with the composer OFF would get "
                    "no floor at all, which is the inverse of the promise")
            node = parent

    def test_02b_the_rewrite_falls_back_rather_than_replacing(self):
        """`or floor` is the whole safety argument for the provider branch."""
        body = self.src.split('def explain_screen(')[1].split('\n    # ')[0]
        self.assertIn('self._explain_composed(floor, screen_key, lang) or floor',
                      body)

    def test_02c_the_composed_rewrite_refuses_on_the_same_things(self):
        """Same five doubts as `_compose`: no provider, no material, an empty
        reply, a NO_ANSWER, one that is too long."""
        body = self.src.split('def _explain_composed(')[1].split('\n    @api.model')[0]
        for guard in ('if not provider:', "if not material.strip():",
                      "'NO_ANSWER' in reply", 'len(reply) > _REPLY_CAP',
                      'except Exception:'):
            self.assertIn(guard, body,
                          "the explain rewrite dropped the guard: %s" % guard)

    # -- 3. what a prompt may carry ---------------------------------------
    def test_03_the_explain_prompt_has_its_refusal_contract(self):
        prompt = explain_prompt('payruns', 'SCREEN: Pay runs — a board')
        self.assertIn('payruns', prompt)
        self.assertIn('NO_ANSWER', prompt,
                      "the model was never told how to decline")
        for promise in ('Never invent', 'Never give tax', 'Never claim to have'):
            self.assertIn(promise, prompt, "the prompt dropped: %s" % promise)

    def test_03b_no_live_value_can_reach_either_prompt(self):
        """THE TWO KINDS OF PLACEHOLDER GET OPPOSITE TREATMENT, and that is
        the point of `_wire_leaf`.

        `{{live:…}}` is read out of the DATABASE. Its key is ours, but nothing
        downstream can resolve one inside a composed answer, so a model that
        echoed it would print a brace pair at the reader. It is replaced by the
        authored `live_fallback` — the sentence every tenant that is not the
        demo world already reads.

        `{{gmTierName}}` is a TENANT FACT SLOT and stays. What leaves this
        server is the KEY, which this module wrote; the tenant-typed VALUE is
        never substituted on this path at all. Stripping it would hand the
        model "then , then , then done", and if the model copies the token
        through, the drawer's `gtx()` resolves it for the reader exactly as it
        resolves an authored one. See test_03c for the half that matters.
        """
        for key in SCREENS:
            for lang in ('en_US', 'vi_VN'):
                corpus = build_corpus(self.tree, key, lang)
                self.assertNotIn('{{live:', corpus,
                                 "%s [%s]: a live token reached the corpus"
                                 % (key, lang))
        self.assertNotIn('{{live:', compose_prompt(
            build_corpus(self.tree, 'payruns', 'vi_VN'), 'a question'))
        # And the substitution is the AUTHORED fallback, not a hole.
        screen = self.screens['payruns']
        corpus = build_corpus(self.tree, 'payruns', 'en_US')
        self.assertIn(screen['live_fallback']['en'].split('.')[0], corpus,
                      "the live sentence was dropped instead of falling back")

    def test_03c_no_tenant_typed_value_is_ever_interpolated(self):
        """The property the slot tokens rest on, asserted rather than assumed.

        A tenant administrator's text lives in `learn.tenant.override`, and
        the corpus builder is a pure function over the CONTENT TREE — it has
        no way to read that table, and the tree does not contain it. So the
        slot keys that survive into a prompt carry no tenant text with them.
        """
        blob = json.dumps(self.tree, ensure_ascii=False)
        self.assertNotIn('learn.tenant.override', blob,
                         "the content plane now ships tenant slot VALUES")
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'models', 'learn_intent.py'),
                  encoding='utf-8') as fh:
            src = fh.read()
        for name in ('corpus_sections', 'build_corpus', '_corpus_screen_part'):
            body = src.split('def %s(' % name)[1].split('\ndef ')[0]
            self.assertNotIn('tenant', body,
                             "%s reaches for the override table" % name)
            self.assertNotIn('resolved_tokens', body)

    # -- 4. the corpus cap and its ordering -------------------------------
    def test_04_a_late_glossary_term_now_reaches_the_composer(self):
        """THE PHASE 2 REVIEW FINDING, closed and pinned.

        The cap was 12,000 characters and the glossary — 12,680 on its own —
        was appended LAST, so on every one of the twenty screens the composer
        received a corpus with no glossary in it at all. Every term added
        since Phase C1 was invisible to it. `filing` is the last entry in the
        glossary, so it is the one that proves the ordering rather than the
        one that happens to fit.
        """
        keys = [g['key'] for g in self.tree['glossary']]
        self.assertEqual(keys[-1], 'filing',
                         "the glossary's last entry moved — this test picked "
                         "`filing` because it was the LAST one, and a middle "
                         "entry proves nothing about the cap")
        for lang in ('en_US', 'vi_VN'):
            corpus = build_corpus(self.tree, 'govreports', lang)
            self.assertIn('TERM ', corpus, "no glossary reached the corpus")
            term = self.tree['glossary'][-1]['term']
            self.assertIn(term['vi' if lang.startswith('vi') else 'en'], corpus,
                          "the last glossary term is still being cut off")

    def test_04b_the_sections_are_ordered_by_answer_value(self):
        corpus = build_corpus(self.tree, 'payslips', 'en_US')
        self.assertLess(corpus.index('SCREEN:'), corpus.index('TERM '),
                        "the glossary now comes before the screen context")
        self.assertLess(corpus.index('TERM '), corpus.index('COLUMN '),
                        "columns come before the glossary — a column question "
                        "never reaches the composer, `_match_column` has it")

    def test_04c_truncation_drops_a_whole_section_and_never_half_an_entry(self):
        """A slice at the cap cuts through whatever entry is there, and a
        model completes a sentence it was handed. Forced with a tiny cap."""
        small = build_corpus(self.tree, 'payslips', 'en_US', cap=4000)
        self.assertTrue(small.strip())
        self.assertLessEqual(len(small), 4000)
        self.assertIn('SCREEN:', small, "the most valuable section was dropped")
        self.assertNotIn('TERM ', small,
                         "a 12k glossary fitted inside a 4k cap")
        # Nothing is half an entry: every line still parses as one.
        for line in small.splitlines():
            self.assertFalse(line.endswith('…'), "a line was cut mid-entry")
        full = build_corpus(self.tree, 'payslips', 'en_US')
        self.assertTrue(full.startswith(small.split('\n')[0]))

    def test_04d_the_widest_screen_fits_the_shipped_cap(self):
        """Measured rather than assumed. If content grows past it the drop is
        logged, not silent — but a phase that ships with a section already
        dropped has shipped a composer that cannot see its own glossary."""
        from odoo.addons.pb_learn.models.learn_intent import (
            _CORPUS_SECTIONS, corpus_sections, _CORPUS_CAP,
        )
        worst = 0
        for screen in self.tree['screens']:
            for lang in ('en_US', 'vi_VN'):
                sections = corpus_sections(self.tree, screen['key'], lang)
                total = sum(len('\n'.join(sections[n]))
                            for n in _CORPUS_SECTIONS) + len(_CORPUS_SECTIONS)
                worst = max(worst, total)
        self.assertLessEqual(
            worst, _CORPUS_CAP,
            "the widest corpus is %d characters and the cap is %d, so at least "
            "one section is being dropped on at least one screen" % (worst, _CORPUS_CAP))

    # -- 5. the scenario offer --------------------------------------------
    def test_05_the_offer_only_names_modes_the_scenario_declares(self):
        """A Try button on a Watch-only walkthrough is a control that starts
        nothing. The generator refuses an authored one; this is the derived
        one, which nobody authored and nothing else would catch."""
        by_key = {s['key']: s for s in self.tree['scenarios']}
        for screen in self.tree['screens']:
            watch, try_ = explain_scenario_offer(self.tree, screen['key'])
            for key, mode in ((watch, 'watch'), (try_, 'try')):
                if not key:
                    continue
                self.assertIn(key, by_key,
                              "%s offers a scenario that does not exist" % screen['key'])
                self.assertIn(mode, by_key[key]['modes'],
                              "%s offers %s of %s, which has no such mode"
                              % (screen['key'], mode, key))
                self.assertIn(screen['key'], by_key[key]['screens'])

    def test_05b_every_authored_offer_is_valid_too(self):
        """The generator already refuses a bad one; this is the belt, and it
        reads the SHIPPED tree rather than the authoring source."""
        by_key = {s['key']: s for s in self.tree['scenarios']}
        offers = 0
        for intent in self.tree['intents']:
            for mode in ('watch', 'try'):
                key = intent.get(mode) or ''
                if not key:
                    continue
                offers += 1
                self.assertIn(key, by_key,
                              "%s.%s names no scenario" % (intent['key'], mode))
                self.assertIn(mode, by_key[key]['modes'],
                              "%s.%s names %s, which has no such mode"
                              % (intent['key'], mode, key))
        self.assertTrue(offers, "no intent declares watch or try — this "
                                "assertion is vacuous, not passing")

    # -- 6. the drawer's side ---------------------------------------------
    def test_06_the_drawer_draws_the_button_only_when_the_mode_exists(self):
        """`_offers` is the browser's copy of the same rule. Belt and braces
        on purpose: the payload is trustworthy, and a stale asset bundle is
        not — this is what makes the button structurally unable to appear for
        a mode the engine would refuse."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static', 'src', 'coach', 'coach.js'),
                  encoding='utf-8') as fh:
            coach = fh.read()
        self.assertIn('_offers(key, mode)', coach)
        self.assertIn('(sc.modes || []).includes(mode)', coach)
        self.assertIn('this._offers(a.watch, "watch")', coach)
        self.assertIn('this._offers(a["try"], "try")', coach)
        self.assertIn('"c-explain"', coach)
        # And it reaches the server through the one method, not a product one.
        self.assertIn('"learn.intent", "explain_screen"', coach)

    def test_06b_explain_stores_nothing_and_asks_nothing(self):
        """Nobody typed a question, so there is none to mine. Recording the
        screen somebody pressed a button on would be a different collection
        from the one they consented to (Phase D2)."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static', 'src', 'coach', 'coach.js'),
                  encoding='utf-8') as fh:
            coach = fh.read()
        body = coach.split('async explainScreen()')[1].split('\n    async ')[0]
        self.assertNotIn('_maybeStore', body,
                         "explain-this-screen feeds the question miner")
        self.assertNotIn('learn.question', body)

    # -- 7. the model scope, from this side too ---------------------------
    def test_07_the_explain_path_reads_nothing_outside_learn(self):
        """The same assertion `contract.json` makes, made here as well because
        the contract checker runs at authoring time and this runs on a server:
        the two see the same file and neither is a substitute for the other.
        """
        tree = ast.parse(self.src)
        for name in ('_explain_floor', '_explain_wire_text'):
            fn = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == name)
            models = set()
            for node in ast.walk(fn):
                if (isinstance(node, ast.Subscript)
                        and isinstance(node.slice, ast.Constant)
                        and isinstance(node.slice.value, str)
                        and '.' in node.slice.value
                        and ' ' not in node.slice.value):
                    models.add(node.slice.value)
            self.assertTrue(models, "%s names no model — the scan is broken" % name)
            rogue = {m for m in models if not m.startswith('learn.')}
            self.assertFalse(rogue, "%s reads %s" % (name, rogue))

    # -- 8. the switch that turns any of this on --------------------------
    def test_08_the_composer_switch_re_asks_both_groups_on_the_server(self):
        """A hidden menu is not an access control. `apply()` is reachable over
        RPC by anything holding a session, which is exactly why Phase D2 moved
        the question-mining gates off the convenience wrapper and onto the ORM
        method. Same ruling, one phase later."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'models', 'learn_companion.py'),
                  encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn("APPLY_GROUPS = ('pb_learn.group_learn_author', "
                      "'base.group_system')", src)
        body = src.split('def apply(')[1]
        self.assertIn('self._check_may_apply()', body)
        self.assertLess(body.index('self._check_may_apply()'),
                        body.index('set_param('),
                        "the parameter is written before the gate is checked")

    def test_08b_the_switch_ships_off_and_nothing_defaults_it_on(self):
        """The shipped state of every database, and the state an upgrade
        leaves it in. A default of True anywhere here would switch on a path
        that lets a model write to a learner, on every tenant, silently."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'models', 'learn_companion.py'),
                  encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn("default=lambda self: self.env['learn.intent']"
                      "._compose_enabled()", src,
                      "the switch shows a default rather than the real state")
        self.assertNotIn('default=True', src)
        for rel in ('data/learn_tenant_slots.xml', 'data/learn_question_cron.xml',
                    'data/learn_sidebar_item.xml'):
            path = os.path.join(base, rel)
            if not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as fh:
                self.assertNotIn('pb_learn.compose_enabled', fh.read(),
                                 "%s writes the composer flag at install" % rel)

    def test_08c_the_change_is_logged_with_who_made_it(self):
        """The one control in this module that changes what a learner can be
        shown by something no author wrote. A change nobody can attribute is a
        change nobody made."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'models', 'learn_companion.py'),
                  encoding='utf-8') as fh:
            body = fh.read().split('def apply(')[1]
        self.assertIn('_logger.warning(', body,
                      "the switch is flipped without a log line")
        self.assertIn('self.env.user.login', body)
        self.assertIn('self.env.uid', body)

    def test_07b_the_new_chrome_ships_in_both_languages(self):
        for key in ('explainScreen', 'explainHint', 'screenAnswer', 'notSure'):
            pair = self.tree['chrome'].get(key)
            self.assertTrue(pair, "no chrome string for %s" % key)
            self.assertTrue(pair['en'] and pair['vi'])
            self.assertNotEqual(
                pair['en'], pair['vi'],
                "%s reaches a Vietnamese reader in English" % key)
            self.assertFalse(
                re.search(r'(?<!phê )trình\s+duyệt(?!\s+web)', pair['vi'], re.I),
                "%s uses the browser word as a noun" % key)
