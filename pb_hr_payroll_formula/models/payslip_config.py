# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipConfig(models.Model):
    _name = 'hr.payslip.config'
    _description = 'Payslip Configuration'
    _order = 'identifier'
    _rec_name = 'identifier'

    identifier = fields.Char(
        string='Identifier',
        required=True,
        help="Short identifier used to group components in payslip and reporting."
    )
    label = fields.Char(
        string='Label',
        help="Display label for the identifier (optional)."
    )

    def name_get(self):
        result = []
        for record in self:
            if record.label:
                name = "%s - %s" % (record.identifier, record.label)
            else:
                name = record.identifier
            result.append((record.id, name))
        return result

    _sql_constraints = [
        ('identifier_uniq', 'unique(identifier)', 'Identifier must be unique.'),
    ]
