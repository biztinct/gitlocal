# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BFSIKpiIntegration(models.Model):
    _name = 'bfsi.kpi.integration'
    _description = 'KPI External System Integration'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(
        string='Integration Name',
        required=True,
        tracking=True,
        help='Name of this integration configuration'
    )

    sequence = fields.Integer(string='Sequence', default=10)

    active = fields.Boolean(string='Active', default=True, tracking=True)

    # Source System
    source_system = fields.Selection([
        ('crm', 'CRM (Customer Relationship Management)'),
        ('hrms', 'HRMS (Human Resource Management)'),
        ('core_banking', 'Core Banking System'),
        ('call_center', 'Call Center / Dialer'),
        ('lms', 'Learning Management System'),
        ('custom_api', 'Custom API'),
    ], string='Source System', required=True, tracking=True)

    # Connection Settings
    api_base_url = fields.Char(
        string='API Base URL',
        help='Base URL of the external system API (e.g., https://crm.example.com/api/v1)'
    )

    auth_type = fields.Selection([
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth 2.0'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
    ], string='Authentication Type', default='api_key')

    api_key = fields.Char(
        string='API Key / Token',
        help='API key or access token for authentication',
        groups='hr_development_ai.group_hr_development_admin'
    )

    api_secret = fields.Char(
        string='API Secret',
        help='API secret or password for authentication',
        groups='hr_development_ai.group_hr_development_admin'
    )

    username = fields.Char(
        string='Username',
        help='Username for Basic Auth'
    )

    oauth_client_id = fields.Char(
        string='OAuth Client ID',
        groups='hr_development_ai.group_hr_development_admin'
    )

    oauth_client_secret = fields.Char(
        string='OAuth Client Secret',
        groups='hr_development_ai.group_hr_development_admin'
    )

    oauth_token_url = fields.Char(
        string='OAuth Token URL',
        help='URL to obtain OAuth access tokens'
    )

    # Data Mapping
    kpi_mapping = fields.Text(
        string='KPI Field Mapping',
        help='JSON mapping of external system fields to internal KPI fields.\n'
             'Example: {"external_field": "internal_field", "sales_count": "conversions"}'
    )

    employee_id_field = fields.Char(
        string='Employee ID Field',
        default='employee_id',
        help='Field name in external system that maps to employee identifier'
    )

    date_field = fields.Char(
        string='Date Field',
        default='date',
        help='Field name in external system for the KPI date'
    )

    # Sync Settings
    sync_frequency = fields.Selection([
        ('manual', 'Manual Only'),
        ('hourly', 'Every Hour'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ], string='Sync Frequency', default='daily')

    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True
    )

    last_sync_status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
        ('never', 'Never Synced'),
    ], string='Last Sync Status', default='never', readonly=True)

    last_sync_message = fields.Text(
        string='Last Sync Message',
        readonly=True
    )

    records_synced = fields.Integer(
        string='Records Synced',
        readonly=True,
        help='Number of records synced in last run'
    )

    # Endpoint Configuration
    data_endpoint = fields.Char(
        string='Data Endpoint',
        help='API endpoint path for fetching KPI data (e.g., /kpis or /metrics)'
    )

    employee_endpoint = fields.Char(
        string='Employee Endpoint',
        help='API endpoint path for employee lookup (e.g., /employees)'
    )

    # Branch Mapping
    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        help='Link this integration to a specific branch'
    )

    # Notes
    notes = fields.Text(
        string='Notes',
        help='Configuration notes and documentation'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('configured', 'Configured'),
        ('testing', 'Testing'),
        ('active', 'Active'),
        ('error', 'Error'),
    ], string='Status', default='draft', tracking=True)

    def action_test_connection(self):
        """Test the API connection"""
        self.ensure_one()
        # Placeholder - would actually make an API call
        self.write({
            'state': 'testing',
            'last_sync_message': _('Connection test initiated. This is a placeholder — actual API integration will be implemented based on your system specifications.'),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Test'),
                'message': _('This is a placeholder. Configure actual API endpoints to enable connection testing.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_sync_now(self):
        """Manually trigger sync"""
        self.ensure_one()
        # Placeholder - would actually fetch and process data
        self.write({
            'last_sync_date': fields.Datetime.now(),
            'last_sync_status': 'success',
            'last_sync_message': _('Manual sync placeholder — no actual data was fetched. Configure API endpoints and mapping to enable real sync.'),
            'records_synced': 0,
        })

    def action_mark_active(self):
        """Mark integration as active"""
        self.ensure_one()
        if not self.api_base_url:
            raise UserError(_('Please configure the API Base URL before activating.'))
        self.state = 'active'

    def action_mark_draft(self):
        """Reset to draft"""
        self.state = 'draft'
