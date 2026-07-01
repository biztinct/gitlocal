# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrPayrollProrationLine(models.Model):
    _name = 'hr.payroll.proration.line'
    _description = 'Payroll Proration Line'
    _order = 'date_from desc, employee_id'

    @api.depends('employee_id', 'component_id', 'date_from')
    def _compute_display_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'Proration'
            comp = rec.component_id.name or rec.component_code or ''
            period = rec.date_from.strftime('%b %Y') if rec.date_from else ''
            label = emp
            if comp:
                label += ' — ' + comp
            if period:
                label += ' · prorated ' + period
            rec.display_name = label

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        ondelete='cascade',
    )
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Import Batch',
        required=True,
        ondelete='cascade',
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
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
    )
    date_from = fields.Date(
        string='Period Start',
        required=True,
    )
    date_to = fields.Date(
        string='Period End',
        required=True,
    )
    proration_basis = fields.Selection([
        ('calendar', 'Calendar Days'),
        ('workdays', 'Work Days'),
    ], string='Proration Basis', required=True, default='calendar')
    period_days = fields.Float(string='Period Days')
    old_days = fields.Float(string='Old Days')
    new_days = fields.Float(string='New Days')
    old_amount = fields.Float(string='Old Amount')
    new_amount = fields.Float(string='New Amount')
    prorated_amount = fields.Float(string='Prorated Amount')
    segment_summary = fields.Text(string='Segment Summary')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='posted', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            'proration_unique_batch',
            'unique(import_batch_id, employee_id, component_id, effective_date)',
            'A proration line already exists for this batch, employee, component and date.'
        ),
    ]
