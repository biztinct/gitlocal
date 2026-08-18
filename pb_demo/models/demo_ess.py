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
from datetime import timedelta

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


# =========================================================================
#  P8 — the ESS WORKFORCE cohort (Workforce redesign, "My Work")
# =========================================================================
# Phase I seeded three logins because three personas were all the ESS story
# needed. P8's story is a ROSTER: an ack badge that reads "12 of 16", a Today
# tile that clears an anonymity floor of five, and a manager watching
# confirmations arrive. Three people cannot demonstrate any of that, so this
# adds a cohort — ten logins in one named department, which is also the
# department every other P6 instrument is concentrated in, so the whole demo
# happens on one filter rather than four.

# The department the demo world is dense in (`demo_workforce_current._GRID_DEPT`
# — restated rather than imported so a change there is a visible conflict here
# rather than a silent re-aim of the ESS cohort).
_ESS_WORK_DEPT = 'Stores - North'
_ESS_COHORT_SIZE = 10
_ESS_WORK_LOGIN = 'ess%s.demo@payobook.com'

# The ack MIX. Not "everything confirmed" (a badge that is always green is an
# instrument nobody reads) and not "nothing confirmed" (which looks broken).
# Roughly three in four, deterministic by index so a regen produces the same
# picture and a screenshot stays true.
_ESS_ACK_SKIP = 4          # every 4th cohort member leaves their week pending

# The pulse. The Today tile's floor is 5, so a demo that seeds four rows shows
# nothing and reads as a broken feature — this seeds comfortably past it, spread
# over the window rather than stacked on one day.
_ESS_PULSE_RATINGS = (5, 4, 4, 3, 5, 4, 2, 5)
# Demo pulse rows carry no employee (that is the model's whole point), so W60's
# "the employee owns the demo data" rule cannot reach them. They are marked in
# the one column they have: a `uniq_hash` prefix, which is also what makes the
# seeder idempotent without a second lookup.
_ESS_PULSE_TAG = 'pbdemo:p8:'


