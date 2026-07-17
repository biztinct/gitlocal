# -*- coding: utf-8 -*-
"""Demo integration mappings (extends pb.demo.generator).

Seeds ~25 production-looking integration connectors (HRIS, ERP, T&A, accounting,
protocols) with field mappings, sync status and counters, on top of the real
engine in pb_hr_payroll_formula. Brand lives in `name`; `connector_type` maps to
the nearest existing implementation so nothing requires schema changes.
"""
import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# (brand, connector_type, auth_type, category, country_code)
_SYSTEMS = [
    ('SAP SuccessFactors', 'sap', 'oauth2', 'HRIS', 'ALL'),
    ('SAP ERP (HCM)', 'sap', 'oauth2', 'ERP', 'ALL'),
    ('SAP Business One', 'sap', 'basic', 'ERP', 'VN'),
    ('Workday', 'workday', 'oauth2', 'HRIS', 'ALL'),
    ('Oracle HCM Cloud', 'oracle', 'oauth2', 'HRIS', 'ALL'),
    ('Oracle ERP Cloud', 'oracle', 'oauth2', 'ERP', 'ALL'),
    ('Oracle NetSuite', 'oracle', 'bearer', 'ERP', 'ALL'),
    ('Microsoft Dynamics 365', 'demo', 'oauth2', 'ERP', 'ALL'),
    ('DarwinHR (Darwinbox)', 'darwin', 'api_key', 'HRIS', 'ALL'),
    ('Zoho People', 'zoho', 'oauth2', 'HRIS', 'VN'),
    ('Zoho Payroll', 'zoho', 'oauth2', 'Payroll', 'VN'),
    ('BambooHR', 'demo', 'api_key', 'HRIS', 'ALL'),
    ('ADP Workforce Now', 'demo', 'oauth2', 'Payroll', 'ALL'),
    ('UKG Pro', 'demo', 'oauth2', 'HRIS', 'ALL'),
    ('Deputy', 'demo', 'api_key', 'Time & Attendance', 'ALL'),
    ('Tanda', 'demo', 'api_key', 'Time & Attendance', 'ALL'),
    ('EasyHR', 'demo', 'api_key', 'HRIS', 'VN'),
    ('MISA AMIS', 'demo', 'api_key', 'Accounting', 'VN'),
    ('Xero', 'demo', 'oauth2', 'Accounting', 'ALL'),
    ('QuickBooks Online', 'demo', 'oauth2', 'Accounting', 'ALL'),
    ('Excel Workbook', 'excel', 'api_key', 'File', 'ALL'),
    ('CSV Import', 'excel', 'api_key', 'File', 'ALL'),
    ('REST API', 'demo', 'bearer', 'Protocol', 'ALL'),
    ('SOAP API', 'demo', 'basic', 'Protocol', 'ALL'),
    ('SFTP Drop', 'demo', 'basic', 'Protocol', 'ALL'),
    ('Direct Database', 'demo', 'basic', 'Protocol', 'VN'),
]

_SOURCE_FIELDS = [
    ('employee_external_id', 'Employee ID', 'direct'),
    ('full_name', 'Full Name', 'direct'),
    ('base_salary', 'Basic Salary', 'direct'),
    ('allowances_total', 'Allowances', 'direct'),
    ('overtime_hours', 'Overtime Hours', 'multiply'),
    ('dependents_count', 'Dependents', 'direct'),
    ('bank_account_no', 'Bank Account', 'direct'),
    ('attendance_days', 'Attendance Days', 'direct'),
]


class HrIntegrationConnector(models.Model):
    _inherit = 'hr.integration.connector'

    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class HrIntegrationFieldMapping(models.Model):
    _inherit = 'hr.integration.field.mapping'

    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    def generate_integrations(self):
        self = self.with_context(**self._GEN_CTX)
        self._clean_integrations()
        Connector = self.env['hr.integration.connector'].sudo()
        Mapping = self.env['hr.integration.field.mapping'].sudo()
        company = self.get_group_company() or self.env.company
        # Deterministic, varied statuses (no Date.now in scripts; derive from index).
        base = datetime(2026, 6, 26, 8, 0, 0)
        n = 0
        for idx, (brand, ctype, auth, category, country) in enumerate(_SYSTEMS):
            # Most connected; a couple error/disconnected for realism.
            if idx % 11 == 5:
                status, sync_status = 'error', 'failed'
            elif idx % 13 == 7:
                status, sync_status = 'disconnected', False
            else:
                status, sync_status = 'connected', 'success'
            host = brand.lower().replace(' ', '').replace('(', '').replace(')', '')
            conn = Connector.create({
                'name': brand,
                'connector_type': ctype,
                'company_id': company.id,
                'auth_type': auth,
                'api_endpoint': 'https://api.%s.com/v2/hr' % host[:18],
                'api_version': 'v2',
                'country_code': country,
                'connection_status': status,
                'last_sync_status': sync_status,
                'last_sync': False if status == 'disconnected' else base - timedelta(hours=idx * 3),
                'last_sync_message': {
                    'connected': 'Sync completed successfully.',
                    'error': 'Auth token expired — re-authentication required.',
                    'disconnected': 'Connector configured, not yet connected.',
                }[status],
                'sync_interval': [0, 60, 360, 720, 1440][idx % 5],
                'total_synced_employees': 0 if status != 'connected' else 350 + idx * 47,
                'total_synced_records': 0 if status != 'connected' else 1200 + idx * 213,
                'is_demo': True,
            })
            # 4–8 field mappings each
            for s_idx, (src, label, transform) in enumerate(_SOURCE_FIELDS[:4 + idx % 5]):
                mvals = {'connector_id': conn.id, 'source_field': src, 'is_demo': True}
                if 'source_field_label' in Mapping._fields:
                    mvals['source_field_label'] = label
                if 'transformation_type' in Mapping._fields:
                    mvals['transformation_type'] = transform
                Mapping.create(mvals)
            n += 1
        _logger.info('pb_demo: %s demo integration connectors created.', n)
        return n

    def _clean_integrations(self):
        self.env['hr.integration.field.mapping'].sudo().search([('is_demo', '=', True)]).unlink()
        self.env['hr.integration.connector'].sudo().search([('is_demo', '=', True)]).unlink()
