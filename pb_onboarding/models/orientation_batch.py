# -*- coding: utf-8 -*-
"""Nobody sits through the welcome session alone.

Joiners arrive one at a time; the welcome session is run for a room. A batch is
the room: a date, the people bucketed into it, and nothing else. The bucketing
rule is one sentence — *the first session on or after the day you start* — and
it is deliberately not clever, because the question the HR coordinator asks is
"who is in Tuesday's session", and any rule they cannot predict makes that
question unanswerable.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _

from .onboarding_common import (
    P_ORIENT_FREQ, P_ORIENT_WEEKDAY, number, param,
)

_logger = logging.getLogger(__name__)

BATCH_STATES = [
    ('upcoming', 'Upcoming'),
    ('done', 'Held'),
    ('cancelled', 'Cancelled'),
]


class PbOrientationBatch(models.Model):
    _name = 'pb.orientation.batch'
    _description = 'Orientation Session'
    _order = 'batch_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Session')
    batch_date = fields.Date(string='Held on', required=True, index=True,
                             default=fields.Date.context_today)
    state = fields.Selection(
        BATCH_STATES, string='Status', default='upcoming', required=True,
        index=True)
    attendee_ids = fields.Many2many(
        'hr.employee', 'pb_orientation_batch_employee_rel', 'batch_id',
        'employee_id', string='Who is coming')
    attendee_count = fields.Integer(
        compute='_compute_attendee_count', string='People')
    location = fields.Char(string='Where')
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('batch_date')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Welcome session — %s', rec.batch_date or _('no date'))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Welcome session')

    @api.depends('attendee_ids')
    def _compute_attendee_count(self):
        for rec in self:
            rec.attendee_count = len(rec.attendee_ids)

    # ------------------------------------------------------------ the calendar
    @api.model
    def _next_session_date(self, from_day, company=None):
        """The first session date on or after `from_day`.

        Weekly means every one of the chosen weekday; fortnightly means every
        other one, anchored on the ISO week number so the answer does not
        depend on when the module was installed — two people looking at the
        same Tuesday must be told the same thing.
        """
        weekday = number(self.env, P_ORIENT_WEEKDAY, 1)
        weekday = weekday if 0 <= weekday <= 6 else 1
        freq = str(param(self.env, P_ORIENT_FREQ) or 'biweekly').strip()
        day = from_day or date.today()
        ahead = (weekday - day.weekday()) % 7
        candidate = day + timedelta(days=ahead)
        if freq == 'weekly':
            return candidate
        # Fortnightly: keep the EVEN ISO weeks. A joiner landing in an odd week
        # waits for the next one rather than getting a session of their own.
        if candidate.isocalendar()[1] % 2:
            candidate += timedelta(days=7)
        return candidate

    @api.model
    def batch_for(self, employee, joining_date):
        """Put this person in the right session, creating it if there is none.

        IDEMPOTENT TWICE OVER (R30): a batch already holding this person is
        returned untouched, and a person already in ANOTHER upcoming session
        is left where they are — a joiner moved between rooms by a second run
        of the same hook is a joiner who turns up on the wrong day.
        """
        if not employee:
            return self.browse()
        company = employee.company_id or self.env.company
        try:
            existing = self.sudo().search([
                ('attendee_ids', 'in', employee.id),
                ('state', '!=', 'cancelled'),
            ], limit=1)
            if existing:
                return existing
            when = self._next_session_date(
                joining_date or fields.Date.today(), company)
            batch = self.sudo().search([
                ('batch_date', '=', when),
                ('company_id', '=', company.id),
                ('state', '=', 'upcoming'),
            ], limit=1)
            if not batch:
                batch = self.sudo().create({
                    'batch_date': when,
                    'company_id': company.id,
                    'state': 'upcoming',
                })
            batch.sudo().write({'attendee_ids': [(4, employee.id)]})
            return batch
        except Exception:               # noqa: BLE001 — never break an arrival
            _logger.exception(
                'pb_onboarding: could not put employee %s in a welcome session',
                employee.id)
            return self.browse()

    # --------------------------------------------------------------- actions
    def action_done(self):
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True

    def action_reopen(self):
        self.write({'state': 'upcoming'})
        return True
