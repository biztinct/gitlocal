# -*- coding: utf-8 -*-
"""Typed contract text writes on import and fills an empty payroll input."""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'journey_text_readback')
class TestJourneyTextReadback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Journey text fallback', 'code': 'JTEXTFALLBACK',
            'country_code': 'VN',
        })
        cls.rule = cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id, 'name': 'Journey text', 'code': 'JTEXTVALUE',
            'column_type': 'input', 'column_role': 'contract', 'value_kind': 'text',
            'appears_on_payslip': False, 'is_contract_component': True,
            'is_text_component': True,
        })
        # This input is needed by a formula, so the normal exclusion of unused
        # people columns does not mask whether the batch resolver reads it.
        cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id, 'name': 'Journey text reader',
            'code': 'JTEXTREADER', 'column_type': 'formula',
            'excel_formula': '=IF(JTEXTVALUE="Stored",1,0)',
        })
        cls.rule.set_source_binding('excel', 'Journey text')
        cls.template = cls.env['hr.contract.advantage.template'].create({
            'name': 'Journey text', 'code': cls.rule.code, 'value_type': 'text',
        })
        cls.employee = cls.env['hr.employee'].create({'name': 'Journey text test'})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'Journey text test', 'employee_id': cls.employee.id,
            'wage': 1000, 'state': 'draft',
        })
        cls.stored = cls.contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id == cls.template)
        if not cls.stored:
            cls.stored = cls.env['hr.contract.advantage'].create({
                'contract_id': cls.contract.id,
                'advantage_template_id': cls.template.id,
            })
        cls.stored.text_value = 'Stored'
        cls.batch = cls.env['hr.payroll.import.batch'].create({
            'name': 'Journey text test', 'source_type': 'excel',
            'formula_config_id': cls.config.id,
        })

    def _resolve(self, raw):
        provenance = {}
        values = self.batch._transform_data_to_formula_inputs(
            raw, contract=self.contract, provenance=provenance)
        return values[self.rule.code], provenance[self.rule.code]

    def _sync(self, raw):
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': self.batch.id, 'employee_id': self.employee.id,
            'raw_data_json': json.dumps(raw),
        })
        self.batch._sync_contract_components(line, self.contract)

    def test_absent_and_empty_cells_read_stored_text(self):
        for raw in ({}, {'Journey text': None}, {'Journey text': ''},
                    {'Journey text': '   '}):
            with self.subTest(raw=raw):
                value, source = self._resolve(raw)
                self.assertEqual(value, 'Stored')
                self.assertEqual(source['src'], 'contract_component')

    def test_import_updates_text_then_a_later_empty_file_reads_it_back(self):
        self._sync({'Journey text': 'Updated'})
        self.assertEqual(self.stored.text_value, 'Updated')
        self.assertEqual(self._resolve({})[0], 'Updated')
        self.assertEqual(self.contract.wage, 1000)
        self.assertEqual(self.stored.amount, 0)

    def test_file_value_wins_without_implicitly_writing_during_resolution(self):
        value, source = self._resolve({'Journey text': 'From file'})
        self.assertEqual(value, 'From file')
        self.assertEqual(source['src'], 'excel')
        self.assertEqual(self.stored.text_value, 'Stored')

    def test_empty_import_keeps_text_and_does_not_create_a_change_log(self):
        Change = self.env['hr.contract.advantage.change']
        before = Change.search_count([])
        self._sync({'Journey text': ''})
        self.assertEqual(self.stored.text_value, 'Stored')
        self.assertEqual(Change.search_count([]), before)

    def test_numeric_looking_text_is_not_replaced_by_its_amount_column(self):
        self.stored.text_value = '0007'
        self.assertEqual(self._resolve({})[0], '0007')
        self.assertNotIn('jtextvalue',
                         self.batch._contract_component_amounts(self.contract))
        self.assertEqual(self._resolve({'Journey text': '0000'})[0], '0000')

    def test_payroll_without_a_file_reads_the_same_stored_text(self):
        slip = self.env['hr.payslip'].new({
            'employee_id': self.employee.id, 'contract_id': self.contract.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
        })
        source = {}
        values = slip._get_formula_input_values(self.config, provenance=source)
        self.assertEqual(values[self.rule.code], 'Stored')
        self.assertEqual(source[self.rule.code]['src'], 'contract_component')

    def test_missing_text_stays_empty_instead_of_becoming_zero(self):
        self.stored.text_value = False
        self.assertEqual(self._resolve({})[0], '')

    def test_unbound_text_component_also_reads_stored_text(self):
        self.rule.source_ids.unlink()
        self.assertEqual(self._resolve({})[0], 'Stored')

    def test_disabling_records_disables_the_text_fallback(self):
        self.config.source_records_enabled = False
        self.assertEqual(self._resolve({})[0], '')

