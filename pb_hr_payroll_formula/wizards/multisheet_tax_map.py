"""Keep statutory cell identity through the existing multi-sheet importer."""
import base64
import io

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..formula_engine.tax_workbook import read_tax_map, SHEET


class TaxMappedPreview(models.TransientModel):
    _inherit = 'hr.formula.multisheet.component.preview'
    constant_cell_ref = fields.Char(string='Original constant cell')


class TaxMappedImport(models.TransientModel):
    _inherit = 'hr.formula.multisheet.import.wizard'

    def _tax_map_groups(self):
        import openpyxl
        self.ensure_one()
        workbook = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.import_file)), data_only=False)
        try:
            groups = read_tax_map(workbook)
        except (ValueError, TypeError) as exc:
            raise UserError(str(exc)) from exc
        if any(g['country_code'] != self.config_id.country_code for g in groups):
            raise UserError(_('Workbook statutory tables must match the payroll configuration country.'))
        return groups

    def action_analyze_file(self):
        groups = self._tax_map_groups() if self.import_file else []
        result = super().action_analyze_file()
        # Metadata must never be offered as an employee table or a join target.
        self.available_sheet_ids.filtered(lambda s: s.sheet_name == SHEET).unlink()
        if groups and self.config_id.state not in ('draft', 'testing'):
            raise UserError(_('Import mapped statutory values into a draft or testing configuration.'))
        return result

    def _collect_constants_for_sheet(self, formula_sheet, sheet_data, formula_columns, data_sheet=None):
        constants = super()._collect_constants_for_sheet(formula_sheet, sheet_data, formula_columns, data_sheet)
        mapped = {v['cell']: v for g in self._tax_map_groups() for v in g['values'] if v['sheet'] == formula_sheet.title}
        found = {c['original_cell']: c for c in constants}
        for cell, entry in mapped.items():
            if formula_sheet[cell].row >= sheet_data['data_start_row']:
                raise UserError(_('Mapped statutory constants must be above the employee header: %s', cell))
            if cell in found:
                found[cell]['name'] = entry['label']
            else:
                constants.append({'name': entry['label'], 'value': entry['value'],
                                  'original_cell': cell, 'row': formula_sheet[cell].row})
        return constants

    def action_execute_import(self):
        groups = self._tax_map_groups()
        if groups and self.config_id.state not in ('draft', 'testing'):
            raise UserError(_('Import mapped statutory values into a draft or testing configuration.'))
        result = super().action_execute_import()
        Table = self.env['hr.payroll.tax.table']
        for group in groups:
            table = Table.search([('company_id', '=', self.config_id.company_id.id),
                                  ('country_code', '=', group['country_code']),
                                  ('code', '=', group['code']), ('version', '=', group['version'])], limit=1)
            mapped_values = {(v['slot'], v['field']): v['value'] for v in group['values']}
            if table:
                keys = ['effective_from', 'effective_to', 'method', 'basis']
                metadata_matches = all(str(table[k] or '') == str(group[k] or '') for k in keys)
                if table._values() != mapped_values or not metadata_matches:
                    raise UserError(_('Workbook values differ from edition %s. Use a new version; an import cannot overwrite a database edition.', table.display_name))
            else:
                vals = {k: group[k] for k in ['code', 'country_code', 'version', 'effective_from', 'effective_to', 'method', 'basis']}
                vals.update(name='%s · %s' % (group['code'], group['version']),
                            company_id=self.config_id.company_id.id, authority=self.import_filename)
                if group['method'] == 'parameters':
                    vals['parameter_ids'] = [(0, 0, {'code': v['slot'], 'name': v['label'], 'value': v['value']}) for v in group['values']]
                else:
                    slots = sorted({v['slot'] for v in group['values']})
                    vals['slab_ids'] = [(0, 0, {'sequence': slot,
                        'income_to': mapped_values[(slot, 'upper')],
                        'tax_rate': mapped_values[(slot, 'rate')]}) for slot in slots]
                table = Table.create(vals)
                table._validate_edition()
            for entry in group['values']:
                previews = self.component_preview_ids.filtered(lambda p:
                    p.include_in_import and p.column_type == 'constant' and
                    p.source_sheet == entry['sheet'] and p.constant_cell_ref == entry['cell'])
                if len(previews) != 1:
                    raise UserError(_('Include the mapped constant %s!%s before importing.', entry['sheet'], entry['cell']))
                rule = self.config_id.rule_ids.filtered(lambda r: r.code == previews.generated_code)
                if len(rule) != 1 or abs(rule.constant_value - entry['value']) > 1e-8:
                    raise UserError(_('The imported statutory constant does not match its workbook value.'))
                rule.write({'tax_table_id': table.id, 'tax_field': entry['field'],
                            'tax_band_sequence': entry['slot'] if entry['field'] != 'parameter' else 0,
                            'tax_parameter_code': entry['slot'] if entry['field'] == 'parameter' else False,
                            'tax_source_sheet': entry['sheet'], 'tax_source_cell': entry['cell']})
        if groups:
            self.config_id.statutory_asof = max(g['effective_from'] for g in groups)
        return result
