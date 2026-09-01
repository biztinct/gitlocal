# -*- coding: utf-8 -*-
"""What runs on its own, and the two switches in front of it.

P0 ships ONE daily job for the whole lifecycle and every phase adds to it
rather than adding a second one — two jobs on the same table is two jobs that
can disagree about what "today" means. So the daily work extends
`_cron_lifecycle_reminders()`.

THE ONE EXCEPTION IS THE LAST-HOURS ALERT, and it is a real exception rather
than a shortcut. "Two hours left to answer" is a thing that has to be said
DURING the day it is true; a job that runs once a night can only ever say it
the morning after. So there is a second, deliberately tiny, HOURLY cron that
does exactly one thing and is stamped so it says it once.

WHAT THE DAILY JOB DOES:

  * opens reviews for trial periods that have come inside their lead time —
    behind `pb_probation.auto_trigger`, which is OFF on install;
  * nudges HR fifteen days and five days before a trial period ends;
  * consolidates a review whose answer window has shut, so a colleague who
    never answered cannot hold a decision up for ever;
  * tops the trial-state backfill up for anybody who arrived through a route
    that bypassed `create` (R44's discipline: the backfill belongs in the daily
    job, not in a migration nobody re-runs).

THE TRIGGER IS OFF ON INSTALL AND THAT IS THE POINT. The first night after
somebody installs this module, every trial period already inside its lead time
would open a review and email a manager. On a database with a few hundred
joiners that is a few hundred emails nobody asked for. Switched off, the job
COUNTS them and writes the number in the log; an administrator reads it and
turns the switch on. And even switched on, one night never opens more than
`pb_probation.trigger_cap`.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .probation_common import (
    GROUP_MANAGER, P_AUTO_TRIGGER, P_HOURLY_ALERTS, P_REMIND_FAR,
    P_REMIND_NEAR, P_TRIGGER_CAP, PROBATION_LIVE, REVIEW_OPEN, counted, flag,
    number,
)

_logger = logging.getLogger(__name__)


class PbJourneyCaseProbationAutomation(models.Model):
    _inherit = 'pb.journey.case'

    @api.model
    def _cron_lifecycle_reminders(self):
        counts = super()._cron_lifecycle_reminders() or {}
        if not isinstance(counts, dict):
            counts = {'base': counts}
        for key, fn in (('probation_reviews', self._trigger_probation_reviews),
                        ('probation_reminders', self._remind_probation_hr),
                        ('probation_consolidated',
                         self._consolidate_closed_windows),
                        ('probation_backfilled',
                         self._top_up_probation_states)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — one piece, one grave
                _logger.exception('pb_probation: %s failed', key)
                counts[key] = 0
        _logger.info(
            'pb_probation: %s review(s) opened, %s HR reminder(s), '
            '%s consolidated, %s trial state(s) filled in',
            counts.get('probation_reviews'),
            counts.get('probation_reminders'),
            counts.get('probation_consolidated'),
            counts.get('probation_backfilled'))
        return counts

    # ------------------------------------------------------- who is coming up
    @api.model
    def _due_for_review(self, today=None):
        """Everybody whose trial period is inside its lead time.

        Read once and used twice — by the trigger and by the count the log
        prints when the trigger is switched off — so the number an
        administrator reads is the number that would actually have happened.
        """
        today = today or fields.Date.today()
        Emp = self.env['hr.employee'].sudo()
        Review = self.env['pb.probation.review'].sudo()
        Policy = self.env['pb.probation.policy']
        # The widest lead time any policy uses, so nobody is missed by a
        # country-specific policy that starts earlier than the default.
        leads = [p.evaluation_lead_days for p
                 in Policy.sudo().search([('active', '=', True)])
                 if p.evaluation_lead_days > 0]
        horizon = today + timedelta(days=max(leads + [21]))
        people = Emp.search([
            ('pb_probation_state', 'in', list(PROBATION_LIVE)),
            ('trial_date_end', '!=', False),
            ('trial_date_end', '<=', horizon),
            ('active', '=', True),
        ])
        out = []
        for person in people:
            try:
                lead = Policy.settings_for(person)['evaluation_lead_days']
                if person.trial_date_end - timedelta(days=lead) > today:
                    continue
                if Review.search_count([('employee_id', '=', person.id),
                                        ('state', 'in', REVIEW_OPEN)]):
                    continue
                out.append(person)
            except Exception:           # noqa: BLE001
                _logger.exception('pb_probation: lead time for employee %s',
                                  person.id)
        return out

    @api.model
    def _trigger_probation_reviews(self, today=None):
        due = self._due_for_review(today)
        if not flag(self.env, P_AUTO_TRIGGER):
            _logger.info(
                'pb_probation: the automatic trigger is switched off. '
                '%s would have had a review opened tonight — turn '
                'pb_probation.auto_trigger on once that number looks right.',
                len(due))
            return 0
        cap = max(1, number(self.env, P_TRIGGER_CAP, 20))
        if len(due) > cap:
            _logger.warning(
                'pb_probation: %s trial periods are inside their lead time, '
                'which is over the cap of %s — the first %s are opened '
                'tonight and the rest tomorrow', len(due), cap, cap)
        Review = self.env['pb.probation.review'].sudo()
        made = 0
        for person in due[:cap]:
            try:
                review = Review.open_for(person, kind='probation')
                review.action_start_nomination()
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_probation: could not open a review for '
                                  'employee %s', person.id)
        return made

    # -------------------------------------------------------- the HR nudges
    @api.model
    def _remind_probation_hr(self, today=None):
        """Fifteen days out, and five. Idempotent — stamped per review.

        A SEARCH BEFORE CREATE on the activity as well as the stamp, because
        the two guards fail differently: the stamp survives an activity
        somebody deleted, and the search survives a review that was somehow
        re-created.
        """
        today = today or fields.Date.today()
        Review = self.env['pb.probation.review'].sudo()
        Activity = self.env['mail.activity'].sudo()
        far = max(1, number(self.env, P_REMIND_FAR, 15))
        near = max(1, number(self.env, P_REMIND_NEAR, 5))
        made = 0
        for days, field_name in ((far, 'remind_far_done'),
                                 (near, 'remind_near_done')):
            reviews = Review.search([
                ('state', 'in', REVIEW_OPEN),
                ('trial_end', '!=', False),
                ('trial_end', '<=', today + timedelta(days=days)),
                (field_name, '=', False),
            ])
            for review in reviews:
                try:
                    left = (review.trial_end - today).days
                    summary = _("Trial period ends in %(days)s days: %(who)s",
                                days=max(left, 0),
                                who=review.employee_id.name or '')
                    existing = Activity.search([
                        ('res_model', '=', 'pb.probation.review'),
                        ('res_id', '=', review.id),
                        ('summary', '=', summary)], limit=1)
                    if not existing:
                        review.activity_schedule(
                            act_type_xmlid='mail.mail_activity_data_todo',
                            summary=summary,
                            note=_("%(who)s's trial period ends on %(when)s "
                                   "and the review is at \"%(state)s\".",
                                   who=review.employee_id.name or '',
                                   when=review.trial_end,
                                   state=review.state_label()),
                            user_id=(review.hrbp_user_id
                                     or review.manager_user_id
                                     or self.env.user).id,
                            date_deadline=review.trial_end)
                    review.write({field_name: True})
                    made += 1
                except Exception:       # noqa: BLE001
                    _logger.exception('pb_probation: HR reminder for review '
                                      '%s', review.id)
        return made

    # --------------------------------------------------- windows that closed
    @api.model
    def _consolidate_closed_windows(self, today=None):
        """A colleague who never answers must not hold a decision up."""
        today = today or fields.Date.today()
        Review = self.env['pb.probation.review'].sudo()
        reviews = Review.search([
            ('state', '=', 'feedback'),
            ('feedback_deadline', '!=', False),
            ('feedback_deadline', '<', today),
        ])
        made = 0
        for review in reviews:
            try:
                if review.maybe_consolidate():
                    made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_probation: consolidating review %s',
                                  review.id)
        return made

    # ------------------------------------------------------- the top-up pass
    @api.model
    def _top_up_probation_states(self):
        """Anybody who arrived without a trial state gets one.

        R44's discipline: the parents that already exist have to be backfilled,
        and the backfill belongs in the daily job — which re-runs — rather than
        in a migration nobody re-runs. Idempotent by construction: it only ever
        touches rows that have no state at all.
        """
        counts = self.env['hr.employee']._pb_backfill_probation_state()
        return sum(counts.values())

    # ------------------------------------------------------------ on demand
    @api.model
    def run_probation_automation(self):
        """The same work, by hand. Managers only — it sends email."""
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only the HR team can run the probation steps by hand."))
        return {
            'reviews': self._trigger_probation_reviews(),
            'reminders': self._remind_probation_hr(),
            'consolidated': self._consolidate_closed_windows(),
            'alerts': self.env['pb.probation.review']._cron_deadline_alerts(),
        }


class PbProbationReviewAlerts(models.Model):
    """The hourly job, and the only thing it does.

    Deliberately its own cron and deliberately tiny. Everything else in this
    module rides P0's daily job; this cannot, because "two hours left" is only
    true for two hours.
    """
    _inherit = 'pb.probation.review'

    @api.model
    def _cron_deadline_alerts(self):
        """Tell the colleagues who have not answered that today is the day.

        ONCE per review, stamped on `deadline_alerted`, which is cleared again
        when a deadline is stretched — so a review whose window moved gets one
        alert on the new last day too, and never two on the same one.
        """
        if not flag(self.env, P_HOURLY_ALERTS):
            _logger.info('pb_probation: the last-hours alert is switched off')
            return 0
        today = fields.Date.today()
        reviews = self.sudo().search([
            ('state', '=', 'feedback'),
            ('feedback_deadline', '=', today),
            ('deadline_alerted', '=', False),
        ])
        made = 0
        for review in reviews:
            try:
                pending = review.pending_respondents()
                if not pending:
                    # Everybody answered; nothing to chase, and stamping it
                    # stops tomorrow's run looking again.
                    review.write({'deadline_alerted': True})
                    continue
                sent = review._mail(
                    'pb_probation.mail_template_deadline_today',
                    pending + review._manager_addresses())
                review.write({'deadline_alerted': True})
                if sent:
                    made += 1
                    review.message_post(body=_(
                        "%s still to answer, and the window closes today — "
                        "they have been reminded.",
                        counted(len(pending), _('colleague is'),
                                _('colleagues are'))))
            except Exception:           # noqa: BLE001
                _logger.exception('pb_probation: last-hours alert for review '
                                  '%s', review.id)
        _logger.info('pb_probation: %s last-hours alert(s)', made)
        return made
