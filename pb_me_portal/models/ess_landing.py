# -*- coding: utf-8 -*-
"""WHERE AN EMPLOYEE LANDS (owner ruling 2026-10-04).

An employee whose work is neither payroll nor hiring was greeted, after
sign-in, by the company-wide payroll command centre ("Get your first payroll
out", "Run Payroll"). Their own world is the My Payobook hub at `/my` —
payslips, profile, time off, schedule, goals, training, My buddy.

"Employee only" is asked of the same rules the left menu uses, so the landing
and the menu can never disagree:

  * an internal user with an employee record,
  * the Pay Run entry is NOT on their left menu (the sidebar's `_state_for`),
  * the Hiring board does not admit them (pb_hiring lands those on Hiring).

Three effects, all for that one person and nobody else:

  1. sign-in with no explicit destination goes to `/my`
     (`controllers/ess_landing.py`);
  2. the app's first screen is Home, not the payroll command centre;
  3. Home drops its Pulse tab and opens on Approvals (`ess_home.js`).
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

PAY_RUN_ITEM = 'pb_payhub.item_pay_run'
HOME_HUB = 'pb_home_hub.action_pb_home_hub'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _pb_employee_only(self):
        self.ensure_one()
        user = self.sudo()
        if not user._is_internal() or user._is_admin() or user._is_system():
            return False
        # Searched, not `user.employee_ids`: that follows the companies of the
        # moment, and at sign-in (or in a job) those need not include the one
        # the person is employed in.
        if not self.env['hr.employee'].sudo().search_count(
                [('user_id', '=', user.id)], limit=1):
            return False
        Item = self.env['pb.sidebar.item'].sudo()
        pay = self.env.ref(PAY_RUN_ITEM, raise_if_not_found=False)
        if pay:
            is_admin, groups = Item._access_of(user)
            visible, _locked = Item._state_for(pay, is_admin, groups)
            if visible:
                return False
        if 'pb.hiring' in self.env and \
                self.env['pb.hiring'].with_user(user).can_open():
            return False
        return True


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        user = self.env.user
        if not info.get('uid') or not user._is_internal():
            return info
        try:
            if user._pb_employee_only():
                home = self.env.ref(HOME_HUB, raise_if_not_found=False)
                if home:
                    info['home_action_id'] = home.id
                info['pb_employee_only'] = True
        except Exception:               # noqa: BLE001
            _logger.warning('pb_me_portal: could not choose the first screen '
                            'for user %s', user.id, exc_info=True)
        return info
