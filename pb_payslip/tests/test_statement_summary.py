"""The statement must reconcile refunds, prior payments and a real zero net."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStatementSummary(TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({'name': 'Statement summary test'})
        self.contract = self.env['hr.contract'].create({
            'name': 'Statement summary test', 'employee_id': self.employee.id,
            'date_start': '2026-01-01', 'wage': 1000,
        })
        self.slip = self.env['hr.payslip'].create({
            'name': 'Statement summary test', 'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
        })
        self.rule = self.env['hr.salary.rule'].search([], limit=1)

    def line(self, code, amount, role, category='DED', detail=False):
        cat = self.env['hr.salary.rule.category'].search([('code', '=', category)], limit=1)
        return self.env['hr.payslip.line'].create({
            'slip_id': self.slip.id, 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'salary_rule_id': self.rule.id,
            'name': code, 'code': code, 'category_id': cat.id,
            'amount': amount, 'quantity': 1, 'rate': 100,
            'pay_role': role, 'component_detail': detail,
        })

    def test_zero_net_remains_zero_and_gap_is_explicit(self):
        self.line('GROSS', 1000, 'earning', 'GROSS')
        self.line('TAX', 100, 'deduction')
        self.line('TAKEHOME', 0, 'net', 'NET')
        result = self.slip._pb_build_statement()
        self.assertEqual(result['net'], 0)
        self.assertEqual(result['adjustment'], 900)
        self.assertEqual(result['adjustment_label'], 'Other net-pay adjustment')

    def test_prior_payment_is_separate_from_deductions(self):
        self.line('GROSS', 1000, 'earning', 'GROSS')
        self.line('TAX', -100, 'deduction')
        self.line('ADVPAY', 400, 'deduction')
        self.line('NET', 500, 'net', 'NET')
        result = self.slip._pb_build_statement()
        self.assertEqual(result['deductions_total'], 100)
        self.assertEqual(result['adjustment'], 400)
        self.assertEqual(result['adjustment_label'], 'Mid-month advance (paid in cycle 1)')

    def test_addition_is_not_an_absolute_value_reduction(self):
        self.line('GROSS', 1000, 'earning', 'GROSS')
        self.line('TAX', 100, 'deduction')
        self.line('NET', 925, 'net', 'NET')
        result = self.slip._pb_build_statement()
        self.assertEqual(result['adjustment'], -25)
        self.assertEqual(result['net'], result['gross'] - result['deductions_total'] - result['adjustment'])

    def test_classified_refund_follows_the_report_convention(self):
        if not self.env['ir.module.module'].search_count([('name', '=', 'pb_payruns'), ('state', '=', 'installed')]):
            self.skipTest('The pay-run refund convention is optional')
        self.line('GROSS', 1000, 'earning', 'GROSS')
        self.line('INSURANCE', 100, 'deduction')
        self.line('TAX_REFUND', -200, 'deduction')
        self.line('NET', 1100, 'net', 'NET')
        result = self.slip._pb_build_statement()
        self.assertEqual(result['deductions_total'], -100)
        self.assertEqual(result['adjustment'], 0)
        self.assertEqual(next(row['amount'] for row in result['deductions'] if row['code'] == 'TAX_REFUND'), -200)
        self.assertEqual(result['deductions_total'], self.slip.line_ids.pb_pay_totals()['deductions'])

    def test_currency_precision_and_fractional_adjustment(self):
        currency = self.env['res.currency'].search([('name', '=', 'SGD')], limit=1)
        config = self.env['hr.formula.config'].create({
            'name': 'Statement cents test', 'code': 'STATEMENT_CENTS_TEST',
            'country_code': 'SG', 'currency_id': currency.id,
            'company_id': self.env.company.id,
        })
        self.slip.formula_config_id = config
        self.line('GROSS', 1200.25, 'earning', 'GROSS')
        self.line('TAX', 100, 'deduction')
        self.line('NET', 1100, 'net', 'NET')
        result = self.slip._pb_build_statement()
        self.assertEqual(result['currency_precision'], 2)
        self.assertEqual(result['adjustment'], .25)
