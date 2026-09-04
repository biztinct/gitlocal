# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
import re

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

    # ==========================================
    # USER-FRIENDLY INPUT LINES
    # ==========================================
    input_line_ids = fields.One2many(
        'hr.formula.sample.input.line',
        'sample_id',
        string='Input Values',
        help="User-friendly input values for testing"
    )

    computed_values_json = fields.Text(
        string='Computed Values (JSON)',
        compute='_compute_results',
        store=True,
        help="JSON object with formula-computed values"
    )

    computed_values_html = fields.Html(
        string='Computed Values (Table)',
        compute='_compute_computed_values_html',
        help="HTML table view of computed values for quick inspection"
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
                results = record._evaluate_rules_with_dependencies(input_values)

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
                # F6: shared coercion (superset of the old plain float() — any
                # value that used to coerce still coerces to the same number, so
                # verdicts are unchanged; regression-checked on the VN demo).
                from ..formula_engine.comparison import coerce_number as _coerce_number

                for code, exp_value in expected.items():
                    if exp_value is None:
                        continue

                    comp_value = computed.get(code, 0)
                    if exp_value == 0 and comp_value == 0:
                        continue

                    # Calculate discrepancy percentage
                    exp_num = _coerce_number(exp_value)
                    comp_num = _coerce_number(comp_value)
                    if exp_num is None or comp_num is None:
                        disc = 0 if str(exp_value) == str(comp_value) else 100
                    else:
                        base = abs(exp_num) if exp_num != 0 else 1
                        disc = abs(exp_num - comp_num) / base * 100

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

    def _compute_computed_values_html(self):
        """Render computed values as an HTML table for the UI tab."""
        for record in self:
            rows_html = []

            computed = record.get_computed_values()
            rules = record.config_id.rule_ids.sorted(key=lambda r: r.sequence)

            for rule in rules:
                value = computed.get(rule.code, 0)
                is_formula = rule.column_type == 'formula'
                row_style = "background:#f6f8fa;font-weight:bold;" if is_formula else ""
                formula_value = rule.excel_formula or ''
                formula_value = re.sub(r'(?<![A-Za-z0-9_])\$?([A-Z]{1,3})\$?\d+', r'\1', formula_value)

                # Format numeric values: round to integer, no decimals
                if isinstance(value, (int, float)):
                    display_value = f"{int(round(value)):,}"
                else:
                    display_value = str(value) if value else ''

                rows_html.append(
                    f"<tr style='{row_style}'>"
                    f"<td style='white-space:nowrap'>{rule.column_letter or ''}</td>"
                    f"<td style='white-space:normal;word-break:break-word;'>"
                    f"{rule.source_sheet_name or ''}</td>"
                    f"<td style='white-space:normal;word-break:break-word;'>{rule.name or ''}</td>"
                    f"<td style='white-space:normal;word-break:break-word;'>"
                    f"{rule.code or ''}</td>"
                    f"<td style='text-align:right;white-space:nowrap'>{display_value}</td>"
                    f"<td style='white-space:normal;word-break:break-word;' title='{formula_value}'>"
                    f"{formula_value}</td>"
                    "</tr>"
                )

            if rows_html:
                table_html = (
                    "<div style='width:100%;overflow-x:auto;'>"
                    "<table class='table table-sm' style='min-width:1200px;width:100%;table-layout:fixed;'>"
                    "<thead><tr>"
                    "<th style='width:6%'>Col</th>"
                    "<th style='width:18%'>Section</th>"
                    "<th style='width:22%'>Label/Name</th>"
                    "<th style='width:20%'>Code</th>"
                    "<th style='width:10%;text-align:right'>Value</th>"
                    "<th style='width:24%'>Formula</th>"
                    "</tr></thead>"
                    "<tbody>"
                    + "".join(rows_html) +
                    "</tbody></table>"
                    "</div>"
                )
            else:
                table_html = "<p class='text-muted'>No computed values available.</p>"

            record.computed_values_html = table_html

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

    def action_generate_input_lines(self):
        """Generate input lines from config's input columns"""
        self.ensure_one()
        if not self.config_id:
            raise UserError(_('Please select a Formula Configuration first.'))

        # Get existing input values
        existing_values = self.get_input_values()

        # Get input and constant columns from config
        input_rules = self.config_id.rule_ids.filtered(
            lambda r: r.column_type in ('input', 'constant')
        ).sorted(key=lambda r: r.sequence)

        # Delete existing lines
        self.input_line_ids.unlink()

        # Create new lines
        lines_to_create = []
        for rule in input_rules:
            value = existing_values.get(rule.code, rule.default_value or 0.0)
            if rule.column_type == 'constant':
                value = rule.constant_value or 0.0
            lines_to_create.append({
                'sample_id': self.id,
                'rule_id': rule.id,
                'column_letter': rule.column_letter,
                'column_code': rule.code,
                'column_name': rule.name,
                'column_type': rule.column_type,
                'value': value,
            })

        if lines_to_create:
            self.env['hr.formula.sample.input.line'].create(lines_to_create)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Input Lines Generated'),
                'message': _('%d input columns loaded. Enter values and click "Sync to JSON".') % len(lines_to_create),
                'type': 'success',
            }
        }

    def action_sync_input_to_json(self):
        """Sync input lines to JSON for computation with field toggle workaround

        This implements a multi-phase approach to handle editable tree pending edits:
        Phase 1: Collect current values and compute
        Phase 2: Save to database
        Phase 3: Toggle is_anonymized field and revert (forces commit of pending edits)
        Phase 4: Save again
        Phase 5: Re-read fresh values and recompute with accurate data
        """
        self.ensure_one()

        _logger.info("=== PHASE 1: Initial data collection and computation ===")

        # Phase 1: Collect current values from input lines (may be from cache/UI layer)
        input_values_phase1 = {}
        for line in self.input_line_ids:
            if line.column_type == 'input':
                input_values_phase1[line.column_code] = line.value
                _logger.debug(f"  Phase 1: {line.column_code} = {line.value}")

        if not input_values_phase1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Input Values'),
                    'message': _('Please click "Load Input Columns" first to populate the table, '
                                'then enter values before computing.'),
                    'type': 'warning',
                }
            }

        _logger.info(f"Phase 1 collected {len(input_values_phase1)} input values: {input_values_phase1}")

        # Compute with phase 1 values
        computed_phase1 = self._compute_formula_results(input_values_phase1)

        # Phase 2: Save to database
        _logger.info("=== PHASE 2: Writing to database (first save) ===")
        self.write({
            'input_values_json': json.dumps(input_values_phase1),
            'computed_values_json': json.dumps(computed_phase1),
            'last_computed': fields.Datetime.now(),
        })

        # Phase 3: Toggle is_anonymized field to force commit of pending editable tree changes
        _logger.info("=== PHASE 3: Toggling is_anonymized field to force commit ===")
        original_anonymized = self.is_anonymized
        _logger.debug(f"  Original is_anonymized: {original_anonymized}")

        # Toggle the field
        self.write({'is_anonymized': not original_anonymized})
        _logger.debug(f"  Toggled to: {not original_anonymized}")

        # Toggle it back to original value
        self.write({'is_anonymized': original_anonymized})
        _logger.debug(f"  Reverted to: {original_anonymized}")

        # Phase 4: Save again to ensure all changes are committed
        _logger.info("=== PHASE 4: Second save after field toggle ===")
        self.env.flush_all()
        self.invalidate_recordset(['input_line_ids'])

        # Refresh record from database to get committed values
        self_fresh = self.browse(self.id)

        # Phase 5: Re-collect input values (now fresh from database with committed edits)
        _logger.info("=== PHASE 5: Re-reading fresh data and recomputing ===")
        input_values_phase5 = {}
        for line in self_fresh.input_line_ids:
            if line.column_type == 'input':
                input_values_phase5[line.column_code] = line.value
                _logger.debug(f"  Phase 5 (fresh): {line.column_code} = {line.value}")

        _logger.info(f"Phase 5 collected {len(input_values_phase5)} fresh values: {input_values_phase5}")

        # Check if values changed between phase 1 and phase 5
        values_changed = input_values_phase1 != input_values_phase5
        if values_changed:
            _logger.info("  ✓ VALUES CHANGED - Pending edits were successfully committed!")
            _logger.info(f"  Phase 1 values: {input_values_phase1}")
            _logger.info(f"  Phase 5 values: {input_values_phase5}")
        else:
            _logger.info("  ℹ Values unchanged between phase 1 and phase 5")

        # Recompute with fresh values
        computed_phase5 = self_fresh._compute_formula_results(input_values_phase5)

        # Write final accurate results
        self_fresh.write({
            'input_values_json': json.dumps(input_values_phase5),
            'computed_values_json': json.dumps(computed_phase5),
            'last_computed': fields.Datetime.now(),
        })

        input_count = len(input_values_phase5)
        result_count = len(computed_phase5)

        _logger.info(f"=== COMPLETE: {input_count} inputs processed, {result_count} results computed ===")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synced & Computed'),
                'message': _('%d input values synced and %d formula results computed. '
                            'Check the Computed Results tab.') % (input_count, result_count),
                'type': 'success',
                'sticky': False,
            }
        }

    def _compute_formula_results(self, input_values):
        """Compute formula results from input values (helper method)"""
        self.ensure_one()
        if not self.config_id:
            _logger.warning("No config_id set for sample data")
            return {}

        try:
            results = self._evaluate_rules_with_dependencies(input_values)
            _logger.info(f"Formula computation complete. Results: {results}")
            return results
        except Exception as e:
            _logger.error(f"Error computing formula results: {e}", exc_info=True)
            return {'error': str(e)}

    def _evaluate_rules_with_dependencies(self, input_values, readonly=False,
                                          errors=None):
        """Evaluate rules using dependency order to handle forward references.

        ``readonly=True`` guarantees ZERO writes: the dependency-metadata
        refresh (a compute-field assignment that stamps write_date on every
        rule) is skipped, and formulas run through the ``_run_formula`` overlay
        with ``write_diagnostics=False`` instead of ``evaluate()``. Required
        for read-only RPC paths (the W54 Problems-rail detection runs on every
        panel open — it must never touch production rules).

        RD48 — ``errors`` is an optional caller-supplied dict, filled with
        ``{code: message}`` for every formula that raised. An OUT-PARAMETER, so
        the return value and every existing caller are untouched.

        It exists because a component's STORED error (``last_evaluation_error``)
        is a message from whatever data the formula last ran against WITH
        diagnostics on — usually a sample — while a read-only preview of a REAL
        person deliberately writes none. The panel could therefore show "float
        division by zero" beside a Standard Working Hour of 198, because a
        sample where that hour was 0 had failed days earlier. An error that
        belongs to THIS subject has to travel with THIS evaluation."""
        self.ensure_one()
        rules = self.config_id.rule_ids
        if not rules:
            return input_values.copy()

        # Refresh dependency metadata to include recent parsing changes.
        if not readonly:
            rules._compute_dependencies()
        try:
            from ..formula_engine import FormulaEvaluator
            evaluator = FormulaEvaluator()
            sorted_rules = evaluator._topological_sort(rules)
        except Exception:
            sorted_rules = rules.sorted(key=lambda r: r.sequence)

        _logger.info(
            "Computing formulas for %d rules with %d input values",
            len(sorted_rules),
            len(input_values)
        )

        results = input_values.copy()
        for rule in sorted_rules:
            _logger.debug("Processing rule %s (%s) - type: %s", rule.column_letter, rule.code, rule.column_type)
            if rule.column_type == 'input':
                if rule.code not in results:
                    results[rule.code] = rule.default_value or 0.0
                    _logger.debug("  Using default value: %s", results[rule.code])
                else:
                    _logger.debug("  Using input value: %s", results[rule.code])
            elif rule.column_type == 'constant':
                results[rule.code] = rule.constant_value or 0.0
                _logger.debug("  Using constant value: %s", results[rule.code])
            elif rule.column_type == 'formula':
                try:
                    _logger.debug("  Evaluating formula: %s", rule.excel_formula)
                    value = (rule._run_formula(results, rule.excel_formula,
                                               write_diagnostics=False)
                             if readonly else rule.evaluate(results))
                    results[rule.code] = value
                    _logger.debug("  Result: %s", value)
                except Exception as e:
                    _logger.warning("Formula evaluation error for %s: %s", rule.code, e)
                    results[rule.code] = 0.0
                    if errors is not None:
                        errors[rule.code] = str(e)
        # Second pass to resolve forward references not captured in dependency parsing.
        for _pass in range(2):
            changed = False
            for rule in sorted_rules:
                if rule.column_type != 'formula':
                    continue
                try:
                    value = (rule._run_formula(results, rule.excel_formula,
                                               write_diagnostics=False)
                             if readonly else rule.evaluate(results))
                except Exception as e:
                    _logger.warning("Formula re-evaluation error for %s: %s", rule.code, e)
                    value = 0.0
                    if errors is not None:
                        errors[rule.code] = str(e)
                else:
                    if errors is not None:
                        errors.pop(rule.code, None)
                if results.get(rule.code) != value:
                    results[rule.code] = value
                    changed = True
            if not changed:
                break

        return results

    @api.onchange('config_id')
    def _onchange_config_id(self):
        """Auto-generate input lines when config changes"""
        if self.config_id and self.source_type == 'manual':
            # Clear existing lines for manual entry
            self.input_line_ids = [(5, 0, 0)]

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


