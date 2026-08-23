# -*- coding: utf-8 -*-
"""The code generator, tested without a database.

``component_code`` is plain Python on purpose, so this table runs under a bare
``python3 pb_hr_payroll_formula/tests/test_component_code.py`` from the repository
root as well as under Odoo's test runner. The corpus is REAL: every label below was
read out of a live salary structure (ABM's VN payroll and the VPTQ configurations),
which is the only way to find out whether "readable" survives contact with a
spreadsheet somebody actually maintains.
"""

import os
import re
import sys
import unittest

if __package__ in (None, ''):                       # bare `python3 …` invocation
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models'))
    import importlib.util

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    _here = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')
    _load('column_role_classifier', os.path.join(_here, 'column_role_classifier.py'))
    _src = open(os.path.join(_here, 'component_code.py')).read().replace(
        'from .column_role_classifier import', 'from column_role_classifier import')
    component_code = type(sys)('component_code')
    exec(compile(_src, 'component_code.py', 'exec'), component_code.__dict__)
else:
    from ..models import component_code


build = component_code.build_component_code
CODE_RE = re.compile(r'^[A-Z][A-Z0-9]*$')

#: The four labels the owner approved as the acceptance target for MF-A1.
OWNER_LABELS = [
    'Chi trả phép năm chưa sử dụng',
    'Tỷ lệ % tạm ứng thưởng HQCV',
    'Constant SI-HI-IU Total 10.5%',
    'Employee Status',
]

#: Vietnamese labels chosen because every one of them loses letters under the old
#: ASCII-only filter. The second element is what those letters must fold to.
ACCENT_CASES = [
    ('Mức lương HĐLĐ', 'MUCLUONGHDLD'),
    ('Họ và tên', 'HOVATEN'),
    ('Đơn vị', 'DONVI'),
    ('Phép năm', 'PHEPNAM'),
    ('Nghỉ chế độ', 'NGHICHEDO'),
    ('Thưởng năm', 'THUONGNAM'),
    ('Hỗ trợ cơm', 'HOTROCOM'),
    ('Giảm trừ NPT', 'GIAMTRUNPT'),
    ('Truy thu BHXH', 'TRUYTHUBHXH'),
    ('Hoàn trả BHXH', 'HOANTRABHXH'),
    ('Thuế TNCN', 'THUETNCN'),
    ('Ngạch lương', 'NGACHLUONG'),
    ('PC chức danh', 'PCCHUCDANH'),
    ('PC kiêm nhiệm', 'PCKIEMNHIEM'),
    ('Tăng ca Lễ tết', 'TANGCALETET'),
    ('Công tác', 'CONGTAC'),
]

