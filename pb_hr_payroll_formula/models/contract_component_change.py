# -*- coding: utf-8 -*-

from odoo import fields, models


class HrContractAdvantageChange(models.Model):
    _name = 'hr.contract.advantage.change'
    _description = 'Contract Component Change'
    _order = 'effective_date desc, id desc'

    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='contract_id.employee_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='contract_id.company_id',
        store=True,
        readonly=True,
    )
    advantage_template_id = fields.Many2one(
        'hr.contract.advantage.template',
        string='Advantage Template',
        required=True,
    )
    advantage_template_code = fields.Char(
        string='Code',
        related='advantage_template_id.code',
        store=True,
        readonly=True,
    )
    old_amount = fields.Float(string='Old Amount')
    new_amount = fields.Float(string='New Amount')
    effective_date = fields.Date(string='Effective Date', required=True)
    change_source = fields.Selection([
        ('import', 'Import'),
        ('import_default', 'Import Default'),
        ('manual', 'Manual'),
    ], string='Source', default='import', required=True)
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Import Batch',
        readonly=True,
    )
    changed_by = fields.Many2one(
        'res.users',
        string='Changed By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    changed_at = fields.Datetime(
        string='Changed At',
        default=fields.Datetime.now,
        readonly=True,
    )
    notes = fields.Text(string='Notes')
