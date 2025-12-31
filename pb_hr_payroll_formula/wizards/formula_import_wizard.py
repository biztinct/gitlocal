# -*- coding: utf-8 -*-
"""
Formula Import Wizard - Import formula configuration from various sources.
"""

import base64
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class FormulaImportWizard(models.TransientModel):
    _name = 'hr.formula.import.wizard'
    _description = 'Formula Configuration Import Wizard'

    config_id = fields.Many2one(
        'hr.formula.config',
        string='Target Configuration',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )

    import_source = fields.Selection([
        ('salary_rules', 'From Existing Salary Rules'),
        ('structure', 'From Payroll Structure'),
        ('json', 'From JSON File'),
        ('excel', 'From Excel File'),
    ], string='Import Source', default='salary_rules', required=True)

    # For salary rules source
    salary_rule_ids = fields.Many2many(
        'hr.salary.rule',
        string='Salary Rules',
    )

    # For structure source
    structure_id = fields.Many2one(
        'hr.payroll.structure',
        string='Payroll Structure',
    )

    # For file sources
    import_file = fields.Binary('Import File')
    import_filename = fields.Char('Filename')

    # Options
    create_input_columns = fields.Boolean(
        'Create Input Columns',
        default=True,
        help="Create input columns for salary rules that use inputs",
    )
    preserve_existing = fields.Boolean(
        'Preserve Existing Rules',
        default=True,
        help="Keep existing rules in the configuration",
    )
    map_categories = fields.Boolean(
        'Map Categories',
        default=True,
        help="Preserve salary rule categories",
    )

    @api.onchange('import_source')
    def _onchange_import_source(self):
        """Clear fields when source changes."""
        self.salary_rule_ids = False
        self.structure_id = False
        self.import_file = False
        self.import_filename = False

    @api.onchange('structure_id')
    def _onchange_structure_id(self):
        """Load salary rules from selected structure."""
        if self.structure_id:
            self.salary_rule_ids = self.structure_id.rule_ids

    def action_import(self):
        """Execute import based on selected source."""
        self.ensure_one()

        if self.import_source == 'salary_rules':
            return self._import_from_salary_rules()
        elif self.import_source == 'structure':
            return self._import_from_structure()
        elif self.import_source == 'json':
            return self._import_from_json()
        elif self.import_source == 'excel':
            return self._import_from_excel()
        else:
            raise UserError(_("Invalid import source"))

    def _import_from_salary_rules(self):
        """Import from selected salary rules."""
        if not self.salary_rule_ids:
            raise UserError(_("Please select salary rules to import"))

        if not self.preserve_existing:
            self.config_id.rule_ids.unlink()

        # Get existing sequence
        max_sequence = max(
            self.config_id.rule_ids.mapped('sequence') or [0]
        )

        created_rules = self.env['hr.formula.rule']

        for rule in self.salary_rule_ids.sorted('sequence'):
            # Check if rule already exists
            existing = self.config_id.rule_ids.filtered(
                lambda r: r.code == rule.code or r.salary_rule_id == rule
            )
            if existing:
                continue

            max_sequence += 10

            # Determine column type
            column_type = 'formula'
            excel_formula = ''
            constant_value = 0.0

            if rule.amount_select == 'fix':
                column_type = 'constant'
                constant_value = rule.amount_fix
            elif rule.amount_select == 'percentage':
                column_type = 'formula'
                # Create formula from percentage
                if rule.amount_percentage_base:
                    excel_formula = f"={rule.amount_percentage_base}*{rule.amount_percentage/100}"

            # Create formula rule
            values = {
                'config_id': self.config_id.id,
                'salary_rule_id': rule.id,
                'name': rule.name,
                'code': rule.code,
                'sequence': max_sequence,
                'column_type': column_type,
                'excel_formula': excel_formula,
                'constant_value': constant_value,
                'category_id': rule.category_id.id if self.map_categories else False,
                'appears_on_payslip': rule.appears_on_payslip,
            }

            created_rules |= self.env['hr.formula.rule'].create(values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%d rules imported successfully') % len(created_rules),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            }
        }

    def _import_from_structure(self):
        """Import from payroll structure."""
        if not self.structure_id:
            raise UserError(_("Please select a payroll structure"))

        self.salary_rule_ids = self.structure_id.rule_ids
        return self._import_from_salary_rules()

    def _import_from_json(self):
        """Import configuration from JSON file."""
        if not self.import_file:
            raise UserError(_("Please upload a JSON file"))

        try:
            content = base64.b64decode(self.import_file).decode('utf-8')
            data = json.loads(content)
        except Exception as e:
            raise UserError(_("Invalid JSON file: %s") % str(e))

        if not self.preserve_existing:
            self.config_id.rule_ids.unlink()

        # Import rules from JSON
        rules_data = data.get('rules', [])
        max_sequence = max(
            self.config_id.rule_ids.mapped('sequence') or [0]
        )

        created_rules = self.env['hr.formula.rule']

        for rule_data in rules_data:
            max_sequence += 10

            values = {
                'config_id': self.config_id.id,
                'name': rule_data.get('name', 'Imported Rule'),
                'code': rule_data.get('code', f'IMPORT_{max_sequence}'),
                'sequence': max_sequence,
                'column_type': rule_data.get('column_type', 'formula'),
                'excel_formula': rule_data.get('excel_formula', ''),
                'constant_value': rule_data.get('constant_value', 0.0),
                'default_value': rule_data.get('default_value', 0.0),
                'number_format': rule_data.get('number_format', 'currency'),
                'decimal_places': rule_data.get('decimal_places', 2),
            }

            created_rules |= self.env['hr.formula.rule'].create(values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%d rules imported from JSON') % len(created_rules),
                'type': 'success',
                'sticky': False,
            }
        }

    def _import_from_excel(self):
        """
        Import configuration from Excel file using advanced header detection.

        This method uses the multisheet import logic which:
        - Auto-detects the header row (handles merged cells, category rows)
        - Extracts component types from horizontal merged cells above headers
        - Handles vertical merges (headers spanning multiple rows)
        - Detects formula vs input columns
        - Works for both single and multi-sheet files
        """
        if not self.import_file:
            raise UserError(_("Please upload an Excel file"))

        try:
            import openpyxl
            import io

            content = base64.b64decode(self.import_file)

            # Load workbook twice: once for values, once for formulas
            workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            formula_workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
            sheet = workbook.active
            formula_sheet = formula_workbook.active

        except ImportError:
            raise UserError(_("openpyxl library required. Install with: pip install openpyxl"))
        except Exception as e:
            raise UserError(_("Failed to read Excel file: %s") % str(e))

        # Use advanced header detection
        try:
            from ..formula_engine.header_detector import HeaderDetector
            from ..formula_engine.merged_cell_parser import MergedCellParser
            from openpyxl.utils import get_column_letter, column_index_from_string

            detector = HeaderDetector(sheet)
            header_row, data_start_row, details = detector.detect_header_row()

            _logger.info(
                f"Excel import: detected header_row={header_row}, "
                f"data_start_row={data_start_row}, score={details.get('detection_score', 0):.2f}"
            )

            # Extract component types from merged cells above header
            parser = MergedCellParser(sheet)
            component_types = parser.extract_component_types(header_row)

            # Get headers using advanced detection (handles vertical merges)
            raw_headers = detector.get_headers(header_row)

            _logger.info(f"Excel import: found {len(raw_headers)} raw headers")

            # Check for empty columns between valid columns - just log them, don't error
            # We skip empty columns but preserve original Excel column letters so formulas remain valid
            empty_columns = self._detect_empty_columns_between_valid(raw_headers, sheet, header_row)
            if empty_columns:
                _logger.info(
                    f"Excel import: skipping {len(empty_columns)} empty columns between valid data: "
                    f"{', '.join(empty_columns)}. Original column positions preserved for formula references."
                )

        except UserError:
            raise  # Re-raise UserError without wrapping
        except Exception as e:
            _logger.warning(f"Advanced header detection failed, falling back to row 1: {e}")
            # Fallback to simple row 1 detection
            header_row = 1
            data_start_row = 2
            raw_headers = []
            component_types = {}
            from openpyxl.utils import get_column_letter, column_index_from_string

            for cell in sheet[1]:
                if cell.value:
                    raw_headers.append({
                        'column_letter': get_column_letter(cell.column),
                        'column_index': cell.column - 1,
                        'value': str(cell.value).strip(),
                        'from_vertical_merge': False,
                    })

        if not self.preserve_existing:
            self.config_id.rule_ids.unlink()

        existing_codes = set(self.config_id.rule_ids.mapped('code'))
        max_sequence = max(self.config_id.rule_ids.mapped('sequence') or [0])
        created_rules = self.env['hr.formula.rule']

        # Detect formula columns by checking first few data rows
        formula_columns = {}
        for row_offset in range(min(5, formula_sheet.max_row - data_start_row + 1)):
            check_row = data_start_row + row_offset
            for header in raw_headers:
                col_letter = header.get('column_letter')
                if col_letter and col_letter not in formula_columns:
                    col_idx = column_index_from_string(col_letter)
                    cell = formula_sheet.cell(row=check_row, column=col_idx)
                    if isinstance(cell.value, str) and cell.value.startswith('='):
                        formula_columns[col_letter] = cell.value

        _logger.info(f"Excel import: detected {len(formula_columns)} formula columns: {list(formula_columns.keys())}")

        # Detect colored constant pairs (red label + green value)
        # IMPORTANT: Use formula_sheet (data_only=False) to preserve color information
        # The 'sheet' variable is from data_only=True which strips formatting
        constant_pairs = self._detect_colored_constant_pairs(formula_sheet, header_row)
        _logger.info(f"Excel import: detected {len(constant_pairs)} colored constant pairs")

        # Also scan formulas to find referenced cells above header row that weren't detected by color
        # This catches constants like $CF$3 that may not have the expected colors
        formula_referenced_constants = self._detect_formula_referenced_constants(
            formula_columns, formula_sheet, header_row
        )

        # Add any formula-referenced constants not already detected by color
        detected_cells = {p['original_cell'] for p in constant_pairs}
        for ref_const in formula_referenced_constants:
            if ref_const['original_cell'] not in detected_cells:
                constant_pairs.append(ref_const)
                detected_cells.add(ref_const['original_cell'])
                _logger.info(
                    f"Excel import: added formula-referenced constant at {ref_const['original_cell']} "
                    f"(name='{ref_const['name']}', value={ref_const['value']})"
                )

        _logger.info(f"Excel import: total constant pairs after formula scan: {len(constant_pairs)}")

        # Build cell mapping for formula reference updates
        # Maps original cell reference (e.g., 'CE3') to new column letter (e.g., 'ZA')
        cell_to_column_mapping = {}
        for idx, pair in enumerate(constant_pairs):
            new_col_letter = self._generate_extended_column_letter(idx)
            cell_to_column_mapping[pair['original_cell']] = new_col_letter
            pair['new_column_letter'] = new_col_letter
            _logger.info(
                f"Constant mapping: {pair['original_cell']} -> {new_col_letter} "
                f"(name='{pair['name']}', value={pair['value']})"
            )

        # Update formula columns with new references
        if cell_to_column_mapping:
            updated_formula_columns = {}
            for col_letter, formula in formula_columns.items():
                updated_formula = self._update_formula_references(formula, cell_to_column_mapping)
                updated_formula_columns[col_letter] = updated_formula
            formula_columns = updated_formula_columns

        # Process each header
        for header in raw_headers:
            header_value = header.get('value')
            if not header_value:
                continue

            col_letter = header.get('column_letter')

            # Determine if this is a formula column
            is_formula = col_letter in formula_columns
            column_type = 'formula' if is_formula else 'input'
            excel_formula = formula_columns.get(col_letter, '')

            # Get component type from merged cells
            comp_type = component_types.get(col_letter, '')

            name = str(header_value).strip()
            code = self._generate_code_from_label(name, existing_codes)
            existing_codes.add(code)

            max_sequence += 10
            values = {
                'config_id': self.config_id.id,
                'name': name,
                'code': code,
                'sequence': max_sequence,
                'column_type': column_type,
                'column_letter': col_letter,
                'component_type': comp_type,
                'data_source': 'formula' if is_formula else 'excel',
                'data_source_field': name,
                'number_format': False,
            }
            if excel_formula:
                values['excel_formula'] = excel_formula

            try:
                created = self.env['hr.formula.rule'].create(values)
                created_rules |= created
                _logger.info(
                    f"Excel import: created rule code={code}, name={name}, "
                    f"type={column_type}, component_type={comp_type}"
                )
            except Exception as e:
                _logger.error(
                    f"Excel import: failed to create rule for '{name}' (code={code}): {e}"
                )

        # Create constant rules from colored pairs at the very end
        constant_rules_created = 0
        for pair in constant_pairs:
            name = pair['name']
            code = self._generate_code_from_label(name, existing_codes)
            existing_codes.add(code)

            max_sequence += 10

            # Convert value to float if possible
            try:
                constant_value = float(pair['value'])
            except (ValueError, TypeError):
                constant_value = 0.0
                _logger.warning(
                    f"Could not convert constant value '{pair['value']}' to float for '{name}'"
                )

            values = {
                'config_id': self.config_id.id,
                'name': name,
                'code': code,
                'sequence': max_sequence,
                'column_type': 'constant',
                'forced_column_letter': pair['new_column_letter'],  # Use forced to override auto-compute
                'original_column_letter': pair['original_cell'],  # Store original cell reference
                'component_type': 'Constant',
                'constant_value': constant_value,
                'data_source': 'manual',
                'data_source_field': f"From cell {pair['original_cell']}",
                'number_format': False,
            }

            try:
                created = self.env['hr.formula.rule'].create(values)
                created_rules |= created
                constant_rules_created += 1
                _logger.info(
                    f"Excel import: created constant rule code={code}, name={name}, "
                    f"col={pair['new_column_letter']}, value={constant_value}, "
                    f"original_cell={pair['original_cell']}"
                )
            except Exception as e:
                _logger.error(
                    f"Excel import: failed to create constant rule for '{name}': {e}"
                )

        # Build success message
        msg_parts = [_('%d rules imported from Excel (header row %d)') % (len(created_rules), header_row)]
        if constant_rules_created > 0:
            msg_parts.append(_('%d constant rules added (ZA onwards)') % constant_rules_created)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': ' | '.join(msg_parts),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_download_template(self):
        """Download Excel template for import."""
        try:
            import openpyxl
            import io
            import base64

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Formula Rules"

            # Template format:
            # Row 1: Labels/Names (stop at first blank)
            # Row 2: Values or formulas. Blank/value => input; formula => formula column_type
            headers = ["Basic Salary", "Std Wrk Hrs", "Actual Wrk Hrs", "Overtime Pay", "Net Pay Cap"]
            formulas = ["", "", "", "=C2*1.5", "=IF(D2>15000000,15000000,D2)"]

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = header
                cell.font = openpyxl.styles.Font(bold=True)

            for col, value in enumerate(formulas, 1):
                ws.cell(row=2, column=col).value = value

            # Save to bytes
            output = io.BytesIO()
            wb.save(output)
            content = output.getvalue()

            # Create attachment
            attachment = self.env['ir.attachment'].create({
                'name': 'formula_import_template.xlsx',
                'type': 'binary',
                'datas': base64.b64encode(content),
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

        except ImportError:
            raise UserError(_("openpyxl library required for template generation"))

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _detect_colored_constant_pairs(self, sheet, header_row):
        """
        Detect red/green colored cell pairs that represent constants.

        These are cells where:
        - Left cell has RED font color (component name/label)
        - Right cell has GREEN font color (constant value)

        Note: We check FONT color (text color), not background/fill color,
        as users typically format these constant cells with colored text.

        Args:
            sheet: openpyxl worksheet object
            header_row: The detected header row number

        Returns:
            List of dictionaries with:
            - 'name': Component name from red cell
            - 'value': Constant value from green cell
            - 'original_cell': Cell reference (e.g., 'CE3') for formula replacement
            - 'row': Row number where found
        """
        from openpyxl.utils import get_column_letter

        constant_pairs = []

        def get_cell_color_info(cell):
            """Get detailed color information from a cell for debugging (both font and fill)."""
            info = {
                'has_fill': False, 'fill_type': None, 'fill_rgb': None,
                'has_font': False, 'font_type': None, 'font_rgb': None, 'font_indexed': None, 'font_theme': None
            }
            try:
                # Check fill (background) color
                fill = cell.fill
                if fill:
                    info['has_fill'] = True
                    info['fill_pattern'] = getattr(fill, 'patternType', None)
                    if fill.fgColor:
                        info['fill_type'] = fill.fgColor.type
                        info['fill_rgb'] = str(fill.fgColor.rgb) if fill.fgColor.rgb else None

                # Check font (text) color - THIS IS WHAT WE NEED
                font = cell.font
                if font and font.color:
                    info['has_font'] = True
                    color = font.color
                    info['font_type'] = color.type
                    info['font_rgb'] = str(color.rgb) if color.rgb else None
                    info['font_indexed'] = color.indexed
                    info['font_theme'] = color.theme
                    info['font_tint'] = getattr(color, 'tint', None)
            except Exception as e:
                info['error'] = str(e)
            return info

        def is_red_color(cell, debug_info=None):
            """Check if cell has red FONT color (text color)."""
            try:
                font = cell.font
                if font and font.color:
                    color = font.color
                    # Check for various red color formats
                    if color.type == 'rgb' and color.rgb:
                        rgb = str(color.rgb).upper()
                        # Common red patterns: FF0000, FFFF0000, red variations
                        # Check if red component is high and green/blue are low
                        if len(rgb) >= 6:
                            # Handle ARGB format (8 chars) or RGB format (6 chars)
                            if len(rgb) == 8:
                                r = int(rgb[2:4], 16)
                                g = int(rgb[4:6], 16)
                                b = int(rgb[6:8], 16)
                            else:
                                r = int(rgb[0:2], 16)
                                g = int(rgb[2:4], 16)
                                b = int(rgb[4:6], 16)
                            if debug_info is not None:
                                debug_info['parsed_r'] = r
                                debug_info['parsed_g'] = g
                                debug_info['parsed_b'] = b
                            # Red if R is high and G, B are relatively low
                            # Relaxed thresholds: R > 150, G < 150, B < 150
                            if r > 150 and g < 150 and b < 150:
                                return True
                            # Also check for salmon/light red (common in Excel)
                            if r > 200 and g < 180 and b < 180 and r > g and r > b:
                                return True
                    elif color.type == 'indexed':
                        # Index 2 is typically red in standard palette
                        # Index 10 is also red in some palettes
                        if color.indexed in [2, 10]:
                            return True
                    elif color.type == 'theme':
                        # Theme colors - check tint for reddish colors
                        # Theme 5 is often accent color (could be red)
                        pass
            except Exception as e:
                _logger.debug(f"Error checking red font color: {e}")
            return False

        def is_green_color(cell, debug_info=None):
            """Check if cell has green FONT color (text color)."""
            try:
                font = cell.font
                if font and font.color:
                    color = font.color
                    if color.type == 'rgb' and color.rgb:
                        rgb = str(color.rgb).upper()
                        if len(rgb) >= 6:
                            if len(rgb) == 8:
                                r = int(rgb[2:4], 16)
                                g = int(rgb[4:6], 16)
                                b = int(rgb[6:8], 16)
                            else:
                                r = int(rgb[0:2], 16)
                                g = int(rgb[2:4], 16)
                                b = int(rgb[4:6], 16)
                            if debug_info is not None:
                                debug_info['parsed_r'] = r
                                debug_info['parsed_g'] = g
                                debug_info['parsed_b'] = b
                            # Green if G is high and R, B are relatively low
                            # Relaxed thresholds
                            if g > 150 and r < 150 and b < 150:
                                return True
                            # Also check for yellow-green (common in Excel)
                            if g > 180 and r > 180 and b < 150:
                                return True
                            # Light green variations
                            if g > 200 and g > r and g > b:
                                return True
                    elif color.type == 'indexed':
                        # Index 3 is typically green, 4 is typically blue
                        # Index 11 is also green in some palettes
                        if color.indexed in [3, 11]:
                            return True
                    elif color.type == 'theme':
                        # Theme colors: Excel uses theme indices for accent colors
                        # Theme 9 = Accent 6 (often green in many Excel themes)
                        # Theme 6 = Accent 3 (can also be green)
                        # We accept theme 6, 9 as potential green colors
                        theme_idx = color.theme
                        if theme_idx in [6, 9]:
                            if debug_info is not None:
                                debug_info['theme_match'] = theme_idx
                            return True
            except Exception as e:
                _logger.debug(f"Error checking green font color: {e}")
            return False

        # Search rows above and around header row for colored pairs
        # Also search all rows in case constants are placed elsewhere
        max_row_to_search = min(header_row + 5, sheet.max_row or 1)

        _logger.info(f"=== COLOR DETECTION DEBUG ===")
        _logger.info(f"Header row: {header_row}, searching rows 1 to {max_row_to_search - 1}")
        _logger.info(f"Sheet max_column: {sheet.max_column}")

        for row_num in range(1, max_row_to_search + 1):
            # Skip the main header row and data rows
            if row_num >= header_row:
                continue

            # Scan ALL columns for red/green pairs (constants can be anywhere)
            # Only limit verbose logging to last 20 columns to reduce noise
            log_start_col = max(1, (sheet.max_column or 1) - 20)

            for col_idx in range(1, (sheet.max_column or 1) + 1):
                cell_left = sheet.cell(row=row_num, column=col_idx)
                cell_right = sheet.cell(row=row_num, column=col_idx + 1)

                # Check colors
                is_left_red = is_red_color(cell_left)
                is_right_green = is_green_color(cell_right)

                # Only verbose logging for last 20 columns to reduce noise
                if col_idx >= log_start_col and (cell_left.value is not None or cell_right.value is not None):
                    left_col_letter = get_column_letter(col_idx)
                    right_col_letter = get_column_letter(col_idx + 1)

                    left_color_info = get_cell_color_info(cell_left)
                    right_color_info = get_cell_color_info(cell_right)

                    left_debug = {}
                    right_debug = {}
                    is_red_color(cell_left, left_debug)
                    is_green_color(cell_right, right_debug)

                    _logger.info(
                        f"Row {row_num}, Col {left_col_letter}-{right_col_letter}: "
                        f"left_value='{cell_left.value}', right_value='{cell_right.value}'"
                    )
                    _logger.info(
                        f"  Left FONT color: type={left_color_info.get('font_type')}, "
                        f"rgb={left_color_info.get('font_rgb')}, indexed={left_color_info.get('font_indexed')}, "
                        f"theme={left_color_info.get('font_theme')}"
                    )
                    if left_debug:
                        _logger.info(f"  Left parsed RGB: R={left_debug.get('parsed_r')}, G={left_debug.get('parsed_g')}, B={left_debug.get('parsed_b')}")
                    _logger.info(f"  Left is_red: {is_left_red}")

                    _logger.info(
                        f"  Right FONT color: type={right_color_info.get('font_type')}, "
                        f"rgb={right_color_info.get('font_rgb')}, indexed={right_color_info.get('font_indexed')}, "
                        f"theme={right_color_info.get('font_theme')}"
                    )
                    if right_debug:
                        _logger.info(f"  Right parsed RGB: R={right_debug.get('parsed_r')}, G={right_debug.get('parsed_g')}, B={right_debug.get('parsed_b')}")
                    _logger.info(f"  Right is_green: {is_right_green}")

                if is_left_red and is_right_green:
                    name = cell_left.value
                    value = cell_right.value

                    if name is not None and value is not None:
                        # Get the cell reference for the value cell (green cell)
                        value_col_letter = get_column_letter(col_idx + 1)
                        original_cell_ref = f"{value_col_letter}{row_num}"

                        constant_pairs.append({
                            'name': str(name).strip(),
                            'value': value,
                            'original_cell': original_cell_ref,
                            'original_col_letter': value_col_letter,
                            'original_col_idx': col_idx + 1,
                            'row': row_num,
                        })

                        _logger.info(
                            f"*** FOUND colored constant pair at row {row_num}: "
                            f"name='{name}', value={value}, cell={original_cell_ref}"
                        )

        _logger.info(f"=== END COLOR DETECTION: Found {len(constant_pairs)} pairs ===")
        return constant_pairs

    def _detect_formula_referenced_constants(self, formula_columns, sheet, header_row):
        """
        Scan formulas to find cell references above header row that might be constants.

        This catches constants like $CF$3 that may not have been detected by color.

        Args:
            formula_columns: Dict of column_letter -> formula string
            sheet: openpyxl worksheet (data_only=False to read values)
            header_row: The detected header row number

        Returns:
            List of dictionaries with:
            - 'name': Label from cell to the left, or generated name
            - 'value': The cell value
            - 'original_cell': Cell reference (e.g., 'CF3')
            - 'row': Row number
        """
        import re
        from openpyxl.utils import get_column_letter, column_index_from_string

        found_constants = []
        seen_cells = set()

        # Pattern to match cell references like: CF3, $CF$3, $CF3, CF$3
        cell_ref_pattern = r'\$?([A-Z]+)\$?(\d+)'

        _logger.info(f"=== SCANNING FORMULAS FOR CONSTANT REFERENCES ===")
        _logger.info(f"Header row: {header_row}, scanning for refs to rows 1-{header_row-1}")

        for col_letter, formula in formula_columns.items():
            # Find all cell references in the formula
            matches = re.findall(cell_ref_pattern, formula, re.IGNORECASE)

            for col_match, row_match in matches:
                row_num = int(row_match)
                col_match = col_match.upper()

                # Only consider cells above the header row (constant area)
                if row_num >= header_row:
                    continue

                cell_ref = f"{col_match}{row_num}"

                # Skip if already seen
                if cell_ref in seen_cells:
                    continue
                seen_cells.add(cell_ref)

                # Get the cell value
                try:
                    col_idx = column_index_from_string(col_match)
                    cell = sheet.cell(row=row_num, column=col_idx)
                    value = cell.value

                    if value is None:
                        _logger.debug(f"  Skipping {cell_ref} - no value")
                        continue

                    # Try to get a name from the cell to the left
                    name = None
                    if col_idx > 1:
                        left_cell = sheet.cell(row=row_num, column=col_idx - 1)
                        if left_cell.value and isinstance(left_cell.value, str):
                            name = str(left_cell.value).strip()

                    # Generate a name if none found
                    if not name:
                        name = f"Constant_{col_match}{row_num}"

                    _logger.info(
                        f"  Found formula reference to {cell_ref}: "
                        f"value={value}, name='{name}'"
                    )

                    found_constants.append({
                        'name': name,
                        'value': value,
                        'original_cell': cell_ref,
                        'original_col_letter': col_match,
                        'original_col_idx': col_idx,
                        'row': row_num,
                    })

                except Exception as e:
                    _logger.warning(f"  Error processing cell {cell_ref}: {e}")

        _logger.info(f"=== END FORMULA SCAN: Found {len(found_constants)} constant references ===")
        return found_constants

    def _generate_extended_column_letter(self, index):
        """
        Generate column letters starting from ZA, ZB, ZC, etc.

        Args:
            index: 0-based index (0=ZA, 1=ZB, etc.)

        Returns:
            Column letter string
        """
        # Start from ZA (which is column 677 in Excel, 1-based)
        # ZA = 26*26 + 1 = 677
        base_col = 26 * 26 + 1 + index  # ZA starts at position 677

        result = ""
        col = base_col
        while col > 0:
            col -= 1
            result = chr(col % 26 + ord('A')) + result
            col //= 26

        return result

    def _update_formula_references(self, formula, cell_mapping):
        """
        Update formula to replace original cell references with new column letters.

        Args:
            formula: Excel formula string (e.g., '=A1+CE3*2')
            cell_mapping: Dict mapping original cell refs to new column letters
                         e.g., {'CE3': 'ZA', 'CF5': 'ZB'}

        Returns:
            Updated formula string
        """
        import re

        if not formula or not cell_mapping:
            return formula

        _logger.info(f"=== FORMULA REFERENCE UPDATE ===")
        _logger.info(f"Original formula: {formula}")
        _logger.info(f"Cell mapping: {cell_mapping}")

        updated_formula = formula

        # Sort by length (longest first) to avoid partial replacements
        sorted_refs = sorted(cell_mapping.keys(), key=len, reverse=True)

        for original_ref in sorted_refs:
            new_col = cell_mapping[original_ref]

            # Parse the cell reference to separate column letters from row number
            # Cell refs like: CE3, CE13, ABC123
            cell_match = re.match(r'^([A-Za-z]+)(\d+)$', original_ref)
            if not cell_match:
                _logger.warning(f"Could not parse cell reference: {original_ref}")
                continue

            col_letters = cell_match.group(1)  # e.g., 'CE'
            row_num = cell_match.group(2)      # e.g., '3' or '13'

            # Build pattern to match: CE3, $CE3, CE$3, $CE$3
            # Using proper escaping and optional $ signs
            pattern = r'\$?' + col_letters + r'\$?' + row_num + r'(?![0-9A-Za-z])'

            # For the replacement, we use the new column with row 2 (data row)
            # Since constants are the same for all rows, we reference row 2
            replacement = f"{new_col}2"

            # Check if pattern matches in formula
            matches = re.findall(pattern, updated_formula, flags=re.IGNORECASE)
            _logger.info(f"  Pattern '{pattern}' -> matches found: {matches}")

            # Replace all occurrences
            before = updated_formula
            updated_formula = re.sub(pattern, replacement, updated_formula, flags=re.IGNORECASE)

            if before != updated_formula:
                _logger.info(f"  Replaced '{original_ref}' variants with '{replacement}'")

        if updated_formula != formula:
            _logger.info(f"Updated formula: '{formula}' -> '{updated_formula}'")
        else:
            _logger.info(f"No changes made to formula")

        return updated_formula

    def _detect_empty_columns_between_valid(self, raw_headers, sheet, header_row):
        """
        Detect empty columns between valid columns.

        Args:
            raw_headers: List of header dictionaries with 'column_letter' and 'value' keys
            sheet: openpyxl worksheet object
            header_row: The detected header row number

        Returns:
            List of empty column letters between valid columns, or empty list if none found
        """
        from openpyxl.utils import get_column_letter, column_index_from_string

        if not raw_headers:
            return []

        # Get all column indices that have valid headers
        valid_col_indices = []
        for header in raw_headers:
            col_letter = header.get('column_letter')
            if col_letter and header.get('value'):
                try:
                    col_idx = column_index_from_string(col_letter)
                    valid_col_indices.append(col_idx)
                except Exception:
                    pass

        if len(valid_col_indices) < 2:
            return []

        # Find the range of columns with data
        min_col = min(valid_col_indices)
        max_col = max(valid_col_indices)

        # Check each column between min and max for empty columns
        empty_columns = []
        valid_col_set = set(valid_col_indices)

        for col_idx in range(min_col, max_col + 1):
            if col_idx not in valid_col_set:
                # This column is not in our headers - check if it's truly empty
                col_letter = get_column_letter(col_idx)

                # Check header row
                header_cell = sheet.cell(row=header_row, column=col_idx)
                header_value = header_cell.value

                # Check a few data rows too (to be thorough)
                has_data = False
                for row_offset in range(5):  # Check first 5 data rows
                    data_row = header_row + 1 + row_offset
                    if data_row > (sheet.max_row or 1):
                        break
                    data_cell = sheet.cell(row=data_row, column=col_idx)
                    if data_cell.value is not None:
                        has_data = True
                        break

                # If both header and data are empty, it's an empty column
                if (header_value is None or (isinstance(header_value, str) and not header_value.strip())) and not has_data:
                    empty_columns.append(col_letter)

        return empty_columns

    def _generate_code_from_label(self, label, existing_codes):
        """Create a short unique code (3-10 chars) derived from the label."""
        import re

        base = re.sub(r'[^A-Za-z0-9]', '', label).upper()
        if not base:
            base = 'COL'

        if len(base) < 3:
            base = (base + 'XXX')[:3]
        if len(base) > 10:
            base = base[:10]

        code = base
        suffix = 1
        while code in existing_codes:
            # ensure total length <=10 when adding suffix
            trimmed = base[: max(1, 10 - len(str(suffix)))]
            code = f"{trimmed}{suffix}"
            suffix += 1

        return code
