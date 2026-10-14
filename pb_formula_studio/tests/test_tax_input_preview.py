"""The live preview must show the same categorical input the engine reads."""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'tax_input_preview')
class TestTaxInputPreview(TransactionCase):
    def test_text_status_identifier_and_review_result_survive_preview(self):
        config = self.env['hr.formula.config'].create({
            'name': 'Indonesia preview test', 'code': 'ID_PREVIEW_TEST',
            'country_code': 'ID', 'company_id': self.env.company.id})
        Rule = self.env['hr.formula.rule']
        Rule.create({'config_id': config.id, 'name': 'PTKP status', 'code': 'PTKPSTATUS',
                     'column_type': 'input', 'forced_column_letter': 'A',
                     'value_kind': 'text', 'is_text_component': True})
        Rule.create({'config_id': config.id, 'name': 'Employee ID', 'code': 'EMPKEY',
                     'column_type': 'input', 'forced_column_letter': 'B',
                     'value_kind': 'identifier', 'is_text_component': True})
        Rule.create({'config_id': config.id, 'name': 'Tax test', 'code': 'TAXTEST',
                     'column_type': 'formula', 'forced_column_letter': 'C',
                     'excel_formula': '=IF(A1="S/0",100,"Review tax status")'})
        sample = self.env['hr.formula.sample.data'].create({
            'config_id': config.id, 'name': 'Fictional input',
            'input_values_json': json.dumps({'PTKPSTATUS': 'S/0', 'EMPKEY': '0017'})})
        studio = self.env['pb.formula.studio']
        values = studio._compute(config, sample.id)['values']
        self.assertEqual(values, {'A': 'S/0', 'B': '0017', 'C': 100.0})
        sample.input_values_json = json.dumps({'PTKPSTATUS': 'Unknown', 'EMPKEY': '0017'})
        self.assertEqual(studio._compute(config, sample.id)['values']['C'], 'Review tax status')
