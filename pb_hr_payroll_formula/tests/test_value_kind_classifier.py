# -*- coding: utf-8 -*-
"""The value-kind ladder and the operand parser, with NO database.

Same shape as `test_column_role_classifier.py` and for the same reason: both
modules under test are plain Python with no `odoo` import, so the table of
expected answers can be run with a bare `python3` — which is how it gets run
while the ladder is being tuned, long before an Odoo test run is affordable.

    python3 pb_hr_payroll_formula/tests/test_value_kind_classifier.py

Deliberately NOT imported from `tests/__init__.py`; the Odoo-side behaviour
(field defaults, the person-wins write, the classifier RPC) lives in
`test_value_kinds.py`.
"""
import os
import sys
import types
import unittest
import importlib.util


def _load():
    """Import the two modules by path, under a stand-in package.

    `value_kind_classifier` does `from .column_role_classifier import …`, so it
    needs a package to be relative TO. The same trick the sibling battery uses.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    models = os.path.join(os.path.dirname(here), 'models')
    pkg = types.ModuleType('_vk_pkg')
    pkg.__path__ = [models]
    sys.modules['_vk_pkg'] = pkg
    out = {}
    for name in ('column_role_classifier', 'formula_operand_context',
                 'value_kind_classifier'):
        spec = importlib.util.spec_from_file_location(
            '_vk_pkg.%s' % name, os.path.join(models, '%s.py' % name))
        module = importlib.util.module_from_spec(spec)
        sys.modules['_vk_pkg.%s' % name] = module
        spec.loader.exec_module(module)
        out[name] = module
    return out


_MODULES = _load()
foc = _MODULES['formula_operand_context']
vkc = _MODULES['value_kind_classifier']


class TestOperandContext(unittest.TestCase):
    """Case 1-5 of the phase plan: which operator touches which reference."""

    def ctx(self, formula):
        return {k: sorted(v) for k, v in foc.operand_contexts(formula).items()}

    def test_01_text_compare_and_arithmetic_in_one_formula(self):
        """ABM's ACTUALMEAL — the formula this whole programme came from."""
        got = self.ctx('=IF(F5="La Nga",0,(X5/AB5*AD5))')
        self.assertEqual(got['F'], ['strcmp'])
        self.assertNotIn('arith', got['F'])
        for ref in ('X', 'AB', 'AD'):
            self.assertIn('arith', got[ref], "%s is divided or multiplied" % ref)

    def test_02_string_compare_and_ordering_are_different_answers(self):
        got = self.ctx('=IF(F5="La Nga",0,IF(F5="HCM",IF(AS5="YES",IF($BS5>0,45000))))')
        self.assertEqual(got['F'], ['strcmp'])
        self.assertEqual(got['AS'], ['strcmp'])
        self.assertEqual(got['BS'], ['numcmp'])

    def test_03_every_member_of_a_range_is_arithmetic(self):
        got = self.ctx('=SUM(AE5:AX5)+BM5')
        for ref in ('AE', 'AX', 'BM'):
            self.assertIn('arith', got[ref])

    def test_04_last_operand_of_a_chain_is_not_dropped(self):
        """`X5/AB5*AD5` — a regex over pairs eats the operators and loses AD5."""
        got = self.ctx('=A1+B1+C1+D1')
        for ref in ('A', 'B', 'C', 'D'):
            self.assertIn('arith', got[ref], '%s lost from the chain' % ref)

    def test_05_operators_inside_a_string_literal_are_not_operators(self):
        got = self.ctx('=IF(A1="a+b",1,2)')
        self.assertEqual(got['A'], ['strcmp'])

    def test_05b_a_long_code_is_one_reference_not_four(self):
        """`BASESALARY` must not read as BAS + ESA + LAR + Y."""
        got = self.ctx('=ROUND(BASESALARY*0.105,0)')
        self.assertEqual(sorted(got), ['BASESALARY'])

    def test_05c_text_functions_mark_their_arguments(self):
        self.assertEqual(self.ctx('=LEFT(FULLNAME,3)'), {'FULLNAME': ['textfn']})

    def test_05d_nothing_raises(self):
        for junk in ('', None, '=(((', '=IF(', '"', 123):
            self.assertIsInstance(foc.operand_contexts(junk), dict)

    def test_05e_roundtrip(self):
        contexts = foc.operand_contexts('=IF(F5="X",0,A1*2)')
        self.assertEqual(foc.deserialize(foc.serialize(contexts)), contexts)


