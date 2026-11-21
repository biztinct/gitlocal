# -*- coding: utf-8 -*-
"""CLOCK-2 handover §6 cases 10–11 — measured time sync and the command
channel (ledger D13)."""
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import tagged

from .common import AdmsCase


@tagged('post_install', '-at_install', 'pb_clock')
class TestCommands(AdmsCase):

    def _live_posts(self, dev, n, offset_s, pin='885', start=0):
        """n realtime posts whose punch time is `offset_s` from now (machine
        clock off by that much)."""
        for i in range(start, start + n):
            local = dev._local_now() + timedelta(seconds=offset_s - i)
            body = self.att(pin, local.strftime('%Y-%m-%d %H:%M:%S'))
            st, text = self.call('cdata', 'POST', body, sn=dev.serial, table='ATTLOG',
                                 Stamp=str(100 + i))
            self.assertEqual((st, text), (200, 'OK: 1'))

    # =================================================================== 10
    def test_10_encoder_known_values(self):
        Dev = type(self.Device)
        self.assertEqual(Dev.zk_encode(datetime(2000, 1, 1, 0, 0, 0)), 0)
        self.assertEqual(Dev.zk_encode(datetime(2000, 1, 2, 0, 0, 0)), 86400)
        self.assertEqual(Dev.zk_encode(datetime(2026, 11, 5, 10, 0, 0)), 862826400)
        self.assertEqual(Dev.zk_decode(862826400), datetime(2026, 11, 5, 10, 0, 0))
        self.assertEqual(Dev.zk_decode(Dev.zk_encode(datetime(2026, 12, 31, 23, 59, 59))),
                         datetime(2026, 12, 31, 23, 59, 59))

    def test_10_skew_measured_and_corrected(self):
        dev = self.allowed(sn='TSTSKW01')
        self._live_posts(dev, 7, -240)
        self.assertLess(abs(dev.clock_skew_s + 243), 10, dev.clock_skew_s)
        self.assertEqual(len(dev._skew_list()), 7)
        cmds = self.Command.search([('device_id', '=', dev.id), ('kind', '=', 'set_time')])
        self.assertEqual(len(cmds), 1, "one command for the whole burst")
        self.assertRegex(cmds.command, r'^SET OPTIONS DateTime=\d+$')
        sent_value = int(cmds.command.split('=')[1])
        told = type(self.Device).zk_decode(sent_value)
        self.assertLess(abs((told - dev._local_now()).total_seconds()), 120,
                        "the command carries the machine's correct LOCAL time")
        # the lens says it in words before the fix
        card = [d for d in self.Lens.get_lens('2026-10-26')['devices'] if d['id'] == dev.id][0]
        self.assertLess(card['skew_s'], -60)
        # the machine polls and gets it
        st, text = self.call('getrequest', sn=dev.serial)
        self.assertEqual(st, 200)
        self.assertEqual(text, 'C:%s:%s' % (cmds.id, cmds.command))
        self.assertEqual(cmds.state, 'sent')
        self.assertEqual(self.call('getrequest', sn=dev.serial), (200, 'OK'),
                         "a sent command is not handed out twice")
        st, text = self.call('devicecmd', 'POST', 'ID=%s&Return=0&CMD=SET' % cmds.id,
                             sn=dev.serial)
        self.assertEqual((st, text), (200, 'OK'))
        self.assertEqual(cmds.state, 'done')
        self.assertTrue(dev.clock_corrected_at)
        self.assertLess(dev.clock_corrected_by_s, -60)
        self.assertEqual(dev._skew_list(), [], "samples reset after the fix")
        # a second burst within six hours queues nothing
        self._live_posts(dev, 7, -300, pin='227')
        self.assertEqual(self.Command.search_count(
            [('device_id', '=', dev.id), ('kind', '=', 'set_time')]), 1)

    def test_10b_on_time_clock_and_backfill_measure_nothing(self):
        dev = self.allowed(sn='TSTSKW02')
        self._live_posts(dev, 5, -5)
        self.assertLess(abs(dev.clock_skew_s), 15)
        self.assertFalse(self.Command.search_count([('device_id', '=', dev.id)]))
        # a backfill of old punches (many lines, months ago) is not a sample
        before = dev._skew_list()
        body = '\n'.join(self.att('885', '2026-09-%02d 07:00:00' % d) for d in range(1, 20))
        self.call('cdata', 'POST', body, sn=dev.serial, table='ATTLOG')
        self.assertEqual(dev._skew_list(), before)

    def test_10c_three_commands_per_poll(self):
        dev = self.allowed(sn='TSTCMD03')
        made = [self.Command._queue(dev, 'check', 'CHECK') for _i in range(5)]
        st, text = self.call('getrequest', sn=dev.serial)
        self.assertEqual(len(text.split('\r\n')), 3)
        self.assertEqual([c.state for c in made], ['sent'] * 3 + ['queued'] * 2)
        # one devicecmd body can close several
        body = '\n'.join('ID=%s&Return=0&CMD=CHECK' % c.id for c in made[:3])
        self.call('devicecmd', 'POST', body, sn=dev.serial)
        self.assertEqual([c.state for c in made[:3]], ['done'] * 3)
        # a command id of another machine is never closed
        other = self.allowed(sn='TSTCMD04')
        self.call('getrequest', sn=dev.serial)
        self.call('devicecmd', 'POST', 'ID=%s&Return=0' % made[3].id, sn=other.serial)
        self.assertEqual(made[3].state, 'sent')

    # =================================================================== 11
    def test_11_resend_since_and_fallback(self):
        dev = self.allowed(sn='TSTRSD01', attlog_stamp='5120')
        out = self.Lens.resend_since(dev.id, '2026-10-01')
        self.assertTrue(out.get('ok'), out)
        cmd = self.Command.search([('device_id', '=', dev.id), ('kind', '=', 'resend')])
        self.assertEqual(len(cmd), 1)
        self.assertTrue(cmd.command.startswith(
            'DATA QUERY ATTLOG StartTime=2026-10-01 00:00:00\tEndTime='))
        self.assertIn('error', self.Lens.resend_since(dev.id, '2026-10-02'),
                      "one resend at a time")
        self.assertIn('error', self.Lens.resend_since(dev.id, '2099-01-01'))
        st, text = self.call('getrequest', sn=dev.serial)
        self.assertEqual(text, 'C:%s:%s' % (cmd.id, cmd.command))
        card = [d for d in self.Lens.get_lens('2026-10-26')['devices'] if d['id'] == dev.id][0]
        self.assertEqual(card['command']['state'], 'sent')
        # the machine refuses
        self.call('devicecmd', 'POST', 'ID=%s&Return=-1&CMD=DATA' % cmd.id, sn=dev.serial)
        self.assertEqual(cmd.state, 'failed')
        self.assertEqual(cmd.return_code, '-1')
        self.assertIn('another way', cmd.note)
        check = self.Command.search([('device_id', '=', dev.id), ('kind', '=', 'check')])
        self.assertEqual(len(check), 1)
        self.assertEqual(check.command, 'CHECK')
        self.assertTrue(check.note)
        self.assertEqual(dev.attlog_stamp, '0', "the machine will send everything again")
        st, body = self.call('cdata', sn=dev.serial, options='all')
        self.assertIn('ATTLOGStamp=0', body)

    def test_11b_no_answer_in_ten_minutes(self):
        dev = self.allowed(sn='TSTRSD02')
        self.Lens.resend_since(dev.id, '2026-10-01')
        cmd = self.Command.search([('device_id', '=', dev.id), ('kind', '=', 'resend')])
        self.call('getrequest', sn=dev.serial)
        self.assertEqual(cmd.state, 'sent')
        later = fields.Datetime.now() + timedelta(minutes=11)
        n = self.Command._sweep(now=later)
        self.assertGreaterEqual(n, 1)
        self.assertEqual(cmd.state, 'failed')
        self.assertIn('No answer', cmd.note)
        self.assertEqual(self.Command.search_count(
            [('device_id', '=', dev.id), ('kind', '=', 'check')]), 1)
        # the pairing job sweeps too (and still pairs)
        self.env['pb.clock.pairing']._cron_run()
