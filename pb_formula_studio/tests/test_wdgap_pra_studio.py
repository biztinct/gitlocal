# -*- coding: utf-8 -*-
"""WDGAP PR-A — the Formula Studio refuses unusable functions on save and
shows the one function list.

T4 (Studio side): save_formula / save_component / bulk_save_formulas refuse a
CHANGED formula using TODAY(), NOW() or an unknown function, in plain words;
an unchanged stored formula is never re-checked. The live check says the same.
T5 (Studio side): the function list the editor reads is the engine's table.
T6 (Studio side): the editor's "add component" never mints a function name.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.formula_engine import functions

PERIOD_SENTENCE = ("A payslip must give the same answer whenever it is worked out. "
                   "Use the pay period instead, for example DATE(PAYYEAR, PAYMONTH, ENDDAY).")


@tagged('post_install', '-at_install', 'wdgap_pra')
class TestWdgapPraStudio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'WDGAP PR-A studio', 'code': 'WDGAPPRAS',
            'country_code': 'VN', 'state': 'draft',
        })
        Rule = cls.env['hr.formula.rule']
        cls.join = Rule.create({'config_id': cls.config.id, 'name': 'Joined',
                                'code': 'JOINDATE', 'column_type': 'input',
                                'value_kind': 'date'})
        cls.year = Rule.create({'config_id': cls.config.id, 'name': 'Pay year',
                                'code': 'PAYYEAR', 'column_type': 'input'})
        cls.month = Rule.create({'config_id': cls.config.id, 'name': 'Pay month',
                                 'code': 'PAYMONTH', 'column_type': 'input'})
        cls.endday = Rule.create({'config_id': cls.config.id, 'name': 'End day',
                                  'code': 'ENDDAY', 'column_type': 'input'})
        cls.service = Rule.create({'config_id': cls.config.id, 'name': 'Years of service',
                                   'code': 'SERVICE', 'column_type': 'formula',
                                   'excel_formula': '=0'})

    def test_01_save_formula_refuses_today_and_unknown_functions(self):
        r = self.Studio.save_formula(self.service.id, '=YEAR(TODAY())-YEAR(JOINDATE)')
        self.assertFalse(r['ok'])
        self.assertIn(PERIOD_SENTENCE, r['msg'])
        self.assertEqual(self.service.excel_formula, '=0')
        r = self.Studio.save_formula(self.service.id, '=NETWORKDAYS(JOINDATE, 1)')
        self.assertFalse(r['ok'])
        self.assertIn('NETWORKDAYS is not a function formulas can use', r['msg'])
        good = '=DATEDIF(JOINDATE,DATE(PAYYEAR,PAYMONTH,ENDDAY),"Y")'
        r = self.Studio.save_formula(self.service.id, good)
        self.assertTrue(r['ok'], r)
        self.assertEqual(self.service.excel_formula, good)
        self.assertIn('self._datedif(', self.service.python_formula)

    def test_02_save_component_checks_only_a_changed_formula(self):
        r = self.Studio.save_component(self.service.id, {'excel_formula': '=NOW()'})
        self.assertFalse(r['ok'])
        self.assertIn('NOW() can\'t be used in a formula.', r['msg'])
        # a formula stored before PR-A with TODAY() in it: renaming the
        # component is not a formula save and is not refused
        self.env.cr.execute("UPDATE hr_formula_rule SET excel_formula = '=TODAY()' WHERE id = %s",
                            (self.service.id,))
        self.service.invalidate_recordset(['excel_formula'])
        r = self.Studio.save_component(self.service.id,
                                       {'name': 'Service (renamed)', 'excel_formula': '=TODAY()'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(self.service.name, 'Service (renamed)')
        self.assertEqual(self.service.excel_formula, '=TODAY()')

    def test_03_bulk_save_skips_refused_items(self):
        r = self.Studio.bulk_save_formulas([
            {'rule_id': self.service.id, 'formula': '=FOO(JOINDATE)'},
        ])
        self.assertEqual(r['saved'], 0)
        self.assertEqual(len(r['refused']), 1)
        self.assertIn('FOO is not a function', r['refused'][0]['msg'])

    def test_04_live_check_names_the_function_in_plain_words(self):
        r = self.Studio.validate_formula_live(self.config.id, '=TODAY()')
        self.assertFalse(r['valid'])
        self.assertIn(PERIOD_SENTENCE, r['message'])
        r = self.Studio.validate_formula_live(self.config.id, '=EDATE(A2, 2)')
        self.assertNotIn('Unsupported function', r['message'])
        self.assertNotIn('EDATE', r['message'])

    def test_05_the_editor_list_is_the_engine_table(self):
        listed = self.env['hr.formula.rule'].pb_formula_functions()
        self.assertEqual([f['name'] for f in listed], [row['name'] for row in functions.rows()])
        datedif = next(f for f in listed if f['name'] == 'DATEDIF')
        self.assertTrue(datedif['help'])
        self.assertEqual(datedif['category'], 'date')
        self.assertIn('DATE(PAYYEAR, PAYMONTH, ENDDAY)',
                      next(f for f in listed if f['name'] == 'DATE')['help'])

    def test_06_add_component_never_mints_a_function_name(self):
        for name in ('Year', 'Day', 'Date'):
            r = self.Studio.add_component(self.config.id, {'name': name, 'column_type': 'input'})
            code = self.env['hr.formula.rule'].browse(r['rule_id']).code
            self.assertNotIn(code, functions.RESERVED_CODE_NAMES, name)
