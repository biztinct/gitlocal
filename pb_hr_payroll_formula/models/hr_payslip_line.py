# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipLine(models.Model):
    _inherit = ['hr.payslip.line']

    report_visible = fields.Boolean(
        string='Report Visible',
        default=False,
        help="True if this component should appear in reporting outputs."
    )
    component_type = fields.Char(
        string='Component Type',
        help="Component type from formula configuration (e.g., Deductions, Allowances)."
    )
    # NETROLE — copied from the component at line creation, exactly like the two
    # fields above, so a payslip stays a record of what the scheme said at the
    # time and a later re-classification cannot rewrite history.
    #
    # A pay run's KPI band must count each dong once. `SI-HI-IU Total 10.5%` is
    # subtracted from net pay and so is `Total Deduction` — but only because the
    # second contains the first, and summing both reported ABM's June
    # deductions as ₫5,058,029,390 against ₫1.9bn of gross. A detail line still
    # shows on the payslip; it is the TOTALS that skip it.
    component_detail = fields.Boolean(
        string='Counted in a Total',
        help="This amount is already included in another line's total, so pay "
             "run figures count the total instead of this line."
    )

    # VALUEKIND P4 — the sibling `component_detail` has needed since the day it
    # was added: WHAT the line is, not merely whether it is folded into a total.
    #
    # Reports used to classify a line through
    # `hr_salary_rule_category.category_type`, a field nobody maintains because
    # nobody SEES it — on ABM the category named "Net" carries the type
    # "allowance", as do "Gross" and "Deduction", so the Analytics Explorer
    # added every subtotal on top of the components it was a subtotal OF and
    # reported ~14bn against a true gross of 927m.
    #
    # The scheme already knows the answer and derives it from its own net-pay
    # formula (`hr.formula.rule.net_role`). Copied here at creation — like the
    # two fields above — so a payslip stays a record of what the scheme said at
    # the time, and so a report never has to join back to a live rule that may
    # since have been reclassified or deleted.
    pay_role = fields.Selection([
        ('earning', 'Adds to net pay'),
        ('deduction', 'Taken off net pay'),
        ('net', 'Net pay itself'),
        ('employer_cost', 'Employer cost'),
        ('info', 'Information only'),
        ('mixed', 'Both added and taken off'),
    ], string='Pay Role', index=True,
        help="What net pay does with this line. Worked out from the scheme's "
             "own formulas when the payslip was computed.")

