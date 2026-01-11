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
            " ('store', '=', True),"
            " ('readonly', '=', False),"
            " ('ttype', 'not in', ('one2many', 'many2many'))]"
        )
    )
    salary_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        required=True
    )
    component_id = fields.Many2one(
        'hr.formula.rule',
        string='Component',
        domain="[('config_id', '=', salary_structure_id)]"
    )
