# -*- coding: utf-8 -*-
"""
Formula Converter - Converts Excel formulas to Python code.

Uses the 'formulas' library for robust Excel formula support,
with fallback to custom conversion for unsupported cases.
"""

import re
from typing import Dict, List, Tuple, Optional, Any
import logging

_logger = logging.getLogger(__name__)

# Try to import the formulas library
try:
    import formulas
    from formulas import Parser as FormulasParser
    HAS_FORMULAS_LIB = True
except ImportError:
    HAS_FORMULAS_LIB = False
    _logger.warning("'formulas' library not installed. Using basic formula conversion.")


class FormulaConverter:
    """
    Converts Excel formulas to Python expressions.

    Primary method uses the 'formulas' library for comprehensive
    Excel function support. Falls back to regex-based conversion
    if library is not available.
    """

    # Excel function to Python function mapping
    FUNCTION_MAP = {
        # Math functions
        'SUM': ('sum', 'list'),           # SUM(A1:C1) -> sum([A1, B1, C1])
        'AVERAGE': ('_avg', 'list'),      # AVERAGE(A1:C1) -> _avg([A1, B1, C1])
        'MIN': ('min', 'list'),
        'MAX': ('max', 'list'),
        'ABS': ('abs', 'single'),
        'ROUND': ('round', 'args'),
        'ROUNDUP': ('_roundup', 'args'),
        'ROUNDDOWN': ('_rounddown', 'args'),
        'CEILING': ('math.ceil', 'single'),
        'FLOOR': ('math.floor', 'single'),
        'POWER': ('pow', 'args'),
        'SQRT': ('math.sqrt', 'single'),
        'MOD': ('_mod', 'args'),
        'INT': ('int', 'single'),
        'SIGN': ('_sign', 'single'),

        # Logical functions
        'IF': ('_if', 'args'),
        'ISBLANK': ('_isblank', 'single'),
        'AND': ('all', 'list'),
        'OR': ('any', 'list'),
        'NOT': ('not', 'single'),
        'IFERROR': ('_iferror', 'args'),

        # Comparison (not typically functions, but can appear)
        'TRUE': ('True', 'constant'),
        'FALSE': ('False', 'constant'),

        # Text functions (simplified)
        'CONCATENATE': ('_concat', 'list'),
        'LEN': ('len', 'single'),

        # Counting
        'COUNT': ('len', 'list'),
        'COUNTA': ('_counta', 'list'),
    }

    def __init__(self, column_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize the converter.

        Args:
            column_mapping: Dict mapping column letters to variable names
                           e.g., {'A': 'BASIC', 'B': 'HRA', 'C': 'GROSS'}
        """
        self.column_mapping = column_mapping or {}
        self._parser = None

        if HAS_FORMULAS_LIB:
            try:
                self._parser = FormulasParser()
            except Exception as e:
                _logger.warning(f"Failed to initialize formulas parser: {e}")

    def convert(self, excel_formula: str, column_map: Optional[Dict[str, str]] = None) -> str:
        """
        Convert an Excel formula to Python expression.

        Args:
            excel_formula: Excel formula string (e.g., "=A1+B1*0.08")
            column_map: Optional override for column mapping

        Returns:
            Python expression string
        """
        if not excel_formula:
            return "0"

        # Use provided mapping or instance mapping; keep on self for helper use
        mapping = column_map or self.column_mapping
        self.column_mapping = mapping

        # Remove leading '=' if present
        formula = excel_formula.lstrip('=').strip()

        if not formula:
            return "0"

        # Try using formulas library first
        if HAS_FORMULAS_LIB and self._parser:
            try:
                return self._convert_with_library(formula, mapping)
            except Exception as e:
                _logger.debug(f"Library conversion failed, using fallback: {e}")

        # Fallback to regex-based conversion
        return self._convert_with_regex(formula, mapping)

    def _convert_with_library(self, formula: str, mapping: Dict[str, str]) -> str:
        """
        Convert using the formulas library.

        The library parses and can evaluate Excel formulas.
        We convert its output to our Python expression format.
        """
        # Parse the formula
        func = formulas.Parser().ast(f"={formula}")

        # Get the formula as a Python-like expression
        # The formulas library creates a callable, we need to extract logic
        # For now, fall back to regex since library integration is complex
        return self._convert_with_regex(formula, mapping)

    def _convert_with_regex(self, formula: str, mapping: Dict[str, str]) -> str:
        """
        Convert formula using regex-based approach.

        This handles common Excel patterns and converts them to Python.
        """
        result = formula

        # Step 1: Replace cell references with variable names
        result = self._replace_cell_references(result, mapping)

        # Step 2: Replace Excel functions with Python equivalents
        result = self._replace_functions(result)

        # Step 3: Replace Excel operators
        result = self._replace_operators(result)

        # Step 4: Convert percent literals (e.g., 8% -> 8/100)
        result = re.sub(r'(\d+(?:\.\d+)?)%', r'(\1/100)', result)

        # Step 4: Clean up
        result = self._cleanup(result)

        return result

    def _replace_cell_references(self, formula: str, mapping: Dict[str, str]) -> str:
        """
        Replace Excel cell references with Python variable names.

        Examples:
            A1 -> values['BASIC']
            B2 -> values['HRA']
        """
        def replace_ref(match):
            col_letter = match.group(1).upper()
            # row_num = match.group(2)  # We treat all as row 1

            var_name = mapping.get(col_letter)
            if var_name:
                return f"values['{var_name}']"
            else:
                # Unknown column - return as-is or raise error
                _logger.warning(f"Unknown column reference: {col_letter}")
                return f"values.get('{col_letter}', 0)"

        # Pattern: Column letter(s) followed by row number
        pattern = r'\$?([A-Z]+)\$?(\d+)\b'
        return re.sub(pattern, replace_ref, formula, flags=re.IGNORECASE)

    def _replace_functions(self, formula: str) -> str:
        """
        Replace Excel functions with Python equivalents.
        """
        result = formula

        for excel_func, (python_func, arg_type) in self.FUNCTION_MAP.items():
            # Pattern to match function call
            pattern = rf'\b{excel_func}\s*\('

            if arg_type == 'constant':
                # Replace function name with constant value
                result = re.sub(pattern, python_func, result, flags=re.IGNORECASE)
            elif arg_type == 'single':
                # Single argument function
                result = re.sub(pattern, f'{python_func}(', result, flags=re.IGNORECASE)
            elif arg_type == 'list':
                # List argument function - wrap args in list
                result = self._convert_list_function(result, excel_func, python_func)
            elif arg_type == 'args':
                # Multiple arguments - just rename function
                result = re.sub(pattern, f'{python_func}(', result, flags=re.IGNORECASE)

        return result

    def _convert_list_function(self, formula: str, excel_func: str, python_func: str) -> str:
        """
        Convert functions that take a range and convert to list operations.

        Example: SUM(A1:C1) -> sum([values['A'], values['B'], values['C']])
        Example: SUM(A1,B1,C1) -> sum([values['A'], values['B'], values['C']])
        """
        pattern = rf'\b{excel_func}\s*\(([^)]+)\)'

        def replacer(match):
            args = match.group(1)

            # Check for range notation (A1:C1)
            range_match = re.search(r'\$?([A-Z]+)\$?\d+\s*:\s*\$?([A-Z]+)\$?\d+', args, re.IGNORECASE)
            if range_match:
                # It's a range - expand it
                start_col = range_match.group(1).upper()
                end_col = range_match.group(2).upper()

                from .column_manager import ColumnManager
                start_idx = ColumnManager.letter_to_index(start_col)
                end_idx = ColumnManager.letter_to_index(end_col)

                # Generate list of column references
                cols = []
                for i in range(start_idx, end_idx + 1):
                    letter = ColumnManager.index_to_letter(i)
                    var_name = self.column_mapping.get(letter, letter)
                    cols.append(f"values.get('{var_name}', 0)")

                return f"{python_func}([{', '.join(cols)}])"
            else:
                # Comma-separated values - wrap in list
                return f"{python_func}([{args}])"

        return re.sub(pattern, replacer, formula, flags=re.IGNORECASE)

    def _replace_operators(self, formula: str) -> str:
        """
        Replace Excel operators with Python operators.
        """
        replacements = [
            (r'\^', '**'),           # Exponentiation
            (r'<>', '!='),           # Not equal
            (r'&', '+'),             # String concatenation (simplified)
            (r'(?<![<>=!])=(?!=)', '=='),  # Equality
        ]

        result = formula
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)

        return result

    def _cleanup(self, formula: str) -> str:
        """
        Clean up the converted formula.
        """
        # Remove extra whitespace
        result = ' '.join(formula.split())

        # Ensure balanced parentheses
        open_count = result.count('(')
        close_count = result.count(')')

        if open_count > close_count:
            result += ')' * (open_count - close_count)

        return result

    def validate(self, formula: str) -> Tuple[bool, str]:
        """
        Validate formula syntax.

        Args:
            formula: Excel formula string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not formula:
            return True, ""

        formula = formula.lstrip('=').strip()

        # Basic syntax checks
        errors = []

        # Check parentheses balance
        if formula.count('(') != formula.count(')'):
            errors.append("Unbalanced parentheses")

        # Check for empty function calls
        if re.search(r'\(\s*\)', formula):
            pass  # Empty args are sometimes valid (e.g., NOW())

        # Check for invalid characters
        invalid = re.findall(r'[^\w\s\+\-\*\/\^\(\)\,\.\:\<\>\=\&\"\']', formula)
        if invalid:
            errors.append(f"Invalid characters: {set(invalid)}")

        # Try to convert - if it fails, formula is invalid
        try:
            self.convert(formula)
        except Exception as e:
            errors.append(f"Conversion error: {str(e)}")

        if errors:
            return False, "; ".join(errors)

        return True, ""

    def get_dependencies(self, formula: str) -> List[str]:
        """
        Extract column dependencies from a formula.

        Args:
            formula: Excel formula string

        Returns:
            List of column letters that the formula depends on
        """
        if not formula:
            return []

        # Extract cell references
        pattern = r'\b([A-Z]+)\d+\b'
        refs = re.findall(pattern, formula.upper())

        # Also check for ranges
        range_pattern = r'([A-Z]+)\d+\s*:\s*([A-Z]+)\d+'
        ranges = re.findall(range_pattern, formula.upper())

        for start, end in ranges:
            from .column_manager import ColumnManager
            start_idx = ColumnManager.letter_to_index(start)
            end_idx = ColumnManager.letter_to_index(end)
            for i in range(start_idx, end_idx + 1):
                refs.append(ColumnManager.index_to_letter(i))

        # Return unique, sorted list
        unique_refs = sorted(set(refs), key=lambda x: (len(x), x))
        return unique_refs


# Helper functions for formula evaluation
def _avg(values: list) -> float:
    """Calculate average of a list"""
    valid = [v for v in values if v is not None and v != '']
    return sum(valid) / len(valid) if valid else 0


def _if(condition, true_value, false_value=0):
    """Excel IF function"""
    return true_value if condition else false_value


def _iferror(value, error_value):
    """Excel IFERROR function"""
    try:
        return value
    except:
        return error_value


def _mod(number, divisor):
    """Excel MOD function"""
    return number % divisor


def _sign(number):
    """Excel SIGN function"""
    if number > 0:
        return 1
    elif number < 0:
        return -1
    return 0


def _roundup(number, decimals=0):
    """Excel ROUNDUP function"""
    import math
    multiplier = 10 ** decimals
    return math.ceil(number * multiplier) / multiplier


def _rounddown(number, decimals=0):
    """Excel ROUNDDOWN function"""
    import math
    multiplier = 10 ** decimals
    return math.floor(number * multiplier) / multiplier


def _concat(*args):
    """Excel CONCATENATE function"""
    return ''.join(str(a) for a in args)


def _counta(values: list) -> int:
    """Excel COUNTA function - count non-empty values"""
    return len([v for v in values if v is not None and v != ''])
