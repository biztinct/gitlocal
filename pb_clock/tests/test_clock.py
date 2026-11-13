# -*- coding: utf-8 -*-
"""CLOCK-1 handover §7 — the ledger, the pairing engine and the lens facade.

Numbered as in the handover; the upload cases (13–15) are in
`test_clock_upload.py`.
"""
from datetime import date, datetime

import pytz

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ClockCase


@tagged('post_install', '-at_install', 'pb_clock')
class TestClockLedger(ClockCase):

    # =================================================================== 1
    def test_01_dedup_same_punches_twice_is_one_row(self):
        times = ['2026-11-03 07:%02d:00' % m for m in range(10)]
        vals = [{'device_id': self.device.id, 'user_code': '885',
                 'punch_local': t} for t in times]
        first = self.Punch._ingest(vals)
        second = self.Punch._ingest(vals)
        rows = self.Punch.search([('company_id', '=', self.company.id)])
        self.assertEqual(len(rows), 10)
        self.assertEqual(first['created'], 10)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['duplicates'], 10)
        # create() hands back the existing row for a repeat, one per input
        again = self.Punch.create(vals[:3])
        self.assertEqual(len(again), 3)
        self.assertEqual(again.ids, first['records'][:3].ids)

    def test_01b_punch_utc_from_device_zone(self):
        p = self.punch('885', '2026-11-04 06:30')
        self.assertEqual(p.punch_utc, datetime(2026, 11, 3, 23, 30))
        self.assertEqual(p.punch_local, datetime(2026, 11, 4, 6, 30))

    def test_01c_clock_code_unique_per_company(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({
                'name': 'CLK dup', 'company_id': self.company.id,
                'pb_clock_code': '227'})

    def test_01d_device_source_counts_as_device(self):
        att = self.Att.create({
            'employee_id': self.e885.id,
            'check_in': datetime(2026, 10, 1, 1, 0),
            'check_out': datetime(2026, 10, 1, 9, 0),
            'pb_entry_source': 'device'})
        self.assertTrue(att._is_device_row())

    # =================================================================== 2
    def test_02_local_day_everywhere(self):
        """06:30 local on 04 Nov = 23:30 UTC on 03 Nov; every surface says
        Wednesday 04 Nov."""
        self.punch('885', '2026-11-04 06:30')
        self.punch('885', '2026-11-04 15:30')
        self.run_pairing()
        att = self.device_atts(self.e885)
        self.assertEqual(len(att), 1)
        self.assertEqual(att.check_in, datetime(2026, 11, 3, 23, 30))
        self.assertEqual(att._pb_local_day(), date(2026, 11, 4))
        grid = self.env['hr.attendance.weekentry'].get_week_entries('2026-11-03')
        row = [r for r in grid['rows'] if r['id'] == self.e885.id][0]
        self.assertEqual(row['cells']['2026-11-04']['measures']['reg']['value'], 9.0)
        self.assertEqual(row['cells']['2026-11-03']['measures']['reg']['value'], 0.0)
        self.assertFalse(row['cells']['2026-11-04']['measures']['reg']['editable'],
                         "a time-clock cell is read-only in the Week Grid")
        if 'pb.timesheet.packet' in self.env:
            packet = self.env['pb.timesheet.packet'].sudo().create({
                'employee_id': self.e885.id, 'week_start': date(2026, 11, 2),
                'company_id': self.company.id})
            days = {d['date']: d for d in packet._scan_week()['days']}
            self.assertEqual(days['2026-11-04']['attendance_ids'], att.ids)
            self.assertEqual(days['2026-11-04']['sources'], ['device'])
            self.assertEqual(att._pb_week_pairs(), [(self.e885.id, date(2026, 11, 4))])

    # =================================================================== 3
    def test_03_night_shift_is_one_day(self):
        self.punch('227', '2026-10-26 19:18')
        self.punch('227', '2026-10-27 07:36')
        self.punch('227', '2026-10-27 19:15')
        self.run_pairing()
        atts = self.device_atts(self.e227)
        self.assertEqual(len(atts), 2)
        first, second = atts
        self.assertEqual(first._pb_local_day(), date(2026, 10, 26))
        self.assertEqual(self.hours(first), 12.3)       # 12 h 18 min
        self.assertEqual(second._pb_local_day(), date(2026, 10, 27))
        self.assertFalse(second.check_out)
        punches = self.Punch.search([('employee_id', '=', self.e227.id)],
                                    order='punch_utc')
        self.assertEqual(punches.mapped('work_day'),
                         [date(2026, 10, 26), date(2026, 10, 26), date(2026, 10, 27)])

    # =================================================================== 4
    def test_04_long_day_shift(self):
        self.punch('885', '2026-10-27 07:30')
        self.punch('885', '2026-10-28 04:00')
        self.run_pairing()
        att = self.device_atts(self.e885)
        self.assertEqual(len(att), 1)
        self.assertEqual(self.hours(att), 20.5)
        self.assertEqual(att._pb_local_day(), date(2026, 10, 27))

    # =================================================================== 5
    def test_05_double_tap_counts_once(self):
        a = self.punch('885', '2026-10-28 07:11:02')
        b = self.punch('885', '2026-10-28 07:11:40')
        c = self.punch('885', '2026-10-28 07:12:30')
        self.run_pairing()
        self.assertEqual(a.state, 'paired')
        self.assertEqual((b | c).mapped('state'),
                         ['ignored_duplicate_tap', 'ignored_duplicate_tap'])
        att = self.device_atts(self.e885)
        self.assertEqual(len(att), 1)
        self.assertEqual(self.local(att.check_in), datetime(2026, 10, 28, 7, 11, 2))
        self.assertFalse(att.check_out)

    # =================================================================== 6
    def test_06_middle_punches_shown_not_paid(self):
        ps = [self.punch('885', '2026-10-29 %s' % t)
              for t in ('07:11', '11:31', '12:29', '20:36')]
        self.run_pairing()
        att = self.device_atts(self.e885)
        self.assertEqual(len(att), 1)
        self.assertEqual(self.local(att.check_in), datetime(2026, 10, 29, 7, 11))
        self.assertEqual(self.local(att.check_out), datetime(2026, 10, 29, 20, 36))
        self.assertEqual([p.state for p in ps],
                         ['paired', 'middle', 'middle', 'paired'])
        self.assertEqual(self.hours(att), 13.42)
        self.assertTrue(all(p.attendance_id == att for p in ps))

    # =================================================================== 7
    def test_07_single_punch_is_an_open_day(self):
        self.punch('885', '2026-10-30 07:11')
        self.run_pairing()
        att = self.device_atts(self.e885)
        self.assertEqual(len(att), 1)
        self.assertFalse(att.check_out)
        rows = self.env['pb.attendance.exception.engine']._get_exceptions(
            self.e885, date(2026, 10, 26), date(2026, 11, 1))
        kinds = {(r['kind'], r['date']) for r in rows}
        self.assertIn(('missing_checkout', '2026-10-30'), kinds)

    # =================================================================== 8
    def test_08_unknown_number_then_assigned(self):
        self.punch('999', '2026-10-28 07:00')
        self.punch('999', '2026-10-28 16:00')
        self.run_pairing()
        unknown = self.Punch.search([('user_code', '=', '999')])
        self.assertEqual(set(unknown.mapped('state')), {'unmatched'})
        if 'pb.clock.lens' not in self.env:
            return
        Lens = self.env['pb.clock.lens']
        self.assertEqual(Lens._unknown_count('2026-10-26'), 1)
        out = Lens.assign_code('999', self.e885.id)
        self.assertFalse(out.get('error'), out)
        self.assertEqual(self.e885.pb_clock_code, '999')
        self.assertEqual(set(unknown.mapped('state')), {'paired'})
        self.assertEqual(len(self.device_atts(self.e885)), 1)
        self.assertEqual(Lens._unknown_count('2026-10-26'), 0)

    # =================================================================== 9
    def test_09_locked_day_holds_the_punch(self):
        if 'pb.wf.lock' not in self.env:
            self.skipTest("pb_close is not installed: no day lock to respect")
        self.punch('885', '2026-11-02 07:00')
        self.punch('885', '2026-11-02 16:00')
        self.run_pairing()
        att = self.device_atts(self.e885)
        before = (att.id, att.check_in, att.check_out)
        self.env['pb.wf.lock'].lock_day(self.company.id, '2026-11-02', 'test')
        late = self.punch('885', '2026-11-02 18:30')
        self.run_pairing()
        att.invalidate_recordset()
        self.assertEqual((att.id, att.check_in, att.check_out), before,
                         "a closed day is never changed by machine data")
        self.assertEqual(late.state, 'held')
        self.assertIn('02 Nov 2026', late.note)

    # ================================================================== 10
    def test_10_manual_entry_wins(self):
        start = self.tz.localize(datetime(2026, 10, 22, 8, 0)).astimezone(
            pytz.UTC).replace(tzinfo=None)
        grid = self.Att.create({'employee_id': self.e885.id, 'check_in': start,
                                'check_out': start.replace(hour=start.hour + 9),
                                'pb_entry_source': 'grid'})
        a = self.punch('885', '2026-10-22 07:11')
        b = self.punch('885', '2026-10-22 20:36')
        self.run_pairing()
        self.assertEqual((a | b).mapped('state'), ['held', 'held'])
        self.assertIn('manual entry exists', a.note)
        self.assertFalse(self.device_atts(self.e885))
        grid.invalidate_recordset()
        self.assertEqual(grid.check_in, start)

    # ================================================================== 11
    def test_11_outlier(self):
        p = self.punch('885', '2000-01-01 07:00')
        f = self.punch('885', '2026-12-31 07:00')     # after the fixed "now"
        self.run_pairing()
        self.assertEqual(p.state, 'ignored_outlier')
        self.assertEqual(f.state, 'ignored_outlier')
        self.assertFalse(self.device_atts(self.e885))

    # ================================================================== 12
    def test_12_idempotent(self):
        for t in ('2026-10-26 19:18', '2026-10-27 07:36', '2026-10-27 19:15'):
            self.punch('227', t)
        for t in ('2026-10-29 07:11', '2026-10-29 11:31', '2026-10-29 20:36'):
            self.punch('885', t)
        self.run_pairing()
        atts = self.device_atts(self.e227) | self.device_atts(self.e885)
        snap = [(a.id, a.check_in, a.check_out, a.write_date) for a in atts]
        punches = self.Punch.search([('company_id', '=', self.company.id)])
        psnap = [(p.id, p.state, p.attendance_id.id, p.work_day, p.write_date)
                 for p in punches]
        self.env.flush_all()
        self.env.cr.execute("SELECT now()")
        second = self.run_pairing()
        self.assertEqual(second['paired_days'], 0)
        self.assertEqual(second['matched'], 0)
        repair = self.Pairing.repair_employee(self.e885.id, '2026-10-26', '2026-11-01')
        self.assertEqual(repair['paired_days'], 0)
        self.assertEqual(repair['held'], 0)
        atts.invalidate_recordset()
        punches.invalidate_recordset()
        self.assertEqual([(a.id, a.check_in, a.check_out, a.write_date) for a in atts], snap)
        self.assertEqual([(p.id, p.state, p.attendance_id.id, p.work_day, p.write_date)
                          for p in punches], psnap)

    # ================================================================ extra
    def test_12b_late_punch_extends_the_day(self):
        """Live pairing (D4): the day opens on the first punch and is updated
        in place when the last one lands."""
        self.punch('885', '2026-10-28 07:05')
        self.run_pairing()
        att = self.device_atts(self.e885)
        self.assertFalse(att.check_out)
        self.punch('885', '2026-10-28 16:40')
        self.run_pairing()
        again = self.device_atts(self.e885)
        self.assertEqual(again, att, "updated in place, not re-created")
        self.assertEqual(self.local(again.check_out), datetime(2026, 10, 28, 16, 40))

    # ================================================================== 16
    def test_16_security(self):
        officer = self._user('clk_officer', ['hr_attendance.group_hr_attendance_officer'])
        manager = self._user('clk_manager', ['hr_attendance.group_hr_attendance_manager'])
        plain = self._user('clk_plain', [])
        p = self.punch('885', '2026-11-03 07:11')
        # an officer reads but cannot write a ledger row at all
        self.assertTrue(p.with_user(officer).read(['user_code']))
        with self.assertRaises(AccessError):
            p.with_user(officer).write({'user_code': '999'})
        # a manager may write the pairing fields, never what the machine said
        with self.assertRaises(UserError):
            p.with_user(manager).write({'user_code': '999'})
        p.with_user(manager).write({'note': 'checked'})
        with self.assertRaises(AccessError):
            p.with_user(manager).unlink()
        # a plain user cannot read the ledger
        with self.assertRaises(AccessError):
            self.Punch.with_user(plain).search([]).read(['user_code'])
            self.Punch.with_user(plain).check_access('read')
        if 'pb.clock.lens' in self.env:
            out = self.env['pb.clock.lens'].with_user(plain).assign_code(
                '999', self.e885.id)
            self.assertIn('error', out)
            self.assertTrue(out['error'])

    def _user(self, login, groups):
        gids = [self.env.ref('base.group_user').id] + \
            [self.env.ref(g).id for g in groups]
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, gids)]})
