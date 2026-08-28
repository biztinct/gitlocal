# -*- coding: utf-8 -*-
"""A component's category comes from what NET pay does with it.

The scheme built in `setUp` is a deliberate miniature of ABM's real one — the
shape that broke the old code-substring categoriser:

    BASE, ALWONE, ALWTWO        inputs
    GROSSAGG = SUM(A5:C5)       a range, so range expansion is load-bearing
    SICAP                       a constant
    SIBASE   = MIN(A5,E5)       BASE is a BASIS here, not a contribution
    SIAMT    = ROUND(F5*0.105,0)
    PITAMT                      an input
    DEDAGG   = G5+H5
    REFUND                      an input added on the way to net
    SWINGSRC                    an input
    SWINGADJ = IF(B5>0,K5,0-K5) both-sign branches
    NETPAY   = D5-I5+J5+L5
    ERSI     = ROUND(F5*0.175,0)
    ERCOST   = M5+N5            references NET, so it CONTAINS pay
    INFOFIELD                   referenced by nobody

BASE is the case the whole design turns on: it is summed into gross AND it is
what the 10.5% is charged on, so a plain union of path signs calls it "both",
which is useless. Reaching net additively in two hops beats reaching it
negatively in four through a scaling, so BASE is an earning and SIBASE — which
only ever reaches net through the insurance — is a deduction.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNetRoleClassifier(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['hr.formula.config'].create({
            'name': 'Net role miniature', 'code': 'NETROLEMINI',
            'country_code': 'VN',
        })
        self.rules = {}
        spec = [
            ('A', 'BASE', 'Base Salary', 'input', ''),
            ('B', 'ALWONE', 'Allowance One', 'input', ''),
            ('C', 'ALWTWO', 'Allowance Two', 'input', ''),
            ('D', 'GROSSAGG', 'Total Income', 'formula', '=SUM(A5:C5)'),
            ('E', 'SICAP', 'Insurance Cap', 'constant', ''),
            ('F', 'SIBASE', 'Salary for Insurance', 'formula', '=MIN(A5,E5)'),
            ('G', 'SIAMT', 'Insurance 10.5%', 'formula', '=ROUND(F5*0.105,0)'),
            ('H', 'PITAMT', 'Monthly Tax', 'input', ''),
            ('I', 'DEDAGG', 'Total Deduction', 'formula', '=G5+H5'),
            ('J', 'REFUND', 'Insurance Refund', 'input', ''),
            ('K', 'SWINGSRC', 'Swing Source', 'input', ''),
            ('L', 'SWINGADJ', 'Swing Adjustment', 'formula',
             '=IF(B5>0,K5,0-K5)'),
            ('M', 'NETPAY', 'Net Pay', 'formula', '=D5-I5+J5+L5'),
            ('N', 'ERSI', 'Employer Insurance 17.5%', 'formula',
             '=ROUND(F5*0.175,0)'),
            ('O', 'ERCOST', 'Total Cost to Employer', 'formula', '=M5+N5'),
            ('P', 'INFOFIELD', 'Reference Note', 'input', ''),
        ]
        # `hr_payslip_line.category_id` and `.salary_rule_id` are both NOT NULL,
        # so an unclassified scheme still arrives with the importer's shadow
        # salary rule and its fallback category. Starting from OTH — never from
        # the answer — is also what makes test 10 mean anything.
        Category = self.env['hr.salary.rule.category']
        for code in ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP', 'OTH'):
            if not Category.search([('code', '=', code)], limit=1):
                Category.create({'name': code.title(), 'code': code})
        other = Category.search([('code', '=', 'OTH')], limit=1)
        sequence = 10
        for letter, code, name, ctype, formula in spec:
            vals = {
                'config_id': self.config.id, 'name': name, 'code': code,
                'column_type': ctype, 'sequence': sequence,
                'column_letter': letter, 'appears_on_payslip': True,
                'category_id': other.id,
            }
            if formula:
                vals['excel_formula'] = formula
            rule = self.env['hr.formula.rule'].create(vals)
            rule.salary_rule_id = self.env['hr.salary.rule'].create({
                'name': name, 'code': code, 'sequence': sequence,
                'category_id': other.id, 'condition_select': 'none',
                'amount_select': 'fix',
            }).id
            self.rules[code] = rule
            sequence += 10
        self.config.invalidate_recordset()

    # ---------------------------------------------------------------- helpers
    def _classify(self):
        summary = self.config.classify_net_roles()[self.config.id]
        self.assertIsNone(summary['error'], summary.get('error'))
        return summary

    def _role(self, code):
        return self.rules[code].net_role

    def _suggested(self, code):
        for row in self.config.suggest_categories():
            if row['code'] == code:
                return row
        self.fail("no suggestion for %s" % code)

    # ------------------------------------------------------------------ 1
    def test_01_base_salary_is_an_earning_not_the_thing_insurance_is_charged_on(self):
        """BASE reaches net additively through gross; the insurance path is a
        BASIS relationship, four hops away and through a scaling."""
        self._classify()
        self.assertEqual(self._role('BASE'), 'earning')
        self.assertEqual(self._suggested('BASE')['suggested_category_code'], 'BASIC')
        self.assertTrue(self.rules['BASE'].net_role_detail,
                        "BASE is folded into GROSSAGG, so a run counts the total")

    # ------------------------------------------------------------------ 2
    def test_02_the_two_roll_ups_are_what_a_run_counts(self):
        self._classify()
        self.assertEqual(self._role('GROSSAGG'), 'earning')
        self.assertEqual(self._suggested('GROSSAGG')['suggested_category_code'], 'GROSS')
        self.assertFalse(self.rules['GROSSAGG'].net_role_detail)
        self.assertEqual(self._role('DEDAGG'), 'deduction')
        self.assertEqual(self._suggested('DEDAGG')['suggested_category_code'], 'DED')
        self.assertFalse(self.rules['DEDAGG'].net_role_detail)

    # ------------------------------------------------------------------ 3
    def test_03_the_parts_of_a_deduction_are_details_of_it(self):
        self._classify()
        for code in ('SIAMT', 'PITAMT'):
            self.assertEqual(self._role(code), 'deduction', code)
            self.assertTrue(self.rules[code].net_role_detail, code)
        self.assertEqual(self._role('SIBASE'), 'deduction')
        self.assertTrue(self.rules['SIBASE'].net_role_detail)
        self.assertIn('Insurance 10.5%', self.rules['SIBASE'].net_role_reason)

    # ------------------------------------------------------------------ 4
    def test_04_something_added_on_the_way_to_net_is_an_allowance(self):
        self._classify()
        self.assertEqual(self._role('REFUND'), 'earning')
        self.assertFalse(self.rules['REFUND'].net_role_detail)
        self.assertEqual(self._suggested('REFUND')['suggested_category_code'], 'ALW')

    # ------------------------------------------------------------------ 5
    def test_05_what_the_employer_pays_on_top_is_not_pay(self):
        """ERCOST references NET *positively* — it CONTAINS pay, so it can never
        be an earning. It is classed employer_cost (not info) because it is the
        employer-cost roll-up itself, and it is marked a detail: every dong in
        it is already counted as net pay or as an employer contribution."""
        self._classify()
        self.assertEqual(self._role('ERSI'), 'employer_cost')
        self.assertEqual(self._suggested('ERSI')['suggested_category_code'], 'COMP')
        self.assertEqual(self._role('ERCOST'), 'employer_cost')
        self.assertNotEqual(self._role('ERCOST'), 'earning')
        self.assertTrue(self.rules['ERCOST'].net_role_detail)

    # ------------------------------------------------------------------ 6
    def test_06_a_component_nothing_refers_to_is_information(self):
        self._classify()
        self.assertEqual(self._role('INFOFIELD'), 'info')
        self.assertEqual(self._suggested('INFOFIELD')['suggested_category_code'], 'OTH')

    # ------------------------------------------------------------------ 7
    def test_07_both_sign_branches_need_a_person(self):
        """The IF's two branches carry the SAME component with opposite signs,
        at the same cost, so nothing in the scheme decides what it is."""
        self._classify()
        self.assertEqual(self._role('SWINGSRC'), 'mixed')
        self.assertEqual(self.rules['SWINGSRC'].net_role_confidence, 'review')
        self.assertEqual(self._suggested('SWINGSRC')['suggested_category_code'], 'OTH')

    # ------------------------------------------------------------------ 8
    def test_08_no_net_pay_component_means_no_guessing(self):
        config = self.env['hr.formula.config'].create({
            'name': 'Netless', 'code': 'NETROLENONET', 'country_code': 'VN'})
        alpha = self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Alpha', 'code': 'ALPHAONE',
            'column_type': 'input', 'sequence': 10, 'column_letter': 'A'})
        beta = self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Beta', 'code': 'BETATWO',
            'column_type': 'formula', 'sequence': 20, 'column_letter': 'B',
            'excel_formula': '=A5*2'})
        summary = config.classify_net_roles()[config.id]
        self.assertTrue(summary['error'])
        self.assertNotIn('Odoo', summary['error'])
        self.assertFalse(alpha.net_role)
        self.assertFalse(beta.net_role)
        self.assertEqual(config.suggest_categories(), [])

    # ------------------------------------------------------------------ 9
    def test_09_a_suggestion_is_not_a_decision(self):
        self._classify()
        before = {r.id: (r.category_id.id, r.net_role, r.net_role_detail)
                  for r in self.config.rule_ids}
        line_count = self.env['hr.salary.rule.category'].search_count([])
        suggestions = self.config.suggest_categories()
        self.assertEqual(len(suggestions), len(self.config.rule_ids))
        after = {r.id: (r.category_id.id, r.net_role, r.net_role_detail)
                 for r in self.config.rule_ids}
        self.assertEqual(before, after, "suggest_categories() wrote something")
        self.assertEqual(
            line_count, self.env['hr.salary.rule.category'].search_count([]))

    # ------------------------------------------------------------------ 10
    def test_10_applying_moves_the_rule_and_its_salary_rule_together(self):
        salary_rule = self.rules['DEDAGG'].salary_rule_id
        self.assertEqual(salary_rule.category_id.code, 'OTH')
        self._classify()
        self.config.apply_suggested_categories()
        self.assertEqual(self.rules['DEDAGG'].category_id.code, 'DED')
        self.assertEqual(salary_rule.category_id.code, 'DED')
        self.assertEqual(self.rules['GROSSAGG'].category_id.code, 'GROSS')
        self.assertEqual(self.rules['NETPAY'].category_id.code, 'NET')

    # ------------------------------------------------------------------ 11
    def test_11_a_range_is_an_edge_for_every_column_inside_it(self):
        edges = self.config._net_role_edges(self.config._net_role_rules())
        sources = {s for s, _sign, _d, _c in edges.get(self.rules['GROSSAGG'].id, [])}
        for code in ('BASE', 'ALWONE', 'ALWTWO'):
            self.assertIn(self.rules[code].id, sources,
                          "%s sits inside SUM(A5:C5)" % code)
        for code in ('REFUND', 'PITAMT', 'INFOFIELD'):
            self.assertNotIn(self.rules[code].id, sources,
                             "%s sits outside SUM(A5:C5)" % code)

    # ------------------------------------------------------------------ 12
    def test_12_the_line_producer_carries_the_flag_onto_the_payslip(self):
        """The other half of this case — that a run's totals then SKIP those
        lines — is `pb_payruns/tests/test_run_totals.py`, where the KPI band
        lives."""
        self._classify()
        self.config.apply_suggested_categories()
        employee = self.env['hr.employee'].create({'name': 'Net Role Person'})
        contract = self.env['hr.contract'].create({
            'name': 'Net role contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'Net role slip',
            'contract_id': contract.id, 'date_from': '2026-06-01',
            'date_to': '2026-06-30'})
        computed = {'BASE': 9000.0, 'ALWONE': 500.0, 'ALWTWO': 0.0,
                    'GROSSAGG': 9500.0, 'SICAP': 0.0, 'SIBASE': 9000.0,
                    'SIAMT': 945.0, 'PITAMT': 55.0, 'DEDAGG': 1000.0,
                    'REFUND': 0.0, 'SWINGSRC': 0.0, 'SWINGADJ': 0.0,
                    'NETPAY': 8500.0, 'ERSI': 1575.0, 'ERCOST': 10075.0,
                    'INFOFIELD': 0.0}
        slip._create_payslip_lines_from_formulas(self.config.rule_ids, computed)
        by_code = {line.code: line for line in slip.line_ids}
        for code in ('SIAMT', 'PITAMT', 'SIBASE', 'BASE', 'ERCOST'):
            self.assertTrue(by_code[code].component_detail,
                            "%s: the producer must copy the flag" % code)
        # VALUEKIND P5 — ERSI moved to the other list. Its only roll-up is
        # ERCOST, which is excluded outright for containing net pay, so ERSI is
        # what a run counts as employer cost; calling it a detail of an
        # excluded total is what made the figure read zero. See test 15.
        for code in ('DEDAGG', 'GROSSAGG', 'REFUND', 'ERSI'):
            self.assertFalse(by_code[code].component_detail, code)
        self.assertEqual(by_code['DEDAGG'].category_id.code, 'DED')
        self.assertEqual(by_code['GROSSAGG'].category_id.code, 'GROSS')

    # ------------------------------------------------------------------ 13
    def test_13_formulas_that_refer_to_each_other_in_a_circle_do_not_hang(self):
        config = self.env['hr.formula.config'].create({
            'name': 'Circular', 'code': 'NETROLECYCLE', 'country_code': 'VN'})
        made = {}
        for letter, code, ctype, formula in (
                ('A', 'CYCONE', 'formula', '=B5+1'),
                ('B', 'CYCTWO', 'formula', '=A5+1'),
                ('C', 'NETPAY', 'formula', '=A5')):
            made[code] = self.env['hr.formula.rule'].create({
                'config_id': config.id, 'name': code.title(), 'code': code,
                'column_type': ctype, 'column_letter': letter,
                'sequence': 10 * (len(made) + 1), 'excel_formula': formula})
        summary = config.classify_net_roles()[config.id]
        self.assertIsNone(summary['error'])
        for code in ('CYCONE', 'CYCTWO'):
            self.assertTrue(made[code].net_role, code)
            self.assertEqual(made[code].net_role_confidence, 'review', code)

    # ------------------------------------------------------------------ 14
    def test_14_a_scheme_nobody_classified_behaves_exactly_as_before(self):
        employee = self.env['hr.employee'].create({'name': 'Unclassified Person'})
        contract = self.env['hr.contract'].create({
            'name': 'Unclassified contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'Unclassified slip',
            'contract_id': contract.id, 'date_from': '2026-06-01',
            'date_to': '2026-06-30'})
        slip._create_payslip_lines_from_formulas(
            self.config.rule_ids, {code: 1.0 for code in self.rules})
        self.assertTrue(slip.line_ids)
        for line in slip.line_ids:
            self.assertFalse(line.component_detail,
                             "%s: nothing classified this scheme" % line.code)
        for rule in self.config.rule_ids:
            self.assertFalse(rule.net_role)

    # ------------------------------------------------------------------ 15
    def test_15_a_detail_of_an_excluded_total_is_counted_itself(self):
        """VALUEKIND P5 — ABM's Employer cost read ZERO for this reason.

        `ERCOST` is a grand total that contains net pay, so it is excluded
        outright. Marking `ERSI` a detail of it meant every level deferred to
        the level above and the top level was excluded, so nothing anywhere was
        counted. A detail is only a detail of a roll-up that is itself counted.
        """
        self._classify()
        self.assertTrue(self.rules['ERCOST'].net_role_detail,
                        "the grand total still contains money counted elsewhere")
        self.assertFalse(
            self.rules['ERSI'].net_role_detail,
            "ERSI's only roll-up is excluded, so ERSI is what a run counts")

    # ------------------------------------------------------------------ 16
    def test_16_a_detail_two_levels_down_is_still_a_detail(self):
        """The counted ancestor may be two hops up, and usually is.

        `SIBASE` is inside `SIAMT`, which is inside `DEDAGG`, which is counted.
        A rule that only looked one level up would call SIBASE countable
        because its immediate parent is not, and report the insurance twice.
        """
        self._classify()
        self.assertFalse(self.rules['DEDAGG'].net_role_detail)
        self.assertTrue(self.rules['SIAMT'].net_role_detail)
        self.assertTrue(self.rules['SIBASE'].net_role_detail,
                        "SIBASE's money is inside SIAMT, which is inside DEDAGG")

    # ------------------------------------------------------------------ 17
    def test_17_a_quantity_is_never_added_to_net_pay(self):
        """VALUEKIND P5 — the value type gates the pay role.

        The graph walk says WHETHER a component reaches net pay; it cannot say
        HOW. Hours reach it as a multiplier, and a multiplier is not a share of
        the money. On ABM nine `quantity` components carried 'earning' and were
        kept out of the money measures by the Subtotal flag alone.
        """
        hours = self.rules['SWINGSRC']
        hours.write({'value_kind': 'quantity', 'value_kind_source': 'user'})
        self._classify()
        self.assertEqual(hours.net_role, 'info',
                         "a value counted in hours cannot be added to net pay")
        self.assertIn('hours', hours.net_role_reason)
        # …and the money components around it are untouched.
        self.assertEqual(self._role('BASE'), 'earning')
        self.assertEqual(self._role('PITAMT'), 'deduction')

    # ------------------------------------------------------------------ 18
    def test_18_the_board_refuses_a_money_role_on_a_non_money_type(self):
        self._classify()
        hours = self.rules['SWINGSRC']
        hours.write({'value_kind': 'quantity', 'value_kind_source': 'user'})
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.config.set_component_setup({'SWINGSRC': {'pay_role': 'earning'}})
        # Changing the TYPE alone retires the role rather than leaving the row
        # saying two things that cannot both be true.
        money = self.rules['REFUND']
        self.config.set_component_setup({'REFUND': {'pay_role': 'earning'}})
        self.config.set_component_setup({'REFUND': {'kind': 'quantity'}})
        self.assertEqual(money.net_role, 'info')

    # ------------------------------------------------------------------ 19
    def test_19_fix_role_conflicts_clears_what_was_stored_before_the_gate(self):
        """Existing rows are flagged, not silently rewritten — this is the
        one action behind the banner that clears them."""
        self._classify()
        hours = self.rules['SWINGSRC']
        # Exactly the state ABM was found in: a money role already stored, and
        # a value type that forbids it.
        hours.write({'value_kind': 'quantity', 'value_kind_source': 'user',
                     'net_role': 'earning'})
        board = self.config.value_kind_board()
        self.assertEqual(board['role_conflict_count'], 1)
        row = next(r for r in board['rows'] if r['code'] == 'SWINGSRC')
        self.assertTrue(row['role_conflict'])
        self.assertEqual(self.config.fix_role_conflicts(), ['SWINGSRC'])
        self.assertEqual(hours.net_role, 'info')
        self.assertEqual(self.config.value_kind_board()['role_conflict_count'], 0)
