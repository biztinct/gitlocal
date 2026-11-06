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

# What each kind of system actually feeds a payroll, by the CATEGORY column of
# `_SYSTEMS` above. A T&A system does not send you salaries and an accounting
# package does not send you dependants; a demo world that gave every connector
# the same five feeds would teach the wrong thing about the product.
#
# These are the data types the seeder writes STORE ROWS for. The endpoints are
# then DERIVED from those rows by `action_sync_endpoint_catalog`, exactly as
# they would be on a real connector that has pulled once — the demo does not
# create endpoints behind the model's back.
_CATEGORY_FEEDS = {
    'HRIS': ['employee', 'dependent', 'leave'],
    'Payroll': ['employee', 'salary'],
    'ERP': ['employee', 'salary'],
    'Time & Attendance': ['employee', 'attendance'],
    'Accounting': ['salary'],
    'File': ['employee', 'salary'],
    'Protocol': ['employee'],
}

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


class HrIntegrationEndpoint(models.Model):
    """The same `is_demo` marker the connector and the mapping carry.

    Endpoints cascade with their connector, so the clean path does not NEED it
    — but `_clean_integrations` deletes by this flag rather than by inference,
    and a satellite that cannot be found by the same question as its owner is a
    row somebody will one day fail to clean.
    """
    _inherit = 'hr.integration.endpoint'

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
        n = feeds = 0
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
            feeds += self._seed_endpoints(conn, category, idx, base)
            n += 1
        _logger.info('pb_demo: %s demo integration connectors created, '
                     '%s feeds catalogued.', n, feeds)
        return n

    def _seed_endpoints(self, conn, category, idx, base):
        """Give a demo connector the feeds its category implies.

        The rows come first and the ENDPOINTS ARE DERIVED FROM THEM: a demo that
        wrote endpoint records directly would be demonstrating a screen rather
        than the product, and the counts on each chip would be decoration. This
        way `staged` and `pulled` on a demo feed are the same arithmetic as on a
        real one, over rows that really exist.

        Never destructive and idempotent by construction: it only runs from
        `generate_integrations`, immediately after the connector was created, so
        there is nothing of anybody else's here to preserve.
        """
        if 'hr.integration.endpoint' not in self.env:
            return 0
        Store = self.env['hr.api.data.store'].sudo()
        types = _CATEGORY_FEEDS.get(category, ['employee'])
        stamp = conn.last_sync or (base - timedelta(hours=idx * 3))

        rows = []
        for t_idx, data_type in enumerate(types):
            # Deterministic and small: this is evidence that the feed exists,
            # not a data set. 3-7 rows per feed, no randomness anywhere.
            for r in range(3 + (idx + t_idx) % 5):
                rows.append({
                    'connector_id': conn.id,
                    'data_type': data_type,
                    'employee_external_id': '%s-%s-%04d' % (
                        conn.connector_type.upper(), data_type[:3].upper(), r + 1),
                    'raw_payload': {'external_id': r + 1, 'source': conn.name,
                                    'kind': data_type},
                    'extracted_data': {'external_id': r + 1, 'kind': data_type},
                    'state': 'extracted',
                    'pull_date': stamp,
                    'pull_triggered_by': 'cron',
                    'company_id': conn.company_id.id,
                })
        if rows:
            Store.create(rows)

        conn.sudo().action_sync_endpoint_catalog()
        eps = conn.sudo().endpoint_ids
        if eps:
            eps.write({
                'is_demo': True,
                # The feed's clock mirrors the connector's, so "stale" on the
                # board means what the connector's own sync interval says and
                # not "the demo forgot to stamp this".
                'last_sync': False if not conn.last_sync else stamp,
                'last_sync_status': conn.last_sync_status or False,
            })
        return len(eps)

    def _clean_integrations(self):
        if 'hr.integration.endpoint' in self.env:
            self.env['hr.integration.endpoint'].sudo().with_context(
                active_test=False).search([('is_demo', '=', True)]).unlink()
        self.env['hr.integration.field.mapping'].sudo().search([('is_demo', '=', True)]).unlink()
        self.env['hr.integration.connector'].sudo().search([('is_demo', '=', True)]).unlink()
