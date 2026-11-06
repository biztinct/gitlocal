# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import json
import logging

_logger = logging.getLogger(__name__)


class EmployerCostCalculator(models.AbstractModel):
    """
    Formula-based employer cost calculator.

    Instead of hardcoded country-specific percentages, this uses the actual
    hr.formula.rule formulas from hr.formula.config to calculate costs.
    When base salary changes, the formula engine re-evaluates all dependent
    components (e.g., =B1*17.5% automatically uses the new B1 value).
    """
    _name = 'wfp.employer.cost.calculator'
    _description = 'WFP Employer Cost Calculator'

    @api.model
    def build_input_values(self, contract, formula_config):
        """Build input_values dict from contract data for formula evaluation.

        Maps:
        - contract.wage → base salary rule code (wfp_category=base_salary)
        - contract.advantage_ids → respective formula rule codes
        """
        values = {}
        rules = formula_config.rule_ids.sorted(key=lambda r: r.sequence)

        for rule in rules:
            if rule.column_type != 'input':
                continue

            value = rule.default_value or 0.0

            # Map the base salary
            if rule.wfp_category == 'base_salary':
                value = contract.wage or 0.0
            elif rule.is_contract_component:
                # Find matching contract advantage by code
                advantage = contract.advantages_ids.filtered(
                    lambda a: a.advantage_template_code == rule.code
                )[:1]
                if advantage:
                    value = advantage.amount or 0.0
            else:
                # Try code-based mapping for common inputs
                code_upper = (rule.code or '').upper()
                if code_upper in ('BASIC', 'BASE', 'WAGE', 'BASE_SALARY', 'BASESALARY'):
                    value = contract.wage or 0.0

            values[rule.code] = value
            if rule.column_letter:
                values[rule.column_letter] = value

        return values

    @api.model
    def build_modified_inputs(self, current_inputs, formula_config, new_base,
                              increase_rule=None):
        """Build modified input_values with the new base salary.

        The key insight: we ONLY modify the base salary input. All formula-
        dependent components (allowances calculated as % of base, employer
        contributions calculated as % of gross) will automatically re-calculate
        when the formula engine runs with the new base value.

        For 'base_and_allowances' rules, we also scale non-formula allowances.
        """
        modified = dict(current_inputs)
        rules = formula_config.rule_ids.sorted(key=lambda r: r.sequence)

        current_base = 0.0
        for rule in rules:
            if rule.wfp_category == 'base_salary' and rule.column_type == 'input':
                current_base = modified.get(rule.code, 0)
                modified[rule.code] = new_base
                if rule.column_letter:
                    modified[rule.column_letter] = new_base
                break

        # For 'base_and_allowances' target: also scale input-type allowances
        # that are NOT formula-calculated (i.e., fixed allowances from contract)
        if increase_rule and increase_rule.component_target == 'base_and_allowances':
            ratio = new_base / current_base if current_base else 1.0
            for rule in rules:
                if (rule.wfp_category == 'allowance' and
                        rule.column_type == 'input'):
                    old_val = modified.get(rule.code, 0)
                    modified[rule.code] = old_val * ratio
                    if rule.column_letter:
                        modified[rule.column_letter] = old_val * ratio

        return modified

    @api.model
    def evaluate_costs(self, formula_config, input_values):
        """Run the formula engine and return categorized cost results.

        Uses the same evaluation logic as the payslip formula engine.

        Returns: {
            'base': float,
            'allowances': float,
            'gross': float,
            'deductions': float,
            'net': float,
            'employer_cost': float,
            'total_cost': float,  # gross + employer_cost
            'bonus': float,
            'components': [{code, name, wfp_category, amount}, ...]
        }
        """
        rules = formula_config.rule_ids.sorted(key=lambda r: r.sequence)
        computed = dict(input_values)

        # Evaluate all rules using dependency order
        # First pass: constants and direct formulas
        for rule in rules:
            try:
                if rule.column_type == 'constant':
                    value = rule.constant_value or 0.0
                elif rule.column_type == 'formula' and rule.excel_formula:
                    value = rule.evaluate(computed)
                elif rule.column_type == 'input':
                    value = computed.get(rule.code, rule.default_value or 0.0)
                else:
                    value = computed.get(rule.code, 0.0)

                computed[rule.code] = value
                if rule.column_letter:
                    computed[rule.column_letter] = value
            except Exception as e:
                _logger.warning(
                    "WFP: Error evaluating rule %s: %s", rule.code, e
                )
                computed[rule.code] = 0.0
                if rule.column_letter:
                    computed[rule.column_letter] = 0.0

        # Second pass to resolve forward references
        for _pass in range(2):
            changed = False
            for rule in rules:
                if rule.column_type != 'formula':
                    continue
                try:
                    value = rule.evaluate(computed)
                except Exception:
                    value = 0.0
                if computed.get(rule.code) != value:
                    computed[rule.code] = value
                    if rule.column_letter:
                        computed[rule.column_letter] = value
                    changed = True
            if not changed:
                break

        # Categorize results by wfp_category
        result = {
            'base': 0.0,
            'allowances': 0.0,
            'gross': 0.0,
            'deductions': 0.0,
            'net': 0.0,
            'employer_cost': 0.0,
            'bonus': 0.0,
            'total_cost': 0.0,
            'components': [],
        }

        for rule in rules:
            amount = computed.get(rule.code, 0.0)
            if not isinstance(amount, (int, float)):
                try:
                    amount = float(amount)
                except (TypeError, ValueError):
                    amount = 0.0

            cat = rule.wfp_category
            if cat == 'base_salary':
                result['base'] += amount
            elif cat == 'allowance':
                result['allowances'] += amount
            elif cat == 'gross':
                result['gross'] = amount  # Gross is a total, not additive
            elif cat == 'deduction':
                result['deductions'] += abs(amount)
            elif cat == 'net':
                result['net'] = amount
            elif cat == 'employer_cost':
                result['employer_cost'] += abs(amount)
            elif cat == 'bonus':
                result['bonus'] += amount

            if cat and cat not in ('exclude', 'info'):
                result['components'].append({
                    'code': rule.code,
                    'name': rule.name,
                    'wfp_category': cat,
                    'amount': amount,
                })

        # If gross wasn't explicitly tagged, compute it
        if not result['gross']:
            result['gross'] = result['base'] + result['allowances'] + result['bonus']

        # Total cost to company = gross + employer contributions
        result['total_cost'] = result['gross'] + result['employer_cost']

        return result
