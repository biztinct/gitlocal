# -*- coding: utf-8 -*-
"""Pure-Python tests for the column role classifier.

DELIBERATELY NOT listed in `tests/__init__.py`. The classifier has no `odoo` import
and no database, and the point of that design is that this table can be run and read
without either:

    python3 -m pytest pb_hr_payroll_formula/tests/test_column_role_classifier.py
    python3 pb_hr_payroll_formula/tests/test_column_role_classifier.py

The module is loaded straight off disk for the same reason — importing it through the
`odoo.addons` package would drag the whole registry in and defeat the exercise.
"""

import importlib.util
import pathlib
import unittest

_MODULE_PATH = (pathlib.Path(__file__).resolve().parents[1]
                / 'models' / 'column_role_classifier.py')
_spec = importlib.util.spec_from_file_location('column_role_classifier', _MODULE_PATH)
crc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crc)


# Test 1 — the table. Headers as an operator would actually type them, English and
# Vietnamese, mapped to the role and confidence we expect.
HEADER_TABLE = [
    # (header, expected_role, expected_tier)
    ('MSNV', 'identity', 'certain'),
    ('Mã nhân viên', 'identity', 'certain'),
    ('Ma so nhan vien', 'identity', 'certain'),
    ('Employee Code', 'identity', 'certain'),
    ('Emp. Code', 'identity', 'certain'),
    ('EmployeeID', 'identity', 'certain'),
    ('Employee Name', 'identity', 'certain'),
    ('Họ và tên', 'identity', 'certain'),
    ('Passport No', 'identity', 'certain'),

    ('Bank Name', 'bank', 'certain'),
    ('Số tài khoản', 'bank', 'certain'),
    ('Bank Account Number', 'bank', 'certain'),
    ('Account No', 'bank', 'certain'),
    ('Ngân hàng', 'bank', 'certain'),
    ('Chi nhánh', 'bank', 'certain'),
    ('IFSC Code', 'bank', 'certain'),
    ('Swift Code', 'bank', 'certain'),
    ('Beneficiary Name', 'bank', 'certain'),

    ('Date of Joining', 'contract', 'certain'),
    ('Joining Date', 'contract', 'certain'),
    ('Last Working Day', 'contract', 'certain'),
    ('Contract Type', 'contract', 'certain'),
    ('Probation End Date', 'contract', 'certain'),
    ('Ngày vào làm', 'contract', 'certain'),
    ('Loại hợp đồng', 'contract', 'certain'),

    ('Gender', 'profile', 'certain'),
    ('Marital Status', 'profile', 'certain'),
    ('Date of Birth', 'profile', 'certain'),
    ('Department', 'profile', 'certain'),
    ('Work Email', 'profile', 'certain'),
    ('Số điện thoại', 'profile', 'certain'),
    ('Phòng ban', 'profile', 'certain'),
    ('Chức vụ', 'profile', 'certain'),
    ('Employee Status', 'profile', 'certain'),
    ('Location', 'profile', 'certain'),
    ('Cost Center', 'profile', 'certain'),

    ('Phone Allowance', 'payroll', 'default'),
    ('Meal Allowance', 'payroll', 'default'),
    ('OT 1.5 Hours', 'payroll', 'default'),
    ('Base Salary', 'payroll', 'default'),
    ('Adjustment', 'payroll', 'default'),
    ('Thirteenth Month Salary', 'payroll', 'default'),
    ('Sales Incentive', 'payroll', 'default'),
    ('Standard Working Hour', 'payroll', 'default'),
    ('Bonus - STIP', 'payroll', 'default'),
    ('Other Deduction', 'payroll', 'default'),
]


