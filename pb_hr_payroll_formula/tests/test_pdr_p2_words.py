# -*- coding: utf-8 -*-
"""PDR P2 — Yes / No and words wherever a flag is shown; numbers stay stored.

T1 worksheet columns carry the words, T2 a toggle save stores the number,
T4 the engine import reads Y / N / words (never a silent 0), T5 a rule
without words is untouched, T7 the full contract form edits the word.
"""
import json

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models.contract_fill_in import (
    parse_value_labels, value_from_words)

YES_NO = '0=No;1=Yes'
MODE = '0=None;1=Insurance tax;2=All tax'


@tagged('post_install', '-at_install', 'pdr_p2')
class TestPdrP2Helper(TransactionCase):

    def test_value_from_words_accepts_every_spelling(self):
        yes_no = parse_value_labels(YES_NO)
        for raw, expected in (('Y', 1), ('n', 0), ('YES', 1), ('no', 0), ('1', 1), ('0', 0),
                              (' y ', 1), (1, 1), (0.0, 0), (True, 1), (False, 0)):
            with self.subTest(raw=raw):
                self.assertEqual(value_from_words(yes_no, raw, 'Final tax period'), expected)
        mode = parse_value_labels(MODE)
        for raw, expected in (('All tax', 2), ('all tax', 2), (' insurance TAX ', 1), ('None', 0), ('2', 2)):
            with self.subTest(raw=raw):
                self.assertEqual(value_from_words(mode, raw, 'Tax allowance mode'), expected)

    def test_unknown_word_is_a_plain_sentence_never_zero(self):
        with self.assertRaisesRegex(ValueError, r'^Final tax period needs Y or N\.$'):
            value_from_words(parse_value_labels(YES_NO), 'maybe', 'Final tax period')
        with self.assertRaisesRegex(ValueError, r'^Tax allowance mode needs one of: None, Insurance tax, All tax\.$'):
            value_from_words(parse_value_labels(MODE), 'Y', 'Tax allowance mode')


@tagged('post_install', '-at_install', 'pdr_p2')
class TestPdrP2EngineImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'PDR P2 words', 'code': 'PDRP2WORDS', 'country_code': 'ID'})
        Rule = cls.env['hr.formula.rule']
        cls.final = Rule.create({'config_id': cls.config.id, 'name': 'Final tax period', 'code': 'PWFINAL',
                                 'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'integer',
                                 'value_labels': YES_NO})
        cls.mode = Rule.create({'config_id': cls.config.id, 'name': 'Tax allowance mode', 'code': 'PWMODE',
                                'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'integer',
                                'value_labels': MODE})
        cls.bonus = Rule.create({'config_id': cls.config.id, 'name': 'Bonus', 'code': 'PWBONUS',
                                 'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money'})
        Rule.create({'config_id': cls.config.id, 'name': 'Uses them', 'code': 'PWUSE',
                     'column_type': 'formula', 'column_role': 'payroll', 'net_role': 'earning',
                     'appears_on_payslip': True,
                     'excel_formula': '=PWFINAL*100+PWMODE*10+PWBONUS'})
        for rule in (cls.final, cls.mode, cls.bonus):
            rule.set_source_binding('excel', rule.name)
        cls.employee = cls.env['hr.employee'].create({'name': 'PDR P2 import'})
        cls.contract = cls.env['hr.contract'].create({'name': 'PDR P2 import', 'employee_id': cls.employee.id,
                                                      'wage': 1000, 'state': 'draft'})
        cls.batch = cls.env['hr.payroll.import.batch'].create({
            'name': 'PDR P2 import', 'source_type': 'excel', 'formula_config_id': cls.config.id})

    def _inputs(self, raw):
        return self.batch._transform_data_to_formula_inputs(raw, contract=self.contract)

    def test_p2_t4_attached_file_words_compute_like_numbers(self):
        numbers = self._inputs({'Final tax period': 1, 'Tax allowance mode': 2, 'Bonus': 5})
        for final, mode in (('Y', 'All tax'), ('yes', 'all tax'), (' y ', 'ALL TAX'), ('1', '2')):
            with self.subTest(final=final, mode=mode):
                words = self._inputs({'Final tax period': final, 'Tax allowance mode': mode, 'Bonus': 5})
                self.assertEqual(words['PWFINAL'], 1.0)
                self.assertEqual(words['PWMODE'], 2.0)
                self.assertEqual({k: words[k] for k in numbers}, numbers)
        no = self._inputs({'Final tax period': 'N', 'Tax allowance mode': 'None', 'Bonus': 5})
        self.assertEqual((no['PWFINAL'], no['PWMODE']), (0.0, 0.0))
        # the payslip formula sees the same numbers either way
        slip_y = self.env['hr.formula.sample.data'].new({'config_id': self.config.id})._evaluate_rules_with_dependencies(
            self._inputs({'Final tax period': 'Y', 'Tax allowance mode': 'All tax', 'Bonus': 5}), readonly=True)
        slip_1 = self.env['hr.formula.sample.data'].new({'config_id': self.config.id})._evaluate_rules_with_dependencies(
            self._inputs({'Final tax period': 1, 'Tax allowance mode': 2, 'Bonus': 5}), readonly=True)
        self.assertEqual(slip_y['PWUSE'], 125)
        self.assertEqual(slip_y, slip_1)

    def test_p2_t4_unknown_word_stops_the_row_never_zero(self):
        with self.assertRaisesRegex(UserError, 'Final tax period needs Y or N'):
            self._inputs({'Final tax period': 'maybe', 'Tax allowance mode': 1, 'Bonus': 5})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': self.batch.id, 'employee_id': self.employee.id, 'sequence': 3,
            'raw_data_json': json.dumps({'PWFINAL': 'maybe', 'PWMODE': 'All tax'})})
        errors = line.validate_line()
        self.assertIn('Row 3: Final tax period needs Y or N.', errors)
        self.assertFalse([e for e in errors if 'Tax allowance mode' in e])

    def test_p2_t5_rule_without_words_is_untouched(self):
        # a numeric column without words keeps the text it was given (as before)
        self.assertEqual(self._inputs({'Final tax period': 1, 'Tax allowance mode': 1, 'Bonus': 'Y'})['PWBONUS'], 'Y')
        self.assertEqual(self.bonus.value_to_text(5), 5)
        self.assertEqual(self.bonus.value_label_for(5), '')


