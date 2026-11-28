# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollCycleCarryover(models.Model):
    _name = 'hr.payroll.cycle.carryover'
    _description = 'Payroll Cycle Carryover'
    _order = 'date_from desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade'
    )
    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        ondelete='restrict'
    )
    source_component_id = fields.Many2one(
        'hr.formula.rule',
        string='Source Component',
        required=True,
        domain="[('config_id', '=', formula_config_id)]",
        ondelete='restrict'
    )
    amount = fields.Monetary(
        string='Amount',
        required=True
    )
    currency_id = fields.Many2one(
        related='formula_config_id.currency_id',
        store=True
    )
    company_id = fields.Many2one(
        related='formula_config_id.company_id',
        store=True
    )
    date_from = fields.Date(
        string='Date From',
        required=True
    )
    date_to = fields.Date(
        string='Date To',
        required=True
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Payslip Run',
        ondelete='set null'
    )
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Import Batch',
        ondelete='set null'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='State', default='draft', required=True)
    active = fields.Boolean(default=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("Date From must be earlier than Date To."))
