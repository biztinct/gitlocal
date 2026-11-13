# -*- coding: utf-8 -*-
"""CLOCK-2 handover §6 — the receiver (cases 1–9, 12–16, 18, 19).

Cases 10–11 (commands, time sync) are in `test_commands.py`, 17 (D11) in
`test_d11.py`, the real HTTP route in `test_iclock_http.py`. Serials are
invented (ledger rule 13).
"""
import os
import re
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from odoo.addons.pb_clock.models import clock_adms

from .common import AdmsCase

LOGGER = 'odoo.addons.pb_clock.models.clock_adms'


@tagged('post_install', '-at_install', 'pb_clock')
class TestIclock(AdmsCase):

    # =================================================================== 1
    def test_01_unknown_serial_becomes_one_pending_machine(self):
        st, body = self.call('cdata', sn='TSTNEW001', options='all', pushver='2.4.1')
        self.assertEqual((st, body), (403, 'pending'))
        rows = self.Device.search([('serial', '=', 'TSTNEW001')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.state, 'pending')
        self.assertEqual(rows.ip, '203.0.113.7')
        self.assertEqual(rows.firmware, 'push 2.4.1')
        self.assertTrue(rows.first_seen_at)
        self.assertFalse(rows.allowed)
        st, body = self.call('getrequest', sn='TSTNEW001')
        self.assertEqual((st, body), (403, 'pending'))
        self.assertEqual(self.Device.search_count([('serial', '=', 'TSTNEW001')]), 1,
                         "a second call creates no second row")
        self.assertFalse(self.Punch.sudo().search_count([('device_id', '=', rows.id)]))

    def test_01b_bad_serial_is_400(self):
        self.assertEqual(self.call('cdata', sn='ab')[0], 400)
        self.assertEqual(self.call('cdata', sn='bad serial!')[0], 400)
        self.assertEqual(self.call('cdata', sn=None)[0], 400)

    # =================================================================== 2
    def test_02_fifty_pending_at_most(self):
        have = self.Device.search_count([('state', '=', 'pending')])
        self.Device.create([{'name': 'P%04d' % i, 'serial': 'TSTP%04d' % i,
                             'kind': 'terminal', 'state': 'pending',
                             'company_id': self.company.id}
                            for i in range(max(0, 50 - have))])
        with self.assertLogs(LOGGER, level='WARNING') as logs:
            st, body = self.call('cdata', sn='TSTOVER51')
        self.assertEqual((st, body), (403, 'pending'))
        self.assertFalse(self.Device.search([('serial', '=', 'TSTOVER51')]))
        self.assertEqual(len([m for m in logs.output if 'pending machines' in m]), 1)

    # =================================================================== 3
    def test_03_allow_then_handshake(self):
        self.call('cdata', sn='TSTNEW003', options='all', pushver='2.4.1')
        dev = self.Device.search([('serial', '=', 'TSTNEW003')])
        out = self.Lens.allow_device(dev.id, {
            'name': 'Factory 2', 'location': 'Gate', 'tz': 'Asia/Ho_Chi_Minh',
            'history_from': '2026-10-01'})
        self.assertTrue(out.get('ok'), out)
        self.assertEqual(dev.state, 'allowed')
        self.assertTrue(dev.allowed and dev.allowed_at)
        self.assertEqual(dev.company_id, self.company, "placed in the manager's company")
        self.assertEqual(dev.history_from, date(2026, 10, 1))
        st, body = self.call('cdata', sn='TSTNEW003', options='all', pushver='2.4.1')
        self.assertEqual(st, 200)
        lines = body.split('\r\n')
        self.assertEqual(lines[0], 'GET OPTION FROM: TSTNEW003')
        self.assertIn('ATTLOGStamp=0', lines)
        self.assertIn('TimeZone=7', lines)
        self.assertIn('TransFlag=TransData AttLog\tOpLog', lines)
        self.assertIn('Realtime=1', lines)
        self.assertTrue(body.endswith('\r\n'))
        flags = [ln for ln in lines if ln.startswith('TransFlag=')][0]
        self.assertNotIn('UserInfo', flags)
        self.assertNotIn('Fp', flags)

    def test_03b_upload_made_terminal_waits_for_allow(self):
        """A machine an upload created (no Allow yet) is not listened to on
        its first call: it becomes pending (D10)."""
        dev = self.Device.create({'name': 'TSTUPL01', 'serial': 'TSTUPL01',
                                  'kind': 'terminal', 'company_id': self.company.id})
        self.assertEqual(dev.state, 'allowed')
        self.assertEqual(self.call('cdata', sn='TSTUPL01'), (403, 'pending'))
        self.assertEqual(dev.state, 'pending')
        self.assertEqual(self.Device.search_count([('serial', '=', 'TSTUPL01')]), 1)

    # =================================================================== 4/5
    def test_04_attlog_post_and_dedup(self):
        dev = self.allowed()
        cron = self.env.ref('pb_clock.cron_pair_punches')
        Trig = self.env['ir.cron.trigger'].sudo()
        before = Trig.search_count([('cron_id', '=', cron.id)])
        body = '\n'.join([
            self.att('885', '2026-10-28 07:11:00'),
            self.att('885', '2026-10-28 16:40:00', '1'),
            self.att('227', '2026-10-28 19:18:00'),
            self.att('227', '2026-10-29 07:36:00', '1', '15'),
            'this line is garbage',
        ]) + '\n'
        st, text = self.call('cdata', 'POST', body, table='ATTLOG', Stamp='9001')
        self.assertEqual((st, text), (200, 'OK: 5'))
        rows = self.ledger(dev)
        self.assertEqual(len(rows), 4)
        self.assertEqual(set(rows.mapped('source')), {'adms'})
        self.assertEqual(dev.attlog_stamp, '9001')
        self.assertGreater(Trig.search_count([('cron_id', '=', cron.id)]), before,
                           "the pairing job was triggered")
        face = rows.filtered(lambda p: p.verify_mode == '15')
        self.assertEqual(len(face), 1)
        self.assertEqual(face.direction_raw, '1')
        self.assertEqual(face.direction, 'unknown', "direction not trusted by default")
        self.assertEqual(fields.Datetime.to_string(rows[0].punch_local), '2026-10-28 07:11:00')
        self.assertEqual(fields.Datetime.to_string(rows[0].punch_utc), '2026-10-28 00:11:00')
        # 5: the same post again
        st, text = self.call('cdata', 'POST', body, table='ATTLOG', Stamp='9001')
        self.assertEqual((st, text), (200, 'OK: 5'))
        self.assertEqual(len(self.ledger(dev)), 4)
        # nothing paired inline; the job pairs
        self.assertFalse(rows.filtered(lambda p: p.state != 'new'))
        self.run_pairing()
        self.assertEqual(len(self.device_atts(self.e885)), 1)
        self.assertEqual(self.hours(self.device_atts(self.e227)), 12.3)

    def test_04b_trusted_direction(self):
        self.company.pb_clock_trust_direction = True
        dev = self.allowed()
        self.call('cdata', 'POST', self.att('885', '2026-10-28 07:11:00', '0') + '\n' +
                  self.att('885', '2026-10-28 16:00:00', '1'), table='ATTLOG')
        self.assertEqual(self.ledger(dev).mapped('direction'), ['in', 'out'])

    # =================================================================== 6
    def test_06_machine_number_column(self):
        dev = self.allowed()
        body = '885\t2026-10-28 07:11:05\t101\t0\t1\t0\n885\t2026-10-28 16:02:59\t101\t1\t4\t0\n'
        self.assertEqual(self.call('cdata', 'POST', body, table='ATTLOG'), (200, 'OK: 2'))
        rows = self.ledger(dev)
        self.assertEqual([fields.Datetime.to_string(r.punch_local) for r in rows],
                         ['2026-10-28 07:11:05', '2026-10-28 16:02:59'])
        self.assertEqual(rows.mapped('direction_raw'), ['0', '1'])
        self.assertEqual(rows.mapped('verify_mode'), ['1', '4'])
        # two-column and eight-column lines also parse
        body2 = '227\t2026-10-28 07:00:00\n227\t2026-10-28 15:00:00\t0\t1\t0\t0\t0\t0\n'
        self.assertEqual(self.call('cdata', 'POST', body2, table='ATTLOG'), (200, 'OK: 2'))
        self.assertEqual(len(self.ledger(dev)), 4)

    # =================================================================== 7
    def test_07_history_from(self):
        dev = self.allowed(history_from=date(2026, 10, 20))
        body = '\n'.join([self.att('885', '2026-10-19 07:00:00'),
                          self.att('885', '2026-10-19 16:00:00'),
                          self.att('885', '2026-10-21 07:00:00'),
                          self.att('885', '2026-10-21 16:00:00')])
        self.call('cdata', 'POST', body, table='ATTLOG')
        rows = self.ledger(dev)
        old = rows.filtered(lambda p: p.punch_local.date() < date(2026, 10, 20))
        self.assertEqual(set(old.mapped('state')), {'ignored_before_start'})
        self.run_pairing()
        self.run_pairing()
        self.assertEqual(set(old.mapped('state')), {'ignored_before_start'}, "never paired")
        new = rows - old
        self.assertEqual(set(new.mapped('state')), {'paired'})
        atts = self.device_atts(self.e885)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts._pb_local_day(), date(2026, 10, 21))
        d = [x for x in self.Lens.get_lens('2026-10-19')['devices'] if x['id'] == dev.id][0]
        self.assertEqual(d['before_start'], 2)
        lens = self.Lens.get_lens('2026-10-19', filters={'state': 'ignored'})
        self.assertEqual({r['kind'] for r in lens['recent']['rows']}, {'before'},
                         "kept-but-not-paired punches say so, and count as ignored")

    # =================================================================== 8
    def test_08_other_tables_dropped(self):
        dev = self.allowed()
        n_rows = self.Punch.sudo().search_count([])
        for table, body in (('OPERLOG', 'OPLOG 4\t0\t2026-10-28 07:00:00\t0\t0\t0\t0\n'
                                        'OPLOG 5\t0\t2026-10-28 07:01:00\t0\t0\t0\t0\n'),
                            ('USERINFO', 'USER PIN=885\tName=Someone\tPri=0\tPasswd=\tCard=\n'),
                            ('BIODATA', 'BIODATA Pin=885\tNo=0\tIndex=0\tValid=1\tType=1\tTmp=AAAA\n')):
            # assertLogs never sees INFO records under this test runner (even a
            # direct logger.info is lost), so the log call itself is counted
            with patch.object(clock_adms._logger, 'info') as info:
                st, text = self.call('cdata', 'POST', body, table=table, Stamp='77')
                self.assertEqual(st, 200)
                self.assertEqual(text, 'OK: %s' % len([x for x in body.split('\n') if x.strip()]))
                self.assertEqual(info.call_count, 1)
                self.assertIn('dropped unread', info.call_args[0][0])
                self.assertIn(table, info.call_args[0])
                # the same table again today: no second log line
                self.call('cdata', 'POST', body, table=table)
                self.assertEqual(info.call_count, 1)
        self.assertEqual(self.Punch.sudo().search_count([]), n_rows, "zero rows anywhere")
        self.assertEqual(dev.operlog_stamp, '77')
        self.assertEqual(dev.attlog_stamp, '0')

    # =================================================================== 9
    def test_09_getrequest_info(self):
        dev = self.allowed()
        st, text = self.call('getrequest',
                             INFO='Ver 6.60 Apr 28 2017,612,1180,48210,192.168.1.201,10,7,15,0,111')
        self.assertEqual((st, text), (200, 'OK'))
        self.assertEqual(dev.firmware, 'Ver 6.60 Apr 28 2017')
        self.assertEqual(dev.users_count, 612)
        self.assertEqual(dev.fp_count, 1180)
        self.assertEqual(dev.attlog_count, 48210)
        self.assertEqual(dev.lan_ip, '192.168.1.201')
        self.assertEqual(dev.ip, '203.0.113.7')
        self.assertTrue(dev.last_seen_at)

    # ================================================================== 12
    def test_12_blocked_machine(self):
        dev = self.allowed(sn='TSTBLK01')
        dev.state = 'blocked'
        self.env.flush_all()
        stamp = dev.write_date
        n_dev = self.Device.search_count([])
        n_rows = self.Punch.sudo().search_count([])
        for route, method, body, params in (
                ('cdata', 'GET', '', {'options': 'all'}),
                ('cdata', 'POST', self.att('885', '2026-10-28 07:00:00'), {'table': 'ATTLOG'}),
                ('getrequest', 'GET', '', {'INFO': 'x,1,2,3'}),
                ('devicecmd', 'POST', 'ID=1&Return=0&CMD=CHECK', {}),
                ('registry', 'POST', '', {}), ('push', 'GET', '', {}),
                ('ping', 'GET', '', {}), ('whatever', 'GET', '', {})):
            st, _t = self.call(route, method, body, sn='TSTBLK01', **params)
            self.assertEqual(st, 403, route)
        self.env.flush_all()
        self.assertEqual(dev.write_date, stamp, "no writes on a blocked machine")
        self.assertEqual(self.Device.search_count([]), n_dev, "no pending row")
        self.assertEqual(self.Punch.sudo().search_count([]), n_rows)

    # ================================================================== 13
    def test_13_paused_tenant(self):
        dev = self.allowed()
        n_rows = self.Punch.sudo().search_count([])
        n_dev = self.Device.search_count([])
        if 'pb.tenancy' in self.env:
            target = patch.object(type(self.env['pb.tenancy']), 'access_state',
                                  lambda self: {'access': 'suspended', 'access_text': ''})
        else:   # a database without the tenancy module: the door's own check
            target = patch.object(type(self.Adms), '_paused', lambda self: True)
        with target:
            for route, method, body, sn in (
                    ('cdata', 'GET', '', 'TSTA0001'),
                    ('cdata', 'POST', self.att('885', '2026-10-28 07:00:00'), 'TSTA0001'),
                    ('getrequest', 'GET', '', 'TSTA0001'),
                    ('devicecmd', 'POST', 'ID=1&Return=0', 'TSTA0001'),
                    ('cdata', 'GET', '', 'TSTNEW013'), ('ping', 'GET', '', None),
                    ('registry', 'POST', '', 'TSTA0001'), ('anything', 'GET', '', None)):
                self.assertEqual(self.call(route, method, body, sn=sn,
                                           table='ATTLOG'), (403, 'paused'), route)
        self.assertEqual(self.Punch.sudo().search_count([]), n_rows)
        self.assertEqual(self.Device.search_count([]), n_dev, "nothing written")
        self.assertEqual(dev.attlog_stamp, '0')

    # ================================================================== 14
    def test_14_plain_connection(self):
        dev = self.allowed()
        plain = {'ip': '203.0.113.7', 'proto': 'http'}
        self.assertFalse(self.company.pb_clock_allow_plain)
        self.assertEqual(self.call('cdata', meta=plain), (403, 'https required'))
        self.assertEqual(self.call('cdata', 'POST', self.att('885', '2026-10-28 07:00:00'),
                                   meta=plain, table='ATTLOG'), (403, 'https required'))
        self.assertFalse(self.ledger(dev))
        out = self.Lens.save_settings(21, 2, False, True)
        self.assertTrue(out.get('ok'))
        self.assertTrue(self.company.pb_clock_allow_plain)
        st, body = self.call('cdata', meta=plain)
        self.assertEqual(st, 200)
        self.assertTrue(dev.plain_connection)
        self.assertEqual(dev.last_proto, 'http')
        d = [x for x in self.Lens.get_lens('2026-10-26')['devices'] if x['id'] == dev.id][0]
        self.assertTrue(d['plain'])
        # back on a secure connection the chip goes away
        self.call('cdata')
        self.assertFalse(dev.plain_connection)

    # ================================================================== 15
    def test_15_v3_and_unknown_paths(self):
        dev = self.allowed()
        self.assertEqual(self.call('ping', sn=None), (200, 'OK'))
        self.assertEqual(self.call('ping'), (200, 'OK'))
        st, body = self.call('registry', 'POST', 'DeviceType=att', pushver='3.0.1')
        self.assertEqual(st, 200)
        self.assertRegex(body, r'^RegistryCode=[0-9a-f]{16}$')
        self.assertEqual(body, 'RegistryCode=%s' % dev.registry_code)
        self.assertEqual(self.call('registry', 'POST', '')[1], body, "stable code")
        st, body = self.call('push', 'POST', '')
        self.assertEqual(st, 200)
        self.assertIn('PushProtVer=3.0.1', body)
        self.assertIn('ServerVersion=3.0.1', body)
        self.assertIn('ATTLOGStamp=0', body)
        self.assertEqual(self.call('whatever', sn=None), (200, 'OK'))
        self.assertEqual(self.call('querydata'), (200, 'OK'))
        self.assertEqual(self.call('cdata.aspx')[0], 200, "the .aspx spelling")
        # 3.x punches named `transaction` are punches
        self.assertEqual(self.call('cdata', 'POST', self.att('885', '2026-10-28 07:00:00'),
                                   table='transaction'), (200, 'OK: 1'))
        self.assertEqual(len(self.ledger(dev)), 1)

    # ================================================================== 16
    def test_16_limits(self):
        dev = self.allowed()
        big = self.att('885', '2026-10-28 07:00:00') + '\n' + ('x' * (2 * 1024 * 1024 + 10))
        self.assertEqual(self.call('cdata', 'POST', big, table='ATTLOG')[0], 413)
        self.assertEqual(self.call('cdata', 'POST', '', meta={'too_big': True},
                                   table='ATTLOG')[0], 413)
        many = '\n'.join(self.att('885', '2026-10-%02d 07:%02d:%02d' % (1 + i % 28, i % 60, i // 60 % 60))
                         for i in range(5001))
        self.assertEqual(self.call('cdata', 'POST', many, table='ATTLOG')[0], 413)
        self.assertFalse(self.ledger(dev), "nothing written")
        self.assertEqual(dev.attlog_stamp, '0')

    # ================================================================== 18
    def test_18_security(self):
        dev = self.allowed()
        officer = self._user('clk2_officer', ['hr_attendance.group_hr_attendance_officer'])
        manager = self._user('clk2_manager', ['hr_attendance.group_hr_attendance_manager'])
        plain = self._user('clk2_plain', [])
        public = self.env.ref('base.public_user')
        # the receiver writes through sudo on its own models, whoever calls it
        st, _t = self.Adms.with_user(public).handle(
            'cdata', 'POST', {'SN': 'TSTA0001', 'table': 'ATTLOG'},
            self.att('885', '2026-10-28 07:00:00'), dict(self.META))
        self.assertEqual(st, 200)
        self.assertEqual(len(self.ledger(dev)), 1)
        self.Command._queue(dev, 'check', 'CHECK')
        with self.assertRaises(AccessError):
            self.env['pb.clock.command'].with_user(plain).search([]).read(['command'])
            self.env['pb.clock.command'].with_user(plain).check_access('read')
        self.assertTrue(self.env['pb.clock.command'].with_user(officer).search(
            [('device_id', '=', dev.id)]))
        with self.assertRaises(AccessError):
            self.env['pb.clock.command'].with_user(officer).create(
                {'device_id': dev.id, 'command': 'CHECK'})
        Lens = self.env['pb.clock.lens']
        out = Lens.with_user(officer).with_company(self.company).resend_since(dev.id, '2026-10-01')
        self.assertIn('error', out)
        out = Lens.with_user(officer).with_company(self.company).allow_device(dev.id, {'name': 'x'})
        self.assertIn('error', out)
        out = Lens.with_user(manager).with_company(self.company).resend_since(dev.id, '2026-10-01')
        self.assertTrue(out.get('ok'), out)
        self.assertEqual(self.Command.search_count([('device_id', '=', dev.id),
                                                    ('kind', '=', 'resend')]), 1)
        # a pending machine is visible to an officer, but only a manager lets it in
        self.call('cdata', sn='TSTNEW018')
        pend = self.Device.search([('serial', '=', 'TSTNEW018')])
        data = Lens.with_user(officer).with_company(self.company).get_lens('2026-10-26')
        self.assertIn('TSTNEW018', [p['serial'] for p in data['pending']])
        self.assertFalse(data['can_manage'])
        self.assertIn('error', Lens.with_user(officer).ignore_device(pend.id))
        self.assertTrue(Lens.with_user(manager).with_company(self.company)
                        .ignore_device(pend.id).get('ok'))
        self.assertEqual(pend.state, 'blocked')
        self.assertTrue(Lens.with_user(manager).with_company(self.company)
                        .unblock_device(pend.id).get('ok'))
        self.assertEqual(pend.state, 'pending')

    def _user(self, login, groups):
        gids = [self.env.ref('base.group_user').id] + \
            [self.env.ref(g).id for g in groups]
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, gids)]})

    # ================================================================== 19
    def test_19_no_brand_name(self):
        bad = []
        roots = [get_module_path('pb_clock')]
        for root in roots:
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [x for x in dirs if x not in ('__pycache__', 'tests')]
                for f in files:
                    if not f.endswith(('.py', '.js', '.xml', '.po', '.pot', '.scss', '.csv')):
                        continue
                    with open(os.path.join(dirpath, f), encoding='utf-8') as fh:
                        for n, line in enumerate(fh, 1):
                            if re.search(r'\bOdoo\b', line):
                                bad.append('%s:%s' % (f, n))
        po = os.path.join(get_module_path('pb_hr_workforce'), 'i18n', 'vi_VN.po')
        with open(po, encoding='utf-8') as fh:
            for n, line in enumerate(fh, 1):
                if line.startswith('msgstr') and re.search(r'\bOdoo\b', line):
                    bad.append('pb_hr_workforce vi_VN.po:%s' % n)
        self.assertFalse(bad, 'the brand name appears in: %s' % bad)

    # ------------------------------------------------------------ lens
    def test_lens_pending_strip_and_allow_sheet(self):
        self.call('cdata', sn='TSTNEW020', pushver='2.4.1')
        data = self.Lens.get_lens('2026-10-26')
        row = [p for p in data['pending'] if p['serial'] == 'TSTNEW020'][0]
        self.assertEqual(row['ip'], '203.0.113.7')
        self.assertTrue(row['history_from'].endswith('-01'), "first day of the month")
        self.assertTrue(data['zones'])
        self.assertNotIn('TSTNEW020', [d['serial'] for d in data['devices']])
        self.assertIn('error', self.Lens.allow_device(row['id'], {'name': ''}))
        self.assertIn('error', self.Lens.allow_device(row['id'], {'name': 'X', 'tz': 'Mars/Base'}))
        out = self.Lens.allow_device(row['id'], {'name': 'Factory 4 #1', 'tz': 'Asia/Ho_Chi_Minh',
                                                 'history_from': row['history_from']})
        self.assertTrue(out['ok'])
        self.assertIn('Factory 4 #1', out['message'])
        data = self.Lens.get_lens('2026-10-26')
        self.assertNotIn('TSTNEW020', [p['serial'] for p in data['pending']])
        card = [d for d in data['devices'] if d['serial'] == 'TSTNEW020'][0]
        self.assertTrue(card['listening'])
        self.assertEqual(card['history_from'], row['history_from'])
        # allowing twice is refused politely
        self.assertIn('error', self.Lens.allow_device(row['id'], {'name': 'again'}))

    def test_lens_allow_merges_with_the_uploaded_machine(self):
        """A serial an upload already knew: Allow keeps that machine (and its
        punches) and drops the empty pending row."""
        up = self.Device.create({'name': 'TSTMRG01', 'serial': 'TSTMRG01',
                                 'kind': 'terminal', 'company_id': self.company.id})
        self.punch('885', '2026-10-28 07:00', device=up)
        other_company = self.env['res.company'].create({'name': 'CLK other'})
        pend = self.Device.create({'name': 'TSTMRG01', 'serial': 'TSTMRG01', 'kind': 'terminal',
                                   'company_id': other_company.id, 'state': 'pending'})
        out = self.Lens.allow_device(pend.id, {'name': 'Office', 'history_from': '2026-10-01'})
        self.assertTrue(out['ok'], out)
        self.assertFalse(pend.exists())
        self.assertEqual(up.state, 'allowed')
        self.assertTrue(up._listening())
        self.assertEqual(up.name, 'Office')

    def test_rate_warning(self):
        self.allowed()
        with self.assertLogs(LOGGER, level='WARNING') as logs:
            for _i in range(240):
                st, _b = self.call('getrequest')
                self.assertEqual(st, 200, "a busy machine is still answered")
        self.assertEqual(len([m for m in logs.output if 'requests in a minute' in m]), 1)
