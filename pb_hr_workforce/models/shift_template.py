# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ShiftTemplate(models.Model):
    _name = 'hr.shift.template'
    _description = 'Shift Template'
    _order = 'sequence, name'

    name = fields.Char(string='Shift Name', required=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Color Index', default=0)
    active = fields.Boolean(default=True)

    # Timing
    start_hour = fields.Float(string='Start Time', required=True,
                              help='Shift start time (24h format, e.g. 8.0 = 08:00)')
    end_hour = fields.Float(string='End Time', required=True,
                            help='Shift end time (24h format, e.g. 17.0 = 17:00)')
    break_duration = fields.Float(string='Break Duration (hrs)', default=1.0)
    duration = fields.Float(string='Work Duration (hrs)', compute='_compute_duration', store=True)

    # Classification
    shift_type = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('night', 'Night'),
        ('split', 'Split Shift'),
        ('flexible', 'Flexible'),
    ], string='Shift Type', required=True, default='morning')

    is_overnight = fields.Boolean(string='Overnight Shift',
                                  help='Check if shift crosses midnight')

    # Linked Work Schedule
    resource_calendar_id = fields.Many2one('resource.calendar',
                                           string='Work Schedule',
                                           help='Link to resource calendar for this shift pattern')

    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Shift code must be unique per company!'),
    ]

    @api.depends('start_hour', 'end_hour', 'break_duration', 'is_overnight')
    def _compute_duration(self):
        for rec in self:
            if rec.is_overnight:
                raw = (24.0 - rec.start_hour) + rec.end_hour
            else:
                raw = rec.end_hour - rec.start_hour
            rec.duration = max(0, raw - rec.break_duration)

    @api.constrains('start_hour', 'end_hour')
    def _check_hours(self):
        for rec in self:
            if rec.start_hour < 0 or rec.start_hour >= 24:
                raise ValidationError(_('Start time must be between 0:00 and 23:59'))
            if rec.end_hour < 0 or rec.end_hour >= 24:
                raise ValidationError(_('End time must be between 0:00 and 23:59'))
            if not rec.is_overnight and rec.end_hour <= rec.start_hour:
                raise ValidationError(
                    _('End time must be after start time (or mark as overnight shift)'))

    def name_get(self):
        return [(r.id, f'[{r.code}] {r.name}') for r in self]
