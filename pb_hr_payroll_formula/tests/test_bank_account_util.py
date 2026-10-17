# -*- coding: utf-8 -*-
"""Pure-Python tests for the imported-account-number sanitizer (COLROLES P3, test 1).

DELIBERATELY NOT listed in `tests/__init__.py`, for the same reason as
`test_column_role_classifier.py`: the module under test has no `odoo` import and no
database, and the point of that design is that this table runs without either.

    python3 -m pytest pb_hr_payroll_formula/tests/test_bank_account_util.py
    python3 pb_hr_payroll_formula/tests/test_bank_account_util.py
"""

import importlib.util
import pathlib
import unittest

_MODULE_PATH = (pathlib.Path(__file__).resolve().parents[1]
                / 'models' / 'bank_account_util.py')
_spec = importlib.util.spec_from_file_location('bank_account_util', _MODULE_PATH)
bau = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bau)


class TestSanitizeAccNumber(unittest.TestCase):
    """The handover's numbered table 1, plus the cases it implies."""

    # (raw, expected_number, expected_damaged, why)
    CASES = [
        # --- the leading zero, which is the entire reason this function exists
        ('0071000123456', '0071000123456', False, 'clean string is left alone'),
        (' 007-100 0123 456 ', '0071000123456', False, 'grouping separators stripped'),
        ('007 100 0123 456', '0071000123456', False, 'NBSP stripped'),
        ('0071.000.123.456', '0071000123456', False, 'dot grouping stripped'),
        # --- numbers that arrived as numbers
        (1234567890.0, '1234567890', False, 'integer-valued float keeps no .0'),
        (1234567890, '1234567890', False, 'plain int'),
        (0.0, '0', False, 'zero is a value, not a blank'),
        # --- damage we can detect and must not guess past
        ('1.23456789012E+11', None, True, 'scientific-notation string is damage'),
        ('1.23456789012e+11', None, True, 'lower-case exponent too'),
        (123.45, None, True, 'a non-integer float is not an account number'),
        (float(2 ** 53), None, True, 'beyond exact float integers the digits are fiction'),
        ('12 34/AB?', None, True, 'a stray punctuation mark means we misread the cell'),
        # --- absence is not damage
        ('', None, False, 'empty string'),
        ('   ', None, False, 'whitespace only'),
        (None, None, False, 'no value at all'),
        ('---', None, False, 'separators only collapse to nothing'),
        (True, None, False, 'a boolean is never an account number'),
        # --- alphanumeric formats must survive
        ('VN82BFTV0071000123456', 'VN82BFTV0071000123456', False, 'IBAN-shaped'),
        ('vn82 bftv 0071', 'vn82bftv0071', False, 'IBAN with spaces, case preserved'),
    ]

    def test_table(self):
        for raw, expected, damaged, why in self.CASES:
            with self.subTest(raw=raw, why=why):
                got, bad = bau.sanitize_acc_number(raw)
                self.assertEqual(got, expected, why)
                self.assertEqual(bad, damaged, why)

    def test_idempotent(self):
        """Re-sanitizing a sanitized value must be a no-op — the import stores the
        clean form and the next run compares against it."""
        for raw, expected, damaged, _why in self.CASES:
            if damaged or expected is None:
                continue
            again, bad = bau.sanitize_acc_number(expected)
            self.assertFalse(bad)
            self.assertEqual(again, expected)


class TestSanitizeBankText(unittest.TestCase):
    def test_table(self):
        self.assertEqual(bau.sanitize_bank_text('  Vietcombank '), 'Vietcombank')
        self.assertEqual(bau.sanitize_bank_text(1234.0), '1234')
        self.assertEqual(bau.sanitize_bank_text(''), None)
        self.assertEqual(bau.sanitize_bank_text(None), None)
        self.assertEqual(bau.sanitize_bank_text(True), None)
        self.assertEqual(bau.sanitize_bank_text('Ngân hàng Á Châu'), 'Ngân hàng Á Châu')


class TestAccNumbersMatch(unittest.TestCase):
    def test_matching(self):
        self.assertTrue(bau.acc_numbers_match('0071000123456', ' 007-100 0123 456 '))
        self.assertTrue(bau.acc_numbers_match('vn82bftv', 'VN82 BFTV'))
        self.assertFalse(bau.acc_numbers_match('0071000123456', '71000123456'))
        self.assertFalse(bau.acc_numbers_match('1.2e+11', '120000000000'))
        self.assertFalse(bau.acc_numbers_match('', '0071'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
