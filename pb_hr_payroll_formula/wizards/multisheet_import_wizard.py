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
        ('select_columns', 'Select Columns'),
        ('configure_order', 'Configure Order'),
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
    # COLUMN SELECTION (Step 3)
    # ==========================================
    column_selection_ids = fields.One2many(
        'hr.formula.multisheet.column.selection',
        'wizard_id',
        string='Column Selections',
        help="Columns available for selection from each worksheet"
    )

    # ==========================================
    # APPEND ORDER (Step 4)
    # ==========================================
    append_order_ids = fields.One2many(
        'hr.formula.multisheet.append.order',
        'wizard_id',
        string='Append Order',
        help="Order in which worksheets are appended to form the final structure"
    )

    # ==========================================
    # CROSS-SHEET RESOLUTION STATS
    # ==========================================
    cross_sheet_formula_count = fields.Integer(
        string='Cross-Sheet Formulas',
        compute='_compute_cross_sheet_stats'
    )

    resolved_formula_count = fields.Integer(
        string='Resolved Formulas',
        compute='_compute_cross_sheet_stats'
    )

    unresolved_formula_count = fields.Integer(
        string='Unresolved Formulas',
        compute='_compute_cross_sheet_stats'
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

    @api.depends('component_preview_ids')
    def _compute_cross_sheet_stats(self):
        """Compute statistics about cross-sheet formula resolution."""
        for rec in self:
            formula_previews = rec.component_preview_ids.filtered(
                lambda p: p.column_type == 'formula' and p.excel_formula
            )
            # Count formulas with cross-sheet references (contain '!' pattern)
            cross_sheet = formula_previews.filtered(
                lambda p: "!" in (p.excel_formula or '')
            )
            rec.cross_sheet_formula_count = len(cross_sheet)
            # Resolved = has resolved_formula and it's different from original
            resolved = cross_sheet.filtered(
                lambda p: p.resolved_formula and p.resolved_formula != p.excel_formula
            )
            rec.resolved_formula_count = len(resolved)
            rec.unresolved_formula_count = rec.cross_sheet_formula_count - rec.resolved_formula_count

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
            # Explicitly load with formulas to detect cross-sheet references
            workbook_data = connector.load_workbook_multisheet(file_content, include_formulas=True)

            # Clear existing sheet lines
            self.available_sheet_ids.unlink()

            # Create sheet lines
            sheet_lines = []
            for idx, sheet_name in enumerate(workbook_data['sheet_names']):
                sheet_info = workbook_data['sheets'][sheet_name]

                # Format referenced sheet names as comma-separated string
                referenced_sheets = sheet_info.get('formulas_referencing_sheets', [])
                referenced_sheet_names = ', '.join(referenced_sheets) if referenced_sheets else ''

                # Debug logging
                if sheet_info.get('has_formulas'):
                    _logger.info(f"Sheet '{sheet_name}' has formulas: {sheet_info.get('has_formulas')}")
                    _logger.info(f"Sheet '{sheet_name}' references other sheets: {sheet_info.get('references_other_sheets')}")
                    _logger.info(f"Sheet '{sheet_name}' referenced sheets list: {referenced_sheets}")

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
                    'referenced_sheet_names': referenced_sheet_names,
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
    # STEP 2: SELECT WORKSHEETS -> STEP 3: SELECT COLUMNS
    # ==========================================
    def action_process_sheets(self):
        """
        Process selected sheets and populate column selection records.
        Transitions to select_columns state where user can choose columns.
        """
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
            formula_workbook = openpyxl.load_workbook(
                io.BytesIO(file_content),
                data_only=False
            )

            # Clear existing column selections
            self.column_selection_ids.unlink()

            sheet_context = {}
            for sheet_line in selected_sheets:
                sheet_data = connector.load_sheet_with_detection(sheet_line.sheet_name)
                formula_sheet = formula_workbook[sheet_line.sheet_name]
                data_sheet = connector.workbook[sheet_line.sheet_name]
                formula_columns = self._detect_formula_columns(
                    formula_sheet, sheet_data['data_start_row'], sheet_data['headers']
                )
                sheet_context[sheet_line.id] = {
                    'sheet_data': sheet_data,
                    'formula_sheet': formula_sheet,
                    'data_sheet': data_sheet,
                    'formula_columns': formula_columns,
                }

            constant_lines = []
            constant_cell_mapping = {}
            constant_index = 0
            for sheet_line in selected_sheets:
                ctx = sheet_context[sheet_line.id]
                sheet_constants = self._collect_constants_for_sheet(
                    ctx['formula_sheet'], ctx['sheet_data'], ctx['formula_columns']
                )
                for const in sheet_constants:
                    cell_ref = const.get('original_cell')
                    if not cell_ref or cell_ref in constant_cell_mapping:
                        continue
                    new_col_letter = self._generate_extended_column_letter(constant_index)
                    constant_index += 1
                    value = const.get('value')
                    parsed_value, _was_pct = self._parse_percentage_value(value)
                    constant_cell_mapping[cell_ref] = new_col_letter
                    constant_lines.append({
                        'wizard_id': self.id,
                        'sheet_line_id': sheet_line.id,
                        'sequence': 10000 + constant_index,
                        'column_letter': new_col_letter,
                        'column_index': 10000 + constant_index,
                        'original_header': const.get('name') or 'Constant',
                        'component_type': 'Constant',
                        'is_selected': True,
                        'column_type': 'constant',
                        'sample_value': str(parsed_value)[:50] if value is not None else '',
                        'has_cross_sheet_ref': False,
                        'cross_sheet_formula': '',
                        'is_referenced_by_main': False,
                        'constant_cell_ref': cell_ref,
                    })

            if constant_cell_mapping:
                for ctx in sheet_context.values():
                    for col_letter, info in ctx['formula_columns'].items():
                        formula = info.get('formula', '')
                        updated = self._update_formula_references(formula, constant_cell_mapping)
                        if updated != formula:
                            info['formula'] = updated

            # Analyze cross-sheet references in main sheet to mark required columns
            main_sheet = main_sheets[0]
            main_ctx = sheet_context[main_sheet.id]
            main_formula_columns = main_ctx['formula_columns']

            # Find all cross-sheet references from main sheet
            cross_sheet_refs = self._extract_cross_sheet_references(main_formula_columns)

            # Process each selected sheet and create column selections
            column_lines = []
            for sheet_line in selected_sheets:
                ctx = sheet_context[sheet_line.id]
                sheet_data = ctx['sheet_data']
                formula_sheet = ctx['formula_sheet']
                data_sheet = ctx['data_sheet']
                formula_columns = ctx['formula_columns']

                for idx, header_info in enumerate(sheet_data['headers']):
                    col_letter = header_info['column_letter']

                    # Check for cross-sheet formula references
                    has_cross_ref = False
                    cross_formula = ''
                    if col_letter in formula_columns:
                        formula_info = formula_columns[col_letter]
                        formula = formula_info.get('formula', '') if isinstance(formula_info, dict) else formula_info
                        # Use improved pattern matching for both quoted and unquoted sheet names
                        # Quoted: 'Sheet Name'!A1, Unquoted: SheetName!A1
                        quoted_refs = re.findall(r"'([^']+)'!", formula)
                        unquoted_refs = re.findall(r"(?<!['\w])([A-Za-z][A-Za-z0-9_\-]*)\s*!", formula)
                        all_refs = quoted_refs + unquoted_refs
                        # Filter out Excel functions
                        valid_refs = [ref for ref in all_refs if ref.upper() not in
                                     ['IF', 'SUM', 'SUMIF', 'AVERAGE', 'COUNT', 'MAX', 'MIN',
                                      'VLOOKUP', 'HLOOKUP', 'INDEX', 'MATCH', 'IFERROR']]
                        has_cross_ref = bool(valid_refs)
                        cross_formula = formula if has_cross_ref else ''

                    # Check if this column is referenced by main sheet
                    is_referenced = self._is_column_referenced(
                        sheet_line.sheet_name, col_letter, idx + 1, cross_sheet_refs
                    )

                    # Get sample value
                    sample = self._get_sample_value(
                        sheet_data, data_sheet, formula_sheet, header_info['value'], col_letter
                    )

                    column_lines.append({
                        'wizard_id': self.id,
                        'sheet_line_id': sheet_line.id,
                        'sequence': idx * 10,
                        'column_letter': col_letter,
                        'column_index': idx,
                        'original_header': header_info['value'],
                        'component_type': header_info.get('component_type') or '',
                        'is_selected': True,  # All columns selected by default
                        'column_type': 'formula' if col_letter in formula_columns else 'input',
                        'sample_value': sample,
                        'has_cross_sheet_ref': has_cross_ref,
                        'cross_sheet_formula': cross_formula,
                        'is_referenced_by_main': is_referenced,
                    })

            column_lines.extend(constant_lines)

            # Create column selection records
            for col_data in column_lines:
                self.env['hr.formula.multisheet.column.selection'].create(col_data)

            self.state = 'select_columns'
            return self._return_wizard_action()

        except Exception as e:
            _logger.exception("Failed to process worksheets")
            raise UserError(_("Failed to process worksheets: %s") % str(e))

    def _extract_cross_sheet_references(self, formula_columns):
        """
        Extract all cross-sheet references from formulas.

        Returns a dict: {sheet_name: [{'col_index': N, 'col_letter': 'XX', 'formula_col': 'YY'}, ...]}
        """
        cross_refs = {}

        # Patterns for VLOOKUP and direct sheet references
        # Quoted patterns - for sheet names with spaces or special chars
        vlookup_quoted_pattern = re.compile(
            r"VLOOKUP\s*\([^,]+,\s*'([^']+)'\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*,\s*(\d+)",
            re.IGNORECASE
        )
        # Unquoted patterns - for simple sheet names
        vlookup_unquoted_pattern = re.compile(
            r"VLOOKUP\s*\([^,]+,\s*([A-Za-z][A-Za-z0-9_\-]*)\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*,\s*(\d+)",
            re.IGNORECASE
        )
        sumif_quoted_pattern = re.compile(
            r"SUMIF\s*\([^,]*'([^']+)'\s*!\s*\$?([A-Z]+)",
            re.IGNORECASE
        )
        sumif_unquoted_pattern = re.compile(
            r"SUMIF\s*\([^,]*([A-Za-z][A-Za-z0-9_\-]*)\s*!\s*\$?([A-Z]+)",
            re.IGNORECASE
        )
        direct_quoted_pattern = re.compile(
            r"'([^']+)'\s*!\s*\$?([A-Z]+)\$?(\d+)",
            re.IGNORECASE
        )
        direct_unquoted_pattern = re.compile(
            r"(?<!['\w])([A-Za-z][A-Za-z0-9_\-]*)\s*!\s*\$?([A-Z]+)\$?(\d+)",
            re.IGNORECASE
        )

        for col_letter, formula_info in formula_columns.items():
            formula = formula_info.get('formula', '') if isinstance(formula_info, dict) else formula_info

            # Find VLOOKUP references (both quoted and unquoted)
            for match in vlookup_quoted_pattern.finditer(formula):
                sheet_name = match.group(1).strip()
                start_col = match.group(2).upper()
                col_index = int(match.group(4))
                start_idx = self._column_letter_to_index(start_col)
                target_idx = start_idx + col_index - 1
                target_col = self._index_to_column_letter(target_idx)

                if sheet_name not in cross_refs:
                    cross_refs[sheet_name] = []
                cross_refs[sheet_name].append({
                    'col_index': target_idx,
                    'col_letter': target_col,
                    'formula_col': col_letter,
                    'type': 'vlookup',
                })

            for match in vlookup_unquoted_pattern.finditer(formula):
                sheet_name = match.group(1).strip()
                start_col = match.group(2).upper()
                col_index = int(match.group(4))
                start_idx = self._column_letter_to_index(start_col)
                target_idx = start_idx + col_index - 1
                target_col = self._index_to_column_letter(target_idx)

                if sheet_name not in cross_refs:
                    cross_refs[sheet_name] = []
                cross_refs[sheet_name].append({
                    'col_index': target_idx,
                    'col_letter': target_col,
                    'formula_col': col_letter,
                    'type': 'vlookup',
                })

            # Find SUMIF references (both quoted and unquoted)
            for match in sumif_quoted_pattern.finditer(formula):
                sheet_name = match.group(1).strip()
                col_letter_ref = match.group(2).upper()
                col_idx = self._column_letter_to_index(col_letter_ref)

                if sheet_name not in cross_refs:
                    cross_refs[sheet_name] = []
                cross_refs[sheet_name].append({
                    'col_index': col_idx,
                    'col_letter': col_letter_ref,
                    'formula_col': col_letter,
                    'type': 'sumif',
                })

            for match in sumif_unquoted_pattern.finditer(formula):
                sheet_name = match.group(1).strip()
                col_letter_ref = match.group(2).upper()
                col_idx = self._column_letter_to_index(col_letter_ref)

                if sheet_name not in cross_refs:
                    cross_refs[sheet_name] = []
                cross_refs[sheet_name].append({
                    'col_index': col_idx,
                    'col_letter': col_letter_ref,
                    'formula_col': col_letter,
                    'type': 'sumif',
                })

            # Find direct references (both quoted and unquoted)
            for match in direct_quoted_pattern.finditer(formula):
                sheet_name = match.group(1).strip()
                col_letter_ref = match.group(2).upper()
                col_idx = self._column_letter_to_index(col_letter_ref)

                if sheet_name not in cross_refs:
                    cross_refs[sheet_name] = []
                cross_refs[sheet_name].append({
                    'col_index': col_idx,
                    'col_letter': col_letter_ref,
                    'formula_col': col_letter,
                    'type': 'direct',
                })

            for match in direct_unquoted_pattern.finditer(formula):
                sheet_name = match.group(1).strip()
                col_letter_ref = match.group(2).upper()
                col_idx = self._column_letter_to_index(col_letter_ref)

                if sheet_name not in cross_refs:
                    cross_refs[sheet_name] = []
                cross_refs[sheet_name].append({
                    'col_index': col_idx,
                    'col_letter': col_letter_ref,
                    'formula_col': col_letter,
                    'type': 'direct',
                })

        return cross_refs

    def _is_column_referenced(self, sheet_name, col_letter, col_index, cross_refs):
        """Check if a column is referenced by main sheet formulas."""
        sheet_name_lower = sheet_name.strip().lower()
        for ref_sheet, refs in cross_refs.items():
            if ref_sheet.strip().lower() == sheet_name_lower:
                for ref in refs:
                    if ref['col_letter'] == col_letter or ref['col_index'] == col_index - 1:
                        return True
        return False

    def _column_letter_to_index(self, col_letter):
        """Convert column letter to 0-based index (A=0, B=1, ...)."""
        result = 0
        for char in col_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    def _index_to_column_letter(self, index):
        """Convert 0-based index to column letter (0=A, 1=B, ...)."""
        result = ""
        idx = index
        while True:
            result = chr(ord('A') + (idx % 26)) + result
            idx = idx // 26 - 1
            if idx < 0:
                break
        return result

    # ==========================================
    # STEP 3: SELECT COLUMNS -> STEP 4: CONFIGURE ORDER
    # ==========================================
    def action_configure_order(self):
        """
        Validate column selection and create append order records.
        Blocks if required columns (referenced by main sheet) are not selected.
        """
        self.ensure_one()

        # Validate: Check all cross-sheet references can be resolved
        validation_errors = self._validate_column_selection()
        if validation_errors:
            error_msg = _("Cannot proceed. The following columns are required by main sheet formulas but are not selected:\n\n")
            for error in validation_errors:
                error_msg += f"• {error['sheet']}: Column {error['col']} ({error['header']}) - used in {error['formula_col']}\n"
            error_msg += _("\nPlease select these columns to continue.")
            raise UserError(error_msg)

        # Clear existing append order
        self.append_order_ids.unlink()

        # Create append order records
        selected_sheets = self.available_sheet_ids.filtered('is_selected')
        order_lines = []

        # Main sheet first (sequence 0)
        main_sheet = selected_sheets.filtered('is_main_sheet')
        if main_sheet:
            order_lines.append({
                'wizard_id': self.id,
                'sheet_line_id': main_sheet.id,
                'append_sequence': 0,
            })

        # Other sheets with sequence 10, 20, 30...
        other_sheets = selected_sheets.filtered(lambda s: not s.is_main_sheet)
        for idx, sheet_line in enumerate(other_sheets.sorted('sheet_name')):
            order_lines.append({
                'wizard_id': self.id,
                'sheet_line_id': sheet_line.id,
                'append_sequence': (idx + 1) * 10,
            })

        # Create records
        for order_data in order_lines:
            self.env['hr.formula.multisheet.append.order'].create(order_data)

        self.state = 'configure_order'
        return self._return_wizard_action()

    def _validate_column_selection(self):
        """
        Validate that all columns referenced by main sheet formulas are selected.
        Returns list of validation errors, empty if valid.
        """
        errors = []
        main_sheet = self.available_sheet_ids.filtered('is_main_sheet')
        if not main_sheet:
            return errors

        # Re-extract cross-sheet references
        try:
            file_content = base64.b64decode(self.import_file)

            from ..integrations import ExcelConnector
            import openpyxl
            connector = ExcelConnector(None)
            connector.load_workbook_multisheet(file_content, include_formulas=True)

            formula_workbook = openpyxl.load_workbook(
                io.BytesIO(file_content),
                data_only=False
            )

            main_formula_sheet = formula_workbook[main_sheet.sheet_name]
            main_data = connector.load_sheet_with_detection(main_sheet.sheet_name)
            main_formula_columns = self._detect_formula_columns(
                main_formula_sheet, main_data['data_start_row'], main_data['headers']
            )
            cross_refs = self._extract_cross_sheet_references(main_formula_columns)

            # Check each reference against selected columns
            for sheet_name, refs in cross_refs.items():
                # Find the sheet line
                sheet_line = self.available_sheet_ids.filtered(
                    lambda s: s.sheet_name.strip().lower() == sheet_name.strip().lower()
                )
                if not sheet_line:
                    continue  # Sheet not even selected

                if not sheet_line.is_selected:
                    # Whole sheet not selected - error
                    for ref in refs:
                        errors.append({
                            'sheet': sheet_name,
                            'col': ref['col_letter'],
                            'header': f"Column {ref['col_letter']}",
                            'formula_col': ref['formula_col'],
                        })
                    continue

                # Check individual columns
                for ref in refs:
                    col_selection = self.column_selection_ids.filtered(
                        lambda c: c.sheet_line_id.id == sheet_line.id and
                                  (c.column_letter == ref['col_letter'] or
                                   c.column_index == ref['col_index'])
                    )
                    if col_selection and not col_selection.is_selected:
                        errors.append({
                            'sheet': sheet_name,
                            'col': ref['col_letter'],
                            'header': col_selection.original_header or f"Column {ref['col_letter']}",
                            'formula_col': ref['formula_col'],
                        })

        except Exception as e:
            _logger.warning(f"Validation failed: {e}")

        return errors

    # ==========================================
    # STEP 4: CONFIGURE ORDER -> STEP 5: REVIEW COMPONENTS
    # ==========================================
    def action_process_with_resolution(self):
        """
        Build final component list with cross-sheet formula resolution.
        Assigns new column letters based on append order.
        """
        self.ensure_one()

        try:
            file_content = base64.b64decode(self.import_file)

            from ..integrations import ExcelConnector
            import openpyxl
            connector = ExcelConnector(None)
            connector.load_workbook_multisheet(file_content, include_formulas=True)

            formula_workbook = openpyxl.load_workbook(
                io.BytesIO(file_content),
                data_only=False
            )

            # Clear existing previews
            self.component_preview_ids.unlink()

            # Build column mapping: (sheet_name, orig_col) -> new_col
            column_mapping = {}
            current_col_index = 0
            all_components = []
            seen_codes = set()
            constant_cell_mapping = {}
            constant_selections = self.column_selection_ids.filtered(
                lambda c: c.is_selected and c.column_type == 'constant' and c.constant_cell_ref
            )
            for const in constant_selections:
                if const.constant_cell_ref not in constant_cell_mapping:
                    constant_cell_mapping[const.constant_cell_ref] = const.column_letter

            # Get sheets in append order
            ordered_sheets = self.append_order_ids.sorted('append_sequence')

            for order_rec in ordered_sheets:
                sheet_line = order_rec.sheet_line_id

                # Get selected columns for this sheet in order
                selected_cols = self.column_selection_ids.filtered(
                    lambda c: c.sheet_line_id.id == sheet_line.id and c.is_selected
                ).sorted('sequence')
                normal_cols = selected_cols.filtered(lambda c: c.column_type != 'constant')
                constant_cols = selected_cols.filtered(lambda c: c.column_type == 'constant')

                sheet_data = connector.load_sheet_with_detection(sheet_line.sheet_name)
                formula_sheet = formula_workbook[sheet_line.sheet_name]

                # Detect formula columns for this sheet
                formula_columns = self._detect_formula_columns(
                    formula_sheet, sheet_data['data_start_row'], sheet_data['headers']
                )
                if constant_cell_mapping:
                    for col_letter, info in formula_columns.items():
                        formula = info.get('formula', '')
                        updated = self._update_formula_references(formula, constant_cell_mapping)
                        if updated != formula:
                            info['formula'] = updated

                for col_sel in normal_cols:
                    # Assign new column letter
                    new_col_letter = self._index_to_column_letter(current_col_index)

                    # Store mapping for cross-sheet resolution
                    sheet_key = sheet_line.sheet_name.strip().lower()
                    column_mapping[(sheet_key, col_sel.column_letter)] = new_col_letter
                    column_mapping[(sheet_key, col_sel.column_index)] = new_col_letter

                    # Get formula if any
                    excel_formula = ''
                    if col_sel.column_letter in formula_columns:
                        excel_formula = formula_columns[col_sel.column_letter].get('formula', '')

                    # Generate unique code
                    code = self._generate_code(col_sel.original_header, seen_codes)
                    seen_codes.add(code)

                    # Determine data source
                    if col_sel.column_type == 'formula':
                        data_source = 'formula'
                    else:
                        data_source = 'excel'

                    component = {
                        'wizard_id': self.id,
                        'source_sheet': sheet_line.sheet_name,
                        'column_letter': new_col_letter,
                        'original_header': col_sel.original_header,
                        'generated_code': code,
                        'generated_name': col_sel.original_header,
                        'component_type': col_sel.component_type or '',
                        'column_type': col_sel.column_type,
                        'excel_formula': excel_formula,
                        'resolved_formula': '',  # Will be filled during resolution
                        'sample_value': col_sel.sample_value,
                        'is_duplicate': False,
                        'include_in_import': True,
                        'is_in_excel': True,
                        'data_source': data_source,
                        '_original_col': col_sel.column_letter,
                    }
                    all_components.append(component)
                    current_col_index += 1

                for col_sel in constant_cols:
                    code = self._generate_code(col_sel.original_header, seen_codes)
                    seen_codes.add(code)
                    component = {
                        'wizard_id': self.id,
                        'source_sheet': sheet_line.sheet_name,
                        'column_letter': col_sel.column_letter,
                        'original_header': col_sel.original_header,
                        'generated_code': code,
                        'generated_name': col_sel.original_header,
                        'component_type': col_sel.component_type or 'Constant',
                        'column_type': 'constant',
                        'excel_formula': '',
                        'resolved_formula': '',
                        'sample_value': col_sel.sample_value,
                        'is_duplicate': False,
                        'include_in_import': True,
                        'is_in_excel': True,
                        'data_source': 'manual',
                    }
                    all_components.append(component)

            # Now resolve formulas (both same-sheet and cross-sheet references)
            for component in all_components:
                if component['excel_formula']:
                    # First resolve same-sheet column references (e.g., I3 -> FS3)
                    formula_with_same_sheet = self._resolve_same_sheet_formula(
                        component['excel_formula'],
                        component['source_sheet'],
                        column_mapping
                    )

                    # Then resolve cross-sheet references (e.g., 'OtherSheet'!A1 -> XX1)
                    resolved = self._resolve_cross_sheet_formula(
                        formula_with_same_sheet,
                        column_mapping
                    )

                    component['resolved_formula'] = resolved
                    # Use the fully resolved formula
                    component['excel_formula'] = resolved

            # Create component preview records
            for comp in all_components:
                # Remove internal tracking field
                comp.pop('_original_col', None)
                self.env['hr.formula.multisheet.component.preview'].create(comp)

            self.state = 'review_components'
            return self._return_wizard_action()

        except Exception as e:
            _logger.exception("Failed to process sheets with resolution")
            raise UserError(_("Failed to process sheets: %s") % str(e))

    def _resolve_cross_sheet_formula(self, formula, column_mapping):
        """
        Resolve cross-sheet references in a formula to simple column references.

        VLOOKUP(B4,'TimeTB 2'!$C$4:$AU$11,45,0) → DM2
        SUMIF(Others!$B$8:$B$15,$B4,Others!$F$8:$F$15) → SUMIF(XX:XX,$B4,YY:YY)
        """
        if not formula:
            return formula

        result = formula

        # Resolve VLOOKUP: Replace entire VLOOKUP with simple column reference
        vlookup_pattern = re.compile(
            r"VLOOKUP\s*\([^,]+,\s*'?([^'!]+)'?\s*!\s*\$?([A-Z]+)\$?\d*:\$?[A-Z]+\$?\d*,\s*(\d+),\s*[^)]+\)",
            re.IGNORECASE
        )

        def resolve_vlookup(match):
            sheet_name = match.group(1).strip().lower()
            start_col = match.group(2).upper()
            col_index = int(match.group(3))

            # Calculate target column
            start_idx = self._column_letter_to_index(start_col)
            target_idx = start_idx + col_index - 1
            target_col = self._index_to_column_letter(target_idx)

            # Look up new column
            new_col = column_mapping.get((sheet_name, target_col))
            if not new_col:
                new_col = column_mapping.get((sheet_name, target_idx))

            if new_col:
                return f"{new_col}2"  # Simple reference to row 2 (data row placeholder)
            else:
                return "0"  # Unresolved - return 0

        result = vlookup_pattern.sub(resolve_vlookup, result)

        # Resolve SUMIF: Replace range references
        sumif_pattern = re.compile(
            r"SUMIF\s*\(\s*'?([^'!]+)'?\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*,\s*([^,]+),\s*'?([^'!]+)'?\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*\s*\)",
            re.IGNORECASE
        )

        def resolve_sumif(match):
            criteria_sheet = match.group(1).strip().lower()
            criteria_col = match.group(2).upper()
            criteria = match.group(4)
            sum_sheet = match.group(5).strip().lower()
            sum_col = match.group(6).upper()

            new_criteria_col = column_mapping.get((criteria_sheet, criteria_col))
            if not new_criteria_col:
                idx = self._column_letter_to_index(criteria_col)
                new_criteria_col = column_mapping.get((criteria_sheet, idx))

            new_sum_col = column_mapping.get((sum_sheet, sum_col))
            if not new_sum_col:
                idx = self._column_letter_to_index(sum_col)
                new_sum_col = column_mapping.get((sum_sheet, idx))

            if new_criteria_col and new_sum_col:
                return f"SUMIF({new_criteria_col}:{new_criteria_col},{criteria},{new_sum_col}:{new_sum_col})"
            else:
                return "0"

        result = sumif_pattern.sub(resolve_sumif, result)

        # Resolve direct references: 'Sheet'!A4 -> NewCol4
        direct_pattern = re.compile(
            r"'?([^'!]+)'?\s*!\s*\$?([A-Z]+)\$?(\d+)",
            re.IGNORECASE
        )

        def resolve_direct(match):
            sheet_name = match.group(1).strip().lower()
            col = match.group(2).upper()
            row = match.group(3)

            new_col = column_mapping.get((sheet_name, col))
            if not new_col:
                idx = self._column_letter_to_index(col)
                new_col = column_mapping.get((sheet_name, idx))

            if new_col:
                return f"{new_col}{row}"
            else:
                return "0"

        result = direct_pattern.sub(resolve_direct, result)

        return result

    def _resolve_same_sheet_formula(self, formula, sheet_name, column_mapping):
        """
        Resolve same-sheet column references in a formula.

        When columns are reordered during import (e.g., I -> FS, J -> FT, K -> FU),
        formulas that reference those columns need to be updated.

        Example:
            Original: =I3+J3+K3
            After resolution: =FS3+FT3+FU3

        Args:
            formula: The Excel formula string
            sheet_name: The name of the sheet this formula belongs to
            column_mapping: Dictionary mapping (sheet_name, old_col) -> new_col

        Returns:
            Formula with updated column references
        """
        if not formula or not formula.startswith('='):
            return formula

        result = formula
        sheet_key = sheet_name.strip().lower()

        # Pattern to match column references in formulas
        # Matches: A1, $A$1, $A1, A$1, AA123, etc.
        # But NOT: Sheet!A1 (cross-sheet refs are handled elsewhere)
        same_sheet_pattern = re.compile(
            r'(?<![!\w])\$?([A-Z]+)\$?(\d+)(?!\w)',
            re.IGNORECASE
        )

        def replace_column(match):
            old_col = match.group(1).upper()
            row = match.group(2)

            # Look up the new column letter
            new_col = column_mapping.get((sheet_key, old_col))
            if not new_col:
                # Try by column index
                try:
                    idx = self._column_letter_to_index(old_col)
                    new_col = column_mapping.get((sheet_key, idx))
                except:
                    pass

            if new_col:
                # Preserve $ markers if present
                prefix = '$' if match.group(0).startswith('$') else ''
                suffix = '$' if '$' + row in match.group(0) else ''
                return f"{prefix}{new_col}{suffix}{row}"
            else:
                # No mapping found, keep original
                return match.group(0)

        result = same_sheet_pattern.sub(replace_column, result)

        return result

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

    def _get_sample_value(self, sheet_data, data_sheet, formula_sheet, header_value, col_letter):
        """Get a sample value for a column, falling back to formulas when needed."""
        if sheet_data.get('data_rows'):
            for row in sheet_data['data_rows']:
                if header_value in row and row[header_value] is not None:
                    return str(row[header_value])[:50]

        data_start_row = sheet_data.get('data_start_row') or (sheet_data.get('header_row', 1) + 1)
        max_row = data_sheet.max_row if data_sheet else data_start_row
        scan_end = min(data_start_row + 10, max_row)

        from openpyxl.utils import column_index_from_string
        col_idx = column_index_from_string(col_letter)

        for row_num in range(data_start_row, scan_end + 1):
            value = None
            if data_sheet:
                value = data_sheet.cell(row=row_num, column=col_idx).value
            if value is not None:
                return str(value)[:50]
            if formula_sheet:
                formula_value = formula_sheet.cell(row=row_num, column=col_idx).value
                if isinstance(formula_value, str) and formula_value.startswith('='):
                    return formula_value[:50]

        return ''

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

    def _parse_percentage_value(self, value):
        """
        Parse a percentage value and convert to decimal.

        Examples:
            "8%" -> 0.08
            "1.5%" -> 0.015
            "100%" -> 1.0
            0.08 (already decimal) -> 0.08
            8 (just number) -> 8.0

        Returns:
            Tuple of (decimal_value, was_percentage)
        """
        if value is None:
            return 0.0, False

        # If it's already a number (float/int)
        if isinstance(value, (int, float)):
            return float(value), False

        # If it's a string, check for percentage sign
        str_value = str(value).strip()
        if str_value.endswith('%'):
            try:
                # Remove % and convert to decimal
                num_part = str_value[:-1].strip()
                decimal_value = float(num_part) / 100.0
                return decimal_value, True
            except ValueError:
                return 0.0, False

        # Try to convert as regular number
        try:
            return float(str_value), False
        except ValueError:
            return 0.0, False

    def _collect_constants_for_sheet(self, formula_sheet, sheet_data, formula_columns):
        """Collect constant definitions from a sheet using color and formula scans."""
        header_row = sheet_data.get('header_row', 1)
        data_start_row = sheet_data.get('data_start_row', header_row + 1)

        constant_pairs = self._detect_colored_constant_pairs(formula_sheet, header_row)
        scan_up_to_row = data_start_row + 2
        blue_constants = self._detect_blue_constant_cells(formula_sheet, scan_up_to_row)
        formula_referenced = self._detect_formula_referenced_constants(
            formula_columns, formula_sheet, header_row
        )

        constants = []
        seen_cells = set()
        for const in constant_pairs + blue_constants + formula_referenced:
            cell_ref = const.get('original_cell')
            if not cell_ref or cell_ref in seen_cells:
                continue
            seen_cells.add(cell_ref)
            constants.append(const)

        return constants

    def _detect_blue_constant_cells(self, sheet, scan_up_to_row):
        """
        Detect cells with blue font color that contain constant values.

        Scans all rows up to scan_up_to_row for cells with blue font.
        Blue is detected when B > R and B > G in the RGB color.

        For cells that are percentages (e.g., "8%"), converts to decimal (0.08).

        Returns list of dictionaries with:
            - name: Generated name (ConstantA, ConstantB, etc.)
            - value: The numeric value (percentages converted to decimals)
            - original_cell: Cell reference like "AY11"
            - original_col_letter: Column letter
            - original_col_idx: Column index
            - row: Row number
            - was_percentage: Boolean if value was originally a percentage
        """
        from openpyxl.utils import get_column_letter

        _logger.info(f"=== BLUE CONSTANT DETECTION START ===")
        _logger.info(f"Scanning rows 1 to {scan_up_to_row - 1}")

        blue_constants = []
        constant_index = 0  # For naming ConstantA, ConstantB, etc.
        cells_with_color_checked = 0

        def is_blue_color(cell, cell_ref=""):
            """Check if cell has blue FONT color (any shade where B > R and B > G)."""
            try:
                font = cell.font
                if not font or not font.color:
                    return False, None

                color = font.color
                color_info = f"type={color.type}"

                # Check RGB color
                if color.type == 'rgb' and color.rgb:
                    rgb = str(color.rgb).upper()
                    color_info += f", rgb={rgb}"
                    if len(rgb) >= 6:
                        # Handle ARGB (8 chars) or RGB (6 chars)
                        if len(rgb) == 8:
                            r = int(rgb[2:4], 16)
                            g = int(rgb[4:6], 16)
                            b = int(rgb[6:8], 16)
                        else:
                            r = int(rgb[0:2], 16)
                            g = int(rgb[2:4], 16)
                            b = int(rgb[4:6], 16)

                        color_info += f" -> R={r}, G={g}, B={b}"

                        # Blue: B is dominant (B > R and B > G)
                        if b > r and b > g and b > 100:
                            return True, color_info

                # Check indexed colors (common blue indices)
                elif color.type == 'indexed':
                    color_info += f", indexed={color.indexed}"
                    if color.indexed in [4, 5, 12, 23, 30, 32, 39, 40, 41, 42, 48, 49, 54, 55, 56]:
                        return True, color_info

                # Check theme colors (theme 4, 5, 8 are often blue variants)
                elif color.type == 'theme':
                    color_info += f", theme={color.theme}"
                    if color.theme in [4, 5, 8]:
                        return True, color_info

                return False, color_info

            except Exception as e:
                return False, f"error: {e}"

        def generate_constant_name(index):
            """Generate ConstantA, ConstantB, ..., ConstantZ, ConstantAA, etc."""
            result = ""
            idx = index
            while True:
                result = chr(ord('A') + (idx % 26)) + result
                idx = idx // 26 - 1
                if idx < 0:
                    break
            return f"Constant{result}"

        def get_column_header_label(row_num, col_idx):
            """
            Look at the row immediately above to get a header label for this column.
            This appends context like _BHXH, _BHYT to the constant name.
            """
            if row_num <= 1:
                return None

            # Check the row immediately above
            header_cell = sheet.cell(row=row_num - 1, column=col_idx)
            if header_cell.value and isinstance(header_cell.value, str):
                label = str(header_cell.value).strip()
                # Clean up the label - remove special chars, keep alphanumeric and underscore
                import re
                clean_label = re.sub(r'[^A-Za-z0-9_]', '', label)
                if clean_label:
                    return clean_label

            return None

        # Scan all rows up to scan_up_to_row
        for row_num in range(1, scan_up_to_row):
            for col_idx in range(1, (sheet.max_column or 1) + 1):
                cell = sheet.cell(row=row_num, column=col_idx)

                # Skip empty cells
                if cell.value is None:
                    continue

                col_letter = get_column_letter(col_idx)
                cell_ref = f"{col_letter}{row_num}"

                # Check if cell has font color
                is_blue, color_info = is_blue_color(cell, cell_ref)
                if color_info:
                    cells_with_color_checked += 1
                    # Log cells with any color info for debugging
                    if cells_with_color_checked <= 20:  # Limit logging
                        _logger.info(f"  Cell {cell_ref} value='{cell.value}' color: {color_info} -> is_blue={is_blue}")

                # Check if cell has blue font
                if is_blue:
                    # Parse the value (handles percentages)
                    decimal_value, was_percentage = self._parse_percentage_value(cell.value)

                    # Generate base name (ConstantA, ConstantB, etc.)
                    base_name = generate_constant_name(constant_index)
                    constant_index += 1

                    # Look for header label in row above to append context
                    header_label = get_column_header_label(row_num, col_idx)
                    if header_label:
                        name = f"{base_name}_{header_label}"
                    else:
                        name = base_name

                    blue_constants.append({
                        'name': name,
                        'value': decimal_value,
                        'original_value': cell.value,  # Keep original for reference
                        'original_cell': cell_ref,
                        'original_col_letter': col_letter,
                        'original_col_idx': col_idx,
                        'row': row_num,
                        'was_percentage': was_percentage,
                    })

                    _logger.info(
                        f"  -> BLUE CONSTANT FOUND: {cell_ref} = {cell.value} "
                        f"-> {name} = {decimal_value}"
                        f"{' (converted from %)' if was_percentage else ''}"
                    )

        _logger.info(f"=== BLUE CONSTANT DETECTION END: {len(blue_constants)} found, {cells_with_color_checked} cells with color checked ===")

        return blue_constants

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

        return constant_pairs

    def _detect_formula_referenced_constants(self, formula_columns, sheet, header_row):
        """
        Scan formulas to find cell references above header row that might be constants.
        This catches constants like $CF$3 that may not have been detected by color.
        """
        import re
        from openpyxl.utils import column_index_from_string

        found_constants = []
        seen_cells = set()
        cell_ref_pattern = r'\$?([A-Z]+)\$?(\d+)'

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

                    name = None
                    if col_idx > 1:
                        left_cell = sheet.cell(row=row_num, column=col_idx - 1)
                        if left_cell.value and isinstance(left_cell.value, str):
                            name = str(left_cell.value).strip()

                    if not name:
                        name = f"Constant_{col_match}{row_num}"

                    found_constants.append({
                        'name': name,
                        'value': value,
                        'original_cell': cell_ref,
                        'original_col_letter': col_match,
                        'original_col_idx': col_idx,
                        'row': row_num,
                    })

                except Exception as e:
                    _logger.warning(f"Error processing cell {cell_ref}: {e}")

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
        """
        Update formula to replace original cell references with new column letters.
        e.g., {'CE3': 'ZA'} -> replaces $CE$3 or CE3 with ZA2
        """
        import re

        if not formula or not cell_mapping:
            return formula

        updated_formula = formula
        sorted_refs = sorted(cell_mapping.keys(), key=len, reverse=True)

        for original_ref in sorted_refs:
            new_col = cell_mapping[original_ref]
            cell_match = re.match(r'^([A-Za-z]+)(\d+)$', original_ref)
            if not cell_match:
                continue

            col_letters = cell_match.group(1)
            row_num = cell_match.group(2)
            pattern = r"(?:'[^']+'!|[A-Za-z0-9_]+!)?\$?" + col_letters + r"\$?" + row_num + r'(?![0-9A-Za-z])'
            replacement = f"{new_col}2"
            updated_formula = re.sub(pattern, replacement, updated_formula, flags=re.IGNORECASE)

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

                sequence = None
                if comp.column_letter:
                    sequence = self._column_letter_to_index(comp.column_letter) + 1

                rule_vals = {
                    'config_id': self.config_id.id,
                    'name': comp.generated_name,
                    'code': comp.generated_code,
                    'column_type': comp.column_type,
                    'component_type': comp.component_type,
                    'source_sheet_name': comp.source_sheet,
                    'original_column_letter': comp.column_letter,
                    'forced_column_letter': comp.column_letter,  # Preserve actual Excel column position for ALL rules
                    'data_source': comp.data_source,
                }
                if sequence is not None:
                    rule_vals['sequence'] = sequence

                if comp.column_type == 'formula' and comp.excel_formula:
                    rule_vals['excel_formula'] = comp.excel_formula

                # Handle constant components (from colored cell pairs)
                if comp.column_type == 'constant':
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

            next_action = self.config_id.get_formview_action()
            next_action['target'] = 'current'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Complete'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                    'next': next_action,
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
        state_order = ['upload', 'select_sheets', 'select_columns', 'configure_order',
                       'review_components', 'map_missing', 'confirm']
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
    _rec_name = 'sheet_name'
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

    sheet_name_html = fields.Html(
        string='Sheet Name',
        compute='_compute_sheet_name_html',
        sanitize=False
    )

    color = fields.Integer(
        string='Color Index',
        compute='_compute_color',
        store=True
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
        string='References Other Sheets',
        readonly=True,
        help="This worksheet contains formulas that reference cells in other worksheets (e.g., =TAM_UNG!A1)"
    )

    referenced_sheet_names = fields.Char(
        string='Depends On',
        readonly=True,
        help="List of worksheets that this sheet references in formulas"
    )

    referenced_sheet_names_html = fields.Html(
        string='Depends On',
        compute='_compute_referenced_sheet_names_html',
        sanitize=False
    )

    header_confidence = fields.Float(
        string='Detection Confidence',
        readonly=True
    )

    @api.depends('sheet_name')
    def _compute_sheet_name_html(self):
        """Generate colored badge HTML for sheet name."""
        for record in self:
            if not record.sheet_name:
                record.sheet_name_html = ''
                continue

            # Generate unique color for this sheet
            bg_color = record._get_unique_color_for_sheet(record.sheet_name)
            # Calculate contrasting text color
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = '#000000' if luminance > 0.5 else '#ffffff'

            record.sheet_name_html = (
                f'<span class="badge sheet-name-badge" '
                f'style="background-color: {bg_color}; color: {text_color}; '
                f'padding: 6px 12px; font-size: 12px; font-weight: 600; '
                f'border-radius: 4px; display: inline-block;">'
                f'{record.sheet_name}</span>'
            )

    @api.depends('sheet_name')
    def _compute_color(self):
        """Compute a consistent color index for each sheet based on its name."""
        for record in self:
            if record.sheet_name:
                # Use a better hash distribution to avoid repetitive colors
                # This ensures similar names get different colors
                import hashlib
                hash_bytes = hashlib.md5(record.sheet_name.encode()).digest()
                hash_val = int.from_bytes(hash_bytes[:4], 'big')
                # Map to color index (0-11) with better distribution
                record.color = hash_val % 12
            else:
                record.color = 0

    def _get_unique_color_for_sheet(self, sheet_name):
        """Generate a unique hex color for a sheet name."""
        import hashlib
        # Generate a hash of the sheet name
        hash_bytes = hashlib.md5(sheet_name.encode()).digest()
        # Use the hash to generate RGB values
        r = hash_bytes[0]
        g = hash_bytes[1]
        b = hash_bytes[2]
        # Adjust brightness to ensure readable colors (not too dark, not too light)
        # Keep values in the 50-200 range for good visibility
        r = 50 + (r % 150)
        g = 50 + (g % 150)
        b = 50 + (b % 150)
        return f'#{r:02x}{g:02x}{b:02x}'

    @api.depends('referenced_sheet_names', 'wizard_id.available_sheet_ids.sheet_name')
    def _compute_referenced_sheet_names_html(self):
        """Generate HTML badges with unique color coding for referenced sheet names."""
        for record in self:
            if not record.referenced_sheet_names:
                record.referenced_sheet_names_html = ''
                continue

            # Build HTML badges with inline colors
            badges = []
            sheet_names = [s.strip() for s in record.referenced_sheet_names.split(',') if s.strip()]
            for sheet_name in sheet_names:
                # Generate unique color for this sheet
                bg_color = self._get_unique_color_for_sheet(sheet_name)
                # Calculate contrasting text color (black or white)
                # Convert hex to RGB to calculate luminance
                r = int(bg_color[1:3], 16)
                g = int(bg_color[3:5], 16)
                b = int(bg_color[5:7], 16)
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                text_color = '#000000' if luminance > 0.5 else '#ffffff'

                badge_html = (
                    f'<span class="badge sheet-badge" '
                    f'style="background-color: {bg_color}; color: {text_color}; '
                    f'margin: 2px; padding: 4px 8px; font-size: 11px; '
                    f'font-weight: 600; border-radius: 4px; display: inline-block;">'
                    f'{sheet_name}</span>'
                )
                badges.append(badge_html)

            record.referenced_sheet_names_html = ' '.join(badges) if badges else ''

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
        ('manual', 'Manual Entry'),
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


class MultiSheetColumnSelection(models.TransientModel):
    """
    Column selection for multi-sheet import wizard.

    Stores per-worksheet column selections, allowing users to choose
    which columns to include from each selected worksheet.
    """
    _name = 'hr.formula.multisheet.column.selection'
    _description = 'Multi-Sheet Import Column Selection'
    _order = 'sheet_line_id, sequence'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True
    )

    sheet_line_id = fields.Many2one(
        'hr.formula.multisheet.sheet.line',
        string='Sheet',
        ondelete='cascade',
        required=True
    )
    sheet_name = fields.Char(
        related='sheet_line_id.sheet_name',
        string='Worksheet',
        readonly=True
    )

    # Column identity
    sequence = fields.Integer(default=10)

    column_letter = fields.Char(
        string='Column',
        readonly=True
    )

    column_index = fields.Integer(
        string='Index',
        readonly=True
    )

    original_header = fields.Char(
        string='Header',
        readonly=True
    )
    constant_cell_ref = fields.Char(
        string='Original Cell',
        readonly=True,
        help="Original Excel cell reference for detected constants"
    )

    # Component type from merged cells above
    component_type = fields.Char(
        string='Category',
        readonly=True,
        help="Component type extracted from merged cell above the header"
    )

    # Selection controls
    is_selected = fields.Boolean(
        string='Include',
        default=True
    )

    # Preview data
    column_type = fields.Selection([
        ('input', 'Input'),
        ('formula', 'Formula'),
        ('constant', 'Constant')
    ], string='Type', readonly=True, default='input')

    sample_value = fields.Char(
        string='Sample',
        readonly=True
    )

    # Cross-sheet reference info
    has_cross_sheet_ref = fields.Boolean(
        string='Cross-Sheet Ref',
        readonly=True,
        help="This column's formula references other worksheets"
    )

    cross_sheet_formula = fields.Char(
        string='Formula',
        readonly=True,
        help="The formula containing cross-sheet references"
    )

    is_referenced_by_main = fields.Boolean(
        string='Referenced by Main',
        readonly=True,
        help="This column is referenced by formulas in the main worksheet"
    )

    is_referenced_by_other_sheet = fields.Boolean(
        string='Referenced by Other',
        compute='_compute_cross_sheet_reference_info',
        readonly=True,
        help="This column is referenced by formulas in other worksheets"
    )

    refers_to_sheet_names = fields.Char(
        string='Refers To Sheets',
        compute='_compute_cross_sheet_reference_info',
        readonly=True,
        help="Worksheets referenced by this column's formula"
    )

    referenced_by_sheet_names = fields.Char(
        string='Referenced By Sheets',
        compute='_compute_cross_sheet_reference_info',
        readonly=True,
        help="Worksheets that reference this column"
    )

    @api.depends(
        'wizard_id.column_selection_ids.cross_sheet_formula',
        'wizard_id.column_selection_ids.sheet_name',
        'wizard_id.column_selection_ids.column_letter'
    )
    def _compute_cross_sheet_reference_info(self):
        for wizard in self.mapped('wizard_id'):
            lines = wizard.column_selection_ids
            references_by_component = {}
            referenced_by_component = {}
            sheet_name_map = {
                self._normalize_sheet_name(line.sheet_name): line.sheet_name
                for line in lines
                if line.sheet_name
            }

            for line in lines:
                if not line.cross_sheet_formula:
                    continue
                source_key = self._normalize_sheet_name(line.sheet_name)
                source_col = (line.column_letter or '').upper()
                for ref in self._extract_cross_sheet_references_from_formula(line.cross_sheet_formula):
                    target_key = self._normalize_sheet_name(ref['sheet_name'])
                    if not target_key or target_key == source_key:
                        continue
                    target_display = sheet_name_map.get(target_key, ref['sheet_name'])
                    references_by_component.setdefault(
                        (source_key, source_col), set()
                    ).add(target_display)
                    referenced_by_component.setdefault(
                        (target_key, ref['col_letter']), set()
                    ).add(line.sheet_name)

            for line in lines & self:
                key = (
                    self._normalize_sheet_name(line.sheet_name),
                    (line.column_letter or '').upper()
                )
                refers_to = references_by_component.get(key, set())
                referenced_by = referenced_by_component.get(key, set())
                line.refers_to_sheet_names = ", ".join(sorted(refers_to))
                line.referenced_by_sheet_names = ", ".join(sorted(referenced_by))
                line.is_referenced_by_other_sheet = bool(referenced_by)

    @staticmethod
    def _normalize_sheet_name(sheet_name):
        return sheet_name.strip().lower() if sheet_name else ''

    def _extract_cross_sheet_references_from_formula(self, formula):
        """Extract referenced sheet/column pairs from a formula."""
        if not formula:
            return []

        refs = set()

        def add_ref(sheet_name, col_letter):
            if not sheet_name or not col_letter:
                return
            refs.add((sheet_name.strip(), col_letter.upper()))

        vlookup_quoted_pattern = re.compile(
            r"VLOOKUP\s*\([^,]+,\s*'([^']+)'\s*!\s*\$?([A-Z]+)\$?\d*:\$?[A-Z]+\$?\d*,\s*(\d+)",
            re.IGNORECASE
        )
        vlookup_unquoted_pattern = re.compile(
            r"VLOOKUP\s*\([^,]+,\s*([A-Za-z][A-Za-z0-9_]*)\s*!\s*\$?([A-Z]+)\$?\d*:\$?[A-Z]+\$?\d*,\s*(\d+)",
            re.IGNORECASE
        )
        sumif_quoted_pattern = re.compile(
            r"SUMIF\s*\(\s*'([^']+)'\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*,\s*([^,]+),\s*'([^']+)'\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*\s*\)",
            re.IGNORECASE
        )
        sumif_unquoted_pattern = re.compile(
            r"SUMIF\s*\(\s*([A-Za-z][A-Za-z0-9_]*)\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*,\s*([^,]+),\s*([A-Za-z][A-Za-z0-9_]*)\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*\s*\)",
            re.IGNORECASE
        )
        range_quoted_pattern = re.compile(
            r"'([^']+)'\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*",
            re.IGNORECASE
        )
        range_unquoted_pattern = re.compile(
            r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)\s*!\s*\$?([A-Z]+)\$?\d*:\$?([A-Z]+)\$?\d*",
            re.IGNORECASE
        )
        direct_quoted_pattern = re.compile(
            r"'([^']+)'\s*!\s*\$?([A-Z]+)\$?\d+",
            re.IGNORECASE
        )
        direct_unquoted_pattern = re.compile(
            r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)\s*!\s*\$?([A-Z]+)\$?\d+",
            re.IGNORECASE
        )

        for match in vlookup_quoted_pattern.finditer(formula):
            sheet_name = match.group(1).strip()
            start_col = match.group(2).upper()
            col_index = int(match.group(3))
            start_idx = self._column_letter_to_index(start_col)
            target_idx = start_idx + col_index - 1
            target_col = self._index_to_column_letter(target_idx)
            add_ref(sheet_name, target_col)

        for match in vlookup_unquoted_pattern.finditer(formula):
            sheet_name = match.group(1).strip()
            start_col = match.group(2).upper()
            col_index = int(match.group(3))
            start_idx = self._column_letter_to_index(start_col)
            target_idx = start_idx + col_index - 1
            target_col = self._index_to_column_letter(target_idx)
            add_ref(sheet_name, target_col)

        for match in sumif_quoted_pattern.finditer(formula):
            criteria_sheet = match.group(1).strip()
            criteria_col = match.group(2).upper()
            add_ref(criteria_sheet, criteria_col)
            sum_sheet = match.group(5).strip()
            sum_col = match.group(6).upper()
            add_ref(sum_sheet, sum_col)

        for match in sumif_unquoted_pattern.finditer(formula):
            criteria_sheet = match.group(1).strip()
            criteria_col = match.group(2).upper()
            add_ref(criteria_sheet, criteria_col)
            sum_sheet = match.group(5).strip()
            sum_col = match.group(6).upper()
            add_ref(sum_sheet, sum_col)

        for match in range_quoted_pattern.finditer(formula):
            sheet_name = match.group(1).strip()
            start_col = match.group(2).upper()
            end_col = match.group(3).upper()
            add_ref(sheet_name, start_col)
            add_ref(sheet_name, end_col)

        for match in range_unquoted_pattern.finditer(formula):
            sheet_name = match.group(1).strip()
            start_col = match.group(2).upper()
            end_col = match.group(3).upper()
            add_ref(sheet_name, start_col)
            add_ref(sheet_name, end_col)

        for match in direct_quoted_pattern.finditer(formula):
            add_ref(match.group(1), match.group(2))

        for match in direct_unquoted_pattern.finditer(formula):
            add_ref(match.group(1), match.group(2))

        return [
            {'sheet_name': sheet_name, 'col_letter': col_letter}
            for sheet_name, col_letter in sorted(refs)
        ]

    @staticmethod
    def _column_letter_to_index(col_letter):
        """Convert column letter to 0-based index (A=0, B=1, ...)."""
        result = 0
        for char in col_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    @staticmethod
    def _index_to_column_letter(index):
        """Convert 0-based index to column letter (0=A, 1=B, ...)."""
        result = ""
        idx = index
        while True:
            result = chr(ord('A') + (idx % 26)) + result
            idx = idx // 26 - 1
            if idx < 0:
                break
        return result



