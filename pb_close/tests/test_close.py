# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P4 — T3: the classification matrix and the review subtraction.

The Close board decides which weeks reach payroll, so the interesting cases are
the ones where it must be QUIET: a rest day is not an exception, an approved
trip is not a missing punch, a person eight minutes off every day is one fact
and not seven. Each of those is a case below, because each of them is a way for
a useful instrument to become an ignored one.
"""

from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import CloseCase


@tagged('post_install', '-at_install')
class TestCloseBoard(CloseCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Close = cls.env['pb.close']
        cls.Review = cls.env['pb.close.review']
        cls.dept = cls.env['hr.department'].create({
            'name': 'P4 Close Dept', 'company_id': cls.company.id})
        cls.emp.department_id = cls.dept
        cls.emp2.department_id = cls.dept

    # ------------------------------------------------------------- helpers
    def _data(self, **kw):
        kw.setdefault('department_id', self.dept.id)
        kw.setdefault('week_start', self.week_start.isoformat())
        return self.Close.get_close_data(**kw)

    def _flags(self, data, employee=None, day=None):
        out = data['flagged']
        if employee:
            out = [r for r in out if r['employee_id'] == employee.id]
        if day:
            out = [r for r in out if r['date'] == day.isoformat()]
        return {r['kind'] for r in out}

    # ==================================================================
    #  the buckets
    # ==================================================================
    def test_a_perfect_day_is_clean_and_produces_no_row(self):
        self._shift(self.emp, self.day)
        self._punch(self.emp, self.day, start_h=8, hours=8.0)
        data = self._data()
        self.assertEqual(data['stats']['flagged'], 0)
        self.assertEqual(data['stats']['clean'], 1)
        self.assertTrue(data['can_lock'])

    def test_a_rest_day_is_neither_clean_nor_flagged(self):
        """Two hundred Sundays in "auto-approved" makes the headline number
        meaningless; two hundred Sundays in "flagged" makes the board useless.
        A day with no shift and no punch is simply not a fact about this week."""
        data = self._data()
        self.assertEqual(data['stats']['clean'], 0)
        self.assertEqual(data['stats']['flagged'], 0)

    def test_a_scheduled_day_with_no_punch_is_a_missing_punch(self):
        self._shift(self.emp, self.day)
        data = self._data()
        self.assertIn('missing_punch', self._flags(data, self.emp, self.day))
        self.assertEqual(data['stats']['missing'], 1)
        self.assertFalse(data['can_lock'])

    def test_an_open_punch_is_a_missing_checkout(self):
        self._shift(self.emp, self.day)
        self.Att.create({
            'employee_id': self.emp.id,
            'check_in': datetime.combine(self.day, time(8, 0)),
            'pb_entry_source': 'grid'})
        self.assertIn('missing_checkout', self._flags(self._data(), self.emp))

    def test_a_punch_outside_tolerance_is_flagged_and_inside_it_is_not(self):
        """The tolerance is about the EDGES of the day: 20 minutes late is a
        compliance question, two hours short in the middle is a lunch break."""
        # 8 minutes late — inside the 10-minute tolerance
        self._shift(self.emp, self.day)
        att = self.Att.create({
            'employee_id': self.emp.id,
            'check_in': datetime.combine(self.day, time(8, 8)),
            'check_out': datetime.combine(self.day, time(16, 8)),
            'pb_entry_source': 'grid'})
        self.assertNotIn('variance_over', self._flags(self._data(), self.emp))

        # 25 minutes late — outside it
        att.write({
            'check_in': datetime.combine(self.day, time(8, 25)),
            'check_out': datetime.combine(self.day, time(16, 25))})
        self.assertIn('variance_over', self._flags(self._data(), self.emp))

    def test_a_punch_with_no_shift_is_an_unscheduled_day(self):
        self._punch(self.emp, self.day, start_h=9, hours=6.0)
        self.assertIn('unscheduled_day', self._flags(self._data(), self.emp))

    def test_a_submitted_overtime_request_flags_its_day(self):
        self._shift(self.emp, self.day)
        self._punch(self.emp, self.day)
        req = self.OT.sudo().create({
            'employee_id': self.emp.id, 'date': self.day,
            'overtime_type': 'weekday', 'planned_hours': 2.0,
            'actual_hours': 2.0, 'reason': 'x',
            'company_id': self.company.id})
        req.action_submit()
        self.assertIn('ot_pending', self._flags(self._data(), self.emp))
        # …and once decided it stops flagging
        req.action_approve()
        self.assertNotIn('ot_pending', self._flags(self._data(), self.emp))

    def test_a_pending_ot_on_an_otherwise_empty_day_still_surfaces(self):
        """The rest-day skip must not swallow the week's most anomalous row: an
        overtime claim with neither a shift nor a punch behind it."""
        req = self.OT.sudo().create({
            'employee_id': self.emp.id, 'date': self.day2,
            'overtime_type': 'weekday', 'planned_hours': 3.0,
            'actual_hours': 3.0, 'reason': 'x', 'company_id': self.company.id})
        req.action_submit()
        self.assertIn('ot_pending', self._flags(self._data(), self.emp, self.day2))

    def test_a_validated_leave_day_is_excused_not_missing(self):
        """An approved absence IS the explanation. Flagging it would make every
        holiday an exception, which is how officers learn to ignore a board."""
        self._shift(self.emp, self.day)
        self.assertIn('missing_punch', self._flags(self._data(), self.emp))
        leave_type = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', 'no')], limit=1)
        if not leave_type:
            self.skipTest('no allocation-free leave type on this database')
        try:
            leave = self.env['hr.leave'].sudo().create({
                'employee_id': self.emp.id,
                'holiday_status_id': leave_type.id,
                'request_date_from': self.day,
                'request_date_to': self.day})
            leave.sudo().write({'state': 'validate'})
        except Exception:
            self.skipTest('hr_holidays refused the fixture on this database')
        self.assertNotIn('missing_punch', self._flags(self._data(), self.emp))

    def test_the_week_tolerance_produces_ONE_row_not_seven(self):
        """Eight minutes off on each of five days is inside the per-punch
        tolerance every single time and forty minutes off over the week. That
        is one fact about one person (deviation D2) — surfacing it as five
        identical rows would bury the days that really need attention."""
        for i in range(5):
            d = self.week_start + timedelta(days=i)
            self._shift(self.emp, d)
            ci = datetime.combine(d, time(8, 0))
            self.Att.create({
                'employee_id': self.emp.id, 'check_in': ci,
                'check_out': ci + timedelta(hours=7, minutes=52),
                'pb_entry_source': 'grid'})
        data = self._data()
        kinds = [r['kind'] for r in data['flagged']
                 if r['employee_id'] == self.emp.id]
        self.assertEqual(kinds.count('week_variance'), 1)
        self.assertNotIn('variance_over', kinds,
                         'no individual day busted the per-punch tolerance')

    def test_a_day_with_two_problems_produces_two_rows(self):
        """The officer waives PROBLEMS, not days — a single row would make
        "approve as-is" a decision about something they did not read."""
        self._shift(self.emp, self.day)
        self.Att.create({                       # 30 min late AND never punched out
            'employee_id': self.emp.id,
            'check_in': datetime.combine(self.day, time(8, 30)),
            'pb_entry_source': 'grid'})
        kinds = self._flags(self._data(), self.emp, self.day)
        self.assertIn('variance_over', kinds)
        self.assertIn('missing_checkout', kinds)
        self.assertEqual(
            len([r for r in self._data()['flagged']
                 if r['employee_id'] == self.emp.id
                 and r['date'] == self.day.isoformat()]), 2)

    # ==================================================================
    #  reviews
    # ==================================================================
    def test_a_reviewed_flag_stops_blocking_the_lock(self):
        self._shift(self.emp, self.day)
        data = self._data()
        self.assertEqual(data['stats']['flagged'], 1)
        self.assertFalse(data['can_lock'])

        self.Close.sudo().review_flag(
            self.emp.id, self.day, 'missing_punch', 'sick, phoned in')

        data = self._data()
        self.assertEqual(data['stats']['flagged'], 0)
        self.assertEqual(data['stats']['reviewed'], 1)
        self.assertTrue(data['can_lock'])
        # …and the row is STILL on the board, so a closed week can answer
        # "what did you decide about this?"
        row = [r for r in data['flagged'] if r['employee_id'] == self.emp.id][0]
        self.assertTrue(row['reviewed'])
        self.assertEqual(row['review_note'], 'sick, phoned in')

    def test_reviewing_the_same_flag_twice_is_idempotent(self):
        self._shift(self.emp, self.day)
        a = self.Close.sudo().review_flag(self.emp.id, self.day, 'missing_punch')
        b = self.Close.sudo().review_flag(self.emp.id, self.day, 'missing_punch')
        self.assertEqual(a, b)
        self.assertEqual(self.Review.sudo().search_count([
            ('employee_id', '=', self.emp.id), ('date', '=', self.day)]), 1)

    def test_a_review_survives_a_reopen(self):
        """Reopening a week ADDS to its history; it does not erase the fact that
        somebody looked at these seven flags."""
        self._shift(self.emp, self.day)
        self.Close.sudo().review_flag(self.emp.id, self.day, 'missing_punch')
        self._lock()
        self._unlock()
        self.assertEqual(self._data()['stats']['reviewed'], 1)

    def test_an_officer_cannot_waive_a_flag(self):
        """§3.4: waiving is what lets a week reach payroll — the same authority
        as locking it. The gate is on the MODEL, so the facade cannot be softer."""
        self._shift(self.emp, self.day)
        officer = self._officer('p4_review_officer')
        with self.assertRaises(AccessError):
            self.Close.with_user(officer).review_flag(
                self.emp.id, self.day, 'missing_punch')
        # …and the payload SAYS so, so the lens never offers a button the
        # server would refuse (the W47 rule).
        theirs = self.Close.with_user(officer).get_close_data(
            department_id=self.dept.id, week_start=self.week_start.isoformat())
        self.assertFalse(theirs['can_review'])
        self.assertFalse(theirs['can_manage_locks'])
        self.assertTrue(self._data()['can_review'],
                        'a manager/admin must still be offered it')

    def test_a_manager_cannot_waive_a_flag_on_their_own_attendance(self):
        """The P1a `_ot_can_decide` spirit: that is signing off on your own
        payslip inputs."""
        manager = self._manager('p4_selfreview_manager')
        self.emp.sudo().write({'user_id': manager.id})
        self._shift(self.emp, self.day)
        with self.assertRaises(AccessError):
            self.Close.with_user(manager).review_flag(
                self.emp.id, self.day, 'missing_punch')
        self.assertFalse(self.Review.sudo().search_count(
            [('employee_id', '=', self.emp.id)]))
        # …but somebody else's row is fine
        self._shift(self.emp2, self.day)
        self.Close.with_user(manager).review_flag(
            self.emp2.id, self.day, 'missing_punch')

    def test_an_unknown_flag_kind_is_refused(self):
        with self.assertRaises(UserError):
            self.Close.sudo().review_flag(self.emp.id, self.day, 'nonsense')

    # ==================================================================
    #  gates and scope
    # ==================================================================
    def test_a_non_officer_cannot_read_the_board(self):
        plain = self._mk_user('p4_plain', [])
        with self.assertRaises(AccessError):
            self.Close.with_user(plain).get_close_data(
                week_start=self.week_start.isoformat())

    def test_the_board_is_scoped_to_the_active_companies(self):
        """`allowed_company_ids` is pinned explicitly, because `res.company.
        create()` ADDS the new company to the creating user's allowed set — so
        a test that just creates one and looks is testing nothing (found in
        P4's own run: the twin assertion below passed vacuously)."""
        other = self.env['res.company'].create({'name': 'P4 Foreign Co'})
        foreign = self.env['hr.employee'].sudo().create({
            'name': 'P4 Foreigner', 'company_id': other.id, 'tz': 'UTC'})
        # a shift with no punch — so this row WOULD flag if scoping failed
        self._shift(foreign, self.day)
        data = self.Close.with_context(
            allowed_company_ids=[self.company.id]).get_close_data(
                week_start=self.week_start.isoformat())
        self.assertNotIn(foreign.id,
                         [r['employee_id'] for r in data['flagged']])

    def test_review_flag_refuses_a_foreign_employee(self):
        other = self.env['res.company'].create({'name': 'P4 Foreign Co 2'})
        foreign = self.env['hr.employee'].sudo().create({
            'name': 'P4 Foreigner 2', 'company_id': other.id, 'tz': 'UTC'})
        with self.assertRaises(UserError):
            self.Close.sudo().with_context(
                allowed_company_ids=[self.company.id]).review_flag(
                    foreign.id, self.day, 'missing_punch')

    # ==================================================================
    #  locks on the board
    # ==================================================================
    def test_the_day_chips_report_the_lock_state(self):
        self._lock(self.day)
        data = self._data()
        chips = {d['iso']: d['locked'] for d in data['days']}
        self.assertTrue(chips[self.day.isoformat()])
        self.assertFalse(chips[self.day2.isoformat()])
        self.assertEqual(data['stats']['days_locked'], 1)

    def test_lock_days_and_unlock_days_go_through_the_manager_gate(self):
        officer = self._officer('p4_cta_officer')
        with self.assertRaises(AccessError):
            self.Close.with_user(officer).lock_days([self.day.isoformat()])
        manager = self._manager('p4_cta_manager')
        self.Close.with_user(manager).lock_days(
            [self.day.isoformat()], 'week 33 closed')
        self.assertTrue(self.Lock._is_locked(self.company, self.day))
        with self.assertRaises(UserError):
            self.Close.with_user(manager).unlock_days(
                [self.day.isoformat()], '')
        self.Close.with_user(manager).unlock_days(
            [self.day.isoformat()], 'payroll query')
        self.assertFalse(self.Lock._is_locked(self.company, self.day))

    # ==================================================================
    #  the handoff rail
    # ==================================================================
    def test_the_handoff_totals_are_aggregates_only(self):
        self._shift(self.emp, self.day)
        self._punch(self.emp, self.day, hours=8.0)
        req = self.OT.sudo().create({
            'employee_id': self.emp.id, 'date': self.day2,
            'overtime_type': 'weekday', 'planned_hours': 2.0,
            'actual_hours': 2.0, 'reason': 'x',
            'company_id': self.company.id})
        req.action_submit()
        req.action_approve()

        h = self._data()['handoff']
        self.assertAlmostEqual(h['regular'], 8.0, places=2)
        self.assertGreater(h['overtime'] + h['bonus'], 0)
        # no per-person rate ever leaves the facade (W12)
        self.assertNotIn('rates', h)
        self.assertIn('rate_missing', h)

    def test_the_checklist_answers_the_four_questions(self):
        keys = [c['key'] for c in self._data()['checklist']]
        self.assertEqual(keys, ['ot', 'corrections', 'flags', 'locks'])

    # ==================================================================
    #  the payload's shape contracts
    # ==================================================================
    def test_the_capped_table_carries_the_true_total(self):
        """W45: a capped read that reports len(items) tells the officer the
        backlog is shrinking while it grows."""
        data = self._data()
        self.assertIn('flagged_total', data)
        self.assertIn('flagged_shown', data)
        self.assertLessEqual(data['flagged_shown'], data['flagged_total'])

    def test_the_tolerance_travels_with_the_payload(self):
        """The stat strip says "within 10-min tolerance" out loud — a hardcoded
        10 in the template would keep saying it after an admin changed it."""
        t = self._data()['tolerance']
        self.assertEqual(t['minutes'], 10)
        self.assertAlmostEqual(t['hours_week'], 0.5, places=6)
