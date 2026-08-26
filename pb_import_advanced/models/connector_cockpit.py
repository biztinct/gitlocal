# -*- coding: utf-8 -*-
import calendar
import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

TYPE_LABEL = {
    'zoho': 'Zoho People', 'excel': 'Excel File', 'sap': 'SAP SuccessFactors',
    'workday': 'Workday', 'oracle': 'Oracle HCM', 'darwin': 'DarwinHR', 'demo': 'Demo / Stub',
}
TYPE_ICON = {
    'zoho': 'cloud', 'excel': 'table', 'sap': 'server',
    'workday': 'briefcase', 'oracle': 'database', 'darwin': 'zap', 'demo': 'beaker',
}
STATUS_LABEL = {
    'disconnected': 'Disconnected', 'connecting': 'Connecting',
    'connected': 'Connected', 'error': 'Error',
}
LIFECYCLE = {
    'action_test_connection', 'action_pull_data', 'action_fetch_available_fields',
    'action_disconnect', 'action_refresh_token',
}
LINKS = {
    'action_view_data_store', 'action_view_mappings', 'action_launch_payroll_import',
}

# A Lucide glyph per data type, from the SHARED registry (W2 — a name that is
# not in `pb_import_kit`'s IC map renders the fallback checkmark, silently).
DATA_TYPE_ICON = {
    'employee': 'users', 'salary': 'banknote', 'attendance': 'clock',
    'leave': 'umbrella', 'dependent': 'user', 'benefit': 'shieldCheck',
    'tax': 'percent', 'custom': 'layers',
}
DEFAULT_API_BASE = {
    'zoho': 'https://people.zoho.com/people/api',
    'darwin': 'https://api.darwinbox.in',
}

# The feed operations whose ANSWER depends on the window they are asked for.
# `employee` and `salary` return the current state of a record and are the same
# whichever month you ask about; the rest are dated and a wrong window silently
# returns a different month's numbers, which is the defect the period selector
# exists to close.
PERIOD_SCOPED = {
    'attendance_summary', 'attendance_daily', 'leave', 'overtime', 'timesheet',
    'generic',
}

# ============================================================== credentials
#
# What each authentication type actually needs, and NOTHING about what is in
# it. The panel is write-only by construction: every RPC on this facade returns
# `is_set` booleans and never a value, not even a masked prefix — a masked
# secret is still a secret with its length and shape published, and the moment
# one path returns one, every future path is a judgement call.
#
# `secret` marks the fields Odoo itself keeps behind `base.group_system`
# (`integration_connector.py`:88-126). Public OAuth locations and scopes live
# in the Connection & Feed Studio now; mixing them into a write-only secrets
# panel made an ordinary URL impossible to review after saving it.
CRED_SETS = {
    'oauth2': [
        ('client_id', 'Client ID', True),
        ('client_secret', 'Client Secret', True),
        ('refresh_token', 'Refresh Token', True),
    ],
    'api_key': [('api_key', 'API Key', True)],
    'basic': [('username', 'Username', True), ('password', 'Password', True)],
    'bearer': [('access_token', 'Access Token', True)],
}

# Everything `save_credentials` will write, and the ONLY things it will write.
# Public endpoint/OAuth configuration has a separate whitelist and validator.
WRITABLE_CREDENTIAL_KEYS = (
    {k for fields_ in CRED_SETS.values() for k, _l, _s in fields_}
    | {'auth_type'}
)


