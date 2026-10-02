# -*- coding: utf-8 -*-
"""
Integration Sync Wizard - Advanced Pull with options.

Repurposed to feed into the main Pull → Store → Transform pipeline
(action_pull_data) with user-selectable filters:
  - Data types to pull
  - Date range / period
  - Max records
  - Preview before committing
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class IntegrationSyncWizard(models.TransientModel):
    _name = 'hr.integration.sync.wizard'
    _description = 'Integration Data Sync Wizard'

    # ==========================================
    # CONNECTION
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Connector',
        required=True,
        default=lambda self: self.env.context.get('default_connector_id')
                             or self.env.context.get('active_id'),
    )

    connector_type = fields.Selection(
        related='connector_id.connector_type',
        readonly=True,
    )

    # ==========================================
    # DATA TYPE SELECTION
    # ==========================================
    pull_employee = fields.Boolean('Employee Master Data', default=True)
    pull_salary = fields.Boolean('Salary / Payroll', default=True)
    pull_dependent = fields.Boolean('Dependents / Family', default=True)
    pull_attendance = fields.Boolean('Attendance', default=True)
    pull_leave = fields.Boolean('Leave / Time-Off', default=True)

    # ==========================================
    # DATE RANGE
    # ==========================================
    date_from = fields.Date(
        'Period From',
        default=lambda self: fields.Date.today().replace(day=1),
        help="Start of payroll period to pull data for",
    )
    date_to = fields.Date(
        'Period To',
        default=fields.Date.today,
        help="End of payroll period to pull data for",
    )

    # ==========================================
    # OPTIONS
    # ==========================================
    max_records = fields.Integer(
        'Max Employees',
        default=0,
        help="Maximum number of employees to pull (0 = all)",
    )

    run_transformations = fields.Boolean(
        'Run Transformation Rules',
        default=True,
        help="Execute transformation rules after pulling data",
    )

    # For Excel connector
    import_file = fields.Binary('Excel/CSV File')
    import_filename = fields.Char('Filename')

    # ==========================================
    # PREVIEW / RESULTS
    # ==========================================
    state = fields.Selection([
        ('setup', 'Setup'),
        ('preview', 'Preview'),
        ('done', 'Done'),
    ], default='setup')

    preview_data = fields.Text('Preview', readonly=True)
    preview_employee_count = fields.Integer('Employees Found', readonly=True)
    preview_record_count = fields.Integer('Total Records', readonly=True)

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('pull_employee', 'pull_salary', 'pull_dependent',
                 'pull_attendance', 'pull_leave')
    def _compute_data_type_summary(self):
        for rec in self:
            types = []
            if rec.pull_employee:
                types.append('Employee')
            if rec.pull_salary:
                types.append('Salary')
            if rec.pull_dependent:
                types.append('Dependents')
            if rec.pull_attendance:
                types.append('Attendance')
            if rec.pull_leave:
                types.append('Leave')
            rec.data_type_summary = ', '.join(types) if types else 'None selected'

    data_type_summary = fields.Char(
        'Selected Data Types',
        compute='_compute_data_type_summary',
    )

    # ==========================================
    # ACTIONS
    # ==========================================
    def _get_selected_data_types(self):
        """Return list of data type strings based on checkbox selection."""
        self.ensure_one()
        types = []
        if self.pull_employee:
            types.append('employee')
        if self.pull_salary:
            types.append('salary')
        if self.pull_dependent:
            types.append('dependent')
        if self.pull_attendance:
            types.append('attendance')
        if self.pull_leave:
            types.append('leave')
        return types

    def action_preview(self):
        """Preview what data will be pulled without committing."""
        self.ensure_one()

        if not self._get_selected_data_types():
            raise UserError(_("Please select at least one data type to pull."))

        connector = self.connector_id._get_connector_instance()

        # Authenticate
        if not connector.authenticate():
            raise UserError(
                _('Authentication failed for connector %s') % self.connector_id.name
            )

        # Preview: fetch employees to show count
        employees = connector.fetch_employees()
        if self.max_records and self.max_records > 0:
            employees = employees[:self.max_records]

        data_types = self._get_selected_data_types()

        # Build preview text
        lines = [
            f"🔌 Connector: {self.connector_id.name}",
            f"📅 Period: {self.date_from} → {self.date_to}",
            f"📋 Data types: {', '.join(data_types)}",
            f"",
            f"👥 Employees found: {len(employees)}",
            f"{'=' * 50}",
        ]

        total_records = len(employees)

        for emp in employees[:10]:
            emp_id = emp.get('employee_id', '?')
            name = emp.get('full_name') or emp.get('name', '?')
            dept = emp.get('department', '')
            lines.append(f"  {emp_id}: {name} ({dept})")

        if len(employees) > 10:
            lines.append(f"  ... and {len(employees) - 10} more employees")

        # Estimate record counts per data type
        lines.append(f"\n📊 Estimated records to pull:")
        if 'employee' in data_types:
            lines.append(f"  • Employee master: {len(employees)}")
            total_records += 0  # already counted
        if 'salary' in data_types:
            lines.append(f"  • Salary records: ~{len(employees)}")
            total_records += len(employees)
        if 'dependent' in data_types:
            lines.append(f"  • Dependent records: varies per employee")
        if 'attendance' in data_types:
            lines.append(f"  • Attendance records: ~{len(employees)}")
            total_records += len(employees)
        if 'leave' in data_types:
            lines.append(f"  • Leave records: varies per employee")

        # Show transformation rules
        rules = self.connector_id.transformation_rule_ids.filtered('active')
        if rules and self.run_transformations:
            lines.append(f"\n🔄 Transformation rules to execute ({len(rules)}):")
            for rule in rules:
                lines.append(f"  • {rule.name} → {rule.output_key} ({rule.rule_type})")

        self.preview_data = '\n'.join(lines)
        self.preview_employee_count = len(employees)
        self.preview_record_count = total_records
        self.state = 'preview'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_pull(self):
        """Execute the pull via the connector's action_pull_data pipeline."""
        self.ensure_one()

        data_types = self._get_selected_data_types()
        if not data_types:
            raise UserError(_("Please select at least one data type to pull."))

        # Delegate to the connector's main pipeline
        result = self.connector_id.action_pull_data(
            data_types=data_types,
            period_from=self.date_from,
            period_to=self.date_to,
            triggered_by='manual',
        )

        return result

    def action_back_to_setup(self):
        """Go back to setup from preview."""
        self.ensure_one()
        self.state = 'setup'
        self.preview_data = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
