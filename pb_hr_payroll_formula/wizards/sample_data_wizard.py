# -*- coding: utf-8 -*-
"""
Sample Data Wizard - Generate sample data for formula testing.
"""

import json
import random
import string
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SampleDataWizard(models.TransientModel):
    _name = 'hr.formula.sample.data.wizard'
    _description = 'Sample Data Generation Wizard'

    config_id = fields.Many2one(
        'hr.formula.config',
        string='Configuration',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )

    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('employees', 'From Employees'),
        ('payslips', 'From Existing Payslips'),
        ('random', 'Generate Random Data'),
    ], string='Data Source', default='employees', required=True)

    # For employee source
    employee_ids = fields.Many2many(
        'hr.employee',
        'formula_sample_wizard_employee_rel',
        'wizard_id', 'employee_id',
        string='Employees',
    )

    # For payslip source
    payslip_ids = fields.Many2many(
        'hr.payslip',
        'formula_sample_wizard_payslip_rel',
        'wizard_id', 'payslip_id',
        string='Payslips',
    )

    # Options
    anonymize = fields.Boolean('Anonymize Data', default=True,
        help="Replace employee names with generic identifiers")
    sample_count = fields.Integer('Number of Samples', default=5,
        help="Number of random samples to generate")
    include_expected = fields.Boolean('Include Expected Values', default=True,
        help="Copy computed values as expected results for validation")

    # Random generation options
    min_salary = fields.Float('Minimum Salary', default=5000000)
    max_salary = fields.Float('Maximum Salary', default=50000000)

    @api.onchange('source')
    def _onchange_source(self):
        """Clear selections when source changes."""
        if self.source != 'employees':
            self.employee_ids = False
        if self.source != 'payslips':
            self.payslip_ids = False

    def action_generate_samples(self):
        """Generate sample data based on selected source."""
        self.ensure_one()

        if self.source == 'employees':
            samples = self._generate_from_employees()
        elif self.source == 'payslips':
            samples = self._generate_from_payslips()
        elif self.source == 'random':
            samples = self._generate_random()
        else:
            raise UserError(_("Please select a data source"))

        if not samples:
            raise UserError(_("No sample data could be generated"))

        # Create sample records
        created = self.env['hr.formula.sample.data']
        for sample_data in samples:
            created |= self.env['hr.formula.sample.data'].create(sample_data)

        # Return action to view created samples
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Samples'),
            'res_model': 'hr.formula.sample.data',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created.ids)],
            'context': {'default_config_id': self.config_id.id},
        }

    def _generate_from_employees(self):
        """Generate samples from selected employees."""
        samples = []

        if not self.employee_ids:
            # Get all active employees
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
            ], limit=self.sample_count)
        else:
            employees = self.employee_ids

        for idx, employee in enumerate(employees):
            sample_name = self._generate_sample_name(idx, employee)
            input_values = self._extract_employee_values(employee)

            samples.append({
                'config_id': self.config_id.id,
                'name': sample_name,
                'description': f"Sample from employee data",
                'source_type': 'employee',
                'source_employee_id': employee.id if not self.anonymize else False,
                'is_anonymized': self.anonymize,
                'input_values_json': json.dumps(input_values),
            })

        return samples

    def _generate_from_payslips(self):
        """Generate samples from existing payslips."""
        samples = []

        if not self.payslip_ids:
            # Get recent payslips
            payslips = self.env['hr.payslip'].search([
                ('state', '=', 'done'),
            ], order='date_to desc', limit=self.sample_count)
        else:
            payslips = self.payslip_ids

        for idx, payslip in enumerate(payslips):
            sample_name = self._generate_sample_name(idx, payslip.employee_id)
            input_values, expected_values = self._extract_payslip_values(payslip)

            sample_data = {
                'config_id': self.config_id.id,
                'name': sample_name,
                'description': f"Sample from payslip {payslip.name if not self.anonymize else 'XXX'}",
                'source_type': 'payslip',
                'source_payslip_id': payslip.id if not self.anonymize else False,
                'source_employee_id': payslip.employee_id.id if not self.anonymize else False,
                'is_anonymized': self.anonymize,
                'input_values_json': json.dumps(input_values),
            }

            if self.include_expected and expected_values:
                sample_data['expected_values_json'] = json.dumps(expected_values)

            samples.append(sample_data)

        return samples

    def _generate_random(self):
        """Generate random sample data."""
        samples = []

        # Get input rules
        input_rules = self.config_id.rule_ids.filtered(
            lambda r: r.column_type == 'input'
        )

        for idx in range(self.sample_count):
            sample_name = f"Random Sample {idx + 1}"
            input_values = {}

            for rule in input_rules:
                # Generate random value based on rule name/code
                value = self._generate_random_value(rule)
                input_values[rule.code] = value

            samples.append({
                'config_id': self.config_id.id,
                'name': sample_name,
                'description': "Randomly generated sample data",
                'source_type': 'manual',
                'is_anonymized': True,
                'input_values_json': json.dumps(input_values),
            })

        return samples

    def _generate_sample_name(self, index, employee=None):
        """Generate anonymized sample name."""
        if self.anonymize or not employee:
            letters = string.ascii_uppercase
            return f"Sample {letters[index % 26]}"
        else:
            return f"Sample - {employee.name}"

    def _extract_employee_values(self, employee):
        """Extract input values from employee record."""
        values = {}

        # Get input rules and their data source fields
        input_rules = self.config_id.rule_ids.filtered(
            lambda r: r.column_type == 'input'
        )

        for rule in input_rules:
            source_field = rule.data_source_field

            if not source_field:
                # Use default value
                values[rule.code] = rule.default_value or 0.0
                continue

            # Try to get value from employee or contract
            value = self._get_field_value(employee, source_field)

            if value is None and employee.contract_id:
                value = self._get_field_value(employee.contract_id, source_field)

            values[rule.code] = value if value is not None else (rule.default_value or 0.0)

        return values

    def _extract_payslip_values(self, payslip):
        """Extract input and expected values from payslip."""
        input_values = {}
        expected_values = {}

        # Get rules
        input_rules = self.config_id.rule_ids.filtered(
            lambda r: r.column_type == 'input'
        )
        formula_rules = self.config_id.rule_ids.filtered(
            lambda r: r.column_type == 'formula'
        )

        # Extract input values from payslip lines
        for rule in input_rules:
            # Find matching payslip line
            line = payslip.line_ids.filtered(
                lambda l: l.code == rule.code or l.salary_rule_id == rule.salary_rule_id
            )[:1]

            if line:
                input_values[rule.code] = line.total
            else:
                input_values[rule.code] = rule.default_value or 0.0

        # Extract expected values for formula columns
        for rule in formula_rules:
            line = payslip.line_ids.filtered(
                lambda l: l.code == rule.code or l.salary_rule_id == rule.salary_rule_id
            )[:1]

            if line:
                expected_values[rule.code] = line.total

        return input_values, expected_values

    def _get_field_value(self, record, field_path):
        """Get field value from record using dot notation."""
        if not field_path or not record:
            return None

        parts = field_path.split('.')
        current = record

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        if isinstance(current, models.Model):
            return None

        return current

    def _generate_random_value(self, rule):
        """Generate random value for a rule based on its type."""
        code_upper = rule.code.upper()

        # Basic salary
        if 'BASIC' in code_upper or 'SALARY' in code_upper:
            return round(random.uniform(self.min_salary, self.max_salary), 0)

        # Allowances (typically 10-30% of basic)
        if any(x in code_upper for x in ['HRA', 'HOUSING', 'RENT']):
            return round(random.uniform(self.min_salary * 0.1, self.min_salary * 0.3), 0)

        if any(x in code_upper for x in ['TRANSPORT', 'TRAVEL', 'CONVEYANCE']):
            return round(random.uniform(200000, 2000000), 0)

        if any(x in code_upper for x in ['MEAL', 'FOOD', 'LUNCH']):
            return round(random.uniform(500000, 1500000), 0)

        if any(x in code_upper for x in ['MEDICAL', 'HEALTH']):
            return round(random.uniform(300000, 1000000), 0)

        # Percentage-based (like tax rates)
        if any(x in code_upper for x in ['RATE', 'PERCENT', 'PCT']):
            return round(random.uniform(0, 0.35), 4)

        # Count/days
        if any(x in code_upper for x in ['DAYS', 'COUNT', 'HOURS']):
            return random.randint(1, 30)

        # Default: small to medium value
        return round(random.uniform(0, self.min_salary * 0.2), 0)
