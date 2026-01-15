# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class HrPayslipFormula(models.Model):
    """
    Extends hr.payslip to support formula-based computation.
    """
    _inherit = 'hr.payslip'

    # ==========================================
    # FORMULA COMPUTATION FIELDS
    # ==========================================
    calculation_method = fields.Selection([
        ('standard', 'Standard (Salary Rules)'),
        ('spreadsheet', 'Spreadsheet Import'),
        ('formula', 'Formula Engine')
    ], string='Calculation Method', default='standard',
       help="Method used to compute this payslip")

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        help="Formula configuration used for computation"
    )

    formula_computation_log = fields.Text(
        string='Computation Log',
        readonly=True,
        help="Detailed log of formula computations"
    )

    formula_input_values = fields.Text(
        string='Input Values (JSON)',
        help="Input values used for formula computation"
    )

    formula_computed_values = fields.Text(
        string='Computed Values (JSON)',
        readonly=True,
        help="Computed values from formula engine"
    )

    payslip_identifier_payload = fields.Text(
        string='Payslip Identifier Payload (JSON)',
        readonly=True,
        help="Grouped component values for payslip printing."
    )
    report_visible_string_payload = fields.Text(
        string='Report Visible String Payload (JSON)',
        readonly=True,
        help="String values for report_visible components (used for exports)."
    )

    has_formula_errors = fields.Boolean(
        string='Has Formula Errors',
        compute='_compute_has_formula_errors'
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('formula_computation_log')
    def _compute_has_formula_errors(self):
        for record in self:
            log = record.formula_computation_log or ''
            record.has_formula_errors = 'Error' in log or 'error' in log

    # ==========================================
    # FORMULA COMPUTATION
    # ==========================================
    def compute_sheet_with_formulas(self):
        """
        Compute payslip using formula engine instead of standard salary rules.
        """
        for payslip in self:
            if not payslip.formula_config_id:
                # Try to find appropriate config
                config = payslip._find_formula_config()
                if config:
                    payslip.formula_config_id = config
                else:
                    raise UserError(_(
                        "No formula configuration found for this payslip. "
                        "Please configure formula rules or use standard computation."
                    ))

            config = payslip.formula_config_id

            # Validate config is active
            if config.state != 'active':
                raise UserError(_(
                    "Formula configuration '%s' is not active. "
                    "Please activate it before using for payroll."
                ) % config.name)

            # Get input values
            input_values = payslip._get_formula_input_values(config)
            payslip.formula_input_values = json.dumps(input_values, indent=2)

            # Get rules in order (display) but compute using dependency sorting
            rules = config.rule_ids.sorted(key=lambda r: r.sequence)

            computed_values, computation_log = payslip._evaluate_rules_with_dependencies(
                rules,
                input_values
            )

            payslip.formula_computed_values = json.dumps(computed_values, indent=2)
            payslip.formula_computation_log = '\n'.join(computation_log)
            if 'report_visible_string_payload' in payslip._fields:
                payload = payslip._build_report_visible_string_payload(rules, computed_values)
                payslip.report_visible_string_payload = json.dumps(payload)

            # Create/update payslip lines
            payslip._create_payslip_lines_from_formulas(rules, computed_values)

            # Mark calculation method
            payslip.calculation_method = 'formula'

        return True

    def _evaluate_rules_with_dependencies(self, rules, input_values):
        """Evaluate rules using dependency order to handle forward references."""
        self.ensure_one()
        if not rules:
            return input_values.copy(), []

        rules._compute_dependencies()
        try:
            from ..formula_engine import FormulaEvaluator
            evaluator = FormulaEvaluator()
            sorted_rules = evaluator._topological_sort(rules)
        except Exception:
            sorted_rules = rules.sorted(key=lambda r: r.sequence)

        results = input_values.copy()
        computation_log = []

        for rule in sorted_rules:
            try:
                if rule.column_type == 'input':
                    if rule.code not in results:
                        results[rule.code] = rule.default_value or 0.0
                    value = results.get(rule.code, 0.0)
                    computation_log.append(
                        f"[{rule.column_letter}] {rule.code} (input) = {value}"
                    )
                elif rule.column_type == 'constant':
                    value = rule.constant_value or 0.0
                    results[rule.code] = value
                    computation_log.append(
                        f"[{rule.column_letter}] {rule.code} (constant) = {value}"
                    )
                elif rule.column_type == 'formula':
                    value = rule.evaluate(results)
                    results[rule.code] = value
                    computation_log.append(
                        f"[{rule.column_letter}] {rule.code} = {rule.excel_formula} -> {value}"
                    )
            except Exception as e:
                error_msg = f"Error in {rule.code}: {str(e)}"
                computation_log.append(f"[ERROR] {error_msg}")
                results[rule.code] = 0.0

            if rule.column_letter:
                results[rule.column_letter] = results.get(rule.code, 0.0)

        # Second pass to resolve forward references not captured in dependency parsing.
        for _pass in range(2):
            changed = False
            for rule in sorted_rules:
                if rule.column_type != 'formula':
                    continue
                try:
                    value = rule.evaluate(results)
                except Exception as e:
                    computation_log.append(f"[ERROR] Error in {rule.code}: {str(e)}")
                    value = 0.0
                if results.get(rule.code) != value:
                    results[rule.code] = value
                    if rule.column_letter:
                        results[rule.column_letter] = value
                    changed = True
            if not changed:
                break

        return results, computation_log

    def _build_report_visible_string_payload(self, rules, computed_values):
        """Capture string values for report_visible components."""
        self.ensure_one()

        def coerce_numeric_string(value):
            cleaned = value.strip().replace(' ', '')
            if not cleaned:
                return None
            try:
                if ',' in cleaned and '.' in cleaned:
                    if cleaned.rfind(',') > cleaned.rfind('.'):
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                    else:
                        cleaned = cleaned.replace(',', '')
                elif ',' in cleaned:
                    parts = cleaned.split(',')
                    if all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                    else:
                        cleaned = cleaned.replace(',', '.')
                elif '.' in cleaned:
                    parts = cleaned.split('.')
                    if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                return float(cleaned)
            except (ValueError, TypeError):
                return None

        payload = []
        for rule in rules:
            if not rule.report_visible:
                continue
            value = computed_values.get(rule.code)
            if value is None and rule.column_letter:
                value = computed_values.get(rule.column_letter)
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            if not stripped:
                continue
            if coerce_numeric_string(stripped) is not None:
                continue
            payload.append({
                'code': rule.code or '',
                'name': rule.name or '',
                'value': stripped,
            })
        return payload

    def _find_formula_config(self):
        """Find appropriate formula configuration for this payslip"""
        self.ensure_one()

        # Try to find config based on structure
        if self.struct_id:
            config = self.env['hr.formula.config'].search([
                ('structure_id', '=', self.struct_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if config:
                return config

        # Try to find config based on employee's country
        if self.employee_id and self.employee_id.country_id:
            country_code = self.employee_id.country_id.code
            config = self.env['hr.formula.config'].search([
                ('country_code', '=', country_code),
                ('state', '=', 'active'),
            ], limit=1)
            if config:
                return config

        # Try to find any active config for this company
        config = self.env['hr.formula.config'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'active'),
        ], limit=1)

        return config

    def _get_formula_input_values(self, config):
        """
        Get input values for formula computation from various sources:
        - Contract data (wage, allowances)
        - Worked days
        - External integration (Zoho, etc.)
        """
        self.ensure_one()
        values = {}

        # Get input rules
        input_rules = config.rule_ids.filtered(lambda r: r.column_type == 'input')

        for rule in input_rules:
            value = rule.default_value

            # Try to get from contract
            if self.contract_id:
                contract_mapping = {
                    'BASIC': 'wage',
                    'WAGE': 'wage',
                    'BASE': 'wage',
                }
                contract_field = contract_mapping.get(rule.code.upper())
                if contract_field and hasattr(self.contract_id, contract_field):
                    value = getattr(self.contract_id, contract_field) or value

            # Try to get from worked days
            if rule.code.startswith('WD_') or rule.code.startswith('HOURS'):
                wd_code = rule.code.replace('WD_', '').replace('HOURS_', '')
                worked_day = self.worked_days_line_ids.filtered(
                    lambda w: w.code == wd_code
                )[:1]
                if worked_day:
                    if 'HOURS' in rule.code:
                        value = worked_day.number_of_hours
                    else:
                        value = worked_day.number_of_days

            # Try to get from integration connector
            if config.connector_id:
                # Get from mapped field
                mapping = config.connector_id.field_mapping_ids.filtered(
                    lambda m: m.target_rule_id == rule
                )[:1]
                if mapping:
                    # TODO: Get actual value from synced data
                    pass

            values[rule.code] = value

        return values

    def _create_payslip_lines_from_formulas(self, rules, computed_values):
        """Create payslip lines from formula computation results"""
        self.ensure_one()

        # Clear existing lines
        self.line_ids.unlink()

        lines_to_create = []

        for rule in rules:
            if not rule.appears_on_payslip:
                continue

            amount = computed_values.get(rule.code, 0.0)

            # Find or create salary rule
            salary_rule = rule.salary_rule_id
            if not salary_rule:
                # Try to find existing rule with same code
                salary_rule = self.env['hr.salary.rule'].search([
                    ('code', '=', rule.code),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            line_data = {
                'slip_id': self.id,
                'name': rule.name,
                'code': rule.code,
                'category_id': rule.category_id.id if rule.category_id else False,
                'sequence': rule.sequence,
                'amount': amount,
                'quantity': 1.0,
                'rate': 100.0,
                'salary_rule_id': salary_rule.id if salary_rule else False,
                'contract_id': self.contract_id.id,
                'employee_id': self.employee_id.id,
                'report_visible': rule.report_visible or False,
                'component_type': rule.component_type or False,
            }
            lines_to_create.append(line_data)

        if lines_to_create:
            self.env['hr.payslip.line'].create(lines_to_create)

    # ==========================================
    # OVERRIDE STANDARD COMPUTE
    # ==========================================
    def compute_sheet(self):
        """Override to support formula-based computation"""
        formula_payslips = self.filtered(
            lambda p: p.calculation_method == 'formula' and p.formula_config_id
        )
        standard_payslips = self - formula_payslips

        # Compute formula payslips
        if formula_payslips:
            formula_payslips.compute_sheet_with_formulas()

        # Compute standard payslips
        if standard_payslips:
            return super(HrPayslipFormula, standard_payslips).compute_sheet()

        return True

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_recompute_formula_lines(self):
        for payslip in self:
            config = payslip.formula_config_id or payslip._find_formula_config()
            if not config:
                raise UserError(_(
                    "No formula configuration found for this payslip."
                ))
            if payslip.formula_config_id != config:
                payslip.formula_config_id = config.id
            if payslip.calculation_method != 'formula':
                payslip.calculation_method = 'formula'

            import_line = self.env['hr.payroll.import.line'].search(
                [('payslip_id', '=', payslip.id)],
                limit=1
            )
            input_values = None
            if import_line and import_line.batch_id:
                batch = import_line.batch_id
                input_values = batch._transform_data_to_formula_inputs(
                    import_line.get_raw_data(),
                    contract=payslip.contract_id,
                    employee=payslip.employee_id,
                )
                payslip.formula_input_values = json.dumps(input_values)
                payslip.line_ids.unlink()
                batch._compute_and_create_payslip_lines(payslip, input_values)
            else:
                if payslip.formula_input_values:
                    try:
                        input_values = json.loads(payslip.formula_input_values or '{}')
                    except Exception:
                        input_values = {}
                else:
                    input_values = payslip._get_formula_input_values(config)
                    payslip.formula_input_values = json.dumps(input_values, indent=2)

                rules = config.rule_ids.sorted(key=lambda r: r.sequence)
                computed_values, computation_log = payslip._evaluate_rules_with_dependencies(
                    rules,
                    input_values
                )
                payslip.formula_computed_values = json.dumps(computed_values, indent=2)
                payslip.formula_computation_log = '\n'.join(computation_log)
                if 'report_visible_string_payload' in payslip._fields:
                    payload = payslip._build_report_visible_string_payload(rules, computed_values)
                    payslip.report_visible_string_payload = json.dumps(payload)
                payslip._create_payslip_lines_from_formulas(rules, computed_values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputed'),
                'message': _("Payslip formulas recalculated with current settings."),
                'type': 'success',
            }
        }

    def action_switch_to_formula(self):
        """Switch this payslip to formula-based computation"""
        self.ensure_one()
        config = self._find_formula_config()
        if not config:
            raise UserError(_(
                "No active formula configuration found. "
                "Please create and activate a formula configuration first."
            ))

        self.write({
            'calculation_method': 'formula',
            'formula_config_id': config.id,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Switched to Formula Mode'),
                'message': _("Using configuration: %s") % config.name,
                'type': 'success',
            }
        }

    def action_payslip_level2_done(self):
        result = super().action_payslip_level2_done()
        self._trigger_mid_cycle_carryover()
        return result

    def _trigger_mid_cycle_carryover(self):
        if 'hr.payroll.import.batch' not in self.env:
            return
        batch_model = self.env['hr.payroll.import.batch']
        batches = batch_model
        for slip in self:
            batch = False
            if slip.payslip_run_id:
                batch = batch_model.search(
                    [('payslip_run_id', '=', slip.payslip_run_id.id)],
                    limit=1
                )
            if not batch:
                batch = batch_model.search(
                    [('created_payslip_ids', 'in', slip.id)],
                    limit=1
                )
            if not batch:
                continue
            config = batch.formula_config_id or slip.formula_config_id
            if not config or config.cycle_type != 'mid_cycle':
                continue
            batches |= batch
        for batch in batches:
            payslips = batch.created_payslip_ids
            run = batch.payslip_run_id
            if not payslips and run:
                payslips = run.slip_ids
            if payslips:
                batch._create_mid_cycle_carryovers(payslips, payslip_run=run)

    def action_switch_to_standard(self):
        """Switch back to standard salary rule computation"""
        self.write({
            'calculation_method': 'standard',
        })

    def action_view_formula_log(self):
        """View detailed formula computation log"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Formula Computation Log'),
            'res_model': 'hr.payslip',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'pb_hr_payroll_formula.view_payslip_formula_log'
            ).id,
            'target': 'new',
        }
