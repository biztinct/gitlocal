# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

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
LINE_LABEL = {
    'matched': 'Matched', 'validated': 'Validated', 'processed': 'Processed',
    'unmatched': 'Unmatched', 'error': 'Error', 'draft': 'Pending',
}

# state -> contextual next-action buttons (draft handled specially for source)
NEXT_ACTIONS = {
    'loaded':    [('action_match_employees', 'Match employees', 'users', 'primary')],
    'matched':   [('action_validate', 'Validate', 'check', 'primary')],
    'validated': [('action_process', 'Commit import', 'play', 'primary')],
    'processing': [],
    'done':      [],
    'error':     [('action_reset_to_draft', 'Reset to draft', 'rotate', 'ghost')],
    'cancelled': [('action_reset_to_draft', 'Reset to draft', 'rotate', 'ghost')],
}
LIFECYCLE = {
    'action_load_file', 'action_load_from_data_store', 'action_match_employees',
    'action_validate', 'action_process', 'action_reset_to_draft', 'action_cancel',
}
# view-actions that return a real act_window dict to forward to doAction
LINKS = {
    'action_view_created_employees', 'action_view_created_payslips',
    'action_open_payslip_run', 'action_view_error_lines',
}


class PbImportBatchCockpit(models.AbstractModel):
    """Read-friendly batch-detail cockpit. Drives the existing
    hr.payroll.import.batch lifecycle: every native action_* returns a
    reload/act_window dict which we DISCARD and re-read truth from the DB."""
    _name = 'pb.import.batch.cockpit'
    _description = 'Payobook import batch detail cockpit'

    @api.model
    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Batch cockpit metric failed: %s", e)
            return default

    # ------------------------------------------------------------------ detail
    @api.model
    def get_batch_detail(self, batch_id):
        b = self.env['hr.payroll.import.batch'].browse(int(batch_id))
        if not b.exists():
            return {'error': 'Batch not found'}
        allowed = self.env.companies.ids or [self.env.company.id]
        if b.company_id and b.company_id.id not in allowed:
            return {'error': 'Batch not found'}

        lines = []
        for l in b.import_line_ids[:500]:
            lines.append({
                'id': l.id,
                'code': l.employee_code or '',
                'name': l.employee_name or '—',
                'email': l.employee_email or '',
                'state': l.state,
                'state_label': ('New employee' if l.is_new_employee else LINE_LABEL.get(l.state, l.state)),
                'is_new': bool(l.is_new_employee),
                'employee_id': l.employee_id.id or False,
                'employee_name': l.employee_id.name or '',
                'error': l.error_message or '',
            })

        cur_idx = PIPELINE.index(b.state) if b.state in PIPELINE else -1
        pipeline = [{
            'key': s, 'label': STATE_LABEL[s],
            'done': (i < cur_idx) if cur_idx >= 0 else False,
            'current': s == b.state,
        } for i, s in enumerate(PIPELINE)]

        return {
            'batch_id': b.id,
            'name': b.name or '—',
            'state': b.state,
            'state_label': STATE_LABEL.get(b.state, b.state),
            'source': SOURCE_LABEL.get(b.source_type, b.source_type or '—'),
            'source_type': b.source_type,
            # RECORDS R1 — a batch that changed no record has to say so on the
            # screen someone opens afterwards to ask "what did this do?".
            'one_time': bool(getattr(b, 'one_time', False)),
            'config': b.formula_config_id.name or '',
            'company': b.company_id.name or '',
            'period': b.payroll_period or '',
            'date_from': str(b.date_from or ''),
            'date_to': str(b.date_to or ''),
            'pipeline': pipeline,
            'counts': {
                'total': b.total_lines, 'matched': b.matched_employees,
                'new': b.new_employees, 'errors': b.error_lines,
                'processed': b.processed_lines,
            },
            'results': {
                'created_employees': len(b.created_employee_ids),
                'created_payslips': len(b.created_payslip_ids),
                'payslip_run_id': b.payslip_run_id.id or False,
                'payslip_run_name': b.payslip_run_id.name or '',
            },
            'lines': lines,
            'next_actions': self._available_actions(b),
            'error': None,
        }

    def _available_actions(self, b):
        acts = []
        if b.state == 'draft':
            if b.source_type in ('connector', 'api_data_store'):
                acts.append({'method': 'action_load_from_data_store',
                             'label': 'Load data', 'icon': 'upload', 'kind': 'primary'})
            elif b.source_type == 'excel':
                acts.append({'method': 'action_load_file',
                             'label': 'Load file', 'icon': 'upload', 'kind': 'primary'})
        else:
            for (m, label, icon, kind) in NEXT_ACTIONS.get(b.state, []):
                acts.append({'method': m, 'label': label, 'icon': icon, 'kind': kind})
        if b.state not in ('done', 'cancelled', 'processing'):
            acts.append({'method': 'action_cancel', 'label': 'Cancel',
                         'icon': 'x', 'kind': 'danger'})
        return acts

    # ------------------------------------------------------------------ actions
    @api.model
    def run_batch_action(self, batch_id, method):
        if method not in LIFECYCLE:
            d = self.get_batch_detail(batch_id)
            d['error'] = 'Action not permitted'
            return d
        b = self.env['hr.payroll.import.batch'].browse(int(batch_id))
        err = None
        try:
            getattr(b, method)()          # discard reload/act_window return
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Action failed'
            _logger.warning("Batch cockpit action %s failed: %s", method, e)
        detail = self.get_batch_detail(batch_id)
        detail['error'] = err
        return detail

    @api.model
    def get_link(self, batch_id, method):
        """Return the act_window dict for a result-view action, for the OWL
        side to forward to doAction. Returns False if not permitted/failed."""
        if method not in LINKS:
            return False
        b = self.env['hr.payroll.import.batch'].browse(int(batch_id))
        try:
            return getattr(b, method)() or False
        except Exception as e:
            _logger.debug("get_link %s failed: %s", method, e)
            return False

    # ------------------------------------------------------------------ lines
    @api.model
    def fix_line(self, line_id, op):
        line = self.env['hr.payroll.import.line'].browse(int(line_id))
        try:
            if op == 'retry' and hasattr(line, 'action_retry'):
                line.action_retry()
            elif op == 'skip' and hasattr(line, 'action_skip'):
                line.action_skip()
        except Exception as e:
            _logger.debug("fix_line failed: %s", e)
        return self.get_batch_detail(line.batch_id.id)

    @api.model
    def search_employees(self, term, limit=20):
        term = (term or '').strip()
        dom = []
        if term:
            dom = ['|', '|', ('name', 'ilike', term),
                   ('barcode', 'ilike', term), ('work_email', 'ilike', term)]
        return [{'id': e.id, 'name': e.name, 'code': e.barcode or '',
                 'email': e.work_email or ''}
                for e in self.env['hr.employee'].search(dom, limit=limit)]

    @api.model
    def match_line(self, line_id, employee_id=False, create_new=False):
        line = self.env['hr.payroll.import.line'].browse(int(line_id))
        try:
            if create_new:
                line.write({'is_new_employee': True, 'employee_id': False, 'state': 'matched'})
            elif employee_id:
                line.write({'employee_id': int(employee_id),
                            'is_new_employee': False, 'state': 'matched'})
        except Exception as e:
            _logger.debug("match_line failed: %s", e)
        return self.get_batch_detail(line.batch_id.id)
