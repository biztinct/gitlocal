# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Phase C — Business Trips (§6 cases 1–7, 10).

Covers the biz_approval_chain mixin through its real consumer (pb.business.trip),
the multi-tier group gating, the audit trail, overlap guards, the
get_trip_day_map integration helper, and the two virtual presence overlays
(Timecards Gantt + Weekly Entry grid). Cases 8/9 live in the two bridge modules.
"""

from datetime import date, datetime, time, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBusinessTrip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr_user = cls.env.ref('hr.group_hr_user')
        g_payroll_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')

        cls.emp_user = Users.create({'name': 'Traveller', 'login': 'trip_emp',
                                     'group_ids': [(6, 0, [g_user.id])]})
        # a LINE MANAGER with no special group — proves rail 4 (specific manager
        # passes tier 2 without any approval group)
        cls.mgr_user = Users.create({'name': 'Line Mgr', 'login': 'trip_mgr',
                                     'group_ids': [(6, 0, [g_user.id])]})
        cls.finance_user = Users.create({
            'name': 'Finance', 'login': 'trip_finance',
            'group_ids': [(6, 0, [g_payroll_mgr.id, g_hr_user.id])]})
        cls.hr_user = Users.create({
            'name': 'HR Admin', 'login': 'trip_hr',
            'group_ids': [(6, 0, [g_payroll_mgr.id, g_hr_user.id])]})
        cls.random_user = Users.create({'name': 'Random', 'login': 'trip_random',
                                        'group_ids': [(6, 0, [g_user.id])]})

        Emp = cls.env['hr.employee']
        cls.mgr = Emp.create({'name': 'Line Mgr', 'user_id': cls.mgr_user.id,
                              'company_id': cls.company.id})
        cls.emp = Emp.create({'name': 'Traveller', 'user_id': cls.emp_user.id,
                              'parent_id': cls.mgr.id, 'company_id': cls.company.id})

        cls.vnd = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.company.currency_id
        cls.policy = cls.env['pb.trip.policy'].create({
            'name': 'Test VN', 'per_diem_rate': 200000.0,
            'currency_id': cls.vnd.id, 'per_diem_channel': 'payroll'})

        anchor = date(2026, 8, 10)
        cls.monday = anchor - timedelta(days=anchor.weekday())
        cls.d1 = cls.monday + timedelta(days=1)   # Tue
        cls.d3 = cls.monday + timedelta(days=3)   # Thu

    # ------------------------------------------------------------ helpers
    def _trip(self, employee=None, d_from=None, d_to=None, rate=200000.0,
              policy=None):
        return self.env['pb.business.trip'].create({
            'employee_id': (employee or self.emp).id,
            'date_from': d_from or self.d1,
            'date_to': d_to or self.d3,
            'purpose': 'Client visit',
            'per_diem_rate': rate,
            'policy_id': (policy or self.policy).id,
            'currency_id': self.vnd.id,
            'company_id': self.company.id,
        })

    def _drive_to_approved(self, trip):
        """Full chain as superuser (bypasses auth) — for the overlay/helper tests."""
        trip.action_submit()
        trip.action_manager_approve()
        trip.action_finance_approve()
        trip.action_hr_approve()

    def _logs(self, trip):
        return self.env['biz.approval.step.log'].search([
            ('res_model', '=', 'pb.business.trip'), ('res_id', '=', trip.id)],
            order='stamp, id')

    # ---------------------------------------------------- §6.1 mixin basics
    def test_01_mixin_transitions_and_log(self):
        trip = self._trip()
        # illegal jump raises
        with self.assertRaises(UserError):
            trip._advance_state('finance_approved')
        # legal transition writes state + exactly one log with the acting uid
        trip.action_submit()
        self.assertEqual(trip.state, 'submitted')
        logs = self._logs(trip)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs.to_state, 'submitted')
        self.assertEqual(logs.user_id, self.env.user)
        # refuse from a mid-state → refused + a second log
        trip.action_manager_approve()
        trip.action_refuse_chain(note='Budget')
        self.assertEqual(trip.state, 'refused')
        refuse_log = self._logs(trip)[-1]
        self.assertEqual(refuse_log.to_state, 'refused')
        self.assertEqual(refuse_log.note, 'Budget')

    # ---------------------------------------------------- §6.2 group gating
    def test_02_tier_group_gating(self):
        trip = self._trip()
        # the employee submits their own trip
        trip.with_user(self.emp_user).action_submit()
        self.assertEqual(trip.state, 'submitted')
        # a random user cannot manager-approve
        with self.assertRaises(AccessError):
            trip.with_user(self.random_user).action_manager_approve()
        # the SPECIFIC manager can — without any approval group (rail 4)
        trip.with_user(self.mgr_user).action_manager_approve()
        self.assertEqual(trip.state, 'manager_approved')
        # finance tier needs a finance/payroll-manager group
        with self.assertRaises(AccessError):
            trip.with_user(self.random_user).action_finance_approve()
        trip.with_user(self.finance_user).action_finance_approve()
        self.assertEqual(trip.state, 'finance_approved')
        # HR tier authorizes
        trip.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(trip.state, 'approved')

    # ---------------------------------------------------- §6.3 happy path trail
    def test_03_full_chain_trail(self):
        trip = self._trip()
        self._drive_to_approved(trip)
        self.assertEqual(trip.state, 'approved')
        logs = self._logs(trip)
        self.assertEqual(logs.mapped('to_state'),
                         ['submitted', 'manager_approved', 'finance_approved', 'approved'])
        trail = trip.get_approval_trail()
        self.assertEqual([t['to_state'] for t in trail],
                         ['submitted', 'manager_approved', 'finance_approved', 'approved'])

    # ---------------------------------------------------- §6.4 overlap guards
    def test_04_overlapping_trip_blocked(self):
        first = self._trip()
        self._drive_to_approved(first)
        # a second trip overlapping the approved one is hard-blocked at submit
        second = self._trip(d_from=self.d1, d_to=self.d1)
        with self.assertRaises(ValidationError):
            second.action_submit()
        self.assertEqual(second.state, 'draft')

    def test_04b_leave_overlap_soft_warns(self):
        lt = self.env['hr.leave.type'].sudo().create({
            'name': 'Trip Test Leave', 'requires_allocation': False})
        leave = self.env['hr.leave'].sudo().create({
            'name': 'x', 'holiday_status_id': lt.id, 'employee_id': self.emp.id,
            'request_date_from': self.d1, 'request_date_to': self.d3})
        leave.sudo().write({'state': 'validate'})
        trip = self._trip()
        # the warning fires but submit still succeeds (HR decides)
        self.assertTrue(trip._leave_overlap_warning())
        trip.action_submit()
        self.assertEqual(trip.state, 'submitted')

    # ---------------------------------------------------- §6.5 trip day map
    def test_05_trip_day_map_inclusive_approved_only(self):
        approved = self._trip(d_from=self.d1, d_to=self.d3)
        self._drive_to_approved(approved)
        draft = self._trip(employee=self.mgr, d_from=self.d1, d_to=self.d3)  # not approved
        Trip = self.env['pb.business.trip']
        m = Trip._get_trip_day_map([self.emp.id, self.mgr.id],
                                   self.monday, self.monday + timedelta(days=6))
        self.assertEqual(m.get(self.emp.id),
                         {self.d1.isoformat(),
                          (self.d1 + timedelta(days=1)).isoformat(),
                          (self.d1 + timedelta(days=2)).isoformat()})
        self.assertNotIn(self.mgr.id, m)  # draft excluded
        self.assertTrue(draft)  # silence linter

    # ---------------------------------------------------- §6.6 timecard overlay
    def test_06_timecard_trip_bars(self):
        trip = self._trip(d_from=self.d1, d_to=self.d3)
        self._drive_to_approved(trip)
        # a real punch on the first trip day — that day keeps its real bar + tag
        ci = datetime.combine(self.d1, time(1, 0))
        self.env['hr.attendance'].create({
            'employee_id': self.emp.id, 'check_in': ci,
            'check_out': ci + timedelta(hours=8)})
        data = self.env['hr.attendance.timecard'].get_timecard_data(
            employee_id=self.emp.id, week_start_str=self.monday.isoformat())
        emp_row = next(e for e in data['employees'] if e['id'] == self.emp.id)
        # an EMPTY trip day gets a full-width trip bar
        empty_day = emp_row['days'][(self.d1 + timedelta(days=1)).isoformat()]
        self.assertTrue(any(b.get('bar_type') == 'trip' for b in empty_day['entries']))
        self.assertTrue(empty_day.get('is_trip'))
        # the punched trip day keeps a real bar AND is tagged
        punched = emp_row['days'][self.d1.isoformat()]
        self.assertTrue(any(b.get('bar_type') != 'trip' for b in punched['entries']))
        self.assertTrue(punched.get('is_trip'))
        # legend gains a trip entry
        self.assertTrue(any(l.get('type') == 'trip' for l in data['ot_legend']))

    # ---------------------------------------------------- §6.7 grid overlay
    def test_07_weekentry_grid_locks_trip_days(self):
        trip = self._trip(d_from=self.d1, d_to=self.d3)
        self._drive_to_approved(trip)
        officer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Officer', 'login': 'trip_officer',
            'group_ids': [(6, 0, [
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
                self.env.ref('hr.group_hr_user').id])]})
        WE = self.env['hr.attendance.weekentry'].with_user(officer)
        data = WE.get_week_entries(self.monday.isoformat())
        row = next(r for r in data['rows'] if r['id'] == self.emp.id)
        self.assertIn(self.d1.isoformat(), row['flags'].get('trip_days', []))
        reg = row['cells'][self.d1.isoformat()]['measures']['reg']
        self.assertFalse(reg['editable'])
        # a crafted REG write on a trip day is refused server-side
        res = WE.save_week_entries({'cells': [{
            'rowId': self.emp.id, 'dayISO': self.d1.isoformat(),
            'measure': 'reg', 'value': 8, 'token': ''}]})
        self.assertFalse(res['results'][0]['ok'])
        self.assertEqual(res['results'][0]['error'], 'trip')

    # ---------------------------------------------------- §6.10 dep hygiene
    def test_10_core_has_no_payroll_or_expense_dep(self):
        mod = self.env['ir.module.module'].search(
            [('name', '=', 'pb_business_trip')], limit=1)
        deps = mod.dependencies_id.mapped('name')
        self.assertNotIn('pb_hr_payroll_formula', deps)
        self.assertNotIn('hr_expense', deps)
        self.assertNotIn('pb_trip_payroll_bridge', deps)
        self.assertNotIn('pb_trip_expense_bridge', deps)
