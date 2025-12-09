# -*- coding: utf-8 -*-
"""
Formula Validator - Validates Excel formulas for syntax, references, and circular dependencies.
"""

import re
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class FormulaValidator:
    """
    Validates Excel formulas for:
    - Syntax correctness
    - Valid cell/column references
    - Circular dependencies
    - Supported functions
    """

    # Supported Excel functions
    SUPPORTED_FUNCTIONS = {
        'SUM', 'AVERAGE', 'MIN', 'MAX', 'ABS', 'ROUND', 'ROUNDUP', 'ROUNDDOWN',
        'CEILING', 'FLOOR', 'POWER', 'SQRT', 'MOD', 'INT', 'SIGN',
        'IF', 'AND', 'OR', 'NOT', 'TRUE', 'FALSE', 'IFERROR', 'IFS',
        'CONCATENATE', 'LEFT', 'RIGHT', 'MID', 'LEN', 'UPPER', 'LOWER', 'TRIM',
        'VLOOKUP', 'HLOOKUP', 'INDEX', 'MATCH', 'CHOOSE',
        'COUNT', 'COUNTA', 'COUNTIF', 'SUMIF', 'AVERAGEIF',
        'DATE', 'TODAY', 'NOW', 'YEAR', 'MONTH', 'DAY',
    }

    def __init__(self):
        pass

    def validate_formula(
        self,
        formula: str,
        available_columns: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Validate a single formula.

        Args:
            formula: Excel formula string
            available_columns: Dict mapping column letters to codes

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not formula:
            return True, ""

        errors = []

        # Check if formula starts with '='
        if not formula.startswith('='):
            errors.append("Formula must start with '='")
            formula = '=' + formula  # Continue validation anyway

        formula_body = formula[1:].strip()

        if not formula_body:
            return True, ""  # Empty formula is valid

        # Check parentheses balance
        paren_error = self._check_parentheses(formula_body)
        if paren_error:
            errors.append(paren_error)

        # Check for valid characters
        char_error = self._check_characters(formula_body)
        if char_error:
            errors.append(char_error)

        # Check column references
        if available_columns:
            ref_errors = self._check_references(formula_body, available_columns)
            errors.extend(ref_errors)

        # Check function names
        func_errors = self._check_functions(formula_body)
        errors.extend(func_errors)

        # Check for common errors
        common_errors = self._check_common_errors(formula_body)
        errors.extend(common_errors)

        if errors:
            return False, "; ".join(errors)

        return True, ""

    def _check_parentheses(self, formula: str) -> Optional[str]:
        """Check for balanced parentheses"""
        count = 0
        for i, char in enumerate(formula):
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
            if count < 0:
                return f"Unexpected ')' at position {i+1}"

        if count > 0:
            return f"Missing {count} closing parenthesis(es)"

        return None

    def _check_characters(self, formula: str) -> Optional[str]:
        """Check for invalid characters"""
        # Valid characters in Excel formulas
        valid_pattern = r'^[\w\s\+\-\*\/\^\(\)\,\.\:\<\>\=\&\"\'\!\$\%]+$'

        if not re.match(valid_pattern, formula):
            # Find invalid characters
            invalid = set()
            for char in formula:
                if not re.match(r'[\w\s\+\-\*\/\^\(\)\,\.\:\<\>\=\&\"\'\!\$\%]', char):
                    invalid.add(char)
            return f"Invalid characters: {invalid}"

        return None

    def _check_references(
        self,
        formula: str,
        available_columns: Dict[str, str]
    ) -> List[str]:
        """Check that all cell references are valid"""
        errors = []

        # Extract cell references
        pattern = r'\b([A-Z]+)(\d+)\b'
        matches = re.findall(pattern, formula.upper())

        for col, row in matches:
            if col not in available_columns:
                errors.append(f"Unknown column reference: {col}")

        return errors

    def _check_functions(self, formula: str) -> List[str]:
        """Check that all functions are supported"""
        errors = []

        # Find function calls (word followed by open paren)
        pattern = r'\b([A-Z_][A-Z0-9_]*)\s*\('
        matches = re.findall(pattern, formula.upper())

        for func_name in matches:
            if func_name not in self.SUPPORTED_FUNCTIONS:
                errors.append(f"Unsupported function: {func_name}")

        return errors

    def _check_common_errors(self, formula: str) -> List[str]:
        """Check for common formula errors"""
        errors = []

        # Check for double operators
        if re.search(r'[\+\-\*\/\^]{2,}', formula):
            errors.append("Consecutive operators found")

        # Check for operator at end (except closing paren)
        if re.search(r'[\+\-\*\/\^]\s*$', formula):
            errors.append("Formula ends with an operator")

        # Check for empty parentheses (except for some functions like NOW())
        empty_parens = re.findall(r'(\w*)\(\s*\)', formula)
        for func in empty_parens:
            if func.upper() not in ('NOW', 'TODAY', 'TRUE', 'FALSE'):
                errors.append(f"Empty parentheses after '{func or 'expression'}'")

        return errors

    def check_circular_references(self, rules: List[Any]) -> Set[str]:
        """
        Check for circular references among formula rules.

        Uses DFS to detect cycles in the dependency graph.

        Args:
            rules: List of formula rule objects with:
                   - code: Rule code
                   - column_letter: Excel column letter
                   - formula_dependencies: Comma-separated dependency letters

        Returns:
            Set of rule codes that are part of circular references
        """
        # Build dependency graph
        letter_to_code = {r.column_letter: r.code for r in rules if r.column_letter}
        code_to_letter = {r.code: r.column_letter for r in rules if r.column_letter}

        # Graph: code -> list of dependency codes
        graph = defaultdict(list)

        for rule in rules:
            if not hasattr(rule, 'column_type') or rule.column_type != 'formula':
                continue

            deps = getattr(rule, 'formula_dependencies', '')
            if not deps:
                continue

            for dep_letter in deps.split(','):
                dep_letter = dep_letter.strip()
                if dep_letter in letter_to_code:
                    dep_code = letter_to_code[dep_letter]
                    graph[rule.code].append(dep_code)

        # DFS to find cycles
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {r.code: WHITE for r in rules}
        in_cycle = set()

        def dfs(node, path):
            color[node] = GRAY
            path.append(node)

            for neighbor in graph[node]:
                if color.get(neighbor, WHITE) == GRAY:
                    # Found cycle - mark all nodes in path from neighbor
                    cycle_start = path.index(neighbor)
                    in_cycle.update(path[cycle_start:])
                elif color.get(neighbor, WHITE) == WHITE:
                    dfs(neighbor, path)

            path.pop()
            color[node] = BLACK

        for rule in rules:
            if color.get(rule.code, WHITE) == WHITE:
                dfs(rule.code, [])

        return in_cycle

    def check_self_reference(self, rule: Any) -> bool:
        """
        Check if a rule references itself.

        Args:
            rule: Formula rule object

        Returns:
            True if self-reference detected
        """
        if not hasattr(rule, 'column_letter') or not rule.column_letter:
            return False

        deps = getattr(rule, 'formula_dependencies', '')
        if not deps:
            return False

        dep_letters = [d.strip() for d in deps.split(',')]
        return rule.column_letter in dep_letters

    def validate_all(
        self,
        rules: List[Any],
        available_columns: Optional[Dict[str, str]] = None
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Validate all formula rules.

        Args:
            rules: List of formula rule objects
            available_columns: Dict mapping column letters to codes

        Returns:
            Dict mapping rule codes to (is_valid, error_message) tuples
        """
        # Build column mapping if not provided
        if available_columns is None:
            available_columns = {
                r.column_letter: r.code
                for r in rules
                if r.column_letter
            }

        results = {}

        # Check each formula
        for rule in rules:
            code = rule.code
            formula = getattr(rule, 'excel_formula', '')

            if not formula or getattr(rule, 'column_type', '') != 'formula':
                results[code] = (True, "")
                continue

            is_valid, error = self.validate_formula(formula, available_columns)

            # Check self-reference
            if self.check_self_reference(rule):
                is_valid = False
                error = (error + "; " if error else "") + "Self-reference detected"

            results[code] = (is_valid, error)

        # Check circular references
        circular = self.check_circular_references(rules)
        for code in circular:
            if code in results:
                is_valid, error = results[code]
                results[code] = (
                    False,
                    (error + "; " if error else "") + "Part of circular reference"
                )

        return results

    def get_dependency_order(self, rules: List[Any]) -> List[str]:
        """
        Get rules in dependency order (dependencies first).

        Args:
            rules: List of formula rule objects

        Returns:
            List of rule codes in evaluation order
        """
        letter_to_code = {r.column_letter: r.code for r in rules if r.column_letter}

        # Build adjacency list (reverse of dependency graph)
        # If A depends on B, we want B before A
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for rule in rules:
            code = rule.code
            in_degree[code]  # Ensure all codes are in dict

            if getattr(rule, 'column_type', '') != 'formula':
                continue

            deps = getattr(rule, 'formula_dependencies', '')
            for dep_letter in deps.split(','):
                dep_letter = dep_letter.strip()
                if dep_letter in letter_to_code:
                    dep_code = letter_to_code[dep_letter]
                    graph[dep_code].append(code)
                    in_degree[code] += 1

        # Topological sort using Kahn's algorithm
        result = []
        queue = [code for code, degree in in_degree.items() if degree == 0]

        while queue:
            code = queue.pop(0)
            result.append(code)

            for dependent in graph[code]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Add any remaining (circular deps) at end
        for rule in rules:
            if rule.code not in result:
                result.append(rule.code)

        return result
