# -*- coding: utf-8 -*-
"""WHERE AN EMPLOYEE LANDS (owner ruling 2026-10-04).

An employee whose work is neither payroll nor hiring was greeted, after
sign-in, by the company-wide payroll command centre ("Get your first payroll
out", "Run Payroll"). Their own world is the My Payobook hub at `/my` —
payslips, profile, time off, schedule, goals, training, My buddy.

"Employee only" is asked of the same rules the left menu uses, so the landing
and the menu can never disagree:

  * an EMPLOYEE LOGIN — a portal (share) account with an employee record
    (TIERS T2) — is employee-only without further questions; otherwise
  * an internal user with an employee record,
  * the Pay Run entry is NOT on their left menu (the sidebar's `_state_for`),
  * the Hiring board does not admit them (pb_hiring lands those on Hiring).

Four effects, all for that one person and nobody else:

  1. sign-in with no explicit destination goes to `/my`
     (`controllers/ess_landing.py`);
  2. the app's first screen is Home, not the payroll command centre;
  3. Home drops its Pulse tab and opens on Approvals (`ess_home.js`);
  4. THE FENCE (TIERS T1, 2026-10-15) — for the narrower "portal only"
     person (`_pb_portal_only()`), the backend itself is out of reach: the
     web-client routes and `/` bounce to `/my` (`controllers/ess_landing.py`),
     and the two frontend links into it are not rendered — the account
     menu's "Apps" entry (`views/portal_templates.xml`) and the website's
     fixed corner shortcut (glue module `pb_me_portal_website`).

"Portal only" is "employee only" MINUS anybody whose work still lives on the
backend until TIERS T3 (ledger T-R8): a person with an active role
assignment, with a direct report, or with an approval seat waiting on them.
Team leads keep the backend.

For an INTERNAL account this is a fence, not a wall (ledger T8): the person
keeps every `base.group_user` ACL and the JSON-RPC endpoints; only the doors
are shut. The wall is the EMPLOYEE LOGIN (TIERS T2): a share account that
holds no backend group at all, which is portal-only by construction. Every
`/my` page serves it through `sudo()` after an own-employee guard (ledger
T-R11; `controllers/portal.py`). The rule fails OPEN (T-R2):
any error logs a warning and answers False, so a bug can never lock somebody
out of their work.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

PAY_RUN_ITEM = 'pb_payhub.item_pay_run'
HOME_HUB = 'pb_home_hub.action_pb_home_hub'
# Direct groups that are NOT a backend permission (TIERS T2b, ledger T22):
# multi-company only widens what a person may see of their own world, and the
# field check-in groups' only screen is `/driver`, a portal-style page.
HARMLESS_GROUPS = (
    'base.group_multi_company',
    'pb_driver_checkin.group_pb_driver',
    'pb_driver_checkin.group_pb_field_staff',
)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _pb_employee_only(self):
        """Is this person an employee whose own world is My Payobook?

        True for

          * an EMPLOYEE LOGIN (TIERS T2): a portal/share account with an
            employee record (`hr.employee.user_id`, ledger T-R10) — it has no
            backend at all, so it is an employee, full stop;
          * an internal account with an employee record whose left menu does
            not carry Pay Run and whom the Hiring board does not admit.

        Never for the public user, an administrator, or anybody without an
        employee record (an agency or vendor portal login is not an employee).
        """
        self.ensure_one()
        user = self.sudo()
        if user._is_public() or user._is_admin() or user._is_system():
            return False
        # Searched, not `user.employee_ids`: that follows the companies of the
        # moment, and at sign-in (or in a job) those need not include the one
        # the person is employed in.
        if not self.env['hr.employee'].sudo().search_count(
                [('user_id', '=', user.id)], limit=1):
            return False
        if user.share:
            return True
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

    # ------------------------------------------------------------ the fence
    def _pb_portal_only(self):
        """Is this person kept out of the backend (TIERS T1, ledger T-R1)?

        The ONE rule every door asks: the web-client routes, `/`, the account
        menu's Apps link and the website's corner shortcut. True only for an
        employee-only person (`_pb_employee_only()`) who also

          * holds no active role assignment (`_pb_holds_role`),
          * holds no backend permission given by hand (`_pb_holds_backend_group`,
            TIERS T2b, ledger T22),
          * manages nobody (`_pb_has_reports`), and
          * has no approval seat waiting on them (`_pb_has_open_seat`)

        — team leads, approvers and anyone an administrator deliberately gave a
        permission keep the backend until TIERS T3 brings approvals to the
        portal (ledger T-R8). Those exclusions are for INTERNAL users only: an
        employee login (a share user, TIERS T2) has no backend to keep and
        cannot hold a role (biz_access `_check_safe`), so it is portal-only by
        construction.

        Fails OPEN (ledger T-R2): any error logs a warning with the trace and
        answers False. Templates call this, so it must never raise.
        """
        try:
            self.ensure_one()
            if not self._pb_employee_only():
                return False
            if self.sudo().share:
                return True
            return bool(not self._pb_holds_role()
                        and not self._pb_holds_backend_group()
                        and not self._pb_has_reports()
                        and not self._pb_has_open_seat())
        except Exception:               # noqa: BLE001
            _logger.warning('pb_me_portal: could not decide whether user(s) '
                            '%s are portal-only; leaving the backend open',
                            self.ids, exc_info=True)
            return False

    def _pb_holds_role(self):
        """An active role assignment (biz_access, soft: not a dependency)."""
        if 'pb.role.assignment' not in self.env:
            return False
        return bool(self.env['pb.role.assignment'].sudo().search_count(
            [('user_id', '=', self.id), ('active', '=', True)], limit=1))

    def _pb_holds_backend_group(self):
        """A permission given by hand (TIERS T2b, ledger T22).

        Roles (biz_access) are not the only way somebody gets a backend
        permission: an administrator can tick a group on the person's record.
        An HR manager without payroll, a budget viewer, an access manager with
        a direct group all have an employee record and no role, and T1 fenced
        them. So: any DIRECT group outside `base.group_user`'s implied closure
        keeps the backend, except the harmless ones in `HARMLESS_GROUPS`
        (multi-company, and the field check-in groups whose only screen is
        `/driver`). The landing rule `_pb_employee_only` is deliberately NOT
        changed by this — where somebody lands and what they may open are two
        different questions.
        """
        user = self.sudo()
        base_user = self.env.ref('base.group_user', raise_if_not_found=False)
        if not base_user:
            return False
        closure = base_user | base_user.all_implied_ids
        harmless = self.env['res.groups']
        for xmlid in HARMLESS_GROUPS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                harmless |= group
        return bool(user.group_ids - closure - harmless)

    def _pb_has_reports(self):
        """Somebody's manager: an active employee whose manager is this user."""
        return bool(self.env['hr.employee'].sudo().search_count(
            [('parent_id.user_id', '=', self.id)], limit=1))

    def _pb_has_open_seat(self):
        """An approval seat that is theirs, or theirs to decide, still open."""
        return bool(self.env['biz.approval.request.seat'].sudo().search_count(
            ['|', ('acting_user_id', '=', self.id), ('user_id', '=', self.id),
             ('status', '=', 'open')], limit=1))


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
                # TIERS T1: harmless today; T2/T3 read it.
                if user._pb_portal_only():
                    info['pb_portal_only'] = True
        except Exception:               # noqa: BLE001
            _logger.warning('pb_me_portal: could not choose the first screen '
                            'for user %s', user.id, exc_info=True)
        return info
