from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestNativeSections(TransactionCase):
    def test_only_platform_administrators_can_save(self):
        employee = new_test_user(self.env, login='settings-section-employee', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.env['res.config.settings'].with_user(employee).pb_save_section('branding', {})

    def test_section_cannot_write_unrelated_fields(self):
        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].pb_save_section('pay_run_review', {'module_crm': True})

    def test_zero_disables_review_without_writing_other_parameters(self):
        settings = self.env['res.config.settings']
        if 'pb_review_change_pct' not in settings._fields:
            self.skipTest('The optional payslip review module is absent.')
        params = self.env['ir.config_parameter']
        key = settings._fields['pb_review_change_pct'].config_parameter
        other = params.search([('key', '!=', key)])
        before = {p.key: p.value for p in other}
        settings.pb_save_section('pay_run_review', {'pb_review_change_pct': 0})
        self.assertEqual(params.get_param(key), '0')
        self.assertEqual(before, {p.key: p.value for p in params.search([('key', '!=', key)])})

    def test_attendance_only_changes_current_company(self):
        settings = self.env['res.config.settings']
        if 'pb_timesheet_block_run' not in settings._fields:
            self.skipTest('The optional timesheet approvals module is absent.')
        other = self.env['res.company'].create({'name': 'Attendance approval scope'})
        for company, flag in [(self.env.company, False), (other, True)]:
            settings.with_company(company).pb_save_section('attendance_approvals', {'pb_timesheet_block_run': flag})
        self.assertFalse(self.env.company.pb_timesheet_block_run)
        self.assertTrue(other.pb_timesheet_block_run)
