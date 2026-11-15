# -*- coding: utf-8 -*-
"""WDGAP S5-A — balances ignore days that have run out (FACTS finding 5).

B1 HR board: an allocation whose validity ended counts no more, nor do the
   days taken from it; with nothing run out the numbers are the old ones.
B2 the employee's tile, the manager's "left after this" and the employee's
   own "after this request" give ONE number.
B3 QF3's over-balance refusal is still right.
B4 the board lists only the companies' own kinds and the shared ones.
B5 a kind whose every day ran out (and none taken since) drops off the page.
"""
from datetime import date, timedelta

from odoo.tests.common import tagged

from .common import LeaveSetupCase


def weekday_before(day, back):
    d = day - timedelta(days=back)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def next_monday(day, weeks=2):
    d = day + timedelta(days=7 * weeks)
    return d - timedelta(days=d.weekday())


@tagged('post_install', '-at_install', 'wdgap_s5a')
class TestBalances(LeaveSetupCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = date.today()
        cls.kind = cls._kind('S5A Counted', request_unit='day',
                             leave_validation_type='no_validation')

    def _board_cell(self, emp, kind):
        TO = self.env['pb.timeoff'].sudo()
        page = 0
        while True:
            board = TO._balances(page)
            for row in board['rows']:
                if row['id'] == emp.id:
                    return row['cells'].get(kind.id)
            if not board['has_more']:
                return None
            page += 1

    def _setup_expired(self, emp):
        # A ran out 40 days ago; 2 days were taken from it while it was valid
        self._alloc(emp, self.kind, 5, self.today - timedelta(days=400),
                    self.today - timedelta(days=40))
        day = weekday_before(self.today, 60)
        self._leave(emp, self.kind, day, day, state='validate')
        day2 = weekday_before(day, 1)
        self._leave(emp, self.kind, day2, day2, state='validate')
        # B is this year's, no end
        self._alloc(emp, self.kind, 10, self.today - timedelta(days=30))

    # ============================================================== B1
    def test_b1_hr_board(self):
        emp = self.emp_portal
        plain = self._emp('S5A No expiry', joined=date(2020, 1, 1))
        self._alloc(plain, self.kind, 7, self.today - timedelta(days=30))
        day = next_monday(self.today)
        self._leave(plain, self.kind, day, day, state='validate')
        nums = self.env['pb.timeoff'].sudo()._pb_balance_numbers([plain.id], [self.kind.id])
        self.assertEqual(nums[(plain.id, self.kind.id)],
                         {'allocated': 7.0, 'taken': 1.0, 'balance': 6.0},
                         'nothing ran out: exactly the old sums')
        self.assertEqual(self.env['pb.timeoff'].sudo()._pb_expired_parts(
            [plain.id], [self.kind.id]), {}, 'and core is not even asked')
        self._setup_expired(emp)
        cell = self._board_cell(emp, self.kind)
        self.assertEqual((cell['allocated'], cell['taken'], cell['balance']), (10.0, 0.0, 10.0),
                         'was 15 given, 2 taken, 13 left')

    # ============================================================== B2
    def test_b2_one_number_everywhere(self):
        emp = self.emp_portal
        self._setup_expired(emp)
        ess = self.env['pb.ess.workforce'].with_user(self.portal_user)
        tile = next(b for b in ess.get_my_leave()['balances'] if b['id'] == self.kind.id)
        self.assertEqual(tile['balance'], 10.0)
        self.assertEqual((tile['allocated'], tile['taken']), (10.0, 0.0))
        # the employee's own preview of a one-day request
        day = next_monday(self.today)
        pv = ess.preview_leave(self.kind.id, day.isoformat(), day.isoformat())
        self.assertEqual(pv['left_before'], 10.0)
        self.assertEqual(pv['after'], 9.0)
        # the manager's "left after this" (core's own reading)
        if 'pb.me.team' in self.env:
            leave = self._leave(emp, self.kind, day, day)
            self.assertEqual(self.env['pb.me.team'].sudo()._balance_after(leave), 9.0)

    # ============================================================== B3
    def test_b3_over_balance_still_refused(self):
        emp = self.emp_portal
        self._setup_expired(emp)
        ess = self.env['pb.ess.workforce'].with_user(self.portal_user)
        start = next_monday(self.today, weeks=3)
        end = start + timedelta(days=17)        # Monday to the Thursday two weeks on: 14 days
        pv = ess.preview_leave(self.kind.id, start.isoformat(), end.isoformat())
        self.assertTrue(pv['over'])
        self.assertTrue(pv['blocked'], 'the days that ran out do not cover it')

    # ============================================================== B4
    def test_b4_board_kinds_of_my_companies(self):
        other = self.env['res.company'].create({'name': 'S5A Other company'})
        theirs = self._kind('S5A Their kind', company_id=other.id)
        board = self.env['pb.timeoff'].sudo().with_context(
            allowed_company_ids=[self.company.id])._balances(0)
        ids = [t['id'] for t in board['types']]
        self.assertIn(self.kind.id, ids)
        self.assertNotIn(theirs.id, ids)

    # ============================================================== B5
    def test_b5_all_ran_out(self):
        emp = self.emp_portal
        k = self._kind('S5A Ran out', leave_validation_type='no_validation')
        self._alloc(emp, k, 3, self.today - timedelta(days=400), self.today - timedelta(days=40))
        ess = self.env['pb.ess.workforce'].with_user(self.portal_user)
        self.assertFalse([b for b in ess.get_my_leave()['balances'] if b['id'] == k.id])
