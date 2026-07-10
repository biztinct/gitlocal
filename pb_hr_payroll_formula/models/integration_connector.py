# -*- coding: utf-8 -*-

import time
import logging
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HrIntegrationConnector(models.Model):
    """
    HR Integration Connector - Manages connections to external HR systems
    like Zoho People, SAP SuccessFactors, Workday, Oracle HCM, or Excel files.
    """
    _name = 'hr.integration.connector'
    _description = 'HR System Integration Connector'
    _inherit = ['mail.thread']
    _order = 'sequence, name'
    _rec_name = 'name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Connector Name',
        required=True,
        tracking=True
    )

    connector_type = fields.Selection([
        ('zoho', 'Zoho People'),
        ('excel', 'Excel File Import'),
        ('sap', 'SAP SuccessFactors'),
        ('workday', 'Workday'),
        ('oracle', 'Oracle HCM'),
        ('demo', 'Demo / Stub (Testing)')
    ], string='Connector Type', required=True, tracking=True)

    description = fields.Text(
        string='Description'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # ==========================================
    # CONNECTION SETTINGS
    # ==========================================
    api_endpoint = fields.Char(
        string='API Endpoint',
        help="Base URL for API calls"
    )

    api_version = fields.Char(
        string='API Version',
        default='v1'
    )

    auth_type = fields.Selection([
        ('oauth2', 'OAuth 2.0'),
        ('api_key', 'API Key'),
        ('basic', 'Basic Authentication'),
        ('bearer', 'Bearer Token')
    ], string='Authentication Type', default='oauth2')

    # ==========================================
    # CREDENTIALS (Sensitive - System Only)
    # ==========================================
    client_id = fields.Char(
        string='Client ID',
        groups="base.group_system"
    )

    client_secret = fields.Char(
        string='Client Secret',
        groups="base.group_system"
    )

    api_key = fields.Char(
        string='API Key',
        groups="base.group_system"
    )

    username = fields.Char(
        string='Username',
        groups="base.group_system"
    )

    password = fields.Char(
        string='Password',
        groups="base.group_system"
    )

    access_token = fields.Text(
        string='Access Token',
        groups="base.group_system"
    )

    refresh_token = fields.Text(
        string='Refresh Token',
        groups="base.group_system"
    )

    token_expiry = fields.Datetime(
        string='Token Expiry',
        groups="base.group_system"
    )

    # ==========================================
    # OAUTH SETTINGS
    # ==========================================
    oauth_authorize_url = fields.Char(
        string='Authorization URL'
    )

    oauth_token_url = fields.Char(
        string='Token URL'
    )

    oauth_scope = fields.Char(
        string='OAuth Scope'
    )

    # ==========================================
    # FIELD MAPPINGS
    # ==========================================
    field_mapping_ids = fields.One2many(
        'hr.integration.field.mapping',
        'connector_id',
        string='Field Mappings'
    )

    mapping_count = fields.Integer(
        string='Mappings',
        compute='_compute_mapping_count'
    )

    # ==========================================
    # API DATA STORE & TRANSFORMATION RULES
    # ==========================================
    data_store_ids = fields.One2many(
        'hr.api.data.store',
        'connector_id',
        string='Stored Data',
    )
    data_store_count = fields.Integer(
        string='Stored Records',
        compute='_compute_data_store_count',
    )
    transformation_rule_ids = fields.One2many(
        'hr.api.transformation.rule',
        'connector_id',
        string='Transformation Rules',
    )

    # ==========================================
    # CONNECTION STATUS
    # ==========================================
    connection_status = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connecting', 'Connecting...'),
        ('connected', 'Connected'),
        ('error', 'Error')
    ], string='Status', default='disconnected', tracking=True)

    last_sync = fields.Datetime(
        string='Last Sync'
    )

    last_sync_status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed')
    ], string='Last Sync Status')

    last_sync_message = fields.Text(
        string='Last Sync Message'
    )

    last_error = fields.Text(
        string='Last Error'
    )

    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=60,
        help="Automatic sync interval in minutes (0 = manual only)"
    )

    # ==========================================
    # SYNC STATISTICS
    # ==========================================
    total_synced_employees = fields.Integer(
        string='Total Synced Employees',
        readonly=True
    )

    total_synced_records = fields.Integer(
        string='Total Synced Records',
        readonly=True
    )

    # ==========================================
    # COUNTRY FILTER
    # ==========================================
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),
        ('KH', 'Cambodia'),
        ('PH', 'Philippines'),
        ('ALL', 'All Countries')
    ], string='Country Filter', default='ALL')

    # ==========================================
    # FILE IMPORT SETTINGS (for Excel connector)
    # ==========================================
    last_import_file = fields.Binary(
        string='Last Imported File'
    )

    last_import_filename = fields.Char(
        string='Last Filename'
    )

    file_header_row = fields.Integer(
        string='Header Row',
        default=1,
        help="Row number containing column headers"
    )

    file_data_start_row = fields.Integer(
        string='Data Start Row',
        default=2,
        help="First row containing data"
    )

    file_sheet_name = fields.Char(
        string='Sheet Name',
        help="Name of sheet to import (leave empty for first sheet)"
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('field_mapping_ids')
    def _compute_mapping_count(self):
        for record in self:
            record.mapping_count = len(record.field_mapping_ids)

    def _compute_data_store_count(self):
        for record in self:
            record.data_store_count = self.env['hr.api.data.store'].search_count([
                ('connector_id', '=', record.id),
                ('state', '!=', 'archived'),
            ])

    # ==========================================
    # CONNECTION ACTIONS
    # ==========================================
    def action_apply_mapping_template(self, config_id=None):
        """F114 — seed field mappings from this vendor's ready-made template.
        Matched by canonical code → 'active'; unmatched or verify/derive rows →
        'suggested' (never load-bearing). Idempotent: an existing mapping for a
        source path is never overwritten."""
        self.ensure_one()
        Tmpl = self.env['hr.integration.mapping.template']
        Map = self.env['hr.integration.field.mapping']
        rows = Tmpl.search([('connector_type', '=', self.connector_type)])
        # sudo the config read — configs are company-scoped/record-rule-gated
        # (same pattern the studio uses); the mapping setup is a trusted action.
        config = False
        if config_id:
            config = self.env['hr.formula.config'].sudo().browse(int(config_id))
            if not config.exists():
                config = False
        if not config:
            config = self.env['hr.formula.config'].sudo().search([('connector_id', '=', self.id)], limit=1)
        existing_src = set((self.field_mapping_ids.mapped('source_field')) or [])
        applied = suggested = 0
        for t in rows:
            if t.source_path in existing_src:
                continue
            rule = self.env['hr.formula.rule']
            if config:
                rule = config.rule_ids.filtered(
                    lambda r: r.column_type == 'input'
                    and (r.code or '').upper() == (t.target_code or '').upper())[:1]
            state = 'active' if (rule and not t.verify) else 'suggested'
            Map.create({
                'connector_id': self.id,
                'connector_type': self.connector_type,
                'source_field': t.source_path,
                'source_field_label': t.target_label or t.target_code,
                'target_rule_id': rule.id if rule else False,
                'transformation_type': t.transformation_type or 'direct',
                'transformation_value': t.transformation_value or 0.0,
                'transformation_code': t.transformation_code or False,
                'is_required': t.is_required,
                'default_value': t.default_value or 0.0,
                'notes': t.note or False,
                'active_state': state,
            })
            existing_src.add(t.source_path)
            if state == 'active':
                applied += 1
            else:
                suggested += 1
        return {'applied': applied, 'suggested': suggested, 'total': applied + suggested}

    @api.model
    def action_open_onboarding(self):
        """Launch the 4-step connect-your-HR-system wizard."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connect an HR / Timesheet System'),
            'res_model': 'hr.integration.onboarding.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_test_connection(self):
        """Test the connection to the external system"""
        self.ensure_one()
        self.connection_status = 'connecting'

        try:
            connector = self._get_connector_instance()
            success, message = connector.test_connection()

            if success:
                self.write({
                    'connection_status': 'connected',
                    'last_error': False,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': message or _('Connected to %s') % self.name,
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'connection_status': 'error',
                    'last_error': message,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': message,
                        'type': 'danger',
                        'sticky': True,
                    }
                }
        except Exception as e:
            self.write({
                'connection_status': 'error',
                'last_error': str(e),
            })
            raise UserError(_('Connection test failed: %s') % str(e))

    def action_disconnect(self):
        """Disconnect and clear tokens"""
        self.ensure_one()
        self.write({
            'connection_status': 'disconnected',
            'access_token': False,
            'token_expiry': False,
        })

    def action_refresh_token(self):
        """Refresh OAuth access token"""
        self.ensure_one()
        if self.auth_type != 'oauth2':
            raise UserError(_('Token refresh is only available for OAuth 2.0'))

        try:
            connector = self._get_connector_instance()
            connector.refresh_access_token()
            self.connection_status = 'connected'
        except Exception as e:
            self.connection_status = 'error'
            self.last_error = str(e)
            raise UserError(_('Token refresh failed: %s') % str(e))

    # ==========================================
    # SYNC ACTIONS
    # ==========================================
    def action_sync_now(self):
        """Manually trigger data sync"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync Data'),
            'res_model': 'hr.integration.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_connector_id': self.id,
            }
        }

    def action_fetch_available_fields(self):
        """Fetch available fields from the source system"""
        self.ensure_one()
        try:
            connector = self._get_connector_instance()
            fields_list = connector.get_available_fields()

            # Create/update field mappings
            existing_sources = self.field_mapping_ids.mapped('source_field')

            for field_info in fields_list:
                source_field = field_info.get('name')
                if source_field and source_field not in existing_sources:
                    self.env['hr.integration.field.mapping'].create({
                        'connector_id': self.id,
                        'source_field': source_field,
                        'source_field_label': field_info.get('label', source_field),
                        'source_data_type': field_info.get('type', 'string'),
                    })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fields Fetched'),
                    'message': _('%d fields discovered') % len(fields_list),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Failed to fetch fields: %s') % str(e))

    # ==========================================
    # VIEW ACTIONS
    # ==========================================
    def action_view_mappings(self):
        """Open field mappings view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Mappings'),
            'res_model': 'hr.integration.field.mapping',
            'view_mode': 'list,form',
            'domain': [('connector_id', '=', self.id)],
            'context': {'default_connector_id': self.id},
        }

    def action_view_sync_history(self):
        """View sync history — now shows data store records."""
        self.ensure_one()
        return self.action_view_data_store()

    def action_view_data_store(self):
        """View stored API data records for this connector."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('API Data Store — %s') % self.name,
            'res_model': 'hr.api.data.store',
            'view_mode': 'list,form',
            'domain': [('connector_id', '=', self.id)],
            'context': {
                'default_connector_id': self.id,
                'search_default_active_records': 1,
            },
        }

    # ==========================================
    # PULL DATA — Core API Integration
    # ==========================================
    def action_pull_data(self, data_types=None, period_from=None, period_to=None,
                         triggered_by='manual'):
        """
        Pull data from external HRIS and store in hr.api.data.store.

        This is the primary entry point for the Pull → Store → Transform pipeline.

        Args:
            data_types: list of data type strings to pull (default: ['employee', 'salary'])
            period_from: start of period (date)
            period_to: end of period (date)
            triggered_by: 'manual' or 'cron'

        Returns:
            Action dict with notification of results.
        """
        self.ensure_one()
        DataStore = self.env['hr.api.data.store']

        if not data_types:
            data_types = ['employee', 'salary']
            # Demo connector supports all data types
            if self.connector_type == 'demo':
                data_types = ['employee', 'salary', 'dependent', 'attendance', 'leave']

        # Default period: current month
        if not period_from:
            import calendar
            today = date.today()
            period_from = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            period_to = today.replace(day=last_day)

        results = {
            'pulled': 0,
            'changes': 0,
            'errors': [],
        }

        try:
            connector = self._get_connector_instance()

            # Authenticate
            if not connector.authenticate():
                raise UserError(_('Authentication failed for connector %s') % self.name)

            # Pull employee data
            if 'employee' in data_types:
                start_time = time.time()
                employees = connector.fetch_employees()
                pull_ms = int((time.time() - start_time) * 1000)

                if employees:
                    for emp_data in employees:
                        self._store_api_record(
                            DataStore, emp_data,
                            data_type='employee',
                            period_from=period_from,
                            period_to=period_to,
                            pull_ms=pull_ms,
                            triggered_by=triggered_by,
                            results=results,
                        )

            # Pull salary/payroll data
            if 'salary' in data_types:
                start_time = time.time()
                try:
                    # Get employee IDs for payroll pull
                    emp_ids = []
                    emp_records = DataStore.search([
                        ('connector_id', '=', self.id),
                        ('data_type', '=', 'employee'),
                        ('state', 'in', ['extracted']),
                    ])
                    for emp_rec in emp_records:
                        ext_id = emp_rec.employee_external_id
                        if ext_id and ext_id not in emp_ids:
                            emp_ids.append(ext_id)

                    if emp_ids:
                        payroll_data = connector.fetch_payroll_data(
                            emp_ids,
                            str(period_from),
                            str(period_to),
                        )
                        pull_ms = int((time.time() - start_time) * 1000)

                        if payroll_data:
                            for emp_id, salary_data in payroll_data.items():
                                self._store_api_record(
                                    DataStore, salary_data,
                                    data_type='salary',
                                    employee_external_id=str(emp_id),
                                    period_from=period_from,
                                    period_to=period_to,
                                    pull_ms=pull_ms,
                                    triggered_by=triggered_by,
                                    results=results,
                                )
                except Exception as e:
                    results['errors'].append(f"Salary pull error: {str(e)}")
                    _logger.warning("Salary pull failed for connector %s: %s", self.name, str(e))

            # Pull dependent data (one record per dependent)
            if 'dependent' in data_types and hasattr(connector, 'fetch_dependents'):
                try:
                    start_time = time.time()
                    emp_ids = list(set(
                        r.employee_external_id for r in DataStore.search([
                            ('connector_id', '=', self.id),
                            ('data_type', '=', 'employee'),
                            ('state', 'in', ['extracted']),
                        ]) if r.employee_external_id
                    ))
                    if emp_ids:
                        dep_data = connector.fetch_dependents(emp_ids)
                        pull_ms = int((time.time() - start_time) * 1000)
                        for emp_id, deps in dep_data.items():
                            for dep_record in deps:
                                self._store_api_record(
                                    DataStore, dep_record,
                                    data_type='dependent',
                                    employee_external_id=str(emp_id),
                                    period_from=period_from,
                                    period_to=period_to,
                                    pull_ms=pull_ms,
                                    triggered_by=triggered_by,
                                    results=results,
                                )
                except Exception as e:
                    results['errors'].append(f"Dependent pull error: {str(e)}")
                    _logger.warning("Dependent pull failed for connector %s: %s", self.name, str(e))

            # Pull attendance data
            if 'attendance' in data_types and hasattr(connector, 'fetch_attendance'):
                try:
                    start_time = time.time()
                    emp_ids = list(set(
                        r.employee_external_id for r in DataStore.search([
                            ('connector_id', '=', self.id),
                            ('data_type', '=', 'employee'),
                            ('state', 'in', ['extracted']),
                        ]) if r.employee_external_id
                    ))
                    if emp_ids:
                        att_data = connector.fetch_attendance(emp_ids, str(period_from), str(period_to))
                        pull_ms = int((time.time() - start_time) * 1000)
                        for emp_id, att_record in att_data.items():
                            self._store_api_record(
                                DataStore, att_record,
                                data_type='attendance',
                                employee_external_id=str(emp_id),
                                period_from=period_from,
                                period_to=period_to,
                                pull_ms=pull_ms,
                                triggered_by=triggered_by,
                                results=results,
                            )
                except Exception as e:
                    results['errors'].append(f"Attendance pull error: {str(e)}")
                    _logger.warning("Attendance pull failed for connector %s: %s", self.name, str(e))

            # Pull leave data (one record per leave entry)
            if 'leave' in data_types and hasattr(connector, 'fetch_leaves'):
                try:
                    start_time = time.time()
                    emp_ids = list(set(
                        r.employee_external_id for r in DataStore.search([
                            ('connector_id', '=', self.id),
                            ('data_type', '=', 'employee'),
                            ('state', 'in', ['extracted']),
                        ]) if r.employee_external_id
                    ))
                    if emp_ids:
                        leave_data = connector.fetch_leaves(emp_ids, str(period_from), str(period_to))
                        pull_ms = int((time.time() - start_time) * 1000)
                        for emp_id, leaves in leave_data.items():
                            for leave_record in leaves:
                                self._store_api_record(
                                    DataStore, leave_record,
                                    data_type='leave',
                                    employee_external_id=str(emp_id),
                                    period_from=period_from,
                                    period_to=period_to,
                                    pull_ms=pull_ms,
                                    triggered_by=triggered_by,
                                    results=results,
                                )
                except Exception as e:
                    results['errors'].append(f"Leave pull error: {str(e)}")
                    _logger.warning("Leave pull failed for connector %s: %s", self.name, str(e))

            # Update connector sync status
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_status': 'success' if not results['errors'] else 'partial',
                'last_sync_message': _(
                    'Pulled %d records (%d with changes). %d errors.'
                ) % (results['pulled'], results['changes'], len(results['errors'])),
                'total_synced_records': results['pulled'],
            })

            # Run transformation rules on newly pulled records
            new_records = DataStore.search([
                ('connector_id', '=', self.id),
                ('state', '=', 'extracted'),
                ('pull_date', '>=', fields.Datetime.now()),
            ])
            if new_records and self.transformation_rule_ids:
                active_rules = self.transformation_rule_ids.filtered('active')
                if active_rules:
                    active_rules._execute_for_records(new_records)

        except Exception as e:
            self.write({
                'last_sync_status': 'failed',
                'last_error': str(e),
                'last_sync_message': _('Pull failed: %s') % str(e),
            })
            _logger.exception("Pull failed for connector %s: %s", self.name, str(e))
            raise UserError(_('Data pull failed: %s') % str(e))

        msg = _('Pulled %d records from %s. %d changes detected.') % (
            results['pulled'], self.name, results['changes']
        )
        if results['errors']:
            msg += _(' %d errors encountered.') % len(results['errors'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Pull Complete'),
                'message': msg,
                'type': 'success' if not results['errors'] else 'warning',
            }
        }

    def _store_api_record(self, DataStore, raw_data, data_type,
                          employee_external_id=None, period_from=None,
                          period_to=None, pull_ms=0, triggered_by='manual',
                          results=None):
        """
        Create a data store record from raw API data.

        Handles:
        1. Storing the raw payload
        2. Extracting flattened data
        3. Computing version + diff against previous
        4. Attempting employee matching
        """
        if results is None:
            results = {'pulled': 0, 'changes': 0, 'errors': []}

        # Try to extract employee external ID from the data if not provided
        if not employee_external_id and isinstance(raw_data, dict):
            for key in ('EmployeeID', 'employee_id', 'emp_id', 'empId',
                        'RecordId', 'record_id', 'ID', 'id'):
                val = raw_data.get(key)
                if val:
                    employee_external_id = str(val)
                    break

        try:
            record = DataStore.create({
                'connector_id': self.id,
                'data_type': data_type,
                'employee_external_id': employee_external_id,
                'period_from': period_from,
                'period_to': period_to,
                'raw_payload': raw_data,
                'pull_date': fields.Datetime.now(),
                'pull_duration_ms': pull_ms,
                'pull_triggered_by': triggered_by,
                'state': 'raw',
                'company_id': self.company_id.id,
            })

            # Extract data
            record.action_extract()

            # Compute version and diff
            record._compute_version_and_diff()

            # Try to match employee
            record._find_matching_employee()
            if record._find_matching_employee():
                record.employee_id = record._find_matching_employee().id

            results['pulled'] += 1
            if record.has_changes:
                results['changes'] += 1

        except Exception as e:
            results['errors'].append(str(e))
            _logger.warning("Failed to store API record: %s", str(e))

    def action_recompute_transformations(self):
        """Recompute all transformation rules for extracted data store records."""
        self.ensure_one()
        records = self.env['hr.api.data.store'].search([
            ('connector_id', '=', self.id),
            ('state', '=', 'extracted'),
        ])
        if not records:
            raise UserError(_('No extracted records found to transform.'))

        active_rules = self.transformation_rule_ids.filtered('active')
        if not active_rules:
            raise UserError(_('No active transformation rules configured.'))

        active_rules._execute_for_records(records)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transformations Complete'),
                'message': _('Recomputed %d rules for %d records.') % (
                    len(active_rules), len(records)
                ),
                'type': 'success',
            }
        }

    def action_launch_payroll_import(self):
        """Launch payroll import using this connector"""
        self.ensure_one()

        # Determine best source type
        if self.connector_type == 'excel':
            source_type = 'excel'
        elif self.data_store_count > 0:
            # If data store has records, default to api_data_store
            source_type = 'api_data_store'
        else:
            source_type = 'connector'

        return {
            'type': 'ir.actions.act_window',
            'name': _('New Payroll Import'),
            'res_model': 'hr.payroll.import.batch',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_connector_id': self.id,
                'default_source_type': source_type,
            },
        }

    # ==========================================
    # CONNECTOR FACTORY
    # ==========================================
    def _get_connector_instance(self):
        """Get the appropriate connector class instance"""
        self.ensure_one()

        from ..integrations import (
            ZohoConnector,
            ExcelConnector,
            SAPConnector,
            WorkdayConnector,
            OracleConnector,
            DemoConnector,
        )

        connector_map = {
            'zoho': ZohoConnector,
            'excel': ExcelConnector,
            'sap': SAPConnector,
            'workday': WorkdayConnector,
            'oracle': OracleConnector,
            'demo': DemoConnector,
        }

        connector_class = connector_map.get(self.connector_type)
        if not connector_class:
            raise UserError(_('Unknown connector type: %s') % self.connector_type)

        return connector_class(self)

    # ==========================================
    # DATA FETCH
    # ==========================================
    def fetch_employees(self, filters=None):
        """Fetch employee data from external system"""
        self.ensure_one()
        connector = self._get_connector_instance()
        return connector.fetch_employees(filters)

    def fetch_payroll_data(self, employee_ids, date_from, date_to):
        """Fetch payroll data for specific employees and period"""
        self.ensure_one()
        connector = self._get_connector_instance()
        return connector.fetch_payroll_data(employee_ids, date_from, date_to)

    def transform_data(self, raw_data):
        """Transform raw data using field mappings"""
        self.ensure_one()
        connector = self._get_connector_instance()
        return connector.transform_data(raw_data, self.field_mapping_ids)

    # ==========================================
    # EXCEL IMPORT
    # ==========================================
    def action_import_excel(self):
        """Open Excel import wizard"""
        self.ensure_one()
        if self.connector_type != 'excel':
            raise UserError(_('Excel import is only available for Excel connector'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Excel File'),
            'res_model': 'hr.integration.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_connector_id': self.id,
                'default_import_type': 'file',
            }
        }
