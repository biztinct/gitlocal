# -*- coding: utf-8 -*-
"""BP-R12 — the formula checker knows the engine's own band tables.

`BRACKET(<table>, <value>)` is not an Excel function; it is the primitive the
converter expands into a progressive band chain before anything runs. The
static checker never knew that, so every configuration built on a country rule
pack reported an error for the one formula the whole pack rests on — measured
on Vietnam: personal income tax computed correctly while the same rule was
flagged "Unsupported function: BRACKET", and the configuration card said
"2 errors" about a healthy payroll.

The fix is expansion, never a fake entry in the supported-function list: a
table that does not exist must still be an error, and it now says which one.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBracketLint(TransactionCase):

    def _config(self):
        config = self.env['hr.formula.config'].create({
            'name': 'BRACKET lint check',
            'country_code': 'VN',
            'state': 'draft',
        })
        table = self.env['hr.formula.rate.table'].create({
            'config_id': config.id, 'code': 'TESTTAX', 'name': 'Test bands',
        })
        self.env['hr.formula.rate.bracket'].create([
            {'table_id': table.id, 'lower': 0.0, 'rate': 0.05},
            {'table_id': table.id, 'lower': 5000000.0, 'rate': 0.1},
        ])
        self.env['hr.formula.rule'].create([
            {'config_id': config.id, 'code': 'INCOME', 'name': 'Income',
             'column_type': 'input', 'sequence': 10},
            {'config_id': config.id, 'code': 'TAXDUE', 'name': 'Tax due',
             'column_type': 'formula', 'sequence': 20,
             'excel_formula': '=BRACKET(TESTTAX,A1)'},
        ])
        return config

    def test_bracket_formula_is_valid(self):
        config = self._config()
        config.action_validate_formulas()
        rule = config.rule_ids.filtered(lambda r: r.code == 'TAXDUE')
        self.assertTrue(rule.is_valid,
                        "a band-table formula the engine computes must not be "
                        "reported as an error: %s" % rule.validation_message)
        config.invalidate_recordset(['has_errors'])
        self.assertFalse(config.has_errors)

    def test_unknown_band_table_is_still_an_error(self):
        config = self._config()
        rule = config.rule_ids.filtered(lambda r: r.code == 'TAXDUE')
        rule.excel_formula = '=BRACKET(NOSUCHTAX,A1)'
        config.action_validate_formulas()
        self.assertFalse(rule.is_valid)
        self.assertIn('NOSUCHTAX', rule.validation_message or '')

    def test_a_genuinely_broken_formula_is_still_broken(self):
        config = self._config()
        rule = config.rule_ids.filtered(lambda r: r.code == 'TAXDUE')
        rule.excel_formula = '=WOBBLE(A1)'
        config.action_validate_formulas()
        self.assertFalse(rule.is_valid)

    def test_missing_rate_tables_helper(self):
        config = self._config()
        self.assertEqual(config._missing_rate_tables('=BRACKET(TESTTAX,A1)'), [])
        self.assertEqual(config._missing_rate_tables('=BRACKET(OTHER,A1)'),
                         ['OTHER'])
        self.assertEqual(config._missing_rate_tables('=A1+B1'), [])
