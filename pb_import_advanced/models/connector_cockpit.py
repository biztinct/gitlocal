# -*- coding: utf-8 -*-
import logging
from odoo import api, models

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
            'next_actions': self._connector_actions(c),
            'error': None,
        }

    def _connector_actions(self, c):
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
