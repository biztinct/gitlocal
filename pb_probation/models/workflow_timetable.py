# -*- coding: utf-8 -*-
"""WORKFLOW-2 P5c (owner decision D31): trial periods declare their timetable.

The lifecycle's daily job already works towards the end of a trial period
(`probation_automation.py`): it opens a review some days before the end (only
while `pb_probation.auto_trigger` is on) and gives HR a to-do fifteen and five
days before. This file only SAYS so, in the duck-typed contract Workflow Studio
reads for employees (`_workflow_effects(company)`), so a workflow started
around "Trial period end" is warned before it repeats it. Nothing here changes
the reminders.

Read from the area's real settings (`pb_probation.evaluation_lead_days`,
`pb_probation.remind_days_far` / `_near`, `pb_probation.auto_trigger`), never
copied numbers. Method-only, restart-loaded (ledger G29); no local named
`user`/`uid` in a method that calls `_()` (G12).
"""

from odoo import api, models, _

from .probation_common import P_AUTO_TRIGGER, P_LEAD_DAYS, P_REMIND_FAR, P_REMIND_NEAR, flag, number


class HrEmployeeWorkflowTimetable(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _workflow_effects(self, company):
        rows = list(super()._workflow_effects(company) or []) if hasattr(super(), '_workflow_effects') else []
        lead = max(1, number(self.env, P_LEAD_DAYS, 21))
        far = max(1, number(self.env, P_REMIND_FAR, 15))
        near = max(1, number(self.env, P_REMIND_NEAR, 5))
        auto = flag(self.env, P_AUTO_TRIGGER)
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'manager', 'owner': _('Trial periods'),
            'text': (_('%s days before a trial period ends, a review opens and the manager is asked to choose '
                       'who gives feedback.', lead) if auto else
                     _('%s days before a trial period ends, a review can open for the manager '
                       '(opening these by itself is switched off here).', lead)),
            'timing': {'field': 'trial_date_end', 'before_days': lead, 'active': auto},
        })
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'hr', 'owner': _('Trial periods'),
            'text': _('While a trial-period review is open, HR (or else the manager) gets a to-do %(far)s days and '
                      'again %(near)s days before the trial period ends.', far=far, near=near),
            'timing': {'field': 'trial_date_end', 'before_days': max(far, near), 'active': True},
        })
        return rows
