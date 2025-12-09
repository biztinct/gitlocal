# -*- coding: utf-8 -*-
"""
Column Manager - Manages Excel-style column letters (A, B, C...Z, AA, AB, etc.)
"""

import re
from typing import List, Dict, Tuple, Optional


class ColumnManager:
    """
    Manages Excel-style column letter operations.

    Supports:
    - Converting between column indices and letters
    - Updating formula references when columns are reordered
    - Generating column letter sequences
    """

    @staticmethod
    def index_to_letter(index: int) -> str:
        """
        Convert a 0-based column index to an Excel-style column letter.

        Examples:
            0 -> 'A'
            25 -> 'Z'
            26 -> 'AA'
            27 -> 'AB'
            702 -> 'AAA'

        Args:
            index: 0-based column index

        Returns:
            Column letter string
        """
        if index < 0:
            raise ValueError("Column index must be non-negative")

        result = ""
        temp = index

        while temp >= 0:
            result = chr(temp % 26 + ord('A')) + result
            temp = temp // 26 - 1

        return result

    @staticmethod
    def letter_to_index(letter: str) -> int:
        """
        Convert an Excel-style column letter to a 0-based index.

        Examples:
            'A' -> 0
            'Z' -> 25
            'AA' -> 26
            'AB' -> 27
            'AAA' -> 702

        Args:
            letter: Column letter string (case-insensitive)

        Returns:
            0-based column index
        """
        if not letter or not letter.isalpha():
            raise ValueError(f"Invalid column letter: {letter}")

        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)

        return result - 1

    @staticmethod
    def get_column_range(start: int, count: int) -> List[str]:
        """
        Generate a list of column letters starting from a given index.

        Args:
            start: Starting column index (0-based)
            count: Number of columns to generate

        Returns:
            List of column letters
        """
        return [ColumnManager.index_to_letter(i) for i in range(start, start + count)]

    @staticmethod
    def get_next_letter(current: str) -> str:
        """
        Get the next column letter after the given one.

        Examples:
            'A' -> 'B'
            'Z' -> 'AA'
            'AZ' -> 'BA'

        Args:
            current: Current column letter

        Returns:
            Next column letter
        """
        index = ColumnManager.letter_to_index(current)
        return ColumnManager.index_to_letter(index + 1)

    @staticmethod
    def get_previous_letter(current: str) -> Optional[str]:
        """
        Get the previous column letter before the given one.

        Args:
            current: Current column letter

        Returns:
            Previous column letter, or None if current is 'A'
        """
        index = ColumnManager.letter_to_index(current)
        if index == 0:
            return None
        return ColumnManager.index_to_letter(index - 1)

    @staticmethod
    def extract_cell_references(formula: str) -> List[Tuple[str, str]]:
        """
        Extract all cell references from a formula.

        A cell reference is a column letter followed by a row number.
        Examples: A1, B2, AA15, ZZ100

        Args:
            formula: Excel formula string

        Returns:
            List of tuples (column_letter, row_number)
        """
        if not formula:
            return []

        # Pattern: One or more letters followed by one or more digits
        pattern = r'([A-Za-z]+)(\d+)'
        matches = re.findall(pattern, formula)

        return [(col.upper(), row) for col, row in matches]

    @staticmethod
    def extract_column_references(formula: str) -> List[str]:
        """
        Extract unique column letters from formula references.

        Args:
            formula: Excel formula string

        Returns:
            List of unique column letters (sorted)
        """
        refs = ColumnManager.extract_cell_references(formula)
        columns = list(set(col for col, row in refs))
        # Sort by column index
        columns.sort(key=lambda c: ColumnManager.letter_to_index(c))
        return columns

    @staticmethod
    def update_formula_reference(
        formula: str,
        old_letter: str,
        new_letter: str
    ) -> str:
        """
        Update a single column reference in a formula.

        Args:
            formula: Original formula
            old_letter: Column letter to replace
            new_letter: New column letter

        Returns:
            Updated formula
        """
        if not formula or not old_letter or not new_letter:
            return formula

        # Pattern to match the column letter followed by a number
        # Use word boundary to avoid partial matches
        pattern = rf'\b{old_letter.upper()}(\d+)\b'
        replacement = f'{new_letter.upper()}\\1'

        return re.sub(pattern, replacement, formula, flags=re.IGNORECASE)

    @staticmethod
    def update_all_formula_references(
        formula: str,
        mapping: Dict[str, str]
    ) -> str:
        """
        Update multiple column references in a formula.

        To avoid conflicts during replacement (e.g., A->B and B->C),
        we use a two-pass approach with temporary placeholders.

        Args:
            formula: Original formula
            mapping: Dictionary mapping old letters to new letters

        Returns:
            Updated formula
        """
        if not formula or not mapping:
            return formula

        result = formula

        # First pass: Replace with temporary placeholders
        temp_map = {}
        for i, (old, new) in enumerate(mapping.items()):
            placeholder = f'__COL_{i}__'
            temp_map[placeholder] = new
            pattern = rf'\b{old.upper()}(\d+)\b'
            result = re.sub(
                pattern,
                f'{placeholder}\\1',
                result,
                flags=re.IGNORECASE
            )

        # Second pass: Replace placeholders with actual values
        for placeholder, new in temp_map.items():
            result = result.replace(placeholder, new.upper())

        return result

    @staticmethod
    def shift_references(
        formula: str,
        shift_amount: int,
        after_column: Optional[str] = None
    ) -> str:
        """
        Shift all column references in a formula by a given amount.

        Used when inserting/deleting columns.

        Args:
            formula: Original formula
            shift_amount: Number of positions to shift (positive=right, negative=left)
            after_column: Only shift columns after this one (optional)

        Returns:
            Updated formula
        """
        if not formula or shift_amount == 0:
            return formula

        after_index = -1
        if after_column:
            after_index = ColumnManager.letter_to_index(after_column)

        refs = ColumnManager.extract_cell_references(formula)
        mapping = {}

        for col, row in refs:
            col_index = ColumnManager.letter_to_index(col)
            if col_index > after_index:
                new_index = max(0, col_index + shift_amount)
                new_col = ColumnManager.index_to_letter(new_index)
                if col != new_col:
                    mapping[col] = new_col

        return ColumnManager.update_all_formula_references(formula, mapping)

    @staticmethod
    def validate_column_letter(letter: str) -> bool:
        """
        Validate that a string is a valid Excel column letter.

        Args:
            letter: String to validate

        Returns:
            True if valid column letter, False otherwise
        """
        if not letter or not isinstance(letter, str):
            return False

        return bool(re.match(r'^[A-Za-z]+$', letter))

    @staticmethod
    def compare_columns(letter1: str, letter2: str) -> int:
        """
        Compare two column letters.

        Args:
            letter1: First column letter
            letter2: Second column letter

        Returns:
            -1 if letter1 < letter2
            0 if letter1 == letter2
            1 if letter1 > letter2
        """
        idx1 = ColumnManager.letter_to_index(letter1)
        idx2 = ColumnManager.letter_to_index(letter2)

        if idx1 < idx2:
            return -1
        elif idx1 > idx2:
            return 1
        else:
            return 0


# Convenience functions for use without class instantiation
def index_to_letter(index: int) -> str:
    return ColumnManager.index_to_letter(index)


def letter_to_index(letter: str) -> int:
    return ColumnManager.letter_to_index(letter)


def update_formula_references(formula: str, mapping: Dict[str, str]) -> str:
    return ColumnManager.update_all_formula_references(formula, mapping)