class TestValueKindLadder(unittest.TestCase):
    """Cases 6-10: the ladder, on the shapes that actually occur."""

    def kind(self, **kwargs):
        return vkc.classify_value_kind(**kwargs)[0]

    def test_06_compared_as_text_is_text(self):
        """ABM LOCATION: role profile, only ever compared, 152 texty values."""
        self.assertEqual(self.kind(
            code='LOCATION', name='Location', column_role='profile',
            net_role='info', contexts={'strcmp'},
            sample_values=['Ho Chi Minh Branch', 'La Nga'] * 20), 'text')

    def test_07_identity_column_is_an_identifier(self):
        self.assertEqual(self.kind(
            code='EMPLOYEECODE', name='Employee Code', column_role='identity',
            net_role='info', contexts=set(),
            sample_values=['11450', '11677', '11688']), 'identifier')

    def test_08_leading_zeros_mean_a_name(self):
        self.assertEqual(self.kind(
            code='EMPBANKACCOA', name='Employee Bank Account No.',
            column_role='payroll', net_role='info', contexts=set(),
            sample_values=['0071001234567', '0071001182392']), 'identifier')

    def test_09_arithmetic_beats_everything_below_it(self):
        self.assertEqual(self.kind(
            code='BASESALARY', name='Base Salary', column_role='profile',
            net_role='', contexts={'arith'},
            sample_values=['12500000', '18500000']), 'money')

    def test_09b_arithmetic_beats_a_text_compare_on_the_same_ref(self):
        kind, reason = vkc.classify_value_kind(
            code='X', name='Mixed', column_role='payroll',
            contexts={'arith', 'strcmp'}, sample_values=['1', '2'])
        self.assertEqual(kind, 'money')
        self.assertIn('arithmetic wins', reason)

    def test_10_no_signal_at_all_stays_money(self):
        """The neutral default: an unclassified scheme must not change."""
        self.assertEqual(self.kind(code='ZZZ', name='Something'), 'money')

    def test_10b_unanimous_values_outrank_a_derived_net_role(self):
        """ABM SHUIPARTICIP carries net_role='earning' and 152 values of "YES".

        `net_role` is itself derived from the formula graph; the values are the
        thing itself. Letting the derived signal win would turn the one text
        component that works today back into 0.0.
        """
        self.assertEqual(self.kind(
            code='SHUIPARTICIP', name='SHUI Participation',
            column_role='contract', net_role='earning', contexts=set(),
            sample_values=['YES', 'NO', 'YES']), 'boolean')

    def test_10c_a_date_is_recognised_but_a_bare_number_is_not(self):
        self.assertTrue(vkc.looks_like_a_date('2022-04-04'))
        self.assertTrue(vkc.looks_like_a_date('04/04/2022'))
        self.assertFalse(vkc.looks_like_a_date('11450'),
                         "an employee code must never read as a year")
        self.assertFalse(vkc.looks_like_a_date(''))
        self.assertEqual(self.kind(
            code='DATEOFJOININ', name='Date of Joining', column_role='contract',
            net_role='info', contexts=set(),
            sample_values=['2025-06-02', '2022-04-04']), 'date')

    def test_10d_a_computed_column_is_always_numeric(self):
        self.assertEqual(self.kind(
            code='NETPAY', name='Net Pay', column_type='formula',
            column_role='payroll', contexts=set()), 'money')

    def test_10e_quantity_is_split_out_of_money(self):
        self.assertEqual(self.kind(
            code='OT15HOURS', name='OT 1.5 Hours', column_role='payroll',
            contexts={'arith'}, quantity=True), 'quantity')

    def test_10f_a_named_reference_number_is_not_an_amount(self):
        self.assertEqual(self.kind(
            code='INSBOOKNO', name='Insurance Book Number',
            column_role='payroll', net_role='info', contexts=set(),
            appears_on_payslip=False,
            sample_values=['7912358272', '7920123456']), 'identifier')

    def test_10g_number_of_dependants_is_a_count_not_a_reference(self):
        self.assertNotEqual(self.kind(
            code='NOOFDEPENDEN', name='Number of Dependants',
            column_role='payroll', contexts={'arith'}, quantity=True,
            sample_values=['2', '0', '1']), 'identifier')


class TestContradictions(unittest.TestCase):

    def test_11_money_contradicted_by_text(self):
        bad = vkc.contradictions('money', ['1000', 'Ho Chi Minh Branch', ''])
        self.assertEqual(bad, ['Ho Chi Minh Branch'])

    def test_11b_a_correct_column_reports_nothing(self):
        self.assertEqual(vkc.contradictions('text', ['anything', 123, None]), [])
        self.assertEqual(vkc.contradictions('money', ['1,000', '2.5', None]), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
