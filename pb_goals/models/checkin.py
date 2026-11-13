# -*- coding: utf-8 -*-
"""`pb.goal.checkin` — the conversation that happens every month.

THE YEAR IS WON OR LOST IN THE MONTHS BETWEEN. A goal sheet agreed in April and
opened again in March is a spreadsheet, not a plan: nobody remembers what
changed, nothing was re-prioritised, and the year-end conversation is about two
people's memories again — which is the exact problem this module exists to
solve. So the month is the unit, and one row a month per agreed sheet is what
makes "we talked" a fact rather than a claim.

ONE ROW PER SHEET PER MONTH, AND THE DATABASE ENFORCES IT. The job that makes
them runs every morning and is therefore reached roughly thirty times per row;
a duplicate-check in Python is a check that is right until two jobs overlap.
`models.Constraint` is the form that works on Odoo 19 — a `_sql_constraints`
LIST is silently ignored and the rule simply is not enforced, with nothing
anywhere to say so.

EITHER SIDE MAY MARK IT DONE, and that is a deliberate choice rather than a
looseness. A conversation has two people in it; insisting the manager records
it means the months where the manager is the problem are the months with no
record. The row carries WHO wrote it down, which is the honest version of the
same information.

MISSED IS A REAL OUTCOME (R54's shape, from the data side). A month that stayed
"planned" past the end of the month is marked `missed` by the same job — not
deleted, not left hanging — because "nobody talked in July" is precisely the
number the manager-compliance report exists to show. A row that quietly stays
planned for ever says nothing at all.

THE SNAPSHOT IS WHAT MAKES IT EVIDENCE. `kr_snapshot_json` freezes where every
key result stood at the moment the conversation was marked done, so a year-end
review can say "it was at 20% in September and 30% in February" over a record
rather than over a recollection. The live numbers keep moving; the snapshot
does not.
"""

import json
import logging

from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goals_common import (
    CHECKIN_STATES, CHECKIN_STATE_LABEL, P_CHECKIN_DAY, P_HR_SENDER, leg,
    number, text,
)

_logger = logging.getLogger(__name__)


def month_first(value):
    """The first of whatever month a date falls in."""
    return date(value.year, value.month, 1)


def month_last(value):
    """The last day of whatever month a date falls in."""
    if value.month == 12:
        return date(value.year, 12, 31)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def add_months(value, months):
    """A date `months` on, clamped to the end of a short month.

    The 31st of January plus one month is the 28th of February and not the 3rd
    of March: a schedule that walks off the end of a month walks the whole
    year with it.
    """
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, month_last(date(year, month, 1)).day)
    return date(year, month, day)


def months_between(start, end):
    """WHOLE months from `start` to `end`, never a rounded fraction.

    "Three months before the half-way point" is a question about calendar
    months and a division by 30.44 is a question about days pretending to be
    one — which is how somebody who joined on the 2nd of July and somebody who
    joined on the 29th of June end up on opposite sides of the same rule for
    no reason anybody can explain.
    """
    if not start or not end:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


