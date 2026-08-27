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

