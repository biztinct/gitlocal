# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import re
import logging

from ..formula_engine import excel_semantics

_logger = logging.getLogger(__name__)

# F7 — fields whose change is worth a version snapshot. A write touching none of
# these (e.g. a pure `sequence` reorder, or engine-set is_valid/python_formula)
# produces no version row.
VERSIONED_FIELDS = {
    'excel_formula', 'code', 'name', 'category_id',
    'column_type', 'number_format', 'appears_on_payslip',
    # B4: statutory constant values are versioned too, so applying a
    # legislation pack (or any rate/cap edit) leaves an F7 audit trail.
    'constant_value',
}
_VALID_VERSION_REASONS = {'edit', 'bulk', 'import', 'fill', 'restore', 'lifecycle', 'rename', 'legislation', 'merge', 'sync'}


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

    # F9 — Payslip Studio: order within the payslip section + per-line visibility
    payslip_sequence = fields.Integer(
        string='Payslip Order',
        default=10,
        help="Order of this line within its payslip section."
    )
    visibility_rule = fields.Selection([
        ('always', 'Always show'),
        ('when_nonzero', 'Only when non-zero'),
        ('never', 'Never (hidden)'),
    ], string='Payslip Visibility', default='always',
        help="Controls whether this line prints on the payslip.")

    report_visible = fields.Boolean(
        string='Visible in Reports',
        default=False,
        help="Include this component in reports and pivots."
    )

    is_contract_component = fields.Boolean(
        string='Contract Component',
        default=False,
        help="Marks this component as a contract component sourced from contract advantages."
    )

    requires_new_contract = fields.Boolean(
        string='Requires New Contract',
        default=False,
        help="If enabled, changes to this component will trigger a new contract effective date."
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
                # Unsaved record with data — show the letter create() will
                # ACTUALLY assign (from the high-water mark), so what the user
                # sees is what gets saved. (The old "count unforced saved
                # siblings" logic showed 'A' post-freeze — a mirage, since every
                # saved rule is forced — and the user would author references
                # against an occupied identity.)
                if record.name or record.code:
                    config = record.config_id
                    used = [self._letter_to_num(r.column_letter)
                            for r in config.rule_ids
                            if isinstance(r.id, int) and r.column_letter
                            and not self._is_constant_namespace(r.column_letter)]
                    base = max(config.col_letter_hwm or 0, max(used) if used else 0)
                    current_key = (record.sequence or 0, str(record.id))
                    offset = len(config.rule_ids.filtered(
                        lambda r: not isinstance(r.id, int) and (r.name or r.code)
                        and (r.sequence or 0, str(r.id)) < current_key))
                    record.column_letter = self._index_to_letter(base + offset)
                else:
                    # Empty/new row - blank
                    record.column_letter = ''

    def _inverse_column_letter(self):
        """Setting a letter (re)freezes it; BLANKING it is ignored when a frozen
        letter already exists — a column letter is a permanent identity (F111),
        so a cleared cell must not silently unfreeze the rule and let it be
        re-lettered positionally, orphaning every formula that referenced it."""
        for record in self:
            value = (record.column_letter or '').strip().upper()
            if value:
                record.forced_column_letter = value
            elif not record.forced_column_letter:
                record.forced_column_letter = False

    @staticmethod
    def _index_to_letter(index):
        """Convert 0-based index to Excel column letter (A, B, ...Z, AA, AB, etc.)"""
        result = ""
        while index >= 0:
            result = chr(index % 26 + ord('A')) + result
            index = index // 26 - 1
        return result

    # ======================================================================
    # F111 — column letters are PERMANENT identities (frozen via
    # forced_column_letter). sequence is pure display order; reordering can
    # never move a letter, so letter-based formula references stay valid.
    # ======================================================================
    @staticmethod
    def _letter_to_num(letter):
        """Excel column letter -> 1-based number ('A'->1, 'Z'->26, 'AA'->27)."""
        n = 0
        for ch in (letter or '').strip().upper():
            if 'A' <= ch <= 'Z':
                n = n * 26 + (ord(ch) - 64)
            else:
                return 0
        return n

    @api.model
    def _is_constant_namespace(self, letter):
        """True for the ZA/ZB… constants namespace (Z followed by a letter),
        which must be skipped when picking the next free identity letter. A
        lone 'Z' is an ordinary column and is NOT excluded (D111.3)."""
        return bool(letter) and len(letter) > 1 and letter[0].upper() == 'Z'

    @api.model
    def _next_free_letter(self, config):
        """The next permanent letter identity for `config`, never reusing a freed
        letter (D111.3). Mirrors create(): the mark is max(letter high-water,
        current max letter), so a deleted top letter is not handed out again. The
        ZA+ constants namespace is skipped."""
        used = [self._letter_to_num(r.column_letter) for r in config.rule_ids
                if r.column_letter and not self._is_constant_namespace(r.column_letter)]
        base = max(config.col_letter_hwm or 0, max(used) if used else 0)
        return self._index_to_letter(base)   # 1-based mark -> next 0-based index

    @api.model
    def _assert_letters_frozen(self, config, before):
        """Guard: after any sequence-only reorder, every rule's column_letter
        must be unchanged (D111.2). Raise — never silently re-point formulas."""
        after = {r.id: r.column_letter for r in config.rule_ids}
        if before != after:
            raise UserError(_(
                "Column letters changed during reorder — the operation was "
                "aborted to protect your formulas. This is a bug; please report it."))

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
                    if rule.column_letter and rule.code:
                        column_map[rule.column_letter] = rule.code

                _logger.debug(f"Column map has {len(column_map)} entries for {record.code}")
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

        # Excel-only operators Python would misparse (strings are masked, so
        # these can only be operators here):
        # - <>  is Excel not-equal; unconverted it is a Python syntax error.
        # - ^   is Excel power; Python ^ is XOR and silently returns garbage
        #       (100^2 == 102). Known edge vs Excel: -2^2 (Excel 4, Python -4)
        #       and right-assoc chains a^b^c — acceptable for payroll formulas.
        # - &   is Excel text concatenation; we cannot rewrite an infix
        #       operator reliably without a full parser, so fail LOUDLY (the
        #       error lands in python_formula / has_evaluation_error) instead
        #       of letting eval() produce a silent 0.
        result = result.replace('<>', '!=')
        result = result.replace('^', '**')
        if '&' in result:
            raise ValueError(
                "Excel '&' text concatenation is not supported yet — "
                "rewrite the formula without '&'."
            )

        # F11 — expand BRACKET(table_code, value) into a nested-IF Excel string
        # BEFORE any further conversion, so the value expression's cell refs and
        # the emitted IF/MAX convert through the normal pipeline. The evaluator
        # never sees a bracket table (D-F11.1).
        if 'BRACKET' in result.upper() and self.config_id:
            result = self.env['hr.formula.rate.table'].expand_brackets(result, self.config_id)

        # Normalize redundant parentheses around cell references like "(B15)".
        # The lookbehind is load-bearing: without it this turns a function
        # call ISBLANK(G1) into ISBLANKG1, which the cell-ref regex then
        # swallows as values.get('ISBLANKG', 0) -> silent 0.
        result = re.sub(r'(?<![A-Za-z0-9_])\(\s*(\$?[A-Z]+\$?\d+)\s*\)', r'\1', result, flags=re.IGNORECASE)

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
                except ValueError as e:
                    # CRITICAL FIX: When columns aren't in the map, we must still generate valid Python code
                    # Check if start_ref and end_ref look like column letters
                    parts = []
                    if start_ref not in column_map.values() and start_ref not in column_map:
                        _logger.warning(f"  Column reference '{start_ref}' not found in column_map - will expand as letter range if possible")
                    if end_ref not in column_map.values() and end_ref not in column_map:
                        _logger.warning(f"  Column reference '{end_ref}' not found in column_map - will expand as letter range if possible")

                    # Try to expand as letter range even if not in column_map
                    # This handles constants and forced columns that might not be in the main map
                    try:
                        from ..formula_engine.column_manager import ColumnManager
                        # Check if both refs look like column letters (1-3 uppercase letters)
                        if re.match(r'^[A-Z]{1,3}$', start_ref) and re.match(r'^[A-Z]{1,3}$', end_ref):
                            start_idx = ColumnManager.letter_to_index(start_ref)
                            end_idx = ColumnManager.letter_to_index(end_ref)
                            if start_idx > end_idx:
                                start_idx, end_idx = end_idx, start_idx
                            for i in range(start_idx, end_idx + 1):
                                letter = ColumnManager.index_to_letter(i)
                                code = column_map.get(letter, letter)  # Use letter as code if not mapped
                                parts.append(f"values.get('{code}', 0)")
                            result = ', '.join(parts)
                            _logger.debug(f"  Range expansion via letter fallback ({len(parts)} values): {result[:100]}...")
                            return result
                    except Exception as letter_err:
                        _logger.error(f"  Letter-based fallback failed: {letter_err}")

                    # Last resort: return just the start and end that we know about
                    if start_code in all_codes_ordered:
                        parts.append(f"values.get('{start_code}', 0)")
                    if end_code in all_codes_ordered and end_code != start_code:
                        parts.append(f"values.get('{end_code}', 0)")

                    if not parts:
                        # Absolute last resort: create placeholder for unknowns
                        result = f"values.get('{start_ref}', 0), values.get('{end_ref}', 0)"
                    else:
                        result = ', '.join(parts)
                    _logger.warning(f"  Range fallback result with missing columns ({len(parts)} values): {result}")
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
                _logger.debug(f"    Expanded {letter} -> code={code}")
            result = ', '.join(parts)
            _logger.debug(f"  NORMAL PATH: Range {start_ref}:{end_ref} expanded to {len(parts)} values: {result[:200]}...")
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

        def _is_inside_quotes(text, position):
            single_quotes = text[:position].count("'")
            double_quotes = text[:position].count('"')
            return (single_quotes % 2) == 1 or (double_quotes % 2) == 1

        # Replace cell references WITH row numbers (e.g., A1, AA1, B2), allow $ for absolute refs
        # CRITICAL: Do NOT match if we're inside quoted strings that were already created by range expansion
        _logger.debug(f"  BEFORE cell ref replacement: {result[:200]}...")
        def replace_ref_with_row(match):
            matched_text = match.group(0)
            start_pos = match.start()
            if _is_inside_quotes(result, start_pos):
                _logger.debug(f"  Skipping cell ref '{matched_text}' - inside quoted string")
                return match.group(0)  # Return unchanged

            col_letter = match.group(1)
            code = column_map.get(col_letter)
            if code:
                _logger.debug(f"  Converting cell ref '{matched_text}' -> values.get('{code}', 0)")
                return f"values.get('{code}', 0)"
            # If not in column_map, try using letter as code (for constants with forced_column_letter)
            _logger.warning(f"  Column letter '{col_letter}' from cell ref '{matched_text}' not in column_map, using letter as code")
            return f"values.get('{col_letter}', 0)"

        result = re.sub(r'\$?([A-Z]+)\$?(\d+)', replace_ref_with_row, result)
        _logger.debug(f"  AFTER cell ref replacement: {result[:200]}...")

        # Excel TRUE()/FALSE() and bare TRUE/FALSE literals -> Python booleans.
        # Must run BEFORE the standalone-letter/code replacement, which would
        # otherwise turn them into values.get('TRUE', 0) == permanent 0.
        result = re.sub(r'\bTRUE\s*\(\s*\)|\bTRUE\b', 'True', result)
        result = re.sub(r'\bFALSE\s*\(\s*\)|\bFALSE\b', 'False', result)

        # Replace standalone column letters WITHOUT row numbers (e.g., A, B, C)
        # But NOT if they're part of a string like "YES" OR inside already-converted values.get()
        def replace_ref_no_row(match):
            start_pos = match.start()
            if _is_inside_quotes(result, start_pos):
                return match.group(0)  # Return unchanged

            col_letter = match.group(1)
            code = column_map.get(col_letter)
            if code:
                return f"values.get('{code}', 0)"
            # If column letter not in map, try using the letter itself as code
            # This handles constants and forced columns (ZA, ZB, etc.) that might not be in column_map
            _logger.warning(f"Standalone column letter '{col_letter}' not found in column_map - using letter as code")
            return f"values.get('{col_letter}', 0)"

        # Match column letters that are standalone (not part of function names, strings, or already converted)
        # Negative lookbehind: not preceded by letter, underscore, or quote
        # Negative lookahead: not followed by letter, digit, underscore, opening bracket, or quote
        result = re.sub(r'(?<![A-Za-z_"\'])([A-Z]+)(?![A-Za-z0-9_\(\["\'])', replace_ref_no_row, result)

        # Replace multi-letter CODES that are in column_map.values() (e.g., BASIC, GROSS)
        # This handles formulas that use codes directly instead of column letters
        # IMPORTANT: Only replace codes that are NOT already inside values.get('...', 0) calls
        def replace_code_ref(match):
            start_pos = match.start()
            if _is_inside_quotes(result, start_pos):
                return match.group(0)  # Return unchanged

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
            # Excel ROUND is half-away-from-zero; Python round() is banker's
            # rounding (2.5 -> 2) which drifts money on .5 boundaries.
            r'\bROUND\(': 'self._round(',
            r'\bIF\(': 'self._if(',
            r'\bIFERROR\(': 'self._iferror(',
            r'\bISBLANK\(': 'self._isblank(',
            r'\bAND\(': 'all([',
            r'\bOR\(': 'any([',
            # NOT must stay a CALL: Python's `not` operator binds looser than
            # *, so not(x)*5 parses as not(x*5).
            r'\bNOT\(': 'self._not(',
            r'\bCOUNTA\(': 'self._counta([',
            r'\bPOWER\(': 'pow(',
            r'\bSQRT\(': 'math.sqrt(',
            # Excel CEILING/FLOOR take a significance argument (round to a
            # multiple); math.ceil/math.floor are 1-arg and TypeError'd here.
            r'\bCEILING\(': 'self._ceiling(',
            r'\bFLOOR\(': 'self._floor(',
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

        # Rewrite IF into a lazy Python ternary and IFERROR into a
        # lambda-guarded call. Python evaluates call arguments eagerly, so
        # without this IF(B1=0,0,A1/B1) raises #DIV/0! out of the branch
        # Excel never evaluates, and IFERROR can catch nothing at all.
        # Runs while string literals are still masked (no commas/parens
        # hiding inside literals).
        result = self._lazify_conditionals(result)

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

        # ISBLANK must see the RAW value: the coerced `values` dict maps
        # blank to 0, so self._isblank(values.get(...)) could never be True.
        result = re.sub(
            r"self\._isblank\(\s*values\.get\('([^']+)',\s*0\)\s*\)",
            r"self._isblank(raw_values.get('\1'))",
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
            r"(not self._isblank_value(raw_values.get('\1')))",
            result
        )
        result = re.sub(
            r"values\.get\('([^']+)', 0\)\s*!=\s*''",
            r"(not self._isblank_value(raw_values.get('\1')))",
            result
        )

        # Treat string literal comparisons as raw string checks (preserve text inputs).
        def _quote_literal(value):
            return repr(value)

        # Excel text equality is case-insensitive ("ct" = "CT" is TRUE), so
        # string comparisons route through self._streq instead of Python ==.
        # The `not` forms are parenthesized: `not x * 5` would otherwise
        # parse as not(x * 5).
        def _replace_raw_eq(match):
            key = match.group(1)
            literal = match.group(2)
            return f"self._streq(raw_values.get('{key}'), {_quote_literal(literal)})"

        def _replace_raw_ne(match):
            key = match.group(1)
            literal = match.group(2)
            return f"(not self._streq(raw_values.get('{key}'), {_quote_literal(literal)}))"

        def _replace_raw_eq_reverse(match):
            literal = match.group(1)
            key = match.group(2)
            return f"self._streq(raw_values.get('{key}'), {_quote_literal(literal)})"

        def _replace_raw_ne_reverse(match):
            literal = match.group(1)
            key = match.group(2)
            return f"(not self._streq(raw_values.get('{key}'), {_quote_literal(literal)}))"

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

    @staticmethod
    def _split_top_level_args(argstr):
        """Split a call's argument string at top-level commas (paren- and
        bracket-depth aware). String literals are masked as __strN__ at this
        stage, so no comma can hide inside a literal."""
        parts, depth, start = [], 0, 0
        for i, ch in enumerate(argstr):
            if ch in '([':
                depth += 1
            elif ch in ')]':
                depth -= 1
            elif ch == ',' and depth == 0:
                parts.append(argstr[start:i])
                start = i + 1
        parts.append(argstr[start:])
        return parts

    def _lazify_conditionals(self, formula):
        """Rewrite eager helper calls into lazy Python forms:

        - self._if(c, t[, f])   -> ((t) if (c) else (f))    [f defaults to 0]
        - self._iferror(x, y)   -> self._iferror(lambda: (x), (y))

        Excel only evaluates the branch it returns; Python evaluates all call
        arguments first, so without this IF(B1=0,0,A1/B1) explodes with
        #DIV/0! from the branch Excel never runs, and IFERROR can never catch
        anything. Processes rightmost-first (rightmost occurrence is always
        innermost for nesting). Bails out to the eager helpers on anything
        malformed — never raises.
        """
        for token, kind in (('self._iferror(', 'iferror'), ('self._if(', 'if')):
            for _guard in range(200):
                idx = formula.rfind(token)
                if kind == 'iferror':
                    # skip occurrences already rewritten to the lambda form
                    while idx != -1 and formula[idx + len(token):].lstrip().startswith('lambda'):
                        idx = formula.rfind(token, 0, idx)
                if idx == -1:
                    break
                open_pos = idx + len(token) - 1
                depth, close_pos = 0, -1
                for i in range(open_pos, len(formula)):
                    ch = formula[i]
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0:
                            close_pos = i
                            break
                if close_pos == -1:
                    break  # unbalanced parens — leave the eager call in place
                args = self._split_top_level_args(formula[open_pos + 1:close_pos])
                if kind == 'if' and len(args) in (2, 3):
                    cond = args[0].strip()
                    true_val = args[1].strip()
                    false_val = args[2].strip() if len(args) == 3 else '0'
                    replacement = f"(({true_val}) if ({cond}) else ({false_val}))"
                elif kind == 'iferror' and len(args) == 2:
                    replacement = (
                        f"self._iferror(lambda: ({args[0].strip()}), ({args[1].strip()}))"
                    )
                else:
                    break  # unexpected arity — leave as-is (eager fallback)
                formula = formula[:idx] + replacement + formula[close_pos + 1:]
        return formula

    def _fix_array_brackets(self, formula):
        """Fix brackets for functions that were converted to list operations

        This handles patterns like:
        - sum([v1, v2, v3) -> sum([v1, v2, v3])
        - sum([v1, v2, v3)+x -> sum([v1, v2, v3])+x

        Must handle multiple occurrences of the same function.
        """
        original = formula
        patterns = ['sum([', 'min([', 'max([', 'self._avg([', 'all([', 'any([']
        patterns.append('self._counta([')

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

            # F11 — expand BRACKET(table_code, value) FIRST so dependencies come
            # from the compiled formula's real column refs (the value expression),
            # not the pseudo-function name or the table code (which would otherwise
            # be mistaken for column codes and poison the topological order).
            formula_src = record.excel_formula
            if 'BRACKET' in formula_src.upper() and record.config_id:
                formula_src = record.env['hr.formula.rate.table'].expand_brackets(
                    formula_src, record.config_id)

            # Extract column references - both with row numbers (A1, B2) and without (A, B, C)
            # Also extract CODE references (BASIC, GROSS, etc.)
            formula = formula_src.upper()
            formula_no_strings = record._strip_string_literals(formula)

            range_refs = []
            try:
                from ..formula_engine.column_manager import ColumnManager

                for start_col, end_col in re.findall(
                    r'\$?([A-Z]+)\$?\d+\s*:\s*\$?([A-Z]+)\$?\d+',
                    formula_no_strings
                ):
                    try:
                        start_idx = ColumnManager.letter_to_index(start_col)
                        end_idx = ColumnManager.letter_to_index(end_col)
                    except Exception:
                        continue
                    if start_idx > end_idx:
                        start_idx, end_idx = end_idx, start_idx
                    for idx in range(start_idx, end_idx + 1):
                        range_refs.append(ColumnManager.index_to_letter(idx))

                for start_col, end_col in re.findall(
                    r'\b([A-Z]{1,3})\s*:\s*([A-Z]{1,3})\b',
                    formula_no_strings
                ):
                    try:
                        start_idx = ColumnManager.letter_to_index(start_col)
                        end_idx = ColumnManager.letter_to_index(end_col)
                    except Exception:
                        continue
                    if start_idx > end_idx:
                        start_idx, end_idx = end_idx, start_idx
                    for idx in range(start_idx, end_idx + 1):
                        range_refs.append(ColumnManager.index_to_letter(idx))
            except Exception:
                range_refs = []

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

            all_refs = range_refs + refs_with_row + refs_no_row + code_refs
            unique_refs = sorted(set(all_refs))
            record.formula_dependencies = ','.join(unique_refs)

    # ==========================================
    # CRUD OVERRIDES
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign sequence to avoid duplicate column letters when adding rows
        manually, and (F111) freeze a permanent letter identity at birth.

        Excel import sets sequence + column_letter explicitly, so both branches
        below no-op for it. Batch-safe: in-batch counters keep siblings created
        in one call from colliding on a sequence or a letter."""
        seq_next = {}   # config_id -> next auto sequence within this batch
        let_next = {}   # config_id -> highest letter number assigned within this batch

        def _base_letter_num(cid, config):
            used = [self._letter_to_num(r.column_letter) for r in config.rule_ids
                    if r.column_letter and not self._is_constant_namespace(r.column_letter)]
            return max(used) if used else 0

        for vals in vals_list:
            cid = vals.get('config_id')
            # sequence: only when unset/default (never override an explicit import
            # order). Count ALL rules — post-F111 every rule carries a forced
            # letter, so an old `forced_column_letter = False` filter would match
            # nothing and pile every new row at sequence 10.
            if cid and vals.get('sequence', 10) == 10:
                if cid not in seq_next:
                    existing = self.env['hr.formula.rule'].search([('config_id', '=', cid)])
                    seq_next[cid] = (max(existing.mapped('sequence')) + 10) if existing else 10
                else:
                    seq_next[cid] += 10
                vals['sequence'] = seq_next[cid]
            # F111 permanent letter: respect an explicit letter/forced letter
            # (import, ZA+ constants); otherwise assign the next letter from a
            # monotonic high-water mark, so a freed letter is never reused.
            if cid and not vals.get('forced_column_letter') and not vals.get('column_letter'):
                config = self.env['hr.formula.config'].browse(cid)
                if config.exists():
                    if cid not in let_next:
                        let_next[cid] = max(config.col_letter_hwm or 0, _base_letter_num(cid, config))
                    let_next[cid] += 1
                    vals['forced_column_letter'] = self._index_to_letter(let_next[cid] - 1)

        records = super(HrFormulaRule, self).create(vals_list)
        # Persist the high-water mark so a freed top letter is NEVER handed out
        # again — derive it from the letters actually assigned (covers both the
        # auto-minted rows above AND explicitly-lettered import rows, which never
        # touched `let_next`). Without this, an Excel/JSON import leaves hwm=0 and
        # the next studio-added component reuses a just-deleted letter (D111.3).
        by_cfg = {}
        for rec in records:
            if rec.config_id and rec.column_letter and not self._is_constant_namespace(rec.column_letter):
                n = self._letter_to_num(rec.column_letter)
                by_cfg[rec.config_id.id] = max(by_cfg.get(rec.config_id.id, 0), n)
        for cid, hwm in by_cfg.items():
            cfg = self.env['hr.formula.config'].browse(cid)
            if cfg.exists() and (cfg.col_letter_hwm or 0) < hwm:
                cfg.sudo().col_letter_hwm = hwm
        return records

    def write(self, vals):
        """F7 capture funnel. Snapshot the OUTGOING state of any rule whose
        versioned fields are about to change, BEFORE the write lands. One row
        per rule per write call; no-op writes and non-versioned-only writes are
        skipped. Callers set `formula_version_reason` in context (edit/bulk/
        fill/import); `skip_formula_version` opts a write out entirely; a mutable
        `formula_version_seen` set in context dedupes multiple writes to the same
        rule within one logical operation (see save_component)."""
        tracked = VERSIONED_FIELDS & set(vals or {})
        if (tracked
                and not self.env.context.get('skip_formula_version')
                and 'hr.formula.rule.version' in self.env):
            reason = self.env.context.get('formula_version_reason', 'edit')
            if reason not in _VALID_VERSION_REASONS:
                reason = 'edit'
            note = self.env.context.get('formula_version_note') or False
            seen = self.env.context.get('formula_version_seen')
            Version = self.env['hr.formula.rule.version'].sudo()
            rows = []
            for rule in self:
                if seen is not None and rule.id in seen:
                    continue
                # skip when the write changes nothing on the tracked fields
                if all(rule._version_field_matches(f, vals) for f in tracked):
                    continue
                rows.append({
                    'rule_id': rule.id,
                    'seq': rule._next_version_seq(),
                    'excel_formula': rule.excel_formula or '',
                    'snapshot_json': json.dumps(rule._version_snapshot()),
                    'reason': reason,
                    'note': note,
                })
                if seen is not None:
                    seen.add(rule.id)
            if rows:
                Version.create(rows)
        return super().write(vals)

    def _version_field_matches(self, fname, vals):
        """True when `fname`'s stored value already equals what the write sets
        (so the write is a no-op for that field)."""
        self.ensure_one()
        field = self._fields[fname]
        return field.convert_to_write(self[fname], self) == vals.get(fname)

    def _next_version_seq(self):
        self.ensure_one()
        last = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', self.id)], order='seq desc', limit=1)
        return (last.seq + 1) if last else 1

    def _version_snapshot(self):
        """Full picture of the versioned + display fields at snapshot time."""
        self.ensure_one()
        return {
            'name': self.name or '',
            'code': self.code or '',
            'category_id': self.category_id.id or False,
            'category_name': self.category_id.name or '',
            'column_type': self.column_type or '',
            'number_format': self.number_format or '',
            'appears_on_payslip': bool(self.appears_on_payslip),
            'column_letter': self.column_letter or '',
            'constant_value': self.constant_value or 0.0,
        }

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
        """Move this column one position left — DISPLAY ONLY (F111/D111.2).
        Letters are frozen; only sequence moves, so no formula is re-pointed."""
        self.ensure_one()
        config = self.config_id
        before = {r.id: r.column_letter for r in config.rule_ids}
        prev_rule = config.rule_ids.filtered(
            lambda r: r.sequence < self.sequence
        ).sorted(key=lambda r: r.sequence, reverse=True)[:1]
        if prev_rule:
            my_seq = self.sequence
            self.sequence = prev_rule.sequence
            prev_rule.sequence = my_seq
        self._assert_letters_frozen(config, before)

    def move_column_right(self):
        """Move this column one position right — DISPLAY ONLY (F111/D111.2)."""
        self.ensure_one()
        config = self.config_id
        before = {r.id: r.column_letter for r in config.rule_ids}
        next_rule = config.rule_ids.filtered(
            lambda r: r.sequence > self.sequence
        ).sorted(key=lambda r: r.sequence)[:1]
        if next_rule:
            my_seq = self.sequence
            self.sequence = next_rule.sequence
            next_rule.sequence = my_seq
        self._assert_letters_frozen(config, before)

    def reorder_to_position(self, new_sequence):
        """Reorder this column to a new display position — DISPLAY ONLY
        (F111/D111.2). Only sequence changes; column letters stay frozen."""
        self.ensure_one()
        config = self.config_id
        old_seq = self.sequence
        if new_sequence == old_seq:
            return True
        before = {r.id: r.column_letter for r in config.rule_ids}
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        if new_sequence > old_seq:
            for rule in rules:
                if old_seq < rule.sequence <= new_sequence:
                    rule.sequence -= 1
        else:
            for rule in rules:
                if new_sequence <= rule.sequence < old_seq:
                    rule.sequence += 1
        self.sequence = new_sequence
        self._assert_letters_frozen(config, before)
        return True

    # ==========================================
    # CONSTRAINTS
    # ==========================================
    # Odoo 19: legacy _sql_constraints is silently IGNORED (model_classes.py
    # logs "no longer supported") — constraints must be models.Constraint
    # class attributes or they never reach the database (ledger C9).
    _code_config_uniq = models.Constraint(
        'unique(code, config_id)',
        'Rule code must be unique within the configuration!')

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
            return self._run_formula(values, self.excel_formula, write_diagnostics=True)

        return 0.0

    def _run_formula(self, values, excel_formula, write_diagnostics=True):
        """Core formula evaluation, factored out of ``evaluate`` so the F8
        simulation overlay can evaluate a *draft* formula for a rule without
        persisting it (D8.2 — draft evaluation is an overlay, never a write).

        ``excel_formula`` is the formula text to run (``self.excel_formula`` for
        a normal evaluation, or a candidate draft for a simulation). When
        ``write_diagnostics`` is False the ``excel_formula_converted`` /
        ``has_evaluation_error`` side-effect writes are suppressed so overlay
        evaluation never mutates the rule record."""
        self.ensure_one()
        if self.column_type == 'formula':
            if not excel_formula:
                _logger.warning(f"No Excel formula defined for {self.code}, returning 0")
                return 0.0

            # ALWAYS compute Python formula fresh to ensure latest conversion logic
            # The cached python_formula field may have been computed with old buggy logic
            try:
                column_map = {}
                for rule in self.config_id.rule_ids:
                    if rule.column_letter and rule.code:
                        column_map[rule.column_letter] = rule.code
                python_code = self._convert_excel_to_python(excel_formula, column_map)

                # Store the converted Python code for debugging
                if write_diagnostics:
                    self.excel_formula_converted = python_code

                # Enhanced logging for debugging IFERROR and other formula issues
                _logger.debug(f"=== Formula Evaluation for {self.code} ===")
                _logger.debug(f"  Excel formula: {self.excel_formula}")
                _logger.debug(f"  Python code: {python_code}")
                _logger.debug(f"  Column map: {column_map}")
            except Exception as e:
                error_msg = f"Error converting formula: {str(e)}\nExcel formula: {excel_formula}"
                _logger.error(f"Error converting formula for {self.code}: {e}")

                # Store the error information
                if write_diagnostics:
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
                # Arithmetic-context coercion — single source of truth shared
                # with FormulaEvaluator so the two paths cannot drift.
                safe_value = excel_semantics.coerce_value

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

                if '"' in (excel_formula or '') or "raw_values" in python_code:
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
                    _logger.debug(
                        "Formula eval debug: code=%s excel=%s python=%s refs=%s",
                        self.code,
                        excel_formula,
                        python_code,
                        ref_values,
                    )

                # Reject anything the converter never emits (ORM/interpreter
                # tokens) BEFORE eval — formula text is user input.
                excel_semantics.assert_safe_expression(python_code)

                # safe_context goes in as GLOBALS (not locals): the IFERROR
                # lambda resolves free names via its globals at call time, so
                # names passed only as eval locals would NameError inside it.
                eval_globals = dict(safe_context)
                eval_globals["__builtins__"] = {}
                result = eval(python_code, eval_globals)
                _logger.debug(f"  Result: {result}")

                # Clear any previous errors on successful evaluation
                if write_diagnostics and self.has_evaluation_error:
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
                error_details.append(f"\nExcel formula: {excel_formula}")
                error_details.append(f"\nPython code: {python_code}")
                error_details.append(f"\nError type: {type(e).__name__}")
                error_details.append(f"\nError message: {str(e)}")
                error_details.append(f"\nAvailable values: {', '.join(list(values.keys())[:10])}")
                if len(values.keys()) > 10:
                    error_details.append(f"... and {len(values.keys()) - 10} more")

                error_msg = '\n'.join(error_details)

                _logger.error(f"Formula evaluation error for {self.code}")
                _logger.error(f"  Excel formula: {excel_formula}")
                _logger.error(f"  Python code: {python_code}")
                _logger.error(f"  Error: {e}")
                _logger.error(f"  Available values: {list(values.keys())}")

                # Store the error information
                if write_diagnostics:
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
                    _logger.debug(f"Regenerated Python formula for {rule.code}: {python_code}")
                except Exception as e:
                    _logger.error(f"Failed to regenerate formula for {rule.code}: {e}")

    def _if(self, condition, true_val, false_val=0):
        """Excel IF function implementation"""
        return true_val if condition else false_val

    def _isblank_value(self, value):
        """Return True when a raw value should be treated as blank."""
        return excel_semantics.is_blank_value(value)

    def _coerce_number(self, value):
        """Convert a value to float for numeric functions, ignoring non-numeric text."""
        return excel_semantics.coerce_number(value)

    def _sumlist(self, values_list):
        """Excel SUM that ignores non-numeric values."""
        return excel_semantics.sum_list(values_list)

    def _maxlist(self, values_list):
        """Excel MAX that ignores non-numeric values."""
        return excel_semantics.max_list(values_list)

    def _minlist(self, values_list):
        """Excel MIN that ignores non-numeric values."""
        return excel_semantics.min_list(values_list)

    def _avg(self, values_list):
        """Excel AVERAGE function implementation"""
        return excel_semantics.avg_list(values_list)

    def _counta(self, values_list):
        """Excel COUNTA function implementation (counts non-empty values)."""
        if values_list is not None and not isinstance(values_list, (list, tuple)):
            return 0 if values_list in (None, '') else 1
        return excel_semantics.counta_list(values_list)

    def _iferror(self, value, error_value):
        """Excel IFERROR — the converter passes the first argument as a
        lambda so real evaluation errors (#DIV/0!…) are caught, like Excel."""
        return excel_semantics.excel_iferror(value, error_value)

    def _isblank(self, value):
        """Excel ISBLANK function implementation"""
        return excel_semantics.excel_isblank(value)

    def _round(self, number, digits=0):
        """Excel ROUND — half away from zero (Python round() is banker's)."""
        return excel_semantics.excel_round(number, digits)

    def _ceiling(self, number, significance=1):
        """Excel CEILING(number, significance) — round up to a multiple."""
        return excel_semantics.excel_ceiling(number, significance)

    def _floor(self, number, significance=1):
        """Excel FLOOR(number, significance) — round down to a multiple."""
        return excel_semantics.excel_floor(number, significance)

    def _not(self, value):
        """Excel NOT as a call (keeps precedence: NOT(x)*5)."""
        return excel_semantics.excel_not(value)

    def _streq(self, left, right):
        """Excel text equality: case-insensitive, trimmed."""
        return excel_semantics.excel_streq(left, right)

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
        """Excel ROUNDUP — away from zero (math.ceil is wrong for negatives
        and float-multiply corrupts exact values like ROUNDUP(1.2, 1))."""
        return excel_semantics.excel_roundup(number, decimals)

    def _rounddown(self, number, decimals=0):
        """Excel ROUNDDOWN — toward zero."""
        return excel_semantics.excel_rounddown(number, decimals)