class PbGoalCheckin(models.Model):
    _name = 'pb.goal.checkin'
    _description = 'Monthly goal check-in'
    #: Newest month first: the question somebody asks of this list is "did we
    #: talk this month", and a list that opens on April is a list nobody
    #: scrolls.
    _order = 'month desc, id desc'

    _one_per_month = models.Constraint(
        'unique(set_id, month)',
        'There is already a check-in on that goal sheet for that month.')

    set_id = fields.Many2one(
        'pb.goal.set', string='Goal sheet', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Whose', related='set_id.employee_id',
        store=True, index=True, readonly=True)
    #: STORED AND RELATED, because the compliance report groups on it and a
    #: non-stored related cannot go in a `_read_group` (R10 from the reporting
    #: side). It follows the sheet, which follows the employee's own parent
    #: (R138), so a re-pointed manager takes effect at once.
    manager_user_id = fields.Many2one(
        'res.users', string='Their manager', related='set_id.manager_user_id',
        store=True, index=True, readonly=True)
    manager_employee_id = fields.Many2one(
        'hr.employee', string='Manager',
        related='set_id.manager_employee_id', store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Part of the business',
        related='set_id.department_id', store=True, readonly=True)
    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Goal year', related='set_id.cycle_id',
        store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='set_id.company_id',
        store=True, index=True, readonly=True)

    name = fields.Char(string='Check-in', compute='_compute_name', store=True,
                       readonly=True)
    month = fields.Date(
        string='Which month', required=True, index=True,
        help='Always the first of the month. One check-in per month per '
             'person.')
    scheduled_date = fields.Date(
        string='Planned for', required=True, index=True,
        help='The day of the month the goal year asks for. It is a prompt '
             'rather than an appointment — either side can mark it done '
             'earlier or later.')
    state = fields.Selection(
        CHECKIN_STATES, string='Status', default='planned', required=True,
        index=True, copy=False)
    progress_note = fields.Text(
        string='What was said',
        help='What moved this month, in a sentence or two. This is what a '
             'year-end conversation is built on.')
    blockers = fields.Text(
        string='What is in the way',
        help='Anything stopping progress that somebody else has to unblock. '
             'Leave it empty if there is nothing.')
    done_at = fields.Datetime(string='Marked done on', readonly=True,
                              copy=False)
    done_by_id = fields.Many2one('res.users', string='Marked done by',
                                 readonly=True, copy=False)
    #: WHERE EVERY KEY RESULT STOOD AT THE MOMENT THE CONVERSATION HAPPENED.
    #: JSON rather than a child table because nothing ever queries INTO it —
    #: it is read whole, beside the row that owns it, and a child table would
    #: be four thousand rows a month for a screen that shows one.
    kr_snapshot_json = fields.Text(string='Where the numbers stood',
                                   readonly=True, copy=False)
    reminder_log = fields.Char(string='Reminders already sent', copy=False,
                               readonly=True, default='')

    # ------------------------------------------------------------- computed
    @api.depends('employee_id', 'month')
    def _compute_name(self):
        for record in self:
            who = record.employee_id.sudo().name or _('Somebody')
            when = record.month and record.month.strftime('%B %Y') or ''
            record.name = '%s · %s' % (who, when)

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or _('Check-in')

    @api.constrains('month')
    def _check_month_is_a_first(self):
        for record in self:
            if record.month and record.month.day != 1:
                raise ValidationError(_(
                    "A check-in belongs to a whole month, so its date is the "
                    "first of that month."))

    # ---------------------------------------------------------------- doors
    @api.model
    def ensure_for(self, goal_set, when=None):
        """This month's check-in for one sheet. Idempotent by construction.

        Returns the row whether it made it or found it — a caller that has to
        tell the difference asks the row's `create_date`, and a caller that
        does not (which is all of them) gets the same answer either way.
        """
        when = when or fields.Date.today()
        first = month_first(when)
        existing = self.sudo().search(
            [('set_id', '=', goal_set.id), ('month', '=', first)], limit=1)
        if existing:
            return existing
        return self.sudo().create({
            'set_id': goal_set.id,
            'month': first,
            'scheduled_date': self._planned_day(
                first, goal_set.sudo().cycle_id.checkin_day),
        })

    @api.model
    def _planned_day(self, first_of_month, cycle_day=0):
        """The configured day of that month, clamped to a short February.

        THE GOAL YEAR'S OWN DAY WINS over the product-wide switch, because two
        companies on one database really do have different month-ends and the
        switch is only the number a new year starts with.
        """
        day = int(cycle_day or 0) or number(self.env, P_CHECKIN_DAY, 25)
        day = max(1, min(28, day))
        # 28 rather than 31: a check-in planned for "the 31st" silently moves
        # to the 28th in February and to the 30th in April, and a prompt that
        # lands on a different day each month is a prompt people stop
        # believing. The cap is at the shortest month so the day is the same
        # day all year.
        last = month_last(first_of_month).day
        return date(first_of_month.year, first_of_month.month,
                    min(day, last))

    def _may_complete(self):
        """Either side of the conversation, or the HR team."""
        self.ensure_one()
        record = self.sudo()
        if self.env.user.has_group('pb_goals.group_goals_manager'):
            return True
        if record.manager_user_id.id == self.env.uid:
            return True
        return bool(record.employee_id.user_id.id == self.env.uid)

    def action_checkin_done(self, note=False, blockers=False):
        """Write it down. THE NOTE IS THE WHOLE POINT and is required.

        A check-in marked done with nothing written on it is a tick in a box,
        and a tick in a box is exactly the thing that makes people stop
        believing a process. The refusal says so in words.
        """
        for record in self:
            if record.state == 'done':
                continue
            if not record._may_complete():
                raise UserError(_(
                    "A check-in is written up by the person whose goals they "
                    "are, by their manager, or by the HR team."))
            written = (note or '').strip()
            if not written:
                raise UserError(_(
                    "Write a line about what moved this month. A check-in "
                    "with nothing on it is a tick in a box, and nobody can "
                    "read a tick in a box next March."))
            record.sudo().write({
                'state': 'done',
                'progress_note': written,
                'blockers': (blockers or '').strip() or False,
                'done_at': fields.Datetime.now(),
                'done_by_id': self.env.uid,
                'kr_snapshot_json': record._snapshot(),
            })
            leg(self.env, 'the check-in note on sheet %s' % record.set_id.id,
                lambda rec=record: rec.set_id.sudo().message_post(body=_(
                    "%(who)s wrote up the %(month)s check-in.",
                    who=self.env.user.name or '',
                    month=(rec.month and rec.month.strftime('%B %Y') or ''))))
        return True

    def action_checkin_missed(self):
        """The month is over and nobody wrote anything down."""
        for record in self.filtered(lambda c: c.state == 'planned'):
            record.sudo().write({'state': 'missed'})
        return True

    def _snapshot(self):
        """Where every key result stood, frozen."""
        self.ensure_one()
        rows = []
        for goal in self.sudo().set_id.with_context(
                active_test=False).goal_ids.sorted(lambda g: (g.sequence,
                                                              g.id)):
            for kr in goal.kr_ids.sorted(lambda k: (k.sequence, k.id)):
                rows.append({
                    'goal': goal.title or '',
                    'kr': kr.title or '',
                    'measure': kr.measure or '',
                    'target': kr.target or 0.0,
                    'current': kr.current or 0.0,
                    'progress': round(kr.progress or 0.0, 1),
                })
        return json.dumps({'at': str(fields.Datetime.now()), 'krs': rows})

    def snapshot_rows(self):
        """The snapshot, as a list a screen can draw."""
        self.ensure_one()
        try:
            return (json.loads(self.kr_snapshot_json or '{}') or {}).get(
                'krs', [])
        except (TypeError, ValueError):
            return []

    # ------------------------------------------------------------- the words
    def _state_word(self):
        self.ensure_one()
        return CHECKIN_STATE_LABEL.get(self.state, self.state or '')

    def _month_word(self):
        self.ensure_one()
        return self.month and self.month.strftime('%B %Y') or ''

    # ------------------------------------------------------------ the chase
    def _already_nudged(self, key):
        self.ensure_one()
        return key in (self.reminder_log or '').split(',')

    def _remember_nudge(self, key):
        self.ensure_one()
        keys = [k for k in (self.reminder_log or '').split(',') if k]
        if key not in keys:
            keys.append(key)
        self.sudo().write({'reminder_log': ','.join(keys[-12:])})
        return True

    def _nudge(self, key):
        """One reminder to BOTH sides, remembered so it goes once.

        Both, because a conversation is two people and reminding only the
        manager makes the employee a passenger in their own year. The key is
        written whether or not there was an address to send to — otherwise
        somebody with no email is "due a nudge" every morning for the rest of
        the year and the job's honest count becomes a number nobody can read.
        """
        self.ensure_one()
        if self._already_nudged(key):
            return False
        record = self.sudo()
        sent = False
        for address in record._recipients():
            if record._send_checkin_mail(address):
                sent = True
        self._remember_nudge(key)
        return sent

    def _recipients(self):
        """The employee and their manager, each once, each a real address."""
        self.ensure_one()
        record = self.sudo()
        employee = record.employee_id
        manager = record.manager_user_id
        out = []
        for address in (employee.work_email or employee.private_email
                        or employee.user_id.email or '',
                        manager.email or manager.partner_id.email or ''):
            if address and address not in out:
                out.append(address)
        return out

    def _send_checkin_mail(self, address):
        """One email, with the recipient passed EXPLICITLY (R6).

        A `mail.template`'s own rendered `email_to` can reach `mail.mail`
        empty — queued, addressed to nobody, with no error anywhere.
        """
        self.ensure_one()
        template = self.env.ref('pb_goals.mail_goals_checkin',
                                raise_if_not_found=False)
        if not template or not address:
            return False
        values = {'email_to': address}
        sender = self.sudo().set_id._sender()
        if sender:
            values['email_from'] = sender
        template.sudo().send_mail(self.id, force_send=False,
                                  email_values=values)
        return True

    # ------------------------------------------------------------- the door
    def action_view_set(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal sheet'),
            'res_model': 'pb.goal.set',
            'res_id': self.set_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }
