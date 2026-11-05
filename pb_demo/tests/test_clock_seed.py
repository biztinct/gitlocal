# -*- coding: utf-8 -*-
"""CLOCK-3 handover §9 case 16 — the time-clock demo seed.

A fresh company in Vietnam with 24 people stands in for the demo cohort, so
the case never depends on (or touches) a demo world. "Now" is fixed: Wednesday
18 Nov 2026, 10:00 in Vietnam.
"""
from datetime import datetime, timedelta

from pytz import timezone

from odoo.tests import TransactionCase, tagged

NOW = datetime(2026, 11, 18, 3, 0)


@tagged('post_install', '-at_install', 'pb_demo', 'pb_clock')
class TestClockSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'pb.clock.punch' not in cls.env:
            return
        cls.company = cls.env['res.company'].create({'name': 'DEMO Clock Seed Co'})
        cls.company.resource_calendar_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        Emp = cls.env['hr.employee']
        cls.people = Emp.browse()
        for i in range(24):
            cls.people |= Emp.create({'name': 'DEMO Seed Person %02d' % i,
                                      'company_id': cls.company.id,
                                      'tz': 'Asia/Ho_Chi_Minh'})
        cls.people[5].pb_clock_code = '777'          # a number already given stays
        cls.tz = timezone('Asia/Ho_Chi_Minh')
        # someone with an old forgotten check-out (an OPEN row from August):
        # the seed must not start a day for them that would still be open
        cls.old_open = cls.env['hr.attendance'].sudo().create({
            'employee_id': cls.people[9].id, 'check_in': datetime(2026, 8, 18, 1, 0)})
        # a person-day that already has hours (typed in the grid): never touched
        cls.busy = cls.env['hr.attendance'].sudo().create({
            'employee_id': cls.people[4].id, 'pb_entry_source': 'grid',
            'check_in': datetime(2026, 11, 16, 1, 0), 'check_out': datetime(2026, 11, 16, 9, 0)})

    def seed(self):
        Gen = self.env['pb.demo.generator']
        today = datetime(2026, 11, 18).date()
        monday = today - timedelta(days=today.weekday())
        return Gen._seed_time_clocks(self.people, self.company, self.tz, today, monday, now=NOW)

    def pair(self):
        Pairing = self.env['pb.clock.pairing']
        for _i in range(5):
            res = Pairing.run(company_ids=[self.company.id], now=NOW)
            if not res['more']:
                break

    def test_16_seed(self):
        if 'pb.clock.punch' not in self.env:
            self.skipTest('pb_clock not installed')
        Punch = self.env['pb.clock.punch'].sudo()
        self.env.flush_all()
        busy_stamp = self.busy.write_date
        first = self.seed()
        self.assertTrue(first['device_created'])
        self.assertEqual(first['people'], 24)
        self.assertGreater(first['punches_added'], 400)
        self.assertEqual(first['codes_filled'], 23)
        self.assertEqual(self.people[5].pb_clock_code, '777')
        device = self.env['pb.clock.device'].sudo().search(
            [('company_id', '=', self.company.id), ('serial', '=', 'DEMO-0001')])
        self.assertEqual(len(device), 1)
        self.assertTrue(device.name.startswith('DEMO'))
        self.assertFalse(device.allowed_at, "a punches-by-file machine: never 'silent'")
        self.assertFalse(self.company.pb_clock_alert_mail, "no emails on the demo world")
        total = Punch.search_count([('device_id', '=', device.id)])
        # idempotent: a second run adds nothing
        again = self.seed()
        self.assertEqual(again['punches_added'], 0)
        self.assertFalse(again['device_created'])
        self.assertEqual(Punch.search_count([('device_id', '=', device.id)]), total)
        # nothing is named after a client
        self.assertFalse(Punch.search_count([('device_id', '=', device.id),
                                             ('user_code', 'ilike', 'rize')]))
        self.assertNotIn('RIZE', device.name.upper())
        # pairing makes the days, nothing waits on hold
        self.pair()
        self.assertFalse(Punch.search_count([('device_id', '=', device.id),
                                             ('state', 'in', ('new', 'matched', 'held'))]))
        Att = self.env['hr.attendance'].sudo()
        days = Att.search([('employee_id', 'in', self.people.ids),
                           ('pb_entry_source', '=', 'device')])
        self.assertGreater(len(days), 150)
        # the night shift is one day that crosses midnight
        night = days.filtered(lambda a: a.employee_id == self.people[0] and a.check_out)
        self.assertTrue(night)
        for a in night:
            self.assertGreater(a.check_out.date(), a.check_in.date(), "19:xx → 07:xx")
            self.assertGreater(a.worked_hours, 11)
        # one double tap, one forgotten check-out, one unknown number
        self.assertEqual(Punch.search_count([('device_id', '=', device.id),
                                             ('state', '=', 'ignored_duplicate_tap')]), 1)
        self.assertEqual(len(days.filtered('pb_clock_auto_closed')), 1)
        self.assertEqual(days.filtered('pb_clock_auto_closed').employee_id, self.people[2])
        unknown = Punch.search([('device_id', '=', device.id), ('user_code', '=', 'DEMO-999')])
        self.assertTrue(unknown)
        self.assertEqual(set(unknown.mapped('state')), {'unmatched'})
        # lunch taps are kept and shown, not paid
        self.assertTrue(Punch.search_count([('device_id', '=', device.id),
                                            ('state', '=', 'middle')]))
        # the busy day: untouched, and no punch of that person on it
        self.env.flush_all()
        self.assertEqual(self.busy.write_date, busy_stamp)
        self.assertFalse(days.filtered(lambda a: a.employee_id == self.people[4]
                                       and a.check_in.date() == datetime(2026, 11, 16).date()))
        # the old open row is untouched and stays the only open one
        self.assertFalse(self.old_open.check_out)
        self.assertEqual(Att.search_count([('employee_id', '=', self.people[9].id),
                                           ('check_out', '=', False)]), 1)
        # nothing in the future
        self.assertFalse(Punch.search_count([('device_id', '=', device.id),
                                             ('punch_utc', '>', NOW)]))
        # the lens shows the machine, the unknown number and the forgotten day
        lens = self.env['pb.clock.lens'].with_company(self.company).get_lens('2026-11-16')
        self.assertEqual(lens['hero']['device'], 'DEMO Factory gate')
        self.assertEqual([r['code'] for r in lens['unknown']['rows']], ['DEMO-999'])
        self.assertEqual(lens['missing_checkout']['total'], 1)
