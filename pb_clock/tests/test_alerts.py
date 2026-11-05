# -*- coding: utf-8 -*-
"""CLOCK-3 handover §9 cases 1–13 and 19 — the alerts, where they show, the
two emails, and no brand name in any new string.

Every case passes an explicit `now` to the watcher (no clock patching): the
fixture company sits in Asia/Ho_Chi_Minh, 18 Nov 2026 is a Wednesday, 21 Nov a
Saturday. Machine serials are invented (ledger rule 13).
"""
import json
import os
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import AdmsCase

WED_10 = datetime(2026, 11, 18, 3, 0)       # 10:00 in Vietnam, a Wednesday
SAT_13 = datetime(2026, 11, 21, 6, 0)       # 13:00 in Vietnam, a Saturday
ALLOWED = datetime(2026, 11, 1, 0, 0)


@tagged('post_install', '-at_install', 'pb_clock')
class TestAlerts(AdmsCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Alert = cls.env['pb.clock.alert'].sudo()

    # ------------------------------------------------------------ helpers
    def watch(self, now, mail=False):
        return self.Alert._watch(now=now, company_ids=[self.company.id], mail=mail)

    def alerts(self, kind=None, state=None):
        dom = [('company_id', '=', self.company.id)]
        if kind:
            dom.append(('kind', '=', kind))
        if state:
            dom.append(('state', '=', state))
        return self.Alert.search(dom)

    def machine(self, sn, **extra):
        extra.setdefault('allowed_at', ALLOWED)
        extra.setdefault('first_seen_at', ALLOWED)
        return self.allowed(sn=sn, **extra)

    def manager(self, login, lang='en_US', email=None):
        group = self.env.ref('hr_attendance.group_hr_attendance_manager')
        return self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'CLK Manager %s' % login, 'login': login,
            'email': email or '%s@example.com' % login, 'lang': lang,
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [group.id, self.env.ref('base.group_user').id])],
        })

    def clock_mails(self, since_id=0):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'res.company'), ('res_id', '=', self.company.id),
            ('id', '>', since_id)], order='id')

    def last_mail_id(self):
        m = self.env['mail.mail'].sudo().search([], order='id desc', limit=1)
        return m.id or 0

    # ================================================================== 1
    def test_01_silent(self):
        dev = self.machine('TSTS0001', last_seen_at=WED_10 - timedelta(minutes=16))
        self.watch(WED_10)
        rows = self.alerts('silent')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.state, 'open')
        self.assertEqual(rows.device_id, dev)
        self.assertIn('has not called in since', rows.detail)
        self.assertIn('09:44', rows.detail, "the time is the machine's local time")
        self.watch(WED_10 + timedelta(minutes=15))
        self.assertEqual(len(self.alerts('silent')), 1, "one condition = one row")
        dev.last_seen_at = WED_10 + timedelta(minutes=20)
        self.watch(WED_10 + timedelta(minutes=21))
        self.assertEqual(self.alerts('silent').state, 'resolved')
        self.assertTrue(self.alerts('silent').resolved_at)
        # it goes quiet again: the SAME row re-opens
        self.watch(WED_10 + timedelta(minutes=50))
        self.assertEqual(len(self.alerts('silent')), 1)
        self.assertEqual(self.alerts('silent').state, 'open')

    # ================================================================== 2
    def test_02_no_punches(self):
        dev = self.machine('TSTN0001')
        # last punch 06:30 local on Wednesday; at 13:00 local that is 6.5 h
        at = WED_10 + timedelta(hours=3)                       # 13:00 local
        dev.write({'last_seen_at': at, 'last_punch_at': datetime(2026, 11, 17, 23, 30)})
        self.watch(at)
        rows = self.alerts('no_punches')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.day, fields.Date.to_date('2026-11-18'))
        self.assertIn('06:30', rows.detail)
        # a punch arrives → resolved
        dev.last_punch_at = at
        self.watch(at + timedelta(minutes=1))
        self.assertEqual(self.alerts('no_punches').state, 'resolved')
        # a Saturday is not a working day → nothing
        dev2 = self.machine('TSTN0002')
        dev2.write({'last_seen_at': SAT_13, 'last_punch_at': datetime(2026, 11, 20, 23, 30)})
        self.watch(SAT_13)
        self.assertFalse(self.alerts('no_punches').filtered(lambda a: a.device_id == dev2))
        # 05:00 local: before the working day starts → nothing
        dev3 = self.machine('TSTN0003')
        early = datetime(2026, 11, 17, 22, 0)                  # Wed 05:00 local
        dev3.write({'last_seen_at': early, 'last_punch_at': datetime(2026, 11, 17, 10, 0)})
        self.watch(early)
        self.assertFalse(self.alerts('no_punches').filtered(lambda a: a.device_id == dev3))

    # ================================================================== 3
    def test_03_clock(self):
        dev = self.machine('TSTC0001', last_seen_at=WED_10, last_punch_at=WED_10,
                           skew_samples=json.dumps([90, 90, 90]), clock_skew_s=90)
        self.watch(WED_10)
        rows = self.alerts('clock')
        self.assertEqual(len(rows), 1)
        self.assertIn('2 min fast', rows.detail)
        # the clock was set and the new samples are on time → resolved
        cmd = self.Command._queue_set_time(dev, now=WED_10)
        cmd.write({'state': 'done', 'done_at': WED_10 + timedelta(minutes=1)})
        dev.write({'skew_samples': json.dumps([10, 10, 10]), 'clock_skew_s': 10})
        self.watch(WED_10 + timedelta(minutes=5))
        self.assertEqual(self.alerts('clock').state, 'resolved')
        # a queued correction on its way does not raise it either
        dev2 = self.machine('TSTC0002', last_seen_at=WED_10, last_punch_at=WED_10,
                            skew_samples=json.dumps([-300, -300, -300]), clock_skew_s=-300)
        self.Command._queue_set_time(dev2, now=WED_10)
        self.watch(WED_10)
        self.assertFalse(self.alerts('clock').filtered(lambda a: a.device_id == dev2))

    def test_03b_future_punches(self):
        """Three punches dated ahead and ignored today → a clock alert too."""
        dev = self.machine('TSTC0003', last_seen_at=WED_10, last_punch_at=WED_10)
        for i in range(3):
            p = self.Punch.sudo().create([{
                'device_id': dev.id, 'user_code': '885', 'source': 'adms',
                'punch_local': '2026-11-19 0%s:00:00' % (i + 1),
                'received_at': WED_10 - timedelta(minutes=5)}])
            p.write({'state': 'ignored_outlier'})
        self.watch(WED_10)
        rows = self.alerts('clock')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.facet, 'future')
        self.assertIn('3 punches dated in the future', rows.detail)

    # ================================================================== 4
    def test_04_pending(self):
        now = fields.Datetime.now()
        p1 = self.Device.create({'name': 'TSTP0001', 'serial': 'TSTP0001', 'kind': 'terminal',
                                 'company_id': self.company.id, 'state': 'pending',
                                 'first_seen_at': now - timedelta(hours=25),
                                 'last_seen_at': now})
        p2 = self.Device.create({'name': 'TSTP0002', 'serial': 'TSTP0002', 'kind': 'terminal',
                                 'company_id': self.company.id, 'state': 'pending',
                                 'first_seen_at': now - timedelta(hours=30),
                                 'last_seen_at': now})
        young = self.Device.create({'name': 'TSTP0003', 'serial': 'TSTP0003', 'kind': 'terminal',
                                    'company_id': self.company.id, 'state': 'pending',
                                    'first_seen_at': now - timedelta(hours=2),
                                    'last_seen_at': now})
        self.watch(now)
        pend = self.alerts('pending')
        self.assertEqual(set(pend.mapped('device_id').ids), {p1.id, p2.id},
                         "only after 24 hours")
        self.assertNotIn(young, pend.mapped('device_id'))
        # Allow → resolved (the lens looks again at once)
        res = self.Lens.allow_device(p1.id, {'name': 'Gate one', 'tz': 'Asia/Ho_Chi_Minh'})
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(self.alerts('pending').filtered(
            lambda a: a.device_id == p1).state, 'resolved')
        # Block → resolved
        self.assertTrue(self.Lens.ignore_device(p2.id).get('ok'))
        self.assertEqual(self.alerts('pending').filtered(
            lambda a: a.device_id == p2).state, 'resolved')

    # ================================================================== 5
    def _auto_closed_day(self, code, emp):
        self.punch(code, '2026-10-27 07:30')
        self.punch(code, '2026-10-28 07:31')
        self.punch(code, '2026-10-28 16:45')
        self.run_pairing()
        day1 = self.device_atts(emp)[0]
        self.assertTrue(day1.pb_clock_auto_closed)
        return day1

    def test_05_auto_closed(self):
        day1 = self._auto_closed_day('885', self.e885)
        self.watch(self.now)
        rows = self.alerts('auto_closed')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.employee_id, self.e885)
        self.assertEqual(rows.day, fields.Date.to_date('2026-10-27'))
        self.assertIn('has no check-out on Tue 27 Oct', rows.detail)
        # not before two days have passed
        self.watch(datetime(2026, 10, 28, 12, 0))
        self.assertEqual(self.alerts('auto_closed').state, 'resolved')
        self.watch(self.now)
        self.assertEqual(self.alerts('auto_closed').state, 'open')
        # a correction is filed → resolved
        corr = self.env['hr.attendance.correction'].sudo().create({
            'employee_id': self.e885.id, 'date': '2026-10-27',
            'correction_type': 'adjust', 'attendance_id': day1.id,
            'new_check_in': day1.check_in,
            'new_check_out': day1.check_in + timedelta(hours=8),
            'reason': 'Forgot to punch out'})
        self.watch(self.now + timedelta(minutes=15))
        self.assertEqual(self.alerts('auto_closed').state, 'resolved')
        # refused → it needs a person again
        corr.sudo().write({'state': 'refused'})
        self.watch(self.now + timedelta(minutes=30))
        self.assertEqual(self.alerts('auto_closed').state, 'open')

    def test_05b_approved_week_no_alert(self):
        if 'pb.timesheet.packet' not in self.env:
            self.skipTest('pb_timesheet_approval not installed')
        self._auto_closed_day('227', self.e227)
        packet = self.env['pb.timesheet.packet'].sudo().create({
            'employee_id': self.e227.id, 'company_id': self.company.id,
            'week_start': '2026-10-26'})
        self.env.cr.execute("UPDATE pb_timesheet_packet SET state = 'approved' WHERE id = %s",
                            [packet.id])
        packet.invalidate_recordset(['state'])
        self.watch(self.now)
        self.assertFalse(self.alerts('auto_closed').filtered(
            lambda a: a.employee_id == self.e227), "the week was approved: nothing to fix")

    # ================================================================== 6
    def test_06_command_failed(self):
        dev = self.machine('TSTF0001', last_seen_at=WED_10, last_punch_at=WED_10)
        for _i in range(2):
            c = self.Command._queue(dev, 'check', 'CHECK')
            c.write({'state': 'failed', 'done_at': WED_10})
        self.watch(WED_10)
        self.assertEqual(self.alerts('command_failed').state, 'open')
        ok = self.Command._queue(dev, 'check', 'CHECK')
        ok.write({'state': 'done', 'done_at': WED_10 + timedelta(minutes=1)})
        self.watch(WED_10 + timedelta(minutes=2))
        self.assertEqual(self.alerts('command_failed').state, 'resolved')
        # one failure alone is not an alert
        dev2 = self.machine('TSTF0002', last_seen_at=WED_10, last_punch_at=WED_10)
        c = self.Command._queue(dev2, 'check', 'CHECK')
        c.write({'state': 'failed', 'done_at': WED_10})
        self.watch(WED_10)
        self.assertFalse(self.alerts('command_failed').filtered(lambda a: a.device_id == dev2))

    # ================================================================== 7
    def test_07_plain(self):
        dev = self.machine('TSTL0001', last_seen_at=WED_10, last_punch_at=WED_10)
        self.company.pb_clock_allow_plain = True
        self.call('getrequest', sn='TSTL0001', meta={'ip': '203.0.113.7', 'proto': 'http'})
        self.assertTrue(dev.plain_connection)
        self.watch(fields.Datetime.now())
        rows = self.alerts('plain')
        self.assertEqual(rows.state, 'open')
        self.assertIn('plain connection', rows.detail)
        self.call('getrequest', sn='TSTL0001', meta={'ip': '203.0.113.7', 'proto': 'https'})
        self.assertFalse(dev.plain_connection)
        self.watch(fields.Datetime.now())
        self.assertEqual(self.alerts('plain').state, 'resolved')

    # ================================================================== 8
    def test_08_held(self):
        manual = self.Att.sudo().create({
            'employee_id': self.e885.id, 'pb_entry_source': 'grid',
            'check_in': datetime(2026, 11, 2, 1, 0), 'check_out': datetime(2026, 11, 2, 10, 0)})
        self.punch('885', '2026-11-02 07:11')
        self.punch('885', '2026-11-02 20:36')
        self.run_pairing()
        held = self.Punch.sudo().search([('employee_id', '=', self.e885.id),
                                          ('state', '=', 'held')])
        self.assertEqual(len(held), 2)
        # younger than a day: nothing yet
        self.watch(fields.Datetime.now())
        self.assertFalse(self.alerts('held'))
        self.watch(fields.Datetime.now() + timedelta(hours=25))
        rows = self.alerts('held')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.ref_value, 2)
        self.assertIn('2 punches of CLK Worker 885', rows.detail)
        # the person's row goes, the punches pair → resolved
        manual.unlink()
        self.Pairing.repair_employee(self.e885.id, '2026-11-02', '2026-11-02')
        self.watch(fields.Datetime.now() + timedelta(hours=26))
        self.assertEqual(self.alerts('held').state, 'resolved')

    # ================================================================== 9
    def test_09_backlog(self):
        from odoo.addons.pb_clock.models import clock_alert
        with patch.object(clock_alert, 'BACKLOG_HIGH', 20), \
                patch.object(clock_alert, 'BACKLOG_LOW', 5):
            for i in range(25):
                self.punch('U%03d' % i, '2026-11-03 08:%02d' % (i % 60))
            t0 = fields.Datetime.now()
            self.watch(t0)
            self.assertFalse(self.alerts('backlog'), "not before 30 minutes")
            self.assertTrue(self.company.pb_clock_backlog_since)
            self.watch(t0 + timedelta(minutes=31))
            rows = self.alerts('backlog')
            self.assertEqual(rows.state, 'open')
            self.assertEqual(rows.ref_value, 25)
            self.run_pairing()                    # all become unknown numbers
            self.watch(t0 + timedelta(minutes=32))
            self.assertEqual(self.alerts('backlog').state, 'resolved')
            self.assertFalse(self.company.pb_clock_backlog_since)

    # ================================================================= 10
    def test_10_mute(self):
        dev = self.machine('TSTM0001', last_seen_at=WED_10 - timedelta(hours=1))
        self.manager('clkmute')
        self.watch(WED_10)
        alert = self.alerts('silent')
        self.assertEqual(alert.state, 'open')
        res = self.Lens.mute_alerts(alert.ids)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(alert.state, 'muted')
        self.assertGreater(alert.muted_until, fields.Datetime.now() + timedelta(days=6))
        # the rest of the case runs on the fixture's clock
        alert.write({'muted_until': WED_10 + timedelta(days=7)})
        # not shown, not counted
        lens = self.Lens.get_lens('2026-11-16')
        self.assertFalse([i for i in lens['attention']['items'] if alert.id in i['ids']])
        self.assertEqual([m['id'] for m in lens['attention']['muted']], [alert.id])
        # not mailed (the 08:00 summary with only a muted alert sends nothing)
        before = self.last_mail_id()
        self.Alert._watch(now=datetime(2026, 11, 19, 1, 5), company_ids=[self.company.id])
        self.assertFalse(self.clock_mails(before), "a muted alert is never mailed")
        self.assertEqual(alert.state, 'muted')
        # a week later it comes back if the machine is still silent
        self.watch(WED_10 + timedelta(days=7, minutes=15))
        self.assertEqual(alert.state, 'open')
        # an officer may not mute
        officer = self.env['res.users'].sudo().create({
            'name': 'CLK Officer', 'login': 'clkoff', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('hr_attendance.group_hr_attendance_officer').id])]})
        res = self.Lens.with_user(officer).mute_alerts(alert.ids)
        self.assertIn('error', res)
        # bring back from the muted list (the lens looks again on the real clock)
        alert._mute(WED_10)
        dev.last_seen_at = fields.Datetime.now() - timedelta(hours=1)
        self.assertTrue(self.Lens.unmute_alerts(alert.ids).get('ok'))
        self.assertEqual(alert.state, 'open')
        self.assertTrue(dev)

    # ================================================================= 11
    def test_11_digest(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['ir.module.module']._load_module_terms(['pb_clock'], ['vi_VN'], overwrite=True)
        self.env.invalidate_all()
        self.env.registry.clear_cache()
        en = self.manager('clkmgr_en', 'en_US')
        vi = self.manager('clkmgr_vi', 'vi_VN')
        self.e885.work_email = 'worker885@example.com'
        self.machine('TSTD0001', last_seen_at=datetime(2026, 11, 17, 20, 0))
        self.machine('TSTD0002', last_seen_at=datetime(2026, 11, 17, 20, 0))
        # 07:00 local → no summary yet
        before = self.last_mail_id()
        seven = datetime(2026, 11, 18, 0, 0)
        self.Alert._watch(now=seven, company_ids=[self.company.id])
        self.assertFalse(self.company.pb_clock_digest_sent_on)
        self.assertFalse(self.clock_mails(before).filtered(
            lambda m: 'things need attention' in (m.subject or '')))
        # 08:05 local → one summary per company per language
        before = self.last_mail_id()
        eight = datetime(2026, 11, 18, 1, 5)
        self.Alert._watch(now=eight, company_ids=[self.company.id])
        mails = self.clock_mails(before)
        en_subject = 'Time clocks: 2 things need attention'
        digest_en = mails.filtered(lambda m: m.subject == en_subject)
        self.assertEqual(len(digest_en), 1)
        self.assertIn(en.email, digest_en.email_to)
        self.assertNotIn(vi.email, digest_en.email_to)
        self.assertIn('has not called in since', digest_en.body_html)
        self.assertIn('/odoo/action-pb_clock.action_pb_clock_lens', digest_en.body_html)
        digest_vi = (mails - digest_en).filtered(lambda m: vi.email in (m.email_to or '')
                                                  and '2' in (m.subject or '')
                                                  and 'Time clocks: 2 things' not in m.subject)
        self.assertEqual(len(digest_vi), 1, [m.subject for m in mails])
        self.assertNotIn(en.email, digest_vi.email_to)
        self.assertNotIn('has not called in since', digest_vi.body_html,
                         "the Vietnamese manager reads Vietnamese")
        for m in mails:
            self.assertNotIn('worker885@example.com', m.email_to or '')
            self.assertFalse(re.search(r'\bodoo\b', (m.subject or ''), re.I))
            text = re.sub(r'href="[^"]*"', '', m.body_html or '')
            self.assertFalse(re.search(r'\bodoo\b', text, re.I), text)
        # again the same morning → nothing
        before = self.last_mail_id()
        self.Alert._watch(now=eight + timedelta(minutes=30), company_ids=[self.company.id])
        self.assertFalse(self.clock_mails(before).filtered(lambda m: m.subject == en_subject))
        # next morning → one more
        before = self.last_mail_id()
        self.Alert._watch(now=eight + timedelta(days=1), company_ids=[self.company.id])
        self.assertEqual(len(self.clock_mails(before).filtered(
            lambda m: m.subject == en_subject)), 1)

    # ================================================================= 12
    def test_12_immediate_silent_mail(self):
        mgr = self.manager('clkmgr_now', 'en_US')
        self.machine('TSTI0001', last_seen_at=WED_10 - timedelta(minutes=20))
        before = self.last_mail_id()
        self.Alert._watch(now=WED_10, company_ids=[self.company.id])
        now_mails = self.clock_mails(before).filtered(
            lambda m: 'has stopped calling in' in (m.subject or ''))
        self.assertEqual(len(now_mails), 1)
        self.assertIn(mgr.email, now_mails.email_to)
        self.assertTrue(self.alerts('silent').last_mailed_at)
        before = self.last_mail_id()
        self.Alert._watch(now=WED_10 + timedelta(hours=1), company_ids=[self.company.id])
        self.assertFalse(self.clock_mails(before).filtered(
            lambda m: 'has stopped calling in' in (m.subject or '')), "not again within 6 h")
        # on a Saturday no immediate note (the summary carries it)
        self.machine('TSTI0002', last_seen_at=SAT_13 - timedelta(minutes=20))
        before = self.last_mail_id()
        self.Alert._watch(now=SAT_13, company_ids=[self.company.id])
        self.assertFalse(self.clock_mails(before).filtered(
            lambda m: 'TSTI0002' in (m.subject or '') or 'Gate TSTI0002' in (m.subject or '')))

    # ================================================================= 13
    def test_13_surfaces(self):
        mgr = self.manager('clkmgr_surf')
        mgr = mgr.with_context(allowed_company_ids=[self.company.id])
        Hub = self.env['pb.time.hub'].with_user(mgr).with_context(
            allowed_company_ids=[self.company.id])
        # no machine yet: integrations says so, nothing on Home
        self.device.active = False
        if 'pb.integrations' in self.env:
            card = self.env['pb.integrations'].with_user(mgr).with_context(
                allowed_company_ids=[self.company.id])._time_clocks_card()
            self.assertEqual(card['status'], 'disconnected')
        dev = self.machine('TSTH0001', last_seen_at=fields.Datetime.now() - timedelta(hours=1))
        self.Alert._watch(company_ids=[self.company.id], mail=False)
        n = self.Alert.with_context(allowed_company_ids=[self.company.id])._count([self.company.id])
        self.assertGreaterEqual(n, 1)
        s = Hub.get_hub_summary(False, '2026-11-16', False)
        self.assertEqual(s['lens_counts']['clocks'], n, "the badge counts open alerts")
        self.assertEqual(s['ribbon']['extra'], n)
        self.assertIn('time-clock alert', s['ribbon']['text'])
        if not s['open_exceptions']:
            self.assertEqual(s['ribbon']['lens'], 'clocks')
        if 'pb.integrations' in self.env:
            board = self.env['pb.integrations'].with_user(mgr).with_context(
                allowed_company_ids=[self.company.id]).get_board()
            card = board['time_clocks']
            self.assertEqual(card['status'], 'error')
            self.assertEqual([h['kind'] for h in card['hints']], ['machines'])
            self.assertEqual(card['hints'][0]['label'], '1 machine needs attention')
        if 'pb.dashboard' in self.env:
            need = self.Alert.with_user(mgr).with_context(
                allowed_company_ids=[self.company.id])._home_need()
            self.assertEqual(need['n'], n)
            self.assertIn('has not called in', need['text'])
        # it calls in again → all clear everywhere
        dev.last_seen_at = fields.Datetime.now()
        dev.last_punch_at = fields.Datetime.now()
        self.Alert._watch(company_ids=[self.company.id], mail=False)
        s = Hub.get_hub_summary(False, '2026-11-16', False)
        self.assertFalse(s['ribbon']['extra'])
        self.assertEqual(s['lens_counts'].get('clocks', 0), 0,
                         "unknown numbers count again when nothing is open")
        if 'pb.integrations' in self.env:
            card = self.env['pb.integrations'].with_user(mgr).with_context(
                allowed_company_ids=[self.company.id])._time_clocks_card()
            self.assertEqual(card['status'], 'connected')
            self.assertFalse(card['hints'])
        if 'pb.dashboard' in self.env:
            self.assertEqual(self.Alert.with_user(mgr).with_context(
                allowed_company_ids=[self.company.id])._home_need()['n'], 0,
                "the Home chip is hidden at zero")
        # a plain employee (no attendance right) sees nothing anywhere
        plain = self.env['res.users'].sudo().create({
            'name': 'CLK Plain', 'login': 'clkplain', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.assertEqual(self.Alert.with_user(plain)._home_need()['n'], 0)
        self.assertIsNone(self.Alert.with_user(plain)._integrations_card())

    def test_13b_person_alerts_group_in_the_strip(self):
        """Many days missing a check-out read as ONE strip row with its door."""
        self._auto_closed_day('885', self.e885)
        self._auto_closed_day('227', self.e227)
        self.watch(self.now)
        items = self.Alert._items([self.company.id], self.now)
        rows = [i for i in items if i['kind'] == 'auto_closed']
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['ids']), 2)
        self.assertEqual(rows[0]['door'], {'block': 'missing'})
        self.assertIn('2 days are missing a check-out', rows[0]['text'])

    # ================================================================= 19
    def test_19_no_brand_name_in_new_strings(self):
        bad = []
        files = [
            ('pb_clock', 'models/clock_alert.py'), ('pb_clock', 'models/clock_recheck.py'),
            ('pb_clock', 'data/mail_template_data.xml'), ('pb_clock', 'views/clock_actions.xml'),
            ('pb_clock', 'static/src/js/clock_lens.js'), ('pb_clock', 'static/src/xml/clock_lens.xml'),
            ('pb_time_hub', 'learn_manifest.py'),
            ('pb_integrations', 'static/src/xml/integrations.xml'),
        ]
        for module, rel in files:
            base = get_module_path(module)
            path = os.path.join(base, rel) if base else None
            if not path or not os.path.isfile(path):
                continue
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    # identifiers (`odoo.`, `from odoo`, `/odoo/action-`) are fine
                    text = re.sub(r'(from|import) odoo\b|odoo\.|/odoo/', '', line)
                    if re.search(r'\bOdoo\b', text):
                        bad.append('%s/%s:%s' % (module, rel, n))
        for module in ('pb_clock', 'pb_time_hub', 'pb_integrations', 'pb_dashboard', 'pb_learn'):
            base = get_module_path(module)
            po = os.path.join(base, 'i18n', 'vi_VN.po') if base else None
            if po and os.path.isfile(po):
                with open(po, encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        if line.startswith('msgstr') and re.search(r'\bOdoo\b', line):
                            bad.append('%s vi_VN.po:%s' % (module, n))
        base = get_module_path('pb_learn')
        content = os.path.join(base, 'static', 'content', 'learn_content.json') if base else None
        if content and os.path.isfile(content):
            with open(content, encoding='utf-8') as fh:
                data = json.load(fh)
            for s in data.get('screens', []):
                if s.get('key') == 'wfclocks' and re.search(r'\bOdoo\b', json.dumps(s)):
                    bad.append('learn screen wfclocks')
            for s in data.get('scenarios', []):
                if s.get('key') == 'sc_wfclocks' and re.search(r'\bOdoo\b', json.dumps(s)):
                    bad.append('learn scenario sc_wfclocks')
        self.assertFalse(bad, 'the brand name appears in: %s' % bad)