class TestColumnRoleClassifier(unittest.TestCase):

    def test_01_header_table(self):
        failures = []
        for header, want_role, want_tier in HEADER_TABLE:
            role, tier, reason = crc.classify_column(header)
            if (role, tier) != (want_role, want_tier):
                failures.append('%-28r want=%-9s/%-8s got=%-9s/%-8s (%s)'
                                % (header, want_role, want_tier, role, tier, reason))
        self.assertFalse(failures, 'classification drift:\n  ' + '\n  '.join(failures))

    def test_02_unknown_header_defaults_to_payroll(self):
        role, tier, reason = crc.classify_column('Zorblax Factor Q')
        self.assertEqual((role, tier), ('payroll', 'default'))
        self.assertIn('payroll by policy', reason)

    def test_03_referenced_forces_payroll(self):
        # A column another formula depends on is payroll even when its header
        # screams "bank" — filing it elsewhere would break the arithmetic.
        self.assertEqual(
            crc.classify_column('Bank Name', is_referenced=True)[0], 'payroll')
        self.assertEqual(
            crc.classify_column('Bank Name', column_type='formula')[0], 'payroll')
        self.assertEqual(crc.classify_column('Bank Name')[0], 'bank')

    def test_04_identifier_row_forces_identity(self):
        role, tier, _r = crc.classify_column('Anything At All', on_identifier_row=True)
        self.assertEqual((role, tier), ('identity', 'certain'))

    def test_05_red_component_value_kind(self):
        numeric = crc.classify_column(
            'Gas Allowance', is_contract_component=True,
            sample_values=[1000, '2,500', 3000.5, ''])
        self.assertEqual((numeric[0], numeric[1]), ('payroll', 'certain'))

        empty = crc.classify_column(
            'Gas Allowance', is_contract_component=True, sample_values=[None, '', '  '])
        self.assertEqual(empty[0], 'payroll')

        texty = crc.classify_column(
            'Bank Account', is_contract_component=True, sample_values=['0071000123456'])
        self.assertEqual((texty[0], texty[1]), ('contract', 'certain'))

    def test_06_green_is_text_component(self):
        for samples in ([1, 2, 3], None, ['abc']):
            role, tier, reason = crc.classify_column(
                'Job Grade', is_text_component=True, sample_values=samples)
            self.assertEqual((role, tier), ('contract', 'certain'))
            self.assertIn('explicit text', reason)

    def test_07_is_texty_sample(self):
        self.assertFalse(crc.is_texty_sample('123'))
        self.assertTrue(crc.is_texty_sample('0123'))
        self.assertTrue(crc.is_texty_sample('abc'))
        self.assertFalse(crc.is_texty_sample(''))
        self.assertFalse(crc.is_texty_sample(None))
        self.assertFalse(crc.is_texty_sample('12.5'))
        self.assertFalse(crc.is_texty_sample('12,5'))
        self.assertFalse(crc.is_texty_sample(1234))
        self.assertFalse(crc.is_texty_sample(12.5))
        self.assertFalse(crc.is_texty_sample(True))
        self.assertTrue(crc.is_texty_sample('VND 1,000'))
        self.assertTrue(crc.is_blank_sample('   '))
        self.assertFalse(crc.is_blank_sample(0))

    def test_08_all_text_samples_become_reference(self):
        role, tier, _r = crc.classify_column(
            'Zorblax Factor Q', sample_values=['alpha', 'beta', ''])
        self.assertEqual((role, tier), ('reference', 'likely'))

    def test_09_normalisation_and_accents(self):
        self.assertEqual(crc.normalize_header('  Emp. Code  '), 'emp code')
        self.assertEqual(crc.normalize_header('Bank_Account/No'), 'bank account no')
        self.assertEqual(crc.strip_accents('hợp đồng'), 'hop dong')
        self.assertEqual(crc.normalize_header(None), '')

    def test_10_bank_wins_over_profile(self):
        # "Bank Name" must not be dragged into profile by the word "name".
        self.assertEqual(crc.classify_column('Bank Name')[0], 'bank')
        self.assertEqual(crc.classify_column('Branch')[0], 'bank')

    def test_11_lexicon_role_helper(self):
        self.assertEqual(crc.lexicon_role('Bank Name'), ('bank', 'certain'))
        self.assertEqual(crc.lexicon_role('Totally Unknown Widget'), (None, None))

    def test_12_fuzzy_tier(self):
        role, tier, _r = crc.classify_column('Departmnt')
        self.assertEqual((role, tier), ('profile', 'likely'))

    def test_13_markers_are_the_single_definition(self):
        self.assertEqual(
            crc.EMPLOYEE_CODE_MARKERS,
            ('MSNV', 'EMP CODE', 'EMPLOYEE CODE', 'EMPLOYEE ID', 'EMPLOYEEID'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
