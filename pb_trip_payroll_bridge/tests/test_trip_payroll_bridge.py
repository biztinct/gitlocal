# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for the trip → payroll bridge (§6 case 8).

TRIPDAYS/PERDIEM are injected only for the in-period days of APPROVED trips, and
PERDIEM honours channel exclusivity — an expense-channel trip contributes 0.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTripPayrollBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.vnd = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.company.currency_id
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Trip Payroll', 'company_id': cls.company.id})
        cls.d_from = date(2026, 6, 1)
        cls.d_to = date(2026, 6, 30)
        cls.slip = cls.env['hr.payslip'].create({
            'employee_id': cls.emp.id, 'date_from': cls.d_from, 'date_to': cls.d_to})
        cls.config = cls._make_config('ZZTRIP1', ['TRIPDAYS', 'PERDIEM', 'WAGE'])
        cls.config_plain = cls._make_config('ZZTRIP2', ['WAGE'])

    @classmethod
    def _make_config(cls, code, codes):
        cfg = cls.env['hr.formula.config'].create({
            'name': code, 'code': code, 'country_code': 'VN',
            'company_id': cls.company.id})
        for rcode in codes:
            cls.env['hr.formula.rule'].create({
                'config_id': cfg.id, 'name': rcode, 'code': rcode,
                'column_type': 'input'})
        return cfg

    def _approved_trip(self, d_from, d_to, rate, channel):
        policy = self.env['pb.trip.policy'].create({
            'name': 'P-%s' % channel, 'per_diem_rate': rate,
            'currency_id': self.vnd.id, 'per_diem_channel': channel})
        trip = self.env['pb.business.trip'].create({
            'employee_id': self.emp.id, 'date_from': d_from, 'date_to': d_to,
            'purpose': 'x', 'per_diem_rate': rate, 'policy_id': policy.id,
            'currency_id': self.vnd.id, 'company_id': self.company.id})
        trip.action_submit()
        trip.action_manager_approve()
        trip.action_finance_approve()
        trip.action_hr_approve()
        return trip

    def test_01_straddling_period_payroll_channel(self):
        # 29 May → 3 Jun: only Jun 1/2/3 fall inside the slip period
        self._approved_trip(date(2026, 5, 29), date(2026, 6, 3), 200000.0, 'payroll')
        values = self.slip._get_formula_input_values(self.config)
        self.assertEqual(values['TRIPDAYS'], 3)
        self.assertAlmostEqual(values['PERDIEM'], 600000.0)

    def test_02_expense_channel_contributes_zero_perdiem(self):
        # expense-channel per-diem is paid via hr.expense, so PERDIEM = 0,
        # but the days still count as TRIPDAYS
        self._approved_trip(date(2026, 6, 10), date(2026, 6, 12), 200000.0, 'expense')
        values = self.slip._get_formula_input_values(self.config)
        self.assertEqual(values['TRIPDAYS'], 3)
        self.assertAlmostEqual(values['PERDIEM'], 0.0)

    def test_03_config_without_codes_untouched(self):
        self._approved_trip(date(2026, 6, 10), date(2026, 6, 12), 200000.0, 'payroll')
        values = self.slip._get_formula_input_values(self.config_plain)
        self.assertNotIn('TRIPDAYS', values)
        self.assertNotIn('PERDIEM', values)
        self.assertIn('WAGE', values)
