# -*- coding: utf-8 -*-
"""CLOCK-3 handover §9 case 15 — a big history: the pairing job runs again
by itself until nothing waits, and the machine card shows the progress."""
from odoo import fields
from odoo.tests import tagged

from .common import AdmsCase


@tagged('post_install', '-at_install', 'pb_clock')
class TestBackfill(AdmsCase):

    def test_15_backfill_retriggers_and_shows_progress(self):
        Pairing = self.env['pb.clock.pairing']
        dev = self.allowed(sn='TSTB0001', attlog_count=12000)
        vals = []
        for i in range(12000):
            code = '885' if i < 60 else 'B%05d' % i      # mostly numbers nobody has
            day = 1 + (i // 600) % 28
            vals.append({'device_id': dev.id, 'user_code': code, 'source': 'adms',
                         'punch_local': '2026-10-%02d %02d:%02d:%02d' % (
                             day, 6 + (i // 3600) % 12, (i // 60) % 60, i % 60)})
        res = self.Punch.sudo()._ingest(vals)
        self.assertEqual(res['created'], 12000)
        lens = self.Lens.get_lens('2026-10-26')
        card = [d for d in lens['devices'] if d['id'] == dev.id][0]
        self.assertTrue(card['backfill'])
        self.assertEqual(card['backfill']['received'], 12000)
        self.assertEqual(card['backfill']['waiting'], 12000)
        self.assertEqual(card['backfill']['pct'], 0)
        self.assertTrue(lens['attention']['backfill'], "the quiet strip line shows")
        cron = self.env.ref('pb_clock.cron_pair_punches')
        Trigger = self.env['ir.cron.trigger'].sudo()
        runs = 0
        while True:
            before = Trigger.search_count([('cron_id', '=', cron.id)])
            out = Pairing._cron_run()
            runs += 1
            after = Trigger.search_count([('cron_id', '=', cron.id)])
            if not out['retriggered']:
                break
            self.assertEqual(after, before + 1, "the job asked to run again at once")
            # half-way: the card shows how far it is and a time left
            if runs == 1:
                card = [d for d in self.Lens.get_lens('2026-10-26')['devices']
                        if d['id'] == dev.id][0]
                self.assertTrue(card['backfill'])
                self.assertEqual(card['backfill']['waiting'], 7000)
                self.assertEqual(card['backfill']['pct'], 41)
                self.assertIsNotNone(card['backfill']['minutes_left'])
            self.assertLess(runs, 5)
        self.assertEqual(runs, 3, "5 000 + 5 000 + 2 000")
        self.assertFalse(self.Punch.sudo().search_count(
            [('device_id', '=', dev.id), ('state', 'in', ('new', 'matched'))]))
        card = [d for d in self.Lens.get_lens('2026-10-26')['devices'] if d['id'] == dev.id][0]
        self.assertFalse(card['backfill'], "the block disappears when nothing waits")
        self.assertTrue(Pairing._rate_per_min())
        # an idle run does not ask again (no spinning)
        self.assertFalse(Pairing._cron_run()['retriggered'])
        self.assertTrue(fields.Datetime.now())
