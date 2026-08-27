# -*- coding: utf-8 -*-
"""The KPI band must report the run it is attached to.

ABM's June 2026 run showed **Total gross 0.00, Deductions 0.00, Total net 0.00**
above 146 employees. Two independent reasons, and neither raised anything:

  * `_compute_pb_totals` reads the payslip tables with raw SQL, so a payslip
    attached to the run in the same transaction is invisible to it until the
    ORM's write buffer is flushed — and a recompute triggered by that very
    write is the normal case, not an exotic one;

  * gross was read only from a salary-rule category coded `GROSS`. A scheme
    built by importing a payroll workbook has a basic and a list of allowances
    and no such category, so ₫1.9bn of basic pay reported as ₫0.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRunTotals(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.employee = self.env['hr.employee'].create({
            'name': 'Totals Person', 'company_id': self.company.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'Totals contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })
        self.rule = self.env['hr.salary.rule'].search([], limit=1)
        self.run = self.env['hr.payslip.run'].create({
            'name': 'Totals June', 'date_start': '2026-06-01',
            'date_end': '2026-06-30'})

    def _cat(self, code):
        return self.env['hr.salary.rule.category'].search(
            [('code', '=', code)], limit=1)

    def _slip_with(self, amounts, in_run=True, details=()):
        """One payslip carrying `{category code: amount}`.

        `details` names the category codes whose line is folded into another
        line's total, so the run must count the total and not this one.
        """
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': 'Totals slip',
            'contract_id': self.contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id,
            'payslip_run_id': self.run.id if in_run else False,
        })
        for code, amount in amounts.items():
            self._line(slip, code, code, amount, detail=code in details)
        return slip

    def _line(self, slip, code, category_code, amount, detail=False):
        category = self._cat(category_code)
        if not category:
            self.skipTest("no '%s' salary-rule category in this database"
                          % category_code)
        vals = {
            'slip_id': slip.id, 'name': code, 'code': code,
            'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            'employee_id': self.employee.id, 'contract_id': self.contract.id,
            'category_id': category.id, 'salary_rule_id': self.rule.id,
        }
        if detail:
            if 'component_detail' not in self.env['hr.payslip.line']._fields:
                self.skipTest("the formula engine is not installed here")
            vals['component_detail'] = True
        return self.env['hr.payslip.line'].create(vals)

    # ---------------------------------------------- what the SQL can see
    def test_a_payslip_attached_in_this_transaction_is_counted(self):
        """Not after the next commit — now, when the screen reads the field."""
        self._slip_with({'NET': 1000.0})
        self.assertEqual(self.run.pb_employee_count, 1)
        self.assertEqual(self.run.pb_total_net, 1000.0)

    def test_a_payslip_moved_into_the_run_updates_the_totals(self):
        slip = self._slip_with({'NET': 1000.0}, in_run=False)
        self.assertEqual(self.run.pb_total_net, 0.0)
        self.run.write({'slip_ids': [(4, slip.id)]})
        self.assertEqual(self.run.pb_total_net, 1000.0)

    # ------------------------------------------------------- what gross means
    def test_gross_falls_back_to_basic_plus_allowances(self):
        self._slip_with({'BASIC': 9000.0, 'ALW': 500.0})
        self.assertEqual(self.run.pb_total_gross, 9500.0)

    def test_an_explicit_gross_component_still_wins(self):
        self._slip_with({'GROSS': 8000.0, 'BASIC': 9000.0})
        self.assertEqual(self.run.pb_total_gross, 8000.0)

    # ------------------------------------------- each dong counted once
    def test_a_component_folded_into_a_total_is_not_counted_twice(self):
        """ABM's June run: `SI-HI-IU Total 10.5%` is subtracted from net pay,
        and so is `Total Deduction` — but only because the second one contains
        the first. Summing both reported ₫5,058,029,390 of deductions against
        ₫1.9bn of gross."""
        slip = self._slip_with({'NET': 8500.0})
        self._line(slip, 'DEDAGG', 'DED', 1000.0)
        self._line(slip, 'SIAMT', 'DED', 945.0, detail=True)
        self._line(slip, 'PITAMT', 'DED', 55.0, detail=True)
        self.assertEqual(self.run.pb_total_deductions, 1000.0)

    def test_gross_skips_the_parts_that_are_inside_the_roll_up(self):
        slip = self._slip_with({'NET': 8500.0})
        self._line(slip, 'GROSSAGG', 'GROSS', 9500.0)
        self._line(slip, 'ACTUBASIC', 'BASIC', 9000.0, detail=True)
        self._line(slip, 'ALWONE', 'ALW', 500.0, detail=True)
        self.assertEqual(self.run.pb_total_gross, 9500.0)

    def test_an_employer_roll_up_containing_net_pay_is_not_a_deduction(self):
        """`TOTACOSTTOER = NETPAY + employer contributions` is a total the
        employer carries. Counting it as a deduction charges the employee for
        their own pay a second time."""
        slip = self._slip_with({'NET': 8500.0})
        self._line(slip, 'DEDAGG', 'DED', 1000.0)
        self._line(slip, 'ERCOST', 'COMP', 10075.0, detail=True)
        self.assertEqual(self.run.pb_total_deductions, 1000.0)

    def test_an_employer_contribution_nobody_folded_still_counts(self):
        """The reference tenant's whole deductions KPI is COMP lines, so the
        bucket stays in the sum; it is the DETAIL flag that removes the
        double-counted roll-ups, never the bucket."""
        slip = self._slip_with({'NET': 8500.0})
        self._line(slip, 'ERSI', 'COMP', 1575.0)
        self.assertEqual(self.run.pb_total_deductions, 1575.0)

    def test_a_run_nobody_classified_reads_exactly_as_before(self):
        self._slip_with({'NET': 8500.0, 'GROSS': 9500.0, 'DED': 1000.0})
        self.assertEqual(self.run.pb_total_gross, 9500.0)
        self.assertEqual(self.run.pb_total_deductions, 1000.0)
        self.assertEqual(self.run.pb_total_net, 8500.0)
        self.assertEqual(self.run.pb_total_gross - self.run.pb_total_deductions,
                         self.run.pb_total_net)

    def test_moving_a_line_to_another_category_moves_the_band(self):
        """The sums are grouped BY category, so re-categorising a line changes
        every figure in the band while the amounts stay untouched."""
        slip = self._slip_with({'NET': 8500.0})
        line = self._line(slip, 'MYSTERY', 'OTH', 1000.0)
        self.assertEqual(self.run.pb_total_deductions, 0.0)
        line.category_id = self._cat('DED').id
        self.assertEqual(self.run.pb_total_deductions, 1000.0)
