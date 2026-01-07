# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re
import logging

_logger = logging.getLogger(__name__)


class HrFormulaRule(models.Model):
    """
    Excel Formula Salary Rule - Individual formula-based salary component
    with Excel-like column letters and formula support.
    """
    _name = 'hr.formula.rule'
    _description = 'Excel Formula Salary Rule'
    _order = 'sequence, id'
    _rec_name = 'display_name'

    # ==========================================
    # LINK TO CONFIG
    # ==========================================
    config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        ondelete='cascade',
        index=True
    )

    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Linked Salary Rule',
        help="Optional link to standard Odoo salary rule"
    )

    company_id = fields.Many2one(
        related='config_id.company_id',
        store=True
    )

    currency_id = fields.Many2one(
        related='config_id.currency_id',
        store=True
    )

    # ==========================================
    # COLUMN IDENTITY
    # ==========================================
    column_letter = fields.Char(
        string='Column Letter',
        compute='_compute_column_letter',
        inverse='_inverse_column_letter',
        store=True,
        help="Excel-style column letter (A, B, C...Z, AA, AB, etc.)"
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Determines column order. Lower numbers appear first (left)."
    )

    # ==========================================
    # RULE DEFINITION
    # ==========================================
    name = fields.Char(
        string='Label/Name',
        required=True,
        help="Display name shown in column header"
    )

    code = fields.Char(
        string='Code',
        required=True,
        help="Unique code for this rule (e.g., BASIC, HRA, PIT)"
    )

    category_id = fields.Many2one(
        'hr.salary.rule.category',
        string='Category',
        help="Salary rule category for grouping"
    )

    payslip_identifier = fields.Many2one(
        'hr.payslip.config',
        string='Payslip Identifier',
        help="Grouping identifier for payslip and reporting."
    )

    # ==========================================
    # COLUMN TYPE
    # ==========================================
    column_type = fields.Selection([
        ('input', 'Input (from data source)'),
        ('formula', 'Calculated (formula)'),
        ('constant', 'Constant Value')
    ], string='Column Type', default='formula', required=True,
       help="""
       - Input: Values come from external data source (Zoho, Excel, etc.)
       - Formula: Calculated using Excel formula
       - Constant: Fixed value for all employees
       """)

    # ==========================================
    # COMPONENT TYPE & DATA SOURCE (Multi-Sheet Import)
    # ==========================================
    component_type = fields.Char(
        string='Component Type',
        help="Category from merged cell above column header (e.g., 'Deductions', 'Allowances', 'Earnings'). "
             "Extracted during multi-worksheet import from merged cells spanning the column."
    )

    data_source = fields.Selection([
        ('excel', 'Excel Import'),
        ('integration', 'Integration Connector'),
        ('formula', 'Calculated (Formula)'),
        ('manual', 'Manual Entry'),
        ('none', 'Not Populated'),
    ], string='Data Source', default='excel',
       help="Where this component's data comes from during payroll import:\n"
            "- Excel Import: Data comes from the primary Excel file\n"
            "- Integration Connector: Data fetched from external system (Zoho, SAP, etc.)\n"
            "- Calculated: Computed from other fields using formula\n"
            "- Manual Entry: User enters value manually\n"
            "- Not Populated: Field exists but has no data source")

    integration_connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Integration Connector',
        help="If data_source is 'integration', specifies which connector provides data for this field. "
             "The connector must be configured and active."
    )

    source_field_mapping = fields.Char(
        string='Integration Field',
        help="Field name in the integration connector that maps to this component. "
             "Used when data_source is 'integration' to identify which field to fetch."
    )

    source_sheet_name = fields.Char(
        string='Source Sheet',
        help="Name of the worksheet this component was imported from (for multi-sheet Excel files)"
    )

    original_column_letter = fields.Char(
        string='Original Column',
        help="Original Excel column letter from the source file (before reordering)"
    )

    forced_column_letter = fields.Char(
        string='Forced Column Letter',
        help="If set, this column letter is used instead of auto-computed. Used for constants at ZA, ZB, etc."
    )

    # ==========================================
    # FORMULA (for formula type)
    # ==========================================
    excel_formula = fields.Char(
        string='Excel Formula',
        help="Excel-style formula (e.g., =A1+B1*0.08, =SUM(A1:C1), =IF(A1>1000,B1*0.1,0))"
    )
    excel_formula_display = fields.Char(
        string='Excel Formula',
        compute='_compute_excel_formula_display',
        inverse='_inverse_excel_formula_display',
        help="Display-friendly formula with row numbers stripped."
    )

    python_formula = fields.Text(
        string='Python Code',
        compute='_compute_python_formula',
        store=True,
        help="Auto-generated Python code from Excel formula"
    )

    formula_dependencies = fields.Char(
        string='Dependencies',
        compute='_compute_dependencies',
        store=True,
        help="List of columns this formula depends on"
    )

    @staticmethod
    def _normalize_excel_formula(formula):
        if not formula:
            return formula
        formula = str(formula).strip()
        return re.sub(r'(?<![A-Za-z0-9_])\$?([A-Z]{1,3})\$?\d+', r'\1', formula)

    @staticmethod
    def _strip_string_literals(formula):
        """Remove Excel string literals to avoid false reference matches."""
        if not formula:
            return formula
        return re.sub(r'"([^"]|"")*"', ' ', formula)

    @api.depends('excel_formula')
    def _compute_excel_formula_display(self):
        for record in self:
            record.excel_formula_display = self._normalize_excel_formula(record.excel_formula or '')

    def _inverse_excel_formula_display(self):
        for record in self:
            record.excel_formula = self._normalize_excel_formula(
                record.excel_formula_display or ''
            )

    # ==========================================
    # INPUT COLUMN SETTINGS
    # ==========================================
    data_source_field = fields.Char(
        string='Source Field Mapping',
        help="Field path in source data (e.g., 'base_salary', 'hours_worked')"
    )

    default_value = fields.Float(
        string='Default Value',
        default=0.0,
        help="Default value when source field is empty"
    )

    # ==========================================
    # CONSTANT COLUMN SETTINGS
    # ==========================================
    constant_value = fields.Float(
        string='Constant Value',
        default=0.0,
        digits=(16, 6),  # Allow up to 6 decimal places for percentages like 0.015
        help="Fixed value for constant columns"
    )

    # ==========================================
    # DISPLAY SETTINGS
    # ==========================================
    column_width = fields.Integer(
        string='Width (px)',
        default=120,
        help="Column width in pixels"
    )

    number_format = fields.Selection([
        ('number', 'Number'),
        ('currency', 'Currency'),
        ('percentage', 'Percentage'),
        ('integer', 'Integer')
    ], string='Number Format', default='currency')

    decimal_places = fields.Integer(
        string='Decimal Places',
        default=2
    )

    text_align = fields.Selection([
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right')
    ], string='Text Alignment', default='right')

    # ==========================================
    # VALIDATION
    # ==========================================
    is_valid = fields.Boolean(
        string='Valid',
        default=True,
        help="Formula validation status"
    )

    validation_message = fields.Char(
        string='Validation Message',
        help="Error message if formula is invalid"
    )

    # ==========================================
    # RUNTIME EVALUATION ERRORS
    # ==========================================
    has_evaluation_error = fields.Boolean(
        string='Has Evaluation Error',
        default=False,
        help="True if this formula failed during last evaluation"
    )

    last_evaluation_error = fields.Text(
        string='Last Evaluation Error',
        help="Detailed error message from last formula evaluation attempt"
    )

    excel_formula_converted = fields.Text(
        string='Python Code (for debugging)',
        help="The Python code generated from the Excel formula (for debugging purposes)"
    )

    last_evaluation_date = fields.Datetime(
        string='Last Evaluated',
        help="When this formula was last evaluated"
    )

    has_circular_ref = fields.Boolean(
        string='Circular Reference',
        default=False,
        help="True if formula creates a circular reference"
    )

    # ==========================================
    # VISIBILITY & BEHAVIOR
    # ==========================================
    appears_on_payslip = fields.Boolean(
        string='Appears on Payslip',
        default=True,
        help="Show this component on payslip document"
    )

    report_visible = fields.Boolean(
        string='Visible in Reports',
        default=False,
        help="Include this component in reports and pivots."
    )

    is_visible_in_grid = fields.Boolean(
        string='Visible in Grid',
        default=True,
        help="Show this column in the Excel grid"
    )

    is_editable = fields.Boolean(
        string='Editable',
        default=True,
        help="Allow editing values in sample data rows"
    )

    is_required = fields.Boolean(
        string='Required',
        default=False,
        help="Mark as required input for payroll calculation"
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
    @api.depends('column_letter', 'code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.column_letter}: {record.name} ({record.code})"

    @api.depends('sequence', 'config_id', 'name', 'code', 'forced_column_letter')
    def _compute_column_letter(self):
        """Compute Excel-style column letter based on sequence order.

        For saved records: compute based on sequence order among saved siblings.
        For unsaved records with data: show provisional letter.
        For empty unsaved records: show blank.

        If forced_column_letter is set, use that instead (for constants at ZA, ZB, etc.)
        """
        for record in self:
            # If forced_column_letter is set, use it directly (for constants)
            if record.forced_column_letter:
                record.column_letter = record.forced_column_letter
                continue

            if not record.config_id:
                # No config - blank
                record.column_letter = ''
            elif isinstance(record.id, int):
                # Saved record - compute position among saved siblings
                # Exclude records with forced_column_letter from the sequence calculation
                saved_siblings = record.config_id.rule_ids.filtered(
                    lambda r: isinstance(r.id, int) and not r.forced_column_letter
                )
                sorted_siblings = saved_siblings.sorted(
                    key=lambda r: (r.sequence or 0, r.id)
                )
                # Find position of this record
                for index, sibling in enumerate(sorted_siblings):
                    if sibling.id == record.id:
                        record.column_letter = self._index_to_letter(index)
                        break
                else:
                    record.column_letter = ''
            else:
                # Unsaved record
                if record.name or record.code:
                    # Has data - show provisional letter
                    # Count saved records (excluding those with forced_column_letter)
                    saved_count = len(record.config_id.rule_ids.filtered(
                        lambda r: isinstance(r.id, int) and not r.forced_column_letter
                    ))
                    # Count unsaved records WITH DATA that come before this one
                    # Use sequence and id string for ordering
                    current_key = (record.sequence or 0, str(record.id))
                    unsaved_with_data_before = len(record.config_id.rule_ids.filtered(
                        lambda r: not isinstance(r.id, int) and
                        (r.name or r.code) and
                        not r.forced_column_letter and
                        (r.sequence or 0, str(r.id)) < current_key
                    ))
                    record.column_letter = self._index_to_letter(saved_count + unsaved_with_data_before)
                else:
                    # Empty/new row - blank
                    record.column_letter = ''

    def _inverse_column_letter(self):
        for record in self:
            value = (record.column_letter or '').strip().upper()
            record.forced_column_letter = value or False

    @staticmethod
    def _index_to_letter(index):
        """Convert 0-based index to Excel column letter (A, B, ...Z, AA, AB, etc.)"""
        result = ""
        while index >= 0:
            result = chr(index % 26 + ord('A')) + result
            index = index // 26 - 1
        return result

    @staticmethod
    def _letter_to_index(letter):
        """Convert Excel column letter to 0-based index"""
        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    @api.depends('excel_formula', 'config_id.rule_ids.code', 'config_id.rule_ids.column_letter')
    def _compute_python_formula(self):
        """Convert Excel formula to Python code"""
        for record in self:
            if not record.excel_formula or record.column_type != 'formula':
                record.python_formula = ''
                continue

            try:
                # Get column mapping from config
                column_map = {}
                for rule in record.config_id.rule_ids:
                    if rule.column_letter:
                        column_map[rule.column_letter] = rule.code

                # Convert formula
                python_code = record._convert_excel_to_python(
                    record.excel_formula,
                    column_map
                )
                record.python_formula = python_code
            except Exception as e:
                record.python_formula = f"# Error: {str(e)}"
                _logger.warning(f"Formula conversion error for {record.code}: {e}")

    def _convert_excel_to_python(self, formula, column_map):
        """Convert Excel formula to Python expression

        This is the PRIMARY formula conversion engine. It handles:
        - Cell references (A1, B2, etc.)
        - Standalone column letters (A, B, C)
        - Column codes (BASIC, GROSS, etc.)
        - Ranges (A1:C1, A:C, BASIC:GROSS)
        - Excel functions (SUM, IF, ROUND, etc.)
        - Percent literals (8% -> 0.08)
        - Comparison operators (= -> ==)
        """
        if not formula:
            return formula

        formula = formula.strip()
        result = formula[1:] if formula.startswith('=') else formula

        _logger.debug(f"Converting formula: {formula}")

        # Protect quoted strings from cell/code replacements (e.g., "B3", "Luong thang").
        string_literals = []

        def _mask_string(match):
            string_literals.append(match.group(0))
            return f"__str{len(string_literals) - 1}__"

        result = re.sub(r'"([^"]|"")*"', _mask_string, result)

        # Resolve same-sheet VLOOKUP into direct column references when possible.
        # Example: VLOOKUP(B5,CM2:$F$5,6,0) -> target column letter.
        vlookup_pattern = re.compile(
            r"VLOOKUP\s*\(\s*[^,]+,\s*\$?([A-Z]+)\$?\d*\s*:\s*\$?([A-Z]+)\$?\d*,\s*(\d+)\s*,\s*[^)]+\)",
            re.IGNORECASE
        )

        def _resolve_vlookup(match):
            start_col = match.group(1).upper()
            end_col = match.group(2).upper()
            col_index = int(match.group(3))
            try:
                from ..formula_engine.column_manager import ColumnManager
                start_idx = ColumnManager.letter_to_index(start_col)
                end_idx = ColumnManager.letter_to_index(end_col)
                base_idx = min(start_idx, end_idx)
                target_idx = base_idx + col_index - 1
                return ColumnManager.index_to_letter(target_idx)
            except Exception:
                return "0"

        result = vlookup_pattern.sub(_resolve_vlookup, result)

        # Build reverse map: code -> column_letter for range expansion
        code_to_letter = {v: k for k, v in column_map.items()}

        # Get all codes in SEQUENCE ORDER for proper range expansion
        # The column_map may not be in sequence order, so we need to sort by column letter
        # Column letters A, B, C, ..., Z, AA, AB follow a specific order
        from ..formula_engine.column_manager import ColumnManager
        all_codes_ordered = [
            column_map[letter] for letter in sorted(
                column_map.keys(),
                key=lambda x: ColumnManager.letter_to_index(x)
            )
        ]

        # Helper function to expand a range of codes/letters into a list
        def expand_range(start_ref, end_ref):
            """Expand a range like A:C or BASIC:GROSS into list of values.get() calls"""
            _logger.debug(f"expand_range called: start_ref={start_ref}, end_ref={end_ref}")

            # Determine if refs are column letters or codes
            start_letter = start_ref if start_ref in column_map else code_to_letter.get(start_ref)
            end_letter = end_ref if end_ref in column_map else code_to_letter.get(end_ref)

            _logger.debug(f"  start_letter={start_letter}, end_letter={end_letter}")

            if not start_letter or not end_letter:
                # Try to find by code directly
                start_code = column_map.get(start_ref, start_ref)
                end_code = column_map.get(end_ref, end_ref)
                _logger.debug(f"  Fallback mode: start_code={start_code}, end_code={end_code}")

                # Find indices in ordered codes
                try:
                    start_idx = all_codes_ordered.index(start_code)
                    end_idx = all_codes_ordered.index(end_code)
                except ValueError:
                    # Fallback: just return the two endpoints
                    result = f"values.get('{start_code}', 0), values.get('{end_code}', 0)"
                    _logger.debug(f"  Range fallback result (2 values): {result}")
                    return result

                # Get all codes in range
                if start_idx > end_idx:
                    start_idx, end_idx = end_idx, start_idx
                parts = []
                for code in all_codes_ordered[start_idx:end_idx + 1]:
                    parts.append(f"values.get('{code}', 0)")
                result = ', '.join(parts)
                _logger.debug(f"  Range expansion result ({len(parts)} values): {result[:100]}...")
                return result

            # Use column manager for letter-based ranges
            from ..formula_engine.column_manager import ColumnManager
            start_idx = ColumnManager.letter_to_index(start_letter)
            end_idx = ColumnManager.letter_to_index(end_letter)
            _logger.debug(f"  Letter range: start_idx={start_idx}, end_idx={end_idx}")
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            parts = []
            for i in range(start_idx, end_idx + 1):
                letter = ColumnManager.index_to_letter(i)
                code = column_map.get(letter, letter)
                parts.append(f"values.get('{code}', 0)")
            result = ', '.join(parts)
            _logger.debug(f"  Range expansion result ({len(parts)} values): {result[:100]}...")
            return result

        # Convert ranges with row numbers (e.g., A1:C1, $A$1:$C$1)
        # NOTE: Don't add brackets here - let function replacement handle it
        # This avoids double brackets like sum([[...]]) when SUM( becomes sum([
        def replace_range_with_row(m):
            start_col = m.group(1)
            end_col = m.group(2)
            _logger.debug(f"Range with row matched: {m.group(0)} -> expanding {start_col}:{end_col}")
            expanded = expand_range(start_col, end_col)
            _logger.debug(f"  Expanded to: {expanded[:100]}..." if len(expanded) > 100 else f"  Expanded to: {expanded}")
            return expanded  # No brackets - SUM([...]) will be handled by function replacement

        result = re.sub(r'\$?([A-Z]+)\$?\d+\s*:\s*\$?([A-Z]+)\$?\d+', replace_range_with_row, result)

        # Convert ranges WITHOUT row numbers - column letters only (e.g., A:C, AA:AC)
        def replace_range_no_row(m):
            start_col = m.group(1)
            end_col = m.group(2)
            _logger.debug(f"Range without row matched: {m.group(0)} -> expanding {start_col}:{end_col}")
            expanded = expand_range(start_col, end_col)
            _logger.debug(f"  Expanded to: {expanded[:100]}..." if len(expanded) > 100 else f"  Expanded to: {expanded}")
            return expanded  # No brackets

        # Match ranges like A:C, AA:AC - must come before cell ref replacement
        result = re.sub(r'\b([A-Z]{1,3})\s*:\s*([A-Z]{1,3})\b', replace_range_no_row, result)

        # Convert ranges with CODE names (e.g., ACTUALBASI:REIMBURSEM)
        # These are multi-letter codes that look like ranges
        def replace_code_range(m):
            start_code = m.group(1)
            end_code = m.group(2)
            # Verify these are actual codes in our map
            if start_code in column_map.values() and end_code in column_map.values():
                expanded = expand_range(start_code, end_code)
                return expanded  # No brackets
            return m.group(0)  # Not a valid range, leave as-is

        # Match CODE:CODE patterns (uppercase letters, 2+ chars each)
        result = re.sub(r'\b([A-Z]{2,}[A-Z0-9]*)\s*:\s*([A-Z]{2,}[A-Z0-9]*)\b', replace_code_range, result)

        # Replace cell references WITH row numbers (e.g., A1, AA1, B2), allow $ for absolute refs
        def replace_ref_with_row(match):
            col_letter = match.group(1)
            code = column_map.get(col_letter)
            if code:
                return f"values.get('{code}', 0)"
            return "0"

        result = re.sub(r'\$?([A-Z]+)\$?(\d+)', replace_ref_with_row, result)

        # Replace standalone column letters WITHOUT row numbers (e.g., A, B, C)
        # But NOT if they're part of a string like "YES"
        def replace_ref_no_row(match):
            col_letter = match.group(1)
            code = column_map.get(col_letter)
            if code:
                return f"values.get('{code}', 0)"
            return "0"

        # Match column letters that are standalone (not part of function names, strings, or already converted)
        # Negative lookbehind: not preceded by letter, underscore, or quote
        # Negative lookahead: not followed by letter, digit, underscore, opening bracket, or quote
        result = re.sub(r'(?<![A-Za-z_"\'])([A-Z]+)(?![A-Za-z0-9_\(\["\'])', replace_ref_no_row, result)

        # Replace multi-letter CODES that are in column_map.values() (e.g., BASIC, GROSS)
        # This handles formulas that use codes directly instead of column letters
        # IMPORTANT: Only replace codes that are NOT already inside values.get('...', 0) calls
        def replace_code_ref(match):
            code = match.group(1)
            if code in column_map.values():
                return f"values.get('{code}', 0)"
            return match.group(0)

        # Match uppercase identifiers that might be codes
        # Use negative lookbehind/lookahead for quotes to avoid matching inside already-converted strings
        # e.g., values.get('BASESALARY', 0) - BASESALARY is inside quotes, should NOT be matched again
        result = re.sub(r"(?<!')([A-Z][A-Z0-9]{1,})(?!')", replace_code_ref, result)

        # Replace Excel functions with Python equivalents
        function_map = {
            r'\bSUM\(': 'sum([',
            r'\bAVERAGE\(': 'self._avg([',
            r'\bMIN\(': 'min([',
            r'\bMAX\(': 'max([',
            r'\bABS\(': 'abs(',
            r'\bROUND\(': 'round(',
            r'\bIF\(': 'self._if(',
            r'\bIFERROR\(': 'self._iferror(',
            r'\bISBLANK\(': 'self._isblank(',
            r'\bAND\(': 'all([',
            r'\bOR\(': 'any([',
            r'\bNOT\(': 'not(',
            r'\bPOWER\(': 'pow(',
            r'\bSQRT\(': 'math.sqrt(',
            r'\bCEILING\(': 'math.ceil(',
            r'\bFLOOR\(': 'math.floor(',
            r'\bSUMIF\(': 'self._sumif(',
            r'\bSUMIFS\(': 'self._sumifs(',
            r'\bROW\(': 'self._row(',
            r'\bSUBTOTAL\(': 'self._subtotal(',
            r'\bMOD\(': 'self._mod(',
            r'\bSIGN\(': 'self._sign(',
            r'\bROUNDUP\(': 'self._roundup(',
            r'\bROUNDDOWN\(': 'self._rounddown(',
        }

        for excel_func, python_func in function_map.items():
            result = re.sub(excel_func, python_func, result, flags=re.IGNORECASE)

        # Convert percent literals (e.g., 8% -> (8/100), 1.5% -> (1.5/100))
        # Must handle cases like *8% or +8% or just 8%
        result = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1/100)', result)

        # Convert single '=' to '==' for comparisons (not touching >=, <=, !=, ==)
        # Also handle string comparisons like ="YES"
        result = re.sub(r'(?<![<>=!])=(?!=)', '==', result)

        # Fix closing brackets for array functions (SUM, MIN, MAX, etc.)
        result = self._fix_array_brackets(result)

        # Restore string literals.
        for idx, literal in enumerate(string_literals):
            result = result.replace(f"__str{idx}__", literal)

        # Normalize values.get('A', 0) for any column letters that exist in column_map.
        # This fixes cases where range expansion fell back to raw letters.
        for col_letter, code in column_map.items():
            if not col_letter or not code:
                continue
            if col_letter == code:
                continue
            result = re.sub(
                rf"values\.get\('{re.escape(col_letter)}',\s*0\)",
                f"values.get('{code}', 0)",
                result
            )

        # Treat empty-string comparisons as blank checks using raw values.
        result = re.sub(
            r"values\.get\('([^']+)', 0\)\s*==\s*\"\"",
            r"self._isblank_value(raw_values.get('\1'))",
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)', 0\)\s*==\s*''",
            r"self._isblank_value(raw_values.get('\1'))",
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)', 0\)\s*!=\s*\"\"",
            r"not self._isblank_value(raw_values.get('\1'))",
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)', 0\)\s*!=\s*''",
            r"not self._isblank_value(raw_values.get('\1'))",
            result
        )

        # Treat string literal comparisons as raw string checks (preserve text inputs).
        def _quote_literal(value):
            return repr(value)

        def _replace_raw_eq(match):
            key = match.group(1)
            literal = match.group(2)
            return f"raw_values.get('{key}') == {_quote_literal(literal)}"

        def _replace_raw_ne(match):
            key = match.group(1)
            literal = match.group(2)
            return f"raw_values.get('{key}') != {_quote_literal(literal)}"

        def _replace_raw_eq_reverse(match):
            literal = match.group(1)
            key = match.group(2)
            return f"{_quote_literal(literal)} == raw_values.get('{key}')"

        def _replace_raw_ne_reverse(match):
            literal = match.group(1)
            key = match.group(2)
            return f"{_quote_literal(literal)} != raw_values.get('{key}')"

        result = re.sub(
            r"values\.get\('([^']+)',\s*0(?:\.0)?\)\s*==\s*\"([^\"]*)\"",
            _replace_raw_eq,
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)',\s*0(?:\.0)?\)\s*==\s*'([^']*)'",
            _replace_raw_eq,
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)',\s*0(?:\.0)?\)\s*!=\s*\"([^\"]*)\"",
            _replace_raw_ne,
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)',\s*0(?:\.0)?\)\s*!=\s*'([^']*)'",
            _replace_raw_ne,
            result
        )
        result = re.sub(
            r"\"([^\"]*)\"\s*==\s*values\.get\('([^']+)',\s*0(?:\.0)?\)",
            _replace_raw_eq_reverse,
            result
        )
        result = re.sub(
            r"'([^']*)'\s*==\s*values\.get\('([^']+)',\s*0(?:\.0)?\)",
            _replace_raw_eq_reverse,
            result
        )
        result = re.sub(
            r"\"([^\"]*)\"\s*!=\s*values\.get\('([^']+)',\s*0(?:\.0)?\)",
            _replace_raw_ne_reverse,
            result
        )
        result = re.sub(
            r"'([^']*)'\s*!=\s*values\.get\('([^']+)',\s*0(?:\.0)?\)",
            _replace_raw_ne_reverse,
            result
        )

        _logger.debug(f"Converted to Python: {result}")

        return result

    def _fix_array_brackets(self, formula):
        """Fix brackets for functions that were converted to list operations

        This handles patterns like:
        - sum([v1, v2, v3) -> sum([v1, v2, v3])
        - sum([v1, v2, v3)+x -> sum([v1, v2, v3])+x

        Must handle multiple occurrences of the same function.
        """
        original = formula
        patterns = ['sum([', 'min([', 'max([', 'self._avg([', 'all([', 'any([']

        for pattern in patterns:
            # Find all occurrences and fix from right-to-left to handle nested calls.
            starts = []
            search_start = 0
            while True:
                start = formula.find(pattern, search_start)
                if start == -1:
                    break
                starts.append(start)
                search_start = start + len(pattern)

            for start in reversed(starts):
                open_count = 0
                found_close = False
                for i, char in enumerate(formula[start:]):
                    if char == '(':
                        open_count += 1
                    elif char == ')':
                        open_count -= 1
                        if open_count == 0:
                            pos = start + i
                            if pos > 0 and formula[pos - 1] != ']':
                                formula = formula[:pos] + ']' + formula[pos:]
                            found_close = True
                            break

                if not found_close:
                    continue

        if formula != original:
            _logger.debug(f"_fix_array_brackets: Modified formula")
            _logger.debug(f"  Before: {original[:100]}..." if len(original) > 100 else f"  Before: {original}")
            _logger.debug(f"  After: {formula[:100]}..." if len(formula) > 100 else f"  After: {formula}")
        return formula

    @api.depends('excel_formula')
    def _compute_dependencies(self):
        """Extract column dependencies from formula - both column letters and codes"""
        for record in self:
            if not record.excel_formula:
                record.formula_dependencies = ''
                continue

            # Extract column references - both with row numbers (A1, B2) and without (A, B, C)
            # Also extract CODE references (BASIC, GROSS, etc.)
            formula = record.excel_formula.upper()
            formula_no_strings = record._strip_string_literals(formula)

            # Find references with row numbers (A1, AA1, etc.)
            refs_with_row = re.findall(r'([A-Z]+)\d+', formula_no_strings)

            # Find standalone column letters (A, B, C) - not part of function names
            # Remove function names first to avoid matching them
            formula_cleaned = re.sub(
                r'(SUM|AVERAGE|MIN|MAX|ABS|ROUND|IF|IFERROR|AND|OR|NOT|POWER|SQRT|CEILING|FLOOR|ISBLANK)\s*\(',
                '',
                formula_no_strings
            )
            refs_no_row = re.findall(r'(?<![A-Z])([A-Z]+)(?![A-Z0-9])', formula_cleaned)

            # Also find multi-letter CODE references (e.g., BASIC, GROSS, NETPAY)
            # These are uppercase identifiers that might be codes
            code_refs = re.findall(r'\b([A-Z][A-Z0-9_]{2,})\b', formula_cleaned)

            all_refs = refs_with_row + refs_no_row + code_refs
            unique_refs = sorted(set(all_refs))
            record.formula_dependencies = ','.join(unique_refs)

    # ==========================================
    # CRUD OVERRIDES
    # ==========================================
    @api.model
    def create(self, vals):
        """Auto-assign sequence to avoid duplicate column letters when adding new rows manually.
        
        This does NOT interfere with Excel import because:
        - Excel import explicitly sets sequence based on column order (line 2143 in multisheet_import_wizard.py)
        - We only auto-assign when sequence is missing or equals the default (10)
        - Excel import assigns unique sequences like 0, 10, 20, 30, etc.
        """
        # Only auto-assign if:
        # 1. config_id is provided (creating a rule for a config)
        # 2. sequence is not explicitly set OR is the default value (10)
        # This prevents duplicate column letters when clicking "Add a line" in the UI
        if 'config_id' in vals and vals.get('sequence', 10) == 10:
            # IMPORTANT: Use explicit search instead of config.rule_ids to avoid pagination issues
            # When viewing a paginated One2many list, config.rule_ids only contains visible records
            existing_rules = self.env['hr.formula.rule'].search([
                ('config_id', '=', vals['config_id']),
                ('forced_column_letter', '=', False)
            ])
            
            if existing_rules:
                # Find the maximum sequence among ALL existing rules (not just current page)
                max_sequence = max(existing_rules.mapped('sequence'))
                # Assign next sequence (increment by 10 as per Odoo convention)
                vals['sequence'] = max_sequence + 10
            # If no existing rules, leave sequence as default (10)
        
        return super(HrFormulaRule, self).create(vals)

    # ==========================================
    # VALIDATION
    # ==========================================
    def validate_formula(self):
        """Validate the formula syntax and references"""
        self.ensure_one()
        if not self.excel_formula or self.column_type != 'formula':
            self.write({'is_valid': True, 'validation_message': ''})
            return True, ''

        errors = []

        # Check formula starts with =
        if not self.excel_formula.startswith('='):
            errors.append(_("Formula must start with '='"))

        # Check for valid column references - both column letters and codes
        formula = self.excel_formula.upper()
        formula_no_strings = self._strip_string_literals(formula)

        # Find references with row numbers (A1, AA1, etc.)
        refs_with_row = re.findall(r'\$?([A-Z]+)\$?\d+', formula_no_strings)

        # Find standalone column letters - remove function names first
        formula_cleaned = re.sub(
            r'(SUM|AVERAGE|MIN|MAX|ABS|ROUND|IF|IFERROR|AND|OR|NOT|POWER|SQRT|CEILING|FLOOR|ISBLANK)\s*\(',
            '',
            formula_no_strings
        )
        refs_no_row = re.findall(r'(?<![A-Z])([A-Z]+)(?![A-Z0-9])', formula_cleaned)

        # Also find code references
        code_refs = re.findall(r'\b([A-Z][A-Z0-9_]{2,})\b', formula_cleaned)

        refs = list(set(refs_with_row + refs_no_row + code_refs))
        valid_letters = set(self.config_id.rule_ids.mapped('column_letter'))
        valid_codes = set(self.config_id.rule_ids.mapped('code'))

        for ref in refs:
            # Check if reference is valid (either a column letter or a code)
            if ref not in valid_letters and ref not in valid_codes:
                errors.append(_("Invalid column reference: %s") % ref)

        # Check for self-reference
        if self.column_letter and self.column_letter in refs:
            errors.append(_("Formula cannot reference its own column"))

        # Check parentheses balance
        if self.excel_formula.count('(') != self.excel_formula.count(')'):
            errors.append(_("Unbalanced parentheses"))

        is_valid = len(errors) == 0
        message = '; '.join(errors) if errors else ''

        self.write({
            'is_valid': is_valid,
            'validation_message': message
        })

        return is_valid, message

    # ==========================================
    # REORDER ACTIONS
    # ==========================================
    def move_column_left(self):
        """Move this column one position left"""
        self.ensure_one()
        prev_rule = self.config_id.rule_ids.filtered(
            lambda r: r.sequence < self.sequence
        ).sorted(key=lambda r: r.sequence, reverse=True)[:1]

        if prev_rule:
            # Swap sequences
            my_seq = self.sequence
            self.sequence = prev_rule.sequence
            prev_rule.sequence = my_seq

        # Trigger recomputation
        self.config_id.rule_ids._compute_column_letter()

    def move_column_right(self):
        """Move this column one position right"""
        self.ensure_one()
        next_rule = self.config_id.rule_ids.filtered(
            lambda r: r.sequence > self.sequence
        ).sorted(key=lambda r: r.sequence)[:1]

        if next_rule:
            # Swap sequences
            my_seq = self.sequence
            self.sequence = next_rule.sequence
            next_rule.sequence = my_seq

        # Trigger recomputation
        self.config_id.rule_ids._compute_column_letter()

    def reorder_to_position(self, new_sequence):
        """Reorder this column to a new sequence position"""
        self.ensure_one()
        old_seq = self.sequence

        if new_sequence == old_seq:
            return

        rules = self.config_id.rule_ids.sorted(key=lambda r: r.sequence)

        if new_sequence > old_seq:
            # Moving right - shift others left
            for rule in rules:
                if old_seq < rule.sequence <= new_sequence:
                    rule.sequence -= 1
        else:
            # Moving left - shift others right
            for rule in rules:
                if new_sequence <= rule.sequence < old_seq:
                    rule.sequence += 1

        self.sequence = new_sequence

        # Update formula references if needed
        self._update_formula_references_after_reorder()

        # Trigger recomputation
        self.config_id.rule_ids._compute_column_letter()

    def _update_formula_references_after_reorder(self):
        """Update formula references in all rules after column reorder"""
        # This is handled by the computed field _compute_python_formula
        # which will regenerate Python code with new column letters
        pass

    # ==========================================
    # CONSTRAINTS
    # ==========================================
    _sql_constraints = [
        ('code_config_uniq', 'unique(code, config_id)',
         'Rule code must be unique within the configuration!'),
    ]

    @api.constrains('column_type', 'excel_formula', 'data_source_field')
    def _check_column_settings(self):
        for record in self:
            if record.column_type == 'formula' and not record.excel_formula:
                # Allow empty formula during creation
                pass
            if record.column_type == 'input' and not record.data_source_field:
                # Allow empty mapping during creation
                pass

    @api.constrains('column_letter', 'config_id')
    def _check_unique_column_letter(self):
        for config in self.mapped('config_id'):
            seen = {}
            for rule in config.rule_ids.filtered(lambda r: r.column_letter):
                letter = (rule.column_letter or '').strip().upper()
                if not letter:
                    continue
                existing = seen.get(letter)
                if existing and existing.id != rule.id:
                    current_name = rule.name or rule.code or _("(unnamed)")
                    existing_name = existing.name or existing.code or _("(unnamed)")
                    raise ValidationError(
                        _("Column letter '%s' is already used by '%s' (conflicts with '%s').")
                        % (letter, existing_name, current_name)
                    )
                seen[letter] = rule

    # ==========================================
    # EVALUATION
    # ==========================================
    def evaluate(self, values):
        """Evaluate this rule with given values context

        IMPORTANT: This always computes the Python formula fresh to ensure
        we use the latest conversion logic. Cached python_formula may be stale.
        """
        self.ensure_one()

        if self.column_type == 'constant':
            return self.constant_value or 0.0

        if self.column_type == 'input':
            return values.get(self.code, self.default_value or 0.0)

        if self.column_type == 'formula':
            if not self.excel_formula:
                _logger.warning(f"No Excel formula defined for {self.code}, returning 0")
                return 0.0

            # ALWAYS compute Python formula fresh to ensure latest conversion logic
            # The cached python_formula field may have been computed with old buggy logic
            try:
                column_map = {}
                for rule in self.config_id.rule_ids:
                    if rule.column_letter and rule.code:
                        column_map[rule.column_letter] = rule.code
                python_code = self._convert_excel_to_python(self.excel_formula, column_map)

                # Store the converted Python code for debugging
                self.excel_formula_converted = python_code

                # Enhanced logging for debugging IFERROR and other formula issues
                _logger.debug(f"=== Formula Evaluation for {self.code} ===")
                _logger.debug(f"  Excel formula: {self.excel_formula}")
                _logger.debug(f"  Python code: {python_code}")
                _logger.debug(f"  Column map: {column_map}")
            except Exception as e:
                error_msg = f"Error converting formula: {str(e)}\nExcel formula: {self.excel_formula}"
                _logger.error(f"Error converting formula for {self.code}: {e}")

                # Store the error information
                self.write({
                    'has_evaluation_error': True,
                    'last_evaluation_error': error_msg,
                    'last_evaluation_date': fields.Datetime.now()
                })
                return 0.0

            if not python_code:
                _logger.warning(f"No Python code generated for {self.code}, returning 0")
                return 0.0

            try:
                # Helper function to safely convert values
                def safe_value(v):
                    """Convert value, preserving non-numeric strings for comparisons like ="YES"

                    - None/empty → 0
                    - Numbers → kept as-is
                    - Numeric strings ("123") → converted to float
                    - Non-numeric strings ("YES") → preserved for IF comparisons
                    """
                    if v is None or v == '':
                        return 0
                    if isinstance(v, (int, float)):
                        return v
                    if isinstance(v, str):
                        cleaned = v.strip().replace(' ', '')
                        if not cleaned:
                            return 0
                        try:
                            # Handle thousands separators and decimal marks.
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
                            # Return 0 for non-numeric strings in arithmetic contexts
                            # String comparisons use raw_values via _isblank_value helper
                            return 0
                    return 0

                # Build safe evaluation context with values properly converted
                raw_values = values.copy()
                safe_context = {
                    'values': {k: safe_value(v) for k, v in values.items()},
                    'raw_values': raw_values,
                    'self': self,
                    'math': __import__('math'),
                    'sum': self._sumlist,
                    'min': self._minlist,
                    'max': self._maxlist,
                    'abs': abs,
                    'round': round,
                    'pow': pow,
                    'all': all,
                    'any': any,
                }

                # Log available values for debugging
                _logger.debug(f"  Available values: {list(safe_context['values'].keys())}")

                # Log specific values referenced in this formula
                for ref_code in values.keys():
                    if ref_code in python_code or f"'{ref_code}'" in python_code:
                        _logger.debug(f"  {ref_code} = {safe_context['values'].get(ref_code, 'NOT FOUND')}")

                if '"' in (self.excel_formula or '') or "raw_values" in python_code:
                    try:
                        ref_codes = re.findall(r"(?:values|raw_values)\.get\('([^']+)'", python_code)
                        ref_values = {
                            code: {
                                'raw': raw_values.get(code),
                                'safe': safe_context['values'].get(code),
                            }
                            for code in ref_codes
                        }
                    except Exception:
                        ref_codes = []
                        ref_values = {}
                    _logger.info(
                        "Formula eval debug: code=%s excel=%s python=%s refs=%s",
                        self.code,
                        self.excel_formula,
                        python_code,
                        ref_values,
                    )

                result = eval(python_code, {"__builtins__": {}}, safe_context)
                _logger.debug(f"  Result: {result}")

                # Clear any previous errors on successful evaluation
                if self.has_evaluation_error:
                    self.write({
                        'has_evaluation_error': False,
                        'last_evaluation_error': False,
                        'last_evaluation_date': fields.Datetime.now()
                    })

                if result is None:
                    return 0.0
                if isinstance(result, str):
                    return result
                try:
                    return float(result)
                except (TypeError, ValueError):
                    return result
            except Exception as e:
                # Build detailed error message
                error_details = []
                error_details.append(f"Error evaluating formula for {self.code}")
                error_details.append(f"\nExcel formula: {self.excel_formula}")
                error_details.append(f"\nPython code: {python_code}")
                error_details.append(f"\nError type: {type(e).__name__}")
                error_details.append(f"\nError message: {str(e)}")
                error_details.append(f"\nAvailable values: {', '.join(list(values.keys())[:10])}")
                if len(values.keys()) > 10:
                    error_details.append(f"... and {len(values.keys()) - 10} more")

                error_msg = '\n'.join(error_details)

                _logger.error(f"Formula evaluation error for {self.code}")
                _logger.error(f"  Excel formula: {self.excel_formula}")
                _logger.error(f"  Python code: {python_code}")
                _logger.error(f"  Error: {e}")
                _logger.error(f"  Available values: {list(values.keys())}")

                # Store the error information
                self.write({
                    'has_evaluation_error': True,
                    'last_evaluation_error': error_msg,
                    'last_evaluation_date': fields.Datetime.now()
                })

                return 0.0

        return 0.0

    def action_regenerate_python_formulas(self):
        """Force regeneration of Python formulas for all rules in the config

        Use this after updating the formula conversion logic to refresh all cached formulas.
        """
        for rule in self:
            if rule.excel_formula and rule.column_type == 'formula':
                try:
                    column_map = {}
                    for r in rule.config_id.rule_ids:
                        if r.column_letter and r.code:
                            column_map[r.column_letter] = r.code
                    python_code = rule._convert_excel_to_python(rule.excel_formula, column_map)
                    rule.write({'python_formula': python_code})
                    _logger.info(f"Regenerated Python formula for {rule.code}: {python_code}")
                except Exception as e:
                    _logger.error(f"Failed to regenerate formula for {rule.code}: {e}")

    def _if(self, condition, true_val, false_val=0):
        """Excel IF function implementation"""
        return true_val if condition else false_val

    def _isblank_value(self, value):
        """Return True when a raw value should be treated as blank."""
        return value is None or value == ''

    def _coerce_number(self, value):
        """Convert a value to float for numeric functions, ignoring non-numeric text."""
        if value is None or value == '':
            return None
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            import numbers
            if isinstance(value, numbers.Number):
                return float(value)
        except Exception:
            pass
        if isinstance(value, str):
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
        return None

    def _sumlist(self, values_list):
        """Excel SUM that ignores non-numeric values."""
        if values_list is None:
            return 0.0

        # Handle case where a single value is passed instead of a list
        if not isinstance(values_list, (list, tuple)):
            number = self._coerce_number(values_list)
            return number if number is not None else 0.0

        _logger.debug(f"_sumlist called with {len(values_list)} values: {values_list[:5]}..." if len(values_list) > 5 else f"_sumlist called with {len(values_list)} values: {values_list}")

        total = 0.0
        for value in values_list:
            number = self._coerce_number(value)
            if number is not None:
                total += number
        _logger.debug(f"_sumlist result: {total}")
        return total

    def _maxlist(self, values_list):
        """Excel MAX that ignores non-numeric values."""
        if values_list is None:
            return 0.0
        numbers = [self._coerce_number(v) for v in values_list]
        numbers = [v for v in numbers if v is not None]
        return max(numbers) if numbers else 0.0

    def _minlist(self, values_list):
        """Excel MIN that ignores non-numeric values."""
        if values_list is None:
            return 0.0
        numbers = [self._coerce_number(v) for v in values_list]
        numbers = [v for v in numbers if v is not None]
        return min(numbers) if numbers else 0.0

    def _avg(self, values_list):
        """Excel AVERAGE function implementation"""
        if not values_list:
            return 0
        numbers = [self._coerce_number(v) for v in values_list]
        numbers = [v for v in numbers if v is not None]
        return sum(numbers) / len(numbers) if numbers else 0

    def _iferror(self, value, error_value):
        """Excel IFERROR function implementation

        Note: In Python, arguments are evaluated before the function is called,
        so we can't catch evaluation errors here. Instead, we check for error
        indicators like None, empty string, or the special ERROR_VALUE sentinel.
        """
        # Check if value is an error indicator
        if value is None or value == '' or (hasattr(value, '__name__') and value.__name__ == 'ERROR_VALUE'):
            return error_value

        # Check if value is NaN or Inf (common error values)
        try:
            import math
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                return error_value
        except:
            pass

        return value

    def _isblank(self, value):
        """Excel ISBLANK function implementation"""
        return value in (None, '')

    def _sumif(self, range_val, criteria, sum_range=None):
        """
        Excel SUMIF function implementation.

        In the payroll context where formulas are evaluated per-employee row,
        SUMIF is simplified: if the criteria matches the range value, return
        the sum_range value (or range_val if sum_range not provided).

        Args:
            range_val: Value from the range column (criteria column)
            criteria: The value to match against
            sum_range: Value to return if match (optional, defaults to range_val)

        Returns:
            sum_range if criteria matches range_val, else 0
        """
        if range_val is None or criteria is None:
            return 0

        try:
            if isinstance(range_val, (int, float)) and isinstance(criteria, (int, float)):
                if range_val == criteria:
                    return float(sum_range) if sum_range is not None else float(range_val)
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

    def _sumifs(self, sum_range, *criteria_pairs):
        """
        Excel SUMIFS function implementation.

        Similar to SUMIF but with multiple criteria pairs.

        Args:
            sum_range: Value to return if all criteria match
            *criteria_pairs: Pairs of (range_val, criteria) to check

        Returns:
            sum_range if all criteria match, else 0
        """
        if sum_range is None:
            return 0

        for i in range(0, len(criteria_pairs), 2):
            if i + 1 >= len(criteria_pairs):
                break
            range_val = criteria_pairs[i]
            criteria = criteria_pairs[i + 1]

            if range_val is None or criteria is None:
                return 0

            try:
                if isinstance(range_val, (int, float)) and isinstance(criteria, (int, float)):
                    if range_val != criteria:
                        return 0
                elif str(range_val).strip().lower() != str(criteria).strip().lower():
                    return 0
            except Exception:
                return 0

        try:
            return float(sum_range)
        except (ValueError, TypeError):
            return 0

    def _row(self, reference=None):
        """
        Excel ROW function implementation.

        In payroll context, ROW() returns the current row being processed.
        For simplicity, returns 1 (or extracts row from reference if provided).

        Args:
            reference: Optional cell reference

        Returns:
            Row number (defaults to 1)
        """
        if reference is not None:
            if isinstance(reference, (int, float)):
                return int(reference)
            if isinstance(reference, str):
                match = re.search(r'(\d+)', str(reference))
                if match:
                    return int(match.group(1))
        return 1

    def _subtotal(self, function_num, *args):
        """
        Excel SUBTOTAL function implementation.

        SUBTOTAL(function_num, ref1, [ref2], ...) performs calculations
        based on function_num:
        1/101 = AVERAGE, 2/102 = COUNT, 3/103 = COUNTA, 4/104 = MAX,
        5/105 = MIN, 6/106 = PRODUCT, 9/109 = SUM

        Args:
            function_num: Function to use
            *args: Values to calculate

        Returns:
            Result of the specified function
        """
        if not args:
            return 0

        values = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                values.extend([v for v in arg if v is not None and v != ''])
            elif arg is not None and arg != '':
                values.append(arg)

        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass

        if not numeric_values:
            return 0

        func_num = int(function_num) % 100 if function_num >= 100 else int(function_num)

        try:
            if func_num == 1:  # AVERAGE
                return sum(numeric_values) / len(numeric_values) if numeric_values else 0
            elif func_num == 2:  # COUNT
                return len(numeric_values)
            elif func_num == 3:  # COUNTA
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
                return sum(numeric_values)
        except Exception:
            return 0

    def _mod(self, number, divisor):
        """Excel MOD function implementation"""
        if divisor == 0:
            return 0
        return number % divisor

    def _sign(self, number):
        """Excel SIGN function implementation"""
        if number > 0:
            return 1
        elif number < 0:
            return -1
        return 0

    def _roundup(self, number, decimals=0):
        """Excel ROUNDUP function implementation"""
        import math
        multiplier = 10 ** int(decimals)
        return math.ceil(number * multiplier) / multiplier

    def _rounddown(self, number, decimals=0):
        """Excel ROUNDDOWN function implementation"""
        import math
        multiplier = 10 ** int(decimals)
        return math.floor(number * multiplier) / multiplier
