# -*- coding: utf-8 -*-
"""What a kind of leave knows about how it is earned (WDGAP S5-A).

EVERY FIELD HAS A DEFAULT AND NONE IS REQUIRED. Another builder (S5-B) creates
a "Time off in lieu" kind with plain core and pb_timeoff fields and knows
nothing about these; older kinds were made before they existed. A kind that
was never touched on the Kinds of leave screen therefore reads
``pb_ls_earning = 'none'`` — "given by HR", exactly today's behaviour — and the
earning job never looks at it.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

EARNING = [
    ('none', 'Given by HR'),
    ('yearly', 'All at once each year'),
    ('monthly', 'A share each month'),
]


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    pb_ls_earning = fields.Selection(
        EARNING, string='How it is earned', default='none',
        help='Given by HR: nothing is added automatically (as before). All at '
             'once each year: the year\'s days are added when the year starts '
             '(or when the person becomes entitled). A share each month: '
             'one twelfth of the year\'s days is added after each month worked.')
    pb_ls_days_per_year = fields.Float(
        string='Days a year', default=0.0, digits=(6, 2))
    pb_ls_waiting_months = fields.Integer(
        string='Starts after this many months of service', default=0)
    pb_ls_max_balance = fields.Float(
        string='Most days a person can hold', default=0.0, digits=(6, 2),
        help='Zero means no limit. Once somebody holds this many days, '
             'nothing more is added until they take some.')
    pb_ls_take_ahead = fields.Boolean(
        string='People can take days before they are earned', default=False,
        help='Off: people can take only what they have earned so far. On: the '
             'whole year\'s days can be taken from the start of the year; if '
             'somebody leaves early they may owe the days they took ahead.')
    pb_ls_expire_months = fields.Integer(
        string='Days run out this many months after the year ends', default=0,
        help='Zero means the days do not run out.')
    pb_ls_earn_from = fields.Date(
        string='Build-up starts from',
        help='The first month the days build up. Months before it are never '
             'added, so days HR already gave by hand are not given twice.')
    pb_ls_step_ids = fields.One2many(
        'pb.leave.service.step', 'leave_type_id', string='Extra days for long service')
    pb_ls_hr_only = fields.Boolean(
        string='Only HR can enter this', default=False,
        help='Employees do not see this kind on their own leave page; HR '
             'enters it for them.')
    pb_ls_starter_key = fields.Char(
        string='Ready-made kind', copy=False, index=True, readonly=True,
        help='Which ready-made kind this was made from (for example VN.annual). '
             'Applying the same country again never makes it twice.')
    pb_ls_starter_version = fields.Char(string='Ready-made version', copy=False, readonly=True)
    pb_ls_review = fields.Boolean(
        string='Waiting for review', default=False, copy=False,
        help='Made from a ready-made kind and not yet reviewed and switched on.')
    pb_ls_sources = fields.Json(
        string='Where the figures come from', copy=False, readonly=True)

    @api.constrains('pb_ls_days_per_year', 'pb_ls_waiting_months', 'pb_ls_max_balance',
                    'pb_ls_expire_months')
    def _check_pb_ls_numbers(self):
        for kind in self:
            if kind.pb_ls_days_per_year < 0 or kind.pb_ls_days_per_year > 366:
                raise ValidationError(_('Days a year must be between 0 and 366.'))
            if kind.pb_ls_waiting_months < 0 or kind.pb_ls_waiting_months > 120:
                raise ValidationError(_('The waiting period must be between 0 and 120 months.'))
            if kind.pb_ls_max_balance < 0:
                raise ValidationError(_('The most days a person can hold cannot be below zero.'))
            if kind.pb_ls_expire_months < 0 or kind.pb_ls_expire_months > 60:
                raise ValidationError(_('Days can run out between 0 and 60 months after the year ends.'))

    def _pb_ls_earns(self):
        """Is this kind looked after by the earning job? Hours kinds and kinds
        bound to a leave policy (Rize) never are: the policy posts its own
        yearly credit and the two would fight (FACTS finding 6)."""
        self.ensure_one()
        return bool(self.active and self.pb_ls_earning in ('yearly', 'monthly')
                    and self.requires_allocation and self.request_unit != 'hour'
                    and not self.pb_policy_category
                    and self.pb_ls_days_per_year > 0)

    def _pb_ls_step_extra(self, years):
        """Extra days a year for somebody with this many COMPLETED years of
        service: the highest step reached (steps are not added together)."""
        self.ensure_one()
        best = 0.0
        for step in self.pb_ls_step_ids:
            if years >= step.after_years:
                best = max(best, step.extra_days)
        return best


class PbLeaveServiceStep(models.Model):
    _name = 'pb.leave.service.step'
    _description = 'Extra days of leave for long service'
    _order = 'after_years, id'

    leave_type_id = fields.Many2one('hr.leave.type', required=True, ondelete='cascade',
                                    index=True)
    after_years = fields.Integer(string='After this many years', required=True, default=1)
    extra_days = fields.Float(string='Extra days a year', required=True, default=1.0,
                              digits=(6, 2))

    @api.constrains('after_years', 'extra_days')
    def _check_step(self):
        for step in self:
            if step.after_years < 1 or step.after_years > 60:
                raise ValidationError(_('A service step starts after 1 to 60 years.'))
            if step.extra_days <= 0 or step.extra_days > 60:
                raise ValidationError(_('A service step adds between 0 and 60 days a year.'))


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    #: The leave year this allocation holds earned days for. Set only by the
    #: earning job; one allocation per person, kind and leave year.
    pb_ls_year = fields.Integer(string='Earned days for the year', readonly=True,
                                copy=False, index=True)

    _pb_ls_year_once = models.Constraint(
        'unique(employee_id, holiday_status_id, pb_ls_year)',
        'Earned days already have an allocation for this person, kind and year.')