class MultiSheetAppendOrder(models.TransientModel):
    """
    Worksheet append order for multi-sheet import wizard.

    Controls the order in which auxiliary worksheets are appended
    to the main worksheet to form the final component structure.
    """
    _name = 'hr.formula.multisheet.append.order'
    _description = 'Multi-Sheet Import Append Order'
    _order = 'append_sequence'

    wizard_id = fields.Many2one(
        'hr.formula.multisheet.import.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True
    )

    sheet_line_id = fields.Many2one(
        'hr.formula.multisheet.sheet.line',
        string='Sheet',
        ondelete='cascade',
        required=True
    )

    sheet_name = fields.Char(
        related='sheet_line_id.sheet_name',
        string='Worksheet',
        readonly=True
    )

    is_main_sheet = fields.Boolean(
        related='sheet_line_id.is_main_sheet',
        string='Main',
        readonly=True
    )

    # Append order (main sheet is always 0)
    append_sequence = fields.Integer(
        string='Order',
        default=10
    )

    # Statistics
    selected_column_count = fields.Integer(
        string='Selected Columns',
        compute='_compute_stats'
    )

    total_column_count = fields.Integer(
        string='Total Columns',
        compute='_compute_stats'
    )

    # Preview info
    start_column_letter = fields.Char(
        string='Start Col',
        compute='_compute_column_range'
    )

    end_column_letter = fields.Char(
        string='End Col',
        compute='_compute_column_range'
    )

    @api.depends('sheet_line_id', 'wizard_id.column_selection_ids')
    def _compute_stats(self):
        """Compute column selection statistics."""
        for rec in self:
            if rec.sheet_line_id and rec.wizard_id:
                sheet_cols = rec.wizard_id.column_selection_ids.filtered(
                    lambda c: c.sheet_line_id.id == rec.sheet_line_id.id and c.column_type != 'constant'
                )
                rec.total_column_count = len(sheet_cols)
                rec.selected_column_count = len(sheet_cols.filtered('is_selected'))
            else:
                rec.total_column_count = 0
                rec.selected_column_count = 0

    @api.depends('append_sequence', 'wizard_id.append_order_ids', 'wizard_id.column_selection_ids')
    def _compute_column_range(self):
        """Compute the column range this sheet will occupy after appending."""
        for rec in self:
            if not rec.wizard_id or not rec.sheet_line_id:
                rec.start_column_letter = ''
                rec.end_column_letter = ''
                continue

            # Calculate cumulative column count for sheets before this one
            ordered = rec.wizard_id.append_order_ids.sorted('append_sequence')
            start_idx = 0
            for order_rec in ordered:
                if order_rec.id == rec.id:
                    break
                start_idx += order_rec.selected_column_count

            end_idx = start_idx + rec.selected_column_count - 1

            # Convert to column letters
            rec.start_column_letter = rec._index_to_column_letter(start_idx) if rec.selected_column_count > 0 else ''
            rec.end_column_letter = rec._index_to_column_letter(end_idx) if rec.selected_column_count > 0 else ''

    def _index_to_column_letter(self, index):
        """Convert 0-based column index to Excel column letter (A, B, ..., Z, AA, AB, ...)."""
        result = ""
        idx = index
        while True:
            result = chr(ord('A') + (idx % 26)) + result
            idx = idx // 26 - 1
            if idx < 0:
                break
        return result
