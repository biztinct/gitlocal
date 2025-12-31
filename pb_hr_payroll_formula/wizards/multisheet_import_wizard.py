# -*- coding: utf-8 -*-
"""
Multi-Sheet Import Wizard - Import payroll configuration from multi-worksheet Excel files.

This wizard guides users through importing formula configurations from Excel files
with multiple worksheets, handling:
- Dynamic header row detection
- Component type extraction from merged cells
- Cross-worksheet formula resolution
- Data source mapping for missing fields
"""

import base64
import io
import re
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MultiSheetImportWizard(models.TransientModel):
    """
    Multi-worksheet Excel import wizard for formula configurations.

    Guides users through a 5-step import process:
    1. Upload File - Upload Excel file and analyze worksheets
    2. Select Worksheets - Choose which sheets to include and set main sheet
    3. Review Components - Preview all detected components across sheets
    4. Map Missing Fields - Assign data sources for fields not in Excel
    5. Confirm Import - Review and execute the import
    """
    _name = 'hr.formula.multisheet.import.wizard'
    _description = 'Multi-Sheet Formula Import Wizard'

    # ==========================================
    # WIZARD STATE
    # ==========================================
    state = fields.Selection([
        ('upload', 'Upload File'),
        ('select_sheets', 'Select Worksheets'),
        ('review_components', 'Review Components'),
        ('map_missing', 'Map Missing Fields'),
        ('confirm', 'Confirm Import'),
    ], string='State', default='upload', required=True)

    # ==========================================
    # FILE AND CONFIG
    # ==========================================
    config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        help="Target configuration to import rules into"
    )

    import_file = fields.Binary(
        string='Import File',
        help="Excel file (.xlsx) containing payroll structure"
    )

    import_filename = fields.Char(
        string='Filename'
    )

    # ==========================================
    # WORKSHEET SELECTION
    # ==========================================
    available_sheet_ids = fields.One2many(
        'hr.formula.multisheet.sheet.line',
        'wizard_id',
        string='Available Worksheets'
    )

    main_sheet_name = fields.Char(
        string='Main Worksheet',
        help="Primary worksheet containing the main payroll structure"
    )

    # ==========================================
    # PRIMARY KEY
    # ==========================================
    primary_key_column = fields.Char(
        string='Primary Key Column',
        help="Column header used to match rows across worksheets (e.g., 'Employee ID')"
    )

    primary_key_column_letter = fields.Char(
        string='Primary Key Column Letter',
        help="Excel column letter for the primary key"
    )

    # ==========================================
    # COMPONENT PREVIEW
    # ==========================================
    component_preview_ids = fields.One2many(
        'hr.formula.multisheet.component.preview',
        'wizard_id',
        string='Detected Components'
    )

    # ==========================================
    # MISSING FIELDS MAPPING
    # ==========================================
    missing_field_ids = fields.One2many(
        'hr.formula.multisheet.missing.field',
        'wizard_id',
        string='Missing Fields',
        help="Existing formula rules not found in the uploaded Excel file"
    )

    has_missing_fields = fields.Boolean(
        string='Has Missing Fields',
        compute='_compute_has_missing'
    )

    # ==========================================
    # IMPORT OPTIONS
    # ==========================================
    preserve_existing = fields.Boolean(
        string='Preserve Existing Rules',
        default=True,
        help="Keep existing rules and add new ones. If unchecked, existing rules will be replaced."
    )

    merge_duplicates = fields.Boolean(
        string='Merge Duplicate Columns',
        default=True,
        help="Merge columns with the same header as a single component"
    )

    update_existing = fields.Boolean(
        string='Update Existing Rules',
        default=True,
        help="Update existing rules if a matching code is found"
    )

    # ==========================================
    # IMPORT SUMMARY
    # ==========================================
    summary_html = fields.Html(
        string='Import Summary',
        compute='_compute_summary',
        sanitize=False
    )

    import_count = fields.Integer(
        string='Components to Import',
        compute='_compute_import_stats'
    )

    duplicate_count = fields.Integer(
        string='Duplicates Found',
        compute='_compute_import_stats'
    )

    formula_count = fields.Integer(
        string='Formulas Detected',
        compute='_compute_import_stats'
    )

    # ==========================================
    # COMPUTED FIELDS
    # ==========================================
    @api.depends('missing_field_ids')
    def _compute_has_missing(self):
        for rec in self:
            rec.has_missing_fields = bool(rec.missing_field_ids)

    @api.depends('component_preview_ids')
    def _compute_import_stats(self):
        for rec in self:
            previews = rec.component_preview_ids.filtered(lambda p: p.include_in_import)
            rec.import_count = len(previews)
            rec.duplicate_count = len(rec.component_preview_ids.filtered('is_duplicate'))
            rec.formula_count = len(previews.filtered(lambda p: p.column_type == 'formula'))

    @api.depends('component_preview_ids', 'missing_field_ids')
    def _compute_summary(self):
        for rec in self:
            html = "<div class='o_import_summary'>"
            html += f"<p><strong>Components to import:</strong> {rec.import_count}</p>"
            html += f"<p><strong>Formulas detected:</strong> {rec.formula_count}</p>"
            if rec.duplicate_count > 0:
                html += f"<p><strong>Duplicates (to merge):</strong> {rec.duplicate_count}</p>"
            if rec.has_missing_fields:
                html += f"<p><strong>Missing fields to map:</strong> {len(rec.missing_field_ids)}</p>"
            html += "</div>"
            rec.summary_html = html

    # ==========================================
    # STEP 1: UPLOAD FILE
    # ==========================================
    def action_analyze_file(self):
        """Analyze uploaded Excel file and populate sheet list."""
        self.ensure_one()

        if not self.import_file:
            raise UserError(_("Please upload an Excel file first."))

        if not self.import_filename or not self.import_filename.lower().endswith(('.xlsx', '.xls')):
            raise UserError(_("Please upload a valid Excel file (.xlsx or .xls)"))

        try:
            file_content = base64.b64decode(self.import_file)

            # Use Excel connector for multi-sheet loading
            from ..integrations import ExcelConnector
            connector = ExcelConnector(None)
            workbook_data = connector.load_workbook_multisheet(file_content)

            # Clear existing sheet lines
            self.available_sheet_ids.unlink()

            # Create sheet lines
            sheet_lines = []
            for idx, sheet_name in enumerate(workbook_data['sheet_names']):
                sheet_info = workbook_data['sheets'][sheet_name]
                sheet_lines.append((0, 0, {
                    'wizard_id': self.id,
                    'sheet_name': sheet_name,
                    'is_selected': True,
                    'is_main_sheet': sheet_name == workbook_data['active_sheet'],
                    'detected_header_row': sheet_info.get('detected_header_row', 1),
                    'column_count': sheet_info.get('max_column', 0),
                    'row_count': sheet_info.get('max_row', 0) - sheet_info.get('detected_data_start_row', 2) + 1,
                    'has_formulas': sheet_info.get('has_formulas', False),
                    'references_other_sheets': sheet_info.get('references_other_sheets', False),
                    'header_confidence': sheet_info.get('header_detection_confidence', 0.0),
                }))

            self.write({
                'available_sheet_ids': sheet_lines,
                'main_sheet_name': workbook_data['active_sheet'],
                'state': 'select_sheets',
            })

            return self._return_wizard_action()

        except Exception as e:
            _logger.exception("Failed to analyze Excel file")
            raise UserError(_("Failed to analyze file: %s") % str(e))

    # ==========================================
    # STEP 2: SELECT WORKSHEETS
    # ==========================================
    def action_process_sheets(self):
        """Process selected sheets and generate component preview."""
        self.ensure_one()

        selected_sheets = self.available_sheet_ids.filtered('is_selected')
        if not selected_sheets:
            raise UserError(_("Please select at least one worksheet."))

        main_sheets = selected_sheets.filtered('is_main_sheet')
        if not main_sheets:
            raise UserError(_("Please designate one worksheet as the main sheet."))

        if len(main_sheets) > 1:
            raise UserError(_("Only one worksheet can be designated as the main sheet."))

        self.main_sheet_name = main_sheets[0].sheet_name

        try:
            file_content = base64.b64decode(self.import_file)

            from ..integrations import ExcelConnector
            connector = ExcelConnector(None)
            workbook_data = connector.load_workbook_multisheet(file_content, include_formulas=True)

            # Load formula workbook for detecting formulas
            import openpyxl
            import io
            formula_workbook = openpyxl.load_workbook(
                io.BytesIO(file_content),
                data_only=False
            )

            # Clear existing previews
            self.component_preview_ids.unlink()

            # Process each selected sheet
            all_components = []
            seen_codes = set()

            _logger.info(f"=== WIZARD: Processing {len(selected_sheets)} selected sheets ===")

            for sheet_line in selected_sheets:
                _logger.info(f"Processing sheet: {sheet_line.sheet_name}")
                sheet_data = connector.load_sheet_with_detection(sheet_line.sheet_name)
                formula_sheet = formula_workbook[sheet_line.sheet_name]

                # Get data rows to detect formula columns
                data_start_row = sheet_data['data_start_row']
                header_row = sheet_data['header_row']

                _logger.info(
                    f"Sheet '{sheet_line.sheet_name}': "
                    f"header_row={header_row}, data_start_row={data_start_row}, "
                    f"headers_count={len(sheet_data['headers'])}, "
                    f"data_rows_count={len(sheet_data['data_rows'])}"
                )

                # Log first few headers for debugging
                for idx, h in enumerate(sheet_data['headers'][:10]):
                    _logger.info(
                        f"  Header {idx}: col={h.get('column_letter')}, "
                        f"value='{h.get('value')}', "
                        f"component_type='{h.get('component_type')}', "
                        f"from_vertical_merge={h.get('from_vertical_merge')}"
                    )

                # Check for empty columns between valid columns
                value_sheet = connector.workbook[sheet_line.sheet_name]
                empty_columns = self._detect_empty_columns_between_valid(
                    sheet_data['headers'], value_sheet, header_row
                )
                # Skip empty columns but preserve original Excel column letters so formulas remain valid
                if empty_columns:
                    _logger.info(
                        f"Excel import: skipping {len(empty_columns)} empty column(s) in sheet '{sheet_line.sheet_name}': "
                        f"{', '.join(empty_columns)}. Original column positions preserved for formula references."
                    )

                # Detect formula columns by checking the first data row
                formula_columns = self._detect_formula_columns(
                    formula_sheet, data_start_row, sheet_data['headers']
                )
                _logger.info(f"  Formula columns detected: {list(formula_columns.keys())}")

                # Detect colored constant pairs (red label + green value)
                # IMPORTANT: Use formula_sheet (data_only=False) to preserve color information
                # The value_sheet is from connector.workbook which uses data_only=True and strips formatting
                constant_pairs = self._detect_colored_constant_pairs(formula_sheet, header_row)
                _logger.info(f"  Colored constant pairs detected: {len(constant_pairs)}")

                # Also scan formulas to find referenced cells above header row that weren't detected by color
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
                            f"  Added formula-referenced constant at {ref_const['original_cell']} "
                            f"(name='{ref_const['name']}', value={ref_const['value']})"
                        )

                _logger.info(f"  Total constant pairs after formula scan: {len(constant_pairs)}")

                # Build cell mapping for formula reference updates
                cell_to_column_mapping = {}
                constant_start_index = len([c for c in all_components if c.get('column_type') == 'constant'])
                for idx, pair in enumerate(constant_pairs):
                    new_col_letter = self._generate_extended_column_letter(constant_start_index + idx)
                    cell_to_column_mapping[pair['original_cell']] = new_col_letter
                    pair['new_column_letter'] = new_col_letter
                    _logger.info(
                        f"  Constant mapping: {pair['original_cell']} -> {new_col_letter}"
                    )

                for header_info in sheet_data['headers']:
                    col_letter = header_info['column_letter']

                    # Generate code from header
                    code = self._generate_code(header_info['value'], seen_codes)
                    seen_codes.add(code)

                    # Determine column type based on formula detection
                    column_type = 'input'
                    excel_formula = ''
                    sample_value = ''

                    if col_letter in formula_columns:
                        column_type = 'formula'
                        excel_formula = formula_columns[col_letter].get('formula', '')
                        # Update formula references if we have constant mappings
                        if cell_to_column_mapping:
                            excel_formula = self._update_formula_references(excel_formula, cell_to_column_mapping)

                    # Get sample value from first data row
                    if sheet_data['data_rows']:
                        sample_value = str(sheet_data['data_rows'][0].get(header_info['value'], ''))[:50]

                    # Check if this is a duplicate across sheets
                    is_duplicate = code in [c['generated_code'] for c in all_components]

                    # Determine data source
                    if column_type == 'formula':
                        data_source = 'formula'
                    else:
                        data_source = 'excel'

                    component = {
                        'wizard_id': self.id,
                        'source_sheet': sheet_line.sheet_name,
                        'column_letter': col_letter,
                        'original_header': header_info['value'],
                        'generated_code': code,
                        'generated_name': header_info['value'],
                        'component_type': header_info.get('component_type') or '',
                        'column_type': column_type,
                        'excel_formula': excel_formula,
                        'sample_value': sample_value,
                        'is_duplicate': is_duplicate,
                        'include_in_import': not is_duplicate or sheet_line.is_main_sheet,
                        'is_in_excel': True,
                        'data_source': data_source,
                    }
                    all_components.append(component)

                # Add constant components from colored pairs at the end
                for pair in constant_pairs:
                    code = self._generate_code(pair['name'], seen_codes)
                    seen_codes.add(code)

                    try:
                        constant_value = float(pair['value'])
                    except (ValueError, TypeError):
                        constant_value = 0.0

                    component = {
                        'wizard_id': self.id,
                        'source_sheet': sheet_line.sheet_name,
                        'column_letter': pair['new_column_letter'],
                        'original_header': pair['name'],
                        'generated_code': code,
                        'generated_name': pair['name'],
                        'component_type': 'Constant',
                        'column_type': 'constant',
                        'excel_formula': '',
                        'sample_value': str(constant_value),
                        'is_duplicate': False,
                        'include_in_import': True,
                        'is_in_excel': True,
                        'data_source': 'manual',
                    }
                    all_components.append(component)
                    _logger.info(
                        f"  Added constant component: {code} = {constant_value} "
                        f"(col={pair['new_column_letter']}, from {pair['original_cell']})"
                    )

            # Create component preview records
            _logger.info(f"=== WIZARD: Creating {len(all_components)} component preview records ===")
            for comp in all_components:
                self.env['hr.formula.multisheet.component.preview'].create(comp)

            _logger.info(f"=== WIZARD: Total components created: {len(self.component_preview_ids)} ===")

            self.state = 'review_components'
            return self._return_wizard_action()

        except Exception as e:
            _logger.exception("Failed to process worksheets")
            raise UserError(_("Failed to process worksheets: %s") % str(e))

    def _detect_formula_columns(self, formula_sheet, data_start_row, headers):
        """
        Detect which columns contain formulas.

        A column is considered a formula column if the first data row has
        a formula (starts with =).

        Args:
            formula_sheet: openpyxl sheet loaded with formulas (data_only=False)
            data_start_row: Row where data starts
            headers: List of header info dicts with column_letter

        Returns:
            Dictionary mapping column letter to formula info
        """
        from openpyxl.utils import column_index_from_string

        formula_columns = {}

        # Check first few data rows for formulas
        for row_offset in range(min(5, formula_sheet.max_row - data_start_row + 1)):
            check_row = data_start_row + row_offset

            for header in headers:
                col_letter = header['column_letter']
                if col_letter in formula_columns:
                    continue  # Already identified as formula

                col_idx = column_index_from_string(col_letter)
                cell = formula_sheet.cell(row=check_row, column=col_idx)

                if isinstance(cell.value, str) and cell.value.startswith('='):
                    formula_columns[col_letter] = {
                        'formula': cell.value,
                        'detected_at_row': check_row,
                    }

        return formula_columns

    def _detect_empty_columns_between_valid(self, headers, sheet, header_row):
        """
        Detect empty columns between valid columns.

        Args:
            headers: List of header dictionaries with 'column_letter' and 'value' keys
            sheet: openpyxl worksheet object
            header_row: The detected header row number

        Returns:
            List of empty column letters between valid columns, or empty list if none found
        """
        from openpyxl.utils import get_column_letter, column_index_from_string

        if not headers:
            return []

        # Get all column indices that have valid headers
        valid_col_indices = []
        for header in headers:
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

        def is_red_color(cell):
            """Check if cell has red FONT color (text color)."""
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
                            # Red if R is high and G, B are relatively low
                            if r > 150 and g < 150 and b < 150:
                                return True
                            # Also check for salmon/light red
                            if r > 200 and g < 180 and b < 180 and r > g and r > b:
                                return True
                    elif color.type == 'indexed':
                        if color.indexed in [2, 10]:
                            return True
            except Exception:
                pass
            return False

        def is_green_color(cell):
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
                            # Green if G is high and R, B are relatively low
                            if g > 150 and r < 150 and b < 150:
                                return True
                            # Also check for yellow-green
                            if g > 180 and r > 180 and b < 150:
                                return True
                            # Light green variations
                            if g > 200 and g > r and g > b:
                                return True
                    elif color.type == 'indexed':
                        if color.indexed in [3, 11]:
                            return True
                    elif color.type == 'theme':
                        # Theme colors: Excel uses theme indices for accent colors
                        # Theme 9 = Accent 6 (often green in many Excel themes)
                        # Theme 6 = Accent 3 (can also be green)
                        if color.theme in [6, 9]:
                            return True
            except Exception:
                pass
            return False

        max_row_to_search = min(header_row + 5, sheet.max_row or 1)

        for row_num in range(1, max_row_to_search + 1):
            if row_num >= header_row:
                continue

            for col_idx in range(1, (sheet.max_column or 1)):
                cell_left = sheet.cell(row=row_num, column=col_idx)
                cell_right = sheet.cell(row=row_num, column=col_idx + 1)

                if is_red_color(cell_left) and is_green_color(cell_right):
                    name = cell_left.value
                    value = cell_right.value

                    if name is not None and value is not None:
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
                            f"Found colored constant pair at row {row_num}: "
                            f"name='{name}', value={value}, cell={original_cell_ref}"
                        )

        return constant_pairs

    def _detect_formula_referenced_constants(self, formula_columns, sheet, header_row):
        """
        Scan formulas to find cell references above header row that might be constants.

        This catches constants like $CF$3 that may not have been detected by color.
        """
        import re
        from openpyxl.utils import get_column_letter, column_index_from_string

        found_constants = []
        seen_cells = set()

        # Pattern to match cell references like: CF3, $CF$3, $CF3, CF$3
        cell_ref_pattern = r'\$?([A-Z]+)\$?(\d+)'

        _logger.info(f"  === SCANNING FORMULAS FOR CONSTANT REFERENCES ===")
        _logger.info(f"  Header row: {header_row}, scanning for refs to rows 1-{header_row-1}")

        for col_letter, formula_info in formula_columns.items():
            formula = formula_info.get('formula', '') if isinstance(formula_info, dict) else formula_info
            matches = re.findall(cell_ref_pattern, formula, re.IGNORECASE)

            for col_match, row_match in matches:
                row_num = int(row_match)
                col_match = col_match.upper()

                if row_num >= header_row:
                    continue

                cell_ref = f"{col_match}{row_num}"

                if cell_ref in seen_cells:
                    continue
                seen_cells.add(cell_ref)

                try:
                    col_idx = column_index_from_string(col_match)
                    cell = sheet.cell(row=row_num, column=col_idx)
                    value = cell.value

                    if value is None:
                        continue

                    # Try to get a name from the cell to the left
                    name = None
                    if col_idx > 1:
                        left_cell = sheet.cell(row=row_num, column=col_idx - 1)
                        if left_cell.value and isinstance(left_cell.value, str):
                            name = str(left_cell.value).strip()

                    if not name:
                        name = f"Constant_{col_match}{row_num}"

                    _logger.info(
                        f"    Found formula reference to {cell_ref}: value={value}, name='{name}'"
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
                    _logger.warning(f"    Error processing cell {cell_ref}: {e}")

        _logger.info(f"  === END FORMULA SCAN: Found {len(found_constants)} constant references ===")
        return found_constants

    def _generate_extended_column_letter(self, index):
        """Generate column letters starting from ZA, ZB, ZC, etc."""
        base_col = 26 * 26 + 1 + index  # ZA starts at position 677

        result = ""
        col = base_col
        while col > 0:
            col -= 1
            result = chr(col % 26 + ord('A')) + result
            col //= 26

        return result

    def _update_formula_references(self, formula, cell_mapping):
        """Update formula to replace original cell references with new column letters."""
        import re

        if not formula or not cell_mapping:
            return formula

        _logger.info(f"=== FORMULA REFERENCE UPDATE ===")
        _logger.info(f"Original formula: {formula}")
        _logger.info(f"Cell mapping: {cell_mapping}")

        updated_formula = formula
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
            replacement = f"{new_col}2"

            # Check if pattern matches in formula
            matches = re.findall(pattern, updated_formula, flags=re.IGNORECASE)
            _logger.info(f"  Pattern '{pattern}' -> matches found: {matches}")

            before = updated_formula
            updated_formula = re.sub(pattern, replacement, updated_formula, flags=re.IGNORECASE)

            if before != updated_formula:
                _logger.info(f"  Replaced '{original_ref}' variants with '{replacement}'")

        if updated_formula != formula:
            _logger.info(f"Updated formula: '{formula}' -> '{updated_formula}'")
        else:
            _logger.info(f"No changes made to formula")

        return updated_formula

    # ==========================================
    # STEP 3: REVIEW COMPONENTS
    # ==========================================
    def action_detect_missing_fields(self):
        """Detect fields in existing config that are missing from Excel."""
        self.ensure_one()

        # Get existing rules from config
        existing_rules = self.config_id.rule_ids.filtered(lambda r: r.column_type == 'input')

        # Get codes from Excel components
        excel_codes = set(self.component_preview_ids.mapped('generated_code'))

        # Clear existing missing fields
        self.missing_field_ids.unlink()

        # Find missing rules
        missing = []
        for rule in existing_rules:
            if rule.code not in excel_codes:
                missing.append({
                    'wizard_id': self.id,
                    'existing_rule_id': rule.id,
                    'field_code': rule.code,
                    'field_name': rule.name,
                    'data_source': 'none',
                })

        if missing:
            for m in missing:
                self.env['hr.formula.multisheet.missing.field'].create(m)
            self.state = 'map_missing'
        else:
            self.state = 'confirm'

        return self._return_wizard_action()

    # ==========================================
    # STEP 4: MAP MISSING FIELDS (Optional)
    # ==========================================
    def action_skip_missing(self):
        """Skip missing field mapping and proceed to confirm."""
        self.ensure_one()
        self.state = 'confirm'
        return self._return_wizard_action()

    def action_apply_missing_mapping(self):
        """Apply missing field mappings and proceed to confirm."""
        self.ensure_one()
        # Mappings are already stored in missing_field_ids
        self.state = 'confirm'
        return self._return_wizard_action()

    # ==========================================
    # STEP 5: CONFIRM AND EXECUTE
    # ==========================================
    def action_execute_import(self):
        """Execute the import and create formula rules."""
        self.ensure_one()

        try:
            components_to_import = self.component_preview_ids.filtered('include_in_import')

            if not components_to_import:
                raise UserError(_("No components selected for import."))

            created_rules = []
            updated_rules = []

            # Process each component
            for comp in components_to_import:
                existing_rule = self.config_id.rule_ids.filtered(
                    lambda r: r.code == comp.generated_code
                )

                rule_vals = {
                    'config_id': self.config_id.id,
                    'name': comp.generated_name,
                    'code': comp.generated_code,
                    'column_type': comp.column_type,
                    'component_type': comp.component_type,
                    'source_sheet_name': comp.source_sheet,
                    'original_column_letter': comp.column_letter,
                    'data_source': comp.data_source,
                }

                if comp.column_type == 'formula' and comp.excel_formula:
                    rule_vals['excel_formula'] = comp.excel_formula

                # Handle constant components (from colored cell pairs)
                # Use forced_column_letter for constants to preserve ZA, ZB, etc.
                if comp.column_type == 'constant':
                    rule_vals['forced_column_letter'] = comp.column_letter
                    if comp.sample_value:
                        try:
                            rule_vals['constant_value'] = float(comp.sample_value)
                        except (ValueError, TypeError):
                            rule_vals['constant_value'] = 0.0

                if comp.data_source == 'integration' and comp.integration_connector_id:
                    rule_vals['integration_connector_id'] = comp.integration_connector_id.id
                    rule_vals['source_field_mapping'] = comp.integration_field_name

                if existing_rule and self.update_existing:
                    existing_rule.write(rule_vals)
                    updated_rules.append(existing_rule)
                elif not existing_rule:
                    new_rule = self.env['hr.formula.rule'].create(rule_vals)
                    created_rules.append(new_rule)

            # Update missing fields with their data source settings
            for missing in self.missing_field_ids:
                if missing.existing_rule_id:
                    update_vals = {'data_source': missing.data_source}
                    if missing.data_source == 'integration' and missing.integration_connector_id:
                        update_vals['integration_connector_id'] = missing.integration_connector_id.id
                        update_vals['source_field_mapping'] = missing.integration_field_name

                    missing.existing_rule_id.write(update_vals)

            # Return success notification
            message = _(
                "Import completed successfully!\n"
                "Created: %d rules\n"
                "Updated: %d rules"
            ) % (len(created_rules), len(updated_rules))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Complete'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'hr.formula.config',
                        'res_id': self.config_id.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }
                }
            }

        except Exception as e:
            _logger.exception("Import execution failed")
            raise UserError(_("Import failed: %s") % str(e))

    # ==========================================
    # NAVIGATION HELPERS
    # ==========================================
    def action_back(self):
        """Navigate to previous step."""
        self.ensure_one()
        state_order = ['upload', 'select_sheets', 'review_components', 'map_missing', 'confirm']
        current_idx = state_order.index(self.state)
        if current_idx > 0:
            # Skip map_missing if no missing fields
            new_idx = current_idx - 1
            if state_order[new_idx] == 'map_missing' and not self.has_missing_fields:
                new_idx -= 1
            self.state = state_order[max(0, new_idx)]
        return self._return_wizard_action()

    def _return_wizard_action(self):
        """Return action to continue showing the wizard."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _generate_code(self, header: str, existing_codes: set) -> str:
        """Generate a unique code from header value."""
        header_str = str(header).strip()

        if header_str.isdigit():
            base_code = f'COL_{header_str}'
        else:
            base_code = re.sub(r'[^A-Za-z0-9]', '', header_str).upper()
            if not base_code:
                base_code = 'UNNAMED'

        code = base_code
        suffix = 1
        while code in existing_codes:
            code = f"{base_code}_{suffix}"
            suffix += 1

        return code


class MultiSheetSheetLine(models.TransientModel):
    """Sheet line for multi-sheet import wizard."""
    _name = 'hr.formula.multisheet.sheet.line'
    _description = 'Multi-Sheet Import Sheet Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True
    )

    sequence = fields.Integer(default=10)

    sheet_name = fields.Char(
        string='Sheet Name',
        readonly=True
    )

    is_selected = fields.Boolean(
        string='Include',
        default=True
    )

    is_main_sheet = fields.Boolean(
        string='Main Sheet',
        default=False
    )

    detected_header_row = fields.Integer(
        string='Header Row',
        default=1
    )

    column_count = fields.Integer(
        string='Columns',
        readonly=True
    )

    row_count = fields.Integer(
        string='Data Rows',
        readonly=True
    )

    has_formulas = fields.Boolean(
        string='Has Formulas',
        readonly=True
    )

    references_other_sheets = fields.Boolean(
        string='Cross-Sheet Refs',
        readonly=True
    )

    header_confidence = fields.Float(
        string='Detection Confidence',
        readonly=True
    )

    @api.onchange('is_main_sheet')
    def _onchange_is_main_sheet(self):
        """Ensure only one sheet can be main."""
        if self.is_main_sheet:
            # Unset other sheets
            for line in self.wizard_id.available_sheet_ids:
                if line.id != self.id:
                    line.is_main_sheet = False
            # Main sheet must be selected
            self.is_selected = True


class MultiSheetComponentPreview(models.TransientModel):
    """Component preview line for multi-sheet import wizard."""
    _name = 'hr.formula.multisheet.component.preview'
    _description = 'Multi-Sheet Import Component Preview'
    _order = 'source_sheet, column_letter'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True
    )

    source_sheet = fields.Char(
        string='Source Sheet',
        readonly=True
    )

    column_letter = fields.Char(
        string='Column',
        readonly=True
    )

    original_header = fields.Char(
        string='Header',
        readonly=True
    )

    generated_code = fields.Char(
        string='Code'
    )

    generated_name = fields.Char(
        string='Name'
    )

    component_type = fields.Char(
        string='Component Type',
        help="Category from merged cell above header"
    )

    column_type = fields.Selection([
        ('input', 'Input'),
        ('formula', 'Formula'),
        ('constant', 'Constant')
    ], string='Type', default='input')

    excel_formula = fields.Char(
        string='Excel Formula'
    )

    resolved_formula = fields.Char(
        string='Resolved Formula',
        help="Formula with cross-sheet references resolved"
    )

    is_duplicate = fields.Boolean(
        string='Duplicate',
        readonly=True
    )

    include_in_import = fields.Boolean(
        string='Include',
        default=True
    )

    sample_value = fields.Char(
        string='Sample'
    )

    is_in_excel = fields.Boolean(
        string='In Excel',
        default=True,
        readonly=True
    )

    data_source = fields.Selection([
        ('excel', 'Excel Import'),
        ('formula', 'Formula (Calculated)'),
        ('integration', 'Integration'),
        ('none', 'Not Populated'),
    ], string='Data Source', default='excel')

    integration_connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Integration',
        domain="[('connection_status', '=', 'connected')]"
    )

    integration_field_name = fields.Char(
        string='Integration Field'
    )


class MultiSheetMissingField(models.TransientModel):
    """Missing field line for data source mapping."""
    _name = 'hr.formula.multisheet.missing.field'
    _description = 'Multi-Sheet Import Missing Field'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True
    )

    existing_rule_id = fields.Many2one(
        'hr.formula.rule',
        string='Existing Rule',
        readonly=True
    )

    field_code = fields.Char(
        string='Code',
        readonly=True
    )

    field_name = fields.Char(
        string='Name',
        readonly=True
    )

    data_source = fields.Selection([
        ('none', 'Not Populated'),
        ('integration', 'From Integration'),
        ('manual', 'Manual Entry'),
    ], string='Data Source', default='none', required=True)

    integration_connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Integration Connector',
        domain="[('connection_status', '=', 'connected')]"
    )

    integration_field_name = fields.Char(
        string='Integration Field'
    )

    @api.onchange('data_source')
    def _onchange_data_source(self):
        """Clear integration fields if not using integration."""
        if self.data_source != 'integration':
            self.integration_connector_id = False
            self.integration_field_name = False
