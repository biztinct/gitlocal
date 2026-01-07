# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    report_visible = fields.Boolean(
        string='Report Visible',
        default=False,
        help="True if this component should appear in reporting outputs."
    )
    component_type = fields.Char(
        string='Component Type',
        help="Component type from formula configuration (e.g., Deductions, Allowances)."
    )

