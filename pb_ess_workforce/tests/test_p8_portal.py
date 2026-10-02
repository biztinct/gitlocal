# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T1 — the four pages resolve the OWN employee, and degrade cleanly without one."""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .common import EssWorkforceCase


@tagged('post_install', '-at_install')
class TestP8Portal(EssWorkforceCase):

    # ------------------------------------------------------------ identity
    def test_own_employee_is_resolved_from_the_session_user(self):
        self.assertEqual(self._as(self.user_a)._own_employee(), self.emp_a)
        self.assertEqual(self._as(self.user_b)._own_employee(), self.emp_b)

    def test_a_user_without_an_employee_gets_an_empty_state_not_a_crash(self):
        """T1's second half. `get_my_counters` must answer zeros — the /my home
        renders for everybody, including the person HR has not linked yet — while
        the four page facades raise the one UserError the controller turns into
        the styled 'not set up for you' page."""
        ess = self._as(self.user_none)
        self.assertEqual(ess.get_my_counters(),
                         {'shift_pending': 0, 'leave_pending': 0,
                          'overtime_pending': 0})
        for fn in (ess.get_my_schedule, ess.get_my_week,
                   ess.get_my_leave, ess.get_my_overtime):
            with self.assertRaises(Exception):
                fn()

    # ------------------------------------------------------------ schedule
    def test_the_schedule_shows_two_weeks_of_own_published_shifts(self):
        day = self._future_day()
        mine = self._shift(self.emp_a, day, state='published')
        theirs = self._shift(self.emp_b, day, state='published')
        draft = self._shift(self.emp_a, day + timedelta(days=1))

        data = self._as(self.user_a).get_my_schedule()
        ids = [s['id'] for w in data['weeks'] for d in w['days'] for s in d['shifts']]
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids, "another employee's shift reached my schedule")
        self.assertNotIn(draft.id, ids, 'an unpublished shift is not a promise')
        self.assertEqual(len(data['weeks']), 2)

    def test_shift_times_are_the_employees_wall_clock_not_the_stored_utc(self):
        """W63: the column is UTC and the card is local. On a UTC+7 tenant the
        two differ by seven hours, which is a different shift, not a rounding."""
        day = self._future_day()
        shift = self._shift(self.emp_a, day, start=8, end=17, state='published')
        self.assertEqual(shift.start_datetime.hour, 1,
                         'fixture stored the wrong UTC value')
        data = self._as(self.user_a).get_my_schedule()
        card = [s for w in data['weeks'] for d in w['days'] for s in d['shifts']
                if s['id'] == shift.id][0]
        self.assertEqual(card['start'], '08:00')
        self.assertEqual(card['end'], '17:00')

    # ----------------------------------------------------------- timesheet
    def test_my_week_uses_the_hubs_arithmetic_for_my_own_employee(self):
        data = self._as(self.user_a).get_my_week()
        self.assertEqual(data['employee']['id'], self.emp_a.id)
        self.assertEqual(len(data['days']), 7)
        for key in ('sched', 'actual', 'entered', 'delta'):
            self.assertIn(key, data['totals'])

    def test_my_week_agrees_with_the_officer_drawer_for_the_same_person(self):
        """The employee and the officer must be reading the SAME week. Two
        surfaces that answer the same question from two computations is how a
        payroll argument starts."""
        day = self.monday
        self._shift(self.emp_a, day, state='published')
        mine = self._as(self.user_a).get_my_week()
        officer = self.env['pb.time.hub'].sudo()._person_week(self.emp_a)
        self.assertEqual([d['sched'] for d in mine['days']],
                         [d['sched'] for d in officer['days']])
        self.assertEqual(mine['totals']['sched'], officer['totals']['sched'])

    def test_request_fix_files_a_correction_for_me_and_submits_it(self):
        yesterday = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=1)
        res = self._as(self.user_a).request_fix(
            yesterday.isoformat(), 'Badge reader missed me', '08:00', '17:00')
        corr = self.env['hr.attendance.correction'].sudo().browse(res['id'])
        self.assertEqual(corr.employee_id, self.emp_a)
        self.assertEqual(corr.state, 'submitted')
        self.assertEqual(corr.create_uid, self.user_a,
                         'the correction must be filed AS the employee')
        # W63 again: 08:00 local on a UTC+7 tenant is 01:00 stored
        self.assertEqual(corr.new_check_in.hour, 1)

    def test_a_fix_without_times_stays_a_draft_rather_than_being_refused(self):
        yesterday = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=1)
        res = self._as(self.user_a).request_fix(yesterday.isoformat(), 'Please check this day')
        self.assertEqual(res['state'], 'draft')

    def test_a_fix_for_a_future_day_is_refused(self):
        with self.assertRaises(Exception):
            self._as(self.user_a).request_fix(
                self._future_day(3).isoformat(), 'I will be late next week')

    def test_a_fix_with_no_reason_is_refused(self):
        yesterday = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=1)
        with self.assertRaises(Exception):
            self._as(self.user_a).request_fix(yesterday.isoformat(), '   ')

    def test_the_week_marks_the_days_that_already_have_a_fix_under_review(self):
        yesterday = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=1)
        self._as(self.user_a).request_fix(yesterday.isoformat(), 'Missed punch', '08:00')
        wk = self._as(self.user_a).get_my_week()
        day = [d for d in wk['days'] if d['date'] == yesterday.isoformat()]
        if day:            # only when yesterday is inside the current week
            self.assertTrue(day[0]['fix'])
            self.assertFalse(day[0]['can_fix'],
                             'a day already under review must not offer a second filing')

    # --------------------------------------------------------------- leave
    def test_leave_page_returns_own_requests_only(self):
        lt = self.env['hr.leave.type'].sudo().search([], limit=1)
        if not lt:
            self.skipTest('no leave type on this database')
        data = self._as(self.user_a).get_my_leave()
        self.assertEqual(data['employee']['id'], self.emp_a.id)
        self.assertIsInstance(data['requests'], list)
        self.assertIsInstance(data['balances'], list)

    # ------------------------------------------------------------ overtime
    def test_overtime_page_returns_own_requests_only(self):
        ot_mine = self.env['hr.overtime.request'].sudo().create({
            'employee_id': self.emp_a.id, 'company_id': self.company.id,
            'date': self.monday, 'planned_hours': 2.0,
            'overtime_type': 'weekday', 'reason': 'P8 fixture',
        })
        self.env['hr.overtime.request'].sudo().create({
            'employee_id': self.emp_b.id, 'company_id': self.company.id,
            'date': self.monday, 'planned_hours': 2.0,
            'overtime_type': 'weekday', 'reason': 'P8 fixture (other)',
        })
        rows = self._as(self.user_a).get_my_overtime()['rows']
        self.assertEqual([r['id'] for r in rows], [ot_mine.id])

    def test_the_overtime_page_has_no_write_path(self):
        """The page is a record, not a filing door (W50): overtime feeds a money
        input and this phase adds no new way to grow one. A grep over the facade
        is the gate, because behaviour alone cannot prove an ABSENT feature."""
        import inspect
        from ..models import ess_workforce
        src = inspect.getsource(ess_workforce)
        self.assertNotIn("['hr.overtime.request'].sudo().create", src)
        self.assertNotIn("['hr.overtime.request'].create", src)

    # ------------------------------------------------------------ counters
    def test_counters_count_only_my_own_pending_things(self):
        day = self._future_day()
        self._shift(self.emp_a, day, state='published')
        self._shift(self.emp_b, day, state='published')
        self.assertEqual(self._as(self.user_a).get_my_counters()['shift_pending'], 1)
        self.assertEqual(self._as(self.user_b).get_my_counters()['shift_pending'], 1)

    # ================================================== WP-6 live findings
    def test_the_week_badge_never_says_all_confirmed_over_a_pending_shift(self):
        """Found live: a week holding two unconfirmed PAST shifts was crowned
        "All confirmed", because the badge was driven by what the employee could
        still act on rather than by what had actually happened. A control that
        is softer than the fact beneath it has to derive from the fact (W42)."""
        from datetime import timedelta as _td
        past = fields.Date.context_today(self.env['hr.employee']) - _td(days=1)
        monday = self.monday
        if past < monday:
            past = monday
        self._shift(self.emp_a, past, state='published')          # unconfirmable
        future = self._shift(self.emp_a, self._future_day(), state='published')
        future._ess_ack('test')

        week = self._as(self.user_a).get_my_schedule()['weeks'][0]
        self.assertEqual(week['pending'], 0, 'nothing is still actionable')
        self.assertFalse(week['all_acked'],
                         'the badge claimed a week with an unconfirmed shift')
        self.assertLess(week['acked'], week['total'])

    def test_a_leave_type_the_employee_has_nothing_of_is_not_a_tile(self):
        """W64 on the portal: 32 tiles all reading "0.0 days left" is
        configuration, not data, and it buries the one balance that matters.
        Only a type this person has an allocation for, or has taken, is a fact
        about them."""
        types = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', True)])
        if not types:
            self.skipTest('no allocation-based leave type on this database')
        balances = self._as(self.user_a).get_my_leave()['balances']
        self.assertEqual(balances, [],
                         'an employee with no allocations was given tiles')

    def test_the_pending_sentence_is_plural_safe(self):
        """"1 shifts still to confirm" is what an English plural inside a msgid
        buys you, and Vietnamese has no plural form to agree with at all. The
        number is a value, not part of a conjugated noun phrase."""
        self._shift(self.emp_a, self._future_day(), state='published')
        label = self._as(self.user_a).get_my_schedule()['pending_label']
        self.assertNotIn('1 shifts', label)
        self.assertIn('1', label)
