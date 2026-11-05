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