@tagged('post_install', '-at_install', 'pdr_p2')
class TestPdrP2ContractForm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'PDR P2 contract words', 'code': 'PDRP2CONTRACT', 'country_code': 'ID',
            'state': 'active', 'company_id': cls.env.company.id})
        Rule = cls.env['hr.formula.rule']
        cls.flag = Rule.create({'config_id': cls.config.id, 'name': 'BPJS words covered', 'code': 'PWBPJS',
                                'column_type': 'input', 'value_kind': 'integer', 'is_contract_component': True,
                                'value_labels': YES_NO})
        cls.plain = Rule.create({'config_id': cls.config.id, 'name': 'Allowance plain', 'code': 'PWALLOW',
                                 'column_type': 'input', 'value_kind': 'money', 'is_contract_component': True})
        Template = cls.env['hr.contract.advantage.template']
        cls.t_flag = Template.create({'name': 'BPJS words covered', 'code': 'PWBPJS'})
        cls.t_plain = Template.create({'name': 'Allowance plain', 'code': 'PWALLOW'})
        cls.employee = cls.env['hr.employee'].create({'name': 'PDR P2 contract'})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'PDR P2 contract', 'employee_id': cls.employee.id, 'wage': 1000,
            'state': 'draft', 'company_id': cls.env.company.id})
        Line = cls.env['hr.contract.advantage']
        cls.line_flag = Line.create({'contract_id': cls.contract.id, 'advantage_template_id': cls.t_flag.id, 'amount': 1})
        cls.line_plain = Line.create({'contract_id': cls.contract.id, 'advantage_template_id': cls.t_plain.id, 'amount': 250})

    def test_p2_t7_worded_line_shows_and_edits_the_word(self):
        self.assertEqual(self.line_flag.pb_amount_word, 'Yes')
        self.assertEqual([o['label'] for o in json.loads(self.line_flag.pb_value_words)], ['Yes', 'No'])
        self.line_flag.pb_amount_word = 'No'
        self.line_flag.flush_recordset()
        self.line_flag.invalidate_recordset()
        self.assertTrue(self.line_flag.exists())     # "No" keeps the line, holding 0
        self.assertEqual(self.line_flag.amount, 0.0)
        self.assertEqual(self.line_flag.pb_amount_word, 'No')
        self.line_flag.write({'pb_amount_word': 'y'})
        self.assertEqual(self.line_flag.amount, 1.0)
        with self.assertRaisesRegex(ValidationError, 'needs Y or N'):
            self.line_flag.write({'pb_amount_word': 'maybe'})

    def test_p2_t7_line_without_words_keeps_the_number(self):
        self.assertFalse(self.line_plain.pb_value_words)
        self.assertFalse(self.line_plain.pb_amount_word)
        self.assertEqual(self.line_plain.amount, 250)

    def test_p2_t7_unmatched_number_shows_itself(self):
        self.line_flag.amount = 7
        self.assertEqual(self.line_flag.pb_amount_word, '7')

    def test_p2_t7_onchange_in_the_form_moves_the_amount(self):
        row = self.env['hr.contract.advantage'].new({
            'contract_id': self.contract.id, 'advantage_template_id': self.t_flag.id, 'amount': 1})
        self.assertEqual(row.pb_amount_word, 'Yes')
        row.pb_amount_word = 'No'
        row._onchange_pb_amount_word()
        self.assertEqual(row.amount, 0.0)
        view = self.env.ref('pb_hr_payroll_formula.view_hr_contract_form_component_words')
        self.assertIn('pb_amount_word', view.arch_db)
