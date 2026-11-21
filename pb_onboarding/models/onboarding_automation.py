# -*- coding: utf-8 -*-
"""One more thing for the daily job to do.

P0 ships ONE cron for the whole lifecycle and every phase adds to it rather
than adding a second one — two jobs on the same table is two jobs that can
disagree about what "today" means. So this extends
`_cron_lifecycle_reminders()` instead of registering a new `ir.cron`.

WHAT IT ADDS, in order:

  * the steps that run themselves, for every joining checklist that is running;
  * the three one-tap checks, planned for any journey that opened before this
    module existed, and sent when they fall due.

DELIBERATELY NOT BEHIND `reminders_enabled`. That switch silences NUDGES — the
"your step is due" mail. These are the steps THEMSELVES: a deployment that
turned reminders off to stop being emailed about overdue tasks did not thereby
ask for its joiners to be left without a password. Each of these has its own
parameter instead, and the log says which one stopped it.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .onboarding_common import GROUP_MANAGER, P_AUTO_STEPS, flag

_logger = logging.getLogger(__name__)

_OPEN = ('pending', 'in_progress', 'blocked')

#: A ceiling on one run. Past it the rest wait for tomorrow — a backlog worked
#: through over three nights is a backlog; four thousand messages in one minute
#: is an incident.
_RUN_CAP = 300


class PbJourneyCaseAutomation(models.Model):
    _inherit = 'pb.journey.case'

    @api.model
    def _cron_lifecycle_reminders(self):
        counts = super()._cron_lifecycle_reminders() or {}
        if not isinstance(counts, dict):
            counts = {'base': counts}
        for key, fn in (('auto_steps', self._run_auto_steps),
                        ('pulses_planned', self._plan_missing_pulses),
                        ('pulses_sent', self._send_due_pulses)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — one piece, one grave
                _logger.exception('pb_onboarding: %s failed', key)
                counts[key] = 0
        _logger.info(
            'pb_onboarding: %s step(s) ran themselves, %s check(s) planned, '
            '%s check(s) sent',
            counts.get('auto_steps'), counts.get('pulses_planned'),
            counts.get('pulses_sent'))
        return counts

    # -------------------------------------------------------------- the parts
    @api.model
    def _run_auto_steps(self, today=None):
        """Every open step that is due and knows how to do itself."""
        if not flag(self.env, P_AUTO_STEPS):
            _logger.info('pb_onboarding: automatic steps are switched off')
            return 0
        today = today or fields.Date.today()
        Task = self.env['pb.journey.task'].sudo()
        due = Task.search([
            ('state', 'in', _OPEN),
            ('due_date', '!=', False),
            ('due_date', '<=', today),
            ('case_id.state', '=', 'active'),
            '|', ('automation_key', '!=', False),
            ('step_kind', '=', 'email'),
        ], order='due_date, id', limit=_RUN_CAP)
        ran = 0
        for task in due:
            try:
                if task.action_auto():
                    ran += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_onboarding: step %s', task.id)
        return ran

    @api.model
    def _plan_missing_pulses(self):
        """Checks for the joining checklists that opened before we existed."""
        Pulse = self.env['pb.newhire.pulse'].sudo()
        cases = self.sudo().search([
            ('case_type', '=', 'onboarding'),
            ('state', 'in', ('active', 'on_hold')),
        ], limit=_RUN_CAP)
        made = 0
        for case in cases:
            try:
                before = Pulse.search_count([('case_id', '=', case.id)])
                Pulse.ensure_for_case(case)
                after = Pulse.search_count([('case_id', '=', case.id)])
                made += max(0, after - before)
            except Exception:           # noqa: BLE001
                _logger.exception('pb_onboarding: planning checks for case %s',
                                  case.id)
        return made

    @api.model
    def _send_due_pulses(self):
        return self.env['pb.newhire.pulse']._cron_send_due()

    # ---------------------------------------------------------- on demand
    @api.model
    def run_onboarding_automation(self):
        """The same work, by hand. Managers only — it sends email."""
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only the HR team can run the joining steps by hand."))
        return {
            'auto_steps': self._run_auto_steps(),
            'pulses_planned': self._plan_missing_pulses(),
            'pulses_sent': self._send_due_pulses(),
        }
