# -*- coding: utf-8 -*-
"""
Formula Import Wizard - Import formula configuration from various sources.
"""

import base64
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError


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
        """Import configuration from Excel file."""
        if not self.import_file:
            raise UserError(_("Please upload an Excel file"))

        try:
            import openpyxl
            import io

            content = base64.b64decode(self.import_file)
            workbook = openpyxl.load_workbook(io.BytesIO(content))
            sheet = workbook.active
        except ImportError:
            raise UserError(_("openpyxl library required. Install with: pip install openpyxl"))
        except Exception as e:
            raise UserError(_("Failed to read Excel file: %s") % str(e))

        if not self.preserve_existing:
            self.config_id.rule_ids.unlink()

        # Read headers from first row
        headers = [cell.value for cell in sheet[1]]

        # Expected columns
        required_cols = ['code', 'name']
        optional_cols = ['column_type', 'excel_formula', 'constant_value', 'default_value']

        # Validate headers
        for col in required_cols:
            if col.lower() not in [h.lower() if h else '' for h in headers]:
                raise UserError(_("Missing required column: %s") % col)

        # Create column index mapping
        col_map = {}
        for idx, header in enumerate(headers):
            if header:
                col_map[header.lower()] = idx

        max_sequence = max(
            self.config_id.rule_ids.mapped('sequence') or [0]
        )

        created_rules = self.env['hr.formula.rule']

        for row in sheet.iter_rows(min_row=2):
            row_values = [cell.value for cell in row]

            # Skip empty rows
            if not any(row_values):
                continue

            max_sequence += 10

            code = row_values[col_map.get('code', 0)]
            name = row_values[col_map.get('name', 1)]

            if not code or not name:
                continue

            values = {
                'config_id': self.config_id.id,
                'code': str(code),
                'name': str(name),
                'sequence': max_sequence,
            }

            # Optional columns
            if 'column_type' in col_map:
                col_type = row_values[col_map['column_type']]
                if col_type in ['input', 'formula', 'constant']:
                    values['column_type'] = col_type

            if 'excel_formula' in col_map:
                formula = row_values[col_map['excel_formula']]
                if formula:
                    values['excel_formula'] = str(formula)

            if 'constant_value' in col_map:
                const = row_values[col_map['constant_value']]
                if const is not None:
                    try:
                        values['constant_value'] = float(const)
                    except (ValueError, TypeError):
                        pass

            if 'default_value' in col_map:
                default = row_values[col_map['default_value']]
                if default is not None:
                    try:
                        values['default_value'] = float(default)
                    except (ValueError, TypeError):
                        pass

            created_rules |= self.env['hr.formula.rule'].create(values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%d rules imported from Excel') % len(created_rules),
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

            # Headers
            headers = ['code', 'name', 'column_type', 'excel_formula', 'constant_value', 'default_value']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = header
                cell.font = openpyxl.styles.Font(bold=True)

            # Sample rows
            samples = [
                ['BASIC', 'Basic Salary', 'input', '', '', '0'],
                ['HRA', 'Housing Allowance', 'formula', '=A1*0.2', '', '0'],
                ['TRANSPORT', 'Transport Allowance', 'constant', '', '500000', ''],
                ['GROSS', 'Gross Salary', 'formula', '=A1+B1+C1', '', '0'],
            ]

            for row_idx, sample in enumerate(samples, 2):
                for col_idx, value in enumerate(sample, 1):
                    ws.cell(row=row_idx, column=col_idx).value = value

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
