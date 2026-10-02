# -*- coding: utf-8 -*-
"""Quoted text is not formula syntax.

The validator reads a formula with regexes — operators, brackets, cell
references, function names, the character whitelist. Inside double quotes none
of that is syntax: it is a job title, a department, a "YES", something somebody
typed into a spreadsheet cell. Every one of those checks used to read straight
through the quotes.

It surfaced on a real Rize Vietnam configuration, whose transport allowance
reads

    =IF(OR(VITRIPOSITIO="Junior Agronomist", ... ,
           VITRIPOSITIO="Compliance Officer – Export & Sustainability"),
        ROUND((800000/NGAYCONGCHUA)*SONGAYLAMVIE,0), ...)

The dash in that last job title is an EN DASH (U+2013) — what a spreadsheet's
autocorrect makes of a typed hyphen, invisible to the person who typed it. The
character whitelist refused the whole rule over it: "Invalid characters: {'–'}".

The engine itself was never confused; only the checker was. So the corpus below
is mostly the shapes that a job title can legitimately contain and a formula
cannot — and, just as important, the shapes that must STILL be refused when
they appear outside quotes, because a checker that passes everything is worth
nothing.

Pure Python, no database: runs under
``python3 pb_hr_payroll_formula/tests/test_formula_string_literals.py`` from the
repository root as well as under Odoo's test runner. Deliberately NOT imported
in ``tests/__init__.py`` for that reason — see the note there.
"""

import os
import sys
import unittest

if __package__ in (None, ''):                       # bare `python3 …` invocation
    import importlib.util

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    _engine = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'formula_engine')
    validator = _load('validator', os.path.join(_engine, 'validator.py'))
else:
    from ..formula_engine import validator


FormulaValidator = validator.FormulaValidator
blank_string_literals = validator.blank_string_literals

#: The columns the Rize Vietnam configuration actually has, as the validator
#: wants them: letter -> code. Only the ones the formulas below reach.
COLUMNS = {
    'C': 'VITRIPOSITIO',
    'L': 'NGAYCONGCHUA',
    'M': 'SONGAYLAMVIE',
    'V': 'XANGXETRANSP',
}

#: The rule that started this, verbatim from the configuration — en dash and
#: all. Written against column letters, which is how it is stored.
RIZE_TRANSPORT = (
    '=IF(OR(C2="Junior Agronomist",C2="Research Agronomist",'
    'C2="Senior Agronomist",C2="Supply Chain Specialist",'
    'C2="Compliance Officer – Export & Sustainability"),'
    'ROUND((800000/L2)*M2,0),'
    'IF(C2="Territory Manager", ROUND((960000/L2)*M2,0),0))'
)


