# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipLineAnalytics(models.Model):
    """Extend hr.payslip.line with fields for pivot analytics"""
    _inherit = ['hr.payslip.line']

    # Related field for direct pivot access to category type
    category_type = fields.Selection(
        related='category_id.category_type',
        string='Category Type',
        store=True,  # Store for pivot performance and searchability
        readonly=True
    )

    # Related field for formula config (for filtering in pivot)
    formula_config_id = fields.Many2one(
        related='slip_id.formula_config_id',
        string='Formula Config',
        store=True,
        readonly=True
    )

    # Related field for department (via employee on payslip)
    department_id = fields.Many2one(
        related='slip_id.employee_id.department_id',
        string='Department',
        store=True,  # Store for pivot grouping
        readonly=True
    )
