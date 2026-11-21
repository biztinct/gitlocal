"""Exercise the real standard-Odoo consent path; no Google requests are sent."""
from urllib.parse import parse_qs, urlsplit

from odoo.tests import TransactionCase, tagged
from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService


BASE = 'https://www.googleapis.com/auth/calendar'


@tagged('post_install', '-at_install')
class TestGoogleCalendarScopes(TransactionCase):
    def test_standard_calendar_consent_uses_minimum_scopes(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('google_calendar_client_id', 'scope-test.apps.googleusercontent.com')
        params.set_param('web.base.url', 'https://scope-test.example.com')
        service = GoogleCalendarService(self.env['google.service'])
        url = service._google_authentication_url(from_url='/bizapp/calendar')
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['scope'][0].split(), [BASE + '.events.owned', BASE + '.events.freebusy'])
        self.assertEqual(query['client_id'], ['scope-test.apps.googleusercontent.com'])
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(query['access_type'], ['offline'])
        self.assertEqual(query['approval_prompt'], ['force'])
        self.assertTrue(query['redirect_uri'][0].endswith('/google_account/authentication'))
        self.assertIn('/bizapp/calendar', query['state'][0])

    def test_readonly_consent_does_not_gain_write_access(self):
        url = self.env['google.service']._get_authorize_uri(
            'calendar', BASE + '.readonly', 'https://example.com/callback')
        scopes = parse_qs(urlsplit(url).query)['scope'][0].split()
        self.assertEqual(scopes, [BASE + '.events.owned.readonly', BASE + '.events.freebusy'])

    def test_unrelated_google_service_is_unchanged(self):
        url = self.env['google.service']._get_authorize_uri(
            'gmail', BASE, 'https://example.com/callback', state='test-state')
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['scope'], [BASE])
        self.assertEqual(query['state'], ['test-state'])

    def test_existing_narrow_scopes_and_extra_scopes_are_preserved(self):
        requested = ' '.join([BASE, BASE + '.events.freebusy', 'openid'])
        url = self.env['google.service']._get_authorize_uri(
            'calendar', requested, 'https://example.com/callback')
        scopes = parse_qs(urlsplit(url).query)['scope'][0].split()
        self.assertEqual(scopes, [BASE + '.events.owned', BASE + '.events.freebusy', 'openid'])
