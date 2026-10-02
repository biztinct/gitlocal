# -*- coding: utf-8 -*-
import calendar
import logging
from datetime import date

from odoo import api, models

_logger = logging.getLogger(__name__)

DATA_TYPES = [
    {'id': 'pull_employee', 'label': 'Employees'},
    {'id': 'pull_salary', 'label': 'Salary / Payroll'},
    {'id': 'pull_dependent', 'label': 'Dependents'},
    {'id': 'pull_attendance', 'label': 'Attendance'},
    {'id': 'pull_leave', 'label': 'Leave / Time-off'},
]


class PbSyncWizard(models.AbstractModel):
    """Bespoke guided wrapper around hr.integration.sync.wizard
    (configure pull -> preview -> pull)."""
    _name = 'pb.import.sync.wizard'
    _description = 'Payobook guided connector sync'

    _MODEL = 'hr.integration.sync.wizard'

    @api.model
    def get_defaults(self, connector_id=False):
        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        c = self.env['hr.integration.connector'].browse(int(connector_id)) if connector_id else None
        return {
            'data_types': DATA_TYPES,
            'connector_id': c.id if c else False,
            'connector_name': c.name if c else '',
            'connector_type': c.connector_type if c else '',
            'date_from': today.replace(day=1).isoformat(),
            'date_to': today.replace(day=last_day).isoformat(),
        }

    def _vals(self, vals):
        cvals = {
            'connector_id': int(vals['connector_id']),
            'run_transformations': bool(vals.get('run_transformations', True)),
        }
        for dt in DATA_TYPES:
            cvals[dt['id']] = bool(vals.get(dt['id'], True))
        if vals.get('date_from'):
            cvals['date_from'] = vals['date_from']
        if vals.get('date_to'):
            cvals['date_to'] = vals['date_to']
        if vals.get('max_records'):
            cvals['max_records'] = int(vals['max_records'])
        if vals.get('file_b64'):
            cvals['import_file'] = vals['file_b64']
            cvals['import_filename'] = vals.get('file_name') or 'sync.xlsx'
        return cvals

    def _summary(self, rec):
        return {
            'wizard_id': rec.id,
            'state': rec.state,
            'preview': {
                'employees': rec.preview_employee_count,
                'records': rec.preview_record_count,
            },
        }

    @api.model
    def create_and_preview(self, vals):
        rec = self.env[self._MODEL].create(self._vals(vals))
        err = None
        try:
            rec.action_preview()
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Preview failed.'
            _logger.warning("Sync preview failed: %s", e)
        out = self._summary(rec)
        out['error'] = err
        return out

    @api.model
    def do_pull(self, wizard_id):
        rec = self.env[self._MODEL].browse(int(wizard_id))
        err = None
        try:
            rec.action_pull()
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Pull failed.'
            _logger.warning("Sync pull failed: %s", e)
        out = self._summary(rec)
        out['error'] = err
        return out
