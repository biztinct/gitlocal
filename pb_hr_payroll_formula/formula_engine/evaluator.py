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
            '_sumif': self._excel_sumif,
            '_sumifs': self._excel_sumifs,
            '_row': self._excel_row,
            '_subtotal': self._excel_subtotal,
            'SUMIF': self._excel_sumif,  # Direct function name for unconverted formulas
            'SUMIFS': self._excel_sumifs,  # Direct function name for unconverted formulas
            'ROW': self._excel_row,  # Direct function name for unconverted formulas
            'SUBTOTAL': self._excel_subtotal,  # Direct function name for unconverted formulas
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
            # Note: context parameter contains the values dict, we need to sanitize it
            safe_context["raw_values"] = context
            safe_context["values"] = {
                k: (0 if v is None else v) for k, v in context.items()
            }

            result = eval(python_formula, {"__builtins__": {}}, safe_context)
            if result is None:
                return 0.0
            if isinstance(result, str):
                return result
            if isinstance(result, bool):
                return float(result)
            if isinstance(result, (int, float)):
                return float(result)
            try:
                return float(result)
            except (TypeError, ValueError):
                return result

        except ZeroDivisionError:
            _logger.warning(f"Division by zero in formula: {python_formula}")
            return 0.0

        except Exception as e:
            if '"' in python_formula or "raw_values" in python_formula:
                try:
                    import re
                    keys = re.findall(r"(?:values|raw_values)\.get\('([^']+)'", python_formula)
                    key_values = {k: context.get(k) for k in keys}
                except Exception:
                    keys = []
                    key_values = {}
                _logger.info(
                    "Formula eval error: formula=%s keys=%s context=%s error=%s",
                    python_formula,
                    keys,
                    key_values,
                    e,
                )
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
            'raw_values': values,

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
                    for dep_ref in deps.split(','):
                        dep_ref = dep_ref.strip()
                        if not dep_ref:
                            continue

                        # Find rule with this column letter OR code
                        # Try matching by column_letter first, then by code
                        found = False
                        for r in rules:
                            if getattr(r, 'column_letter', '') == dep_ref:
                                dependencies[rule.code].add(r.code)
                                dependents[r.code].add(rule.code)
                                found = True
                                break

                        # If not found by column_letter, try matching by code
                        if not found:
                            for r in rules:
                                if getattr(r, 'code', '') == dep_ref:
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
        """Excel IFERROR function

        Note: In Python, arguments are evaluated before the function is called,
        so we can't catch evaluation errors here. Instead, we check for error
        indicators like None, empty string, NaN, or Inf.
        """
        # Check if expression is an error indicator
        if expression is None or expression == '':
            return error_value

        # Check if expression is NaN or Inf (common error values)
        try:
            import math
            if isinstance(expression, float) and (math.isnan(expression) or math.isinf(expression)):
                return error_value
        except:
            pass

        return expression

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

    @staticmethod
    def _excel_sumif(range_val, criteria, sum_range=None):
        """
        Simplified SUMIF for payroll use.

        In the payroll context where formulas are evaluated per-employee row,
        SUMIF is simplified: if the criteria matches the range value, return
        the sum_range value (or range_val if sum_range not provided).

        This handles the common pattern:
        SUMIF(EmpCodeColumn, CurrentEmpCode, AmountColumn)
        -> If EmpCodeColumn == CurrentEmpCode, return AmountColumn value

        Args:
            range_val: Value from the range column (criteria column)
            criteria: The value to match against
            sum_range: Value to return if match (optional, defaults to range_val)

        Returns:
            sum_range if criteria matches range_val, else 0
        """
        # Handle None values
        if range_val is None or criteria is None:
            return 0

        # Convert to comparable types
        try:
            # Try numeric comparison first
            if isinstance(range_val, (int, float)) and isinstance(criteria, (int, float)):
                if range_val == criteria:
                    return float(sum_range) if sum_range is not None else float(range_val)
            # String comparison
            elif str(range_val).strip().lower() == str(criteria).strip().lower():
                if sum_range is not None:
                    try:
                        return float(sum_range)
                    except (ValueError, TypeError):
                        return 0
                return float(range_val) if isinstance(range_val, (int, float)) else 0
        except Exception:
            pass

        return 0

    @staticmethod
    def _excel_sumifs(sum_range, *criteria_pairs):
        """
        Simplified SUMIFS for payroll use.

        Similar to SUMIF but with multiple criteria pairs.

        Args:
            sum_range: Value to return if all criteria match
            *criteria_pairs: Pairs of (range_val, criteria) to check

        Returns:
            sum_range if all criteria match, else 0
        """
        if sum_range is None:
            return 0

        # Process criteria pairs
        for i in range(0, len(criteria_pairs), 2):
            if i + 1 >= len(criteria_pairs):
                break
            range_val = criteria_pairs[i]
            criteria = criteria_pairs[i + 1]

            if range_val is None or criteria is None:
                return 0

            # Check if criteria matches
            try:
                if isinstance(range_val, (int, float)) and isinstance(criteria, (int, float)):
                    if range_val != criteria:
                        return 0
                elif str(range_val).strip().lower() != str(criteria).strip().lower():
                    return 0
            except Exception:
                return 0

        # All criteria matched
        try:
            return float(sum_range)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _excel_row(reference=None):
        """
        Excel ROW function.

        In the payroll context where formulas are evaluated per-employee row,
        ROW() typically returns the current row being processed.

        For simplicity in payroll evaluation, we return 1 (or the row if provided).

        Args:
            reference: Optional cell reference (not used in simplified version)

        Returns:
            Row number (defaults to 1 for payroll context)
        """
        if reference is not None:
            # If a row number or reference is provided, try to extract row
            if isinstance(reference, (int, float)):
                return int(reference)
            if isinstance(reference, str):
                # Try to extract row number from cell reference like "A5"
                import re
                match = re.search(r'(\d+)', str(reference))
                if match:
                    return int(match.group(1))
        # Default to row 1 for payroll evaluation context
        return 1

    @staticmethod
    def _excel_subtotal(function_num, *args):
        """
        Excel SUBTOTAL function.

        SUBTOTAL(function_num, ref1, [ref2], ...) performs calculations
        based on the function_num:

        Function numbers (ignore hidden values):
        1 or 101 = AVERAGE
        2 or 102 = COUNT
        3 or 103 = COUNTA
        4 or 104 = MAX
        5 or 105 = MIN
        6 or 106 = PRODUCT
        7 or 107 = STDEV
        8 or 108 = STDEVP
        9 or 109 = SUM
        10 or 110 = VAR
        11 or 111 = VARP

        Args:
            function_num: Number indicating which function to use
            *args: Values to include in the calculation

        Returns:
            Result of the specified function
        """
        if not args:
            return 0

        # Flatten and filter values
        values = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                values.extend([v for v in arg if v is not None and v != ''])
            elif arg is not None and arg != '':
                values.append(arg)

        # Convert to numbers where possible
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass

        if not numeric_values:
            return 0

        # Map function number to operation (both regular and "ignore hidden" versions)
        func_num = int(function_num) % 100 if function_num >= 100 else int(function_num)

        try:
            if func_num == 1:  # AVERAGE
                return sum(numeric_values) / len(numeric_values) if numeric_values else 0
            elif func_num == 2:  # COUNT (count numbers only)
                return len(numeric_values)
            elif func_num == 3:  # COUNTA (count non-empty)
                return len(values)
            elif func_num == 4:  # MAX
                return max(numeric_values) if numeric_values else 0
            elif func_num == 5:  # MIN
                return min(numeric_values) if numeric_values else 0
            elif func_num == 6:  # PRODUCT
                result = 1
                for v in numeric_values:
                    result *= v
                return result
            elif func_num == 9:  # SUM
                return sum(numeric_values)
            else:
                # Unsupported function number, default to SUM
                _logger.warning(f"SUBTOTAL function_num {function_num} not fully supported, using SUM")
                return sum(numeric_values)
        except Exception as e:
            _logger.warning(f"SUBTOTAL calculation error: {e}")
            return 0


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
