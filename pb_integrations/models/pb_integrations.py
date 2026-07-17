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
STATUS_LABEL = {'disconnected': 'Disconnected', 'connecting': 'Connecting',
                'connected': 'Connected', 'error': 'Error'}
STATUS_CLS = {'connected': 'ok', 'error': 'err', 'connecting': 'warn', 'disconnected': 'muted'}

LINKS = [
    ('pb_hr_payroll_formula.action_field_mapping', 'Field Mappings', 'Source → rule mappings', 'list'),
    ('pb_hr_payroll_formula.action_api_data_store', 'API Data Store', 'Staged & versioned records', 'database'),
    ('pb_hr_payroll_formula.action_api_transformation_rule', 'Transformation Rules', 'Derived computed values', 'sigma'),
]


class PbIntegrations(models.AbstractModel):
    _name = 'pb.integrations'
    _description = 'Payobook integrations cockpit'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Integrations metric failed: %s", e)
            return default

    @api.model
    def get_board(self):
        if 'hr.integration.connector' not in self.env:
            return {'kpis': {}, 'connectors': [], 'links': [], 'total': 0, 'shown': 0}
        C = self.env['hr.integration.connector']
        cons = self._safe(lambda: C.search([], order='name'), default=C.browse())

        rows = []
        connected = errored = 0
        synced = mappings = staged = 0
        for c in cons:
            try:
                status = c.connection_status or 'disconnected'
                if status == 'connected':
                    connected += 1
                if status == 'error':
                    errored += 1
                mc = getattr(c, 'mapping_count', 0) or len(c.field_mapping_ids)
                dc = getattr(c, 'data_store_count', 0) or len(c.data_store_ids)
                sr = getattr(c, 'total_synced_records', 0) or 0
                synced += sr
                mappings += mc
                staged += dc
                rows.append({
                    'id': c.id, 'name': c.name or '—',
                    'type': c.connector_type or '', 'type_label': TYPE_LABEL.get(c.connector_type, c.connector_type or '—'),
                    'icon': TYPE_ICON.get(c.connector_type, 'plug'),
                    'status': status, 'status_label': STATUS_LABEL.get(status, status),
                    'status_cls': STATUS_CLS.get(status, 'muted'),
                    'country': c.country_code or '',
                    'last_sync': str(c.last_sync or ''),
                    'mappings': mc, 'staged': dc, 'synced': sr,
                })
            except Exception as ex:
                _logger.debug("Connector row failed: %s", ex)
                continue

        types = {}
        for r in rows:
            types[r['type']] = types.get(r['type'], 0) + 1

        links = []
        for xmlid, label, desc, icon in LINKS:
            if self.env.ref(xmlid, raise_if_not_found=False):
                links.append({'xmlid': xmlid, 'label': label, 'desc': desc, 'icon': icon})

        return {
            'kpis': {
                'connectors': len(rows), 'connected': connected, 'errors': errored,
                'synced': synced, 'mappings': mappings, 'staged': staged,
            },
            'types': [{'name': TYPE_LABEL.get(k, k), 'type': k, 'count': v}
                      for k, v in sorted(types.items(), key=lambda x: -x[1])],
            'connectors': rows,
            'links': links,
            'total': len(rows), 'shown': len(rows),
        }
