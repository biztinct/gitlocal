"""Google push is a hint: queue it, then use the native incremental sync.

No calendar data or OAuth credentials travel in webhook notifications. These
internal models intentionally have no user ACL; the facade exposes own status
only. Each worker transaction is scoped to one connected user.
"""
import hashlib
import hmac
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService
from odoo.exceptions import LockError

_logger = logging.getLogger(__name__)
CALLBACK_PATH = '/pb/calendar/google/notify'


class CalendarNotificationSettings(models.Model):
    _inherit = 'res.users.settings'

    def write(self, vals):
        result = super().write(vals)
        if 'google_calendar_rtoken' in vals:
            # Reconnection can select a different account or OAuth application.
            # Do not accept old-account hints or reuse its watch subscription.
            self.env['pb.calendar.google.channel'].sudo().search([
                ('user_id', 'in', self.user_id.ids)]).write({
                    'channel': False, 'token_hash': False, 'resource': False, 'expires': False,
                    'next_watch': fields.Datetime.now(), 'next_sync': fields.Datetime.now(),
                    'failures': 0, 'watch_failures': 0})
        return result


class GoogleCalendarNotification(models.Model):
    _name = 'pb.calendar.google.notification'
    _description = 'Internal Google calendar change queue'

    channel_id = fields.Many2one('pb.calendar.google.channel', required=True, ondelete='cascade', index=True)
    message = fields.Char(required=True)
    _message_unique = models.Constraint('unique(channel_id, message)', 'Notification already queued.')


