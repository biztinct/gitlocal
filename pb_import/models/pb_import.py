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
# IA Cycle 3 — the one-door law. `pb_hr_payroll_formula.action_integration_
# connector` used to be a launch tile here: a raw `list,form` on
# hr.integration.connector, sitting beside two guided wizards and looking like
# one of them. It is gone, along with the Connectors KPI and the Connectors
# panel below. Connectors have exactly ONE home now (Settings · Integrations),
# and Import reaches it through a back-chipped deep link — the same cockpit, and
# for the first time the same way back.
#
# The action itself is untouched and still registered: this cycle replaces the
# DOORS, not the models behind them.
LAUNCH_CANDIDATES = [
    ('pb_hr_payroll_formula.action_payroll_import_batch_new',
     'New Import Batch', 'Upload a file and run map → validate → commit', 'upload', True),
    ('pb_import_advanced.action_pb_multisheet_wizard',
     'Multi-sheet Excel', 'Guided multi-tab workbook import', 'table', False),
    ('pb_import_advanced.action_pb_employee_wizard',
     'Import Employees', 'Create employees from file or Zoho', 'users', False),
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
        # NOT a list any more — a COUNT, and only so the deep link can say how
        # many are over there ("Manage connectors · 31"). Reading 24 connector
        # rows to render a panel this cockpit no longer owns would be work done
        # for a surface that is gone. `has_connectors` is separate from the
        # number because a database with the model but no rows is a real state
        # and "0" is a fact, not a missing key (W45).
        connectors = 0
        has_model = 'hr.integration.connector' in self.env
        if has_model:
            connectors = self._safe(
                lambda: self.env['hr.integration.connector'].search_count([]))

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
            },
            'pipeline': [{'key': s, 'label': STATE_LABEL[s],
                          'count': state_counts.get(s, 0)} for s in PIPELINE],
            'batches': batches,
            'connectors': connectors,
            'has_connectors': has_model,
            'launches': launches,
        }
