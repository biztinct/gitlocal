# -*- coding: utf-8 -*-
"""FLEET P3 — T7 and T8: the sweep and the sender, with the live box taken out.

Everything that would reach the machine is replaced here — the readings, the
outgoing mail, the file nginx serves — which leaves exposed the thing worth
arguing with: a problem is created once, mailed once, reminded about on a
clock, and closed when it stops.

TWO THINGS THIS SUITE HAS TO DO BEFORE IT CAN SAY ANYTHING (both learned the
hard way in P2B, ledger F28 and F29):
  * it runs on a LIVE platform database with real customers and real alerts on
    it, so the fleet and the alert list are stood down inside the transaction —
    which is rolled back and never reaches them;
  * the sweep commits per pass, and a test cursor refuses to commit, so the
    refusal is patched off the INSTANCE (patching the class does nothing).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

HEALTHY = {
    'tenants': [], 'wildcard_cert_days': 90,
    'disk': {'free_pct': 50, 'free_gb': 29.0},
    'memory': {'total_mb': 1907, 'available_mb': 900, 'rss_mb': 565},
    'mail': {'default_from': True, 'failed_recent': 0},
    'rollout': {}, 'master_behind_files': [], 'template_hot_crons': 0,
    'status_page': {'writable': True, 'age_min': 1},
}


@tagged('post_install', '-at_install')
class TestAlerts(TransactionCase):

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        self.cls = type(self.svc)
        self.Alert = self.env['pb.alert'].sudo()
        # The real fleet and the real alert list, stood down inside the
        # transaction (F28) so what is measured here is the machine.
        self.env['pb.tenant'].sudo().search([]).write({'state': 'decommissioned'})
        self.Alert.search([]).write({'state': 'resolved'})
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.alert_emails', 'fleet.test@example.com')
        self.sent = []
        # THE PUBLIC PAGE IS A FILE, AND A FILE IS NOT ROLLED BACK. `alert_ack`
        # and `alert_resolve` rewrite it, so a suite run on the live platform
        # published a page built from the fabricated fleet inside this
        # transaction — harmless the day it was noticed, and one fabricated
        # critical away from advertising an incident that never happened to
        # anybody who opened payobook.com/status. Stood down for the whole
        # class, not just inside `_patches`.
        page = patch.object(type(self.env['pb.tenants']), '_write_status_page',
                            lambda _self: {'ok': True, 'path': '(not written '
                                                               'during tests)'})
        page.start()
        self.addCleanup(page.stop)

    # ------------------------------------------------------------- harness
    def _readings(self, **over):
        data = dict(HEALTHY)
        data.update(over)
        data['now'] = fields.Datetime.now()
        return data

    def _patches(self, readings, sender=None):
        def gather(_self, window_minutes=15):
            return readings() if callable(readings) else readings

        def send(_self, subject, body_html, kind='alert', recipients=None):
            self.sent.append({'subject': subject, 'body': body_html, 'kind': kind})
            return {'ok': True, 'reason': '', 'to': ['fleet.test@example.com']}

        return [
            patch.object(self.cls, '_gather_readings', gather),
            patch.object(self.cls, '_send_alert_mail', sender or send),
            # The page is a file on a live server; writing it is proven on the
            # box at deploy time, not here.
            patch.object(self.cls, '_write_status_page',
                         lambda _self: {'ok': True}),
            # A cron body that commits per pass, in a transaction that must not
            # (F29 — this has to be the INSTANCE, not the class).
            patch.object(self.env.cr, 'commit', lambda: None),
        ]

    def _sweep(self, readings, sender=None):
        pats = self._patches(readings, sender)
        for p in pats:
            p.start()
        try:
            self.svc._cron_alerts()
        finally:
            for p in pats:
                p.stop()

    def _open(self, key=None):
        dom = [('state', 'in', ('open', 'acknowledged'))]
        if key:
            dom.append(('key', '=', key))
        return self.Alert.search(dom)

    # ------------------------------------------------------------------ T7
    def test_t7_01_a_problem_is_created_once_and_mailed_once(self):
        bad = self._readings(disk={'free_pct': 3, 'free_gb': 1.0})
        self._sweep(bad)
        rec = self._open('disk_low')
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.severity, 'critical')
        self.assertEqual(rec.count, 1)
        self.assertTrue(rec.notified_at, "The first sighting has to be mailed.")
        self.assertEqual(len(self.sent), 1)
        self.assertIn('[Payobook]', self.sent[0]['subject'])

        # Same problem, same quarter of an hour later: no second row, NO SECOND
        # EMAIL. This is the whole reason the alert is a record.
        self._sweep(bad)
        rec = self._open('disk_low')
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.count, 2)
        self.assertEqual(len(self.sent), 1)

    def test_t7_02_a_reminder_after_the_interval(self):
        bad = self._readings(disk={'free_pct': 3, 'free_gb': 1.0})
        self._sweep(bad)
        self.assertEqual(len(self.sent), 1)
        rec = self._open('disk_low')
        rec.write({'notified_at': fields.Datetime.now() - timedelta(hours=3)})
        self._sweep(bad)
        self.assertEqual(len(self.sent), 2)
        self.assertIn('Still open', self.sent[1]['subject'])

    def test_t7_03_it_clears_and_says_so(self):
        self._sweep(self._readings(disk={'free_pct': 3, 'free_gb': 1.0}))
        self.assertTrue(self._open('disk_low'))
        self._sweep(self._readings())
        self.assertFalse(self._open('disk_low'))
        closed = self.Alert.search([('key', '=', 'disk_low'),
                                    ('state', '=', 'resolved')], limit=1)
        self.assertTrue(closed.resolved_at)
        self.assertEqual(len(self.sent), 2)
        self.assertIn('Cleared', self.sent[1]['subject'])

    def test_t7_04_a_warning_clearing_is_not_worth_an_email(self):
        warn = self._readings(disk={'free_pct': 9, 'free_gb': 20.0})
        self._sweep(warn)
        self.assertEqual(self._open('disk_low').severity, 'warning')
        self.assertEqual(len(self.sent), 1)
        self._sweep(self._readings())
        self.assertFalse(self._open('disk_low'))
        self.assertEqual(len(self.sent), 1,
                         "A warning going away is not news.")

    def test_t7_05_an_acknowledged_problem_stops_nagging(self):
        bad = self._readings(disk={'free_pct': 3, 'free_gb': 1.0})
        self._sweep(bad)
        rec = self._open('disk_low')
        rec.write({'state': 'acknowledged',
                   'notified_at': fields.Datetime.now() - timedelta(hours=9)})
        self._sweep(bad)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self._open('disk_low').count, 2,
                         "It is still counted, it is simply not shouted about.")

    def test_t7_06_several_new_problems_are_one_email(self):
        self._sweep(self._readings(
            disk={'free_pct': 3, 'free_gb': 1.0},
            memory={'total_mb': 1907, 'available_mb': 90, 'rss_mb': 1600},
            template_hot_crons=9))
        self.assertEqual(len(self._open()), 3)
        self.assertEqual(len(self.sent), 1,
                         "Three problems in one sweep is one email, not three.")
        self.assertIn('3 new problems', self.sent[0]['subject'])

    def test_t7_07_when_the_sender_fails_the_platform_says_so_on_screen(self):
        def broken(_self, subject, body_html, kind='alert', recipients=None):
            _self._channel_down("The mail provider refused the sign-in.")
            return {'ok': False, 'reason': 'refused', 'to': []}

        bad = self._readings(disk={'free_pct': 3, 'free_gb': 1.0})
        self._sweep(bad, sender=broken)
        channel = self._open('alert_channel_down')
        self.assertTrue(channel, "A dead channel must be visible somewhere.")
        self.assertEqual(channel.severity, 'critical')
        self.assertIn('Next:', channel.text)
        self.assertFalse(self._open('disk_low').notified_at,
                         "Nothing may be stamped as told when it was not.")
        # And the sweep that follows must not resolve it just because no
        # reading can see it.
        self._sweep(self._readings(), sender=broken)
        self.assertTrue(self._open('alert_channel_down'))

    def test_t7_08_a_message_getting_through_clears_the_channel_alert(self):
        self.svc._channel_down("The mail provider refused the sign-in.")
        self.assertTrue(self._open('alert_channel_down'))
        self.svc._channel_up()
        self.assertFalse(self._open('alert_channel_down'))

    def test_t7_09_readings_that_cannot_be_taken_do_not_crash_the_sweep(self):
        def boom(_self, window_minutes=15):
            raise RuntimeError("the log is on fire")

        with patch.object(self.cls, '_gather_readings', boom), \
             patch.object(self.env.cr, 'commit', lambda: None):
            self.svc._cron_alerts()          # must not raise
        self.assertFalse(self._open())

    def test_t7_10_the_alerts_screen_groups_what_it_is_given(self):
        self._sweep(self._readings(
            disk={'free_pct': 3, 'free_gb': 1.0}, template_hot_crons=9))
        data = self.svc.alerts_data()
        self.assertEqual(data['critical_count'], 1)
        self.assertEqual(len(data['critical']), 1)
        self.assertEqual(len(data['warning']), 1)
        self.assertEqual(data['open_count'], 2)
        self.assertIn('Next:', data['critical'][0]['text'])
        self.svc.alert_ack(data['critical'][0]['id'])
        data = self.svc.alerts_data()
        self.assertEqual(data['critical_count'], 0)
        self.assertEqual(len(data['acknowledged']), 1)
        data = self.svc.alert_resolve(data['acknowledged'][0]['id'], 'Freed space')
        self.assertEqual(data['open_count'], 1)
        self.assertTrue(any(r['resolution'] == 'Freed space'
                            for r in data['history']))

    def test_t7_11_the_morning_summary_speaks_even_when_all_is_well(self):
        pats = self._patches(self._readings())
        for p in pats:
            p.start()
        try:
            self.svc._cron_alert_digest()
        finally:
            for p in pats:
                p.stop()
        self.assertEqual(len(self.sent), 1)
        self.assertIn('all clear', self.sent[0]['subject'])
        self.assertIn('Nothing open', self.sent[0]['body'])

    def test_t7_12_the_morning_summary_lists_what_is_open(self):
        self._sweep(self._readings(disk={'free_pct': 3, 'free_gb': 1.0}))
        self.sent = []
        pats = self._patches(self._readings())
        for p in pats:
            p.start()
        try:
            self.svc._cron_alert_digest()
        finally:
            for p in pats:
                p.stop()
        self.assertEqual(len(self.sent), 1)
        self.assertIn('1 open', self.sent[0]['subject'])
        self.assertIn('running out of disk', self.sent[0]['body'])

    def test_t7_13_no_email_body_ever_says_the_framework_s_name(self):
        self._sweep(self._readings(disk={'free_pct': 3, 'free_gb': 1.0}))
        for mail in self.sent:
            self.assertNotIn('odoo', mail['body'].lower())
            self.assertNotIn('odoo', mail['subject'].lower())

    # ------------------------------------------------------------------ T8
    def test_t8_a_refused_login_is_explained_in_words(self):
        plain = self.svc._plain_smtp(
            "SMTPAuthenticationError: (535, b'5.7.8 Username and Password not "
            "accepted. For more information...')")
        self.assertIn('refused the sign-in', plain)
        self.assertIn('app password', plain)
        self.assertIn('sender address',
                      self.svc._plain_smtp(
                          "You must either provide a sender address explicitly"))
        self.assertIn('nobody to send it to',
                      self.svc._plain_smtp("At least one valid recipient"))
        # Anything we have never seen keeps its own first line rather than
        # being flattened into "something went wrong".
        self.assertEqual(self.svc._plain_smtp("Weird thing\nstack trace"),
                         "Weird thing")

    def test_t8_the_test_button_reports_the_failure_it_hit(self):
        def broken(_self, subject, body, kind='alert', recipients=None):
            reason = _self._plain_smtp("535 Username and Password not accepted")
            _self._channel_down(reason)
            return {'ok': False, 'reason': reason, 'to': []}

        with patch.object(self.cls, '_send_alert_mail', broken):
            res = self.svc.mail_test()
        self.assertFalse(res['ok'])
        self.assertIn('refused the sign-in', res['message'])
        self.assertTrue(self._open('alert_channel_down'))

    def test_t8_the_test_button_records_the_proof_when_it_works(self):
        with patch.object(self.cls, '_send_alert_mail',
                          lambda _s, sub, body, kind='alert', recipients=None:
                          {'ok': True, 'reason': '', 'to': ['a@b.com']}):
            res = self.svc.mail_test()
        self.assertTrue(res['ok'])
        self.assertIn('check the inbox', res['message'])
        self.assertTrue(self.svc._alert_param('pb_tenants.mail_proven_at', ''))

    def test_t8_a_platform_with_nobody_to_tell_refuses_to_pretend(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.alert_emails', 'nobody-at-all')
        with patch.object(self.cls, '_alert_recipients', lambda _s: []):
            res = self.svc.mail_test()
        self.assertFalse(res['ok'])
        self.assertIn('Alert settings', res['reason'])

    # ------------------------------------------------- settings and capacity
    def test_t8_settings_refuse_nonsense_and_keep_the_alarm_on(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.svc.alert_settings_save({'emails': 'not-an-address'})
        with self.assertRaises(UserError):
            self.svc.alert_settings_save({'emails': 'a@b.com',
                                          'interval_critical': 'soon'})
        with self.assertRaises(UserError):
            self.svc.alert_settings_save({'emails': 'a@b.com',
                                          'thresholds': {'disk_free_pct': 99}})
        saved = self.svc.alert_settings_save({
            'emails': 'a@b.com, c@d.com', 'from': 'platform@payobook.com',
            'interval_critical': 3, 'interval_warning': 12,
            'thresholds': {'disk_free_pct': 20, 'error_lines': 5}})
        self.assertEqual(saved['thresholds']['disk_free_pct'], 20)
        self.assertEqual(saved['interval_critical'], 3.0)
        self.assertEqual(self.svc._alert_thresholds()['error_lines'], 5)
        self.assertEqual(self.svc._alert_from(), 'platform@payobook.com')

    def test_t8_a_full_machine_refuses_the_next_customer(self):
        from odoo.exceptions import UserError
        full = {'level': 'full', 'headroom': 0, 'reason': 'No room.'}
        with patch.object(self.cls, '_capacity', lambda _s: full):
            with self.assertRaises(UserError) as caught:
                self.svc.provision_start({
                    'name': 'Too Many Ltd', 'slug': 'toomanyltd2026',
                    'admin_email': 'a@b.com'})
        self.assertIn('cannot safely hold another customer', str(caught.exception))
        self.assertIn('SAAS_RESIZE_RUNBOOK', str(caught.exception))
        self.assertFalse(self.env['pb.tenant'].sudo().search_count(
            [('slug', '=', 'toomanyltd2026')]),
            "A refused customer must leave no half-made record behind.")

    def test_t8_the_capacity_reading_is_real(self):
        cap = self.svc.capacity_check()
        self.assertIn(cap['level'], ('ok', 'warn', 'full'))
        self.assertGreater(cap['mem_total_mb'], 0,
                           "The machine's memory has to be readable.")
        self.assertGreater(cap['rss_mb'], 0)
        self.assertNotIn('odoo', cap['reason'].lower())

    # ------------------------------------------------------- the public page
    def test_t9_the_page_the_platform_would_publish_names_nobody(self):
        tenant = self.env['pb.tenant'].sudo().create({
            'name': 'Secret Payroll Ltd', 'slug': 'secretpayroll2026',
            'state': 'live',
            'notice': '{"id": "n1", "kind": "maintenance", "title": '
                      '"Planned update tonight", "text": "A short pause.", '
                      '"starts_at": "", "ends_at": "", "public": true}'})
        self.Alert.create({
            'key': 'tenant_down:secretpayroll2026', 'kind': 'tenant_down',
            'severity': 'critical', 'title': 'Secret Payroll Ltd cannot be reached',
            'text': 'Next: look at it.', 'tenant_id': tenant.id})
        page = self.svc.status_page_preview()
        self.assertNotIn('Secret Payroll', page)
        self.assertNotIn('secretpayroll2026', page)
        self.assertIn('Planned update tonight', page)
        self.assertIn('Some systems are degraded', page)
