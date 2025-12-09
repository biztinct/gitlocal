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
        store=True,
        readonly=True,
        help="Auto-assigned Excel-style column letter (A, B, C...Z, AA, AB, etc.)"
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
    # FORMULA (for formula type)
    # ==========================================
    excel_formula = fields.Char(
        string='Excel Formula',
        help="Excel-style formula (e.g., =A1+B1*0.08, =SUM(A1:C1), =IF(A1>1000,B1*0.1,0))"
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

    @api.depends('sequence', 'config_id')
    def _compute_column_letter(self):
        """Compute Excel-style column letter based on sequence order.

        For saved records: compute based on sequence order among saved siblings.
        For unsaved records: show blank (will get letter after save).
        """
        for record in self:
            if not record.config_id:
                # No config - blank
                record.column_letter = ''
            elif not isinstance(record.id, int):
                # Unsaved record - blank until saved
                record.column_letter = ''
            else:
                # Saved record - compute position among saved siblings only
                # Read directly from database to avoid cache issues during editing
                saved_siblings = record.config_id.rule_ids.filtered(
                    lambda r: isinstance(r.id, int)
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
        """Convert Excel formula to Python expression"""
        if not formula or not formula.startswith('='):
            return formula

        result = formula[1:]  # Remove leading '='

        # Replace cell references (e.g., A1, AA1) with variable names
        # Pattern matches column letters followed by row number
        def replace_ref(match):
            col_letter = match.group(1)
            # row_num = match.group(2)  # For now, we use row 1 always
            code = column_map.get(col_letter)
            if code:
                return f"values['{code}']"
            return match.group(0)

        result = re.sub(r'([A-Z]+)(\d+)', replace_ref, result)

        # Replace Excel functions with Python equivalents
        function_map = {
            r'\bSUM\(': 'sum([',
            r'\bAVERAGE\(': 'self._avg([',
            r'\bMIN\(': 'min([',
            r'\bMAX\(': 'max([',
            r'\bABS\(': 'abs(',
            r'\bROUND\(': 'round(',
            r'\bIF\(': 'self._if(',
            r'\bAND\(': 'all([',
            r'\bOR\(': 'any([',
            r'\bNOT\(': 'not(',
            r'\bPOWER\(': 'pow(',
            r'\bSQRT\(': 'math.sqrt(',
            r'\bCEILING\(': 'math.ceil(',
            r'\bFLOOR\(': 'math.floor(',
        }

        for excel_func, python_func in function_map.items():
            result = re.sub(excel_func, python_func, result, flags=re.IGNORECASE)

        # Fix closing brackets for array functions (SUM, MIN, MAX, etc.)
        # This is a simplified approach - full implementation would need proper parsing
        result = self._fix_array_brackets(result)

        return result

    def _fix_array_brackets(self, formula):
        """Fix brackets for functions that were converted to list operations"""
        # Simple fix: for functions converted to list operations,
        # convert comma-separated args to list items
        # e.g., sum([A1, B1, C1) -> sum([A1, B1, C1])

        # Find patterns like "sum([..." and ensure proper closing
        patterns = ['sum([', 'min([', 'max([', 'self._avg([', 'all([', 'any([']
        for pattern in patterns:
            if pattern in formula:
                # Find the matching closing paren and add ]
                start = formula.find(pattern)
                if start != -1:
                    # Count parentheses to find matching close
                    open_count = 0
                    for i, char in enumerate(formula[start:]):
                        if char == '(':
                            open_count += 1
                        elif char == ')':
                            open_count -= 1
                            if open_count == 0:
                                # Insert ] before the closing )
                                pos = start + i
                                formula = formula[:pos] + ']' + formula[pos:]
                                break

        return formula

    @api.depends('excel_formula')
    def _compute_dependencies(self):
        """Extract column dependencies from formula"""
        for record in self:
            if not record.excel_formula:
                record.formula_dependencies = ''
                continue

            # Extract column references
            refs = re.findall(r'([A-Z]+)\d+', record.excel_formula.upper())
            unique_refs = sorted(set(refs))
            record.formula_dependencies = ','.join(unique_refs)

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

        # Check for valid column references
        refs = re.findall(r'([A-Z]+)\d+', self.excel_formula.upper())
        valid_letters = set(self.config_id.rule_ids.mapped('column_letter'))

        for ref in refs:
            if ref not in valid_letters:
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

    # ==========================================
    # EVALUATION
    # ==========================================
    def evaluate(self, values):
        """Evaluate this rule with given values context"""
        self.ensure_one()

        if self.column_type == 'constant':
            return self.constant_value

        if self.column_type == 'input':
            return values.get(self.code, self.default_value)

        if self.column_type == 'formula':
            if not self.python_formula:
                return 0.0

            try:
                # Build safe evaluation context
                safe_context = {
                    'values': values,
                    'self': self,
                    'math': __import__('math'),
                    'sum': sum,
                    'min': min,
                    'max': max,
                    'abs': abs,
                    'round': round,
                    'pow': pow,
                }
                result = eval(self.python_formula, {"__builtins__": {}}, safe_context)
                return float(result) if result is not None else 0.0
            except Exception as e:
                _logger.error(f"Formula evaluation error for {self.code}: {e}")
                return 0.0

        return 0.0

    def _if(self, condition, true_val, false_val):
        """Excel IF function implementation"""
        return true_val if condition else false_val

    def _avg(self, values_list):
        """Excel AVERAGE function implementation"""
        valid_values = [v for v in values_list if v is not None]
        return sum(valid_values) / len(valid_values) if valid_values else 0
