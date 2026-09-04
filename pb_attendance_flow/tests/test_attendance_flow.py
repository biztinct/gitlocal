# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Phase G — Attendance Workflow (§6 cases 1–10).

The system never invents a punch: every mutation goes through an approved
correction's single guarded writer, or the bulk import's per-row savepoints.
"""

import base64
from datetime import date, datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAttendanceFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Att = cls.env['hr.attendance']
        cls.Corr = cls.env['hr.attendance.correction']
        cls.Engine = cls.env['pb.attendance.exception.engine']
        cls.Wiz = cls.env['pb.attendance.import.wizard']
        Emp = cls.env['hr.employee']

        cls.today = date.today()

        # --- deactivate any pre-existing attendance rules, seed a clean global
        cls.env['pb.attendance.rule'].sudo().search([]).write({'active': False})
        cls.rule = cls.env['pb.attendance.rule'].sudo().create({
            'name': 'Test Global', 'company_id': False,
            'grace_in_minutes': 15, 'grace_out_minutes': 15,
            'open_checkout_hours': 16})

        # employees
        cls.ework = Emp.create({'name': 'Erin Worker', 'company_id': cls.company.id,
                                'tz': 'UTC', 'barcode': 'EW001'})
        cls.emp_adult = Emp.create({'name': 'Adam Adult', 'company_id': cls.company.id,
                                    'tz': 'UTC', 'barcode': 'AA002'})
        cls.minor = Emp.create({
            'name': 'Molly Minor', 'company_id': cls.company.id, 'tz': 'UTC',
            'barcode': 'MM003', 'birthday': cls.today - relativedelta(years=17, days=50)})

        # shift template
        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'Day', 'code': 'DAY', 'start_hour': 8.0, 'end_hour': 16.0,
            'is_overnight': False, 'shift_type': 'morning', 'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    def _shift(self, emp, d, actual_in=None, actual_out=None, state='published'):
        s = self.env['hr.shift.planning'].create({
            'employee_id': emp.id,
            'shift_template_id': self.tmpl.id,
            'date': d,
            'start_datetime': datetime.combine(d, time(8, 0)),
            'end_datetime': datetime.combine(d, time(16, 0)),
            'actual_check_in': actual_in,
            'actual_check_out': actual_out,
            'state': state,
        })
        return s

    def _att(self, emp, d, start_h=8, hours=8, source='grid', check_out=True):
        ci = datetime.combine(d, time(start_h, 0))
        vals = {'employee_id': emp.id, 'check_in': ci, 'pb_entry_source': source or False}
        if check_out:
            vals['check_out'] = ci + timedelta(hours=hours)
        return self.Att.create(vals)

    def _workday(self, days_back):
        """A WEEKDAY `days_back` days ago (stepping further back over a
        weekend). hr_holidays refuses to validate a leave on a non-working day
        ("not supposed to work during that period"), so any date-relative
        fixture that feeds a leave must be calendar-stable — otherwise the
        suite passes on a Friday and fails on a Tuesday."""
        d = self.today - timedelta(days=days_back)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    def _officer(self, login='atf_officer', extra=None):
        groups = [self.env.ref('base.group_user').id,
                  self.env.ref('hr.group_hr_user').id,
                  self.env.ref('hr_attendance.group_hr_attendance_officer').id]
        groups += (extra or [])
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'group_ids': [(6, 0, groups)]})

    # =================================================================== 1
    def test_01_exception_engine_kinds(self):
        """missing_punch / late / early_leave / missing_checkout are detected."""
        d_miss = self.today - timedelta(days=3)
        d_late = self.today - timedelta(days=4)
        d_early = self.today - timedelta(days=5)
        # missing punch: published shift, past, no punch
        self._shift(self.ework, d_miss)
        # late 20 min
        self._shift(self.ework, d_late,
                    actual_in=datetime.combine(d_late, time(8, 20)),
                    actual_out=datetime.combine(d_late, time(16, 0)))
        # early leave 40 min
        self._shift(self.ework, d_early,
                    actual_in=datetime.combine(d_early, time(8, 0)),
                    actual_out=datetime.combine(d_early, time(15, 20)))
        # open punch 21h ago → missing checkout
        open_ci = datetime.now() - timedelta(hours=21)
        self.Att.create({'employee_id': self.ework.id, 'check_in': open_ci,
                         'pb_entry_source': 'grid'})

        rows = self.Engine._get_exceptions(
            self.ework, self.today - timedelta(days=7), self.today)
        by_kind = {}
        for r in rows:
            by_kind.setdefault(r['kind'], []).append(r)
        self.assertIn('missing_punch', by_kind)
        self.assertIn('late', by_kind)
        self.assertIn('early_leave', by_kind)
        self.assertIn('missing_checkout', by_kind)
        self.assertAlmostEqual(by_kind['late'][0]['minutes'], 20, delta=1)
        self.assertAlmostEqual(by_kind['early_leave'][0]['minutes'], 40, delta=1)

    # =================================================================== 2
    def test_02_trip_and_leave_exclusion(self):
        """An approved trip day and a validated leave day yield NO missing punch."""
        d = self._workday(3)

        # --- leave (hr_holidays is always in the stack) ---
        emp_lv = self.env['hr.employee'].create({
            'name': 'Leo Leave', 'company_id': self.company.id, 'tz': 'UTC'})
        self._shift(emp_lv, d)
        lt = self.env['hr.leave.type'].create({
            'name': 'ATF Unpaid', 'requires_allocation': False,
            'leave_validation_type': 'no_validation'})
        leave = self.env['hr.leave'].create({
            'name': 'off', 'employee_id': emp_lv.id, 'holiday_status_id': lt.id,
            'request_date_from': d, 'request_date_to': d})
        if leave.state != 'validate':
            leave.sudo().action_approve()   # no_validation type → straight to validate
        self.assertEqual(leave.state, 'validate')
        rows = self.Engine._get_exceptions(emp_lv, d - timedelta(days=1), self.today)
        self.assertFalse([r for r in rows if r['kind'] == 'missing_punch'],
                         "A validated leave day must not raise a missing punch.")

        # --- trip (soft-hook; skip if pb_business_trip absent) ---
        if 'pb.business.trip' in self.env:
            emp_tr = self.env['hr.employee'].create({
                'name': 'Tina Trip', 'company_id': self.company.id, 'tz': 'UTC'})
            self._shift(emp_tr, d)
            self.env['pb.business.trip'].sudo().create({
                'employee_id': emp_tr.id, 'purpose': 'Site visit',
                'date_from': d, 'date_to': d, 'state': 'approved',
                'company_id': self.company.id})
            rows = self.Engine._get_exceptions(emp_tr, d - timedelta(days=1), self.today)
            self.assertFalse([r for r in rows if r['kind'] == 'missing_punch'],
                             "An approved trip day must not raise a missing punch.")

    # =================================================================== 3
    def test_03_grace_config_and_company_isolation(self):
        """grace_in=30 makes a 20-min-late shift on_time; two-search isolation."""
        d = self.today - timedelta(days=4)
        # a company rule with a wide grace overrides the global
        co_rule = self.env['pb.attendance.rule'].sudo().create({
            'name': 'Wide', 'company_id': self.company.id,
            'grace_in_minutes': 30, 'grace_out_minutes': 15, 'open_checkout_hours': 16})
        emp = self.env['hr.employee'].create({
            'name': 'Grace Test', 'company_id': self.company.id, 'tz': 'UTC'})
        # shift computed AFTER the company rule exists → 20<30 → on_time
        self._shift(emp, d,
                    actual_in=datetime.combine(d, time(8, 20)),
                    actual_out=datetime.combine(d, time(16, 0)))
        rows = self.Engine._get_exceptions(emp, d - timedelta(days=1), self.today)
        self.assertFalse([r for r in rows if r['kind'] == 'late'],
                         "With grace 30, a 20-min-late row is not late.")
        # two-search: company A resolves to its own rule, not the global
        resolved = self.env['pb.attendance.rule']._for_company(self.company)
        self.assertEqual(resolved, co_rule)
        # a company with no rule falls back to the global
        other = self.env['res.company'].create({'name': 'ATF Co B'})
        self.assertEqual(
            self.env['pb.attendance.rule']._for_company(other), self.rule)

    # =================================================================== 4
    def test_04_correction_lifecycle_manager_tier(self):
        """Employee files adjust → line manager (no officer group) approves →
        attendance updated, source='correction', log rows exist; self-approve
        is refused."""
        d = self.today - timedelta(days=2)
        req_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Req', 'login': 'atf_req',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        mgr_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Mgr', 'login': 'atf_mgr',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        mgr_emp = self.env['hr.employee'].create({
            'name': 'Manager Emp', 'company_id': self.company.id, 'user_id': mgr_user.id})
        worker = self.env['hr.employee'].create({
            'name': 'Worker Emp', 'company_id': self.company.id, 'tz': 'UTC',
            'user_id': req_user.id, 'parent_id': mgr_emp.id})
        att = self._att(worker, d, start_h=8, hours=8, source='grid')

        corr = self.Corr.with_user(req_user).create({
            'employee_id': worker.id, 'date': d, 'correction_type': 'adjust',
            'attendance_id': att.id,
            'new_check_in': datetime.combine(d, time(8, 0)),
            'new_check_out': datetime.combine(d, time(17, 0)),
            'reason': 'Forgot to log the extra hour'})
        corr.with_user(req_user).action_submit()
        self.assertEqual(corr.state, 'submitted')

        # requester cannot self-approve
        with self.assertRaises(AccessError):
            corr.with_user(req_user).action_approve()

        # line manager (no officer group) approves
        corr.with_user(mgr_user).action_approve()
        self.assertEqual(corr.state, 'approved')
        att.invalidate_recordset()
        self.assertEqual(att.pb_entry_source, 'correction')
        self.assertEqual(att.check_out, datetime.combine(d, time(17, 0)))
        logs = self.env['biz.approval.step.log'].search([
            ('res_model', '=', 'hr.attendance.correction'), ('res_id', '=', corr.id)])
        self.assertTrue(logs.filtered(lambda l: l.to_state == 'approved'))

    # =================================================================== 5
    def test_05_delete_correction_and_device_guard(self):
        """A delete correction removes a grid row; a device row can't be unlinked
        without the sentinel, but can via an approved correction."""
        d = self.today - timedelta(days=6)
        officer = self._officer('atf_off5', extra=[
            self.env.ref('hr_attendance.group_hr_attendance_manager').id])

        grid_att = self._att(self.ework, d, start_h=8, hours=8, source='grid')
        corr = self.Corr.create({
            'employee_id': self.ework.id, 'date': d, 'correction_type': 'delete',
            'attendance_id': grid_att.id, 'reason': 'Double entry'})
        corr.action_submit()
        corr.action_approve()
        self.assertFalse(grid_att.exists())

        # a DEVICE punch (blank source)
        dev = self._att(self.emp_adult, d, start_h=9, hours=8, source=False)
        # officer holds unlink ACL but is not su → guard raises
        with self.assertRaises(UserError):
            dev.with_user(officer).unlink()
        self.assertTrue(dev.exists())
        # via an approved correction it succeeds
        corr2 = self.Corr.create({
            'employee_id': self.emp_adult.id, 'date': d, 'correction_type': 'delete',
            'attendance_id': dev.id, 'reason': 'Bad device punch'})
        corr2.action_submit()
        corr2.action_approve()
        self.assertFalse(dev.exists())

    # =================================================================== 6
    def test_06_direct_state_write_blocked(self):
        """A direct write({'state':'approved'}) is refused (mixin token)."""
        d = self.today - timedelta(days=2)
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Sneaky', 'login': 'atf_sneak',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        emp = self.env['hr.employee'].create({
            'name': 'Sneak Emp', 'company_id': self.company.id, 'user_id': user.id})
        corr = self.Corr.with_user(user).create({
            'employee_id': emp.id, 'date': d, 'correction_type': 'create',
            'new_check_in': datetime.combine(d, time(8, 0)),
            'new_check_out': datetime.combine(d, time(16, 0)),
            'reason': 'x'})
        with self.assertRaises(AccessError):
            corr.with_user(user).write({'state': 'approved'})

    # =================================================================== 7
    def test_07_young_worker_correction_refused(self):
        """A correction pushing a minor past the daily cap lands in 'refused'
        with the law message — not a traceback."""
        if not self.env['pb.young.worker']._has_any_rule():
            self.skipTest("No active young-worker rule in this DB.")
        d = self.today - timedelta(days=3)
        corr = self.Corr.create({
            'employee_id': self.minor.id, 'date': d, 'correction_type': 'create',
            'new_check_in': datetime.combine(d, time(6, 0)),
            'new_check_out': datetime.combine(d, time(18, 0)),  # 12h > 8h cap
            'reason': 'Long day'})
        corr.action_submit()
        corr.action_approve()  # must NOT raise
        self.assertEqual(corr.state, 'refused')
        self.assertTrue(corr.apply_error)
        self.assertFalse(self.Att.search([
            ('employee_id', '=', self.minor.id),
            ('check_in', '=', datetime.combine(d, time(6, 0)))]))

    # =================================================================== 8
    def test_08_import_validate_and_commit(self):
        """5-row file: 1 unknown, 1 overlap, 1 cap breach, 2 good → validate
        flags 3, commit creates 2; re-import creates 0."""
        d = self.today - timedelta(days=7)
        g1 = self.env['hr.employee'].create({
            'name': 'Good One', 'company_id': self.company.id, 'tz': 'UTC', 'barcode': 'G1'})
        g2 = self.env['hr.employee'].create({
            'name': 'Good Two', 'company_id': self.company.id, 'tz': 'UTC', 'barcode': 'G2'})
        ov = self.env['hr.employee'].create({
            'name': 'Over Lap', 'company_id': self.company.id, 'tz': 'UTC', 'barcode': 'OV'})
        # pre-existing punch that the import row overlaps
        self._att(ov, d, start_h=8, hours=8, source='grid')

        iso = d.isoformat()
        csv = ("Employee,Date,Check In,Check Out\n"
               "G1,%s,08:00,16:00\n"
               "G2,%s,09:00,17:00\n"
               "OV,%s,08:30,12:00\n"
               "NOPE,%s,08:00,16:00\n"
               "MM003,%s,06:00,18:00\n" % (iso, iso, iso, iso, iso))
        b64 = base64.b64encode(csv.encode()).decode()
        mapping = {'employee': 'Employee', 'date': 'Date',
                   'check_in': 'Check In', 'check_out': 'Check Out'}

        val = self.Wiz.validate(b64, 'punches.csv', mapping)
        self.assertEqual(val['summary']['total'], 5)
        self.assertEqual(val['summary']['valid'], 2)
        self.assertEqual(val['summary']['invalid'], 3)

        res = self.Wiz.commit(b64, 'punches.csv', mapping)
        self.assertEqual(res['created'], 2)
        self.assertEqual(res['skipped'], 3)
        imported = self.Att.search([
            ('employee_id', 'in', (g1 | g2).ids), ('pb_entry_source', '=', 'import')])
        self.assertEqual(len(imported), 2)

        # re-import the same file → overlaps everything now → 0 created
        res2 = self.Wiz.commit(b64, 'punches.csv', mapping)
        self.assertEqual(res2['created'], 0)

    # =================================================================== 9
    def test_09_grid_untouched_stale_token(self):
        """The Phase-B grid still refuses a stale token (unbroken by Phase G)."""
        d = self.today - timedelta(days=2)
        officer = self._officer('atf_off9')
        att = self._att(self.ework, d, start_h=8, hours=8, source='grid')
        Grid = self.env['hr.attendance.weekentry'].with_user(officer)
        payload = {'cells': [{
            'rowId': self.ework.id, 'dayISO': d.isoformat(), 'measure': 'reg',
            'value': 5.0, 'token': 'not-the-real-token'}]}
        out = Grid.save_week_entries(payload)
        self.assertEqual(out['results'][0]['error'], 'stale')
        att.invalidate_recordset()
        self.assertEqual(att.check_out, datetime.combine(d, time(16, 0)),
                         "A stale save must not have mutated the row.")

    # =================================================================== 10
    def test_10_adult_no_shift_no_exception(self):
        """A 12h device punch for an adult with no published shift raises no
        exception and is not blocked (report-only world)."""
        d = self.today - timedelta(days=6)
        att = self._att(self.emp_adult, d, start_h=6, hours=12, source=False)
        self.assertTrue(att.exists())
        rows = self.Engine._get_exceptions(
            self.emp_adult, d - timedelta(days=1), d + timedelta(days=1))
        # no shift that day → no shift-derived exception; punch is closed → no
        # missing checkout
        self.assertFalse([r for r in rows if r['date'] == d.isoformat()])

    # ================================================= combined-review fixes
    def test_11_engine_is_private_and_day_punches_gated(self):
        """Review G-C1/G-H3: the sudo feed is underscore-private (C18.32) and
        the punch timeline is officer-or-self-or-line-manager only."""
        self.assertFalse(hasattr(type(self.Engine), 'get_exceptions'),
                         "the RPC-reachable engine name must be gone")
        d = self.today - timedelta(days=2)
        self._att(self.emp_adult, d)
        Cockpit = self.env['pb.attendance.flow']
        stranger = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'atf_str', 'login': 'atf_str',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            Cockpit.with_user(stranger).get_day_punches(
                self.emp_adult.id, d.isoformat())
        # self passes
        self.emp_adult.user_id = stranger
        rows = Cockpit.with_user(stranger).get_day_punches(
            self.emp_adult.id, d.isoformat())
        self.assertTrue(rows, "an employee sees their own punches")

    def test_12_review_fields_freeze_after_submit(self):
        """Review G-H2 (C18.31 TOCTOU): the facts an approver rules on are
        immutable once submitted — no rewrite between submit and approve."""
        d = self.today - timedelta(days=2)
        requester = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'atf_req', 'login': 'atf_req',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.ework.user_id = requester
        corr = self.Corr.with_user(requester).create({
            'employee_id': self.ework.id, 'date': d,
            'correction_type': 'create',
            'new_check_in': datetime.combine(d, time(8, 0)),
            'new_check_out': datetime.combine(d, time(16, 0)),
            'reason': 'forgot badge'})
        corr.with_user(requester).action_submit()
        self.assertEqual(corr.state, 'submitted')
        with self.assertRaises(AccessError):
            corr.with_user(requester).write({
                'new_check_out': datetime.combine(d, time(23, 0))})
        # reset to draft re-opens editing for the requester
        corr.with_user(requester).action_reset_to_draft()
        corr.with_user(requester).write({
            'new_check_out': datetime.combine(d, time(17, 0))})
        self.assertEqual(corr.state, 'draft')

    def test_13_adjust_keeps_existing_checkout(self):
        """Review G-M6: adjusting only the check-in must not wipe the existing
        check-out (that reopened the punch and zeroed its hours)."""
        d = self.today - timedelta(days=2)
        att = self._att(self.ework, d, start_h=9, hours=7, source=False)
        original_out = att.check_out
        corr = self.Corr.create({
            'employee_id': self.ework.id, 'date': d,
            'correction_type': 'adjust', 'attendance_id': att.id,
            'new_check_in': datetime.combine(d, time(8, 0)),
            'reason': 'badge lag'})
        corr.action_submit()
        officer = self._officer('atf_off_adj')
        corr.with_user(officer).action_approve()
        self.assertEqual(corr.state, 'approved')
        att.invalidate_recordset()
        self.assertEqual(att.check_in, datetime.combine(d, time(8, 0)))
        self.assertEqual(att.check_out, original_out,
                         "the untouched check-out must survive the adjust")

    def test_14_punch_days_use_employee_local_dates(self):
        """Review G-M5 (C18.49): a VN 05:58 punch is 22:58 the PREVIOUS UTC day
        — UTC keying would invent a missing_punch for the local shift day."""
        emp_vn = self.env['hr.employee'].create({
            'name': 'Vy VN', 'company_id': self.company.id,
            'tz': 'Asia/Ho_Chi_Minh'})
        d = self.today - timedelta(days=3)
        self._shift(emp_vn, d)   # 08:00 local shift, published, in the past
        # punch at 05:58 LOCAL = 22:58 UTC the day before
        self.Att.create({
            'employee_id': emp_vn.id,
            'check_in': datetime.combine(d - timedelta(days=1), time(22, 58)),
            'check_out': datetime.combine(d, time(9, 0)),
        })
        rows = self.Engine._get_exceptions(
            emp_vn, d - timedelta(days=1), d + timedelta(days=1))
        missing = [r for r in rows if r['kind'] == 'missing_punch'
                   and r['date'] == d.isoformat()]
        self.assertFalse(missing,
                         "an early local punch must count for the LOCAL day")

    # =================================================================== 15
    # Workforce P1a WP-3 — the facade gained an optional window + department so
    # the Time hub can embed this cockpit as its Exceptions lens (W17). The
    # no-argument call MUST stay byte-for-byte the historical behaviour.
    def test_15_get_control_data_default_window_unchanged(self):
        """No arguments => the rolling 14-day, all-department board."""
        d_in = self.today - timedelta(days=3)
        d_out = self.today - timedelta(days=40)        # outside the 14-day window
        self._shift(self.ework, d_in)
        self._shift(self.ework, d_out)

        data = self.env['pb.attendance.flow'].get_control_data()
        self.assertEqual(data['window']['to'], self.today.isoformat())
        self.assertEqual(
            data['window']['from'],
            (self.today - timedelta(days=13)).isoformat(),
            "the default look-back must remain 14 days for the standalone cockpit")
        dates = {x['date'] for x in data['exceptions']}
        self.assertIn(d_in.isoformat(), dates)
        self.assertNotIn(d_out.isoformat(), dates)

    def test_16_get_control_data_honours_an_explicit_window(self):
        """A window narrows the feed to exactly those days."""
        d_hit = self.today - timedelta(days=3)
        d_miss = self.today - timedelta(days=10)
        self._shift(self.ework, d_hit)
        self._shift(self.ework, d_miss)

        data = self.env['pb.attendance.flow'].get_control_data(
            (self.today - timedelta(days=4)).isoformat(),
            (self.today - timedelta(days=2)).isoformat())
        self.assertEqual(data['window'], {
            'from': (self.today - timedelta(days=4)).isoformat(),
            'to': (self.today - timedelta(days=2)).isoformat()})
        dates = {x['date'] for x in data['exceptions']}
        self.assertIn(d_hit.isoformat(), dates)
        self.assertNotIn(d_miss.isoformat(), dates)

        # an inverted window is repaired rather than returning nothing
        flipped = self.env['pb.attendance.flow'].get_control_data(
            (self.today - timedelta(days=2)).isoformat(),
            (self.today - timedelta(days=4)).isoformat())
        self.assertEqual(flipped['window'], data['window'])

    def test_17_get_control_data_honours_the_department(self):
        """The context department narrows the cohort (W4)."""
        dept_a = self.env['hr.department'].create({
            'name': 'P1a Dept A', 'company_id': self.company.id})
        dept_b = self.env['hr.department'].create({
            'name': 'P1a Dept B', 'company_id': self.company.id})
        self.ework.department_id = dept_a
        self.emp_adult.department_id = dept_b
        d = self.today - timedelta(days=3)
        self._shift(self.ework, d)
        self._shift(self.emp_adult, d)

        df = (self.today - timedelta(days=4)).isoformat()
        dt = self.today.isoformat()
        both = self.env['pb.attendance.flow'].get_control_data(df, dt)
        only_a = self.env['pb.attendance.flow'].get_control_data(df, dt, dept_a.id)

        ids_both = {x['employee_id'] for x in both['exceptions']}
        ids_a = {x['employee_id'] for x in only_a['exceptions']}
        self.assertIn(self.ework.id, ids_both)
        self.assertIn(self.emp_adult.id, ids_both)
        self.assertEqual(ids_a & {self.ework.id, self.emp_adult.id}, {self.ework.id},
                         "department filtering must drop the other department's rows")

    # =================================================================== 18
    def test_18_create_correction_reuse_draft_is_idempotent(self):
        """`reuse_draft` reopens this day's DRAFT instead of minting another.

        The Time hub's drawer hand-off is an idempotent "open the correction for
        this day" gesture. Without this, a component mount that runs twice for
        any reason leaves duplicate drafts in the pipeline — which is exactly
        what a P1a render loop did to the live database (W21) before it was
        caught, 591 times in 90 seconds.
        """
        d = self.today - timedelta(days=3)
        payload = {'employee_id': self.ework.id, 'date': d.isoformat(),
                   'correction_type': 'adjust', 'reason': 'first',
                   'reuse_draft': True}
        first = self.env['pb.attendance.flow'].create_correction(payload)
        second = self.env['pb.attendance.flow'].create_correction(dict(payload, reason='again'))
        self.assertEqual(first['id'], second['id'],
                         'reuse_draft must return the existing draft')
        self.assertEqual(self.Corr.search_count([
            ('employee_id', '=', self.ework.id), ('date', '=', d),
            ('correction_type', '=', 'adjust')]), 1)

        # without the flag the historical behaviour is unchanged: a new draft
        third = self.env['pb.attendance.flow'].create_correction(
            {k: v for k, v in payload.items() if k != 'reuse_draft'})
        self.assertNotEqual(third['id'], first['id'])

        # a SUBMITTED correction is history: it is never silently reopened.
        # An `adjust` needs a target punch before it can be submitted
        # (_check_ready_to_submit), so give it one — same recipe as test_04.
        self.Corr.browse(third['id']).unlink()
        att = self._att(self.ework, d, start_h=8, hours=8, source='grid')
        opened = self.Corr.browse(first['id'])
        opened.write({
            'attendance_id': att.id,
            'new_check_in': datetime.combine(d, time(8, 0)),
            'new_check_out': datetime.combine(d, time(17, 0)),
            'reason': 'ready to submit',
        })
        opened.action_submit()
        self.assertEqual(opened.state, 'submitted')

        fourth = self.env['pb.attendance.flow'].create_correction(payload)
        self.assertNotEqual(fourth['id'], opened.id,
                            'a submitted correction must never be silently reopened')
        self.assertEqual(
            self.Corr.browse(fourth['id']).state, 'draft',
            'reuse_draft falls back to creating a fresh DRAFT')
