# -*- coding: utf-8 -*-
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError

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

# ============================================================== credentials
#
# What each authentication type actually needs, and NOTHING about what is in
# it. The panel is write-only by construction: every RPC on this facade returns
# `is_set` booleans and never a value, not even a masked prefix — a masked
# secret is still a secret with its length and shape published, and the moment
# one path returns one, every future path is a judgement call.
#
# `secret` marks the fields Odoo itself keeps behind `base.group_system`
# (`integration_connector.py`:88-126). The three OAuth locations are plain
# configuration on the connector, but they are listed here because they are
# edited in the same breath as the credentials they belong to — and they are
# returned the same way, as `is_set` only, so the rule has no exceptions to
# remember.
CRED_SETS = {
    'oauth2': [
        ('client_id', 'Client ID', True),
        ('client_secret', 'Client Secret', True),
        ('refresh_token', 'Refresh Token', True),
        ('oauth_authorize_url', 'Authorization URL', False),
        ('oauth_token_url', 'Token URL', False),
        ('oauth_scope', 'OAuth Scope', False),
    ],
    'api_key': [('api_key', 'API Key', True)],
    'basic': [('username', 'Username', True), ('password', 'Password', True)],
    'bearer': [('access_token', 'Access Token', True)],
}

# Everything `save_credentials` will write, and the ONLY things it will write.
# `api_endpoint` and `auth_type` are here because changing an auth type without
# being able to fill in what it then needs is a dead end.
WRITABLE_CREDENTIAL_KEYS = (
    {k for fields_ in CRED_SETS.values() for k, _l, _s in fields_}
    | {'api_endpoint', 'auth_type'}
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
            'last_sync': str(c.last_sync or '')[:16],
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
            'last_sync': str(c.last_sync or '')[:16],
            'sync_status': c.last_sync_status or '',
            'sync_message': c.last_sync_message or '',
            'last_error': c.last_error or '',
            'api_endpoint': c.api_endpoint or '',
            'mappings': mappings,
            'mapping_count': len(c.field_mapping_ids),
            'data_store_count': len(c.data_store_ids),
            'rules': rules,
            'endpoints': self._endpoints(c),
            'credentials': self._credentials(c),
            'can_write': c.has_access('write'),
            'next_actions': self._connector_actions(c),
            'error': None,
        }

    # =================================================================== feeds
    def _endpoint_row(self, e):
        return {
            'id': e.id,
            'name': e.name or e.code or '—',
            'code': e.code or '',
            'data_type': e.data_type or '',
            'data_type_label': dict(
                e._fields['data_type'].selection).get(e.data_type, e.data_type or ''),
            'icon': DATA_TYPE_ICON.get(e.data_type, 'database'),
            'method': (e.http_method or 'get').upper(),
            'path': e.path or '',
            'params_note': e.params_note or '',
            # Both halves of W46: the machine twin beside the display one, from
            # the same field in the same expression, so the two can never end up
            # describing different moments.
            'last_sync': str(e.last_sync or '')[:16],
            'last_sync_iso': e.last_sync.isoformat() if e.last_sync else '',
            'status': e.last_sync_status or '',
            'last_error': e.last_error or '',
            'synced': e.synced_count,
            'staged': e.staged_count,
            'mapping_count': e.mapping_count,
            'is_legacy_abm': bool(e.is_legacy_abm),
        }

    def _endpoints(self, c):
        # The TABLE, not the registry — see `_schema_ready`'s docstring. On a
        # database that has not been upgraded since the model was added, this
        # cockpit answered 500 rather than rendering without a feeds strip.
        Endpoint = self.env.get('hr.integration.endpoint') \
            if 'hr.integration.endpoint' in self.env else None
        if Endpoint is None or not Endpoint._schema_ready():
            return []
        return [self._endpoint_row(e) for e in c.endpoint_ids]

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
    def run_connector_action(self, connector_id, method):
        if method not in LIFECYCLE:
            d = self.get_connector_detail(connector_id)
            d['error'] = 'Action not permitted'
            return d
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        err = None
        try:
            getattr(c, method)()          # discard notification/reload return
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Action failed'
            _logger.warning("Connector action %s failed: %s", method, e)
        detail = self.get_connector_detail(connector_id)
        detail['error'] = err
        return detail

    # ================================================================== feeds
    @api.model
    def sync_endpoint(self, connector_id, endpoint_id):
        """Pull ONE feed — `action_pull_data` scoped to that feed's data type.

        Returns the refreshed endpoint row (plus an `error` when the pull said
        something), so the chip can repaint itself without re-reading the whole
        connector. The endpoint is looked up THROUGH the connector rather than
        browsed by id alone: an id from the browser must not be able to make
        this method pull for a connector the caller was not looking at.
        """
        c = self.env['hr.integration.connector'].browse(int(connector_id))
        if not c.exists():
            return {'error': 'Connector not found'}
        ep = c.endpoint_ids.filtered(lambda e: e.id == int(endpoint_id))
        if not ep:
            return {'error': 'That feed is not on this connector.'}
        err = None
        try:
            c.action_pull_data(data_types=[ep.data_type])
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
