# -*- coding: utf-8 -*-
"""
Formula Evaluator - Evaluates converted Python formulas at runtime.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class FormulaEvaluationError(Exception):
    """Raised when formula evaluation fails"""
    pass


class FormulaEvaluator:
    """
    Evaluates converted Python formulas in a safe context.

    Features:
    - Topological sorting for correct evaluation order
    - Safe evaluation with restricted builtins
    - Caching for performance
    - Error handling with detailed messages
    """

    # Safe functions available in formula context
    SAFE_FUNCTIONS = {
        # Math
        'sum': sum,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round,
        'pow': pow,
        'int': int,
        'float': float,

        # Math module functions
        'sqrt': math.sqrt,
        'ceil': math.ceil,
        'floor': math.floor,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,

        # Boolean
        'all': all,
        'any': any,
        'len': len,

        # Type checking
        'isinstance': isinstance,
        'type': type,
    }

    def __init__(self):
        self.results_cache: Dict[str, float] = {}
        self._helper_functions = self._create_helper_functions()

    def _create_helper_functions(self) -> Dict[str, callable]:
        """Create helper functions for Excel function emulation"""
        return {
            '_avg': self._excel_average,
            '_if': self._excel_if,
            '_iferror': self._excel_iferror,
            '_isblank': self._excel_isblank,
            '_mod': self._excel_mod,
            '_sign': self._excel_sign,
            '_roundup': self._excel_roundup,
            '_rounddown': self._excel_rounddown,
            '_concat': self._excel_concat,
            '_counta': self._excel_counta,
            '_vlookup': self._excel_vlookup,
        }

    def evaluate_all(
        self,
        rules: List[Any],
        input_values: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Evaluate all formula rules in dependency order.

        Args:
            rules: List of formula rule objects with attributes:
                   - code: Rule identifier
                   - column_type: 'input', 'constant', or 'formula'
                   - python_formula: Converted Python expression
                   - constant_value: Value for constant type
                   - default_value: Default for missing inputs
            input_values: Dict of input values by rule code

        Returns:
            Dict of all computed values by rule code
        """
        # Initialize results with input values
        results = input_values.copy()

        # Sort rules by dependency order
        sorted_rules = self._topological_sort(rules)

        # Evaluate each rule
        for rule in sorted_rules:
            try:
                if rule.column_type == 'input':
                    # Use provided value or default
                    if rule.code not in results:
                        results[rule.code] = getattr(rule, 'default_value', 0.0) or 0.0

                elif rule.column_type == 'constant':
                    results[rule.code] = getattr(rule, 'constant_value', 0.0) or 0.0

                elif rule.column_type == 'formula':
                    formula = getattr(rule, 'python_formula', '')
                    if formula:
                        value = self.evaluate_single(formula, results)
                        results[rule.code] = value
                    else:
                        results[rule.code] = 0.0

            except Exception as e:
                _logger.error(f"Error evaluating rule {rule.code}: {e}")
                results[rule.code] = 0.0

        return results

    def evaluate_single(
        self,
        python_formula: str,
        context: Dict[str, float]
    ) -> float:
        """
        Evaluate a single Python formula expression.

        Args:
            python_formula: Python expression string
            context: Dict of available variable values

        Returns:
            Computed float value
        """
        if not python_formula:
            return 0.0

        # Build safe evaluation context
        safe_context = self._build_safe_context(context)

        try:
            # Sanitize None -> 0 for arithmetic
            safe_context["values"] = {
                k: (0 if v is None else v) for k, v in values.items()
            }

            result = eval(python_formula, {"__builtins__": {}}, safe_context)
            return float(result) if result is not None else 0.0

        except ZeroDivisionError:
            _logger.warning(f"Division by zero in formula: {python_formula}")
            return 0.0

        except Exception as e:
            raise FormulaEvaluationError(
                f"Error evaluating '{python_formula}': {str(e)}"
            )

    def _build_safe_context(self, values: Dict[str, float]) -> Dict[str, Any]:
        """
        Build a safe evaluation context with values and functions.
        """
        context = {
            # Values dictionary for cell references
            'values': values,

            # Math module
            'math': math,
        }

        # Add safe functions
        context.update(self.SAFE_FUNCTIONS)

        # Add helper functions
        context.update(self._helper_functions)

        # Add self reference for method calls
        context['self'] = self

        return context

    def _topological_sort(self, rules: List[Any]) -> List[Any]:
        """
        Sort rules in dependency order using topological sort.

        Rules are sorted so that dependencies are evaluated before
        the rules that depend on them.
        """
        # Build dependency graph
        code_to_rule = {r.code: r for r in rules}
        dependencies = defaultdict(set)
        dependents = defaultdict(set)

        for rule in rules:
            if rule.column_type == 'formula':
                # Get dependencies from formula_dependencies or parse formula
                deps = getattr(rule, 'formula_dependencies', '')
                if deps:
                    for dep_letter in deps.split(','):
                        dep_letter = dep_letter.strip()
                        # Find rule with this column letter
                        for r in rules:
                            if getattr(r, 'column_letter', '') == dep_letter:
                                dependencies[rule.code].add(r.code)
                                dependents[r.code].add(rule.code)
                                break

        # Kahn's algorithm for topological sort
        # Start with rules that have no dependencies
        in_degree = {r.code: len(dependencies[r.code]) for r in rules}
        queue = [r for r in rules if in_degree[r.code] == 0]
        sorted_rules = []

        while queue:
            rule = queue.pop(0)
            sorted_rules.append(rule)

            for dep_code in dependents[rule.code]:
                in_degree[dep_code] -= 1
                if in_degree[dep_code] == 0:
                    queue.append(code_to_rule[dep_code])

        # Check for circular dependencies
        if len(sorted_rules) != len(rules):
            missing = set(r.code for r in rules) - set(r.code for r in sorted_rules)
            _logger.warning(f"Possible circular dependency involving: {missing}")
            # Add remaining rules at the end
            for rule in rules:
                if rule not in sorted_rules:
                    sorted_rules.append(rule)

        return sorted_rules

    # ==========================================
    # Excel Function Implementations
    # ==========================================

    @staticmethod
    def _excel_average(values: list) -> float:
        """Excel AVERAGE function"""
        valid = [v for v in values if v is not None and v != '' and v != 0]
        return sum(valid) / len(valid) if valid else 0.0

    @staticmethod
    def _excel_if(condition, true_value, false_value=0):
        """Excel IF function"""
        return true_value if condition else false_value

    @staticmethod
    def _excel_iferror(expression, error_value):
        """Excel IFERROR function"""
        try:
            if expression is None:
                return error_value
            return expression
        except:
            return error_value

    @staticmethod
    def _excel_isblank(value):
        """Excel ISBLANK function"""
        return value in (None, '')

    @staticmethod
    def _excel_mod(number, divisor):
        """Excel MOD function"""
        if divisor == 0:
            return 0
        return number % divisor

    @staticmethod
    def _excel_sign(number):
        """Excel SIGN function"""
        if number > 0:
            return 1
        elif number < 0:
            return -1
        return 0

    @staticmethod
    def _excel_roundup(number, decimals=0):
        """Excel ROUNDUP function"""
        multiplier = 10 ** int(decimals)
        return math.ceil(number * multiplier) / multiplier

    @staticmethod
    def _excel_rounddown(number, decimals=0):
        """Excel ROUNDDOWN function"""
        multiplier = 10 ** int(decimals)
        return math.floor(number * multiplier) / multiplier

    @staticmethod
    def _excel_concat(*args):
        """Excel CONCATENATE function"""
        return ''.join(str(a) for a in args if a is not None)

    @staticmethod
    def _excel_counta(values: list) -> int:
        """Excel COUNTA function - count non-empty values"""
        return len([v for v in values if v is not None and v != ''])

    @staticmethod
    def _excel_vlookup(lookup_value, table: dict, col_index: int, exact_match: bool = True):
        """
        Simplified VLOOKUP for payroll use.

        In payroll context, this typically looks up tax rates or thresholds.

        Args:
            lookup_value: Value to find
            table: Dict of {threshold: result} pairs
            col_index: Not used in simplified version
            exact_match: If True, require exact match

        Returns:
            Matching value or 0 if not found
        """
        if not table:
            return 0

        if exact_match:
            return table.get(lookup_value, 0)
        else:
            # Find largest key <= lookup_value
            keys = sorted(k for k in table.keys() if isinstance(k, (int, float)))
            result = 0
            for key in keys:
                if key <= lookup_value:
                    result = table[key]
                else:
                    break
            return result