class PbDemoGeneratorEssWorkforce(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # ------------------------------------------------------------- cohort
    def _ess_work_department(self, company):
        return self.env['hr.department'].sudo().search(
            [('name', '=', _ESS_WORK_DEPT), ('company_id', '=', company.id)],
            limit=1)

    def _ess_work_cohort(self, company):
        """The ten demo employees who get a login.

        Alphabetical head of the department, which is EXACTLY the slice
        `demo_workforce_current._p6_dept_slice` seeds shifts, punches and
        overtime for — so every person who can log in has a week worth looking
        at. A random pick would have produced logins onto empty schedules.
        """
        dept = self._ess_work_department(company)
        if not dept:
            return self.env['hr.employee'].sudo().browse()
        return self.env['hr.employee'].sudo().search([
            ('is_demo', '=', True), ('active', '=', True),
            ('company_id', '=', company.id),
            ('department_id', '=', dept.id),
            ('user_id', '=', False),
        ], order='name', limit=_ESS_COHORT_SIZE)

    def ensure_ess_workforce_cohort(self):
        """Ten passwordless ESS logins + a realistic ack mix + a live pulse.

        Idempotent by login (the users) and by hash prefix (the pulse); never
        destructive (W60) — an ack an officer or a demo visitor already gave is
        left exactly where it is.
        """
        self = self.with_context(**self._GEN_CTX)
        out = {'users': 0, 'linked': 0, 'acked': 0, 'pending': 0, 'pulse': 0}
        company = self.get_group_company()
        if not company:
            _logger.warning('pb_demo P8: no demo company; skipping ESS cohort')
            return out

        # --- the logins --------------------------------------------------
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        existing = Users.search(
            [('login', 'like', 'ess%.demo@payobook.com')])
        need = _ESS_COHORT_SIZE - len(existing)
        fresh = self._ess_work_cohort(company) if need > 0 else \
            self.env['hr.employee'].sudo().browse()

        cohort_emps = self.env['hr.employee'].sudo().browse()
        for i in range(_ESS_COHORT_SIZE):
            login = _ESS_WORK_LOGIN % (i + 1)
            user = Users.search([('login', '=', login)], limit=1)
            emp = self.env['hr.employee'].sudo().browse()
            if user:
                # Re-link: demo employees are recreated on every regen, so a
                # surviving login is re-pointed at a current employee rather
                # than left dangling (the Phase-I rule, restated for ten).
                emp = self.env['hr.employee'].sudo().search(
                    [('user_id', '=', user.id)], limit=1)
                if not emp and fresh:
                    emp, fresh = fresh[0], fresh[1:]
            elif fresh:
                emp, fresh = fresh[0], fresh[1:]
            if not emp:
                continue
            if not user:
                out['users'] += 1
            user = self._ensure_demo_login(login, emp.name or login, company)
            self._link_user_employee(user, emp)
            out['linked'] += 1
            cohort_emps |= emp

        if not cohort_emps:
            _logger.warning('pb_demo P8: no %s employees free for ESS logins',
                            _ESS_WORK_DEPT)
            return out

        out.update(self._ess_seed_acks(cohort_emps))
        out.update(self._ess_seed_pulse(company))
        _logger.info(
            'pb_demo P8: ESS cohort ready — %(linked)s logins, %(acked)s shifts '
            'confirmed, %(pending)s left pending, %(pulse)s pulse ratings', out)
        return out

    # ---------------------------------------------------------------- acks
    def _ess_seed_acks(self, cohort):
        """Confirm most of the cohort's published week; leave a few pending.

        Only FUTURE shifts are marked, because that is the only set the portal
        would let a person confirm — a demo state a user could not have produced
        is a demo that lies about the product (`_ess_can_ack` is the same
        predicate the button uses).
        """
        if 'ack_state' not in self.env['hr.shift.planning']._fields:
            return {}                     # pb_ess_workforce not installed
        Shift = self.env['hr.shift.planning'].sudo()
        now = fields.Datetime.now()
        acked = pending = 0
        for idx, emp in enumerate(cohort.sorted(key=lambda e: (e.name or '', e.id))):
            shifts = Shift.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'published'),
                ('start_datetime', '>', now),
            ], order='start_datetime')
            if idx % _ESS_ACK_SKIP == 3:
                pending += len(shifts.filtered(
                    lambda s: s.ack_state == 'pending'))
                continue
            for s in shifts:
                if s.ack_state == 'acked':
                    continue
                # one shift each stays pending, so every badge is "n of m"
                # rather than a wall of green checks
                if s == shifts[-1] and len(shifts) > 1:
                    pending += 1
                    continue
                if s._ess_ack('demo'):
                    acked += 1
        return {'acked': acked, 'pending': pending}

    # --------------------------------------------------------------- pulse
    def _ess_seed_pulse(self, company):
        """Enough anonymous ratings, spread over the window, to clear the floor.

        No employee is involved and none can be: the rows are tagged in their
        uniqueness hash, which is the only column they have that is not a fact
        about a department and a day.
        """
        if 'pb.shift.pulse' not in self.env:
            return {}
        Pulse = self.env['pb.shift.pulse'].sudo()
        dept = self._ess_work_department(company)
        today = fields.Date.context_today(self)
        made = 0
        for i, rating in enumerate(_ESS_PULSE_RATINGS):
            day = today - timedelta(days=i % 6)
            digest = '%s%s:%s' % (_ESS_PULSE_TAG, day.isoformat(), i)
            if Pulse.search_count([('uniq_hash', '=', digest)]):
                continue
            Pulse.create({
                'company_id': company.id,
                'department_id': dept.id if dept else False,
                'date': day,
                'rating': rating,
                'uniq_hash': digest,
            })
            made += 1
        return {'pulse': made}

    # -------------------------------------------------------------- cleanup
    def clean_demo_employees(self):
        """Take the demo pulse rows with the demo employees.

        They are the one piece of P8 demo residue `clean_demo_employees` cannot
        find by employee (W60), because having no employee is the point. The
        tag is the handle, and it is scoped tightly enough that a real rating
        can never match it.
        """
        if 'pb.shift.pulse' in self.env:
            self.env['pb.shift.pulse'].sudo().search(
                [('uniq_hash', '=like', _ESS_PULSE_TAG + '%')]).unlink()
        return super().clean_demo_employees()
