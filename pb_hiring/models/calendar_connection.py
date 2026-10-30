"""Explicit, own-user Google connection management, separate from syncing."""
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService


class CalendarConnection(models.AbstractModel):
    _inherit = 'pb.shared.calendar'

    def _google_settings(self):
        self._require()
        return self.env.user.res_users_settings_id.sudo()

    @api.model
    def google_connection_check(self):
        settings = self._google_settings()
        if not self.env.user._has_setup_credentials():
            return {'status': 'missing_credentials'}
        if not settings.google_calendar_rtoken:
            return {'status': 'needs_auth'}
        # Check only on a user's explicit request, never on every page load.
        # Do not use the native refresh helper here: on failure it rolls back
        # and commits the caller's transaction and can hide revoked access.
        try:
            token = settings.google_calendar_token
            if not token or not settings._is_google_calendar_valid():
                params = self.env['ir.config_parameter'].sudo()
                response = requests.post('https://oauth2.googleapis.com/token', timeout=10,
                    data={'grant_type': 'refresh_token',
                          'refresh_token': settings.google_calendar_rtoken,
                          'client_id': params.get_param('google_calendar_client_id'),
                          'client_secret': params.get_param('google_calendar_client_secret')})
                if response.status_code in (400, 401):
                    return {'status': 'needs_auth' if response.json().get('error') == 'invalid_grant'
                            else 'configuration_error'}
                response.raise_for_status()
                data = response.json()
                token = data['access_token']
                settings.write({'google_calendar_token': token,
                    'google_calendar_token_validity': fields.Datetime.now() + timedelta(seconds=int(data['expires_in']))})
            # The existing events permission can return the calendar's title.
            # Do not guess an account email from the Payobook login or ask for
            # broader calendar/profile permissions merely to label this card.
            response = requests.get('https://www.googleapis.com/calendar/v3/calendars/primary/events',
                headers={'Authorization': 'Bearer ' + token},
                params={'maxResults': 1, 'fields': 'summary'}, timeout=10)
            if response.status_code == 401:
                return {'status': 'needs_auth'}
            response.raise_for_status()
            return {'status': 'connected', 'calendar_name': response.json().get('summary') or '',
                    'sync_status': self.env.user._get_google_sync_status()}
        except (requests.RequestException, ValueError, KeyError, TypeError):
            # A network outage or API configuration error is not a revocation.
            # Preserve the connection and let the user retry or remove it.
            return {'status': 'unavailable'}

    @api.model
    def google_connection_authorize(self, from_path='/bizapp/calendar'):
        self._require()
        statuses = self.env.user.check_synchronization_status()
        if not self.env.user._has_setup_credentials():
            raise UserError(_('Ask an administrator to configure Google Calendar first.'))
        if statuses.get('google_calendar') == 'sync_paused':
            raise UserError(_('Your administrator has paused Google Calendar synchronisation.'))
        if statuses.get('microsoft_calendar') == 'sync_active':
            raise UserError(_('Pause your Microsoft connection before connecting Google Calendar.'))
        if not isinstance(from_path, str) or not from_path.startswith('/bizapp/') or '\\' in from_path:
            raise UserError(_('Return to Calendar and try connecting again.'))
        base = self.env['google.service'].get_base_url().rstrip('/')
        service = GoogleCalendarService(self.env['google.service'].with_context(base_url=base))
        parts = urlsplit(service._google_authentication_url(from_url=base + from_path))
        query = dict(parse_qsl(parts.query))
        query.pop('approval_prompt', None)
        # Only an explicit fresh connection reaches here. Ordinary sync and
        # valid saved connections never request another account selection.
        query['prompt'] = 'select_account consent'
        return {'url': urlunsplit(parts._replace(query=urlencode(query)))}

    @api.model
    def google_connection_remove(self):
        settings = self._google_settings()
        # Forget only this user's local credentials. Never revoke the Google
        # application's grant globally or delete calendar events.
        if settings:
            settings.write({'google_calendar_rtoken': False, 'google_calendar_token': False,
                'google_calendar_token_validity': False, 'google_calendar_sync_token': False,
                'google_synchronization_stopped': True})
        return self.capabilities()


class CalendarConnectionSettings(models.Model):
    _inherit = 'res.users.settings'

    def _set_google_auth_tokens(self, access_token, refresh_token, ttl):
        result = super()._set_google_auth_tokens(access_token, refresh_token, ttl)
        if access_token and refresh_token:
            # Successful consent repairs a stopped/revoked connection. Do not
            # bypass the independent administrator-wide pause.
            self.sudo().write({'google_synchronization_stopped': False,
                               'google_calendar_sync_token': False})
        return result
