# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

SOURCES = [
    {'id': 'file', 'label': 'File upload'},
    {'id': 'zoho', 'label': 'Zoho People'},
    {'id': 'api', 'label': 'External API'},
]


class PbEmployeeWizard(models.AbstractModel):
    """Bespoke guided wrapper around employee.import.wizard
    (configure -> preview -> import -> results)."""
    _name = 'pb.import.employee.wizard'
    _description = 'Payobook guided employee import'

    _MODEL = 'employee.import.wizard'

    @api.model
    def get_defaults(self):
        countries = []
        try:
            field = self.env[self._MODEL]._fields.get('country_code')
            for code, label in (field.selection or []):
                countries.append({'id': code, 'label': label})
        except Exception:
            pass
        return {'sources': SOURCES, 'countries': countries}

    def _vals(self, vals):
        cvals = {
            'import_source': vals.get('import_source') or 'file',
            'update_existing': bool(vals.get('update_existing', True)),
            'create_contracts': bool(vals.get('create_contracts', True)),
        }
        if vals.get('country_code'):
            cvals['country_code'] = vals['country_code']
        if vals.get('file_b64'):
            cvals['import_file'] = vals['file_b64']
            cvals['import_filename'] = vals.get('file_name') or 'employees.xlsx'
        if vals.get('data_source_url'):
            cvals['data_source_url'] = vals['data_source_url']
        if vals.get('zoho_api_key'):
            cvals['zoho_api_key'] = vals['zoho_api_key']
        if vals.get('zoho_org_id'):
            cvals['zoho_org_id'] = vals['zoho_org_id']
        return cvals

    def _summary(self, rec):
        return {
            'wizard_id': rec.id,
            'state': rec.state,
            'preview': {
                'employees': rec.preview_employee_count,
                'new': rec.preview_new_employees,
                'existing': rec.preview_existing_employees,
                'errors': rec.preview_validation_errors,
            },
            'results': {
                'imported': rec.imported_count,
                'updated': rec.updated_count,
                'failed': rec.failed_count,
                'contracts': rec.contracts_created,
            },
        }

    @api.model
    def test_zoho(self, vals):
        rec = self.env[self._MODEL].create(self._vals(vals))
        ok, msg = True, 'Connection OK.'
        try:
            res = rec.action_test_zoho_connection()
            try:
                msg = res['params']['message']
            except Exception:
                pass
        except Exception as e:
            ok = False
            msg = str(getattr(e, 'name', None) or e) or 'Connection failed.'
        return {'ok': ok, 'message': msg}

    @api.model
    def create_and_preview(self, vals):
        rec = self.env[self._MODEL].create(self._vals(vals))
        err = None
        try:
            rec.action_load_preview()
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Preview failed.'
            _logger.warning("Employee preview failed: %s", e)
        out = self._summary(rec)
        out['error'] = err
        return out

    @api.model
    def do_import(self, wizard_id):
        rec = self.env[self._MODEL].browse(int(wizard_id))
        err = None
        try:
            rec.action_start_import()
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Import failed.'
            _logger.warning("Employee import failed: %s", e)
        out = self._summary(rec)
        out['error'] = err
        return out

    @api.model
    def get_link(self, wizard_id, method):
        if method not in ('action_view_imported_employees', 'action_download_template',
                          'action_download_error_report'):
            return False
        rec = self.env[self._MODEL].browse(int(wizard_id))
        try:
            return getattr(rec, method)() or False
        except Exception as e:
            _logger.debug("employee get_link %s failed: %s", method, e)
            return False
