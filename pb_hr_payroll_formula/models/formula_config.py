# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class HrFormulaConfig(models.Model):
    """
    Excel Formula Configuration - Main configuration model linking
    payroll structures to formula-based salary rules.
    """
    _name = 'hr.formula.config'
    _description = 'Excel Formula Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _rec_name = 'display_name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Configuration Name',
        required=True,
        tracking=True,
        help="A descriptive name for this formula configuration"
    )
    code = fields.Char(
        string='Reference Code',
        required=True,
        tracking=True,
        help="Unique code for this configuration (e.g., VN_STD_2024)"
    )
    description = fields.Html(
        string='Description',
        help="Detailed description of this configuration"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Determines display order"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    # ==========================================
    # COUNTRY & STRUCTURE LINKING
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
    ], string='Country', required=True, tracking=True)

    country_id = fields.Many2one(
        'res.country',
        string='Country Reference',
        compute='_compute_country_id',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True
    )

    payroll_journal_id = fields.Many2one(
        'account.journal',
        string='Payroll Journal',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help="Optional default journal to use when creating payslips from this configuration."
    )
    debit_account_id = fields.Many2one(
        'account.account',
        string='Default Debit Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Default debit account to assign when creating salary rules from this formula configuration."
    )
    credit_account_id = fields.Many2one(
        'account.account',
        string='Default Credit Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Default credit account to assign when creating salary rules from this formula configuration."
    )

    structure_id = fields.Many2one(
        'hr.payroll.structure',
        string='Payroll Structure',
        tracking=True,
        help="Link to the payroll structure this config applies to"
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # ==========================================
    # FORMULA RULES (One2many)
    # ==========================================
    rule_ids = fields.One2many(
        'hr.formula.rule',
        'config_id',
        string='Formula Rules',
        copy=True
    )

    rule_count = fields.Integer(
        string='Rules Count',
        compute='_compute_rule_count'
    )

    input_rule_count = fields.Integer(
        string='Input Rules',
        compute='_compute_rule_count'
    )

    formula_rule_count = fields.Integer(
        string='Formula Rules',
        compute='_compute_rule_count'
    )

    # ==========================================
    # SAMPLE DATA & TESTING
    # ==========================================
    sample_data_ids = fields.One2many(
        'hr.formula.sample.data',
        'config_id',
        string='Sample Data'
    )

    test_result_ids = fields.One2many(
        'hr.formula.test.result',
        'config_id',
        string='Test Results'
    )

    sample_count = fields.Integer(
        string='Sample Count',
        compute='_compute_sample_count'
    )

    # ==========================================
    # INTEGRATION
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Data Source Connector',
        help="HR system connector for importing payroll input data"
    )

    # ==========================================
    # STATE & VALIDATION
    # ==========================================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('testing', 'Testing'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)

    validation_status = fields.Selection([
        ('pending', 'Pending Validation'),
        ('passed', 'All Tests Passed'),
        ('failed', 'Tests Failed'),
        ('warning', 'Warnings')
    ], string='Validation Status', compute='_compute_validation_status', store=True)

    last_validated = fields.Datetime(
        string='Last Validated',
        readonly=True
    )

    last_validated_by = fields.Many2one(
        'res.users',
        string='Validated By',
        readonly=True
    )

    validation_message = fields.Text(
        string='Validation Message',
        readonly=True
    )

    has_circular_refs = fields.Boolean(
        string='Has Circular References',
        compute='_compute_has_circular_refs',
        store=True
    )

    has_errors = fields.Boolean(
        string='Has Errors',
        compute='_compute_has_errors',
        store=True
    )

    error_details = fields.Text(
        string='Error Details',
        compute='_compute_error_details',
        help="Detailed list of formulas with errors"
    )

    circular_ref_details = fields.Text(
        string='Circular Reference Details',
        compute='_compute_circular_ref_details',
        help="Detailed list of formulas with circular references"
    )

    # ==========================================
    # UI SETTINGS
    # ==========================================
    theme = fields.Selection([
        ('light', 'Light Theme'),
        ('dark', 'Dark Theme'),
        ('auto', 'Auto (System)')
    ], string='Grid Theme', default='light')

    grid_row_height = fields.Integer(
        string='Row Height (px)',
        default=32
    )

    show_formula_bar = fields.Boolean(
        string='Show Formula Bar',
        default=True
    )

    show_column_letters = fields.Boolean(
        string='Show Column Letters',
        default=True
    )

    show_gridlines = fields.Boolean(
        string='Show Gridlines',
        default=True
    )

    frozen_columns = fields.Integer(
        string='Frozen Columns',
        default=1,
        help="Number of columns to freeze on the left"
    )

    default_column_width = fields.Integer(
        string='Default Column Width (px)',
        default=120
    )

    # ==========================================
    # DISPLAY NAME
    # ==========================================
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('name', 'code', 'country_code')
    def _compute_display_name(self):
        for record in self:
            country = dict(self._fields['country_code'].selection).get(record.country_code, '')
            record.display_name = f"[{record.code}] {record.name} ({country})"

    @api.depends('country_code')
    def _compute_country_id(self):
        country_mapping = {
            'VN': 'VN', 'ID': 'ID', 'IN': 'IN', 'SG': 'SG',
            'MY': 'MY', 'TH': 'TH', 'KH': 'KH', 'PH': 'PH'
        }
        for record in self:
            if record.country_code:
                country = self.env['res.country'].search([
                    ('code', '=', country_mapping.get(record.country_code))
                ], limit=1)
                record.country_id = country
            else:
                record.country_id = False

    @api.depends('country_code')
    def _compute_currency_id(self):
        currency_mapping = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR', 'SG': 'SGD',
            'MY': 'MYR', 'TH': 'THB', 'KH': 'KHR', 'PH': 'PHP'
        }
        for record in self:
            if record.country_code:
                currency = self.env['res.currency'].search([
                    ('name', '=', currency_mapping.get(record.country_code))
                ], limit=1)
                record.currency_id = currency or self.env.company.currency_id
            else:
                record.currency_id = self.env.company.currency_id

    @api.depends('rule_ids', 'rule_ids.column_type')
    def _compute_rule_count(self):
        for record in self:
            record.rule_count = len(record.rule_ids)
            record.input_rule_count = len(record.rule_ids.filtered(
                lambda r: r.column_type == 'input'
            ))
            record.formula_rule_count = len(record.rule_ids.filtered(
                lambda r: r.column_type == 'formula'
            ))

    @api.depends('sample_data_ids')
    def _compute_sample_count(self):
        for record in self:
            record.sample_count = len(record.sample_data_ids)

    @api.depends('test_result_ids', 'test_result_ids.status')
    def _compute_validation_status(self):
        for record in self:
            if not record.test_result_ids:
                record.validation_status = 'pending'
            elif all(r.status == 'passed' for r in record.test_result_ids):
                record.validation_status = 'passed'
            elif any(r.status == 'failed' for r in record.test_result_ids):
                record.validation_status = 'failed'
            else:
                record.validation_status = 'warning'

    @api.depends('rule_ids.has_circular_ref')
    def _compute_has_circular_refs(self):
        for record in self:
            record.has_circular_refs = any(
                r.has_circular_ref for r in record.rule_ids
            )

    @api.depends('rule_ids.is_valid')
    def _compute_has_errors(self):
        for record in self:
            record.has_errors = any(
                not r.is_valid for r in record.rule_ids if r.excel_formula
            )

    @api.depends('rule_ids.is_valid', 'rule_ids.validation_message')
    def _compute_error_details(self):
        for record in self:
            invalid_rules = record.rule_ids.filtered(
                lambda r: r.excel_formula and not r.is_valid
            )
            if invalid_rules:
                details = []
                for rule in invalid_rules:
                    error_msg = rule.validation_message or _("Unknown error")
                    details.append(
                        f"• Column {rule.column_letter} ({rule.code}): {error_msg}"
                    )
                record.error_details = "\n".join(details)
            else:
                record.error_details = False

    @api.depends('rule_ids.has_circular_ref')
    def _compute_circular_ref_details(self):
        for record in self:
            circular_rules = record.rule_ids.filtered('has_circular_ref')
            if circular_rules:
                details = []
                for rule in circular_rules:
                    formula_preview = (rule.excel_formula or '')[:50]
                    if len(rule.excel_formula or '') > 50:
                        formula_preview += "..."
                    details.append(
                        f"• Column {rule.column_letter} ({rule.code}): {formula_preview}"
                    )
                record.circular_ref_details = "\n".join(details)
            else:
                record.circular_ref_details = False

    # ==========================================
    # CONSTRAINTS
    # ==========================================
    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Configuration code must be unique per company!'),
    ]

    @api.constrains('rule_ids')
    def _check_rule_codes(self):
        for record in self:
            codes = record.rule_ids.mapped('code')
            if len(codes) != len(set(codes)):
                raise ValidationError(_(
                    "Duplicate rule codes found! Each rule must have a unique code."
                ))

    # ==========================================
    # STATE ACTIONS
    # ==========================================
    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_start_testing(self):
        self.write({'state': 'testing'})
        return self.action_validate_formulas()

    def action_validate(self):
        """Validate all formulas and mark as validated"""
        self.ensure_one()
        self.action_validate_formulas()
        if not self.has_errors and not self.has_circular_refs:
            self.write({
                'state': 'validated',
                'last_validated': fields.Datetime.now(),
                'last_validated_by': self.env.user.id,
                'validation_message': _("All formulas validated successfully.")
            })
        else:
            self.write({
                'validation_message': _("Validation failed. Please fix errors before activating.")
            })

    def action_activate(self):
        """Activate the configuration for use in payroll"""
        self.ensure_one()
        if self.has_errors or self.has_circular_refs:
            raise UserError(_(
                "Cannot activate configuration with errors or circular references. "
                "Please validate and fix all issues first."
            ))
        self.write({'state': 'active'})

    def action_archive(self):
        self.write({'state': 'archived', 'active': False})

    # ==========================================
    # FORMULA VALIDATION
    # ==========================================
    def action_regenerate_formulas(self):
        """Regenerate Python code for all formula rules

        Use this after updating the formula conversion logic to refresh
        all cached Python formulas with the latest conversion engine.
        """
        self.ensure_one()
        rules = self.rule_ids.filtered(lambda r: r.column_type == 'formula' and r.excel_formula)

        # Build column mapping
        column_map = {}
        for r in self.rule_ids.sorted(key=lambda r: r.sequence):
            if r.column_letter and r.code:
                column_map[r.column_letter] = r.code

        regenerated = 0
        errors = []
        for rule in rules:
            try:
                python_code = rule._convert_excel_to_python(rule.excel_formula, column_map)
                rule.write({'python_formula': python_code})
                regenerated += 1
                _logger.info(f"Regenerated formula for {rule.code}: {rule.excel_formula} -> {python_code}")
            except Exception as e:
                errors.append(f"{rule.code}: {str(e)}")
                _logger.error(f"Failed to regenerate formula for {rule.code}: {e}")

        if errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Regeneration Complete with Errors'),
                    'message': _('%d formulas regenerated, %d errors:\n%s') % (
                        regenerated, len(errors), '\n'.join(errors[:5])
                    ),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Formulas Regenerated'),
                'message': _('%d Python formulas successfully regenerated.') % regenerated,
                'type': 'success',
            }
        }

    def action_validate_formulas(self):
        """Validate all formulas in this configuration"""
        self.ensure_one()
        from ..formula_engine import FormulaValidator

        validator = FormulaValidator()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)

        # Build column mapping
        column_map = {r.column_letter: r.code for r in rules}

        # Validate each formula
        errors = []
        for rule in rules:
            if rule.column_type == 'formula' and rule.excel_formula:
                is_valid, message = validator.validate_formula(
                    rule.excel_formula,
                    column_map
                )
                rule.write({
                    'is_valid': is_valid,
                    'validation_message': message if not is_valid else ''
                })
                if not is_valid:
                    errors.append(f"{rule.column_letter} ({rule.code}): {message}")

        # Check circular references
        circular = validator.check_circular_references(rules)
        for rule in rules:
            rule.has_circular_ref = rule.code in circular

        if errors:
            self.validation_message = _("Errors found:\n") + "\n".join(errors)
        else:
            self.validation_message = _("All formulas are valid.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validation Complete'),
                'message': self.validation_message,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            }
        }

    # ==========================================
    # SAMPLE DATA TESTING
    # ==========================================
    def action_run_tests(self):
        """Run all sample data tests"""
        self.ensure_one()
        from ..formula_engine import FormulaEvaluator

        evaluator = FormulaEvaluator()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)

        # Clear previous test results
        self.test_result_ids.unlink()

        results = []
        for sample in self.sample_data_ids:
            # Get input values
            input_values = json.loads(sample.input_values_json or '{}')
            expected_values = json.loads(sample.expected_values_json or '{}')

            # Evaluate formulas
            try:
                computed = evaluator.evaluate_all(rules, input_values)
                sample.computed_values_json = json.dumps(computed)

                # Compare results
                for code, expected in expected_values.items():
                    actual = computed.get(code, 0)
                    discrepancy = abs(expected - actual) / max(abs(expected), 1) * 100

                    results.append({
                        'config_id': self.id,
                        'sample_id': sample.id,
                        'rule_code': code,
                        'expected_value': expected,
                        'computed_value': actual,
                        'discrepancy_percent': discrepancy,
                        'status': 'passed' if discrepancy < 0.01 else 'failed',
                    })
            except Exception as e:
                results.append({
                    'config_id': self.id,
                    'sample_id': sample.id,
                    'rule_code': 'ERROR',
                    'expected_value': 0,
                    'computed_value': 0,
                    'discrepancy_percent': 100,
                    'status': 'failed',
                    'error_message': str(e),
                })

        # Create test result records
        self.env['hr.formula.test.result'].create(results)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tests Complete'),
                'message': _('%d tests executed. Check results for details.') % len(results),
                'type': 'info',
            }
        }

    # ==========================================
    # GRID DATA FOR UI
    # ==========================================
    def get_grid_data(self):
        """Return data formatted for the Excel-like grid widget"""
        self.ensure_one()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)

        columns = []
        for rule in rules:
            columns.append({
                'id': rule.id,
                'letter': rule.column_letter,
                'code': rule.code,
                'name': rule.name,
                'type': rule.column_type,
                'formula': rule.excel_formula or '',
                'width': rule.column_width,
                'format': rule.number_format,
                'decimals': rule.decimal_places,
                'isValid': rule.is_valid,
                'hasCircularRef': rule.has_circular_ref,
                'validationMessage': rule.validation_message or '',
                'categoryId': rule.category_id.id if rule.category_id else False,
                'categoryName': rule.category_id.name if rule.category_id else '',
            })

        # Sample data rows
        rows = []
        for sample in self.sample_data_ids:
            input_vals = json.loads(sample.input_values_json or '{}')
            computed_vals = json.loads(sample.computed_values_json or '{}')
            expected_vals = json.loads(sample.expected_values_json or '{}')

            row = {
                'id': sample.id,
                'name': sample.name,
                'isHeader': False,
                'values': {},
            }
            for rule in rules:
                code = rule.code
                row['values'][code] = {
                    'input': input_vals.get(code),
                    'computed': computed_vals.get(code),
                    'expected': expected_vals.get(code),
                }
            rows.append(row)

        return {
            'configId': self.id,
            'name': self.name,
            'theme': self.theme,
            'showFormulaBar': self.show_formula_bar,
            'showColumnLetters': self.show_column_letters,
            'showGridlines': self.show_gridlines,
            'frozenColumns': self.frozen_columns,
            'rowHeight': self.grid_row_height,
            'columns': columns,
            'rows': rows,
            'currency': self.currency_id.symbol if self.currency_id else '',
        }

    def save_grid_data(self, data):
        """Save grid data from the Excel-like widget"""
        self.ensure_one()

        # Update column order and formulas
        for col_data in data.get('columns', []):
            rule = self.env['hr.formula.rule'].browse(col_data['id'])
            if rule.exists():
                rule.write({
                    'sequence': col_data.get('sequence', rule.sequence),
                    'excel_formula': col_data.get('formula', rule.excel_formula),
                    'column_width': col_data.get('width', rule.column_width),
                    'name': col_data.get('name', rule.name),
                })

        # Update sample data
        for row_data in data.get('rows', []):
            sample = self.env['hr.formula.sample.data'].browse(row_data['id'])
            if sample.exists():
                sample.write({
                    'input_values_json': json.dumps(row_data.get('inputValues', {})),
                    'expected_values_json': json.dumps(row_data.get('expectedValues', {})),
                })

        # Trigger recomputation of column letters
        self.rule_ids._compute_column_letter()

        return {'success': True}

    # ==========================================
    # IMPORT FROM EXISTING STRUCTURE
    # ==========================================
    def action_import_from_structure(self):
        """Open wizard to import rules from existing payroll structure"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import from Payroll Structure'),
            'res_model': 'hr.formula.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
                'default_structure_id': self.structure_id.id if self.structure_id else False,
            }
        }

    # ==========================================
    # IMPORT FROM EXCEL (MULTI-SHEET WIZARD)
    # ==========================================
    def action_import_from_excel_multisheet(self):
        """Open multi-sheet Excel import wizard with enhanced features.

        This wizard provides:
        - Worksheet selection with checkboxes
        - Per-sheet column selection
        - Append order configuration
        - Cross-sheet formula resolution (VLOOKUP, SUMIF, etc.)
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import from Excel (Multi-Sheet)'),
            'res_model': 'hr.formula.multisheet.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
            }
        }

    # ==========================================
    # GENERATE SAMPLE DATA
    # ==========================================
    def action_generate_sample_data(self):
        """Open wizard to generate sample data from employees/payslips"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Sample Data'),
            'res_model': 'hr.formula.sample.data.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
            }
        }

    # ==========================================
    # OPEN EXCEL GRID
    # ==========================================
    def action_open_excel_grid(self):
        """Open the Excel-like formula configuration grid"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Formula Configuration Grid'),
            'res_model': 'hr.formula.config',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_formula.view_formula_config_excel_grid').id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_launch_payroll_import(self):
        """Launch payroll import with this configuration pre-selected"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Payroll Import'),
            'res_model': 'hr.payroll.import.batch',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_formula_config_id': self.id,
                'default_source_type': 'excel',
            },
        }

    def action_delete_all_rules(self):
        """Delete all salary component rules from this configuration"""
        self.ensure_one()
        rule_count = len(self.rule_ids)
        if rule_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Components'),
                    'message': _('There are no salary components to delete.'),
                    'type': 'warning',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

        self.rule_ids.unlink()
        _logger.info(f"Deleted {rule_count} salary component rules from config {self.code}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Components Deleted'),
                'message': _('%d salary components have been deleted.') % rule_count,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
