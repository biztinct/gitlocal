# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipConfig(models.Model):
    _name = 'hr.payslip.config'
    _description = 'Payslip Configuration'
    _order = 'identifier'

    identifier = fields.Char(
        string='Identifier',
        required=True,
        help="Short identifier used to group components in payslip and reporting."
    )
    label = fields.Char(
        string='Label',
        help="Display label for the identifier (optional)."
    )

    _sql_constraints = [
        ('identifier_uniq', 'unique(identifier)', 'Identifier must be unique.'),
    ]
