"""Tax map round trips, date/country isolation and reviewed refresh arithmetic."""
import base64
import io

import openpyxl
from openpyxl.styles import Font
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError

from ..formula_engine.tax_workbook import HEADERS, read_tax_map
from ..models.payroll_tax_table import _APPLY_KEY, _APPLY_TOKEN, stamp


@tagged('post_install', '-at_install', 'country_tax_mapping')
class TestCountryTaxMapping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Tax map test', 'code': 'TAX_MAP_TEST', 'country_code': 'ID',
            'company_id': cls.company.id})

    def table(self, country='ID', version='August', start='2026-08-01', rate=.05):
        return self.env['hr.payroll.tax.table'].create({
            'name': 'Test TER', 'code': 'TESTTER', 'country_code': country,
            'company_id': self.company.id, 'version': version, 'effective_from': start,
            'method': 'whole_income', 'basis': 'monthly',
            'slab_ids': [(0, 0, {'sequence': 1, 'income_to': 5400000, 'tax_rate': 0}),
                         (0, 0, {'sequence': 2, 'income_to': 0, 'tax_rate': rate})]})

    def bind(self, table):
        return self.env['hr.formula.rule'].create({
            'name': 'Mapped rate', 'code': 'MAPPEDRATE', 'config_id': self.config.id,
            'column_type': 'constant', 'constant_value': .05, 'forced_column_letter': 'B',
            'tax_table_id': table.id, 'tax_field': 'rate', 'tax_band_sequence': 2,
            'tax_source_sheet': 'Payroll', 'tax_source_cell': 'B2'})

    def publish(self, table):
        table._validate_edition()
        table.with_context(**{_APPLY_KEY: _APPLY_TOKEN}).write({'state': 'published'})

    def workbook(self):
        w = openpyxl.Workbook()
        s = w.active
        s.title = 'Payroll'
        # Four distinct constants, then a single employee header and formula.
        for r, pair in enumerate([('Cap 1', 5400000), ('Rate 1', 0), ('Cap 2', 0), ('Rate 2', .05)], 1):
            s.cell(r, 1, pair[0])
            s.cell(r, 2, pair[1]).font = Font(color='0000FF')
        s.append([])
        s.append(['Employee ID', 'Gross income', 'Monthly tax'])
        s.append(['EXAMPLE1', 5500000, '=ROUND(IF(B7<=$B$1,B7*$B$2,B7*$B$4),0)'])
        s.append(['EXAMPLE2', 5400000, '=ROUND(IF(B8<=$B$1,B8*$B$2,B8*$B$4),0)'])
        m = w.create_sheet('Tax Map')
        m.append(HEADERS)
        for slot, field, cell in [(1, 'upper', 'B1'), (1, 'rate', 'B2'), (2, 'upper', 'B3'), (2, 'rate', 'B4')]:
            m.append(['TESTTER', 'ID', 'August', '2026-08-01', '', 'whole_income',
                      'monthly', slot, field, 'Payroll', cell, '%s %s' % (field, slot)])
        return w

    def test_import_preserves_cell_bindings_and_metadata_is_not_payroll(self):
        w = self.workbook()
        out = io.BytesIO()
        w.save(out)
        wizard = self.env['hr.formula.multisheet.import.wizard'].create({
            'config_id': self.config.id, 'import_file': base64.b64encode(out.getvalue()),
            'import_filename': 'test_tax_map.xlsx', 'primary_key_column': 'Employee ID'})
        wizard.action_analyze_file()
        self.assertEqual(wizard.available_sheet_ids.mapped('sheet_name'), ['Payroll'])
        wizard.available_sheet_ids.write({'is_selected': True, 'is_main_sheet': True})
        wizard.action_process_sheets()
        wizard.action_configure_order()
        wizard.action_process_with_resolution()
        wizard.action_execute_import()
        rules = self.config.rule_ids.filtered('tax_table_id')
        self.assertEqual(len(rules), 4)
        self.assertEqual(set(rules.mapped('tax_source_cell')), {'B1', 'B2', 'B3', 'B4'})
        self.assertTrue(all(rules.mapped('tax_aligned')))
        self.assertEqual(rules.tax_table_id.state, 'draft')
        self.assertFalse(self.config.rule_ids.filtered(lambda r: r.name == 'Table Code'))
        # Same edition and same cells round-trip without duplicate source tables.
        wizard.action_execute_import()
        self.assertEqual(len(self.env['hr.payroll.tax.table'].search([('code', '=', 'TESTTER')])), 1)

    def test_date_selection_and_explicit_refresh_leave_old_values_intact(self):
        old = self.table()
        self.publish(old)
        rule = self.bind(old)
        new = self.table(version='November', start='2026-11-01', rate=.06)
        self.publish(new)
        before = self.config._tax_refresh_plan('2026-08-31')
        self.assertEqual(before[0]['after'], .05)
        self.assertEqual(self.config._tax_refresh_plan('2026-11-01')[0]['after'], .06)
        self.assertEqual(rule.constant_value, .05)
        self.config.with_context(**{_APPLY_KEY: _APPLY_TOKEN})._apply_tax_refresh('2026-11-01')
        self.assertEqual(rule.constant_value, .06)
        self.assertEqual(rule.tax_table_id, new)
        self.assertEqual(old._values()[(2, 'rate')], .05)
        self.assertTrue(self.env['hr.formula.rule.version'].search([('rule_id', '=', rule.id), ('reason', '=', 'legislation')]))
        self.config.state = 'active'
        with self.assertRaises(UserError):
            self.config._tax_refresh_plan('2026-11-01')

    def test_country_mismatch_cannot_bind(self):
        table = self.table(country='VN')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.bind(table)

    def test_published_child_values_are_immutable(self):
        t = self.table()
        self.publish(t)
        with self.assertRaises(UserError):
            t.slab_ids[-1].tax_rate = .06
        with self.assertRaises(UserError):
            t.slab_ids[-1].unlink()
        with self.assertRaises(UserError):
            t.write({'version': 'Edited'})

    def test_band_structure_change_requires_formula_review(self):
        old = self.table()
        self.publish(old)
        self.bind(old)
        new = self.table(version='November', start='2026-11-01')
        new.slab_ids[-1].income_to = 9000000
        new.write({'slab_ids': [(0, 0, {'sequence': 3, 'income_to': 0, 'tax_rate': .1})]})
        self.publish(new)
        with self.assertRaises(UserError):
            self.config._tax_refresh_plan('2026-11-01')

    def test_mapping_rejects_formulas_duplicates_bad_percent_and_wrong_country(self):
        w = self.workbook()
        self.assertEqual(len(read_tax_map(w)[0]['values']), 4)
        w['Payroll']['B4'] = 5
        with self.assertRaises(ValueError):
            read_tax_map(w)
        w['Payroll']['B4'] = '=1/20'
        with self.assertRaises(ValueError):
            read_tax_map(w)
        w['Payroll']['B4'] = .05
        w['Tax Map']['K5'] = 'B2'
        with self.assertRaises(ValueError):
            read_tax_map(w)

    def test_proposal_stamp_changes_when_draft_values_move(self):
        t = self.table()
        before = t._stamp()
        t.slab_ids[-1].tax_rate = .06
        self.assertNotEqual(before, t._stamp())

    def test_cockpit_country_filter_never_returns_vietnam_for_indonesia(self):
        if 'pb.statutory' not in self.env:
            self.skipTest('Statutory cockpit is not installed')
        self.table(country='ID')
        self.table(country='VN')
        data = self.env['pb.statutory'].get_statutory_data('ID')
        self.assertTrue(data['tax_tables'])
        self.assertTrue(all(t['country'] == 'ID' for t in data['tax_tables']))
        self.assertFalse(any(t['model'] == 'vietnam.tax.table' for t in data['tax_tables']))