class BatchEvaluator:
    """
    Evaluates formulas for multiple employees/records in batch.
    """

    def __init__(self, rules: List[Any]):
        self.rules = rules
        self.evaluator = FormulaEvaluator()
        self._sorted_rules = None

    def evaluate_batch(
        self,
        records: List[Dict[str, float]]
    ) -> List[Dict[str, float]]:
        """
        Evaluate formulas for multiple records.

        Args:
            records: List of input value dicts

        Returns:
            List of result dicts with all computed values
        """
        results = []

        for record in records:
            try:
                result = self.evaluator.evaluate_all(self.rules, record)
                results.append(result)
            except Exception as e:
                _logger.error(f"Batch evaluation error: {e}")
                results.append(record.copy())

        return results

    def evaluate_with_comparison(
        self,
        records: List[Dict[str, float]],
        expected: List[Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate and compare with expected values.

        Args:
            records: List of input value dicts
            expected: List of expected result dicts

        Returns:
            List of comparison results with discrepancies
        """
        computed = self.evaluate_batch(records)
        comparisons = []

        for i, (comp, exp) in enumerate(zip(computed, expected)):
            comparison = {
                'index': i,
                'computed': comp,
                'expected': exp,
                'discrepancies': {},
                'all_passed': True,
            }

            for code in exp:
                exp_val = exp.get(code, 0)
                comp_val = comp.get(code, 0)

                if exp_val != 0:
                    disc = abs(exp_val - comp_val) / abs(exp_val) * 100
                else:
                    disc = 100 if comp_val != 0 else 0

                if disc > 0.01:  # More than 0.01% difference
                    comparison['discrepancies'][code] = {
                        'expected': exp_val,
                        'computed': comp_val,
                        'discrepancy': disc,
                    }
                    comparison['all_passed'] = False

            comparisons.append(comparison)

        return comparisons
