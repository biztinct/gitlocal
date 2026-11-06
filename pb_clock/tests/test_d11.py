# -*- coding: utf-8 -*-
"""CLOCK-2 handover §6 case 17 — D11: a forgotten check-out never blocks
later days — plus the two CLOCK-1 wording / avatar gaps."""
import os
from datetime import date, datetime

from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import ClockCase


@tagged('post_install', '-at_install', 'pb_clock')
class TestD11(ClockCase):

    # ================================================================== 17
    def test_17_forgotten_checkout_in_one_run(self):
        """Two anchors on consecutive days, the first day with one punch →
        day 1 closed at 0 h and flagged, day 2 paired, nothing held."""
        self.punch('885', '2026-10-27 07:30')
        self.punch('885', '2026-10-28 07:31')
        self.punch('885', '2026-10-28 16:45')
        self.run_pairing()
        atts = self.device_atts(self.e885)
        self.assertEqual(len(atts), 2)
        day1, day2 = atts
        self.assertEqual(day1._pb_local_day(), date(2026, 10, 27))
        self.assertEqual(day1.check_out, day1.check_in)
        self.assertTrue(day1.pb_clock_auto_closed)
        self.assertEqual(day1.worked_hours, 0)
        self.assertFalse(day2.pb_clock_auto_closed)
        self.assertEqual(self.local(day2.check_out), datetime(2026, 10, 28, 16, 45))
        punches = self.Punch.search([('employee_id', '=', self.e885.id)])
        self.assertFalse(punches.filtered(lambda p: p.state == 'held'), "nothing held")
        first = punches.filtered(lambda p: p.punch_local == datetime(2026, 10, 27, 7, 30))
        self.assertEqual(first.state, 'paired')
        self.assertIn('Check-out missing', first.note)
        # idempotent (ledger rule 10)
        self.env.flush_all()
        stamps = [(a.id, a.write_date, a.check_in, a.check_out) for a in atts]
        self.run_pairing()
        self.Pairing.repair_employee(self.e885.id, date(2026, 10, 26), date(2026, 11, 1))
        self.env.flush_all()
        self.assertEqual([(a.id, a.write_date, a.check_in, a.check_out)
                          for a in self.device_atts(self.e885)], stamps)

    def test_17b_forgotten_checkout_across_runs(self):
        """Day 1 was paired (open) by an earlier run; day 2's first punch
        arrives later and closes it."""
        self.punch('227', '2026-10-27 07:30')
        self.run_pairing()
        open_day = self.device_atts(self.e227)
        self.assertFalse(open_day.check_out)
        self.punch('227', '2026-10-28 07:29')
        self.run_pairing()
        atts = self.device_atts(self.e227)
        self.assertEqual(len(atts), 2)
        self.assertEqual(atts[0], open_day)
        self.assertEqual(open_day.check_out, open_day.check_in)
        self.assertTrue(open_day.pb_clock_auto_closed)
        self.assertFalse(atts[1].check_out, "day 2 is open, waiting for its check-out")
        self.assertFalse(self.Punch.search([('employee_id', '=', self.e227.id),
                                            ('state', '=', 'held')]))
        # the lens lists it, with the door to a correction
        lens = self.env['pb.clock.lens'].with_company(self.company).get_lens('2026-10-26')
        rows = lens['missing_checkout']['rows']
        self.assertEqual([(r['employee_id'], r['day']) for r in rows
                          if r['employee_id'] == self.e227.id],
                         [(self.e227.id, '2026-10-27')])
        self.assertEqual(rows[0]['check_in'], '07:30')
        # the late check-out of day 1 turns up after all → the day heals
        self.punch('227', '2026-10-27 16:30')
        self.run_pairing()
        self.assertFalse(open_day.pb_clock_auto_closed)
        self.assertEqual(self.local(open_day.check_out), datetime(2026, 10, 27, 16, 30))

    def test_17c_a_hand_made_open_row_is_never_closed(self):
        """Rule 9: an open row a person made is left alone; the new day is
        held as before."""
        manual = self.Att.create({
            'employee_id': self.e885.id,
            'check_in': datetime(2026, 10, 27, 0, 30),
            'pb_entry_source': 'grid'})
        # an OPEN new day is what the platform refuses next to another open row
        self.punch('885', '2026-10-28 07:31')
        self.run_pairing()
        manual.invalidate_recordset()
        self.assertFalse(manual.check_out)
        self.assertFalse(manual.pb_clock_auto_closed)
        held = self.Punch.search([('employee_id', '=', self.e885.id), ('state', '=', 'held')])
        self.assertTrue(held)

    # ------------------------------------------------------------ CLOCK-1 gaps
    def test_week_grid_lock_sentence(self):
        path = os.path.join(get_module_path('pb_hr_workforce'), 'models',
                            'attendance_weekentry.py')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('Punch from a time clock — change it with a correction', body)
        self.assertNotIn('Device/kiosk punch — edit on the attendance form', body)

    def test_people_search_avatar(self):
        res = self.env['pb.clock.lens'].with_company(self.company).search_people('CLK Worker')
        self.assertTrue(res)
        self.assertTrue(all(r['avatar'].startswith('/web/image') for r in res))
