# -*- coding: utf-8 -*-
"""Which component the screen proposes as net pay, when nothing says.

A scheme imported from a workbook rarely names its take-home column in a way
the engine can trust, so the Component categories screen asks. It used to ask
badly: it listed every calculated column in COLUMN ORDER and arrived with the
first one selected, beside a button reading "Read the scheme again".

On a live Rize Vietnam configuration the first calculated column is K, "Lương
bảo hiểm (Insurance salary)" — the base the 8% is charged ON, the START of the
arithmetic rather than its end. It was accepted without being read. All 80
components were then classified from it: 77 landed as Information, the
Deductions tab showed 0 on a Vietnam payroll, and the take-home figure beside
the wizard equalled gross.

The fixture below is that workbook in miniature, keeping every feature that
matters: an insurance base early, two columns whose headers both mention "net",
one of which feeds the other, and a total employer cost that CONTAINS net pay.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNetPayCandidates(TransactionCase):

    def setUp(self):
        super().setUp()
        Category = self.env['hr.salary.rule.category']
        self.other = Category.search([('code', '=', 'OTH')], limit=1) \
            or Category.create({'name': 'Other', 'code': 'OTH'})
        self.config, self.rules = self._make_config(
            'Net-pay picker miniature', 'NETPICKMINI', [
                # letter, code, name, type, formula
                ('J', 'LUONGHOPVND', 'Lương hợp đồng (Gross contract salary VND)',
                 'input', ''),
                ('X', 'PHUCAPBAOHIE', 'Phụ cấp bảo hiểm (Insurance allowance)',
                 'input', ''),
                # The trap: the FIRST calculated column, and a base, not a total.
                ('K', 'LUONGBAOHIEM', 'Lương bảo hiểm (Insurance salary)',
                 'formula', '=J2+X2'),
                ('AL', 'BHXH8', 'BHXH 8% (BHXH SI 8%)', 'formula', '=K2*8%'),
                ('AJ', 'TONGTHUNHAP', 'Tổng thu nhập (Total monthly income)',
                 'formula', '=J2+X2'),
                ('AZ', 'THUETNCNPIT', 'Thuế TNCN (PIT)', 'formula', '=AJ2*10%'),
                ('BG', 'HOANTNCNPIT', 'Hoàn thuế TNCN (PIT refund)', 'input', ''),
                ('BA', 'THUNHAVNDVND', 'Thu nhập ròng VND (Net Income VND)',
                 'formula', '=AJ2-AL2-AZ2'),
                ('BH', 'SOTIENVNDVND', 'Số tiền thực nhận VND (Net Payment VND)',
                 'formula', '=BA2+BG2'),
                ('BC', 'TONGCHIPHI', 'Tổng chi phí lương (Total salary cost)',
                 'formula', '=AJ2+AL2'),
            ])

    def _make_config(self, name, code, spec):
        config = self.env['hr.formula.config'].create({
            'name': name, 'code': code, 'country_code': 'VN'})
        rules, sequence = {}, 10
        for letter, rcode, rname, ctype, formula in spec:
            vals = {'config_id': config.id, 'name': rname, 'code': rcode,
                    'column_type': ctype, 'sequence': sequence,
                    'column_letter': letter, 'category_id': self.other.id}
            if formula:
                vals['excel_formula'] = formula
            rules[rcode] = self.env['hr.formula.rule'].create(vals)
            sequence += 10
        config.invalidate_recordset()
        return config, rules

    def _candidates(self):
        return self.env['pb.formula.studio']._net_pay_candidates(self.config)

    def _suggested(self, candidates=None):
        return [c for c in (candidates or self._candidates()) if c['suggested']]

    # ------------------------------------------------------------------ 1
    def test_01_the_screen_asks_because_nothing_names_net_pay(self):
        """The precondition. If this stops holding the fixture is wrong, and
        every assertion below would be testing the happy path by accident."""
        data = self.env['pb.formula.studio'].category_review_data(self.config.id)
        self.assertTrue(data.get('error'), "the fixture must have no net pay")
        self.assertTrue(data.get('net_candidates'))

    # ------------------------------------------------------------------ 2
    def test_02_the_take_home_column_is_the_one_proposed(self):
        suggested = self._suggested()
        self.assertEqual([c['code'] for c in suggested], ['SOTIENVNDVND'])

    # ------------------------------------------------------------------ 3
    def test_03_the_insurance_base_is_never_the_one_proposed(self):
        """The whole bug in one assertion."""
        self.assertNotIn('LUONGBAOHIEM',
                         [c['code'] for c in self._suggested()])

    # ------------------------------------------------------------------ 4
    def test_04_the_proposal_comes_first_in_the_list(self):
        candidates = self._candidates()
        self.assertEqual(candidates[0]['code'], 'SOTIENVNDVND')
        self.assertTrue(candidates[0]['suggested'])

    # ------------------------------------------------------------------ 5
    def test_05_every_calculated_column_is_still_offered(self):
        """Ranking must not hide anything: the answer may be none of the ones
        we like, and the user has to be able to reach it."""
        offered = {c['code'] for c in self._candidates()}
        formulas = {(r.code or '').upper() for r in self.config.rule_ids
                    if r.column_type == 'formula'}
        self.assertEqual(offered, formulas)

    # ------------------------------------------------------------------ 6
    def test_06_only_one_component_is_proposed(self):
        """Two columns here mention "net" — Net Income and Net Payment. A screen
        that pre-ticks two of them has not answered the question."""
        self.assertEqual(len(self._suggested()), 1)

    # ------------------------------------------------------------------ 7
    def test_07_net_income_loses_to_net_payment_because_it_feeds_it(self):
        """Both headers say net. The tie-break is that Net Income is worked out
        FROM — it is not the end of the arithmetic."""
        by_code = {c['code']: c for c in self._candidates()}
        self.assertLess(
            [c['code'] for c in self._candidates()].index('SOTIENVNDVND'),
            [c['code'] for c in self._candidates()].index('THUNHAVNDVND'))
        self.assertFalse(by_code['THUNHAVNDVND']['suggested'])

    # ------------------------------------------------------------------ 8
    def test_08_the_proposal_says_why(self):
        """The screen prints this. An unexplained default is what got accepted
        without being read the first time."""
        self.assertTrue(self._suggested()[0]['reason'])

    # ------------------------------------------------------------------ 9
    def test_09_only_the_proposal_explains_itself(self):
        for candidate in self._candidates():
            if not candidate['suggested']:
                self.assertFalse(candidate['reason'], candidate)

    # ------------------------------------------------------------------ 10
    def test_10_a_workbook_with_no_hint_at_all_proposes_the_sink(self):
        """No header mentions net. The end of the arithmetic is still a better
        guess than the first column — but it must be a guess about the END."""
        config, _rules = self._make_config('No hints', 'NOHINTMINI', [
            ('A', 'PAYBASE', 'Base', 'input', ''),
            ('B', 'FIRSTCALC', 'Charged on', 'formula', '=A2*2'),
            ('C', 'MIDDLECALC', 'Middle step', 'formula', '=B2+A2'),
            ('D', 'LASTCALC', 'Final figure', 'formula', '=C2-B2'),
        ])
        candidates = self.env['pb.formula.studio']._net_pay_candidates(config)
        self.assertEqual(candidates[0]['code'], 'LASTCALC')
        self.assertTrue(candidates[0]['suggested'])
        self.assertNotIn('FIRSTCALC',
                         [c['code'] for c in candidates if c['suggested']])

    # ------------------------------------------------------------------ 11
    def test_11_a_scheme_with_no_calculations_offers_nothing(self):
        """Rather than offering an input column that could never be net pay."""
        config, _rules = self._make_config('Inputs only', 'INPUTSONLY', [
            ('A', 'ONLYINPUT', 'Typed in', 'input', ''),
        ])
        self.assertEqual(
            self.env['pb.formula.studio']._net_pay_candidates(config), [])

    # ------------------------------------------------------------------ 12
    def test_12_choosing_one_makes_the_screen_read_the_scheme(self):
        """End to end: the proposal, accepted, produces a scheme that reads."""
        pick = self._suggested()[0]
        data = self.env['pb.formula.studio'].category_review_set_net(
            self.config.id, pick['id'])
        self.assertFalse(data.get('error'), data.get('error'))
        self.assertEqual(data.get('net_code'), 'SOTIENVNDVND')

        self.config.invalidate_recordset()
        roles = {(r.code or '').upper(): r.net_role for r in self.config.rule_ids}
        self.assertEqual(roles['SOTIENVNDVND'], 'net')
        self.assertIn('deduction', roles.values(),
                      "a scheme with a PIT and an 8% cannot have no deductions")
