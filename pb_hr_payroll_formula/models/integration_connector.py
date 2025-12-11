# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrIntegrationConnector(models.Model):
    """
    HR Integration Connector - Manages connections to external HR systems
    like Zoho People, SAP SuccessFactors, Workday, Oracle HCM, or Excel files.
    """
    _name = 'hr.integration.connector'
    _description = 'HR System Integration Connector'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
        ('oracle', 'Oracle HCM')
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

    # ==========================================
    # CONNECTION ACTIONS
    # ==========================================
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
            'view_mode': 'tree,form',
            'domain': [('connector_id', '=', self.id)],
            'context': {'default_connector_id': self.id},
        }

    def action_view_sync_history(self):
        """View sync history"""
        self.ensure_one()
        # TODO: Implement sync history model
        pass

    def action_launch_payroll_import(self):
        """Launch payroll import using this connector"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Payroll Import'),
            'res_model': 'hr.payroll.import.batch',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_connector_id': self.id,
                'default_source_type': 'connector' if self.connector_type != 'excel' else 'excel',
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
        )

        connector_map = {
            'zoho': ZohoConnector,
            'excel': ExcelConnector,
            'sap': SAPConnector,
            'workday': WorkdayConnector,
            'oracle': OracleConnector,
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
