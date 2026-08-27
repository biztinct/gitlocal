# -*- coding: utf-8 -*-
"""NETROLE P2 — an hours count is not an allowance.

Phase 1 read ABM's scheme correctly and still put `STANWORKHOUR` on the
Allowance shelf: the column sits in the numerator of
`=ROUND(BASESALARY/STANWORKHOUR*ACTUWORKHOUR,0)`, which is added into gross,
which is added into net pay. The sign walk has nothing to be sorry about — the
column really is on a positive path. It is simply not money.

Every one of ABM's ten hour columns is a `detail` (each is folded into the
amount it drives), so no total moves either way; the shelf is the whole of the
problem. The correction therefore lives in the SUGGESTION, never in the walk,
and these tests hold that line: `net_role` stays `earning`, the suggested
category becomes `OTH`.

The miniature below is ABM's real shape:

    BASESALARY    input     the money being spread
    STANWORKHOUR  input     the divisor — hours, by its label
    ACTUWORKHOUR  input     hours, by its label
    OTNIGHTWK     input     hours by ARITHMETIC ONLY — "OT Night shift week
                            day" carries no unit word anywhere
    OTNIGHTAMT    formula   =BASESALARY/STANWORKHOUR*OTNIGHTWK*210%
    ACTUBASIC     formula   =ROUND(BASESALARY/STANWORKHOUR*ACTUWORKHOUR,0)
    OTHOURSAMT    input     "Overtime Hours Amount" — says hours, IS money
    GROSSPAY      formula   =ACTUBASIC+OTNIGHTAMT+OTHOURSAMT
    PITAMOUNT     input
    NETPAY        formula   =GROSSPAY-PITAMOUNT
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models.formula_net_role import (
    band_kind, looks_like_a_quantity,
)


@tagged('post_install', '-at_install')
class TestNetRoleQuantity(TransactionCase):

    def setUp(self):
        super().setUp()
        Category = self.env['hr.salary.rule.category']
        for code in ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP', 'OTH'):
            if not Category.search([('code', '=', code)], limit=1):
                Category.create({'name': code.title(), 'code': code})
        self.other = Category.search([('code', '=', 'OTH')], limit=1)
        self.config = self.env['hr.formula.config'].create({
            'name': 'Quantity miniature', 'code': 'NETROLEQTY',
            'country_code': 'VN',
        })
        spec = [
            ('A', 'BASESALARY', 'Base Salary', 'input', '', ''),
            ('B', 'STANWORKHOUR', 'Standard Working Hour', 'input', '', ''),
            ('C', 'ACTUWORKHOUR', 'Actual Working Hours including Paid leave',
             'input', '', ''),
            ('D', 'OTNIGHTWK', 'OT Night shift  week day', 'input', '',
             'Allowances'),
            ('E', 'OTNIGHTAMT', 'OT Night shift wk day amount', 'formula',
             '=IF(C5=0,0,($A5/$B5*D5*210%))', ''),
            ('F', 'ACTUBASIC', 'Actual Basic salary', 'formula',
             '=ROUND(A5/B5*C5,0)', ''),
            ('G', 'OTHOURSAMT', 'Overtime Hours Amount', 'input', '', ''),
            ('H', 'GROSSPAY', 'Actual Total Income', 'formula', '=F5+E5+G5', ''),
            ('I', 'PITAMOUNT', 'Monthly PIT', 'input', '', 'Deductions'),
            ('J', 'NETPAY', 'Net Pay', 'formula', '=H5-I5', ''),
        ]
        self.rules = {}
        sequence = 10
        for letter, code, name, ctype, formula, band in spec:
            vals = {
                'config_id': self.config.id, 'name': name, 'code': code,
                'column_type': ctype, 'sequence': sequence,
                'column_letter': letter, 'category_id': self.other.id,
            }
            if formula:
                vals['excel_formula'] = formula
            if band:
                vals['component_type'] = band
            self.rules[code] = self.env['hr.formula.rule'].create(vals)
            sequence += 10
        self.config.invalidate_recordset()

    def _suggested(self, code):
        for row in self.config.suggest_categories():
            if row['code'] == code:
                return row
        self.fail("no suggestion for %s" % code)

    # ------------------------------------------------------------------ Q1
    def test_q1_the_label_says_whether_it_is_a_count(self):
        """The pure lexicon, including the two traps: a money word anywhere
        vetoes the unit word, and "Holiday" is not a "day"."""
        for label in ('Standard Working Hour', 'OT 1.5 Hours', 'Night shift hour',
                      'Number of Dependents', 'Actual Working Hours',
                      'Ngày công', 'Số giờ làm thêm', 'Total Working Hours'):
            self.assertTrue(looks_like_a_quantity(label), label)
        for label in ('Overtime Hours Amount', 'Hourly Rate Pay', 'Holiday Bonus',
                      'Meal Allowance', 'Base Salary', 'Phụ cấp xăng xe',
                      'OT 1.5 Amount', 'Thirteenth Month Salary'):
            self.assertFalse(looks_like_a_quantity(label), label)
        # The code is consulted only for markers strong enough to survive
        # squashing — a label with nothing to say still lets one through.
        self.assertTrue(looks_like_a_quantity('Chuyen can', 'STANWORKHOUR'))

    # ------------------------------------------------------------------ Q2
    def test_q2_the_arithmetic_says_so_when_the_label_does_not(self):
        """`$A5/$B5*D5*210%` reads "the hourly rate, times D5". Once B5 is
        known to be hours, D5 counts the same units — which is how the night
        shift columns, named without a unit word anywhere, are recognised.

        Position is load-bearing: A5 is the money being SPREAD across the
        hours, and calling it a count would be a catastrophe.
        """
        rules = self.config._net_role_rules()
        quantities = self.config._net_role_quantity_ids(rules)
        for code in ('STANWORKHOUR', 'ACTUWORKHOUR', 'OTNIGHTWK'):
            self.assertIn(self.rules[code].id, quantities, code)
        for code in ('BASESALARY', 'OTHOURSAMT', 'GROSSPAY', 'NETPAY',
                     'PITAMOUNT'):
            self.assertNotIn(self.rules[code].id, quantities, code)

    # ------------------------------------------------------------------ Q3
    def test_q3_the_walk_is_untouched_only_the_shelf_moves(self):
        """Phase 1 owns the math. An hours count still reaches net pay
        positively, is still a detail, and is still reported that way."""
        self.config.classify_net_roles()
        for code in ('STANWORKHOUR', 'ACTUWORKHOUR', 'OTNIGHTWK'):
            rule = self.rules[code]
            self.assertEqual(rule.net_role, 'earning', code)
            self.assertTrue(rule.net_role_detail, code)

    # ------------------------------------------------------------------ Q4
    def test_q4_a_count_is_suggested_as_information(self):
        self.config.classify_net_roles()
        for code in ('STANWORKHOUR', 'ACTUWORKHOUR', 'OTNIGHTWK'):
            row = self._suggested(code)
            self.assertEqual(row['suggested_category_code'], 'OTH', code)
            self.assertTrue(row['quantity'], code)
            self.assertIn('hours', row['reason'].lower(), code)
            self.assertNotIn('Odoo', row['reason'])

    # ------------------------------------------------------------------ Q5
    def test_q5_money_that_merely_mentions_hours_stays_pay(self):
        self.config.classify_net_roles()
        row = self._suggested('OTHOURSAMT')
        self.assertEqual(row['suggested_category_code'], 'ALW')
        self.assertFalse(row['quantity'])
        base = self._suggested('BASESALARY')
        self.assertEqual(base['suggested_category_code'], 'BASIC')
        self.assertFalse(base['quantity'])

    # ------------------------------------------------------------------ Q6
    def test_q6_applying_files_the_counts_as_information(self):
        self.config.classify_net_roles()
        self.config.apply_suggested_categories()
        for code in ('STANWORKHOUR', 'ACTUWORKHOUR', 'OTNIGHTWK'):
            self.assertEqual(self.rules[code].category_id.code, 'OTH', code)
        self.assertEqual(self.rules['OTHOURSAMT'].category_id.code, 'ALW')
        self.assertEqual(self.rules['BASESALARY'].category_id.code, 'BASIC')
        self.assertEqual(self.rules['NETPAY'].category_id.code, 'NET')

    # ------------------------------------------------------------------ Q7
    def test_q7_the_users_own_band_is_the_other_opinion(self):
        """OTNIGHTWK sits under an "Allowances" band and is a count of hours;
        PITAMOUNT sits under "Deductions" and the formula agrees with it."""
        self.assertEqual(band_kind('Allowances'), 'earning')
        self.assertEqual(band_kind('Các khoản khấu trừ'), 'deduction')
        self.assertEqual(band_kind('Employer contributions'), 'employer_cost')
        self.assertIsNone(band_kind('Column 14'))

        self.config.classify_net_roles()
        flagged = self._suggested('OTNIGHTWK')
        self.assertTrue(flagged['band_conflict'])
        self.assertIn('Allowances', flagged['band_conflict_text'])
        self.assertNotIn('Odoo', flagged['band_conflict_text'])

        agreed = self._suggested('PITAMOUNT')
        self.assertEqual(agreed['band_kind'], 'deduction')
        self.assertFalse(agreed['band_conflict'])

    # ------------------------------------------------------------------ Q8
    def test_q8_a_suggestion_is_still_not_a_decision(self):
        """P2 added fields to the payload and no writes to the method."""
        self.config.classify_net_roles()
        before = {r.id: r.category_id.id for r in self.config.rule_ids}
        categories = self.env['hr.salary.rule.category'].search_count([])
        rows = self.config.suggest_categories()
        self.assertTrue(rows)
        self.assertEqual(
            before, {r.id: r.category_id.id for r in self.config.rule_ids})
        self.assertEqual(
            categories, self.env['hr.salary.rule.category'].search_count([]))