class HrFormulaSampleInputLine(models.Model):
    """
    Formula Sample Input Line - Stores individual input values for a sample data set.
    Provides a user-friendly way to enter test data instead of raw JSON.
    """
    _name = 'hr.formula.sample.input.line'
    _description = 'Formula Sample Input Line'
    _order = 'sequence, id'

    # ==========================================
    # LINKS
    # ==========================================
    sample_id = fields.Many2one(
        'hr.formula.sample.data',
        string='Sample Data',
        required=True,
        ondelete='cascade',
        index=True
    )

    rule_id = fields.Many2one(
        'hr.formula.rule',
        string='Formula Rule',
        ondelete='set null',
        help="Link to the formula rule this input corresponds to"
    )

    # ==========================================
    # COLUMN IDENTIFICATION
    # ==========================================
    column_letter = fields.Char(
        string='Column',
        readonly=True,
        help="Excel-style column letter (A, B, C...)"
    )

    column_code = fields.Char(
        string='Code',
        required=True,
        help="Salary rule code (e.g., BASIC, HRA)"
    )

    column_name = fields.Char(
        string='Name',
        help="Display name of the column"
    )

    column_type = fields.Selection([
        ('input', 'Input'),
        ('constant', 'Constant')
    ], string='Type', default='input')

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    # ==========================================
    # VALUE
    # ==========================================
    value = fields.Float(
        string='Value',
        digits=(16, 2),
        help="The input value for this column"
    )

    # ==========================================
    # COMPUTED FIELDS
    # ==========================================
    is_editable = fields.Boolean(
        string='Editable',
        compute='_compute_is_editable',
        help="Whether this value can be edited (only input columns are editable)"
    )

    @api.depends('column_type')
    def _compute_is_editable(self):
        """Only input columns should be editable by user"""
        for record in self:
            record.is_editable = record.column_type == 'input'

    # ==========================================
    # ONCHANGE
    # ==========================================
    @api.onchange('rule_id')
    def _onchange_rule_id(self):
        """Auto-fill column details from linked rule"""
        if self.rule_id:
            self.column_letter = self.rule_id.column_letter
            self.column_code = self.rule_id.code
            self.column_name = self.rule_id.name
            self.column_type = self.rule_id.column_type if self.rule_id.column_type in ('input', 'constant') else 'input'
            if self.rule_id.column_type == 'constant':
                self.value = self.rule_id.constant_value or 0.0
            elif not self.value:
                self.value = self.rule_id.default_value or 0.0