class GoogleCalendarChannel(models.Model):
    _name = 'pb.calendar.google.channel'
    _description = 'Internal Google calendar notification subscription'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    channel = fields.Char(index=True, copy=False)
    token_hash = fields.Char(copy=False)
    resource = fields.Char(copy=False)
    expires = fields.Datetime(copy=False)
    last_sync = fields.Datetime(copy=False)
    next_sync = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    next_watch = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    failures = fields.Integer(default=0)
    watch_failures = fields.Integer(default=0)
    _user_unique = models.Constraint('unique(user_id)', 'One subscription per user.')
    _channel_unique = models.Constraint('unique(channel)', 'Channel identifiers must be unique.')

    @api.model
    def _callback(self):
        # Explicit opt-in per database prevents a restored clone from registering
        # subscriptions against the production hostname.
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('pb_calendar.google_push_database') != self.env.cr.dbname:
            return False
        base = params.get_param('pb_calendar.google_push_origin', '').rstrip('/')
        url = urlsplit(base)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path:
            return False
        return base + CALLBACK_PATH

    @api.model
    def _receive(self, headers):
        """Authenticate a hint; never call Google from a public HTTP request."""
        if not self._callback():
            return False
        channel, token, resource, message, state = [headers.get('X-Goog-' + key, '') for key in
            ('Channel-ID', 'Channel-Token', 'Resource-ID', 'Message-Number', 'Resource-State')]
        if not (0 < len(channel) <= 64 and 0 < len(token) <= 256 and 0 < len(resource) <= 512
                and 0 < len(message) <= 20 and message.isascii() and message.isdecimal()
                and state in ('sync', 'exists', 'not_exists')):
            return False
        rec = self.sudo().search([('channel', '=', channel)], limit=1)
        if not rec or not rec.expires or rec.expires <= fields.Datetime.now():
            return False
        if not hmac.compare_digest(rec.token_hash or '', hashlib.sha256(token.encode()).hexdigest()):
            return False
        if not hmac.compare_digest(rec.resource or '', resource):
            return False
        # A separate append-only queue avoids blocking the callback on a sync.
        # Repeated message numbers are harmless; out-of-order hints are retained.
        self.env.cr.execute('''INSERT INTO pb_calendar_google_notification
            (channel_id, message, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
            ON CONFLICT (channel_id, message) DO NOTHING''',
            (rec.id, message, SUPERUSER_ID, SUPERUSER_ID))
        return True

    def _active_user(self):
        self.ensure_one()
        user = self.user_id.sudo()
        return user.active and not user.share and user.google_calendar_rtoken and user._get_google_sync_status() == 'sync_active'

    def _watch(self):
        self.ensure_one()
        callback = self._callback()
        if not callback or not self._active_user():
            return
        user = self.user_id.with_user(self.user_id).sudo()
        token = user._get_google_calendar_token()
        channel, secret = str(uuid.uuid4()), secrets.token_urlsafe(32)
        # Never log response bodies, bearer tokens or webhook secrets.
        response = requests.post('https://www.googleapis.com/calendar/v3/calendars/primary/events/watch',
            headers={'Authorization': 'Bearer ' + token}, timeout=15,
            json={'id': channel, 'type': 'web_hook', 'address': callback, 'token': secret,
                  'expiration': str(int((time.time() + 7 * 86400) * 1000))})
        response.raise_for_status()
        data = response.json()
        expiry = datetime.utcfromtimestamp(int(data['expiration']) / 1000)
        if data.get('id') != channel or not data.get('resourceId') or expiry <= fields.Datetime.now():
            raise ValueError('Invalid Google notification subscription response')
        old_channel, old_resource = self.channel, self.resource
        self.write({'channel': channel, 'token_hash': hashlib.sha256(secret.encode()).hexdigest(),
                    'resource': data['resourceId'], 'expires': expiry,
                    'next_watch': max(fields.Datetime.now() + timedelta(minutes=5), expiry - timedelta(hours=24)),
                    'watch_failures': 0})
        # A sync immediately after registration covers notifications that arrived
        # before the watch response committed. Old channels otherwise expire.
        if old_channel and old_resource:
            try:
                requests.post('https://www.googleapis.com/calendar/v3/channels/stop',
                    headers={'Authorization': 'Bearer ' + token}, timeout=5,
                    json={'id': old_channel, 'resourceId': old_resource}).raise_for_status()
            except requests.RequestException:
                _logger.info('Old Google calendar subscription will expire for user %s', user.id)

    def _process(self):
        self.ensure_one()
        if not self._callback() or not self._active_user():
            self.env['pb.calendar.google.notification'].sudo().search([('channel_id', '=', self.id)]).unlink()
            return
        user = self.user_id.with_user(self.user_id).sudo()
        # The native connector also takes this lock; acquire before doing any
        # work so a skipped concurrent sync cannot be mistaken for success.
        user.lock_for_update(allow_referencing=True)
        now = fields.Datetime.now()
        renewed = False
        if self.next_watch <= now:
            try:
                self._watch()
                renewed = True
            except (requests.RequestException, ValueError, KeyError):
                failures = self.watch_failures + 1
                self.write({'watch_failures': failures,
                    'next_watch': now + timedelta(minutes=min(60, 2 ** min(failures, 6)))})
                _logger.warning('Google calendar subscription retry scheduled for user %s', user.id)
        queued = self.env['pb.calendar.google.notification'].sudo().search([('channel_id', '=', self.id)])
        if self.failures and self.next_sync > now:
            return
        if not renewed and not queued and self.next_sync > now:
            return
        service = GoogleCalendarService(user.env['google.service'])
        user._sync_google_calendar(service)
        self.write({'last_sync': now, 'next_sync': now + timedelta(hours=1), 'failures': 0})
        # Delete only the observed hints, retaining any received during sync.
        queued.unlink()

    @api.model
    def _cron_process(self):
        if not self._callback():
            return
        # Provision new connections without changing the native OAuth flow.
        self.env.cr.execute('''INSERT INTO pb_calendar_google_channel
            (user_id, next_sync, next_watch, failures, watch_failures, create_uid, write_uid, create_date, write_date)
            SELECT u.id, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC', 0, 0, 1, 1,
                NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
            FROM res_users u JOIN res_users_settings s ON s.user_id=u.id
            WHERE u.active AND NOT u.share AND s.google_calendar_rtoken IS NOT NULL
            AND NOT COALESCE(s.google_synchronization_stopped, false)
            ON CONFLICT (user_id) DO NOTHING''')
        self.env.cr.commit()
        self.env.cr.execute('''SELECT c.id FROM pb_calendar_google_channel c
            JOIN res_users u ON u.id=c.user_id JOIN res_users_settings s ON s.user_id=u.id
            WHERE u.active AND NOT u.share AND s.google_calendar_rtoken IS NOT NULL
            AND NOT COALESCE(s.google_synchronization_stopped, false)
            AND (c.next_watch <= NOW() AT TIME ZONE 'UTC' OR
                c.next_sync <= NOW() AT TIME ZONE 'UTC' OR
                (COALESCE(c.failures,0)=0 AND EXISTS
                    (SELECT 1 FROM pb_calendar_google_notification n WHERE n.channel_id=c.id)))
            ORDER BY c.last_sync NULLS FIRST, c.id LIMIT 30''')
        ids = [row[0] for row in self.env.cr.fetchall()]
        deadline = time.monotonic() + 45
        for channel_id in ids:
            if time.monotonic() >= deadline:
                break
            # Native token refresh can commit/rollback; isolate it from the
            # scheduler and from other users' synchronization transactions.
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                rec = env[self._name].browse(channel_id)
                try:
                    rec._process()
                    cr.commit()
                except LockError:
                    cr.rollback()
                except Exception:
                    cr.rollback()
                    rec.invalidate_recordset()
                    failures = rec.failures + 1
                    rec.write({'failures': failures,
                        'next_sync': fields.Datetime.now() + timedelta(minutes=min(60, 2 ** min(failures, 6))),
                        'next_watch': fields.Datetime.now() + timedelta(minutes=min(60, 2 ** min(failures, 6)))})
                    cr.commit()
                    _logger.warning('Google calendar sync retry scheduled for user %s', rec.user_id.id)

    @api.model
    def _own_status(self):
        rec = self.sudo().search([('user_id', '=', self.env.uid)], limit=1)
        enabled = bool(self._callback())
        return {'enabled': enabled,
                'active': bool(enabled and rec and rec._active_user() and rec.expires and rec.expires > fields.Datetime.now()),
                'last_sync': str(rec.last_sync) if rec.last_sync else False,
                'retrying': bool(rec.failures or rec.watch_failures)}
