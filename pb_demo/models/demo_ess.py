# -*- coding: utf-8 -*-
"""ESS/MSS demo enablement (Sudima Phase I §3) — extends pb.demo.generator.

Creates three persistent, PASSWORDLESS logins (C18.14 — password set at demo
time by an admin) and RE-LINKS them to the current demo employees on every
generate run (demo employees are recreated each run, so the linkage is rebuilt):

  * a MANAGER login → the demo manager with the most direct reports, granted the
    attendance-manager + HR-user groups so their approvals actually land (there
    is no parent-based OT record rule — approval needs attendance-manager);
  * an EMPLOYEE login → one adult report (the ESS profile / documents / tax story);
  * a MINOR login → 'Demo Minor 17', re-parented under the manager for the story.

It also seeds a couple of submitted overtime requests for adult reports so the My
Team queue is non-empty on a fresh demo (cleaned by clean_demo_employees).
"""

import logging

from odoo import fields, models

from .demo_employees import _YW_DEMOS

_logger = logging.getLogger(__name__)

_MINOR_NAMES = [d['name'] for d in _YW_DEMOS]
_MINOR_17 = 'Demo Minor 17 (Young Worker)'

_ESS_MANAGER_LOGIN = 'manager.demo@payobook.com'
_ESS_EMPLOYEE_LOGIN = 'employee.demo@payobook.com'
_ESS_MINOR_LOGIN = 'minor.demo@payobook.com'


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # -------------------------------------------------------------- users
    def _ess_group_ids(self, manager=False):
        xmlids = ['pb_demo.group_payobook_demo', 'base.group_user',
                  'base.group_multi_company']
        if manager:
            # attendance-manager: approve any OT (no parent-scoped OT rule
            # exists); hr.group_hr_user: read private fields for the roster
            # metrics (C18.34). Trip/correction/leave approvals pass on the
            # parent linkage without an extra group.
            xmlids += ['hr.group_hr_user',
                       'hr_attendance.group_hr_attendance_manager']
        gids = []
        for x in xmlids:
            g = self.env.ref(x, raise_if_not_found=False)
            if g:
                gids.append(g.id)
        return gids

    def _ensure_demo_login(self, login, name, company, manager=False):
        """Idempotent by login; passwordless (C18.14). Refreshes groups/company
        on an existing user so a regen re-asserts the demo state."""
        Users = self.env['res.users'].sudo().with_context(
            no_reset_password=True, mail_create_nosubscribe=True)
        gids = self._ess_group_ids(manager)
        user = Users.with_context(active_test=False).search(
            [('login', '=', login)], limit=1)
        vals = {
            'name': name, 'email': login,
            'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, gids)], 'active': True,
        }
        if user:
            user.write(vals)   # NO password — stays passwordless
            return user
        vals['login'] = login
        return Users.create(vals)   # NO password field (C18.14)

    def _link_user_employee(self, user, employee):
        """Link user ↔ employee, clearing any stale link (a user maps to one
        employee per company; demo employees are recreated each run)."""
        if not (user and employee):
            return
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        stale = Employee.search([('user_id', '=', user.id), ('id', '!=', employee.id)])
        if stale:
            stale.write({'user_id': False})
        employee.user_id = user.id

    # ----------------------------------------------------------- queue seed
    def _seed_team_queue(self, manager, company):
        """A couple of submitted OT requests for ADULT reports so the My Team
        queue is populated on a fresh demo. Never a minor (the young-worker gate
        blocks OT at creation — a stronger guarantee than a queue refusal)."""
        if 'hr.overtime.request' not in self.env:
            return
        OT = self.env['hr.overtime.request'].sudo()
        today = fields.Date.context_today(self)
        adults = manager.child_ids.filtered(
            lambda e: e.is_demo and e.name not in _MINOR_NAMES)[:2]
        for emp in adults:
            if OT.search_count([('employee_id', '=', emp.id),
                                ('state', '=', 'submitted')]):
                continue
            ot = OT.create({
                'employee_id': emp.id, 'company_id': company.id,
                'date': today, 'planned_hours': 2.0,
                'overtime_type': 'weekday',
                'reason': 'Month-end close support',
            })
            ot.action_submit()

    # -------------------------------------------------------------- entry
    def ensure_ess_demo_users(self):
        """Create/refresh the ESS+MSS demo logins and link them to the current
        demo world. Called from action_generate_all after generate_employees."""
        self = self.with_context(**self._GEN_CTX)
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        company = self.get_group_company()
        if not company:
            _logger.warning('pb_demo: no demo company; skipping ESS demo users')
            return

        managers = Employee.search([
            ('is_demo', '=', True), ('company_id', '=', company.id),
            ('parent_id', '=', False)]).filtered(lambda m: m.child_ids)
        if not managers:
            _logger.warning('pb_demo: no demo manager with reports; skipping ESS users')
            return
        manager = max(managers, key=lambda m: len(m.child_ids))

        # re-parent the demo minor under this manager for the MSS story
        minor = Employee.search([('name', '=', _MINOR_17)], limit=1)
        if minor:
            minor.parent_id = manager.id

        adult = manager.child_ids.filtered(
            lambda e: e.is_demo and e.name not in _MINOR_NAMES)[:1]

        mgr_user = self._ensure_demo_login(
            _ESS_MANAGER_LOGIN, 'Demo Manager (MSS)', company, manager=True)
        emp_user = self._ensure_demo_login(
            _ESS_EMPLOYEE_LOGIN, 'Demo Employee (ESS)', company)
        minor_user = self._ensure_demo_login(
            _ESS_MINOR_LOGIN, 'Demo Minor (ESS)', company)

        self._link_user_employee(mgr_user, manager)
        self._link_user_employee(emp_user, adult)
        self._link_user_employee(minor_user, minor)

        self._seed_team_queue(manager, company)
        _logger.info(
            'pb_demo: ESS demo users ready — manager=%s (%s reports), '
            'employee=%s, minor=%s', mgr_user.login, len(manager.child_ids),
            emp_user.login, minor_user.login)
        return {'manager': mgr_user, 'employee': emp_user, 'minor': minor_user}
