# Part of Payobook. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShiftPlanning(models.Model):
    _name = 'hr.shift.planning'
    _description = 'Shift Planning'
    _order = 'date desc, start_datetime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                   required=True, tracking=True,
                                   index=True)
    department_id = fields.Many2one('hr.department', string='Department',
                                    related='employee_id.department_id',
                                    store=True, readonly=True)
    shift_template_id = fields.Many2one('hr.shift.template',
                                         string='Shift Template',
                                         required=True, tracking=True)
    date = fields.Date(string='Date', required=True, tracking=True, index=True)
    start_datetime = fields.Datetime(string='Start', required=True)
    end_datetime = fields.Datetime(string='End', required=True)

    # Actual attendance (linked)
    actual_check_in = fields.Datetime(string='Actual Check-In')
    actual_check_out = fields.Datetime(string='Actual Check-Out')
    actual_hours = fields.Float(string='Actual Hours',
                                compute='_compute_actual_hours', store=True)

    # Compliance
    planned_hours = fields.Float(string='Planned Hours',
                                  related='shift_template_id.duration',
                                  store=True)
    compliance_status = fields.Selection([
        ('pending', 'Pending'),
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('early_leave', 'Early Leave'),
        ('absent', 'Absent'),
        ('overtime', 'Overtime'),
    ], string='Status', compute='_compute_compliance_status', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True, index=True)

    color = fields.Integer(related='shift_template_id.color')
    note = fields.Text(string='Notes')
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)

    @api.depends('employee_id', 'date', 'shift_template_id')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or ''
            dt = rec.date.strftime('%d/%m') if rec.date else ''
            shift = rec.shift_template_id.code or ''
            rec.name = f'{emp} - {shift} - {dt}'

    @api.depends('actual_check_in', 'actual_check_out')
    def _compute_actual_hours(self):
        for rec in self:
            if rec.actual_check_in and rec.actual_check_out:
                delta = rec.actual_check_out - rec.actual_check_in
                rec.actual_hours = delta.total_seconds() / 3600.0
            else:
                rec.actual_hours = 0.0

    @api.depends('state', 'actual_check_in', 'actual_check_out',
                 'start_datetime', 'end_datetime', 'date')
    def _compute_compliance_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ('draft', 'cancelled'):
                rec.compliance_status = 'pending'
                continue
            if not rec.actual_check_in:
                if rec.end_datetime and now > rec.end_datetime:
                    rec.compliance_status = 'absent'
                else:
                    rec.compliance_status = 'pending'
                continue
            # Check late (15 min tolerance)
            tolerance = timedelta(minutes=15)
            if rec.actual_check_in > rec.start_datetime + tolerance:
                rec.compliance_status = 'late'
            elif rec.actual_check_out and rec.actual_check_out < rec.end_datetime - tolerance:
                rec.compliance_status = 'early_leave'
            elif rec.actual_hours and rec.planned_hours and rec.actual_hours > rec.planned_hours + 0.5:
                rec.compliance_status = 'overtime'
            else:
                rec.compliance_status = 'on_time'

    def action_publish(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'published'})

    def action_complete(self):
        self.filtered(lambda r: r.state == 'published').write({'state': 'completed'})

    def action_cancel(self):
        self.filtered(lambda r: r.state != 'completed').write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})
