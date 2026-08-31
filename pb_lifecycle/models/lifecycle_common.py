# -*- coding: utf-8 -*-
"""The vocabulary every lifecycle model shares.

One module, one copy. A selection list restated in two files is two lists the
day one of them grows a value, and the screens then disagree about what a
journey IS — which is the whole point of the engine.
"""

CASE_TYPES = [
    ('onboarding', 'Onboarding'),
    ('offboarding', 'Offboarding'),
    ('probation', 'Probation'),
    ('pip', 'Performance improvement'),
    ('conversion', 'Conversion'),
    ('other', 'Other'),
]

#: What a step's offset counts from. `case_open` is the only anchor that needs
#: no date on the case, which is why it is the default: a journey opened with
#: nothing else known still produces a working checklist.
ANCHORS = [
    ('case_open', 'When the journey opens'),
    ('doj', 'Joining date'),
    ('lwd', 'Last working day'),
    ('probation_end', 'Probation end'),
]

#: WHO owns a step, as a rule rather than a person. Resolved once, when the
#: journey opens — see `pb.journey.case._resolve_assignee`.
ASSIGNEE_RULES = [
    ('hr', 'HR'),
    ('hrbp', 'HRBP'),
    ('manager', 'Manager'),
    ('buddy', 'Buddy'),
    ('it', 'IT'),
    ('finance', 'Finance'),
    ('admin', 'Admin'),
    ('employee', 'The employee'),
    ('candidate', 'The joiner (before day one)'),
    ('user', 'Specific person'),
]

STEP_KINDS = [
    ('task', 'Task'),
    ('confirmation', 'Confirmation'),
    ('form', 'Form'),
    ('email', 'Automatic email'),
    ('letter', 'Letter'),
]

TASK_STATES = [
    ('pending', 'To do'),
    ('in_progress', 'In progress'),
    ('blocked', 'Blocked'),
    ('done', 'Done'),
    ('skipped', 'Skipped'),
]

CASE_STATES = [
    ('draft', 'Draft'),
    ('active', 'Running'),
    ('on_hold', 'On hold'),
    ('done', 'Finished'),
    ('cancelled', 'Cancelled'),
]

LETTER_TYPES = [
    ('experience', 'Experience letter'),
    ('probation_pass', 'Probation passed'),
    ('probation_extend', 'Probation extended'),
    ('probation_fail', 'Probation not passed'),
    ('incentive', 'Incentive letter'),
    ('ff_cover', 'Final settlement cover'),
    ('pip', 'PIP letter'),
    ('custom', 'Custom'),
]

#: A task carries a link only when somebody without a login has to answer it.
TOKEN_KINDS = ('confirmation', 'form')

CASE_TYPE_LABEL = dict(CASE_TYPES)
STEP_KIND_LABEL = dict(STEP_KINDS)
TASK_STATE_LABEL = dict(TASK_STATES)
CASE_STATE_LABEL = dict(CASE_STATES)
ASSIGNEE_RULE_LABEL = dict(ASSIGNEE_RULES)
LETTER_TYPE_LABEL = dict(LETTER_TYPES)

#: The group ladder, by xmlid, so a facade never spells one twice.
GROUP_USER = 'pb_lifecycle.group_lifecycle_user'
GROUP_MANAGER = 'pb_lifecycle.group_lifecycle_manager'
GROUP_ADMIN = 'pb_lifecycle.group_lifecycle_admin'

#: Config parameters. Every one of them has a working default; none of them has
#: to be set for the module to behave.
PARAM_REMINDERS_ON = 'pb_lifecycle.reminders_enabled'
PARAM_REMIND_DAYS = 'pb_lifecycle.remind_days'
DEFAULT_REMIND_DAYS = 2
