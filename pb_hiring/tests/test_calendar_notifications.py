import hashlib
from datetime import timedelta
from unittest.mock import Mock, patch

from werkzeug.datastructures import Headers

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'shared_calendar')
class TestCalendarNotifications(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = new_test_user(self.env, login='calendar.push.test', groups='base.group_user')
        self.other = new_test_user(self.env, login='calendar.push.other', groups='base.group_user')
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.set_param('pb_calendar.google_push_database', self.env.cr.dbname)
        self.params.set_param('pb_calendar.google_push_origin', 'https://payobook.com')
        self.params.set_param('google_calendar_sync_paused', 'False')
        self.env['res.users.settings']._find_or_create_for_user(self.user).sudo().write({'google_calendar_rtoken': 'test-only-refresh',
            'google_calendar_token': 'test-only-token',
            'google_calendar_token_validity': fields.Datetime.now() + timedelta(hours=2)})
        self.channels = self.env['pb.calendar.google.channel'].sudo()
        self.queue = self.env['pb.calendar.google.notification'].sudo()
        self.rec = self.channels.create({'user_id': self.user.id, 'channel': 'test-channel',
            'resource': 'test-resource', 'token_hash': hashlib.sha256(b'test-secret').hexdigest(),
            'expires': fields.Datetime.now() + timedelta(days=5),
            'next_watch': fields.Datetime.now() + timedelta(days=4),
            'next_sync': fields.Datetime.now() + timedelta(hours=1)})

    def headers(self, **overrides):
        values = {'Channel-ID': 'test-channel', 'Channel-Token': 'test-secret',
                  'Resource-ID': 'test-resource', 'Message-Number': '10', 'Resource-State': 'exists'}
        values.update(overrides)
        return Headers({'X-Goog-' + k: v for k, v in values.items()})

    def test_secret_resource_channel_and_expiry_required(self):
        for key in ('Channel-ID', 'Channel-Token', 'Resource-ID', 'Message-Number', 'Resource-State'):
            self.assertFalse(self.channels._receive(self.headers(**{key: 'invalid'})))
        self.rec.expires = fields.Datetime.now() - timedelta(seconds=1)
        self.assertFalse(self.channels._receive(self.headers()))
        self.assertFalse(self.queue.search([('channel_id', '=', self.rec.id)]))

    def test_duplicates_and_out_of_order_notifications_coalesce(self):
        for number in ('10', '10', '7', '12'):
            self.assertTrue(self.channels._receive(self.headers(**{'Message-Number': number})))
        self.assertEqual(self.queue.search_count([('channel_id', '=', self.rec.id)]), 3)
        with patch.object(type(self.user), '_sync_google_calendar', return_value=False) as sync:
            self.rec._process()
        sync.assert_called_once()
        self.assertFalse(self.queue.search([('channel_id', '=', self.rec.id)]))
        self.assertTrue(self.rec.last_sync)

    def test_arrival_during_sync_is_preserved(self):
        self.channels._receive(self.headers())
        with patch.object(type(self.user), '_sync_google_calendar', side_effect=lambda service:
                self.channels._receive(self.headers(**{'Message-Number': '11'}))):
            self.rec._process()
        self.assertEqual(self.queue.search([('channel_id', '=', self.rec.id)]).mapped('message'), ['11'])

    def test_no_poll_until_hourly_fallback(self):
        with patch.object(type(self.user), '_sync_google_calendar', return_value=False) as sync:
            self.rec._process()
            sync.assert_not_called()
            self.rec.next_sync = fields.Datetime.now() - timedelta(seconds=1)
            self.rec._process()
            sync.assert_called_once()

    def test_pause_and_revocation_stop_processing(self):
        self.channels._receive(self.headers())
        self.user.sudo().google_synchronization_stopped = True
        with patch.object(type(self.user), '_sync_google_calendar') as sync:
            self.rec._process()
            sync.assert_not_called()
        self.assertFalse(self.queue.search([('channel_id', '=', self.rec.id)]))
        self.user.res_users_settings_id.sudo().write({'google_calendar_rtoken': False})
        self.assertFalse(self.rec.channel)
        self.assertFalse(self.channels._receive(self.headers()))

    def test_clone_and_insecure_callback_rejected(self):
        self.params.set_param('pb_calendar.google_push_database', 'a-different-database')
        self.assertFalse(self.channels._callback())
        self.assertFalse(self.channels._receive(self.headers()))
        self.params.set_param('pb_calendar.google_push_database', self.env.cr.dbname)
        for origin in ('http://payobook.com', 'https://name:secret@payobook.com', 'https://payobook.com/path'):
            self.params.set_param('pb_calendar.google_push_origin', origin)
            self.assertFalse(self.channels._callback())

    def test_channel_credentials_never_readable_by_employee(self):
        with self.assertRaises(AccessError):
            self.rec.with_user(self.user).read(['token_hash'])
        with self.assertRaises(AccessError):
            self.queue.with_user(self.user).search_count([])
        own = self.channels.with_user(self.user)._own_status()
        other = self.channels.with_user(self.other)._own_status()
        self.assertTrue(own['active'])
        self.assertFalse(other['active'])
        self.assertNotIn('token_hash', own)

    def test_renewal_uses_new_secret_and_retains_incremental_sync(self):
        self.rec.next_watch = fields.Datetime.now() - timedelta(seconds=1)
        self.user.res_users_settings_id.sudo().google_calendar_sync_token = 'existing-sync-token'
        def reply(url, **kwargs):
            if url.endswith('/watch'):
                self.assertEqual(kwargs['json']['address'], 'https://payobook.com/pb/calendar/google/notify')
                return Mock(raise_for_status=Mock(), json=lambda: {'id': kwargs['json']['id'],
                    'resourceId': 'new-resource', 'expiration': str(int((fields.Datetime.now() + timedelta(days=7)).timestamp()*1000))})
            return Mock(raise_for_status=Mock())
        with patch('odoo.addons.pb_hiring.models.calendar_notifications.requests.post', side_effect=reply), \
                patch.object(type(self.user), '_sync_google_calendar', return_value=False) as sync:
            self.rec._process()
        sync.assert_called_once()
        self.assertNotEqual(self.rec.channel, 'test-channel')
        self.assertFalse(self.channels._receive(self.headers()))
        self.assertEqual(self.user.sudo().google_calendar_sync_token, 'existing-sync-token')

    def test_watch_failure_does_not_block_fallback(self):
        import requests
        self.rec.write({'next_watch': fields.Datetime.now() - timedelta(seconds=1),
                        'next_sync': fields.Datetime.now() - timedelta(seconds=1)})
        with patch('odoo.addons.pb_hiring.models.calendar_notifications.requests.post', side_effect=requests.Timeout), \
                patch.object(type(self.user), '_sync_google_calendar', return_value=False) as sync:
            self.rec._process()
        sync.assert_called_once()
        self.assertEqual(self.rec.watch_failures, 1)
        self.assertGreater(self.rec.next_watch, fields.Datetime.now())

    def test_backoff_retains_pending_hints(self):
        self.channels._receive(self.headers())
        self.rec.failures = 2
        with patch.object(type(self.user), '_sync_google_calendar') as sync:
            self.rec._process()
            sync.assert_not_called()
        self.assertEqual(self.queue.search_count([('channel_id', '=', self.rec.id)]), 1)
