# -*- coding: utf-8 -*-
"""CLOCK-1 step 1 — a day is the employee-LOCAL day everywhere.

In Vietnam (UTC+7) a 06:30 check-in is stored as 23:30 UTC the day before.
Before CLOCK-1 the Week Grid, the person drawer, the weekly packet and the
freeze keyed a punch by that stored UTC date; the lock and the exception feed
used the local day. These cases pin the new single answer.

Fixtures live in a fresh company so no lock / packet already on the test
database can own these days.
"""
from datetime import date, datetime

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'clock_local_day')
class LocalDayCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'CLK Local Day Co'})
        cls.company.resource_calendar_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id]))
        cls.Att = cls.env['hr.attendance']
        cls.emp = cls.env['hr.employee'].create({
            'name': 'CLK Local Vy', 'company_id': cls.company.id,
            'tz': 'Asia/Ho_Chi_Minh'})
        # 2026-11-04 06:30 local == 2026-11-03 23:30 UTC (a Wednesday)
        cls.att = cls.Att.create({
            'employee_id': cls.emp.id,
            'check_in': datetime(2026, 11, 3, 23, 30),
            'check_out': datetime(2026, 11, 4, 9, 30),
        })

    def test_01_helper_local_day(self):
        self.assertEqual(self.att.check_in.date(), date(2026, 11, 3))
        self.assertEqual(self.att._pb_local_day(), date(2026, 11, 4))

    def test_02_helper_matches_lock(self):
        """Same semantics as pb.wf.lock._local_day (ledger §1)."""
        if 'pb.wf.lock' not in self.env:
            self.skipTest('pb_close not installed')
        self.assertEqual(
            self.env['pb.wf.lock']._local_day(self.emp, self.att.check_in),
            self.att._pb_local_day())

    def test_03_window_covers_local_week(self):
        lo, hi = self.Att._pb_week_window_utc(
            self.emp, date(2026, 11, 2), date(2026, 11, 8))
        # local Mon 00:00 +07 == Sun 17:00 UTC
        self.assertEqual(lo, datetime(2026, 11, 1, 17, 0))
        self.assertEqual(hi.date(), date(2026, 11, 8))
        self.assertEqual((hi.hour, hi.minute), (16, 59))

    def test_04_week_grid_cell_is_local_day(self):
        grid = self.env['hr.attendance.weekentry'].get_week_entries(
            '2026-11-03')
        row = [r for r in grid['rows'] if r['id'] == self.emp.id][0]
        wed = row['cells']['2026-11-04']['measures']['reg']['value']
        tue = row['cells']['2026-11-03']['measures']['reg']['value']
        self.assertEqual(wed, 10.0, "the 06:30 local check-in is Wednesday's")
        self.assertEqual(tue, 0.0, "nothing may show on the UTC date")

    def test_05_monday_early_punch_stays_in_its_week(self):
        """The worst case: Monday 06:30 local is Sunday 23:30 UTC — the
        previous WEEK under the old keying."""
        self.Att.create({
            'employee_id': self.emp.id,
            'check_in': datetime(2026, 11, 1, 23, 30),
            'check_out': datetime(2026, 11, 2, 7, 30),
        })
        grid = self.env['hr.attendance.weekentry'].get_week_entries(
            '2026-11-02')
        row = [r for r in grid['rows'] if r['id'] == self.emp.id][0]
        self.assertEqual(
            row['cells']['2026-11-02']['measures']['reg']['value'], 8.0)
        prev = self.env['hr.attendance.weekentry'].get_week_entries(
            '2026-10-26')
        prow = [r for r in prev['rows'] if r['id'] == self.emp.id][0]
        self.assertEqual(
            prow['cells']['2026-11-01']['measures']['reg']['value'], 0.0)

    def test_06_packet_scan_is_local_day(self):
        Packet = self.env['pb.timesheet.packet'].sudo()
        packet = Packet.create({
            'employee_id': self.emp.id, 'week_start': date(2026, 11, 2),
            'company_id': self.company.id})
        scan = packet._scan_week()
        by_date = {d['date']: d for d in scan['days']}
        self.assertEqual(by_date['2026-11-04']['attendance_ids'], self.att.ids)
        self.assertEqual(by_date['2026-11-03']['attendance_ids'], [])
        self.assertEqual(by_date['2026-11-04']['reg'], 10.0)

    def test_07_freeze_pairs_are_local_day(self):
        self.assertEqual(self.att._pb_week_pairs(),
                         [(self.emp.id, date(2026, 11, 4))])

    def test_08_person_drawer_is_local_day(self):
        if 'pb.time.hub' not in self.env:
            self.skipTest('pb_time_hub not installed')
        drawer = self.env['pb.time.hub']._person_week(self.emp, '2026-11-02')
        days = {d['date']: d for d in drawer['days']}
        self.assertEqual(days['2026-11-04']['entered'], 10.0)
        self.assertEqual(days['2026-11-03']['entered'], 0.0)

    def test_09_week_grid_save_sees_local_rows(self):
        """A grid edit on Wednesday finds the device row (`notgrid`), not an
        empty cell it could write over."""
        WE = self.env['hr.attendance.weekentry']
        grid = WE.get_week_entries('2026-11-02')
        row = [r for r in grid['rows'] if r['id'] == self.emp.id][0]
        token = row['cells']['2026-11-04']['measures']['reg']['token']
        res = WE.save_week_entries({'cells': [{
            'rowId': self.emp.id, 'dayISO': '2026-11-04', 'measure': 'reg',
            'value': 4, 'token': token}]})
        self.assertEqual(res['results'][0]['error'], 'notgrid')
