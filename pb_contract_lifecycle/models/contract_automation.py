# -*- coding: utf-8 -*-
"""What runs on its own, and the switch in front of it.

P0 ships ONE daily job for the whole lifecycle and every phase adds to it rather
than adding a second one — two jobs on the same table is two jobs that can
disagree about what "today" means. So this rides
`pb.journey.case._cron_lifecycle_reminders()` exactly as P5's does. This module
ships NO cron of its own.

WHAT THE DAILY JOB DOES HERE:

  * raises a decision for every contract that has come inside its lead time —
    behind `pb_contract_lifecycle.auto_trigger`, which is OFF on install;
  * escalates an extension nobody agreed inside the window, once;
  * nudges HR every day in the last week before a contract ends;
  * marks a decision LAPSED when the date went past and nobody chose;
  * tops up the employment-type backfill and makes sure the two contract types
    exist (R44: the backfill belongs in the job that re-runs, not in a
    migration nobody re-runs).

THE TRIGGER IS OFF ON INSTALL AND THAT IS THE POINT (R54). The first night
after somebody installs this module, every contract already inside its lead time
would raise a decision and email a manager. Switched off, the job COUNTS them
and writes the number in the log; the lens says the same number on screen with
the same words; an administrator turns it on once the number looks right. And
even switched on, one night never raises more than `trigger_cap`.

THE CAP IS A PARAMETER, NEVER A CONSTANT IN A READ (R76). The screen's read of
the board is capped at three hundred rows because that is right for a screen;
the job passes no cap at all, because a cap that is right for a screen is a bug
in a job — it would quietly leave the four hundred and first contract to expire.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .contract_common import (
    GROUP_MANAGER, P_AUTO_TRIGGER, P_LEAD_DAYS, P_NAG_DAYS, P_TRIGGER_CAP,
    REVIEW_WAITING, counted, flag, number,
)

_logger = logging.getLogger(__name__)


class PbJourneyCaseContractAutomation(models.Model):
    _inherit = 'pb.journey.case'

    @api.model
    def _cron_lifecycle_reminders(self):
        counts = super()._cron_lifecycle_reminders() or {}
        if not isinstance(counts, dict):
            counts = {'base': counts}
        for key, fn in (
                ('contract_types', self._ensure_contract_vocabulary),
                ('contract_decisions', self._trigger_contract_reviews),
                ('contract_escalations', self._escalate_contract_extensions),
                ('contract_nudges', self._nudge_contract_decisions),
                ('contract_lapsed', self._lapse_contract_reviews),
                ('contract_typed', self._top_up_employment_types)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — one piece, one grave
                _logger.exception('pb_contract_lifecycle: %s failed', key)
                counts[key] = 0
        _logger.info(
            'pb_contract_lifecycle: %s decision(s) raised, %s extension(s) '
            'escalated, %s nudge(s), %s lapsed, %s employment type(s) filled '
            'in',
            counts.get('contract_decisions'),
            counts.get('contract_escalations'),
            counts.get('contract_nudges'),
            counts.get('contract_lapsed'),
            counts.get('contract_typed'))
        return counts

    # -------------------------------------------------- who is coming up
    @api.model
    def _due_for_decision(self, today=None, cap=None):
        """Every contract inside its lead time with no open decision on it.

        Read once and used twice — by the trigger and by the count the log
        prints when the trigger is switched off — so the number an
        administrator reads is the number that would actually have happened.

        `cap` defaults to NO cap. The board's own read caps at three hundred
        rows because that is right for a screen; a job that stopped at three
        hundred would leave the three hundred and first contract to expire with
        nobody told (R76).
        """
        today = today or fields.Date.today()
        lead = max(1, number(self.env, P_LEAD_DAYS, 60))
        horizon = today + timedelta(days=lead)
        Contract = self.env['hr.contract'].sudo()
        Review = self.env['pb.contract.review'].sudo()
        contracts = Contract.search([
            ('date_end', '!=', False),
            ('date_end', '>=', today),
            ('date_end', '<=', horizon),
            ('state', 'in', ('draft', 'open')),
        ], order='date_end, id', limit=(cap or None))
        out = []
        for contract in contracts:
            try:
                if not contract.employee_id:
                    continue
                # ANY decision, not just an OPEN one. A contract whose
                # decision was made — extended, converted, let go — is a
                # contract nobody has to decide about again: the thing to
                # watch from then on is the NEW contract that followed, which
                # has its own end date and turns up here in its own time.
                # Testing only the open states raised a second decision on
                # every contract the night after it was extended, and emailed
                # the manager about it, for ever. Re-raising a decided
                # contract is a human act, and `open_for` says so.
                if Review.search_count([('contract_id', '=', contract.id)]):
                    continue
                out.append(contract)
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: lead time for '
                                  'contract %s', contract.id)
        return out

    @api.model
    def _trigger_contract_reviews(self, today=None):
        due = self._due_for_decision(today)
        if not flag(self.env, P_AUTO_TRIGGER):
            _logger.info(
                'pb_contract_lifecycle: the automatic trigger is switched '
                'off. %s contract(s) would have had a decision raised '
                'tonight — turn pb_contract_lifecycle.auto_trigger on once '
                'that number looks right.', len(due))
            return 0
        cap = max(1, number(self.env, P_TRIGGER_CAP, 20))
        if len(due) > cap:
            _logger.warning(
                'pb_contract_lifecycle: %s contracts are inside their lead '
                'time, which is over the cap of %s — the first %s are raised '
                'tonight and the rest tomorrow', len(due), cap, cap)
        Review = self.env['pb.contract.review'].sudo()
        made = 0
        for contract in due[:cap]:
            try:
                review = Review.open_for(contract)
                review.notify_decision_needed()
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: could not raise a '
                                  'decision for contract %s', contract.id)
        return made

    # ------------------------------------------------------- the escalations
    @api.model
    def _escalate_contract_extensions(self, today=None):
        return self.env['pb.contract.extension']._escalate_overdue(today)

    @api.model
    def _nudge_contract_decisions(self, today=None):
        """Halfway to the date, then every day in the last week.

        TWO DIFFERENT NUDGES WITH TWO DIFFERENT STAMPS, because they mean
        different things. The escalation says "this is no longer only the
        manager's" and happens ONCE; the daily nudge says "this is now urgent"
        and has to repeat, so it is stamped with the DATE it last went rather
        than with a boolean — a boolean would fire once and go quiet exactly
        when it matters most.

        Only a decision NOBODY IS WORKING ON is chased. An extension waiting
        for a manager has its own escalation and an evaluation that is running
        has its own reminders; chasing those as well would teach everybody to
        ignore all three.
        """
        today = today or fields.Date.today()
        Review = self.env['pb.contract.review'].sudo()
        Activity = self.env['mail.activity'].sudo()
        nag_days = max(1, number(self.env, P_NAG_DAYS, 7))
        made = 0

        # ---- halfway: it is no longer only the manager's ----
        rows = Review.search([('state', 'in', REVIEW_WAITING),
                              ('escalated', '=', False),
                              ('end_date', '!=', False)])
        for row in rows:
            try:
                half = max(1, (row.lead_days or 60) // 2)
                if row.end_date - timedelta(days=half) > today:
                    continue
                row.notify_decision_needed()
                row._mail('pb_contract_lifecycle.mail_template_decision_late',
                          row._hr_addresses())
                row.write({'escalated': True})
                row.message_post(body=_(
                    "Halfway to the date and still undecided — the HR team "
                    "has been told. %s left.",
                    counted(max(0, (row.end_date - today).days), _('day'),
                            _('days'))))
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: escalation for '
                                  'decision %s', row.id)

        # ---- the last week: every day, and a to-do somebody can see ----
        rows = Review.search([
            ('state', 'in', REVIEW_WAITING),
            ('end_date', '!=', False),
            ('end_date', '>=', today),
            ('end_date', '<=', today + timedelta(days=nag_days)),
            '|', ('nagged_on', '=', False), ('nagged_on', '<', today),
        ])
        for row in rows:
            try:
                left = (row.end_date - today).days
                summary = _("Contract ends in %(days)s days: %(who)s",
                            days=max(left, 0),
                            who=row.employee_id.name or '')
                existing = Activity.search([
                    ('res_model', '=', 'pb.contract.review'),
                    ('res_id', '=', row.id),
                    ('summary', '=', summary)], limit=1)
                if not existing:
                    row.activity_schedule(
                        act_type_xmlid='mail.mail_activity_data_todo',
                        summary=summary,
                        note=_("%(who)s's contract ends on %(when)s and "
                               "nobody has chosen yet. Let it end, extend it, "
                               "or make it permanent.",
                               who=row.employee_id.name or '',
                               when=row.end_date),
                        user_id=(row.manager_user_id or self.env.user).id,
                        date_deadline=row.end_date)
                row.write({'nagged_on': today})
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: daily nudge for '
                                  'decision %s', row.id)
        return made

    # ---------------------------------------------------- the date went past
    @api.model
    def _lapse_contract_reviews(self, today=None):
        """A decision nobody made, said out loud rather than left open.

        LAPSED IS NOT A FAILURE STATE, IT IS AN HONEST ONE. The contract has
        ended; whatever anybody meant to do, what actually happened is that
        nothing was decided. Leaving the record at "Decision needed" for ever
        would put a permanent red number on a board and teach everybody to
        ignore it.

        Only `upcoming` and `decide` lapse. An extension waiting for a manager
        and an evaluation that is running are both decisions IN PROGRESS — they
        are told they are late, and they keep their state, because closing them
        would throw away work somebody is doing.
        """
        today = today or fields.Date.today()
        Review = self.env['pb.contract.review'].sudo()
        made = 0
        rows = Review.search([('state', 'in', REVIEW_WAITING),
                              ('end_date', '!=', False),
                              ('end_date', '<', today)])
        for row in rows:
            try:
                row.write({'state': 'lapsed'})
                row.message_post(body=_(
                    "This contract ended on %s and nobody chose. It is "
                    "recorded as ended undecided — somebody has to speak to "
                    "them, and to payroll.", row.end_date))
                if not row.lapse_alerted:
                    row._mail(
                        'pb_contract_lifecycle.mail_template_decision_lapsed',
                        row._hr_addresses() + row._manager_addresses())
                    row.write({'lapse_alerted': True})
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: could not lapse '
                                  'decision %s', row.id)

        # In-progress work that has run past the date is TOLD, never closed.
        late = Review.search([('state', 'in', ('extension', 'conversion')),
                              ('end_date', '!=', False),
                              ('end_date', '<', today),
                              ('lapse_alerted', '=', False)])
        for row in late:
            try:
                row._mail('pb_contract_lifecycle.mail_template_decision_late',
                          row._hr_addresses() + row._manager_addresses())
                row.write({'lapse_alerted': True})
                row.message_post(body=_(
                    "The contract ended on %s while this was still being "
                    "worked on. It has not been closed — finish it, and date "
                    "the new contract from the day after the old one ended.",
                    row.end_date))
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: late alert for '
                                  'decision %s', row.id)
        return made

    # ------------------------------------------------------- the top-up pass
    @api.model
    def _top_up_employment_types(self):
        counts = self.env['hr.employee']._pb_backfill_employment_type()
        return (counts.get('intern', 0) + counts.get('contractor', 0)
                + counts.get('other', 0))

    @api.model
    def _ensure_contract_vocabulary(self):
        made = self.env['hr.employee']._pb_ensure_contract_types()
        return len(made)

    # ------------------------------------------------------------ on demand
    @api.model
    def run_contract_automation(self):
        """The same work, by hand. HR only — it sends email.

        EXACTLY what the night does, in the same order, including the top-up
        (R53: a "run it now" button that does a subset of the job is a button
        whose result nobody can compare to tomorrow morning's).
        """
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only the HR team can run the contract steps by hand."))
        return {
            'types': self._ensure_contract_vocabulary(),
            'decisions': self._trigger_contract_reviews(),
            'escalations': self._escalate_contract_extensions(),
            'nudges': self._nudge_contract_decisions(),
            'lapsed': self._lapse_contract_reviews(),
            'typed': self._top_up_employment_types(),
        }
