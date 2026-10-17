# -*- coding: utf-8 -*-
"""The two tables that make assignments by themselves.

`pb.training.rule`      the courses a NEW JOINER is put on, on their first day
`pb.training.schedule`  the courses EVERYBODY does again every so often

They are deliberately two tables and not one with a switch on it, because they
answer different questions and are filled in by different people at different
times. A day-one rule is a statement about the company's induction and is
written once; a compliance schedule is a statement about a certificate that
expires and has a date attached that moves every year.

BOTH SHIP EMPTY. A module that arrived with a fire-safety schedule pointed at
somebody else's course would email the whole company on its first night. So
there are no rows until a person makes one, the day-one handler is behind its
own switch as well, and a switch that is off SAYS so on the screen rather than
looking broken (R54).
"""

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .training_common import (
    ASSIGN_OPEN, SCHEDULE_AUDIENCES, counted,
)

_logger = logging.getLogger(__name__)


class PbTrainingRule(models.Model):
    """What a new joiner is put on, on their first day."""
    _name = 'pb.training.rule'
    _description = 'Day-one training rule'
    _order = 'sequence, id'

    name = fields.Char(
        string='What to call it', required=True,
        default=lambda self: _('Day-one courses'),
        help='A name a person would recognise on a list. "Induction", '
             '"Day one for field staff".')
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    channel_ids = fields.Many2many(
        'slide.channel', 'pb_training_rule_channel_rel', 'rule_id',
        'channel_id', string='Courses',
        help='Everybody this rule is about is put on every one of these on '
             'their first day.')
    due_days = fields.Integer(
        string='Days they get', default=14, required=True,
        help='Counted from their first day. Two weeks is the usual answer.')
    department_ids = fields.Many2many(
        'hr.department', 'pb_training_rule_dept_rel', 'rule_id', 'dept_id',
        string='Only these parts of the business',
        help='Leave empty and the rule is about everybody who joins.')
    job_ids = fields.Many2many(
        'hr.job', 'pb_training_rule_job_rel', 'rule_id', 'job_id',
        string='Only these jobs',
        help='Leave empty and the rule is about every job.')
    active = fields.Boolean(default=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Day-one courses')

    # ------------------------------------------------------------- matching
    @api.model
    def _for_employee(self, employee):
        """Every live rule that is about this person.

        Read as the system: the joining checklist runs as whoever ticked the
        step off, and that is usually somebody with no training permission at
        all.
        """
        if not employee:
            return self.browse()
        emp = employee.sudo()
        rules = self.sudo().search([
            ('active', '=', True),
            ('company_id', '=', (emp.company_id or self.env.company).id),
        ])
        return rules.filtered(lambda r: r._matches(emp))

    def _matches(self, emp):
        self.ensure_one()
        if self.department_ids and emp.department_id not in self.department_ids:
            return False
        if self.job_ids and emp.job_id not in self.job_ids:
            return False
        return bool(self.channel_ids)


class PbTrainingSchedule(models.Model):
    """A course everybody does again, every so often."""
    _name = 'pb.training.schedule'
    _description = 'Compliance training schedule'
    _order = 'next_run asc, id desc'

    name = fields.Char(string='What to call it', required=True,
                       help='"Fire safety, every year". The words the board '
                            'shows and the words the log uses.')
    channel_id = fields.Many2one('slide.channel', string='Course',
                                 required=True, index=True,
                                 ondelete='cascade')
    audience = fields.Selection(
        SCHEDULE_AUDIENCES, string='Who has to do it', required=True,
        default='company')
    department_id = fields.Many2one('hr.department',
                                    string='Which part of the business')
    job_id = fields.Many2one('hr.job', string='Which job')
    every_months = fields.Integer(
        string='How often, in months', default=12, required=True,
        help='Twelve is once a year. The next date moves on by this much '
             'every time the schedule runs.')
    due_days = fields.Integer(
        string='Days they get', default=30, required=True)
    next_run = fields.Date(
        string='Next time it runs', required=True, index=True,
        default=fields.Date.context_today,
        help='On this day the courses are assigned and this date moves on.')
    last_run = fields.Date(string='Last time it ran', readonly=True,
                           copy=False)
    last_count = fields.Integer(string='People it caught last time',
                                readonly=True, copy=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Schedule')

    @api.constrains('every_months', 'due_days')
    def _check_numbers(self):
        for rec in self:
            if rec.every_months < 1:
                raise ValidationError(_(
                    "A schedule has to come round at least once — set how "
                    "often to one month or more."))
            if rec.due_days < 1:
                raise ValidationError(_(
                    "Give people at least one day to do it."))

    # --------------------------------------------------------- the audience
    def _people(self):
        """Everybody this schedule is about, as employees.

        As the system and narrowly (R56), and never the whole employee record:
        the job only wants the id and the login.
        """
        self.ensure_one()
        Employee = self.env['hr.employee'].sudo()
        domain = [('active', '=', True)]
        if self.audience == 'everyone':
            pass
        elif self.audience == 'department' and self.department_id:
            domain += [('department_id', 'child_of', self.department_id.id)]
        elif self.audience == 'job' and self.job_id:
            domain += [('job_id', '=', self.job_id.id),
                       ('company_id', '=', self.company_id.id)]
        else:
            domain += [('company_id', '=', self.company_id.id)]
        return Employee.search(domain)

    def run_now(self):
        """Make this round's assignments. Once per person per ROUND.

        TWO SKIPS AND BOTH ARE NEEDED, and the second one was found live.

        The obvious test — "have they got an open assignment for this course"
        — is right for somebody who is still working through it and WRONG for
        somebody who had already finished the course before the schedule ever
        ran: their assignment is created `done` in the same breath (which is
        honest — they have done it), it is therefore not open, and the next
        run of the schedule assigns it to them again. On a nightly job that is
        one row per person per night, for ever, with a cheerful count in the
        log and nothing on any screen to say so.

        So the real question is the one the schedule is actually about: has
        THIS schedule already asked THIS person within the period it comes
        round in. A year-old row is outside the window and is reassigned,
        which is the whole point of a yearly course.
        """
        self.ensure_one()
        Assignment = self.env['pb.training.assignment'].sudo()
        today = fields.Date.today()
        due = today + relativedelta(days=max(self.due_days, 1))
        # The first day of the round that is running now.
        since = today - relativedelta(months=max(self.every_months, 1)) \
            + relativedelta(days=1)
        made = 0
        for emp in self._people():
            if not emp.user_id or not emp.user_id.partner_id:
                continue
            if Assignment.search_count([
                    ('channel_id', '=', self.channel_id.id),
                    ('employee_id', '=', emp.id),
                    ('state', 'in', ASSIGN_OPEN)]):
                continue
            if Assignment.search_count([
                    ('schedule_id', '=', self.id),
                    ('employee_id', '=', emp.id),
                    ('assigned_on', '>=', since)]):
                continue
            try:
                with self.env.cr.savepoint():
                    Assignment.create({
                        'channel_id': self.channel_id.id,
                        'employee_id': emp.id,
                        'reason': 'compliance',
                        'due_date': due,
                        'schedule_id': self.id,
                        'company_id': (emp.company_id
                                       or self.company_id).id,
                    })
                made += 1
            except Exception:           # noqa: BLE001 — one person, one grave
                _logger.warning('pb_training: schedule %s could not put %s on '
                                'course %s', self.id, emp.id,
                                self.channel_id.id, exc_info=True)
        # THE DATE ONLY MOVES WHEN THE ROUND WAS ACTUALLY DUE, and it lands on
        # the next date in the FUTURE. Rolling on every call meant pressing
        # "run it now" twice pushed a yearly course two years out — and a
        # schedule that had been missed for three years came back one year on
        # and was immediately overdue again. Found live.
        vals = {'last_run': today, 'last_count': made}
        nxt = self.next_run or today
        if nxt <= today:
            step = relativedelta(months=max(self.every_months, 1))
            while nxt <= today:
                nxt += step
            vals['next_run'] = nxt
        self.sudo().write(vals)
        _logger.info('pb_training: schedule "%s" put %s %s on %s; next on %s',
                     self.name, made,
                     counted(made, 'person', 'people'),
                     self.channel_id.name, self.next_run)
        return made
