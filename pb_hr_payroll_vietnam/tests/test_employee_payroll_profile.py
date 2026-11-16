"""Full details must agree with the drawer without changing payroll data."""
from datetime import timedelta
from unittest import SkipTest
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.hr_employee_payroll_profile import INSURANCE_KEYS, SHARED_KEYS, profile_html


@tagged('post_install', '-at_install')
class TestEmployeePayrollProfile(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.people = cls.env.get('pb.people')
        if cls.people is None or not hasattr(cls.people, '_e360_vietnam'):
            raise SkipTest('Employee vault is optional')
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Full profile consistency', 'company_id': cls.env.company.id,
            'payroll_country': 'VN', 'vietnam_tax_code': 'PROFILE-TAX',
            'vietnam_social_insurance_number': 'PROFILE-SI'})
        cls.contract = cls.env['hr.contract'].with_context(pb_skip_fill_in=True).create({
            'name': 'Profile consistency', 'employee_id': cls.emp.id,
            'date_start': fields.Date.today() - timedelta(days=10), 'state': 'open', 'wage': 40000000})
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Full profile scheme', 'code': 'FULL_PROFILE_TEST_VN',
            'country_code': 'VN', 'company_id': cls.env.company.id})
        for code, amount in [('VNPERSONAL', 15500000), ('VNDEPAMT', 6200000)]:
            cls.env['hr.formula.rule'].create({'config_id': cls.config.id,
                'code': code, 'name': code, 'column_type': 'constant', 'constant_value': amount})
        template = cls.env['hr.contract.advantage.template'].create({
            'name': 'VNREGISTER', 'code': 'VNREGISTER', 'value_type': 'amount'})
        cls.count_line = cls.env['hr.contract.advantage'].create({
            'contract_id': cls.contract.id, 'advantage_template_id': template.id, 'amount': 2})
        cls.hr = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Profile HR reader', 'login': 'full_profile_hr',
            'group_ids': [(6, 0, [cls.env.ref('om_hr_payroll.group_hr_payroll_user').id])]})

    def compute(self, emp=None, config=True):
        emp = emp if emp is not None else self.emp
        with patch.object(type(self.people), '_e360_vn_scheme', return_value=self.config if config else None):
            emp._compute_vn_payroll_profile()
            drawer = self.people.with_env(emp.env)._e360_vietnam(emp, self.people.with_env(emp.env)._vault_unmask_wage())
        return drawer

    def test_same_values_as_drawer_without_writing_legacy_fields(self):
        before = self.emp.read(['write_date', 'vn_monthly_tax_allowance', 'vietnam_dependents_count'])
        drawer = self.compute()
        self.assertTrue(self.emp.vn_uses_payroll_profile)
        tax = self.emp.vn_payroll_tax_summary
        insurance = self.emp.vn_payroll_insurance_summary
        for row in drawer['groups'][0]['rows']:
            target = insurance if row['key'] in INSURANCE_KEYS else tax
            self.assertIn(str(row['value']), target)
            if row['key'] in SHARED_KEYS:
                self.assertIn(str(row['value']), insurance)
        for value in ['15,500,000', '6,200,000', '12,400,000']:
            self.assertIn(value, tax)
        self.assertNotIn('11,000,000', tax)
        self.assertEqual(before, self.emp.read(['write_date', 'vn_monthly_tax_allowance', 'vietnam_dependents_count']))

    def test_missing_scheme_does_not_fall_back_to_eleven_million(self):
        self.compute(config=False)
        self.assertTrue(self.emp.vn_uses_payroll_profile)
        self.assertIn('Not recorded', self.emp.vn_payroll_tax_summary)
        self.assertNotIn('11,000,000', self.emp.vn_payroll_tax_summary)

    def test_zero_and_unknown_dependents_remain_distinct(self):
        self.count_line.amount = 0
        self.compute()
        self.assertIn('>0 VND / month<', self.emp.vn_payroll_tax_summary)
        self.contract.state = 'cancel'
        self.compute()
        self.assertIn('Not recorded', self.emp.vn_payroll_tax_summary)
        self.assertNotIn('>0 VND / month<', self.emp.vn_payroll_tax_summary)

    def test_hr_reader_cannot_reuse_managers_cached_amounts(self):
        self.compute()
        hr_emp = self.emp.with_user(self.hr)
        self.compute(hr_emp)
        html = hr_emp.vn_payroll_tax_summary + hr_emp.vn_payroll_insurance_summary
        self.assertIn('Visible to payroll managers only', html)
        for amount in ['15,500,000', '6,200,000', '12,400,000', '40,000,000']:
            self.assertNotIn(amount, html)
        self.assertIn('15,500,000', self.emp.vn_payroll_tax_summary)

    def test_pending_documents_do_not_replace_registered_count(self):
        dep = self.env['vietnam.employee.dependent'].create({
            'employee_id': self.emp.id, 'name': 'Pending child', 'relationship': 'child',
            'status': 'pending', 'effective_from': False, 'tax_allowance': 0})
        self.compute()
        self.assertIn('12,400,000', self.emp.vn_payroll_tax_summary)
        self.assertEqual(dep.status, 'pending')
        self.assertFalse(dep.effective_from)
        self.assertEqual(dep.tax_allowance, 0)

    def test_other_countries_keep_original_form(self):
        self.emp.payroll_country = 'ID'
        self.compute()
        self.assertFalse(self.emp.vn_uses_payroll_profile)
        self.assertFalse(self.emp.vn_payroll_tax_summary)

    def test_html_values_are_escaped(self):
        html = profile_html([{'label': '<b>Label</b>', 'value': '<script>alert(1)</script>'}], '<img src=x onerror=alert(1)>')
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img ', html)
        self.assertIn('&lt;script&gt;', html)

    def test_full_form_hides_legacy_allowances_when_using_payroll_summary(self):
        view = self.env.ref('pb_hr_payroll_vietnam.view_employee_form_vietnam_insurance')
        arch = etree.fromstring(view.arch_db.encode())
        self.assertEqual(arch.xpath('//field[@name="vn_monthly_tax_allowance"]/ancestor::group[@string="Tax Configuration"]/@invisible'), ['vn_uses_payroll_profile'])
        self.assertEqual(arch.xpath('//field[@name="tax_allowance"]/@column_invisible'), ['parent.vn_uses_payroll_profile'])
        # Compile the real inherited employee form too, not only our fragment.
        combined = self.emp.get_view(view_id=self.env.ref('hr.view_employee_form').id, view_type='form')
        self.assertIn('vn_payroll_tax_summary', combined['arch'])