class TestStringLiteralsAreNotSyntax(unittest.TestCase):

    def setUp(self):
        self.v = FormulaValidator()

    def _ok(self, formula, columns=None):
        valid, message = self.v.validate_formula(
            formula, columns if columns is not None else COLUMNS)
        self.assertTrue(valid, "expected clean, got: %s" % message)
        return message

    def _bad(self, formula, columns=None):
        valid, message = self.v.validate_formula(
            formula, columns if columns is not None else COLUMNS)
        self.assertFalse(valid, "expected a complaint, formula passed")
        return message

    # -- 1. the reported bug ------------------------------------------------

    def test_01_the_rize_transport_rule_is_valid(self):
        """The whole real formula, en dash included, passes."""
        self._ok(RIZE_TRANSPORT)

    def test_02_an_en_dash_in_a_job_title_is_not_an_invalid_character(self):
        message = self.v.validate_formula('=IF(C2="Export – Sales",1,0)', COLUMNS)[1]
        self.assertNotIn('Invalid characters', message)

    def test_03_other_punctuation_a_job_title_carries(self):
        """Em dash, curly quote, slash, accents, Vietnamese — all fine inside
        quotes. Every one of these appears in a real HR title somewhere."""
        for title in ('Head — Payroll', 'People’s Officer', 'QA/QC Lead',
                      'Trưởng phòng Nhân sự', 'R&D (Hanoi) #2',
                      'Manager, Level 3 — 50% FTE'):
            with self.subTest(title=title):
                self._ok('=IF(C2="%s",1,0)' % title)

    # -- 2. the other four checks read through quotes too -------------------

    def test_04_a_bracket_in_a_title_does_not_unbalance_the_formula(self):
        self._ok('=IF(C2="Analyst (Payroll)",1,0)')

    def test_05_an_unclosed_bracket_in_a_title_does_not_unbalance_it_either(self):
        """The shape that would have been reported as 'Missing 1 closing
        parenthesis' — the quotes make it text, not a bracket."""
        self._ok('=IF(C2="Analyst (Payroll",1,0)')

    def test_06_a_function_name_in_a_title_is_not_an_unsupported_function(self):
        message = self.v.validate_formula('=IF(C2="PAYROLL(Senior)",1,0)', COLUMNS)[1]
        self.assertNotIn('Unsupported function', message)

    def test_07_a_cell_reference_in_a_title_is_not_an_unknown_column(self):
        """'ZZ99 Warehouse' looks exactly like a cell reference."""
        message = self.v.validate_formula('=IF(C2="ZZ99 Warehouse",1,0)', COLUMNS)[1]
        self.assertNotIn('Unknown column', message)

    def test_08_operators_in_a_title_are_not_consecutive_operators(self):
        message = self.v.validate_formula('=IF(C2="Grade A++",1,0)', COLUMNS)[1]
        self.assertNotIn('Consecutive operators', message)

    def test_09_a_title_ending_in_an_operator_does_not_end_the_formula(self):
        message = self.v.validate_formula('=IF(C2="Band C+",1,0)', COLUMNS)[1]
        self.assertNotIn('ends with an operator', message)

    def test_10_empty_brackets_in_a_title_are_not_empty_brackets(self):
        message = self.v.validate_formula('=IF(C2="Trainee ()",1,0)', COLUMNS)[1]
        self.assertNotIn('Empty parentheses', message)

    # -- 3. the escape Excel actually uses ----------------------------------

    def test_11_a_doubled_quote_inside_a_literal_is_one_quote(self):
        """Excel writes a quote inside a string by doubling it. The literal here
        is: Head of "Special" Projects."""
        self._ok('=IF(C2="Head of ""Special"" Projects",1,0)')

    def test_12_two_literals_side_by_side_do_not_merge(self):
        """`"a"&"b"` must not be read as one literal swallowing the `&`."""
        self._ok('=IF(C2="a"&"b",1,0)')

    # -- 4. nothing outside quotes got easier -------------------------------

    def test_13_an_en_dash_outside_quotes_is_still_refused(self):
        """The same character, used as a minus sign, is still wrong: it is not
        an operator and the engine cannot run it."""
        self.assertIn('Invalid characters', self._bad('=L2 – M2'))

    def test_14_an_unbalanced_bracket_outside_quotes_is_still_refused(self):
        self.assertIn('parenthesis', self._bad('=ROUND((800000/L2)*M2,0'))

    def test_15_an_unsupported_function_outside_quotes_is_still_refused(self):
        self.assertIn('Unsupported function', self._bad('=XLOOKUP(C2,L2,M2)'))

    def test_16_an_unknown_column_outside_quotes_is_still_refused(self):
        self.assertIn('Unknown column', self._bad('=ZZ2+L2'))

    def test_17_consecutive_operators_outside_quotes_are_still_refused(self):
        self.assertIn('Consecutive operators', self._bad('=L2**M2'))

    def test_18_a_complaint_about_the_text_outside_still_names_it(self):
        """A formula that is wrong OUTSIDE the quotes must still be caught even
        when it also has a perfectly innocent literal — the blanking must not
        swallow the rest of the line."""
        self.assertIn('Invalid characters',
                      self._bad('=IF(C2="Export – Sales",L2 – M2,0)'))

    # -- 5. the helper itself ------------------------------------------------

    def test_19_blanking_keeps_the_literal_a_literal(self):
        """A formula that IS a string stays syntactically whole, so the checks
        downstream never see a stray quote."""
        self.assertEqual(blank_string_literals('="x"'), '=""')
        self.assertEqual(blank_string_literals('=IF(C2="a",1,0)'), '=IF(C2="",1,0)')

    def test_20_blanking_leaves_a_formula_without_quotes_untouched(self):
        for formula in ('=ROUND((800000/L2)*M2,0)', '=L2+M2', '', '=SUM(A2:C2)'):
            with self.subTest(formula=formula):
                self.assertEqual(blank_string_literals(formula), formula)

    def test_21_an_unterminated_quote_does_not_eat_the_formula(self):
        """A missing closing quote is a typo, not a licence to blank the rest of
        the line — the tail must survive so its own errors are still reported."""
        self.assertIn('L2', blank_string_literals('=IF(C2="oops,L2,0)'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
