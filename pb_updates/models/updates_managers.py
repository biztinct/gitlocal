# -*- coding: utf-8 -*-
"""UPDATES P3a (D12) — a manager whose login is employee self-service only.

Owner decision D12: a person who has only an employee self-service (portal)
login CAN be named as somebody's manager or coach. They are recorded as the
manager; their login is not changed and they get no extra screens.

WHERE IT FAILED. Not in Payobook's own code: in the stock time-off module.
`hr_holidays` makes the new manager's LOGIN the person's time-off approver
whenever the manager changes (`hr.employee.write`: `parent_id` →
`leave_manager_id`, hr_holidays/models/hr_employee.py:208-218), and making a
login a time-off approver adds it to "Time Off / Responsible"
(:221-227, `group_hr_holidays_responsible`), which implies the staff
"Role / User". A self-service login cannot be both portal and staff, so the
whole write was refused ("cannot be at the same time in Role / Portal and
Role / User") — from Updates, the Records screen and the employee form alike.
The org chart already side-steps it the same way (`pb_orgchart_write.py`,
FOLLOWERS, ledger G16 there).

WHAT CHANGES. When the new manager's login is self-service only, the person's
time-off approver and expense approver keep the value they have, written in
the SAME write (which protects them from the stock recompute). Nothing is
bypassed: the guard that stops a portal login receiving staff groups is never
touched — the grant is simply not asked for. A staff manager is handled
exactly as before.

APPROVALS. An approval step "their manager" (or "their manager's manager")
that lands on such a login falls back the way the engine already does for a
manager with no login at all: the step stops with "No manager is recorded…"
and can be moved to somebody. Only a self-service login is left out; a staff
manager is asked as before (test F12).
"""
from odoo import _, api, models

#: Approver fields the stock employee record moves to the new manager's login.
FOLLOWERS = ('leave_manager_id', 'expense_manager_id')


class HrEmployeePortalManager(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _pb_portal_manager_login(self, manager_id):
        """The manager's login when it is self-service only, else False."""
        if not manager_id:
            return False
        manager = self.env['hr.employee'].sudo().browse(int(manager_id)).exists()
        user = manager.user_id
        return user if user and user.share else False

    def _pb_followers_present(self):
        return [f for f in FOLLOWERS if f in self._fields]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            portal_manager = bool(vals.get('parent_id')) and bool(
                self._pb_portal_manager_login(vals['parent_id']))
            for name in self._pb_followers_present():
                if name in vals and self._pb_is_portal_user(vals[name]) \
                        and (name == 'leave_manager_id' or portal_manager):
                    vals[name] = False
                elif portal_manager:
                    vals.setdefault(name, False)
        return super().create(vals_list)

    @api.model
    def _pb_is_portal_user(self, user_id):
        if not user_id:
            return False
        user = self.env['res.users'].sudo().browse(int(user_id)).exists()
        return bool(user and user.share)

    def write(self, vals):
        followers = self._pb_followers_present()
        if not followers:
            return super().write(vals)
        # A follower sent with a self-service login (the employee form's own
        # recompute after the manager changed) is never accepted: it would
        # only fail, or hand approval to a login that cannot approve.
        portal_manager = bool(vals.get('parent_id')) and bool(
            self._pb_portal_manager_login(vals['parent_id']))
        sent_portal = [f for f in followers
                       if f in vals and self._pb_is_portal_user(vals[f])
                       and (f == 'leave_manager_id' or portal_manager)]
        keep = list(sent_portal)
        if portal_manager:
            keep += [f for f in followers if f not in vals]
        if not keep:
            return super().write(vals)
        base = {k: v for k, v in vals.items() if k not in sent_portal}
        # Keep each person's approvers as they are, in the same write.
        groups = {}
        for employee in self.sudo():
            key = tuple((f, employee[f].id or False) for f in keep)
            groups.setdefault(key, []).append(employee.id)
        result = True
        for key, ids in groups.items():
            result = super(HrEmployeePortalManager, self.browse(ids)).write(
                dict(base, **dict(key))) and result
        return result


class BizApprovalEnginePortalManagers(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    def _resolve_step_people(self, step, ctx, company, on_date, record=None):
        people, issue = super()._resolve_step_people(
            step, ctx, company, on_date, record=record)
        mode = (step.get('who') or {}).get('mode')
        if mode not in ('manager', 'skip') or not people:
            return people, issue
        users = self.env['res.users'].sudo().browse(
            [p['user_id'] for p in people]).exists()
        portal = set(users.filtered('share').ids)
        if not portal:
            return people, issue
        people = [p for p in people if p['user_id'] not in portal]
        if people:
            return people, issue
        # Exactly the engine's own answer for a manager with no login.
        return [], {
            'level': 'block', 'code': 'manager_missing',
            'msg': _("No manager is recorded for the people this is "
                     "about, so nobody can be asked."),
            'fixes': [{'label': _('Open the employee record'),
                       'act': 'open_subject', 'arg': ''}]}
