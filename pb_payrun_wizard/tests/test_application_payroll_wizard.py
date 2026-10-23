"""Application payroll must fail closed before creating or cleaning payroll."""
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApplicationPayrunWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['pb.payrun.wizard']
        cls.employee = cls.env['hr.employee'].create({'name': 'App wizard subject', 'company_id': cls.env.company.id})
        cls.contract = cls.env['hr.contract'].create({'name': 'App wizard contract',
            'employee_id': cls.employee.id, 'company_id': cls.env.company.id,
            'wage': 2200., 'state': 'open', 'date_start': '2026-01-01'})
        cls.config = cls.env['hr.formula.config'].create({'name': 'App wizard scheme',
            'code': 'APPWIZTEST', 'country_code': 'VN', 'company_id': cls.env.company.id,
            'state': 'active', 'application_data_enabled': True, 'application_effective_from': '2026-10-01'})
        cls.env['hr.formula.rule'].create({'config_id': cls.config.id, 'name': 'Paid days',
            'code': 'PAIDDAYS', 'column_type': 'input', 'column_role': 'payroll',
            'value_kind': 'quantity', 'is_required': True,
            'application_source_key': 'period.paid_day_equivalents'})
        cls.officer = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Application payroll officer', 'login': 'app.officer@test.invalid',
            'company_id': cls.env.company.id, 'company_ids': [(6, 0, cls.env.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                cls.env.ref('pb_hr_payroll_base.group_payroll_base_officer').id])]})

    def _vals(self):
        return {'name': 'Application October', 'date_start': '2026-10-01', 'date_end': '2026-10-31',
                'formula_config_id': self.config.id, 'employee_ids': self.employee.ids,
                'spreadsheet_skipped': True, 'force_clean': True,
                'application_certification_reason': 'Reviewed October attendance and leave'}

    def test_missing_coverage_blocks_before_run_or_slip_mutation(self):
        counts = [self.env[m].search_count([]) for m in ('hr.payslip.run', 'hr.payslip')]
        with patch.object(type(self.Wizard), '_require_scheme', return_value=self.config), \
             patch.object(type(self.Wizard), '_eligible_employees', return_value=self.employee.ids):
            answer = self.Wizard.prepare_run(self._vals())
        self.assertTrue(answer['blocked'])
        self.assertFalse(answer['application_preflight']['ok'])
        self.assertEqual(counts, [self.env[m].search_count([]) for m in ('hr.payslip.run', 'hr.payslip')])

    def test_sudo_metadata_does_not_grant_officer_certification(self):
        scheme = self.config.with_user(self.officer).sudo()
        with self.assertRaises(AccessError):
            scheme._application_require_access(certify=True)
        with self.assertRaises(AccessError):
            scheme.application_preflight(self.employee.ids, '2026-10-01', '2026-10-31',
                                         {'channels': {'leave': True}})
        with patch.object(type(self.Wizard), '_require_scheme', return_value=scheme), \
             patch.object(type(self.Wizard), '_eligible_employees', return_value=self.employee.ids):
            with self.assertRaises(AccessError):
                self.Wizard.with_user(self.officer).prepare_run(self._vals())

    def test_application_route_does_not_schedule_spreadsheet_cache_refresh(self):
        with patch.object(type(self.Wizard), '_require_scheme', return_value=self.config):
            self.assertEqual(self.Wizard.sync_plan(self._vals()), {'steps': [], 'unroutable': []})

    def test_certification_scope_comes_from_server_eligible_employees(self):
        vals = self._vals()
        vals['application_certifications'] = {'employee_ids': [99999999], 'channels': {'leave': True}}
        cert = self.Wizard._application_certification_payload(vals, self.employee.ids)
        self.assertEqual(cert['employee_ids'], self.employee.ids)

    def test_compute_cannot_change_certified_period_or_employee_scope(self):
        run = self.env['hr.payslip.run'].create({'name': 'Application scoped run',
            'date_start': '2026-10-01', 'date_end': '2026-10-31',
            'pb_formula_config_id': self.config.id, 'application_data_mode': True})
        run.action_certify_application_data({'employee_ids': self.employee.ids,
            'channels': {'leave': True}}, 'Approved scope only')
        payload = {'run_id': run.id, 'date_start': '2026-10-01', 'date_end': '2026-10-31',
                   'formula_config_id': self.config.id, 'emp_ids': self.employee.ids}
        with self.assertRaises(AccessError):
            self.Wizard.compute_batch(dict(payload, date_start='2026-09-01'))
        with self.assertRaises(AccessError):
            self.Wizard.compute_batch(dict(payload, emp_ids=[99999999]))

    def test_loose_spreadsheet_slips_cannot_be_adopted(self):
        slip = self.env['hr.payslip'].create({'name': 'Legacy loose slip', 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'date_from': '2026-10-01', 'date_to': '2026-10-31'})
        with patch.object(type(self.Wizard), '_require_scheme', return_value=self.config), \
             patch.object(type(self.Wizard), '_eligible_employees', return_value=self.employee.ids), \
             patch.object(type(self.Wizard), 'application_data_preview', return_value={'ok': True}):
            with self.assertRaisesRegex(UserError, 'unassigned payslips'):
                self.Wizard.prepare_run(self._vals())
        self.assertFalse(slip.payslip_run_id)

    def test_officer_cannot_edit_sources_even_with_sudo_metadata(self):
        with self.assertRaises(AccessError):
            self.config.with_user(self.officer).sudo().application_save_sources(
                self.config._application_settings_stamp(), {'fixed_standard_days': 99}, [])

    def test_zero_choices_only_show_missing_monthly_items(self):
        rules = self.env['hr.formula.rule'].create([
            {'config_id': self.config.id, 'name': 'Missing bonus', 'code': 'MISSINGBONUS', 'column_type': 'input', 'value_kind': 'money', 'application_source_key': 'period.input.MISSINGBONUS', 'application_zero_allowed': True},
            {'config_id': self.config.id, 'name': 'Existing bonus', 'code': 'EXISTINGBONUS', 'column_type': 'input', 'value_kind': 'money', 'application_source_key': 'period.input.EXISTINGBONUS', 'application_zero_allowed': True}])
        row = self.env['hr.payroll.period.input'].create({'config_id': self.config.id,
            'component_id': rules[1].id, 'employee_id': self.employee.id, 'company_id': self.env.company.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31', 'unit': 'money', 'value_decimal': '20',
            'reason': 'Approved bonus', 'evidence_reference': 'Fixture'})
        row.action_approve()
        with patch.object(type(self.Wizard), '_require_scheme', return_value=self.config), \
             patch.object(type(self.Wizard), '_eligible_employees', return_value=self.employee.ids):
            answer = self.Wizard.application_data_preview(self._vals())
        self.assertEqual([r['key'] for r in answer['zero_options']], ['period.input.MISSINGBONUS'])
        self.assertEqual(answer['zero_options'][0]['missing_count'], 1)
        self.assertEqual(row.state, 'approved')
        self.assertFalse(row.reserved_run_id)
