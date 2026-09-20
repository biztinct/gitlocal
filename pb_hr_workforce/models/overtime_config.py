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

    # ── Day applicability ──
    apply_monday = fields.Boolean(string='Mon', default=False,
                                   help='This rule applies on Mondays')
    apply_tuesday = fields.Boolean(string='Tue', default=False)
    apply_wednesday = fields.Boolean(string='Wed', default=False)
    apply_thursday = fields.Boolean(string='Thu', default=False)
    apply_friday = fields.Boolean(string='Fri', default=False)
    apply_saturday = fields.Boolean(string='Sat', default=False)
    apply_sunday = fields.Boolean(string='Sun', default=False)

    applicable_days_display = fields.Char(
        string='Applicable Days',
        compute='_compute_applicable_days_display',
        help='Which days of the week this rule applies to')

    # ── Time boundaries ──
    time_from = fields.Float(string='Applies From',
                              help='24h format. E.g. 22.0 = 10:00 PM')
    time_to = fields.Float(string='Applies To',
                            help='24h format. E.g. 6.0 = 6:00 AM')
    time_display = fields.Char(
        string='Time Window',
        compute='_compute_time_display')

    # ── Threshold ──
    threshold_hours = fields.Float(
        string='Overtime After (hrs)',
        default=8.0,
        help='Hours worked per day after which overtime begins. '
             'E.g. 8 = OT starts after 8 hours of regular work.')

    note = fields.Html(string='Description')
    color = fields.Integer(string='Color', default=0)

    @api.depends('rate_multiplier')
    def _compute_rate_display(self):
        for rec in self:
            pct = int(rec.rate_multiplier * 100)
            rec.rate_display = f'{pct}%'

    @api.depends('apply_monday', 'apply_tuesday', 'apply_wednesday',
                 'apply_thursday', 'apply_friday', 'apply_saturday', 'apply_sunday')
    def _compute_applicable_days_display(self):
        day_map = [
            ('apply_monday', 'Mon'), ('apply_tuesday', 'Tue'),
            ('apply_wednesday', 'Wed'), ('apply_thursday', 'Thu'),
            ('apply_friday', 'Fri'), ('apply_saturday', 'Sat'),
            ('apply_sunday', 'Sun'),
        ]
        for rec in self:
            days = [label for field, label in day_map if getattr(rec, field)]
            if len(days) == 7:
                rec.applicable_days_display = 'Every day'
            elif len(days) == 5 and not rec.apply_saturday and not rec.apply_sunday:
                rec.applicable_days_display = 'Weekdays (Mon–Fri)'
            elif len(days) == 2 and rec.apply_saturday and rec.apply_sunday:
                rec.applicable_days_display = 'Weekends (Sat–Sun)'
            elif days:
                rec.applicable_days_display = ', '.join(days)
            else:
                rec.applicable_days_display = 'Auto (based on type)'

    @api.depends('time_from', 'time_to')
    def _compute_time_display(self):
        for rec in self:
            if rec.time_from or rec.time_to:
                def fmt(h):
                    hours = int(h)
                    mins = int((h - hours) * 60)
                    ampm = 'AM' if hours < 12 else 'PM'
                    h12 = hours if hours <= 12 else hours - 12
                    if h12 == 0:
                        h12 = 12
                    return f'{h12}:{mins:02d} {ampm}'
                rec.time_display = f'{fmt(rec.time_from)} → {fmt(rec.time_to)}'
            else:
                rec.time_display = 'All hours'

    @api.onchange('overtime_type')
    def _onchange_overtime_type(self):
        """Auto-set day applicability based on overtime type."""
        if self.overtime_type == 'weekday':
            self.apply_monday = self.apply_tuesday = self.apply_wednesday = True
            self.apply_thursday = self.apply_friday = True
            self.apply_saturday = self.apply_sunday = False
            self.threshold_hours = 8.0
        elif self.overtime_type == 'weekend':
            self.apply_monday = self.apply_tuesday = self.apply_wednesday = False
            self.apply_thursday = self.apply_friday = False
            self.apply_saturday = self.apply_sunday = True
            self.threshold_hours = 0.0
        elif self.overtime_type == 'holiday':
            # Holiday OT applies on any day that is a public holiday
            self.apply_monday = self.apply_tuesday = self.apply_wednesday = True
            self.apply_thursday = self.apply_friday = True
            self.apply_saturday = self.apply_sunday = True
            self.threshold_hours = 0.0
        elif self.overtime_type == 'night':
            self.apply_monday = self.apply_tuesday = self.apply_wednesday = True
            self.apply_thursday = self.apply_friday = True
            self.apply_saturday = self.apply_sunday = True
            self.time_from = 22.0
            self.time_to = 6.0
            self.threshold_hours = 0.0

    @api.constrains('rate_multiplier')
    def _check_rate(self):
        for rec in self:
            if rec.rate_multiplier < 1.0:
                raise ValidationError(
                    _('Rate multiplier must be at least 1.0 (100%)'))

    def name_get(self):
        return [(r.id, f'{r.name} ({r.rate_display})') for r in self]
