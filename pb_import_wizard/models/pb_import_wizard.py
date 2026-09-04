# -*- coding: utf-8 -*-
import calendar
import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

SOURCES = [
    {'id': 'excel', 'label': 'Excel / CSV file'},
    {'id': 'api_data_store', 'label': 'API data store'},
    {'id': 'manual', 'label': 'Manual entry'},
]


def _period_presets():
    """Quick period chips for step 1 — mirrors hr.payroll.import.batch
    _onchange_payroll_period so the dates match the native form."""
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    first_cur = today.replace(day=1)
    last_prev = first_cur - timedelta(days=1)
    def iso(d):
        return d.isoformat()
    return [
        {'id': 'current', 'label': 'This month',
         'date_from': iso(first_cur), 'date_to': iso(today.replace(day=last_day))},
        {'id': 'previous', 'label': 'Last month',
         'date_from': iso(last_prev.replace(day=1)), 'date_to': iso(last_prev)},
        {'id': 'mid_cycle', 'label': 'Mid cycle',
         'date_from': iso(first_cur), 'date_to': iso(today.replace(day=15))},
        {'id': 'end_cycle', 'label': 'End cycle',
         'date_from': iso(first_cur), 'date_to': iso(today.replace(day=last_day))},
        {'id': 'custom', 'label': 'Custom', 'date_from': '', 'date_to': ''},
    ]


def _err(e):
    return str(getattr(e, 'name', None) or e) or 'Unexpected error'


