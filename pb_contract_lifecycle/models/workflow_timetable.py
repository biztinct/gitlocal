# -*- coding: utf-8 -*-
"""WORKFLOW-2 P5c (owner decision D31): contracts declare their own timetable.

Workflow Studio can start a workflow around a date on a record ("At a record
date", or on a schedule). Contracts already chase their own end date on the
lifecycle's daily job (`contract_automation.py`); this file only SAYS so, in
the duck-typed contract Studio reads (`_workflow_effects(company)`), so Studio
can list it under "Already happens" and warn a designer before a workflow
repeats it. Nothing here changes what the reminders do, when, or to whom.

Read from the area's real settings, never copied numbers:
  * `pb_contract_lifecycle.lead_days`     — how early a decision is raised;
  * `pb_contract_lifecycle.auto_trigger`  — whether it is raised by itself;
  * `pb_contract_lifecycle.nag_days`      — the daily last-week nudge.

Method-only, restart-loaded (no version bump, ledger G29). No local is called
`user` or `uid` in a method that calls `_()` (ledger G12).
"""

from odoo import api, models, _

from .contract_common import P_AUTO_TRIGGER, P_LEAD_DAYS, P_NAG_DAYS, flag, number


class HrContractWorkflowTimetable(models.Model):
    _inherit = 'hr.contract'

    @api.model
    def _workflow_effects(self, company):
        rows = list(super()._workflow_effects(company) or []) if hasattr(super(), '_workflow_effects') else []
        lead = max(1, number(self.env, P_LEAD_DAYS, 60))
        nag = max(1, number(self.env, P_NAG_DAYS, 7))
        auto = flag(self.env, P_AUTO_TRIGGER)
        settings = {'action': 'pb_contract_lifecycle.action_pb_contractlife'}
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'manager', 'owner': _('Contracts'),
            'text': (_('%s days before a contract ends, its manager is asked to decide what happens next.', lead)
                     if auto else
                     _('%s days before a contract ends, its manager can be asked to decide what happens next '
                       '(raising these by itself is switched off here).', lead)),
            'settings': settings,
            # What Studio compares a date-based workflow with (D31).
            'timing': {'field': 'date_end', 'before_days': lead, 'active': auto},
        })
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'hr', 'owner': _('Contracts'),
            'text': _('While a contract decision is still open, HR is told halfway to the end date, '
                      'and every day in the last %s days.', nag),
            'settings': settings,
            'timing': {'field': 'date_end', 'before_days': max(nag, lead // 2), 'active': True},
        })
        return rows
