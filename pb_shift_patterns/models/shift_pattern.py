# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Rotating shift patterns (WDGAP S5-C).

THE SHAPE
---------
A pattern is a CYCLE of `cycle_days` days (7 = one week, 14 = two weeks,
8 = "4 on, 4 off" ...) whose day 1 is `start_date`. Each day of the cycle has
at most one SLOT: a shift template, or nothing (= off).

Teams carry the rotation. Team A starts the cycle on `start_date`; Team B
starts it `offset_days` later, and so on. On a calendar day `d` a member of a
team works the slot of cycle day

    ((d - start_date).days - team.offset_days) % cycle_days

so two teams on a two-week day/night cycle with offsets 0 and 7 are always on
opposite halves, and four teams on a 28-day cycle with offsets 0/7/14/21 cover
the four weeks between them. Python's `%` is never negative, so days before
`start_date` (or before a team's own start) still land on the right slot.

Members are people in a team, optionally from / to a date (somebody moving
from Team A to Team B on 1 March is two member rows that do not overlap).

Nothing here makes a shift. `pb.shift.pattern.engine` does, and only when a
manager presses "Make drafts".

RIGHTS
------
Attendance officers READ patterns (the lens is theirs, like the Schedule);
attendance managers create, change and make drafts — the same people who may
create `hr.shift.planning` rows at all (pb_hr_workforce ACL: officers read
shifts only). Global company rules on every model.
"""

from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

MAX_CYCLE_DAYS = 56          # eight weeks — longer rotations are rare and
                             # unreadable as a grid
MAX_TEAMS = 8
TEAM_LETTERS = 'ABCDEFGH'


class ShiftPattern(models.Model):
    _name = 'pb.shift.pattern'
    _description = 'Rotating shift pattern'
    _order = 'name, id'

    name = fields.Char(string='Pattern name', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    department_id = fields.Many2one(
        'hr.department', string='Department',
        help='Where the pattern is used. People from other departments can '
             'still be added.')
    start_date = fields.Date(
        string='Day 1 of the cycle', required=True,
        default=lambda self: self._default_start(),
        help='The first day of the cycle for Team A. Other teams start a '
             'number of days later.')
    cycle_days = fields.Integer(
        string='Repeats every (days)', required=True, default=14)
    work_on_holidays = fields.Boolean(
        string='Work on public holidays', default=False,
        help='Off: no shift is made on a public holiday and the day is listed '
             'in the report. On: holidays are worked like any other day.')
    note = fields.Text(string='Notes')

    slot_ids = fields.One2many('pb.shift.pattern.slot', 'pattern_id',
                               string='Days of the cycle')
    team_ids = fields.One2many('pb.shift.pattern.team', 'pattern_id',
                               string='Teams')
    member_ids = fields.One2many('pb.shift.pattern.member', 'pattern_id',
                                 string='People')
    shift_ids = fields.One2many('hr.shift.planning', 'pb_pattern_id',
                                string='Shifts made from this pattern')

    last_made_on = fields.Datetime(string='Drafts last made on', readonly=True,
                                   copy=False)
    last_made_by = fields.Many2one('res.users', string='Drafts last made by',
                                   readonly=True, copy=False)
    last_made_to = fields.Date(string='Drafts made up to', readonly=True,
                               copy=False)

    member_count = fields.Integer(compute='_compute_counts', string='Number of people')
    team_count = fields.Integer(compute='_compute_counts', string='Number of teams')

    _cycle_bounds = models.Constraint(
        'CHECK (cycle_days >= 1 AND cycle_days <= 56)',
        'A pattern repeats every 1 to 56 days.')

    @api.model
    def _default_start(self):
        today = fields.Date.context_today(self)
        return today - timedelta(days=today.weekday())

    @api.depends('member_ids', 'team_ids')
    def _compute_counts(self):
        for rec in self:
            rec.member_count = len(rec.member_ids.mapped('employee_id'))
            rec.team_count = len(rec.team_ids)

    # ------------------------------------------------------------ the cycle
    def _pb_slot_map(self):
        """{cycle day index: hr.shift.template} — off days are absent."""
        self.ensure_one()
        return {s.day_index: s.template_id for s in self.slot_ids
                if s.template_id and 0 <= s.day_index < self.cycle_days}

    def _pb_cycle_index(self, day, offset_days=0):
        """The cycle day (0-based) a team with this offset works on `day`."""
        self.ensure_one()
        length = max(1, self.cycle_days or 1)
        return ((day - self.start_date).days - (offset_days or 0)) % length

    @api.constrains('cycle_days', 'slot_ids', 'team_ids')
    def _check_cycle(self):
        for rec in self:
            if not 1 <= (rec.cycle_days or 0) <= MAX_CYCLE_DAYS:
                raise ValidationError(_("A pattern repeats every 1 to %s days.",
                                        MAX_CYCLE_DAYS))
            if len(rec.team_ids) > MAX_TEAMS:
                raise ValidationError(_("A pattern has at most %s teams.",
                                        MAX_TEAMS))
            for slot in rec.slot_ids:
                if not 0 <= slot.day_index < rec.cycle_days:
                    raise ValidationError(_(
                        "Day %(day)s is outside a %(n)s-day cycle.",
                        day=slot.day_index + 1, n=rec.cycle_days))
            for team in rec.team_ids:
                if not 0 <= (team.offset_days or 0) < rec.cycle_days:
                    raise ValidationError(_(
                        "%(team)s must start 0 to %(n)s days after Team A.",
                        team=team.name, n=rec.cycle_days - 1))


class ShiftPatternSlot(models.Model):
    _name = 'pb.shift.pattern.slot'
    _description = 'Day of a shift pattern cycle'
    _order = 'pattern_id, day_index'

    pattern_id = fields.Many2one('pb.shift.pattern', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='pattern_id.company_id', store=True,
                                 index=True)
    day_index = fields.Integer(string='Day of the cycle', required=True,
                               help='0 is day 1 of the cycle.')
    template_id = fields.Many2one('hr.shift.template', string='Shift',
                                  ondelete='restrict',
                                  help='Empty means the day is off.')

    _day_uniq = models.Constraint(
        'UNIQUE (pattern_id, day_index)',
        'Each day of the cycle has one shift at most.')


class ShiftPatternTeam(models.Model):
    _name = 'pb.shift.pattern.team'
    _description = 'Team of a shift pattern'
    _order = 'pattern_id, sequence, id'

    pattern_id = fields.Many2one('pb.shift.pattern', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='pattern_id.company_id', store=True,
                                 index=True)
    name = fields.Char(string='Team', required=True)
    sequence = fields.Integer(default=10)
    offset_days = fields.Integer(
        string='Starts this many days after Team A', default=0)
    member_ids = fields.One2many('pb.shift.pattern.member', 'team_id',
                                 string='People')


class ShiftPatternMember(models.Model):
    _name = 'pb.shift.pattern.member'
    _description = 'Person on a shift pattern'
    _order = 'pattern_id, team_id, id'

    pattern_id = fields.Many2one('pb.shift.pattern', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='pattern_id.company_id', store=True,
                                 index=True)
    team_id = fields.Many2one('pb.shift.pattern.team', string='Team',
                              required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Person', required=True,
                                  ondelete='cascade', index=True)
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='Until')

    @api.constrains('team_id', 'pattern_id', 'date_from', 'date_to',
                    'employee_id')
    def _check_member(self):
        for rec in self:
            if rec.team_id.pattern_id != rec.pattern_id:
                raise ValidationError(_("A person's team must belong to the "
                                        "same pattern."))
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_(
                    "%s: the end date is before the start date.",
                    rec.employee_id.name))
            others = rec.pattern_id.member_ids.filtered(
                lambda m: m.id != rec.id and m.employee_id == rec.employee_id)
            for other in others:
                if _ranges_overlap(rec.date_from, rec.date_to,
                                   other.date_from, other.date_to):
                    raise ValidationError(_(
                        "%s is in this pattern twice for the same days. Give "
                        "each team row its own dates.", rec.employee_id.name))

    def _pb_covers(self, day):
        self.ensure_one()
        return ((not self.date_from or self.date_from <= day)
                and (not self.date_to or day <= self.date_to))


_LOW = date(1900, 1, 1)
_HIGH = date(9999, 12, 31)


def _ranges_overlap(a_from, a_to, b_from, b_to):
    """Open-ended date ranges (False = no limit) overlap?"""
    return (a_from or _LOW) <= (b_to or _HIGH) and (b_from or _LOW) <= (a_to or _HIGH)
