# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrPayrollRetroAdjustment(models.Model):
    _name = 'hr.payroll.retro.adjustment'
    _description = 'Payroll Retro Adjustment'
    _order = 'period_from desc, employee_id'

    @api.depends('employee_id', 'component_id', 'period_from')
    def _compute_display_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'Retro adjustment'
            comp = rec.component_id.name or rec.component_code or ''
            period = rec.period_from.strftime('%b %Y') if rec.period_from else ''
            label = emp
            if comp:
                label += ' — ' + comp
            if period:
                label += ' · retro ' + period
            rec.display_name = label

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        ondelete='restrict',
    )
    applied_in_batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Applied In Batch',
        ondelete='cascade',
    )
    applied_in_payslip_id = fields.Many2one(
        'hr.payslip',
        string='Applied In Payslip',
        ondelete='set null',
    )
    original_payslip_id = fields.Many2one(
        'hr.payslip',
        string='Original Payslip',
        ondelete='set null',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        ondelete='set null',
    )
    component_id = fields.Many2one(
        'hr.formula.rule',
        string='Component',
        required=True,
        ondelete='restrict',
    )
    component_code = fields.Char(
        string='Component Code',
        related='component_id.code',
        store=True,
        readonly=True,
    )
    advantage_change_id = fields.Many2one(
        'hr.contract.advantage.change',
        string='Change Reference',
        ondelete='set null',
    )
    change_effective_date = fields.Date(string='Change Effective Date')
    period_from = fields.Date(string='Period Start', required=True)
    period_to = fields.Date(string='Period End', required=True)
    old_amount = fields.Float(string='Old Amount')
    new_amount = fields.Float(string='New Amount')
    delta_amount = fields.Float(string='Retro Delta')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='posted', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )

    # Odoo 19: legacy _sql_constraints is silently IGNORED (model_classes.py
    # logs "no longer supported") — constraints must be models.Constraint
    # class attributes or they never reach the database (ledger C9).
    _retro_unique_period = models.Constraint(
        'unique(applied_in_batch_id, employee_id, component_id, original_payslip_id, advantage_change_id)',
        'A retro adjustment already exists for this batch and period.')
