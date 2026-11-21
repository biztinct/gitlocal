# -*- coding: utf-8 -*-
"""The conversations a journey schedules — and the red flag one can raise.

The 30/60/90 is not paperwork. `red_flag` is the whole point of this model: it
is how a quiet new joiner becomes visible to HR in week three instead of in the
resignation email in month four.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

CHECKIN_KINDS = [
    ('d30', '30-day'),
    ('d60', '60-day'),
    ('d90', '90-day'),
    ('hrbp', 'HRBP catch-up'),
    ('buddy', 'Buddy connect'),
    ('probation', 'Probation 1:1'),
    ('pip', 'PIP check-in'),
    ('other', 'Other'),
]

CHECKIN_KIND_LABEL = dict(CHECKIN_KINDS)


class PbEmployeeCheckin(models.Model):
    _name = 'pb.employee.checkin'
    _description = 'Employee Check-in'
    _order = 'scheduled_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Check-in')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    case_id = fields.Many2one(
        'pb.journey.case', string='Journey', index=True, ondelete='set null')
    kind = fields.Selection(
        CHECKIN_KINDS, string='Kind', required=True, default='d30')
    owner_user_id = fields.Many2one(
        'res.users', string='Run by', index=True,
        default=lambda self: self.env.user)
    scheduled_date = fields.Date(string='Planned for', index=True,
                                 default=fields.Date.context_today)
    state = fields.Selection(
        [('scheduled', 'Planned'), ('done', 'Done'), ('missed', 'Missed'),
         ('cancelled', 'Cancelled')],
        string='Status', default='scheduled', required=True, index=True)
    notes = fields.Text(string='What was said')
    red_flag = fields.Boolean(
        string='Needs attention',
        help='Tick this when something came up that HR should look at.')
    red_flag_note = fields.Char(string='What needs attention')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('employee_id', 'kind')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (
                rec.employee_id.name or _('Employee'),
                CHECKIN_KIND_LABEL.get(rec.kind, rec.kind or ''))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Check-in')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.company_id:
            self.company_id = self.employee_id.company_id

    def action_done(self, notes=None, red_flag=None, red_flag_note=None):
        for rec in self:
            vals = {'state': 'done'}
            if notes is not None:
                vals['notes'] = notes
            if red_flag is not None:
                vals['red_flag'] = bool(red_flag)
            if red_flag_note is not None:
                vals['red_flag_note'] = red_flag_note
            rec.write(vals)
            if rec.case_id:
                rec.case_id.message_post(body=_(
                    "Check-in done: %(what)s%(flag)s.",
                    what=CHECKIN_KIND_LABEL.get(rec.kind, rec.kind or ''),
                    flag=_(' — flagged for attention') if rec.red_flag else ''))
        return True

    def action_missed(self):
        self.write({'state': 'missed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True