#: 60+ real headers: the ABM English structure plus the VPTQ Vietnamese one.
CORPUS = [
    'Employee Code', 'Employee Name', 'Date of Joining', 'Employee Status',
    'Last Working Day', 'Location', 'Full Name ( VN)', 'Work Email', 'Designation',
    'Employment Type', 'Residency Status', 'ID Card Number', 'PIT Number',
    'Insurance Book Number', 'Enroll for Tax', 'Enroll for Insurance',
    'Employee Bank Account Name', 'Employee Bank  Account No.', 'Bank Name',
    'Base Salary', 'Gas Allowance', 'Phone Allowance', 'Meal Allowance',
    'Responsibility Alowance', 'Parking Allowance', 'Taxi allowance',
    'Standard Working Hour', 'Actual Working Hours including Paid leave',
    'Actual Working Hours excluding paid leave', 'Actual Basic salary',
    'Actual Gas Allowance', 'Actual Phone Amount', 'Actual Meal',
    'Actual Responsibility', 'Actual Parking', 'Actual Taxi allowance',
    'Recognition Bonus', 'Other Income', 'Paid Leave Unused', 'Other Bonus',
    'Bonus - STIP', 'Marsh Insurance refund (Non-tax)', 'Adjustment',
    'SHUI Participation', 'TU Participation', 'Sales Incentive',
    'Thirteenth Month Salary', 'Severance Allowance', 'Reimbursement Payment',
    'OT 1.5 Hours', 'OT 2 Hours', 'OT 3 Hours', 'Night shift hour',
    'OT Night shift  week day', 'OT Night shift weekend day',
    'OT Ngiht shift Holiday', 'OT 1.5 Amount', 'OT 2 Amount', 'OT 3 Amount',
    'Total Overtime Amount', 'OT Non-Taxable', 'OT Taxable', 'Actual Total Income',
    'Salary for SI', 'Salary for UI', 'Social Ins. - 8%', 'Medical Ins. - 1.5%',
    'Unemployment Ins. - 1 %', 'SI-HI-IU Total 10.5%', 'Employee Trade Union',
    'Number of Dependents', 'Dependent Amount', 'Taxable Income',
    'Taxable Income after deduction', 'Monthly PIT', 'Other Deduction',
    'Total Deduction', 'Net Pay', 'Social Ins. - 17.5%', 'Medical Ins. - 3%',
    'SI-HI-UI Total 21.5%', 'Trade Union ER 2%', 'Total Cost to Employer',
    'Cost center for Payroll', 'Constant Social Ins. - 8%',
    'Constant SI-HI-IU Total 10.5%', 'Constant SI-HI-UI Total 21.5%',
    'Mức lương HĐLĐ', 'Tỷ lệ % tạm ứng thưởng HQCV', 'Lương trực hỗ trợ bảo vệ',
    'Phép năm nghỉ việc', 'Truy lãnh lương', 'Truy thu lương', 'Hỗ trợ cơm',
    'Hỗ trợ Nhà ở', 'Thưởng năm', 'Chi trả phép năm chưa sử dụng',
    'Thu nhập chịu thuế khác', 'Truy thu BHXH', 'Hoàn trả BHXH',
    'Thu tiền tạm ứng', 'Thu tiền điện thoại vượt mức', 'Tiền phúng điếu',
    'Tiền cơm', 'Ngạch lương', 'PC chức danh', 'PC kiêm nhiệm', 'PC Biệt phái',
    'PC thâm niên', 'Giảm trừ NPT', 'Đối tượng được tính làm thêm giờ',
    'Công đi làm ngày thường', 'Làm việc ngày T7 được nghỉ', '14 ngày đầu',
    'Từ ngày 15 trở đi', 'Lương ngày nghỉ phép', 'Lương tăng ca ngày Lễ/Tết',
]


def _generate(labels, reserved=()):
    """Generate a batch the way every caller does: seeding each code with the ones
    already handed out, so uniqueness is a property of the batch, not of luck."""
    existing, out = set(), []
    for label in labels:
        code = build(label, existing_codes=existing, reserved=reserved)
        existing.add(code)
        out.append(code)
    return out


