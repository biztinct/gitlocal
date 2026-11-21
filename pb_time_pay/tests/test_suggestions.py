# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""S5-B T1–T10: overtime suggested from clock punches (owner ruling L6)."""


from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TimePayCase


@tagged('post_install', '-at_install', 'wdgap_s5b')
class TestSuggestions(TimePayCase):

    def _sugg(self, emp, day=None):
        rows, _late = self._week()
        return {(r['date'], r['kind']): r for r in rows
                if r['employee_id'] == emp.id
                and (day is None or r['date'] == day.isoformat())}

    # ------------------------------------------------------------ the maths
    def test_t01_past_the_shift_is_suggested_against_the_shift(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 19)
        got = self._sugg(self.shifty, self.mon)
        row = got[(self.mon.isoformat(), 'weekday')]
        self.assertEqual(row['hours'], 3.0)
        self.assertEqual(row['basis'], 'shift')
        self.assertEqual(row['expected'], 8.0)

    def test_t02_no_shift_compares_with_working_hours(self):
        """L6: no published shift, so the person's normal working hours
        (08:00-17:00, lunch 12-13 = 8 h) are the yardstick; the lunch hour is
        neither worked nor overtime."""
        self._punch(self.office, self.mon, 8, 19)
        got = self._sugg(self.office, self.mon)
        row = got[(self.mon.isoformat(), 'weekday')]
        self.assertEqual(row['basis'], 'hours')
        self.assertEqual(row['expected'], 8.0)
        self.assertEqual(row['hours'], 2.0)

    def test_t03_late_and_staying_late_to_make_up_is_not_overtime(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 9, 17)
        self.assertFalse(self._sugg(self.shifty, self.mon))

    def test_t04_a_rest_day_is_all_overtime(self):
        self._punch(self.office, self.sat, 8, 12)
        got = self._sugg(self.office, self.sat)
        row = got[(self.sat.isoformat(), 'weekend')]
        self.assertEqual(row['hours'], 4.0)
        self.assertEqual(row['basis'], 'rest')

    def test_t05_a_public_holiday_is_public_holiday_overtime(self):
        """Finding 4: the holiday is a company closure."""
        self._closure(self.mon)
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 12)
        got = self._sugg(self.shifty, self.mon)
        row = got[(self.mon.isoformat(), 'holiday')]
        self.assertEqual(row['hours'], 4.0)
        self.assertEqual(row['basis'], 'holiday')
        _rows, late = self._week()
        self.assertFalse([r for r in late if r['employee_id'] == self.shifty.id],
                         'nobody can be late or leave early on a holiday')

    def test_t06_hours_in_the_night_window_are_night_overtime(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 23)
        got = self._sugg(self.shifty, self.mon)
        self.assertEqual(got[(self.mon.isoformat(), 'weekday')]['hours'], 6.0)
        self.assertEqual(got[(self.mon.isoformat(), 'night')]['hours'], 1.0)

    def test_t07_noise_and_rounding(self):
        """Inside the 10-minute Close tolerance: nothing. 40 minutes over:
        rounded DOWN to the quarter hour."""
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 16 + 8 / 60.0)
        self.assertFalse(self._sugg(self.shifty, self.mon))
        self._shift(self.shifty, self.tue)
        self._punch(self.shifty, self.tue, 8, 16 + 40 / 60.0)
        got = self._sugg(self.shifty, self.tue)
        self.assertEqual(got[(self.tue.isoformat(), 'weekday')]['hours'], 0.5)

    def test_t08_typed_grid_hours_are_not_punches(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 19, source='grid')
        self.assertFalse(self._sugg(self.shifty, self.mon))
        _rows, late = self._week()
        self.assertFalse(late)

    # ---------------------------------------------------- accept / dismiss
    def test_t09_accept_makes_an_ordinary_request_and_the_suggestion_goes(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 19)
        payload = self._payload(self.manager_user)
        keys = [r['key'] for r in payload['suggestions']]
        self.assertEqual(len(keys), 1)
        res = self.TP.with_user(self.manager_user).accept_suggestions(
            keys, 'pay', self.dept.id, self.week_start.isoformat(), '')
        self.assertEqual(res['created'], 1, res)
        req = self.OT.sudo().browse(res['request_ids'][0])
        self.assertEqual(req.state, 'submitted')
        self.assertEqual((req.planned_hours, req.actual_hours), (3.0, 3.0))
        self.assertEqual(req.overtime_type, 'weekday')
        self.assertTrue(req.pb_from_punches)
        self.assertNotEqual(req.pb_comp_choice, 'time_off')
        self.assertFalse(self._payload(self.manager_user)['suggestions'],
                         'an accepted suggestion is no longer offered')
        # accepting it again finds nothing to accept
        res = self.TP.with_user(self.manager_user).accept_suggestions(
            keys, 'pay', self.dept.id, self.week_start.isoformat(), '')
        self.assertEqual(res['created'], 0)
        self.assertEqual(len(res['skipped']), 1)

    def test_t09b_accept_as_time_off_carries_the_choice(self):
        self._punch(self.office, self.sat, 8, 12)
        keys = [r['key'] for r in self._payload(self.manager_user)['suggestions']]
        res = self.TP.with_user(self.manager_user).accept_suggestions(
            keys, 'time_off', self.dept.id, self.week_start.isoformat(), '')
        req = self.OT.sudo().browse(res['request_ids'][0])
        self.assertEqual(req.pb_comp_choice, 'time_off')
        self.assertEqual(req.overtime_type, 'weekend')

    def test_t09c_own_and_locked_are_refused_per_row(self):
        self._shift(self.boss, self.mon)
        self._punch(self.boss, self.mon, 8, 19)
        self._shift(self.shifty, self.tue)
        self._punch(self.shifty, self.tue, 8, 19)
        self.env['pb.wf.lock'].sudo().lock_day(self.company.id, self.tue,
                                               'closing')
        rows = self._payload(self.manager_user)['suggestions']
        own = [r for r in rows if r['employee_id'] == self.boss.id]
        locked = [r for r in rows if r['employee_id'] == self.shifty.id]
        self.assertTrue(own and own[0]['own'])
        self.assertTrue(locked and locked[0]['locked'])
        res = self.TP.with_user(self.manager_user).accept_suggestions(
            [own[0]['key'], locked[0]['key']], 'pay', self.dept.id,
            self.week_start.isoformat(), '')
        self.assertEqual(res['created'], 0)
        self.assertEqual(len(res['skipped']), 2, res)

    def test_t10_not_overtime_hides_it_and_keeps_why(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 19)
        key = self._payload(self.manager_user)['suggestions'][0]['key']
        self.TP.with_user(self.manager_user).dismiss_suggestion(
            key, 'meeting ran late, agreed unpaid', self.dept.id,
            self.week_start.isoformat(), '')
        self.assertFalse(self._payload(self.manager_user)['suggestions'])
        mark = self.env['pb.time.ot.dismiss'].sudo().search(
            [('employee_id', '=', self.shifty.id)])
        self.assertEqual(mark.note, 'meeting ran late, agreed unpaid')
        self.assertEqual(mark.hours, 3.0)

    def test_t10b_an_officer_who_cannot_decide_cannot_accept(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 19)
        key = self._payload()['suggestions'][0]['key']
        with self.assertRaises(AccessError):
            self.TP.with_user(self.officer_user).accept_suggestions(
                [key], 'pay', self.dept.id, self.week_start.isoformat(), '')

    def test_t10c_an_existing_request_of_that_kind_suppresses_it(self):
        self._shift(self.shifty, self.mon)
        self._punch(self.shifty, self.mon, 8, 19)
        self._approved(self.shifty, self.mon, 2.0)
        self.assertFalse(self._payload(self.manager_user)['suggestions'])
