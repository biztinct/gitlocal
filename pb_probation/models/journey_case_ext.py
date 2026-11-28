# -*- coding: utf-8 -*-
"""What else happens the moment a JOINING checklist opens.

Two things — the trial end date and the training rows — and both obey the three
rules P2 wrote down when it bolted asset steps onto an exit, P3 repeated when it
bolted five onto an arrival and P4 repeated again:

  1. **Super first, always.** This is an addition to what P0 and P3 did, never
     a replacement.
  2. **It never raises.** A checklist that opens is the important thing. A
     trial end date that could not be worked out is a dash in one column; a
     joiner with no checklist at all is a laptop nobody asks for.
  3. **It is idempotent (R30).** The same case reaches this code more than once
     — `action_open()` and the connected system's `_after_onboard` both lead
     here — and both must leave the same one date and the same rows behind.

THE DATE IS ONLY EVER FILLED IN WHEN IT IS EMPTY. A trial end somebody typed on
a contract by hand beats a policy every time: they knew something the policy did
not, and overwriting it on every re-open is how a date quietly stops meaning
anything.
"""

import logging

from odoo import _, models

from .probation_common import counted

_logger = logging.getLogger(__name__)


class PbJourneyCaseProbation(models.Model):
    _inherit = 'pb.journey.case'

    def action_open(self):
        res = super().action_open()
        for rec in self:
            if rec.case_type != 'onboarding':
                continue
            try:
                rec.setup_probation()
            except Exception:           # noqa: BLE001 — rule 2
                _logger.exception(
                    'pb_probation: could not set up the trial period for '
                    'journey %s', rec.id)
        return res

    def setup_probation(self):
        """The trial end date and the training rows. Both idempotent."""
        self.ensure_one()
        done = {}
        for name, fn in (('trial_end', self._set_trial_end),
                         ('training', self._plan_training)):
            try:
                done[name] = fn()
            except Exception:           # noqa: BLE001
                _logger.exception('pb_probation: %s failed for journey %s',
                                  name, self.id)
                done[name] = False
        return done

    def _set_trial_end(self):
        """Joining date plus the policy's duration — only if it is unset."""
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return False
        Policy = self.env['pb.probation.policy']
        settings = Policy.settings_for(emp)
        if not settings['policy_id']:
            # No policy covers this person's country. The parameters still give
            # a duration, and using it silently would put a date on a contract
            # nobody chose — so the journey says so and leaves the date alone.
            self.message_post(body=_(
                "No probation policy covers this person yet, so no trial end "
                "date was filled in. Add one and the next joiner is handled "
                "automatically."))
            return False
        existing = False
        try:
            existing = emp.sudo().trial_date_end
        except Exception:               # noqa: BLE001
            existing = False
        if existing:
            # A date already there wins, and the state is brought into line
            # with it rather than left behind.
            if existing >= self._joining_date() and not emp._pb_in_probation():
                emp._pb_set_probation_state('in_probation')
            return existing
        joined = self.anchor_date or self._joining_date()
        end = Policy.trial_end_for(emp, joined_on=joined)
        if not end:
            return False
        emp.pb_set_trial_end(end, note=_(
            "The trial period runs for %(count)s from %(start)s under "
            "%(policy)s, so it ends on %(end)s.",
            count=counted(settings['duration_months'], _('month'),
                          _('months')),
            start=joined, policy=settings['policy_name'] or _('the policy'),
            end=end))
        emp._pb_set_probation_state('in_probation')
        self.message_post(body=_(
            "Their trial period ends on %s.", end))
        return end

    def _plan_training(self):
        """Any course this person's job requires. Idempotent on the item."""
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return 0
        made = self.env['pb.training.track'].ensure_for_employee(emp)
        if made:
            self.message_post(body=_(
                "%s to finish before their trial period can be passed.",
                counted(made, _('One course item'), _('course items'))))
        return made


class PbJourneyTaskProbation(models.Model):
    """One more key the daily job knows how to run.

    A joining checklist may carry a step that says "start the probation
    review", dated at the lead time. When it falls due the step opens the
    review and asks the manager for colleagues — which is the same thing the
    trigger does, reached from the other direction, and both are idempotent so
    a checklist that has the step and a database that has the trigger switched
    on produce exactly one review.
    """
    _inherit = 'pb.journey.task'

    def _automation_handlers(self):
        handlers = super()._automation_handlers()
        handlers['probation_review'] = '_auto_probation_review'
        return handlers

    def _auto_probation_review(self):
        self.ensure_one()
        emp = self._employee()
        if not emp:
            return False
        if not emp._pb_in_probation():
            _logger.info('pb_probation: %s is not in a trial period — step %s '
                         'left alone', emp.name, self.id)
            return False
        review = self.env['pb.probation.review'].sudo().open_for(
            emp, kind='probation', case=self.case_id)
        review.action_start_nomination()
        return _('The probation review is open and the manager has been '
                 'asked for colleagues.')
