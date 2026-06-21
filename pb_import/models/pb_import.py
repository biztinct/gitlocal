# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Batch lifecycle — ordered pipeline + terminal/exception states.
STATE_LABEL = {
    'draft': 'Draft', 'loaded': 'Loaded', 'matched': 'Matched',
    'validated': 'Validated', 'processing': 'Processing', 'done': 'Done',
    'error': 'Error', 'cancelled': 'Cancelled',
}
PIPELINE = ['draft', 'loaded', 'matched', 'validated', 'processing', 'done']

SOURCE_LABEL = {
    'excel': 'Excel / CSV', 'connector': 'Connector',
    'api_data_store': 'API store', 'manual': 'Manual',
}
CONNECTOR_LABEL = {
    'zoho': 'Zoho People', 'excel': 'Excel File', 'sap': 'SAP SuccessFactors',
    'workday': 'Workday', 'oracle': 'Oracle HCM', 'demo': 'Demo / Stub',
}

LAUNCH_CANDIDATES = [
    ('pb_hr_payroll_formula.action_payroll_import_batch_new',
     'New Import Batch', 'Upload a file and run map → validate → commit', 'upload', True),
    ('pb_import_advanced.action_pb_multisheet_wizard',
     'Multi-sheet Excel', 'Guided multi-tab workbook import', 'table', False),
    ('pb_import_advanced.action_pb_employee_wizard',
     'Import Employees', 'Create employees from file or Zoho', 'users', False),
    ('pb_hr_payroll_formula.action_integration_connector',
     'Connectors', 'Manage external HR / payroll systems', 'plug', False),
    ('pb_import_advanced.action_pb_formula_wizard',
     'Import Formula Config', 'Load rules from salary structure or file', 'function', False),
]


class PbImport(models.AbstractModel):
    _name = 'pb.import'
    _description = 'Payobook Import cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Import metric failed: %s", e)
            return default

    @api.model
    def get_import_data(self):
        company = self.env.company
        co_ids = self.env.companies.ids or [company.id]
        DOM = [('company_id', 'in', co_ids)]

        # ---------- batches ----------
        batches = []
        state_counts = {k: 0 for k in STATE_LABEL}
        total_batches = 0
        if 'hr.payroll.import.batch' in self.env:
            Batch = self.env['hr.payroll.import.batch']
            total_batches = self._safe(lambda: Batch.search_count(DOM))
            try:
                for g in Batch.read_group(DOM, ['state'], ['state']):
                    st = g.get('state')
                    if st in state_counts:
                        state_counts[st] = g.get('state_count') or g.get('__count') or 0
            except Exception:
                pass
            try:
                recs = Batch.search_read(
                    DOM,
                    ['name', 'state', 'source_type', 'date_from', 'date_to',
                     'total_lines', 'matched_employees', 'new_employees',
                     'error_lines', 'create_date'],
                    order='create_date desc, id desc', limit=20)
                for r in recs:
                    st = r.get('state')
                    batches.append({
                        'id': r['id'],
                        'name': r.get('name') or '—',
                        'state': st,
                        'state_label': STATE_LABEL.get(st, st or '—'),
                        'step': (PIPELINE.index(st) + 1) if st in PIPELINE else 0,
                        'source': SOURCE_LABEL.get(r.get('source_type'), r.get('source_type') or '—'),
                        'total_lines': r.get('total_lines') or 0,
                        'matched': r.get('matched_employees') or 0,
                        'new': r.get('new_employees') or 0,
                        'errors': r.get('error_lines') or 0,
                        'date': str(r.get('create_date') or '')[:10],
                    })
            except Exception as e:
                _logger.debug("Import batch list failed: %s", e)

        done = state_counts.get('done', 0)
        errors = state_counts.get('error', 0)
        in_progress = sum(state_counts.get(s, 0)
                          for s in ('draft', 'loaded', 'matched', 'validated', 'processing'))

        # ---------- connectors ----------
        connectors = []
        if 'hr.integration.connector' in self.env:
            Conn = self.env['hr.integration.connector']
            try:
                recs = Conn.search_read(
                    [], ['name', 'connector_type', 'active',
                         'last_sync', 'connection_status', 'last_sync_status'],
                    order='name', limit=24)
                for r in recs:
                    connectors.append({
                        'id': r['id'],
                        'name': r.get('name') or '—',
                        'type': r.get('connector_type') or '',
                        'type_label': CONNECTOR_LABEL.get(r.get('connector_type'),
                                                          r.get('connector_type') or '—'),
                        'active': bool(r.get('active')),
                        'status': r.get('connection_status') or 'disconnected',
                        'sync_status': r.get('last_sync_status') or '',
                        'last_sync': str(r.get('last_sync') or '')[:16],
                    })
            except Exception as e:
                _logger.debug("Connector list failed: %s", e)

        # ---------- launch buttons ----------
        launches = []
        for xmlid, label, desc, icon, primary in LAUNCH_CANDIDATES:
            try:
                if self.env.ref(xmlid, raise_if_not_found=False):
                    launches.append({'xmlid': xmlid, 'label': label, 'desc': desc,
                                     'icon': icon, 'primary': primary})
            except Exception:
                continue

        return {
            'company': company.name,
            'kpis': {
                'total_batches': total_batches, 'done': done,
                'in_progress': in_progress, 'errors': errors,
                'connectors': len(connectors),
            },
            'pipeline': [{'key': s, 'label': STATE_LABEL[s],
                          'count': state_counts.get(s, 0)} for s in PIPELINE],
            'batches': batches,
            'connectors': connectors,
            'launches': launches,
        }
