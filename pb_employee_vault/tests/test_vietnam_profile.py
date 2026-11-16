"""Profile reads must not manufacture tax eligibility or expose masked pay."""
from datetime import timedelta
from unittest import SkipTest
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVietnamProfile(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'vietnam.employee.dependent' not in cls.env or 'hr.formula.config' not in cls.env:
            raise SkipTest('Vietnam and formula modules are optional')
        cls.today = fields.Date.today()
        cls.People = cls.env['pb.people']
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Profile Vietnam test', 'company_id': cls.env.company.id,
            'payroll_country': 'VN', 'vietnam_tax_code': 'PROFILE-TAX',
            'vietnam_social_insurance_number': 'PROFILE-SI'})
        cls.contract = cls.env['hr.contract'].with_context(pb_skip_fill_in=True).create({
            'name': 'Current profile test', 'employee_id': cls.emp.id,
            'date_start': cls.today - timedelta(days=10), 'state': 'open', 'wage': 40000000})
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Profile test scheme', 'code': 'PROFILE_TEST_VN',
            'country_code': 'VN', 'company_id': cls.env.company.id})
        for code, amount in [('VNPERSONAL', 15500000), ('VNDEPAMT', 6200000)]:
            cls.env['hr.formula.rule'].create({'config_id': cls.config.id,
                'code': code, 'name': code, 'column_type': 'constant', 'constant_value': amount})

    def setting(self, code, value):
        template = self.env['hr.contract.advantage.template'].create({
            'name': code, 'code': code, 'value_type': 'text' if isinstance(value, str) else 'amount'})
        return self.env['hr.contract.advantage'].create({
            'contract_id': self.contract.id, 'advantage_template_id': template.id,
            **({'text_value': value} if isinstance(value, str) else {'amount': value})})

    def profile(self, unmask=True):
        with patch.object(type(self.People), '_e360_vn_scheme', return_value=self.config):
            data = self.People._e360_vietnam(self.emp, unmask)
        return data, {r['key']: r['value'] for g in data['groups'] for r in g['rows']}

    def test_saved_count_stays_separate_from_pending_documents(self):
        self.setting('VNREGISTER', 4)
        self.setting('VNSIJOIN', 'No')
        self.setting('VNTAXMODE', 'Workbook')
        self.env['vietnam.employee.dependent'].create({
            'employee_id': self.emp.id, 'name': 'Pending child', 'relationship': 'child',
            'status': 'pending', 'effective_from': False, 'tax_allowance': 0})
        before = self.emp.read(['vietnam_dependents_count', 'vietnam_tax_code', 'write_date'])
        data, rows = self.profile()
        self.assertEqual(rows['VNREGISTER'], '4')
        self.assertIn('24,800,000', rows['vn_dependent_total'])
        self.assertIn('15,500,000', rows['VNPERSONAL'])
        self.assertEqual(rows['vn_pending_dependents'], '1')
        self.assertIn('Pending verification', data['groups'][1]['rows'][0]['value'])
        self.assertFalse(data['insurance'])
        self.assertEqual(data['insurance_label'], 'SI: No')
        self.assertTrue(data['tax'])
        self.assertEqual(before, self.emp.read(['vietnam_dependents_count', 'vietnam_tax_code', 'write_date']))

    def test_missing_is_not_zero_or_no_and_zero_is_shown(self):
        data, rows = self.profile()
        self.assertIn('review required', rows['VNREGISTER'])
        self.assertEqual(data['insurance_label'], 'SI: Review required')
        self.setting('VNREGISTER', 0)
        _, rows = self.profile()
        self.assertEqual(rows['VNREGISTER'], '0')
        self.assertEqual(rows['vn_dependent_total'], '0 VND / month')

    def test_future_or_cancelled_contract_does_not_supply_current_settings(self):
        self.setting('VNREGISTER', 2)
        self.contract.write({'state': 'draft', 'date_start': self.today + timedelta(days=10)})
        self.emp.contract_id = self.contract
        _, rows = self.profile()
        self.assertIn('review required', rows['VNREGISTER'])
        self.contract.write({'state': 'cancel'})
        _, rows = self.profile()
        self.assertIn('review required', rows['VNREGISTER'])

    def test_masked_payload_contains_no_salary_or_relief_amounts(self):
        self.setting('VNREGISTER', 2)
        self.setting('VNINSMODE', 'Contract salary')
        data, rows = self.profile(unmask=False)
        text = str(data)
        for amount in ['40,000,000', '15500000', '15,500,000', '6,200,000', '12,400,000']:
            self.assertNotIn(amount, text)
        self.assertEqual(rows['VNREGISTER'], '2')
        self.assertEqual(rows['vn_insurance_salary'], 'Visible to payroll managers only')

    def test_missing_private_allowance_is_not_assumed_zero(self):
        self.setting('VNINSMODE', 'Salary + private insurance')
        _, rows = self.profile()
        self.assertIn('review required', rows['vn_insurance_salary'])
        self.setting('VNPRIVATE', 1000000)
        _, rows = self.profile()
        self.assertEqual(rows['vn_insurance_salary'], '41,000,000 VND / month')

    def test_unreviewed_or_invalid_counts_never_produce_relief(self):
        line = self.setting('VNREGISTER', 1.5)
        _, rows = self.profile()
        self.assertIn('review required', rows['vn_dependent_total'])
        if 'pb_fill' in line._fields:
            line.with_context(pb_fill_in_write=True).write({'amount': 3, 'pb_fill': 'auto', 'pb_checked_at': False})
            _, rows = self.profile()
            self.assertIn('review required', rows['VNREGISTER'])

    def test_other_countries_keep_their_existing_profile(self):
        self.emp.payroll_country = 'ID'
        self.assertIsNone(self.People._e360_vietnam(self.emp, True))

    def test_rates_come_from_scheme_not_legacy_employee_default(self):
        self.config.rule_ids.filtered(lambda r: r.code == 'VNDEPAMT').constant_value = 7000000
        self.setting('VNREGISTER', 2)
        _, rows = self.profile()
        self.assertIn('7,000,000', rows['VNDEPAMT'])
        self.assertIn('14,000,000', rows['vn_dependent_total'])