class PbImportWizard(models.AbstractModel):
    """Backend orchestration for the guided Import wizard.

    Drives the existing hr.payroll.import.batch lifecycle (load → match →
    validate → process) — no new lifecycle logic. Each step is wrapped so a
    failure surfaces as a readable message rather than aborting the UI.
    """
    _name = 'pb.import.wizard'
    _description = 'Payobook guided import wizard orchestration'

    # ---------------- Step 1: defaults ----------------
    @api.model
    def get_defaults(self):
        today = fields.Date.today()
        configs = []
        try:
            for c in self.env['hr.formula.config'].search([], limit=50):
                configs.append({'id': c.id, 'name': c.name})
        except Exception:
            pass
        connectors = []
        try:
            for c in self.env['hr.integration.connector'].search(
                    [('active', '=', True)], limit=20):
                connectors.append({'id': c.id, 'name': c.name, 'type': c.connector_type})
        except Exception:
            pass
        return {
            'today': today.isoformat(),
            'company': self.env.company.name,
            'name': 'Import %s' % today.strftime('%d %b %Y'),
            'sources': SOURCES,
            'configs': configs,
            'connectors': connectors,
            'periods': _period_presets(),
        }

    # ---------------- summary ----------------
    @api.model
    def get_summary(self, batch_id):
        b = self.env['hr.payroll.import.batch'].browse(batch_id)
        if not b.exists():
            return {'error': 'Batch not found'}
        lines = []
        for l in b.import_line_ids[:300]:
            lines.append({
                'id': l.id,
                'code': l.employee_code or '',
                'name': l.employee_name or '—',
                'state': l.state,
                'is_new': bool(l.is_new_employee),
                'error': l.error_message or '',
            })
        return {
            'batch_id': b.id, 'name': b.name, 'state': b.state,
            'total_lines': b.total_lines, 'matched': b.matched_employees,
            'new': b.new_employees, 'errors': b.error_lines, 'processed': b.processed_lines,
            'lines': lines,
            'created_employees': len(b.created_employee_ids),
            'created_payslips': len(b.created_payslip_ids),
            'payslip_run_id': b.payslip_run_id.id or False,
            'payslip_run_name': b.payslip_run_id.name or '',
            'error': None,
        }

    # ---------------- Step 1 → 2: create + load + match ----------------
    @api.model
    def create_and_load(self, vals):
        Batch = self.env['hr.payroll.import.batch']
        source = vals.get('source_type') or 'excel'
        cvals = {
            'name': vals.get('name') or 'Import',
            'source_type': source,
        }
        if vals.get('formula_config_id'):
            cvals['formula_config_id'] = int(vals['formula_config_id'])
        if vals.get('connector_id'):
            cvals['connector_id'] = int(vals['connector_id'])
        if vals.get('date_from'):
            cvals['date_from'] = vals['date_from']
        if vals.get('date_to'):
            cvals['date_to'] = vals['date_to']
        # the OWL wizard sends file_b64 / file_name; accept import_file too
        _file = vals.get('import_file') or vals.get('file_b64')
        if _file:
            cvals['import_file'] = _file
            cvals['import_filename'] = (
                vals.get('import_filename') or vals.get('file_name') or 'import.xlsx'
            )
        batch = Batch.create(cvals)

        err = None
        try:
            if source == 'api_data_store':
                batch.action_load_from_data_store()
            elif source == 'excel':
                batch.action_load_file()
            # manual: leave at draft for the user to add lines on the form
        except Exception as e:
            _logger.warning("Import wizard load failed: %s", e)
            err = _err(e)
        # auto-match after a successful load
        if not err and batch.state == 'loaded':
            try:
                batch.action_match_employees()
            except Exception as e:
                _logger.warning("Import wizard match failed: %s", e)
                err = _err(e)
        s = self.get_summary(batch.id)
        s['error'] = err
        return s

    # ---------------- Step 2 → 3: validate ----------------
    @api.model
    def do_validate(self, batch_id):
        b = self.env['hr.payroll.import.batch'].browse(batch_id)
        err = None
        try:
            b.action_validate()
        except Exception as e:
            _logger.warning("Import wizard validate failed: %s", e)
            err = _err(e)
        s = self.get_summary(batch_id)
        s['error'] = err
        return s

    # ---------------- Step 3 → 4: process (commit) ----------------
    @api.model
    def do_process(self, batch_id):
        b = self.env['hr.payroll.import.batch'].browse(batch_id)
        err = None
        try:
            b.action_process()
        except Exception as e:
            _logger.warning("Import wizard process failed: %s", e)
            err = _err(e)
        s = self.get_summary(batch_id)
        s['error'] = err
        return s

    # ---------------- inline line fixes ----------------
    @api.model
    def fix_line(self, line_id, op):
        line = self.env['hr.payroll.import.line'].browse(line_id)
        try:
            if op == 'retry' and hasattr(line, 'action_retry'):
                line.action_retry()
            elif op == 'skip' and hasattr(line, 'action_skip'):
                line.action_skip()
        except Exception as e:
            _logger.debug("fix_line failed: %s", e)
        return self.get_summary(line.batch_id.id)

    # ---------------- inline manual match (mirrors line match wizard action_confirm) ----------------
    @api.model
    def search_employees(self, term, limit=20):
        """Typeahead for the inline manual-match picker."""
        term = (term or '').strip()
        dom = []
        if term:
            dom = ['|', '|', ('name', 'ilike', term),
                   ('barcode', 'ilike', term), ('work_email', 'ilike', term)]
        out = []
        for e in self.env['hr.employee'].search(dom, limit=limit):
            out.append({'id': e.id, 'name': e.name,
                        'code': e.barcode or '', 'email': e.work_email or ''})
        return out

    @api.model
    def match_line(self, line_id, employee_id=False, create_new=False):
        """Resolve one line: attach an existing employee, or flag a new one
        to be created on commit. Replicates hr.payroll.import.line.match.wizard."""
        line = self.env['hr.payroll.import.line'].browse(line_id)
        try:
            if create_new:
                line.write({'is_new_employee': True, 'employee_id': False, 'state': 'matched'})
            elif employee_id:
                line.write({'employee_id': int(employee_id),
                            'is_new_employee': False, 'state': 'matched'})
        except Exception as e:
            _logger.debug("match_line failed: %s", e)
        return self.get_summary(line.batch_id.id)
