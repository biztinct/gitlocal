# -*- coding: utf-8 -*-
"""
Integration Sync Wizard - Sync data from external HR systems.
"""

import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IntegrationSyncWizard(models.TransientModel):
    _name = 'hr.integration.sync.wizard'
    _description = 'Integration Data Sync Wizard'

    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Connector',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )

    config_id = fields.Many2one(
        'hr.formula.config',
        string='Target Configuration',
        help="Leave empty to use connector's linked configuration",
    )

    sync_mode = fields.Selection([
        ('preview', 'Preview Only'),
        ('sample', 'Create Sample Data'),
        ('full', 'Full Sync'),
    ], string='Sync Mode', default='preview', required=True)

    # For Excel connector
    import_file = fields.Binary('Excel/CSV File')
    import_filename = fields.Char('Filename')

    # Date range for API connectors
    date_from = fields.Date('Date From', default=fields.Date.context_today)
    date_to = fields.Date('Date To', default=fields.Date.context_today)

    # Options
    create_mappings = fields.Boolean(
        'Auto-Create Mappings',
        default=True,
        help="Automatically suggest field mappings",
    )
    anonymize = fields.Boolean(
        'Anonymize Data',
        default=True,
        help="Anonymize employee names in sample data",
    )
    max_records = fields.Integer(
        'Maximum Records',
        default=100,
        help="Maximum number of records to sync",
    )

    # Preview results
    preview_data = fields.Text('Preview Data', readonly=True)
    field_count = fields.Integer('Fields Discovered', readonly=True)
    record_count = fields.Integer('Records Found', readonly=True)

    state = fields.Selection([
        ('setup', 'Setup'),
        ('preview', 'Preview'),
        ('mapping', 'Mapping'),
        ('done', 'Done'),
    ], default='setup')

    @api.onchange('connector_id')
    def _onchange_connector_id(self):
        """Update config when connector changes."""
        if self.connector_id:
            # Find linked configurations
            configs = self.env['hr.formula.config'].search([
                ('connector_id', '=', self.connector_id.id),
            ])
            if configs:
                self.config_id = configs[0]

    def action_test_connection(self):
        """Test connection to external system."""
        self.ensure_one()

        connector = self._get_connector_instance()
        success, message = connector.test_connection()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success' if success else 'danger',
                'sticky': False,
            }
        }

    def action_fetch_fields(self):
        """Fetch available fields from source."""
        self.ensure_one()

        connector = self._get_connector_instance()

        # For Excel, load file first
        if self.connector_id.connector_type == 'excel':
            if not self.import_file:
                raise UserError(_("Please upload a file first"))

            content = base64.b64decode(self.import_file)
            if not connector.load_file(content, self.import_filename):
                raise UserError(_("Failed to load file"))

        fields_data = connector.get_available_fields()

        self.field_count = len(fields_data)
        self.preview_data = self._format_fields_preview(fields_data)
        self.state = 'preview'

        # Auto-create mappings if enabled
        if self.create_mappings and self.config_id:
            self._create_suggested_mappings(fields_data)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_fetch_data(self):
        """Fetch data from source."""
        self.ensure_one()

        connector = self._get_connector_instance()

        # For Excel, ensure file is loaded
        if self.connector_id.connector_type == 'excel':
            if not self.import_file:
                raise UserError(_("Please upload a file first"))

            content = base64.b64decode(self.import_file)
            if not connector.load_file(content, self.import_filename):
                raise UserError(_("Failed to load file"))

        # Fetch employees
        employees = connector.fetch_employees()

        if self.max_records and len(employees) > self.max_records:
            employees = employees[:self.max_records]

        self.record_count = len(employees)
        self.preview_data = self._format_data_preview(employees)
        self.state = 'preview'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_sync(self):
        """Execute data sync."""
        self.ensure_one()

        if not self.config_id:
            raise UserError(_("Please select a target configuration"))

        connector = self._get_connector_instance()

        # For Excel, ensure file is loaded
        if self.connector_id.connector_type == 'excel':
            if not self.import_file:
                raise UserError(_("Please upload a file first"))

            content = base64.b64decode(self.import_file)
            if not connector.load_file(content, self.import_filename):
                raise UserError(_("Failed to load file"))

        # Get mappings
        mappings = self.connector_id.field_mapping_ids.filtered(lambda m: m.active)

        if not mappings:
            raise UserError(_("No field mappings configured"))

        # Fetch and transform data
        employees = connector.fetch_employees()

        if self.max_records and len(employees) > self.max_records:
            employees = employees[:self.max_records]

        # Create sample data
        import json
        created_samples = self.env['hr.formula.sample.data']

        for idx, emp in enumerate(employees):
            try:
                transformed = connector.transform_data(emp, mappings)

                sample_name = f"Sync {idx + 1}"
                if not self.anonymize and 'name' in emp:
                    sample_name = f"Sync - {emp['name']}"

                values = {
                    'config_id': self.config_id.id,
                    'name': sample_name,
                    'description': f"Synced from {self.connector_id.name}",
                    'source_type': 'manual',
                    'is_anonymized': self.anonymize,
                    'input_values_json': json.dumps(transformed),
                }

                created_samples |= self.env['hr.formula.sample.data'].create(values)

            except Exception as e:
                _logger = __import__('logging').getLogger(__name__)
                _logger.warning(f"Failed to sync record {idx}: {e}")

        self.state = 'done'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%d records synced successfully') % len(created_samples),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'hr.formula.sample.data',
                    'view_mode': 'tree,form',
                    'domain': [('id', 'in', created_samples.ids)],
                },
            }
        }

    def _get_connector_instance(self):
        """Get connector class instance."""
        from ..integrations import (
            ZohoConnector, ExcelConnector, SAPConnector,
            WorkdayConnector, OracleConnector
        )

        connector_map = {
            'zoho': ZohoConnector,
            'excel': ExcelConnector,
            'sap': SAPConnector,
            'workday': WorkdayConnector,
            'oracle': OracleConnector,
        }

        connector_class = connector_map.get(self.connector_id.connector_type)
        if not connector_class:
            raise UserError(_("Unknown connector type: %s") % self.connector_id.connector_type)

        return connector_class(self.connector_id)

    def _format_fields_preview(self, fields_data):
        """Format fields data for preview display."""
        if not fields_data:
            return "No fields discovered"

        lines = ["Discovered Fields:", "=" * 40]
        for field in fields_data[:20]:
            lines.append(
                f"  {field.get('name', '?')}: {field.get('label', '')} "
                f"({field.get('data_type', 'unknown')})"
            )

        if len(fields_data) > 20:
            lines.append(f"  ... and {len(fields_data) - 20} more fields")

        return "\n".join(lines)

    def _format_data_preview(self, data):
        """Format data for preview display."""
        if not data:
            return "No data found"

        import json
        lines = [f"Found {len(data)} records:", "=" * 40]

        for idx, record in enumerate(data[:5]):
            # Show first few fields
            preview = {k: v for k, v in list(record.items())[:5] if not k.startswith('_')}
            lines.append(f"Record {idx + 1}: {json.dumps(preview, default=str)[:100]}...")

        if len(data) > 5:
            lines.append(f"... and {len(data) - 5} more records")

        return "\n".join(lines)

    def _create_suggested_mappings(self, fields_data):
        """Create suggested field mappings."""
        if not self.config_id:
            return

        # Get input rules
        input_rules = self.config_id.rule_ids.filtered(
            lambda r: r.column_type == 'input'
        )

        # Get existing mappings
        existing_sources = self.connector_id.field_mapping_ids.mapped('source_field')

        for field in fields_data:
            if field['name'] in existing_sources:
                continue

            # Try to match to a rule
            best_match = None
            best_score = 0

            field_name_upper = field['name'].upper().replace(' ', '_')

            for rule in input_rules:
                # Check code match
                if rule.code.upper() == field_name_upper:
                    best_match = rule
                    break

                # Check partial match
                if rule.code.upper() in field_name_upper or field_name_upper in rule.code.upper():
                    if len(rule.code) > best_score:
                        best_score = len(rule.code)
                        best_match = rule

            if best_match:
                self.env['hr.integration.field.mapping'].create({
                    'connector_id': self.connector_id.id,
                    'source_field': field['name'],
                    'source_field_label': field.get('label', field['name']),
                    'source_data_type': field.get('data_type', 'string'),
                    'target_rule_id': best_match.id,
                    'transformation_type': 'direct',
                    'active': True,
                })