class PbConnectorCockpit(models.AbstractModel):
    """Guided connector cockpit. Drives the existing hr.integration.connector
    methods (test/pull/fetch/disconnect) which return notification/reload dicts
    we DISCARD, then re-read the connector state."""
    _name = 'pb.import.connector.cockpit'
    _description = 'Payobook connector cockpit'

    @api.model
    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Connector cockpit metric failed: %s", e)
            return default

    @api.model
    def get_connectors(self):
        """List view (used if the cockpit is opened without a specific id)."""
        out = []
        for c in self.env['hr.integration.connector'].search([], order='name'):
            out.append(self._card(c))
        return {'connectors': out}

    def _card(self, c):
        return {
            'id': c.id, 'name': c.name or '—',
            'type': c.connector_type or '', 'icon': TYPE_ICON.get(c.connector_type, 'plug'),
            'type_label': TYPE_LABEL.get(c.connector_type, c.connector_type or '—'),
            'status': c.connection_status or 'disconnected',
            'status_label': STATUS_LABEL.get(c.connection_status, c.connection_status or 'Disconnected'),
            # The same derived truth the detail header uses (C7 WP-5): a list
            # and a detail that disagree about one connector is the same defect
            # one screen further out.
            'last_sync': self._sync_truth(c)['when'],
        }

    @api.model
    def get_connector_detail(self, connector_id):
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        if not c.exists():
            return {'error': 'Connector not found'}
        mappings = [{
            'id': m.id,
            'source': m.source_field or '',
            'label': m.source_field_label or m.source_field or '',
            'target': m.target_rule_id.name or '',
            'transform': m.transformation_type or 'direct',
            'required': bool(m.is_required),
        } for m in c.field_mapping_ids[:200]]
        rules = [{
            'id': r.id, 'name': r.name or '—',
            'type': r.rule_type or '', 'active': bool(r.active),
        } for r in c.transformation_rule_ids[:100]]
        return {
            'id': c.id, 'name': c.name or '—',
            'type': c.connector_type or '', 'icon': TYPE_ICON.get(c.connector_type, 'plug'),
            'type_label': TYPE_LABEL.get(c.connector_type, c.connector_type or '—'),
            'status': c.connection_status or 'disconnected',
            'status_label': STATUS_LABEL.get(c.connection_status, c.connection_status or 'Disconnected'),
            # C7 WP-5 — kept for any caller that still reads it, but the header
            # renders `sync_truth`, which is derived from the feeds the reader
            # can see rather than from a field nothing on the screen
            # corroborates.
            'last_sync': str(c.last_sync or '')[:16],
            'sync_truth': self._sync_truth(c),
            'conn_test': str(c.last_connection_test or '')[:16]
                         if 'last_connection_test' in c._fields else '',
            'sync_status': c.last_sync_status or '',
            'sync_message': c.last_sync_message or '',
            'last_error': c.last_error or '',
            'api_endpoint': c.api_endpoint or '',
            'mappings': mappings,
            'mapping_count': len(c.field_mapping_ids),
            'data_store_count': len(c.data_store_ids),
            'rules': rules,
            'endpoints': self._endpoints(c),
            'pull_period': self._default_pull_period(c),
            'configuration': self._configuration(c),
            'credentials': self._credentials(c),
            'can_write': c.has_access('write'),
            # Cycle 6 — can this vendor be ASKED for its field list, and if not
            # why not. Three booleans and a sentence; never a credential.
            'field_fetch': c.field_fetch_capability(),
            'next_actions': self._connector_actions(c),
            'error': None,
        }

    # ============================================== one sync truth per screen
    def _sync_truth(self, c):
        """What this connector's HEADER is entitled to say about syncing.

        Integrations Cycle 7, WP-5. The owner's cockpit read
        `Connected · Last sync 2026-08-20 23:25` above seven feed cards that
        each read `Never synced · 0 staged · 0 pulled`. Both halves came off
        the same record and disagreed, which is the failure class this
        programme exists to close.

        The cause was upstream (a connection TEST stamped `last_sync`; fixed at
        `base_connector.update_connector_status`, with a migration for the rows
        it already wrote). The cure is this: the header stops reading a
        connector-level field that nothing on the screen corroborates, and
        derives its sentence from the SAME facts the cards are drawn from.

        Three shapes, and the vocabulary differs deliberately so that two
        sentences on one screen can never be read as one claim:

          sync   at least one feed has run. `when` is the most recent of them,
                 so the header cannot be newer than every card under it.
          pull   no feed has run, but the connector carries a recorded pull
                 with a status — a real event from before per-feed history
                 existed. It is not thrown away to make the screen tidy; it is
                 named "Last pull" and carries its own explanation.
          never  neither. The header says exactly what every card says.

        A connection test is reported separately and always, because it is a
        different fact and the reader wanted it: "Connection tested <when>".
        """
        eps = []
        Endpoint = self.env.get('hr.integration.endpoint') \
            if 'hr.integration.endpoint' in self.env else None
        if Endpoint is not None and Endpoint._schema_ready():
            eps = [e.last_sync for e in c.endpoint_ids if e.last_sync]
        if eps:
            return {'kind': 'sync', 'when': str(max(eps))[:16], 'note': ''}
        if c.last_sync:
            return {
                'kind': 'pull', 'when': str(c.last_sync)[:16],
                'note': "This connector recorded a pull before it kept "
                        "per-feed history, so no feed below shows it.",
            }
        return {'kind': 'never', 'when': '', 'note': ''}

    # =================================================================== feeds
    def _endpoint_row(self, e):
        configured_base = e.connector_id.api_endpoint or DEFAULT_API_BASE.get(
            e.connector_id.connector_type, '')
        base = configured_base.rstrip('/') + '/'
        path = e.path or ''
        full_url = path if path.startswith(('http://', 'https://')) else \
            urljoin(base, path.lstrip('/')) if base and path else ''
        operation = e.operation or 'catalog_only'
        template_backed = bool(
            self.env['hr.integration.endpoint.template'].with_context(
                active_test=False).search([
                    ('connector_type', '=', e.connector_id.connector_type),
                    ('code', '=', e.code),
                ], limit=1))
        return {
            'id': e.id,
            'name': e.name or e.code or '—',
            'code': e.code or '',
            'data_type': e.data_type or '',
            'data_type_label': dict(
                e._fields['data_type'].selection).get(e.data_type, e.data_type or ''),
            'operation': operation,
            'operation_label': dict(
                e._fields['operation'].selection).get(operation, operation),
            'runnable': bool(e.active and operation != 'catalog_only' and path),
            'active': bool(e.active),
            'template_backed': template_backed,
            'icon': DATA_TYPE_ICON.get(e.data_type, 'database'),
            'method': (e.http_method or 'get').upper(),
            'path': e.path or '',
            'full_url': full_url,
            'params_note': e.params_note or '',
            # Both halves of W46: the machine twin beside the display one, from
            # the same field in the same expression, so the two can never end up
            # describing different moments.
            'last_sync': str(e.last_sync or '')[:16],
            'last_sync_iso': e.last_sync.isoformat() if e.last_sync else '',
            # WHICH window this feed last pulled, beside WHEN it pulled. A feed
            # whose rows are August's, refreshed during a July run, looked
            # identical to a correct one until this was on the card.
            'period_from': str(e.last_period_from or ''),
            'period_to': str(e.last_period_to or ''),
            'period_label': self._period_label(e.last_period_from,
                                               e.last_period_to),
            'period_scoped': (e.operation or 'catalog_only') in PERIOD_SCOPED,
            'status': e.last_sync_status or '',
            'last_error': e.last_error or '',
            'synced': e.synced_count,
            'staged': e.staged_count,
            'legacy_unassigned': e.unassigned_count,
            'mapping_count': e.mapping_count,
            'is_legacy_abm': bool(e.is_legacy_abm),
            # Integrations Cycle 6 — how many fields this feed is KNOWN to
            # deliver. Zero on a database that has not been upgraded for the
            # catalogue, which is the same "hidden, not wrong" answer the feeds
            # strip itself gives there.
            'field_count': self._endpoint_field_count(e),
        }

    def _configuration(self, c):
        web_base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        callback = c.oauth_redirect_uri or (
            web_base.rstrip('/') + '/zoho/callback' if web_base else '')
        endpoints = self._endpoints(c)
        runnable = sum(1 for row in endpoints if row['runnable'])
        issues = []
        effective_base = c.api_endpoint or DEFAULT_API_BASE.get(c.connector_type, '')
        if c.connector_type != 'excel' and not effective_base:
            issues.append('Add the API base URL.')
        secret_state = c.sudo()
        if c.auth_type == 'oauth2' and not (
                secret_state.refresh_token or
                (secret_state.access_token and secret_state.token_expiry)):
            issues.append('Complete OAuth or add a refresh token.')
        incomplete = sum(
            1 for row in endpoints
            if row['active'] and row['operation'] != 'catalog_only'
            and not row['path'])
        if incomplete:
            issues.append(_('%s executable feeds need a path.') % incomplete)
        return {
            'api_endpoint': effective_base,
            'api_endpoint_is_default': bool(not c.api_endpoint and effective_base),
            'api_version': c.api_version or '',
            'sync_interval': c.sync_interval or 0,
            'auth_type': c.auth_type or 'oauth2',
            'oauth_authorize_url': c.oauth_authorize_url or '',
            'oauth_token_url': c.oauth_token_url or '',
            'oauth_scope': c.oauth_scope or '',
            'oauth_redirect_uri': c.oauth_redirect_uri or '',
            'effective_redirect_uri': callback,
            # Exact, copy-ready values for Zoho's "Create New Client" form.
            # Credential readiness leaves this method only as booleans; the
            # write-only secret contract of `_credentials` remains intact.
            'application_home_url': web_base.rstrip('/'),
            'oauth_client_ready': bool(
                secret_state.client_id and secret_state.client_secret),
            'oauth_token_ready': bool(secret_state.refresh_token),
            'runnable': runnable,
            'total': len(endpoints),
            'issues': issues,
            'ready': not issues,
            'can_edit': c.has_access('write'),
        }

    def _endpoint_field_count(self, e):
        Field = self.env.get('hr.integration.endpoint.field') \
            if 'hr.integration.endpoint.field' in self.env else None
        if Field is None or not Field._schema_ready():
            return 0
        return Field.search_count([('endpoint_id', '=', e.id)])

    def _endpoints(self, c):
        # The TABLE, not the registry — see `_schema_ready`'s docstring. On a
        # database that has not been upgraded since the model was added, this
        # cockpit answered 500 rather than rendering without a feeds strip.
        Endpoint = self.env.get('hr.integration.endpoint') \
            if 'hr.integration.endpoint' in self.env else None
        if Endpoint is None or not Endpoint._schema_ready():
            return []
        # Configuration must be able to turn an inactive feed back on. Reading
        # only the one2many's default active scope made deactivation a one-way
        # door: the row disappeared from the only screen that could restore it.
        rows = Endpoint.with_context(active_test=False).search(
            [('connector_id', '=', c.id)], order='sequence, name, id')
        return [self._endpoint_row(e) for e in rows]

    # ============================================================= credentials
    def _credentials(self, c):
        """What this connector needs to authenticate, and whether it is there.

        `editable` is `base.group_system`, which is the group Odoo puts the
        credential FIELDS behind — so a caller who is not in it cannot read
        them at all, and the honest payload for that persona is an empty field
        list rather than a list of unanswerable questions. That also means this
        method never needs `sudo()` to build the booleans (W12): the only
        caller who gets them is the only caller allowed to read them.
        """
        editable = self.env.user.has_group('base.group_system')
        auth = c.auth_type or 'oauth2'
        out = {'auth_type': auth,
               'auth_label': dict(
                   c._fields['auth_type'].selection).get(auth, auth),
               'editable': editable, 'fields': []}
        if not editable:
            return out
        for key, label, secret in CRED_SETS.get(auth, []):
            out['fields'].append({
                'key': key, 'label': label, 'secret': secret,
                # A BOOLEAN. Never the value, never a prefix, never a length.
                'is_set': bool(c[key]),
            })
        return out

    def _connector_actions(self, c):
        """The lifecycle bar — offered only to a caller who may WRITE.

        Found on the live run of Integrations Cycle 1: the read-only demo
        persona was offered "Test connection", "Pull data", "Fetch fields" and
        "Disconnect", every one of which writes the connector and answers with
        an access error. That is W29's door that can only produce an error, and
        it predates this cycle — but gating the cycle's NEW per-feed Sync while
        leaving its connector-wide twin ungated on the same screen would teach
        the next reader that the gate is decoration. One flag, derived from the
        model's own `has_access`, governs both.
        """
        if not c.has_access('write'):
            return []
        acts = []
        connected = c.connection_status == 'connected'
        is_excel = c.connector_type == 'excel'
        acts.append({'method': 'action_test_connection', 'label': 'Test connection',
                     'icon': 'zap', 'kind': 'primary' if not connected else 'outline'})
        if connected and not is_excel:
            acts.append({'method': 'action_pull_data', 'label': 'Pull data',
                         'icon': 'download', 'kind': 'primary'})
            acts.append({'method': 'action_fetch_available_fields', 'label': 'Fetch fields',
                         'icon': 'refresh', 'kind': 'ghost'})
        if connected:
            acts.append({'method': 'action_disconnect', 'label': 'Disconnect',
                         'icon': 'x', 'kind': 'danger'})
        return acts

    @api.model
    def run_connector_action(self, connector_id, method,
                             period_from=None, period_to=None):
        if method not in LIFECYCLE:
            d = self.get_connector_detail(connector_id)
            d['error'] = 'Action not permitted'
            return d
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        start, end = self._period(period_from, period_to)
        err = None
        try:
            if method == 'action_pull_data' and start:
                # The only lifecycle action that reads a window. The others
                # take no arguments and must keep being called with none.
                c.action_pull_data(period_from=start, period_to=end)
            else:
                getattr(c, method)()      # discard notification/reload return
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Action failed'
            _logger.warning("Connector action %s failed: %s", method, e)
        detail = self.get_connector_detail(connector_id)
        detail['error'] = err
        return detail

    # ================================================================== feeds
    def _default_pull_period(self, c):
        """The window the cockpit should offer, and why that one.

        The LAST window this connector's feeds were actually pulled for, when
        there is one — a connector being worked on for July should keep saying
        July until somebody changes it, rather than silently rolling to the
        current month the moment the calendar does. Otherwise the current
        month, which is the right guess for a first pull.

        Returned with the month's own bounds, never a partial month, so the
        control opens on something a pay run can use as-is.
        """
        today = date.today()
        start = today.replace(day=1)
        end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        Endpoint = self.env.get('hr.integration.endpoint') \
            if 'hr.integration.endpoint' in self.env else None
        if Endpoint is not None and Endpoint._schema_ready():
            last = Endpoint.search(
                [('connector_id', '=', c.id), ('last_period_from', '!=', False)],
                order='last_sync desc, id desc', limit=1)
            if last:
                start, end = last.last_period_from, last.last_period_to or end
        return {'from': str(start), 'to': str(end),
                'label': self._period_label(start, end)}

    @staticmethod
    def _period_label(start, end):
        """"Jul 2026", or "01 Jul – 15 Aug 2026" when it is not a whole month."""
        if not (start and end):
            return ''
        month_start = start.day == 1
        month_end = end.day == calendar.monthrange(end.year, end.month)[1]
        if month_start and month_end and (start.year, start.month) == (end.year, end.month):
            return start.strftime('%b %Y')
        return '%s – %s' % (start.strftime('%d %b'), end.strftime('%d %b %Y'))

    @staticmethod
    def _period(period_from, period_to):
        """The window a pull should ask the vendor for, validated.

        Returned as `(from, to)` strings, or `(None, None)` to let the model
        keep its own default. A half-given or malformed window is refused
        rather than half-applied: silently pulling a different month than the
        one on screen is the defect this parameter exists to fix, and doing it
        by falling back would reintroduce it one level down.
        """
        if not (period_from and period_to):
            return None, None
        try:
            start = fields.Date.to_date(period_from)
            end = fields.Date.to_date(period_to)
        except (TypeError, ValueError):
            raise ValidationError(_('That period is not a pair of dates.'))
        if not (start and end):
            raise ValidationError(_('That period is not a pair of dates.'))
        if end < start:
            raise ValidationError(_('A period cannot end before it starts.'))
        if (end - start).days > 366:
            raise ValidationError(_('Pull one year at a time or less.'))
        return start, end

    @api.model
    def sync_endpoint(self, connector_id, endpoint_id,
                      period_from=None, period_to=None):
        """Pull ONE feed, for a stated period.

        Returns the refreshed endpoint row (plus an `error` when the pull said
        something), so the chip can repaint itself without re-reading the whole
        connector. The endpoint is looked up THROUGH the connector rather than
        browsed by id alone: an id from the browser must not be able to make
        this method pull for a connector the caller was not looking at.

        `period_from`/`period_to` reach the vendor call. Without them the model
        falls back to the CURRENT calendar month, which is right for a routine
        refresh and wrong for every other case: a July pay run refreshed from
        this button in August got August's attendance, August's overtime and
        August's leave, stamped onto rows the run then read as July's. Nothing
        errored — the numbers were simply the wrong month's.
        """
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        if not c.exists():
            return {'error': 'Connector not found'}
        ep = c.endpoint_ids.filtered(lambda e: e.id == int(endpoint_id))
        if not ep:
            return {'error': 'That feed is not on this connector.'}
        start, end = self._period(period_from, period_to)
        err = None
        try:
            c.action_pull_endpoint(ep.id, period_from=start, period_to=end)
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Pull failed'
            _logger.warning("Endpoint sync failed for %s/%s: %s",
                            c.name, ep.code, e)
        ep.invalidate_recordset()
        c.invalidate_recordset()
        # `data_store_count` is the number the cockpit's own side panel prints,
        # and a pull that only refreshed the CHIP left the two disagreeing on
        # one screen — found on the live run: the feeds added up to 16 while
        # the panel beside them still said 11. One RPC, both numbers.
        return {'endpoint': self._endpoint_row(ep),
                'data_store_count': c.data_store_count,
                'error': err}

    @api.model
    def sync_catalog(self, connector_id):
        """Catalogue this connector's feeds — the empty state's one button.

        Create-only on the model side, so pressing it twice is free.
        """
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        if not c.exists():
            return {'error': 'Connector not found'}
        err = None
        res = {'created': 0, 'skipped': 0}
        try:
            res = c.action_sync_endpoint_catalog()
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Could not detect feeds'
            _logger.warning("Catalogue sync failed for %s: %s", c.name, e)
        detail = self.get_connector_detail(connector_id)
        detail['error'] = err
        detail['catalog'] = res
        return detail

    # ======================================================= feed configuration
    @staticmethod
    def _clean_url(value, label, allow_empty=True):
        value = (value or '').strip()
        if not value and allow_empty:
            return False
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValidationError(_('%s must be a complete HTTP(S) URL.') % label)
        if parsed.username or parsed.password:
            raise ValidationError(_('%s must not contain credentials.') % label)
        return value.rstrip('/')

    @api.model
    def save_configuration(self, connector_id, connector_vals, endpoint_rows):
        """Save public connection settings and additive feed definitions.

        Secrets stay behind `save_credentials`; this method never accepts
        their keys. A missing endpoint id creates a custom feed, while existing
        ids are resolved through this connector so the browser cannot move or
        edit another connector's row. There is intentionally no delete verb.
        """
        c = self.env['hr.integration.connector'].browse(int(connector_id or 0))
        if not c.exists():
            return {'error': 'Connector not found'}
        if not c.has_access('write'):
            raise AccessError(_('You cannot configure this connector.'))

        incoming = connector_vals or {}
        vals = {}
        if 'api_endpoint' in incoming:
            vals['api_endpoint'] = self._clean_url(
                incoming.get('api_endpoint'), _('API endpoint'))
        for key, label in (
                ('oauth_authorize_url', _('Authorization URL')),
                ('oauth_token_url', _('Token URL')),
                ('oauth_redirect_uri', _('Redirect URI'))):
            if key in incoming:
                vals[key] = self._clean_url(incoming.get(key), label)
        if 'oauth_scope' in incoming:
            vals['oauth_scope'] = (incoming.get('oauth_scope') or '').strip() or False
        if 'api_version' in incoming:
            vals['api_version'] = (incoming.get('api_version') or '').strip() or False
        if 'sync_interval' in incoming:
            try:
                interval = int(incoming.get('sync_interval') or 0)
            except (TypeError, ValueError):
                raise ValidationError(_('Sync interval must be a whole number.'))
            if interval < 0 or interval > 525600:
                raise ValidationError(_(
                    'Sync interval must be between 0 and 525600 minutes.'))
            vals['sync_interval'] = interval
        if vals:
            c.write(vals)

        Endpoint = self.env['hr.integration.endpoint']
        if not Endpoint._schema_ready():
            if endpoint_rows:
                raise ValidationError(_(
                    'Upgrade this database before changing feed definitions.'))
            c.invalidate_recordset()
            return self.get_connector_detail(c.id)
        allowed_operations = {key for key, _label in
                              Endpoint._fields['operation'].selection}
        allowed_types = {key for key, _label in
                         Endpoint._fields['data_type'].selection}
        allowed_methods = {key for key, _label in
                           Endpoint._fields['http_method'].selection}
        existing = Endpoint.with_context(active_test=False).search([
            ('connector_id', '=', c.id)])
        claimed_codes = {row.code: row.id for row in existing if row.code}
        for position, raw in enumerate(endpoint_rows or [], start=1):
            endpoint_id = int(raw.get('id') or 0)
            endpoint = existing.filtered(lambda row: row.id == endpoint_id)[:1]
            if endpoint_id and not endpoint:
                raise AccessError(_('That feed does not belong to this connector.'))
            code = (raw.get('code') or '').strip().lower()
            if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,63}', code):
                raise ValidationError(_(
                    'Feed codes use 2–64 lowercase letters, numbers, hyphens '
                    'or underscores.'))
            owner_id = claimed_codes.get(code)
            if owner_id and owner_id != endpoint.id:
                raise ValidationError(_(
                    'Feed code “%s” is already used on this connector.') % code)
            if endpoint and code != endpoint.code:
                seeded = self.env['hr.integration.endpoint.template'].with_context(
                    active_test=False).search([
                        ('connector_type', '=', c.connector_type),
                        ('code', '=', endpoint.code),
                    ], limit=1)
                if seeded:
                    raise ValidationError(_(
                        'A vendor feed code is stable and cannot be renamed. '
                        'Change its display name instead.'))
            operation = raw.get('operation') or 'catalog_only'
            data_type = raw.get('data_type') or ''
            method = (raw.get('http_method') or 'get').lower()
            if (operation not in allowed_operations or data_type not in allowed_types
                    or method not in allowed_methods):
                raise ValidationError(_(
                    'That feed has an unsupported configuration value.'))
            if (endpoint and data_type != endpoint.data_type and
                    self.env['hr.api.data.store'].search_count([
                        ('endpoint_id', '=', endpoint.id)])):
                raise ValidationError(_(
                    '“Produces” cannot change after this feed has stored data. '
                    'Create a new feed instead so existing provenance remains true.'))
            path = (raw.get('path') or '').strip()
            if path.startswith(('http://', 'https://')):
                path = self._clean_url(path, _('Feed URL'))
            elif path.startswith('//'):
                raise ValidationError(_('A feed path cannot start with //.'))
            row_vals = {
                'connector_id': c.id,
                'name': (raw.get('name') or code).strip(),
                'code': code,
                'data_type': data_type,
                'operation': operation,
                'http_method': method,
                'path': path or False,
                'params_note': (raw.get('params_note') or '').strip() or False,
                'active': bool(raw.get('active')),
            }
            if endpoint:
                old_code = endpoint.code
                endpoint.write(row_vals)
                if old_code != code:
                    claimed_codes.pop(old_code, None)
                claimed_codes[code] = endpoint.id
            else:
                created = Endpoint.create(row_vals)
                existing |= created
                claimed_codes[code] = created.id or -position

        c.invalidate_recordset()
        return self.get_connector_detail(c.id)

    @api.model
    def restore_endpoint_template(self, connector_id, endpoint_id):
        """Explicitly restore one feed; automatic detection never overwrites."""
        c = self.env['hr.integration.connector'].browse(int(connector_id or 0))
        if not c.exists() or not c.has_access('write'):
            raise AccessError(_('You cannot configure this connector.'))
        Endpoint = self.env['hr.integration.endpoint']
        if not Endpoint._schema_ready():
            return {'error': 'Upgrade this database before restoring feeds.'}
        endpoint = Endpoint.with_context(
            active_test=False).search([
                ('connector_id', '=', c.id),
                ('id', '=', int(endpoint_id or 0)),
            ], limit=1)
        if not endpoint:
            return {'error': 'Feed not found'}
        template = self.env['hr.integration.endpoint.template'].with_context(
            active_test=False).search([
                ('connector_type', '=', c.connector_type),
                ('code', '=', endpoint.code),
            ], limit=1)
        if not template:
            return {'error': 'This custom feed has no vendor template.'}
        endpoint.write({
            'name': template.name, 'data_type': template.data_type,
            'operation': template.operation or 'catalog_only',
            'http_method': template.http_method or 'get',
            'path': template.path or False,
            'params_note': template.params_note or False,
            'description': template.description or False,
            'sequence': template.sequence or 10,
            'is_legacy_abm': template.is_legacy_abm,
            'active': template.active,
        })
        return self.get_connector_detail(c.id)

    @api.model
    def fetch_endpoint_fields(self, connector_id, endpoint_id):
        """Ask the vendor what this feed delivers, and catalogue the answer.

        Integrations Cycle 6, WP-3. Three things this method is careful about:

          * the endpoint is resolved THROUGH the connector, never browsed by id
            alone — the same rail `sync_endpoint` has, for the same reason: an
            id from the browser must not be able to write a catalogue row onto
            a connector the caller was not looking at;
          * a connector class that cannot really be asked says so. Three of the
            seven (`sap`, `workday`, `oracle`) have a `get_available_fields`
            that logs "not implemented" and returns a hard-coded example list;
            `HrIntegrationConnector.FIELD_FETCH_SUPPORT` refuses those by name
            rather than publishing four invented fields as SAP's schema;
          * NOTHING in the return value comes from a credential. The connector's
            `field_fetch_capability` reads them as booleans, under `sudo`, and
            returns a sentence.
        """
        c = self.env['hr.integration.connector'].browse(int(connector_id or 0))
        if not c.exists():
            return {'error': 'Connector not found'}
        ep = c.endpoint_ids.filtered(lambda e: e.id == int(endpoint_id or 0))
        if not ep:
            return {'error': 'That feed is not on this connector.'}
        if not c.has_access('write'):
            return {'error': 'You cannot change this connector.'}
        res = c.action_fetch_endpoint_fields(ep.id)
        ep.invalidate_recordset()
        return {'endpoint': self._endpoint_row(ep),
                'ok': bool(res.get('ok')),
                'created': res.get('created', 0),
                'updated': res.get('updated', 0),
                'msg': res.get('msg') or '',
                'error': None if res.get('ok') else (res.get('msg') or '')}

    # ============================================================ credentials
    @api.model
    def save_credentials(self, connector_id, vals, clear=None):
        """Write the connector's secrets. Never read them back.

        Four rails, and each of them is the reason for a different past bug:

          * the gate is EXPLICIT and raises. The fields' own `groups=` would
            refuse the write anyway, but it would refuse it as an ORM traceback
            about a field that "does not exist" — a control that fails
            incomprehensibly is a control nobody reports (W40);
          * the keys are a WHITELIST. A forged key must not be able to write
            `active`, `company_id` or anything else on the connector through a
            method whose name says credentials;
          * an EMPTY STRING IS NOT A CLEAR. The inputs are write-only with an
            "unchanged" placeholder, so an untouched field arrives empty on
            every save — treating that as "delete the secret" would wipe a
            working connector the first time somebody fixed a typo in another
            field. Deletion is the explicit `clear` list;
          * the response is `_credentials()`, i.e. booleans.
        """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                "Only a system administrator may change a connector's "
                "credentials."))
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        if not c.exists():
            return {'error': 'Connector not found'}

        write_vals = {}
        for key, value in (vals or {}).items():
            if key not in WRITABLE_CREDENTIAL_KEYS:
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            if key == 'auth_type' and value not in CRED_SETS:
                # A selection the model does not know raises a ValueError deep
                # in the ORM; refusing it here keeps the whole call meaningful.
                continue
            write_vals[key] = value.strip()
        for key in (clear or []):
            if key in WRITABLE_CREDENTIAL_KEYS and key != 'auth_type':
                write_vals[key] = False

        if write_vals:
            c.write(write_vals)
        c.invalidate_recordset()
        return {'credentials': self._credentials(c),
                'api_endpoint': c.api_endpoint or '',
                'saved': sorted(write_vals), 'error': None}

    @api.model
    def get_link(self, connector_id, method):
        if method not in LINKS:
            return False
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        try:
            return getattr(c, method)() or False
        except Exception as e:
            _logger.debug("connector get_link %s failed: %s", method, e)
            return False
