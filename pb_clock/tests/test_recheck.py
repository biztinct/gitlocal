# -*- coding: utf-8 -*-
"""CLOCK-3 handover §9 case 14 — the nightly re-check."""
from datetime import datetime, timedelta

from odoo.tests import tagged

from .common import ClockCase

NIGHT = datetime(2026, 11, 19, 19, 35)        # 02:35 on 20 Nov in Vietnam


@tagged('post_install', '-at_install', 'pb_clock')
class TestRecheck(ClockCase):

    def test_14_recheck_restores_and_counts(self):
        Recheck = self.env['pb.clock.recheck']
        self.punch('885', '2026-11-16 07:30')
        self.punch('885', '2026-11-16 16:30')
        self.punch('885', '2026-11-17 07:30')
        self.punch('885', '2026-11-17 16:30')
        self.run_pairing()
        day1, day2 = self.device_atts(self.e885)
        good1 = (day1.check_in, day1.check_out)
        # someone edits both time-clock days by hand (bypassing a correction)
        day1.sudo().write({'check_out': day1.check_out - timedelta(hours=1)})
        edited2 = day2.check_out - timedelta(hours=1)
        day2.sudo().write({'check_out': edited2})
        locked = False
        if 'pb.wf.lock' in self.env:
            self.env['pb.wf.lock'].lock_day(self.company.id, '2026-11-17', 'test')
            locked = True
        # 01:00 local: not the night window yet → nothing runs
        self.assertEqual(Recheck._run_due(now=datetime(2026, 11, 19, 18, 0)), {})
        out = Recheck._run_due(now=NIGHT)
        self.assertEqual(out, {self.company.id: 1})
        self.assertEqual((day1.check_in, day1.check_out), good1, "restored from its punches")
        if locked:
            self.assertEqual(day2.check_out, edited2, "a closed day is never touched")
        self.assertEqual(self.company.pb_clock_last_recheck_fixed, 1)
        self.assertEqual(self.company.pb_clock_last_recheck_at, NIGHT)
        alert = self.env['pb.clock.alert'].sudo().search([
            ('company_id', '=', self.company.id), ('kind', '=', 'recheck_changed')])
        self.assertEqual(alert.state, 'open')
        self.assertIn('changed 1 day', alert.detail)
        # the lens settings card reads it
        lens = self.env['pb.clock.lens'].with_company(self.company).get_lens('2026-11-16')
        self.assertEqual(lens['recheck']['fixed'], 1)
        # once a night only
        self.assertEqual(Recheck._run_due(now=NIGHT + timedelta(minutes=30)), {})
        # the next night is clean → the alert resolves; nothing is written twice
        self.env.flush_all()
        stamp = day1.write_date
        out = Recheck._run_due(now=NIGHT + timedelta(days=1))
        self.assertEqual(out, {self.company.id: 0})
        self.env.flush_all()
        self.assertEqual(day1.write_date, stamp, "idempotent (rule 10)")
        self.assertEqual(alert.state, 'resolved')

    def test_14b_recheck_rebuilds_a_removed_day(self):
        """A time-clock day deleted by hand comes back from its punches."""
        self.punch('227', '2026-11-16 07:00')
        self.punch('227', '2026-11-16 15:00')
        self.run_pairing()
        att = self.device_atts(self.e227)
        self.assertEqual(len(att), 1)
        att.sudo().unlink()
        fixed = self.env['pb.clock.recheck'].run_company(self.company, NIGHT)
        self.assertEqual(fixed, 1)
        self.assertEqual(len(self.device_atts(self.e227)), 1)
