# -*- coding: utf-8 -*-
"""Step 6 — the Finish page, the gate, and what a person may finish with.

Two ideas are under test and they pull in opposite directions on purpose:

* **A judgement call never blocks.** Every open decision — a benefit whose
  insurance treatment nobody has chosen, a value that drifted from the rule
  pack, a scenario nobody has agreed to — is LISTED, counted and linked, and the
  setup can still be finished. A screen that refuses until every question is
  answered is a screen people learn to work around.
* **Arithmetic and evidence always block.** A formula the engine cannot read, a
  check that needs attention, checks that were never run or were run against
  different rules: each one is refused by name, on the server, in words.

Every test runs against a real draft made through `bp_start`.
"""
import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

BANNED = ('odoo', 'schema', 'blueprint', 'rule set')


@tagged('post_install', '-at_install')
class TestFinish(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.Blueprint = cls.env['pb.formula.blueprint']
        cls.Config = cls.env['hr.formula.config']
        cls.complete = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_complete_2026')], limit=1)
        cls.essentials = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_standard_2026'), ('state', '!=', 'superseded')],
            limit=1)

    # ------------------------------------------------------------------
    def _draft(self, token, key='blank'):
        res = self.Studio.bp_start({
            'name': 'B6 %s' % token, 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': key,
            'situations': {'audiences': ['local'], 'reallife': ['joiners']},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        return self.Config.browse(res['config_id'])

    def _complete(self, token):
        if not self.complete:
            self.skipTest("the Vietnam · Complete starter is not installed")
        return self._draft(token, 'vn_complete_2026')

    def _codes(self, res):
        return {r['code'] for r in (res.get('gate') or {}).get('reasons', [])
                or res.get('reasons') or []}

    # ==================================================================
    # 1 — the gate, one refusal at a time
    # ==================================================================
    def test_a_configuration_nobody_checked_is_refused_and_says_so(self):
        config = self._complete('b6-gate-notrun')
        data = self.Studio.bp_finish_data(config.id)
        self.assertTrue(data['ok'])
        self.assertFalse(data['gate']['ok'])
        self.assertIn('not_run', self._codes(data))
        reason = next(r for r in data['gate']['reasons'] if r['code'] == 'not_run')
        self.assertEqual(reason['step'], 'test',
                         "a refusal has to say which step fixes it")
        refused = self.Studio.bp_finish(config.id)
        self.assertFalse(refused['ok'])
        self.assertTrue(refused['reason'])
        self.assertEqual(
            self.Blueprint.search([('config_id', '=', config.id)]).state, 'draft',
            "a refused finish changes nothing")

    def test_checks_run_then_a_change_makes_them_stale(self):
        config = self._complete('b6-gate-stale')
        self.assertTrue(self.Studio.bp_run_checks(config.id).get('ok'))
        self.assertTrue(self.Studio.bp_finish_data(config.id)['gate']['ok'],
                        "a checked starter is ready to finish")

        # Move a real number: the same edit the Tax tab makes.
        relief = config.rule_ids.filtered(lambda r: r.code == 'DEDUCTSELF')
        if not relief:
            self.skipTest("this starter has no personal-relief constant")
        relief.constant_value = (relief.constant_value or 0.0) + 1000000.0

        data = self.Studio.bp_finish_data(config.id)
        self.assertFalse(data['gate']['ok'])
        self.assertIn('stale', self._codes(data))
        self.assertTrue(data['checks']['stale'])

    def test_a_check_that_needs_attention_blocks_and_is_counted(self):
        config = self._complete('b6-gate-failed')
        self.assertTrue(self.Studio.bp_run_checks(config.id).get('ok'))
        sample = config.sample_data_ids[:1]
        expected = json.loads(sample.expected_values_json or '{}')
        key = 'NET' if 'NET' in expected else (list(expected) or [None])[0]
        if not key:
            self.skipTest("this starter's scenarios expect nothing")
        expected[key] = float(expected[key] or 0.0) + 12345.0
        sample.expected_values_json = json.dumps(expected)
        self.assertTrue(self.Studio.bp_run_checks(config.id).get('ok'))

        data = self.Studio.bp_finish_data(config.id)
        self.assertIn('failed', self._codes(data))
        self.assertTrue(data['checks']['failed'])

    def test_nobody_has_agreed_to_any_numbers(self):
        config = self._complete('b6-gate-unconfirmed')
        config.sample_data_ids.write({'expected_confirmed': False})
        self.assertTrue(self.Studio.bp_run_checks(config.id).get('ok'))
        codes = self._codes(self.Studio.bp_finish_data(config.id))
        self.assertIn('unconfirmed', codes)
        self.assertNotIn('failed', codes,
                         "a scenario waiting for confirmation is not a failure")

    def test_a_formula_the_engine_cannot_read_is_refused_by_name(self):
        config = self._draft('b6-gate-unreadable')
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'code': 'LOOPA', 'name': 'Loop A',
            'column_type': 'formula', 'excel_formula': '=B1', 'column_letter': 'A',
        })
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'code': 'LOOPB', 'name': 'Loop B',
            'column_type': 'formula', 'excel_formula': '=A1', 'column_letter': 'B',
        })
        config.invalidate_recordset()
        data = self.Studio.bp_finish_data(config.id)
        self.assertFalse(data['gate']['ok'])
        self.assertIn('circular', self._codes(data))
        self.assertEqual(
            next(r for r in data['gate']['reasons']
                 if r['code'] == 'circular')['step'], 'rules')

    def test_a_blank_canvas_has_nothing_to_prove(self):
        """The evidence gates apply to arithmetic, and a configuration with no
        calculations has none. Somebody building their own components from
        nothing must still be able to finish (the plan's step 8)."""
        config = self._draft('b6-gate-blank')
        data = self.Studio.bp_finish_data(config.id)
        self.assertTrue(data['gate']['ok'], data['gate']['reasons'])
        done = self.Studio.bp_finish(config.id)
        self.assertTrue(done['ok'], done.get('reason'))

    def test_finishing_twice_is_not_an_error(self):
        config = self._draft('b6-idempotent')
        self.assertTrue(self.Studio.bp_finish(config.id)['ok'])
        again = self.Studio.bp_finish(config.id)
        self.assertTrue(again['ok'])
        self.assertTrue(again['already'])

    # ==================================================================
    # 2 — a finished setup, read back and reopened
    # ==================================================================
    def test_a_finished_setup_reads_back_and_can_be_revisited(self):
        config = self._draft('b6-reopen')
        self.assertTrue(self.Studio.bp_finish(config.id)['ok'])
        data = self.Studio.bp_finish_data(config.id)
        self.assertTrue(data['finished'])
        self.assertTrue(data['editable'],
                        "the configuration is still a draft, so it may be revisited")
        self.assertTrue(data['identity']['finished_by'],
                        "a finished page says whose decision it was")

        back = self.Studio.bp_reopen(config.id)
        self.assertTrue(back['ok'], back.get('reason'))
        self.assertEqual(
            self.Blueprint.search([('config_id', '=', config.id)]).state, 'draft')
        self.assertFalse(self.Studio.bp_finish_data(config.id)['finished'])

    def test_a_configuration_that_left_draft_cannot_be_reopened(self):
        config = self._draft('b6-reopen-refused')
        self.assertTrue(self.Studio.bp_finish(config.id)['ok'])
        config.state = 'validated'
        refused = self.Studio.bp_reopen(config.id)
        self.assertFalse(refused['ok'])
        self.assertIn('components grid', refused['reason'])

    # ==================================================================
    # 3 — discarding
    # ==================================================================
    def test_discard_says_what_it_would_destroy(self):
        config = self._complete('b6-discard')
        check = self.Studio.bp_discard_check(config.id)
        self.assertTrue(check['ok'])
        self.assertTrue(check['allowed'])
        self.assertEqual(check['name'], config.name)
        self.assertEqual(check['counts']['components'], len(config.rule_ids))
        self.assertTrue(self.Studio.bp_discard(config.id)['ok'])
        self.assertFalse(config.exists())

    def test_a_configuration_that_has_paid_somebody_is_never_discarded(self):
        config = self._draft('b6-discard-refused')
        with patch.object(type(self.Studio), '_has_payslips', return_value=True):
            check = self.Studio.bp_discard_check(config.id)
            self.assertTrue(check['ok'])
            self.assertFalse(check['allowed'])
            self.assertIn('payslips', check['reason'])
            refused = self.Studio.bp_discard(config.id)
            self.assertFalse(refused['ok'])
        self.assertTrue(config.exists(), "nothing was deleted")

    # ==================================================================
    # 4 — the decisions list, from all four sources
    # ==================================================================
    def test_every_kind_of_open_decision_reaches_the_list(self):
        config = self._complete('b6-decisions')
        blueprint = self.Blueprint.search([('config_id', '=', config.id)])

        # (a) a scenario nobody has agreed to.
        sample = config.sample_data_ids[:1]
        sample.expected_confirmed = False

        # (b) a statutory value that drifted from the rule pack.
        relief = config.rule_ids.filtered(lambda r: r.code == 'DEDUCTSELF')
        if relief:
            relief.constant_value = (relief.constant_value or 0.0) - 500000.0

        # (c) an optional task somebody finished, undermined by a change since.
        # Written the way "Mark as done" writes it — the snapshot is the whole
        # point of the test, so it is set here rather than through a mapping
        # board this test has no business driving.
        status = blueprint.optional_status()
        status['mapping'].update({
            'status': 'configured',
            'snapshot': [r.code for r in config.rule_ids
                         if r.column_type == 'input' and r.code],
        })
        blueprint.set_optional_status(status)
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'code': 'B6NEWIN', 'name': 'A new input',
            'column_type': 'input', 'column_letter': 'ZZ',
        })

        data = self.Studio.bp_finish_data(config.id)
        kinds = {item['kind'] for item in data['decisions']}
        self.assertIn('scenario', kinds)
        self.assertIn('task', kinds)
        if relief:
            self.assertIn('pack', kinds)
        # (d) a component whose sentence still asks a question — the Complete
        # starter ships several (the employer-paid tax on private health cover,
        # and the scope of the overtime exemption).
        self.assertIn('component', kinds)

        for item in data['decisions']:
            self.assertTrue(item['text'], "a decision without words is a dot")
            self.assertIn(item['step'],
                          ('start', 'rules', 'connect', 'outputs', 'test',
                           'finish'))
        self.assertGreaterEqual(data['decisions_total'], len(data['decisions']))

    def test_open_decisions_do_not_block_finishing(self):
        config = self._complete('b6-decisions-dont-block')
        self.assertTrue(self.Studio.bp_run_checks(config.id).get('ok'))
        data = self.Studio.bp_finish_data(config.id)
        self.assertTrue(data['decisions_total'],
                        "the Complete starter asks at least one question")
        self.assertTrue(data['gate']['ok'], data['gate']['reasons'])
        self.assertTrue(self.Studio.bp_finish(config.id)['ok'])

    # ==================================================================
    # 5 — the page itself
    # ==================================================================
    def test_the_page_says_what_this_configuration_is(self):
        config = self._complete('b6-identity')
        data = self.Studio.bp_finish_data(config.id)
        identity = data['identity']
        self.assertEqual(identity['name'], config.name)
        self.assertEqual(identity['code'], config.code)
        self.assertEqual(identity['company'], config.company_id.name)
        self.assertTrue(identity['cycle'])
        self.assertTrue(identity['starter'])
        self.assertTrue(identity['calendar']['payday_rule_label'])
        self.assertTrue(identity['calendar']['late_label'])
        self.assertTrue(identity['payment']['bank_label'])
        self.assertEqual(identity['payment']['currency'], config.currency_id.name)
        self.assertIn('Local employees', identity['situations'])

        self.assertEqual(data['counts']['components'], len(config.rule_ids))
        self.assertEqual(
            data['counts']['inputs'],
            len(config.rule_ids.filtered(lambda r: r.column_type == 'input')))
        tasks = {row['task'] for row in data['optional']}
        self.assertEqual(tasks, {'mapping', 'payslip', 'approvals'})

    def test_the_checks_line_counts_the_live_list_not_the_stamp(self):
        """BP43 — adding a scenario changes no formula, so nothing is stale;
        a line reading "5 checks passed" over six rows is a page arguing with
        itself."""
        config = self._complete('b6-live-counts')
        self.assertTrue(self.Studio.bp_run_checks(config.id).get('ok'))
        before = self.Studio.bp_finish_data(config.id)['checks']
        self.env['hr.formula.sample.data'].create({
            'config_id': config.id, 'name': 'One more person',
            'source_type': 'manual',
            'input_values_json': json.dumps({'BASIC': 11000000.0}),
            'expected_values_json': json.dumps({'NET': 1.0}),
            'expected_confirmed': False,
        })
        after = self.Studio.bp_finish_data(config.id)['checks']
        self.assertEqual(after['checks'], before['checks'] + 1)
        self.assertEqual(after['pending'], before['pending'] + 1)
        self.assertFalse(after['stale'],
                         "a new scenario is not a change to the rules")

    def test_a_configuration_that_does_not_exist_is_refused_in_words(self):
        for method in ('bp_finish_data', 'bp_discard_check', 'bp_reopen'):
            res = getattr(self.Studio, method)(999999999)
            self.assertFalse(res['ok'])
            self.assertTrue(res['reason'])
            self.assertNotIn('Traceback', res['reason'])

    def test_nothing_on_this_page_says_a_word_a_payroll_manager_should_not_read(self):
        config = self._complete('b6-white-label')
        self.Studio.bp_run_checks(config.id)
        blob = json.dumps(self.Studio.bp_finish_data(config.id),
                          default=str).lower()
        for word in BANNED:
            self.assertNotIn(word, blob,
                             "the Finish payload says “%s”" % word)
