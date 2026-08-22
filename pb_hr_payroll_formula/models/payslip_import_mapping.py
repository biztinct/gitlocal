# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipImportMapping(models.Model):
    _name = 'hr.payslip.import.mapping'
    _description = 'Payslip Import Mapping'
    _rec_name = 'target_field_id'
    _order = 'id desc'

    target_model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('model', 'in', ('hr.employee', 'hr.contract'))]"
    )
    target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        domain=(
            "[('model_id', '=', target_model_id),"
            " ('readonly', '=', False),"
            " ('ttype', 'not in', ('one2many', 'many2many'))]"
        )
    )
    salary_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        required=True,
        # Setup metadata, not payroll history: these go with the configuration
        # rather than blocking its removal (required + no ondelete would have
        # defaulted to RESTRICT and made a merely-configured config undeletable).
        ondelete='cascade',
    )
    component_id = fields.Many2one(
        'hr.formula.rule',
        string='Component',
        domain="[('config_id', '=', salary_structure_id)]"
    )
