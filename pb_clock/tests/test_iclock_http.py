# -*- coding: utf-8 -*-
"""CLOCK-2 — the REAL route, driven by the emulator (`tools/zk_emulator.py`)
over HTTP: a machine calls in, waits, is let in, handshakes, pushes punches,
polls, takes a command and answers it. Also proves the route is read/write
(an auth='none' route defaults to the read-only cursor on this build), that a
body labelled as a web form still reads, and the plain-connection header.
"""
from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_clock.tools.zk_emulator import ZkEmulator


@tagged('post_install', '-at_install', 'pb_clock')
class TestIclockHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'CLK HTTP Panels'})
        cls.company.resource_calendar_id.tz = 'Asia/Ho_Chi_Minh'
        cls.emp = cls.env['hr.employee'].create({
            'name': 'CLK HTTP 885', 'company_id': cls.company.id,
            'tz': 'Asia/Ho_Chi_Minh', 'barcode': '885'})
        cls.Device = cls.env['pb.clock.device'].sudo().with_context(active_test=False)

    def setUp(self):
        super().setUp()
        self.authenticate(None, None)      # a session that names the database
        from odoo.addons.pb_clock.models import clock_adms
        clock_adms._TABLE_LOGGED.clear()

    def _http(self, extra_headers=None):
        def call(method, url, data=None, headers=None):
            hdrs = {'Content-Type': 'text/plain'}
            hdrs.update(extra_headers or {})
            hdrs.update(headers or {})
            r = self.url_open(url, data=data.encode() if isinstance(data, str) else data,
                              headers=hdrs, method=method, allow_redirects=False)
            return r.status_code, r.text
        return call

    def emu(self, sn, **kw):
        return ZkEmulator(self.base_url(), sn, tz_hours=7, http=self._http(kw.pop('headers', None)),
                          out=False, **kw)

    def test_machine_life_over_http(self):
        emu = self.emu('TSTHTTP01')
        st, body = emu.handshake()
        self.assertEqual((st, body), (403, 'pending'))
        dev = self.Device.search([('serial', '=', 'TSTHTTP01')])
        self.assertEqual(dev.state, 'pending', "written through the read/write cursor")
        self.assertEqual(dev.firmware, 'push 2.4.1')
        # a manager lets it in from the lens
        out = self.env['pb.clock.lens'].with_company(self.company).allow_device(dev.id, {
            'name': 'HTTP gate', 'tz': 'Asia/Ho_Chi_Minh', 'history_from': '2026-10-01'})
        self.assertTrue(out.get('ok'), out)
        st, body = emu.handshake()
        self.assertEqual(st, 200)
        self.assertEqual(emu.options.get('ATTLOGStamp'), '0')
        self.assertEqual(emu.options.get('TimeZone'), '7')
        self.assertEqual(emu.options.get('TransFlag'), 'TransData AttLog\tOpLog')
        self.assertTrue(body.startswith('GET OPTION FROM: TSTHTTP01\r\n'))
        # punches: one before the start day, two after
        emu.add('885', '2026-09-30 07:00:00')
        emu.add('885', '2026-10-28 07:11:00')
        emu.add('885', '2026-10-28 16:40:00', '1')
        st, text = emu.post_held()
        self.assertEqual((st, text), (200, 'OK: 3'))
        Punch = self.env['pb.clock.punch'].sudo()
        rows = Punch.search([('device_id', '=', dev.id)], order='punch_utc')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].state, 'ignored_before_start')
        # poll with INFO, nothing to do
        st, text, results = emu.getrequest()
        self.assertEqual((st, text.strip(), results), (200, 'OK', []))
        self.assertEqual(dev.lan_ip, '192.168.1.201')
        # "Resend since" → the emulator re-posts what it holds and answers
        self.env['pb.clock.lens'].with_company(self.company).resend_since(dev.id, '2026-10-01')
        st, text, results = emu.getrequest()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], 0)
        cmd = self.env['pb.clock.command'].sudo().search([('device_id', '=', dev.id)])
        self.assertEqual(cmd.state, 'done')
        self.assertEqual(Punch.search_count([('device_id', '=', dev.id)]), 3, "resend is harmless")
        # a body labelled as a web form still reads (rebuilt from the fields)
        r = self.url_open(
            '/iclock/cdata?SN=TSTHTTP01&table=ATTLOG&Stamp=9',
            data='885\t2026-10-29 07:02:00\t0\t1\t0\t0\n885\t2026-10-29 16:20:00\t1\t1\t0\t0\n',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST')
        self.assertEqual((r.status_code, r.text), (200, 'OK: 2'))
        self.assertEqual(Punch.search_count([('device_id', '=', dev.id)]), 5)
        self.assertEqual(fields.Datetime.to_string(
            Punch.search([('device_id', '=', dev.id)], order='punch_utc desc', limit=1).punch_local),
            '2026-10-29 16:20:00')
        # unknown path: 200 OK, never a 404
        r = self.url_open('/iclock/whatever?SN=TSTHTTP01')
        self.assertEqual((r.status_code, r.text), (200, 'OK'))
        self.assertTrue(r.headers.get('Content-Type', '').startswith('text/plain'))

    def test_plain_header_and_v3_over_http(self):
        dev = self.Device.create({
            'name': 'HTTP plain', 'serial': 'TSTHTTP02', 'kind': 'terminal',
            'company_id': self.company.id, 'tz': 'Asia/Ho_Chi_Minh', 'state': 'allowed',
            'allowed_at': fields.Datetime.now(), 'first_seen_at': fields.Datetime.now()})
        plain = self.emu('TSTHTTP02', headers={'X-Forwarded-Proto': 'http'})
        self.assertEqual(plain.handshake(), (403, 'https required'))
        self.company.pb_clock_allow_plain = True
        st, _b = plain.handshake()
        self.assertEqual(st, 200)
        self.assertTrue(dev.plain_connection)
        v3 = self.emu('TSTHTTP02')
        ping, reg, push = v3.v3_dance()
        self.assertEqual(ping, (200, 'OK'))
        self.assertEqual(reg[0], 200)
        self.assertTrue(reg[1].startswith('RegistryCode='))
        self.assertEqual(push[0], 200)
        self.assertIn('PushProtVer=3.0.1', push[1])
