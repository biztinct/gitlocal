# -*- coding: utf-8 -*-
"""WORKFLOW-2 P6a (owner decision D31, the next areas): training assignments
declare their own due-date timetable.

Workflow Studio can start a workflow around a date on a record ("At a record
date", or on a schedule for each record). Training already chases its own due
dates on its daily job (`automation._chase_one`): the person 3 days, 1 day and
on the day before a course is due and every 3 days while it is late; their
manager once it is late by the manager setting, then weekly; the HR lead once
it is late by the HR setting, then weekly. This file only SAYS so, in the
duck-typed contract Studio reads (`_workflow_effects(company)`), so Studio can
list it under "Already happens" and warn a designer before a workflow repeats
it. Nothing here changes what the reminders do, when, or to whom.

Read from the area's real settings, never copied numbers:
  * `pb_training.reminders`              — whether the chase runs at all;
  * `pb_training.manager_escalate_days`  — days late before the manager;
  * `pb_training.hr_escalate_days`       — days late before the HR lead.
The person's own 3 / 1 / 0 days and "every 3 days late" are fixed in the
chase itself (no setting exists), so they are named as the chase uses them.

Method-only, restart-loaded (no version bump, ledger G29). No local is called
`user` or `uid` in a method that calls `_()` (ledger G12).
"""

from odoo import api, models, _

from .training_common import P_HR_DAYS, P_MANAGER_DAYS, P_REMINDERS, flag, number

#: The person's own reminders before the due date (`automation._chase_one`:
#: keys d3 / d1 / d0) and how often while it is late (od…, every 3 days).
BEFORE_DAYS = 3
LATE_EVERY = 3


class TrainingAssignmentWorkflowTimetable(models.Model):
    _inherit = 'pb.training.assignment'

    @api.model
    def _workflow_effects(self, company):
        rows = list(super()._workflow_effects(company) or []) if hasattr(super(), '_workflow_effects') else []
        on = flag(self.env, P_REMINDERS)
        manager_days = max(number(self.env, P_MANAGER_DAYS, 2), 0)
        hr_days = max(number(self.env, P_HR_DAYS, 5), 0)
        owner = _('Training')
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'requester', 'owner': owner,
            'text': (_('%(before)s days and 1 day before a course is due, and on the day, the person gets a '
                       'reminder email; while it is late, every %(every)s days.', before=BEFORE_DAYS, every=LATE_EVERY)
                     if on else
                     _('%(before)s days and 1 day before a course is due, and on the day, the person can get a '
                       'reminder email; while it is late, every %(every)s days (the reminders are switched off here).',
                       before=BEFORE_DAYS, every=LATE_EVERY)),
            # What Studio compares a date-based workflow with (D31): before
            # the date, and from the day after it while it is late.
            'timing': {'field': 'due_date', 'before_days': BEFORE_DAYS, 'after_days': 1, 'active': on},
        })
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'manager', 'owner': owner,
            'text': (_('When a course is %s days late, the person’s manager is told, then once a week.', manager_days)
                     if on else
                     _('When a course is %s days late, the person’s manager can be told, then once a week '
                       '(the reminders are switched off here).', manager_days)),
            'timing': {'field': 'due_date', 'after_days': manager_days, 'active': on},
        })
        rows.append({
            'stage': None, 'kind': 'reminder', 'audience': 'hr', 'owner': owner,
            'text': (_('When a course is %s days late, the HR lead is told, then once a week.', hr_days)
                     if on else
                     _('When a course is %s days late, the HR lead can be told, then once a week '
                       '(the reminders are switched off here).', hr_days)),
            'timing': {'field': 'due_date', 'after_days': hr_days, 'active': on},
        })
        return rows
