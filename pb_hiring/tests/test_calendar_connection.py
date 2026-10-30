"""Connection lifecycle, revoked grants, and own-user isolation; no HTTP calls."""
import json
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCalendarConnection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Connection owner', 'login': 'calendar.connection.owner',
            'group_ids': [(6, 0, cls.env.ref('base.group_user').ids)]})
        cls.other = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other connection', 'login': 'calendar.connection.other',
            'group_ids': [(6, 0, cls.env.ref('base.group_user').ids)]})
        cls.settings = cls.env['res.users.settings']._find_or_create_for_user(cls.user).sudo()
        cls.other_settings = cls.env['res.users.settings']._find_or_create_for_user(cls.other).sudo()
        cls.api = cls.env['pb.shared.calendar'].with_user(cls.user)
        cls.env['ir.config_parameter'].sudo().set_param('google_calendar_client_id', 'connection-test.apps.googleusercontent.com')
        cls.env['ir.config_parameter'].sudo().set_param('google_calendar_client_secret', 'test-only-secret')
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://calendar.example.com')
        cls.env['ir.config_parameter'].sudo().set_param('google_calendar_sync_paused', 'False')

    def setUp(self):
        super().setUp()
        for settings in (self.settings, self.other_settings):
            settings.write({'google_calendar_rtoken': 'test-only-refresh',
                'google_calendar_token': 'test-only-access',
                'google_calendar_token_validity': fields.Datetime.now() + timedelta(hours=1),
                'google_synchronization_stopped': True})

    def response(self, status=200, data=None):
        result = Mock(status_code=status)
        result.json.return_value = data or {}
        if status >= 400:
            result.raise_for_status.side_effect = requests.HTTPError(response=result)
        return result

    def test_valid_saved_connection_returns_calendar_without_oauth_or_event_details(self):
        with patch('odoo.addons.pb_hiring.models.calendar_connection.requests.get',
                   return_value=self.response(data={'summary': 'My work calendar'})) as get:
            result = self.api.google_connection_check()
        self.assertEqual(result['status'], 'connected')
        self.assertEqual(result['calendar_name'], 'My work calendar')
        self.assertNotIn('url', result)
        self.assertNotIn('test-only', json.dumps(result))
        self.assertEqual(get.call_args.kwargs['params']['fields'], 'summary')

    def test_revoked_but_unexpired_token_requires_auth(self):
        with patch('odoo.addons.pb_hiring.models.calendar_connection.requests.get',
                   return_value=self.response(401)):
            self.assertEqual(self.api.google_connection_check(), {'status': 'needs_auth'})

    def test_revoked_refresh_token_requires_auth_without_clearing_other_connections(self):
        self.settings.google_calendar_token_validity = False
        with patch('odoo.addons.pb_hiring.models.calendar_connection.requests.post',
                   return_value=self.response(400, {'error': 'invalid_grant'})):
            self.assertEqual(self.api.google_connection_check(), {'status': 'needs_auth'})
        self.assertEqual(self.other_settings.google_calendar_rtoken, 'test-only-refresh')

    def test_invalid_client_is_not_presented_as_user_revocation(self):
        self.settings.google_calendar_token_validity = False
        with patch('odoo.addons.pb_hiring.models.calendar_connection.requests.post',
                   return_value=self.response(400, {'error': 'invalid_client'})):
            self.assertEqual(self.api.google_connection_check(), {'status': 'configuration_error'})

    def test_expired_valid_connection_refreshes_without_account_chooser(self):
        self.settings.google_calendar_token_validity = False
        with patch('odoo.addons.pb_hiring.models.calendar_connection.requests.post',
                   return_value=self.response(data={'access_token': 'refreshed-test', 'expires_in': 3600})), \
             patch('odoo.addons.pb_hiring.models.calendar_connection.requests.get',
                   return_value=self.response(data={'summary': 'My calendar'})):
            result = self.api.google_connection_check()
        self.assertEqual(result['status'], 'connected')
        self.assertNotIn('url', result)
        self.assertEqual(self.settings.google_calendar_token, 'refreshed-test')

    def test_network_failure_preserves_saved_connection(self):
        with patch('odoo.addons.pb_hiring.models.calendar_connection.requests.get', side_effect=requests.Timeout):
            self.assertEqual(self.api.google_connection_check(), {'status': 'unavailable'})
        self.assertEqual(self.settings.google_calendar_rtoken, 'test-only-refresh')

    def test_fresh_authorization_bypasses_stale_token_but_preserves_minimum_scopes(self):
        result = self.api.google_connection_authorize('/bizapp/action-1617')
        query = parse_qs(urlsplit(result['url']).query)
        self.assertEqual(query['prompt'], ['select_account consent'])
        self.assertNotIn('approval_prompt', query)
        self.assertEqual(query['scope'][0].split(), [
            'https://www.googleapis.com/auth/calendar.events.owned',
            'https://www.googleapis.com/auth/calendar.events.freebusy'])
        self.assertEqual(query['access_type'], ['offline'])
        state = json.loads(query['state'][0])
        self.assertEqual(state['d'], self.env.cr.dbname)
        self.assertEqual(state['f'], 'https://calendar.example.com/bizapp/action-1617')
        self.assertNotIn('secret', result['url'])
        for url in ('https://foreign.example/', '//foreign.example/', '/bizapp/\\foreign'):
            with self.assertRaises(UserError):
                self.api.google_connection_authorize(url)

    def test_removal_only_forgets_own_connection_and_preserves_meetings(self):
        event = self.env['calendar.event'].with_context(dont_notify=True).create({
            'name': 'Keep this meeting', 'user_id': self.user.id,
            'start': fields.Datetime.now(), 'stop': fields.Datetime.now() + timedelta(hours=1),
            'need_sync': False, 'google_id': 'test-existing-meeting'})
        self.settings.google_calendar_sync_token = 'old-cursor'
        result = self.api.google_connection_remove()
        self.assertFalse(result['google_connection_saved'])
        self.assertFalse(self.settings.google_calendar_token)
        self.assertFalse(self.settings.google_calendar_sync_token)
        self.assertTrue(self.settings.google_synchronization_stopped)
        self.assertTrue(event.exists())
        self.assertEqual(event.google_id, 'test-existing-meeting')
        self.assertEqual(self.other_settings.google_calendar_rtoken, 'test-only-refresh')

    def test_successful_consent_restarts_only_user_sync(self):
        self.env['ir.config_parameter'].sudo().set_param('google_calendar_sync_paused', 'True')
        self.settings._set_google_auth_tokens('new-access', 'new-refresh', 3600)
        self.assertFalse(self.settings.google_synchronization_stopped)
        self.assertEqual(self.user._get_google_sync_status(), 'sync_paused')

    def test_portal_and_other_active_provider_cannot_authorize(self):
        portal = self.env.ref('base.public_user')
        for name in ('google_connection_check', 'google_connection_authorize', 'google_connection_remove'):
            with self.assertRaises(AccessError):
                getattr(self.api.with_user(portal), name)()
        with patch.object(type(self.user), 'check_synchronization_status',
                          return_value={'microsoft_calendar': 'sync_active'}):
            with self.assertRaises(UserError): self.api.google_connection_authorize()
        self.env['ir.config_parameter'].sudo().set_param('google_calendar_sync_paused', 'True')
        with self.assertRaises(UserError): self.api.google_connection_authorize()
