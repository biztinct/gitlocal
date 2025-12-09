# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class HrFormulaSampleData(models.Model):
    """
    Formula Sample Data - Stores sample employee data for testing formulas.
    Supports importing from real employees/payslips with anonymization.
    """
    _name = 'hr.formula.sample.data'
    _description = 'Formula Sample Data'
    _order = 'sequence, name'
    _rec_name = 'name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        ondelete='cascade',
        index=True
    )

    name = fields.Char(
        string='Sample Name',
        required=True,
        help="Descriptive name (e.g., 'Employee A', 'High Earner', 'Part-time Worker')"
    )

    description = fields.Text(
        string='Description',
        help="Additional notes about this sample data set"
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # ==========================================
    # SOURCE INFORMATION
    # ==========================================
    source_type = fields.Selection([
        ('manual', 'Manual Entry'),
        ('employee', 'From Employee'),
        ('payslip', 'From Payslip'),
        ('import', 'Imported from File')
    ], string='Source', default='manual')

    source_employee_id = fields.Many2one(
        'hr.employee',
        string='Source Employee',
        help="Original employee (for anonymized data)"
    )

    source_payslip_id = fields.Many2one(
        'hr.payslip',
        string='Source Payslip',
        help="Original payslip used for expected values"
    )

    is_anonymized = fields.Boolean(
        string='Anonymized',
        default=True,
        help="Data has been anonymized (names/IDs removed)"
    )

    source_date = fields.Date(
        string='Source Date',
        default=fields.Date.today,
        help="Date when sample data was captured"
    )

    # ==========================================
    # SAMPLE VALUES (JSON)
    # ==========================================
    input_values_json = fields.Text(
        string='Input Values (JSON)',
        default='{}',
        help="JSON object with input column values: {'BASIC': 10000, 'HOURS': 176, ...}"
    )

    expected_values_json = fields.Text(
        string='Expected Values (JSON)',
        default='{}',
        help="JSON object with expected calculated values for comparison"
    )

    computed_values_json = fields.Text(
        string='Computed Values (JSON)',
        compute='_compute_results',
        store=True,
        help="JSON object with formula-computed values"
    )

    # ==========================================
    # VALIDATION RESULTS
    # ==========================================
    all_passed = fields.Boolean(
        string='All Passed',
        compute='_compute_validation',
        store=True
    )

    discrepancy_count = fields.Integer(
        string='Discrepancies',
        compute='_compute_validation',
        store=True,
        help="Number of columns with value mismatch"
    )

    max_discrepancy = fields.Float(
        string='Max Discrepancy %',
        compute='_compute_validation',
        store=True,
        help="Maximum discrepancy percentage among all columns"
    )

    validation_status = fields.Selection([
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('warning', 'Warning')
    ], string='Status', compute='_compute_validation', store=True)

    last_computed = fields.Datetime(
        string='Last Computed',
        readonly=True
    )

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('input_values_json', 'config_id.rule_ids')
    def _compute_results(self):
        """Compute formula results for this sample data"""
        for record in self:
            if not record.input_values_json or not record.config_id:
                record.computed_values_json = '{}'
                continue

            try:
                input_values = json.loads(record.input_values_json)
                rules = record.config_id.rule_ids.sorted(key=lambda r: r.sequence)

                # Build results by evaluating each rule in order
                results = input_values.copy()

                for rule in rules:
                    if rule.column_type == 'input':
                        # Use input value or default
                        if rule.code not in results:
                            results[rule.code] = rule.default_value
                    elif rule.column_type == 'constant':
                        results[rule.code] = rule.constant_value
                    elif rule.column_type == 'formula':
                        # Evaluate formula with current results
                        value = rule.evaluate(results)
                        results[rule.code] = value

                record.computed_values_json = json.dumps(results)
                record.last_computed = fields.Datetime.now()

            except Exception as e:
                _logger.error(f"Error computing sample data {record.name}: {e}")
                record.computed_values_json = json.dumps({'error': str(e)})

    @api.depends('computed_values_json', 'expected_values_json')
    def _compute_validation(self):
        """Compare computed values with expected values"""
        for record in self:
            if not record.computed_values_json or not record.expected_values_json:
                record.all_passed = False
                record.discrepancy_count = 0
                record.max_discrepancy = 0
                record.validation_status = 'pending'
                continue

            try:
                computed = json.loads(record.computed_values_json)
                expected = json.loads(record.expected_values_json)

                discrepancies = 0
                max_disc = 0

                for code, exp_value in expected.items():
                    if exp_value is None:
                        continue

                    comp_value = computed.get(code, 0)
                    if exp_value == 0 and comp_value == 0:
                        continue

                    # Calculate discrepancy percentage
                    base = abs(exp_value) if exp_value != 0 else 1
                    disc = abs(exp_value - comp_value) / base * 100

                    if disc > 0.01:  # More than 0.01% difference
                        discrepancies += 1
                        max_disc = max(max_disc, disc)

                record.discrepancy_count = discrepancies
                record.max_discrepancy = max_disc
                record.all_passed = discrepancies == 0

                if discrepancies == 0:
                    record.validation_status = 'passed'
                elif max_disc > 1:  # More than 1% discrepancy
                    record.validation_status = 'failed'
                else:
                    record.validation_status = 'warning'

            except Exception as e:
                _logger.error(f"Error validating sample data {record.name}: {e}")
                record.all_passed = False
                record.discrepancy_count = 0
                record.max_discrepancy = 100
                record.validation_status = 'failed'

    # ==========================================
    # HELPER METHODS
    # ==========================================
    def get_input_values(self):
        """Return input values as dictionary"""
        self.ensure_one()
        return json.loads(self.input_values_json or '{}')

    def get_expected_values(self):
        """Return expected values as dictionary"""
        self.ensure_one()
        return json.loads(self.expected_values_json or '{}')

    def get_computed_values(self):
        """Return computed values as dictionary"""
        self.ensure_one()
        return json.loads(self.computed_values_json or '{}')

    def set_input_values(self, values):
        """Set input values from dictionary"""
        self.ensure_one()
        self.input_values_json = json.dumps(values)

    def set_expected_values(self, values):
        """Set expected values from dictionary"""
        self.ensure_one()
        self.expected_values_json = json.dumps(values)

    def get_comparison_data(self):
        """Get side-by-side comparison data for UI"""
        self.ensure_one()

        input_vals = self.get_input_values()
        expected_vals = self.get_expected_values()
        computed_vals = self.get_computed_values()

        comparison = []
        for rule in self.config_id.rule_ids.sorted(key=lambda r: r.sequence):
            code = rule.code
            expected = expected_vals.get(code)
            computed = computed_vals.get(code, 0)
            input_val = input_vals.get(code)

            # Calculate discrepancy
            disc = 0
            if expected is not None and expected != 0:
                disc = abs(expected - computed) / abs(expected) * 100
            elif expected is None and computed != 0:
                disc = 100

            comparison.append({
                'column_letter': rule.column_letter,
                'code': code,
                'name': rule.name,
                'column_type': rule.column_type,
                'input': input_val,
                'expected': expected,
                'computed': computed,
                'discrepancy': disc,
                'passed': disc < 0.01,
            })

        return comparison

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_recompute(self):
        """Force recomputation of values"""
        self._compute_results()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputed'),
                'message': _('Sample data values have been recomputed.'),
                'type': 'success',
            }
        }

    def action_copy_computed_to_expected(self):
        """Copy computed values to expected values"""
        self.ensure_one()
        self.expected_values_json = self.computed_values_json
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Copied'),
                'message': _('Computed values have been copied to expected values.'),
                'type': 'info',
            }
        }

    def action_view_comparison(self):
        """Open detailed comparison view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Value Comparison: %s') % self.name,
            'res_model': 'hr.formula.sample.data',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'pb_hr_payroll_formula.view_formula_sample_data_comparison'
            ).id,
            'target': 'new',
        }

    # ==========================================
    # IMPORT FROM PAYSLIP
    # ==========================================
    @api.model
    def create_from_payslip(self, payslip, config, anonymize=True):
        """Create sample data from an existing payslip"""
        input_values = {}
        expected_values = {}

        # Map payslip line values
        for line in payslip.line_ids:
            code = line.code
            # Find matching rule in config
            rule = config.rule_ids.filtered(lambda r: r.code == code)
            if rule:
                if rule.column_type == 'input':
                    input_values[code] = line.amount
                expected_values[code] = line.total

        # Get worked days data
        for wd in payslip.worked_days_line_ids:
            code = f"WD_{wd.code}"
            if code in [r.code for r in config.rule_ids]:
                input_values[code] = wd.number_of_hours

        # Create sample name
        name = f"Sample {payslip.number}"
        if anonymize:
            name = f"Employee Sample {len(config.sample_data_ids) + 1}"

        return self.create({
            'config_id': config.id,
            'name': name,
            'source_type': 'payslip',
            'source_payslip_id': payslip.id if not anonymize else False,
            'source_employee_id': payslip.employee_id.id if not anonymize else False,
            'is_anonymized': anonymize,
            'source_date': payslip.date_to,
            'input_values_json': json.dumps(input_values),
            'expected_values_json': json.dumps(expected_values),
        })


class HrFormulaTestResult(models.Model):
    """
    Formula Test Result - Stores individual test results for each
    rule/sample combination.
    """
    _name = 'hr.formula.test.result'
    _description = 'Formula Test Result'
    _order = 'sample_id, rule_code'

    # ==========================================
    # LINKS
    # ==========================================
    config_id = fields.Many2one(
        'hr.formula.config',
        string='Configuration',
        required=True,
        ondelete='cascade',
        index=True
    )

    sample_id = fields.Many2one(
        'hr.formula.sample.data',
        string='Sample Data',
        ondelete='cascade',
        index=True
    )

    # ==========================================
    # TEST DATA
    # ==========================================
    rule_code = fields.Char(
        string='Rule Code',
        required=True
    )

    rule_name = fields.Char(
        string='Rule Name',
        compute='_compute_rule_name'
    )

    expected_value = fields.Float(
        string='Expected',
        digits=(16, 2)
    )

    computed_value = fields.Float(
        string='Computed',
        digits=(16, 2)
    )

    difference = fields.Float(
        string='Difference',
        compute='_compute_difference',
        digits=(16, 2)
    )

    discrepancy_percent = fields.Float(
        string='Discrepancy %',
        digits=(5, 2)
    )

    # ==========================================
    # STATUS
    # ==========================================
    status = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
        ('error', 'Error')
    ], string='Status', required=True)

    error_message = fields.Text(
        string='Error Message'
    )

    test_date = fields.Datetime(
        string='Test Date',
        default=fields.Datetime.now
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('rule_code', 'config_id')
    def _compute_rule_name(self):
        for record in self:
            rule = record.config_id.rule_ids.filtered(
                lambda r: r.code == record.rule_code
            )[:1]
            record.rule_name = rule.name if rule else record.rule_code

    @api.depends('expected_value', 'computed_value')
    def _compute_difference(self):
        for record in self:
            record.difference = record.expected_value - record.computed_value
