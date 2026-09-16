# -*- coding: utf-8 -*-
"""The one job that runs every morning.

WHAT IT CHASES, AND WHAT IT DELIBERATELY DOES NOT. It chases the EMPLOYEE, and
only the employee: three days before their deadline, the day before, on the
day, and every third day after it. The manager's "you have goals to read" chase
is the ROUTE'S own (`late.remind_days`) and the HR lead's escalation is the
route's too (`late.escalate_days`) — a second opinion written here would be a
second set of dates that sooner or later disagrees with the request's own trail,
and the person reading the trail would have no way to tell which was right.

EVERY NUDGE IS SENT ONCE. The key is written onto the sheet (`reminder_log`),
so a job that runs twice in a morning — a restore, a manual press, a cron that
caught up after an outage — sends nothing the second time. The key names the
DAY as well as the kind for the late nudges, which is what makes "every third
day" a schedule rather than a flood.

A CAP THAT IS RIGHT FOR A SCREEN IS A BUG IN A JOB (R76), so the cap here is its
own dial and it is a safety rail rather than a page size: it exists so a
misconfigured deadline cannot email four thousand people twice. The job logs
honestly when it hits it.

OFF IS A REAL STATE (R54). With `pb_goals.reminders` off the job still runs,
still works out who it would have chased, and LOGS the number — and the board
says the same thing on screen with the same number. A thing that is off and
does not say so is reported as broken.
"""

import logging

from odoo import _, api, fields, models

from .goals_common import (
    P_REMINDER_CAP, P_REMINDERS, counted, flag, leg, number,
)

_logger = logging.getLogger(__name__)

#: How many days before the deadline a nudge goes out, and the key each one is
#: remembered by. Written as data so adding a fourth is a line rather than a
#: branch.
BEFORE = ((3, 'd3'), (1, 'd1'), (0, 'd0'))

#: How often the late nudge repeats, in days.
LATE_EVERY = 3


class PbGoalsAutomation(models.AbstractModel):
    _name = 'pb.goals.automation'
    _description = 'Goals: the daily job'

    # ==================================================================
    @api.model
    def _ensure_route(self):
        """A third leg on "every database ends up with a route", and it is the
        one that HEALS.

        `post_init_hook` covers a fresh install and a migration covers a
        database upgrading to a new version — and between them is the case
        that actually happened here: an install where the catalogue row this
        module owns had not loaded yet when the hook ran, so the seed refused
        with a single INFO line and the install reported success. Nothing
        visibly broke. A goal sheet sent in simply never reached anybody's
        inbox, and the only trace was one line in a log nobody was reading.

        `Seed.lay` asks the database what is already there before it creates
        anything, so on every ordinary morning this costs a handful of queries
        and does nothing at all. Guarded, because a route that could not be
        laid must never stop the chasing.
        """
        return leg(self.env, 'making sure the goal route exists', lambda: (
            __import__('odoo.addons.pb_goals.models.goal_set_approval',
                       fromlist=['seed_all']).seed_all(self.env)))

    @api.model
    def _cron_daily(self):
        """Everything the morning owes, in one line in the log."""
        self._ensure_route()
        today = fields.Date.today()
        on = flag(self.env, P_REMINDERS)
        cap = number(self.env, P_REMINDER_CAP, 400)
        due = self._due_reminders(today)
        if not on:
            _logger.info(
                'pb_goals: chasing is switched off — %s goal sheet(s) would '
                'have been nudged this morning', len(due))
            return {'sent': 0, 'would_have': len(due), 'off': True}
        sent = 0
        capped = False
        for goal_set, key, kind in due:
            if sent >= cap:
                capped = True
                break
            # ONE SAVEPOINT PER SHEET (R131). A single employee with a broken
            # address must not cost the other three hundred their reminder.
            if leg(self.env, 'nudging goal sheet %s' % goal_set.id,
                   lambda s=goal_set, k=key, n=kind: s._nudge(k, n)):
                sent += 1
        _logger.info(
            'pb_goals: %s goal sheet(s) nudged this morning, %s were due%s',
            sent, len(due), (' (the cap of %s was reached)' % cap)
            if capped else '')
        return {'sent': sent, 'due': len(due), 'capped': capped}

    @api.model
    def _due_reminders(self, today=None):
        """Which sheets owe which nudge this morning, as the system.

        The search is explicit about the states rather than about the spelling
        of them (R50): ordering or filtering by a Selection column sorts the
        stored string, which is alphabetical and never lifecycle order.
        """
        today = today or fields.Date.today()
        Set = self.env['pb.goal.set'].sudo()
        rows = []
        open_sheets = Set.search([
            ('state', 'in', ('draft', 'returned')),
            ('deadline', '!=', False),
            ('cycle_id.state', '=', 'open'),
        ], order='deadline asc')
        for sheet in open_sheets:
            days = (sheet.deadline - today).days
            key = None
            kind = ''
            for offset, tag in BEFORE:
                if days == offset:
                    key, kind = tag, tag
                    break
            if key is None and days < 0:
                over = -days
                if over % LATE_EVERY == 0:
                    key, kind = 'late-%s' % over, 'late'
            if not key or sheet._already_nudged(key):
                continue
            rows.append((sheet, key, kind))
        return rows

    # ------------------------------------------------------- the manual door
    @api.model
    def run_now(self):
        """"Run it this minute" — EXACTLY what the night does (R53).

        Not a subset of it: a button whose number cannot be compared to the
        morning's log is a button nobody trusts, and the piece somebody leaves
        out is always the piece that turns out to be broken.
        """
        if not self.env.user.has_group('pb_goals.group_goals_manager'):
            from odoo.exceptions import UserError
            raise UserError(_(
                "Running the goals job by hand is for the HR team."))
        return self._cron_daily()


class PbGoalSetReminders(models.Model):
    _inherit = 'pb.goal.set'

    def _already_nudged(self, key):
        self.ensure_one()
        return key in (self.reminder_log or '').split(',')

    def _remember_nudge(self, key):
        self.ensure_one()
        keys = [k for k in (self.reminder_log or '').split(',') if k]
        if key not in keys:
            keys.append(key)
        # The column is a Char and a year of late nudges would overrun it, so
        # only the last twenty are kept — which is twenty more than anything
        # reads and still fits.
        self.sudo().write({'reminder_log': ','.join(keys[-20:])})
        return True

    def _nudge(self, key, kind):
        """One reminder to one person, remembered so it goes once."""
        self.ensure_one()
        if self._already_nudged(key):
            return False
        sent = self._send('pb_goals.mail_goals_reminder')
        # THE KEY IS WRITTEN EVEN WHEN THERE WAS NO ADDRESS TO SEND TO.
        # Otherwise a person with no email address is "due a nudge" every
        # single morning for the rest of the year, and the job's honest count
        # becomes a number nobody can read.
        self._remember_nudge(key)
        if sent and kind == 'late':
            self.message_post(body=_(
                "Reminded — their goals are %s overdue.",
                key.split('-')[-1] + ' ' + counted(
                    int(key.split('-')[-1] or 1), _('day'), _('days'))))
        return bool(sent)
