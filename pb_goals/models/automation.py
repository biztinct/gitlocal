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

from datetime import timedelta

from odoo import _, api, fields, models

from .checkin import month_first
from .goals_common import (
    P_BULK_CAP, P_CHECKINS, P_REMINDER_CAP, P_REMINDERS, P_REVIEW_LEAD_DAYS,
    SET_RUNNING, counted, flag, leg, number,
)

_logger = logging.getLogger(__name__)

#: How many days before the deadline a nudge goes out, and the key each one is
#: remembered by. Written as data so adding a fourth is a line rather than a
#: branch.
BEFORE = ((3, 'd3'), (1, 'd1'), (0, 'd0'))

#: How often the late nudge repeats, in days.
LATE_EVERY = 3

#: The monthly conversation is nudged three days before the day it is planned
#: for, on the day, and three days after — and then never again, because a
#: month has an end and a nudge about a month that is over is noise. The month
#: itself is closed off as `missed` instead, which is a fact rather than an
#: email.
CHECKIN_BEFORE = 3
CHECKIN_AFTER = 3

#: A review is worth more warning than a check-in and is chased until it is
#: written up: a week before, on the day, and every week after.
REVIEW_BEFORE = 7
REVIEW_LATE_EVERY = 7


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
        laid = leg(self.env, 'making sure the goal route exists', lambda: (
            __import__('odoo.addons.pb_goals.models.goal_set_approval',
                       fromlist=['seed_all']).seed_all(self.env)))
        # B2's route heals the same way and for the same reason. Two separate
        # legs, because a catalogue row that failed to load for one of them
        # must not cost the other its route.
        leg(self.env, 'making sure the goal-change route exists', lambda: (
            __import__('odoo.addons.pb_goals.models.change_approval',
                       fromlist=['seed_all_changes']).seed_all_changes(
                           self.env)))
        return laid

    @api.model
    def _cron_daily(self):
        """Everything the morning owes, in one line in the log.

        SIX LEGS AND EACH ONE IN ITS OWN SAVEPOINT (R131). A try/except is not
        enough once a leg has reached the database: Postgres aborts the whole
        transaction and every statement after it fails too, so a broken
        check-in would silently cost the deadline nudges as well — with four
        cheerful warnings in the log and nothing on any screen.
        """
        out = {}
        self._ensure_route()
        today = fields.Date.today()
        # THE DEADLINE LEG KEEPS ITS OWN SHAPE, and that is not tidiness: the
        # "run it now" button reports these numbers and the morning's log line
        # prints them, so a refactor that folded them into a single count
        # would silently change what a button somebody trusts says (R53 — a
        # number that cannot be compared to the morning's log is a number
        # nobody trusts).
        deadlines = leg(self.env, 'the deadline nudges',
                        lambda: self._run_deadline_nudges(today)) or {}
        out.update(deadlines if isinstance(deadlines, dict) else {})
        out['deadlines'] = out.get('sent', 0)
        out['checkins_made'] = leg(self.env, 'making this month\'s check-ins',
                                   lambda: self._make_checkins(today))
        out['checkins_missed'] = leg(self.env, 'closing off last month',
                                     lambda: self._close_missed(today))
        out['checkin_nudges'] = leg(self.env, 'the check-in nudges',
                                    lambda: self._checkin_nudges(today))
        out['reviews_made'] = leg(self.env, 'opening the reviews that are due',
                                  lambda: self._make_reviews(today))
        out['review_nudges'] = leg(self.env, 'the review nudges',
                                   lambda: self._review_nudges(today))
        _logger.info(
            'pb_goals: this morning — %s', ', '.join(
                '%s %s' % (value, key) for key, value in out.items()))
        return out

    @api.model
    def _run_deadline_nudges(self, today=None):
        """Chase the people whose goals are not written yet."""
        today = today or fields.Date.today()
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

    # ==================================================================
    #  B2 — the year after the goals are agreed
    # ==================================================================
    @api.model
    def _running_sets(self):
        """Every agreed sheet on an open goal year, as the system.

        Explicit about the STATES rather than about the spelling of them
        (R50), and explicit about the cycle being open — a sheet on a year
        somebody closed is finished, and a finished year does not owe anybody
        a conversation.
        """
        return self.env['pb.goal.set'].sudo().search([
            ('state', 'in', list(SET_RUNNING)),
            ('cycle_id.state', '=', 'open'),
        ], order='id')

    @api.model
    def _make_checkins(self, today=None):
        """This month's conversation, for everybody whose goals are agreed.

        IDEMPOTENT BY CONSTRUCTION, twice over: `ensure_for` searches first
        and a unique index on (sheet, month) catches the case where two jobs
        overlap. A monthly row made by a job that runs thirty times a month
        cannot be protected by a Python check alone.

        OFF IS A REAL STATE (R54): with `pb_goals.checkins` off the job still
        works out how many it would have made and LOGS the number, because a
        thing that is off and does not say so is reported as broken.
        """
        today = today or fields.Date.today()
        first = month_first(today)
        sheets = self._running_sets()
        wanted = [sheet for sheet in sheets
                  if sheet._checkin_is_due_this_month(first)]
        if not flag(self.env, P_CHECKINS):
            _logger.info(
                'pb_goals: monthly check-ins are switched off — %s would '
                'have been opened this month', len(wanted))
            return 0
        Checkin = self.env['pb.goal.checkin']
        # ONLY THE COUNT EVER LIES, AND THAT IS ENOUGH TO BREAK IT (R90).
        # "Did this row get made just now" cannot be asked of `create_date`:
        # a row made at six o'clock this morning was made TODAY, so a second
        # run on the same day reported one made every time over a table it had
        # not touched — the figures identical, the number a fiction, and the
        # job's whole claim being that it is idempotent. Found live by
        # pressing "run it now" twice. The honest question is which sheets had
        # no row BEFORE this pass, asked once, in one query.
        already = set(Checkin.sudo().search([
            ('month', '=', first),
            ('set_id', 'in', [s.id for s in wanted]),
        ]).mapped('set_id').ids)
        made = 0
        cap = number(self.env, P_BULK_CAP, 2000)
        for sheet in wanted:
            if sheet.id in already:
                continue
            if made >= cap:
                _logger.info('pb_goals: the check-in cap of %s was reached; '
                             'the rest are made tomorrow', cap)
                break
            if leg(self.env, 'the check-in for sheet %s' % sheet.id,
                   lambda s=sheet: Checkin.ensure_for(s, today)):
                made += 1
        return made

    @api.model
    def _close_missed(self, today=None):
        """A month that ended with nothing written down is MISSED, not open.

        The question is about the MONTH and not about today: anything still
        planned whose month has finished is missed, however far back it goes,
        so a job that did not run for a week catches up rather than leaving a
        hole (R148's shape — ask the honest question, and let the stamp be
        belt as well as braces).
        """
        today = today or fields.Date.today()
        first = month_first(today)
        stale = self.env['pb.goal.checkin'].sudo().search([
            ('state', '=', 'planned'), ('month', '<', first)])
        if stale:
            stale.action_checkin_missed()
        return len(stale)

    @api.model
    def _checkin_nudges(self, today=None):
        """Three days before, on the day, three days after. Once each.

        BOTH SIDES GET IT, because a conversation is two people and reminding
        only the manager makes the employee a passenger in their own year.
        """
        today = today or fields.Date.today()
        if not flag(self.env, P_REMINDERS) or not flag(self.env, P_CHECKINS):
            return 0
        cap = number(self.env, P_REMINDER_CAP, 400)
        rows = self.env['pb.goal.checkin'].sudo().search([
            ('state', '=', 'planned'),
            ('scheduled_date', '>=', today - timedelta(days=CHECKIN_AFTER)),
            ('scheduled_date', '<=', today + timedelta(days=CHECKIN_BEFORE)),
        ], order='scheduled_date')
        sent = 0
        for row in rows:
            if sent >= cap:
                break
            days = (row.scheduled_date - today).days
            key = None
            if days == CHECKIN_BEFORE:
                key = 'before'
            elif days == 0:
                key = 'day'
            elif days == -CHECKIN_AFTER:
                key = 'after'
            if not key or row._already_nudged(key):
                continue
            if leg(self.env, 'nudging check-in %s' % row.id,
                   lambda r=row, k=key: r._nudge(k)):
                sent += 1
        return sent

    @api.model
    def _make_reviews(self, today=None):
        """Open a review when it is nearly due, and never a year early.

        A LIST OF THINGS DUE IN NINE MONTHS IS A LIST NOBODY READS. The lead
        time is a dial (`pb_goals.review_lead_days`, 30) because a company
        that runs a long review season wants longer.
        """
        today = today or fields.Date.today()
        lead = max(1, number(self.env, P_REVIEW_LEAD_DAYS, 30))
        horizon = today + timedelta(days=lead)
        made = 0
        sheets = self._running_sets()
        # Same lesson as the check-ins above: ask which (sheet, kind) pairs
        # exist BEFORE this pass rather than asking a row how old it is.
        already = {
            (row.set_id.id, row.kind)
            for row in self.env['pb.goal.review'].sudo().search(
                [('set_id', 'in', sheets.ids)])}
        for sheet in sheets:
            for kind, due in sheet._review_due_dates().items():
                if not due or due > horizon:
                    continue
                if (sheet.id, kind) in already:
                    continue
                if leg(self.env,
                       'the %s review for sheet %s' % (kind, sheet.id),
                       lambda s=sheet, k=kind, d=due: s._ensure_review(k, d)):
                    made += 1
        return made

    @api.model
    def _review_nudges(self, today=None):
        """A week before, on the day, and every week late. Once each.

        THE MANAGER AND NOT BOTH SIDES: writing a review up is the manager's
        job, and chasing somebody about a piece of work they do not owe is how
        a process gets a reputation.
        """
        today = today or fields.Date.today()
        if not flag(self.env, P_REMINDERS):
            return 0
        cap = number(self.env, P_REMINDER_CAP, 400)
        rows = self.env['pb.goal.review'].sudo().search([
            ('state', '=', 'planned'),
            ('due_date', '<=', today + timedelta(days=REVIEW_BEFORE)),
        ], order='due_date')
        sent = 0
        for row in rows:
            if sent >= cap:
                break
            days = (row.due_date - today).days
            key = None
            if days == REVIEW_BEFORE:
                key = 'before'
            elif days == 0:
                key = 'day'
            elif days < 0 and (-days) % REVIEW_LATE_EVERY == 0:
                key = 'late-%s' % (-days)
            if not key or row._already_nudged(key):
                continue
            if leg(self.env, 'nudging review %s' % row.id,
                   lambda r=row, k=key: r._nudge(k)):
                sent += 1
        return sent

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

    def _checkin_is_due_this_month(self, first_of_month):
        """Whether this sheet owes a conversation for this month.

        THREE QUESTIONS AND ALL THREE MATTER. The month has to fall inside the
        goal year — a check-in dated after the year ends is a conversation
        about nothing. It has to fall on or after the day this person's goals
        start covering — somebody who joined on the 20th does not owe a
        conversation about the first nineteen days. And the sheet has to be
        agreed, which the caller has already asked.
        """
        self.ensure_one()
        record = self.sudo()
        cycle = record.cycle_id
        if not cycle or not cycle.date_start or not cycle.date_end:
            return False
        if first_of_month > cycle.date_end:
            return False
        covered = record.covered_from or cycle.date_start
        # The month somebody joined in counts: a conversation on the 25th
        # about the fortnight since they arrived is a conversation worth
        # having, and the alternative is a new starter's first check-in
        # falling five weeks after their goals were agreed.
        if first_of_month < month_first(covered):
            return False
        # AND NEVER BEFORE THE GOALS WERE AGREED. A conversation about a plan
        # nobody had yet is a row with nothing in it.
        locked_on = record.locked_at and record.locked_at.date()
        if locked_on and first_of_month < month_first(locked_on):
            return False
        return True

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
