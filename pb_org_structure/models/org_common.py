# -*- coding: utf-8 -*-
"""Shared words and rights for the Organisation tab (S8-C).

Who does what (least access):

* READ the Jobs tab — HR officers (`hr.group_hr_user`), the talent lead and
  administrators.
* CHANGE jobs, levels and cost centres — HR managers (`hr.group_hr_manager`)
  and administrators.
* PAUSE or restart hiring — the talent lead (`pb_hiring.group_hiring_manager`,
  which the Head of hiring implies), HR managers and administrators.
* WOULD REHIRE — HR managers / the exits team who may change an exit; never a
  line manager, never an agency.

Every facade method checks its own gate first and then reads or writes under
sudo (W2B-2: the person may hold no read on `hr.contract`).
"""
from odoo import _
from odoo.exceptions import AccessError

GROUP_HR_USER = 'hr.group_hr_user'
GROUP_HR_MANAGER = 'hr.group_hr_manager'
GROUP_HIRING_LEAD = 'pb_hiring.group_hiring_manager'

#: Payslips in these states are still being worked on: their lines follow the
#: contract's cost centre. Every other state is history and is never
#: rewritten (see `hr_contract.py`).
DRAFT_SLIP_STATES = ('draft', 'verify')

REHIRE = [
    ('yes', 'Yes'),
    ('no', 'No'),
    ('unsure', 'Not sure'),
]


def has(user, *groups):
    if user._is_admin() or user._is_superuser():
        return True
    for group in groups:
        try:
            if user.has_group(group):
                return True
        except (ValueError, KeyError):
            continue
    return False


def can_read(env):
    return has(env.user, GROUP_HR_USER, GROUP_HR_MANAGER, GROUP_HIRING_LEAD,
               'base.group_system')


def can_manage(env):
    return has(env.user, GROUP_HR_MANAGER, 'base.group_system')


def can_pause(env):
    return has(env.user, GROUP_HIRING_LEAD, GROUP_HR_MANAGER,
               'base.group_system')


def require_read(env):
    if not can_read(env):
        raise AccessError(_(
            "Jobs and cost centres are looked after by the HR team. Ask them "
            "if you need something changed."))


def require_manage(env):
    if not can_manage(env):
        raise AccessError(_(
            "Changing jobs, levels and cost centres is for HR managers. Ask "
            "one of them to make the change."))


def require_pause(env):
    if not can_pause(env):
        raise AccessError(_(
            "Pausing or restarting hiring is for the talent lead and HR "
            "managers."))