class TestComponentCode(unittest.TestCase):

    # 1 ------------------------------------------------------------------
    def test_01_owner_approved_labels_are_readable(self):
        codes = _generate(OWNER_LABELS)
        for label, code in zip(OWNER_LABELS, codes):
            self.assertTrue(CODE_RE.match(code), '%s -> %r' % (label, code))
            self.assertLessEqual(len(code), component_code.MAX_LEN, '%s -> %s' % (label, code))
        # The two the algorithm reproduces exactly; the other two are recorded in
        # the phase report because the owner accepted "the spirit holds".
        self.assertEqual(codes[2], 'SIHIIUTOT105')
        self.assertEqual(codes[3], 'EMPSTATUS')
        self.assertEqual(codes[0], 'CHITRAPHEP')
        self.assertEqual(codes[1], 'TYLETAMHQCV')

    # 2 ------------------------------------------------------------------
    def test_02_accents_fold_they_do_not_vanish(self):
        for label, expected in ACCENT_CASES:
            self.assertEqual(build(label), expected, label)
        # The specific failure this replaces: an ASCII-only filter DELETES the
        # accented letters instead of folding them.
        lossy = re.sub(r'[^A-Za-z0-9]', '', 'Chi trả phép năm chưa sử dụng').upper()
        self.assertEqual(lossy, 'CHITRPHPNMCHASDNG')
        self.assertNotEqual(build('Chi trả phép năm chưa sử dụng'), lossy)
        for label, _expected in ACCENT_CASES:
            self.assertNotIn('đ', build(label).lower())

    # 3 ------------------------------------------------------------------
    def test_03_invariants_over_the_real_corpus(self):
        self.assertGreaterEqual(len(CORPUS), 60)
        letters = {'A', 'B', 'C', 'AA', 'AB', 'ZA', 'ZB'}
        codes = _generate(CORPUS, reserved=letters)
        self.assertEqual(len(codes), len(set(codes)), 'codes must be unique in a batch')
        for label, code in zip(CORPUS, codes):
            self.assertTrue(CODE_RE.match(code), '%s -> %r' % (label, code))
            self.assertNotIn('_', code)
            self.assertLessEqual(len(code), 12, '%s -> %s' % (label, code))
            self.assertNotIn(code, letters, '%s -> %s collides with a column letter' % (label, code))
            # >= 6 characters keeps a code inside the importer's fuzzy header
            # fallback. A label with fewer letters than that cannot be padded to it
            # out of thin air, so the floor is "as long as the label allows".
            available = len(re.sub(r'[^A-Za-z0-9]', '',
                                   component_code.strip_accents(label)))
            self.assertGreaterEqual(len(code), min(6, available), '%s -> %s' % (label, code))

    # 4 ------------------------------------------------------------------
    def test_04_deterministic(self):
        self.assertEqual(_generate(CORPUS), _generate(CORPUS))

    # 5 ------------------------------------------------------------------
    def test_05_idempotent_on_its_own_output(self):
        codes = _generate(CORPUS)
        for code in codes:
            self.assertEqual(build(code), code,
                             'feeding a generated code back in must change nothing')

    # 6 ------------------------------------------------------------------
    def test_06_transposed_acronyms_stay_distinct(self):
        pair = _generate(['Constant SI-HI-IU Total 10.5%', 'Constant SI-HI-UI Total 21.5%'])
        self.assertNotEqual(pair[0], pair[1])
        # And the same label with and without its leading noise word.
        four = _generate(['SI-HI-IU Total 10.5%', 'Constant SI-HI-IU Total 10.5%',
                          'SI-HI-UI Total 21.5%', 'Constant SI-HI-UI Total 21.5%'])
        self.assertEqual(len(set(four)), 4, four)

    # 7 ------------------------------------------------------------------
    def test_07_dedupe_uses_letters_not_digits_or_underscores(self):
        codes = _generate(['Meal Allowance'] * 4)
        self.assertEqual(len(set(codes)), 4)
        for code in codes:
            self.assertNotIn('_', code)
            self.assertLessEqual(len(code), 12)
        self.assertEqual(codes[0], 'MEALALLOW')
        self.assertEqual(codes[1], 'MEALALLOWA')
        # The old single-sheet generator produced digit suffixes that ATE a letter
        # of the base to stay under its cap. Nothing here does that.
        self.assertFalse(any(c[-1].isdigit() for c in codes[1:]))

    # 8 ------------------------------------------------------------------
    def test_08_reserved_column_letters_are_never_taken(self):
        self.assertNotEqual(build('Net Pay', reserved={'NETPAY'}), 'NETPAY')
        self.assertEqual(build('OT', reserved={'OT'}) != 'OT', True)

    # 9 ------------------------------------------------------------------
    def test_09_normalize_keeps_a_code_that_is_already_fine(self):
        self.assertEqual(component_code.normalize_code('BASIC'), 'BASIC')
        self.assertEqual(component_code.normalize_code('NETPAY'), 'NETPAY')
        # …and repairs the ones that are not.
        self.assertEqual(component_code.normalize_code('SI_EMP'), 'SIEMP')
        self.assertEqual(component_code.normalize_code('TOTAL_DED'), 'TOTALDED')
        self.assertEqual(component_code.normalize_code('basic salary'), 'BASICSALARY')
        long_code = 'ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE'
        repaired = component_code.normalize_code(long_code)
        self.assertLessEqual(len(repaired), 12)
        self.assertTrue(CODE_RE.match(repaired))

    # 10 -----------------------------------------------------------------
    def test_10_shape_validator(self):
        for good in ('BASIC', 'SIEMP', 'OT15AMOUNT', 'C14NGAYDAU'):
            self.assertTrue(component_code.is_valid_code(good), good)
        for bad in ('SI_EMP', 'si emp', '1BASIC', '', 'BASIC-1', 'BASIC '):
            self.assertFalse(component_code.is_valid_code(bad), bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)
