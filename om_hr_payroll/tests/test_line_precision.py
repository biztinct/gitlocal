from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayslipLinePrecision(TransactionCase):
    def setUp(self):
        super().setUp()
        employee = self.env['hr.employee'].create({'name': 'Line precision test'})
        contract = self.env['hr.contract'].create({
            'name': 'Line precision contract', 'employee_id': employee.id,
            'wage': 25419, 'date_start': '2026-01-01', 'state': 'open'})
        self.slip = self.env['hr.payslip'].create({
            'name': 'Line precision test', 'employee_id': employee.id,
            'contract_id': contract.id, 'date_from': '2026-08-01',
            'date_to': '2026-08-31'})
        self.category = self.env['hr.salary.rule.category'].create({
            'name': 'Line precision', 'code': 'LINEPREC'})
        self.rule = self.env['hr.salary.rule'].create({
            'name': 'Line precision', 'code': 'LINEPREC',
            'category_id': self.category.id})

    def line(self, amount):
        return self.env['hr.payslip.line'].create({
            'slip_id': self.slip.id, 'salary_rule_id': self.rule.id,
            'category_id': self.category.id, 'name': 'Line precision',
            'code': 'LINEPREC', 'amount': amount, 'quantity': 1, 'rate': 100})

    def test_large_and_small_positive_and_refund_amounts_keep_cents(self):
        for amount in (11.25, 999.25, 1000.01, 25430.25, -1234.56, 1202094026):
            line = self.line(amount)
            self.assertAlmostEqual(line.amount, amount, places=2)
            self.assertAlmostEqual(line.total, amount, places=2)

    def test_total_recompute_preserves_cents_above_threshold(self):
        line = self.line(25430.25)
        line.write({'quantity': 2, 'rate': 50})
        self.assertAlmostEqual(line.total, 25430.25, places=2)
        line.write({'amount': 3210.11, 'quantity': 1, 'rate': 100})
        self.assertAlmostEqual(line.total, 3210.11, places=2)
