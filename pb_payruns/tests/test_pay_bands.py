# -*- coding: utf-8 -*-
"""Every screen must read Gross and Deductions the same way.

The Rize August 2026 run reported ₫2,060,124,305 gross and ₫289,886,044
deductions on the pay run, and ₫0 gross with ₫10,747,123,945 deductions on the
Payroll Report opened from that same run's own button. Both were arithmetic on
the same 4,830 payslip lines. The report classified them by
`hr_salary_rule_category.code`, and that scheme has no `GROSS` category at all
while its `DED` category holds insurance bases, tax bases and day counts —
working figures, not money withheld.

`hr.payslip.line.pb_pay_totals` is now the one answer, and
`hr.payslip.run._pb_bucket_sql` is the same rule in SQL because a run cannot
afford the ORM. These tests hold the two together.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayBands(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.employee = self.env['hr.employee'].create({
            'name': 'Bands Person', 'company_id': self.company.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'Bands contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })
        self.rule = self.env['hr.salary.rule'].search([], limit=1)
        self.run = self.env['hr.payslip.run'].create({
            'name': 'Bands August', 'date_start': '2026-08-01',
            'date_end': '2026-08-31'})
        self.slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': 'Bands slip',
            'contract_id': self.contract.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'company_id': self.company.id,
            'payslip_run_id': self.run.id,
        })
        Line = self.env['hr.payslip.line']
        self.role_aware = 'pay_role' in Line._fields
        self.detail_aware = 'component_detail' in Line._fields

    def _cat(self, code):
        category = self.env['hr.salary.rule.category'].search(
            [('code', '=', code)], limit=1)
        if not category:
            self.skipTest("no '%s' salary-rule category in this database" % code)
        return category

    def _line(self, code, category_code, amount, detail=False, role=None):
        vals = {
            'slip_id': self.slip.id, 'name': code, 'code': code,
            'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            'employee_id': self.employee.id, 'contract_id': self.contract.id,
            'category_id': self._cat(category_code).id,
            'salary_rule_id': self.rule.id,
        }
        if detail:
            if not self.detail_aware:
                self.skipTest("the formula engine is not installed here")
            vals['component_detail'] = True
        if role:
            if not self.role_aware:
                self.skipTest("the formula engine is not installed here")
            vals['pay_role'] = role
        return self.env['hr.payslip.line'].create(vals)

    def _totals(self):
        return self.slip.line_ids.pb_pay_totals()

    # ------------------------------------------- what the scheme itself says
    def test_1_the_pay_role_beats_the_rule_category(self):
        """The rize shape: real gross filed under a category called DED."""
        self._line('TONGTHUNHAP', 'DED', 9100000.0, role='earning')
        self._line('BHXH', 'DED', 910000.0, role='deduction')
        totals = self._totals()
        self.assertEqual(totals['gross'], 9100000.0)
        self.assertEqual(totals['deductions'], 910000.0)

    def test_2_a_working_figure_is_not_money_withheld(self):
        """An insurance base sits in DED and nobody's pay is reduced by it."""
        self._line('LUONG', 'BASIC', 9100000.0, role='earning')
        self._line('LUONGBHXH', 'DED', 8000000.0, role='info')
        self._line('BHXH', 'DED', 840000.0, role='deduction')
        totals = self._totals()
        self.assertEqual(totals['deductions'], 840000.0,
                         "the insurance base was counted as money withheld")
        self.assertEqual(totals['gross'], 9100000.0)

    def test_3_a_component_that_is_both_has_no_band(self):
        self._line('LUONG', 'BASIC', 9100000.0, role='earning')
        self._line('ADJ', 'DED', 500000.0, role='mixed')
        self.assertEqual(self._totals()['deductions'], 0.0)

    def test_4_an_employer_cost_is_not_taken_off_anybody(self):
        self._line('LUONG', 'BASIC', 9100000.0, role='earning')
        self._line('BHXHCTY', 'COMP', 1700000.0, role='employer_cost')
        totals = self._totals()
        self.assertEqual(totals['deductions'], 0.0)
        self.assertEqual(totals['employer_cost'], 1700000.0)

    # ------------------------------------------------ counting money once
    def test_5_a_subtotal_is_not_added_on_top_of_its_own_parts(self):
        self._line('TOTALDED', 'DED', 910000.0, role='deduction')
        self._line('BHXH', 'DED', 700000.0, role='deduction', detail=True)
        self._line('BHYT', 'DED', 210000.0, role='deduction', detail=True)
        self.assertEqual(self._totals()['deductions'], 910000.0)

    def test_6_the_schemes_own_gross_line_beats_its_parts(self):
        self._line('GROSS', 'GROSS', 9100000.0, role='earning')
        self._line('BASIC', 'BASIC', 7000000.0, role='earning', detail=True)
        self._line('MEAL', 'ALW', 2100000.0, role='earning', detail=True)
        self.assertEqual(self._totals()['gross'], 9100000.0)

    def test_7_deductions_signed_both_ways_add_up_rather_than_cancel(self):
        """The demo shape: insurance negative, the advance positive."""
        self._line('LUONG', 'BASIC', 30000000.0, role='earning')
        self._line('SIEMP', 'DED', -900000.0, role='deduction')
        self._line('ADVPAY', 'DED', 600000.0, role='deduction')
        self.assertEqual(self._totals()['deductions'], 1500000.0)

    # ----------------------------------------- the fallback, for old lines
    def test_8_a_line_with_no_role_still_reads_its_category(self):
        self._line('BASIC', 'BASIC', 7000000.0)
        self._line('MEAL', 'ALW', 2100000.0)
        self._line('BHXH', 'DED', 910000.0)
        self._line('NET', 'NET', 8190000.0)
        totals = self._totals()
        self.assertEqual(totals['gross'], 9100000.0)
        self.assertEqual(totals['deductions'], 910000.0)
        self.assertEqual(totals['net'], 8190000.0)

    # ------------------------------------------------- naming take-home pay
    def test_9_the_net_line_is_the_one_the_scheme_calls_net(self):
        """The demo shape: FULLPAY and NET both in the NET category."""
        self._line('FULLPAY', 'NET', 25000000.0, role='info')
        self._line('NET', 'NET', 4898403.0, role='net')
        self.assertEqual(self.slip.line_ids.pb_net_line().code, 'NET')
        self.assertEqual(self.slip.pb_net_amount(), 4898403.0)

    def test_10_a_classified_scheme_with_no_net_hands_out_no_figure(self):
        """Better no number than the wrong one — C17, never derive money."""
        self._line('GROSS', 'NET', 25000000.0, role='info')
        self.assertFalse(self.slip.line_ids.pb_net_line())
        self.assertEqual(self.slip.pb_net_amount(), 0.0)

    def test_11_an_unclassified_scheme_still_finds_its_net_by_category(self):
        self._line('NETPAY', 'NET', 8190000.0)
        self.assertEqual(self.slip.line_ids.pb_net_line().code, 'NETPAY')

    # ------------------------------------------------------- the breakdowns
    def test_12_a_breakdown_adds_up_to_the_figure_above_it(self):
        self._line('TONGTHUNHAP', 'DED', 9100000.0, role='earning')
        self._line('BHXH', 'DED', 700000.0, role='deduction')
        self._line('BHYT', 'DED', 210000.0, role='deduction')
        self._line('LUONGBHXH', 'DED', 8000000.0, role='info')
        lines = self.slip.line_ids
        self.assertEqual(
            sum(abs(l.total) for l in lines.pb_lines_in_band('deductions')),
            lines.pb_pay_totals()['deductions'])
        self.assertEqual(
            sum(l.total for l in lines.pb_lines_in_band('gross')),
            lines.pb_pay_totals()['gross'])

    def test_13_the_search_domain_finds_what_the_total_counts(self):
        self._line('TONGTHUNHAP', 'DED', 9100000.0, role='earning')
        self._line('BHXH', 'DED', 700000.0, role='deduction')
        self._line('LUONGBHXH', 'DED', 8000000.0, role='info')
        Line = self.env['hr.payslip.line']
        found = Line.search([('slip_id', '=', self.slip.id)]
                            + Line.pb_band_domain('deductions'))
        self.assertEqual(found.mapped('code'), ['BHXH'])

    # ------------------------------------- the report and the run must agree
    def test_14_the_helper_and_the_pay_runs_kpi_band_give_one_answer(self):
        """The whole point. Same payslip, two aggregations, one set of figures."""
        self._line('TONGTHUNHAP', 'DED', 9100000.0, role='earning')
        self._line('LUONGBHXH', 'DED', 8000000.0, role='info')
        self._line('BHXH', 'DED', 700000.0, role='deduction')
        self._line('ADVPAY', 'DED', 210000.0, role='deduction')
        self._line('BHXHCTY', 'COMP', 1700000.0, role='employer_cost')
        self._line('NET', 'NET', 8190000.0, role='net')
        self.run.invalidate_recordset()
        totals = self.slip.line_ids.pb_pay_totals()
        self.assertEqual(totals['gross'], self.run.pb_total_gross)
        self.assertEqual(totals['deductions'], self.run.pb_total_deductions)
        self.assertEqual(totals['net'], self.run.pb_total_net)
        self.assertEqual(totals['employer_cost'],
                         self.run.pb_total_employer_cost)

    def test_15_they_agree_on_the_reference_demo_shape(self):
        """Deductions written negative and ADDED IN, a mid-month advance
        written positive, and a running total sharing the NET category with
        the real net line. The shape that broke five things at once."""
        self._line('GROSS', 'GROSS', 30000000.0, role='earning')
        self._line('SIEMP', 'DED', -2400000.0, role='deduction')
        self._line('PIT', 'DED', -690000.0, role='deduction')
        self._line('ADVPAY', 'DED', 19593613.0, role='deduction')
        self._line('FULLPAY', 'NET', 26910000.0, role='info')
        self._line('NET', 'NET', 7316387.0, role='net')
        self.run.invalidate_recordset()
        totals = self.slip.line_ids.pb_pay_totals()
        self.assertEqual(totals['deductions'], 22683613.0,
                         "the advance cancelled the insurance and the tax")
        self.assertEqual(totals['gross'], self.run.pb_total_gross)
        self.assertEqual(totals['deductions'], self.run.pb_total_deductions)
        self.assertEqual(totals['net'], self.run.pb_total_net)
        self.assertEqual(self.slip.pb_net_amount(), 7316387.0)

    def test_16_they_agree_on_an_unclassified_scheme_too(self):
        self._line('BASIC', 'BASIC', 7000000.0)
        self._line('MEAL', 'ALW', 2100000.0)
        self._line('BHXH', 'DED', 910000.0)
        self._line('NET', 'NET', 8190000.0)
        self.run.invalidate_recordset()
        totals = self.slip.line_ids.pb_pay_totals()
        self.assertEqual(totals['gross'], self.run.pb_total_gross)
        self.assertEqual(totals['deductions'], self.run.pb_total_deductions)
        self.assertEqual(totals['net'], self.run.pb_total_net)
