# -*- coding: utf-8 -*-

import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrPayrollImportLine(models.Model):
    """
    Individual employee import line (staging data).
    This is a NEW staging model - does NOT use existing zoho staging tables.
    """
    _name = 'hr.payroll.import.line'
    _description = 'Payroll Import Line'
    _order = 'sequence, id'

    batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Import Batch',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(string='Row #', default=10)

    # Raw data storage
    raw_data_json = fields.Text(
        string='Raw Data (JSON)',
        help="Original row data from Excel as JSON"
    )

    # Matching fields (extracted from raw data for employee matching)
    employee_code = fields.Char(
        string='Employee Code',
        index=True,
        help="Employee code/ID from Excel (used for matching)"
    )
    employee_name = fields.Char(
        string='Employee Name',
        help="Employee name from Excel"
    )
    employee_email = fields.Char(
        string='Employee Email',
        index=True,
        help="Employee email from Excel (used for matching)"
    )

    # Matched/Created records
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        help="Matched or created employee"
    )
    is_new_employee = fields.Boolean(
        string='New Employee',
        default=False,
        help="True if employee needs to be created"
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        readonly=True,
        help="Created payslip"
    )

    # Computed salary values (after formula calculation)
    computed_values_json = fields.Text(
        string='Computed Values (JSON)',
        readonly=True,
        help="Formula computation results as JSON"
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('matched', 'Employee Matched'),
        ('unmatched', 'Unmatched'),
        ('validated', 'Validated'),
        ('error', 'Error'),
        ('processed', 'Processed'),
    ], string='Status', default='draft')

    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )

    # Display fields
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name'
    )

    # Related fields for easy access
    company_id = fields.Many2one(
        related='batch_id.company_id',
        store=True
    )
    formula_config_id = fields.Many2one(
        related='batch_id.formula_config_id',
        store=True
    )

    @api.depends('sequence', 'employee_name', 'employee_code')
    def _compute_display_name(self):
        for line in self:
            name_parts = []
            if line.sequence:
                name_parts.append("Row %d" % line.sequence)
            if line.employee_code:
                name_parts.append("[%s]" % line.employee_code)
            if line.employee_name:
                name_parts.append(line.employee_name)

            line.display_name = " - ".join(name_parts) if name_parts else "Import Line"

    def get_raw_data(self):
        """Parse and return raw data as dictionary"""
        self.ensure_one()
        if self.raw_data_json:
            try:
                return json.loads(self.raw_data_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_raw_data(self, data):
        """Store data as JSON"""
        self.ensure_one()
        self.raw_data_json = json.dumps(data)

    def get_computed_values(self):
        """Parse and return computed values as dictionary"""
        self.ensure_one()
        if self.computed_values_json:
            try:
                return json.loads(self.computed_values_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_computed_values(self, values):
        """Store computed values as JSON"""
        self.ensure_one()
        self.computed_values_json = json.dumps(values)

    def validate_line(self):
        """
        Validate the import line.
        Returns list of error messages (empty if valid).
        """
        self.ensure_one()
        errors = []

        # Check if we have employee info
        if not self.employee_id and not self.is_new_employee:
            if not self.employee_name:
                errors.append(_("Row %d: Missing employee name") % self.sequence)

        # Validate raw data against formula config
        raw_data = self.get_raw_data()
        config = self.formula_config_id

        if config:
            # Check required input fields
            for rule in config.rule_ids.filtered(lambda r: r.column_type == 'input' and r.is_required):
                value = self._get_value_for_rule(raw_data, rule)
                if value is None or value == '':
                    errors.append(_("Row %d: Missing required field '%s' (%s)") % (
                        self.sequence, rule.name, rule.code
                    ))

        if errors:
            self.error_message = "\n".join(errors)
        else:
            self.error_message = False

        return errors

    def _get_value_for_rule(self, raw_data, rule):
        """Get value from raw data for a specific rule"""
        # Try multiple possible keys
        possible_keys = [
            rule.code,
            rule.column_letter,
            rule.name,
            rule.data_source_field,
        ]

        for key in possible_keys:
            if key and key in raw_data:
                return raw_data[key]

            # Try case-insensitive
            if key:
                for data_key in raw_data.keys():
                    if data_key.lower() == key.lower():
                        return raw_data[data_key]

        return None

    def action_view_raw_data(self):
        """View raw data in popup"""
        self.ensure_one()
        raw_data = self.get_raw_data()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Raw Data - Row %d') % self.sequence,
            'res_model': 'hr.payroll.import.line',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_manual_match(self):
        """Open wizard to manually match employee"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Match Employee'),
            'res_model': 'hr.payroll.import.line.match.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_employee_name': self.employee_name,
                'default_employee_code': self.employee_code,
                'default_employee_email': self.employee_email,
            }
        }

    def action_retry(self):
        """Reset line to draft for retry"""
        self.ensure_one()
        self.state = 'draft'
        self.error_message = False

    def action_skip(self):
        """Skip this line (don't process)"""
        self.ensure_one()
        self.state = 'error'
        self.error_message = "Skipped by user"


class HrPayrollImportLineMatchWizard(models.TransientModel):
    """Wizard to manually match employee to import line"""
    _name = 'hr.payroll.import.line.match.wizard'
    _description = 'Match Employee Wizard'

    line_id = fields.Many2one(
        'hr.payroll.import.line',
        string='Import Line',
        required=True
    )
    employee_name = fields.Char(string='Name from Excel', readonly=True)
    employee_code = fields.Char(string='Code from Excel', readonly=True)
    employee_email = fields.Char(string='Email from Excel', readonly=True)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Match to Employee',
        help="Select existing employee to match"
    )
    create_new = fields.Boolean(
        string='Create New Employee',
        default=False
    )

    def action_confirm(self):
        """Confirm the match"""
        self.ensure_one()

        if self.create_new:
            self.line_id.is_new_employee = True
            self.line_id.employee_id = False
            self.line_id.state = 'unmatched'
        elif self.employee_id:
            self.line_id.employee_id = self.employee_id.id
            self.line_id.is_new_employee = False
            self.line_id.state = 'matched'
        else:
            raise ValidationError(_("Please select an employee or mark as new"))

        return {'type': 'ir.actions.act_window_close'}
