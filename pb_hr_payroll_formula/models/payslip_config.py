# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipConfig(models.Model):
    _name = 'hr.payslip.config'
    _description = 'Payslip Configuration'
    _order = 'sequence, identifier'
    _rec_name = 'identifier'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Order used to display sections in the payslip."
    )
    salary_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        ondelete='cascade',
        help="Salary structure that this payslip identifier set applies to."
    )
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
        ('identifier_config_uniq',
         'unique(identifier, salary_structure_id)',
         'Identifier must be unique per salary structure.'),
    ]
