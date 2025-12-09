# -*- coding: utf-8 -*-
"""
Formula Parser - Parses Excel formulas into an abstract syntax tree.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

_logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Types of tokens in an Excel formula"""
    NUMBER = 'NUMBER'
    STRING = 'STRING'
    CELL_REF = 'CELL_REF'
    RANGE_REF = 'RANGE_REF'
    FUNCTION = 'FUNCTION'
    OPERATOR = 'OPERATOR'
    LPAREN = 'LPAREN'
    RPAREN = 'RPAREN'
    COMMA = 'COMMA'
    COLON = 'COLON'
    EQUALS = 'EQUALS'
    COMPARISON = 'COMPARISON'
    BOOLEAN = 'BOOLEAN'


@dataclass
class Token:
    """Represents a token in the formula"""
    type: TokenType
    value: Any
    position: int


@dataclass
class ASTNode:
    """Abstract Syntax Tree node"""
    type: str
    value: Any = None
    children: List['ASTNode'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class FormulaParser:
    """
    Parser for Excel formulas.

    Converts formula strings into an abstract syntax tree (AST)
    that can be analyzed or converted to Python code.

    Supported elements:
    - Cell references (A1, B2, AA100)
    - Range references (A1:B10)
    - Numbers (integers and decimals)
    - Strings ("text")
    - Functions (SUM, IF, ROUND, etc.)
    - Operators (+, -, *, /, ^, &)
    - Comparisons (=, <, >, <=, >=, <>)
    - Parentheses
    - Booleans (TRUE, FALSE)
    """

    # Supported Excel functions
    SUPPORTED_FUNCTIONS = {
        # Math functions
        'SUM', 'AVERAGE', 'MIN', 'MAX', 'ABS', 'ROUND', 'ROUNDUP', 'ROUNDDOWN',
        'CEILING', 'FLOOR', 'POWER', 'SQRT', 'MOD', 'INT', 'SIGN',

        # Logical functions
        'IF', 'AND', 'OR', 'NOT', 'TRUE', 'FALSE', 'IFERROR', 'IFS',

        # Text functions
        'CONCATENATE', 'LEFT', 'RIGHT', 'MID', 'LEN', 'UPPER', 'LOWER', 'TRIM',

        # Lookup functions
        'VLOOKUP', 'HLOOKUP', 'INDEX', 'MATCH', 'CHOOSE',

        # Statistical functions
        'COUNT', 'COUNTA', 'COUNTIF', 'SUMIF', 'AVERAGEIF',

        # Date functions
        'DATE', 'TODAY', 'NOW', 'YEAR', 'MONTH', 'DAY',
    }

    # Operator precedence (higher = binds tighter)
    OPERATOR_PRECEDENCE = {
        '^': 4,   # Exponentiation
        '*': 3,   # Multiplication
        '/': 3,   # Division
        '+': 2,   # Addition
        '-': 2,   # Subtraction
        '&': 1,   # Concatenation
        '=': 0,   # Comparison
        '<': 0,
        '>': 0,
        '<=': 0,
        '>=': 0,
        '<>': 0,
    }

    def __init__(self):
        self.tokens: List[Token] = []
        self.position: int = 0
        self.formula: str = ""

    def parse(self, formula: str) -> ASTNode:
        """
        Parse an Excel formula into an AST.

        Args:
            formula: Excel formula string (with or without leading '=')

        Returns:
            Root node of the AST
        """
        # Remove leading '=' if present
        self.formula = formula.lstrip('=').strip()
        if not self.formula:
            return ASTNode(type='empty')

        # Tokenize
        self.tokens = self._tokenize(self.formula)
        self.position = 0

        # Parse expression
        return self._parse_expression()

    def _tokenize(self, formula: str) -> List[Token]:
        """Convert formula string into a list of tokens"""
        tokens = []
        pos = 0

        while pos < len(formula):
            char = formula[pos]

            # Skip whitespace
            if char.isspace():
                pos += 1
                continue

            # String literal
            if char == '"':
                end = formula.find('"', pos + 1)
                if end == -1:
                    raise ValueError(f"Unterminated string at position {pos}")
                tokens.append(Token(TokenType.STRING, formula[pos+1:end], pos))
                pos = end + 1
                continue

            # Number
            if char.isdigit() or (char == '.' and pos + 1 < len(formula) and formula[pos + 1].isdigit()):
                match = re.match(r'[\d.]+', formula[pos:])
                if match:
                    value = match.group()
                    tokens.append(Token(TokenType.NUMBER, float(value), pos))
                    pos += len(value)
                    continue

            # Cell reference or function
            if char.isalpha() or char == '_':
                match = re.match(r'[A-Za-z_][A-Za-z0-9_]*', formula[pos:])
                if match:
                    value = match.group().upper()

                    # Check if it's a boolean
                    if value in ('TRUE', 'FALSE'):
                        tokens.append(Token(TokenType.BOOLEAN, value == 'TRUE', pos))
                    # Check if followed by '(' (function)
                    elif pos + len(value) < len(formula) and formula[pos + len(value)] == '(':
                        tokens.append(Token(TokenType.FUNCTION, value, pos))
                    # Check if it's a cell reference (letters followed by digits)
                    elif re.match(r'^[A-Z]+$', value):
                        # Look ahead for digits
                        rest = formula[pos + len(value):]
                        digit_match = re.match(r'\d+', rest)
                        if digit_match:
                            cell_ref = value + digit_match.group()
                            tokens.append(Token(TokenType.CELL_REF, cell_ref, pos))
                            pos += len(cell_ref)
                            continue
                        else:
                            # Just letters - could be a named range or error
                            tokens.append(Token(TokenType.CELL_REF, value + '1', pos))
                    else:
                        # Named reference or function without parens
                        tokens.append(Token(TokenType.CELL_REF, value, pos))

                    pos += len(value)
                    continue

            # Comparison operators (must check before single char operators)
            if formula[pos:pos+2] in ('<=', '>=', '<>'):
                tokens.append(Token(TokenType.COMPARISON, formula[pos:pos+2], pos))
                pos += 2
                continue

            # Single character tokens
            if char == '(':
                tokens.append(Token(TokenType.LPAREN, '(', pos))
            elif char == ')':
                tokens.append(Token(TokenType.RPAREN, ')', pos))
            elif char == ',':
                tokens.append(Token(TokenType.COMMA, ',', pos))
            elif char == ':':
                tokens.append(Token(TokenType.COLON, ':', pos))
            elif char in '+-*/^&':
                tokens.append(Token(TokenType.OPERATOR, char, pos))
            elif char in '<>=':
                tokens.append(Token(TokenType.COMPARISON, char, pos))
            else:
                raise ValueError(f"Unexpected character '{char}' at position {pos}")

            pos += 1

        return tokens

    def _current_token(self) -> Optional[Token]:
        """Get current token without advancing"""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def _advance(self) -> Optional[Token]:
        """Get current token and advance position"""
        token = self._current_token()
        self.position += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        """Expect and consume a token of the given type"""
        token = self._advance()
        if not token or token.type != token_type:
            expected = token_type.value
            actual = token.type.value if token else 'EOF'
            raise ValueError(f"Expected {expected}, got {actual}")
        return token

    def _parse_expression(self, min_precedence: int = 0) -> ASTNode:
        """Parse an expression using precedence climbing"""
        left = self._parse_primary()

        while True:
            token = self._current_token()
            if not token:
                break

            if token.type not in (TokenType.OPERATOR, TokenType.COMPARISON):
                break

            precedence = self.OPERATOR_PRECEDENCE.get(token.value, -1)
            if precedence < min_precedence:
                break

            operator = self._advance()
            right = self._parse_expression(precedence + 1)

            left = ASTNode(
                type='binary_op',
                value=operator.value,
                children=[left, right]
            )

        return left

    def _parse_primary(self) -> ASTNode:
        """Parse a primary expression (number, cell, function, parenthesized expr)"""
        token = self._current_token()

        if not token:
            raise ValueError("Unexpected end of formula")

        # Unary minus
        if token.type == TokenType.OPERATOR and token.value == '-':
            self._advance()
            operand = self._parse_primary()
            return ASTNode(type='unary_op', value='-', children=[operand])

        # Number
        if token.type == TokenType.NUMBER:
            self._advance()
            return ASTNode(type='number', value=token.value)

        # String
        if token.type == TokenType.STRING:
            self._advance()
            return ASTNode(type='string', value=token.value)

        # Boolean
        if token.type == TokenType.BOOLEAN:
            self._advance()
            return ASTNode(type='boolean', value=token.value)

        # Cell reference (possibly range)
        if token.type == TokenType.CELL_REF:
            self._advance()

            # Check for range
            if self._current_token() and self._current_token().type == TokenType.COLON:
                self._advance()  # consume ':'
                end_token = self._expect(TokenType.CELL_REF)
                return ASTNode(
                    type='range_ref',
                    value=(token.value, end_token.value)
                )

            return ASTNode(type='cell_ref', value=token.value)

        # Function call
        if token.type == TokenType.FUNCTION:
            return self._parse_function()

        # Parenthesized expression
        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        raise ValueError(f"Unexpected token: {token.type.value} '{token.value}'")

    def _parse_function(self) -> ASTNode:
        """Parse a function call"""
        func_token = self._advance()
        func_name = func_token.value

        self._expect(TokenType.LPAREN)

        args = []
        while True:
            token = self._current_token()
            if not token or token.type == TokenType.RPAREN:
                break

            args.append(self._parse_expression())

            token = self._current_token()
            if token and token.type == TokenType.COMMA:
                self._advance()
            else:
                break

        self._expect(TokenType.RPAREN)

        return ASTNode(type='function', value=func_name, children=args)

    def validate(self, formula: str) -> Tuple[bool, str]:
        """
        Validate a formula for syntax errors.

        Args:
            formula: Excel formula string

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.parse(formula)
            return True, ""
        except Exception as e:
            return False, str(e)

    def get_cell_references(self, formula: str) -> List[str]:
        """
        Extract all cell references from a formula.

        Args:
            formula: Excel formula string

        Returns:
            List of cell references (e.g., ['A1', 'B2', 'C3'])
        """
        try:
            ast = self.parse(formula)
            return self._collect_cell_refs(ast)
        except Exception:
            return []

    def _collect_cell_refs(self, node: ASTNode) -> List[str]:
        """Recursively collect cell references from AST"""
        refs = []

        if node.type == 'cell_ref':
            refs.append(node.value)
        elif node.type == 'range_ref':
            # Expand range to individual cells would be done here
            refs.extend(node.value)

        for child in node.children:
            refs.extend(self._collect_cell_refs(child))

        return refs

    def get_functions_used(self, formula: str) -> List[str]:
        """
        Get list of functions used in a formula.

        Args:
            formula: Excel formula string

        Returns:
            List of function names
        """
        try:
            ast = self.parse(formula)
            return self._collect_functions(ast)
        except Exception:
            return []

    def _collect_functions(self, node: ASTNode) -> List[str]:
        """Recursively collect function names from AST"""
        funcs = []

        if node.type == 'function':
            funcs.append(node.value)

        for child in node.children:
            funcs.extend(self._collect_functions(child))

        return funcs
