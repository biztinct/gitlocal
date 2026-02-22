# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class OvertimeConfig(models.Model):
    _name = 'hr.overtime.config'
    _description = 'Overtime Rate Configuration'
    _order = 'country_id, sequence'

    name = fields.Char(string='Rule Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    country_id = fields.Many2one('res.country', string='Country',
                                  help='Leave blank for global rules')
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)

    overtime_type = fields.Selection([
        ('weekday', 'Weekday Overtime'),
        ('weekend', 'Weekend Overtime'),
        ('holiday', 'Public Holiday Overtime'),
        ('night', 'Night Shift Premium'),
        ('extended', 'Extended Overtime (>8hrs OT)'),
    ], string='Overtime Type', required=True)

    rate_multiplier = fields.Float(string='Rate Multiplier', required=True, default=1.5,
                                    help='Multiplier applied to base hourly rate. E.g. 1.5 = 150%')
    rate_display = fields.Char(string='Rate Display',
                                compute='_compute_rate_display')

    max_hours_per_day = fields.Float(string='Max OT Hours/Day', default=4.0,
                                      help='Maximum overtime hours allowed per day')
    max_hours_per_month = fields.Float(string='Max OT Hours/Month', default=40.0,
                                        help='Maximum overtime hours allowed per month')
    requires_approval = fields.Boolean(string='Requires Approval', default=True)

    # Time boundaries (for night shift)
    time_from = fields.Float(string='Applies From (hour)',
                              help='24h format. E.g. 22.0 = 10:00 PM')
    time_to = fields.Float(string='Applies To (hour)',
                            help='24h format. E.g. 6.0 = 6:00 AM')

    note = fields.Html(string='Description')
    color = fields.Integer(string='Color', default=0)

    @api.depends('rate_multiplier')
    def _compute_rate_display(self):
        for rec in self:
            pct = int(rec.rate_multiplier * 100)
            rec.rate_display = f'{pct}%'

    @api.constrains('rate_multiplier')
    def _check_rate(self):
        for rec in self:
            if rec.rate_multiplier < 1.0:
                raise ValidationError(
                    _('Rate multiplier must be at least 1.0 (100%)'))

    def name_get(self):
        return [(r.id, f'{r.name} ({r.rate_display})') for r in self]
