# -*- coding: utf-8 -*-
"""RUNSRC Phase D — the composer offers the pay run's numbers, and saves them.

Handover test 7, plus the two rails the composer half of D1 has to keep:

  * the six are offered as OPERANDS, in their own group, labelled in plain
    words — not merged into the source's field list, where they would read as
    something the source had promised;
  * the save validator accepts them, and still refuses a name that is neither
    a field of the source nor one of the six;
  * a connector whose source has sent NOTHING keeps its old leniency. The six
    being always-known must not turn the "nobody can say" branch off.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import pay_period


@tagged('post_install', '-at_install')
class TestRunsrcPdComposer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cockpit = cls.env['pb.integrations']
        cls.Rule = cls.env['hr.api.transformation.rule']
        cls.Store = cls.env['hr.api.data.store']
        cls.connector = cls.env['hr.integration.connector'].create({
            'name': 'RUNSRC-D composer', 'connector_type': 'zoho'})
        for payload in ({'LOPDays': 1, 'totalDays': 31},
                        {'LOPDays': 0, 'totalDays': 31}):
            cls.Store.create({
                'connector_id': cls.connector.id, 'data_type': 'attendance',
                'employee_external_id': 'RSD-RPC',
                'period_from': '2036-08-01', 'period_to': '2036-08-31',
                'raw_payload': payload, 'extracted_data': payload,
                'state': 'extracted'})
        cls.manager = cls.env['res.users'].create({
            'name': 'RUNSRC-D manager', 'login': 'runsrcd-manager',
            'group_ids': [(4, cls.env.ref(
                'pb_hr_payroll_formula.group_formula_manager').id)]})

    def _spec(self, **over):
        spec = {
            'name': 'Unpaid leave share', 'output_key': 'RSDSHARE',
            'builder_mode': 'excel', 'rule_type': 'sum',
            'source_data_type': 'attendance', 'record_source': 'records',
            'excel_formula': 'IFERROR([LOPDays]/[stddays], 0)',
            'filter_conditions': {'join': 'all', 'rows': []},
            'value_steps': [], 'default_value': 0.0,
        }
        spec.update(over)
        return spec

    # ==================================================================== 7
    def test_07_the_six_are_offered_as_operands(self):
        """Test 7 — the guided lane's operand vocabulary carries them."""
        data = self.Cockpit.with_user(self.manager).rule_composer_data(
            self.connector.id)
        self.assertTrue(data['ok'])
        names = [v['name'] for v in data['run_values']]
        self.assertEqual(names, list(pay_period.NAMESPACE_NAMES))
        labels = {v['name']: v['label'] for v in data['run_values']}
        self.assertEqual(labels['stddays'], "Standard working days")
        self.assertTrue(data['run_values_label'])
        # They are NOT smuggled into the source's own field list.
        for fields in (data['fields'] or {}).values():
            self.assertFalse([f for f in fields if f['path'] in names])

    def test_07b_a_guided_value_step_may_name_one(self):
        """The steps lane accepts an operand and computes with it."""
        out = self.Cockpit.with_user(self.manager).rule_save(
            self.connector.id, self._spec(
                output_key='RSDSTEP', builder_mode='guided',
                excel_formula='',
                value_steps=[{'field': 'stddays', 'contains': 'number'}]))
        self.assertTrue(out['ok'], out.get('msg'))
        rule = self.Rule.browse(out['id'])
        self.assertEqual(rule.value_steps,
                         [{'field': 'stddays', 'contains': 'number'}])

    def test_07c_a_condition_may_compare_against_one(self):
        """And so does a KEEP condition — the other numeric slot."""
        out = self.Cockpit.with_user(self.manager).rule_save(
            self.connector.id, self._spec(
                output_key='RSDCOND', builder_mode='guided',
                excel_formula='', rule_type='count',
                filter_conditions={'join': 'all', 'rows': [
                    {'field': 'paymonth', 'op': 'is', 'value': '8'}]},
                value_steps=[]))
        self.assertTrue(out['ok'], out.get('msg'))

    def test_07d_the_formula_lane_compiles_against_them(self):
        """The Excel lane saves `[stddays]` instead of refusing it."""
        out = self.Cockpit.with_user(self.manager).rule_save(
            self.connector.id, self._spec())
        self.assertTrue(out['ok'], out.get('msg'))

    def test_07e_a_name_that_is_neither_is_still_refused(self):
        """The check still checks. This is the half that could have been lost."""
        out = self.Cockpit.with_user(self.manager).rule_save(
            self.connector.id, self._spec(
                output_key='RSDGHOST',
                excel_formula='IFERROR([ghostfield]/[stddays], 0)'))
        self.assertFalse(out['ok'])
        self.assertIn('ghostfield', out['msg'])

    def test_07f_a_source_that_has_sent_nothing_keeps_its_leniency(self):
        """The rail the six must not switch off.

        An empty catalogue means "nobody can say whether this field is real",
        and every name is accepted. Folding six always-known names into the
        same set would have made that branch unreachable for every brand-new
        connector — a check that could not run, reported as a check that
        failed.
        """
        blank = self.env['hr.integration.connector'].create({
            'name': 'RUNSRC-D blank', 'connector_type': 'zoho'})
        out = self.Cockpit.with_user(self.manager).rule_save(
            blank.id, self._spec(output_key='RSDBLANK',
                                 excel_formula='[anything at all]'))
        self.assertTrue(out['ok'], out.get('msg'))

    # ==================================================================== 6
    def test_06_the_tester_says_which_number_it_used(self):
        """Test 6, through the RPC the screen actually calls."""
        out = self.Cockpit.with_user(self.manager).rule_preview(
            self.connector.id, self._spec())
        self.assertTrue(out['ok'], out.get('error'))
        self.assertAlmostEqual(out['result'], 1.0 / 21.0, 9)
        self.assertEqual(out['period']['std_days'], 21.0)
        self.assertIn('21', out['period']['note'])
        self.assertNotIn('odoo', out['period']['note'].lower())

    def test_02b_the_tester_follows_the_run(self):
        """A run with a hand-typed number moves the tester's answer."""
        self.env['hr.payslip.run'].create({
            'name': 'RUNSRC D composer run',
            'date_start': '2036-08-01', 'date_end': '2036-08-31',
            'pb_std_work_days': 20.0})
        out = self.Cockpit.with_user(self.manager).rule_preview(
            self.connector.id, self._spec())
        self.assertTrue(out['ok'], out.get('error'))
        self.assertAlmostEqual(out['result'], 1.0 / 20.0, 9)
        self.assertIn('pay run', out['period']['note'])

    # =================================================================== 14
    def test_14_the_worked_example_ships_and_never_names_the_platform(self):
        """Test 14 for this module, and the D2 starter being reachable."""
        data = self.Cockpit.with_user(self.manager).rule_composer_data(
            self.connector.id)
        keys = [r['key'] for r in data['recipes']]
        self.assertIn('unpaid_leave', keys)
        recipe = next(r for r in data['recipes'] if r['key'] == 'unpaid_leave')
        self.assertIn('stddays', recipe['spec']['excel_formula'])
        for text in (recipe['title'], recipe['blurb'],
                     data['run_values_label']):
            self.assertNotIn('odoo', (text or '').lower(), text)
