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
negatively in four through a scaling, so BASE is an earning.

SIBASE is the other half of that sentence, and it took the rize payslip of
August 2026 to finish it. SIBASE reaches net pay ONLY through the insurance,
which is to say only ever multiplied — so it is not money at all, and calling
it a deduction put a ₫50,600,000 ceiling in a person's deductions column. A
component with no additive route to net pay is a working figure (test 3b), and
so is a figure that adds and subtracts money on the way there (test 25).
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

    # ------------------------------------------------------------------ 3b
    def test_03b_what_a_deduction_is_charged_on_is_not_itself_a_deduction(self):
        """`SIBASE` used to be called a deduction. Nobody is charged it.

        It reaches net pay only as the thing the 10.5% is multiplied BY, and
        this class's own docstring has always called that "a BASIS, not a
        contribution" — but `derived` merely RANKED the routes, so when every
        route was scaled the cheapest scaled one still won and the component
        was still money. On rize that put `Lương bảo hiểm` (insurance salary)
        and two insurance CEILINGS in the deductions column of a payslip,
        ₫157,000,000 of ceiling against ₫8,000,000 of pay.

        A working figure is what it is. The 10.5% charged on it is the
        deduction, and that is counted exactly once, as before.
        """
        self._classify()
        self.assertEqual(self._role('SIBASE'), 'info',
                         "a base is what a deduction is worked out FROM")
        self.assertFalse(self.rules['SIBASE'].net_role_detail,
                         "a working figure is not a detail of anything")
        self.assertIn('Insurance 10.5%', self.rules['SIBASE'].net_role_reason,
                      "the reason still says what it is used to work out")
        # The ceiling it is capped against is not money either.
        self.assertEqual(self._role('SICAP'), 'info')
        # …and the deduction itself is untouched.
        self.assertEqual(self._role('SIAMT'), 'deduction')

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
        # SIBASE was in this list until it stopped being money at all (test 3b).
        # A working figure is a detail of nothing, so it is checked below with
        # the others that carry no flag.
        for code in ('SIAMT', 'PITAMT', 'BASE', 'ERCOST'):
            self.assertTrue(by_code[code].component_detail,
                            "%s: the producer must copy the flag" % code)
        # VALUEKIND P5 — ERSI moved to the other list. Its only roll-up is
        # ERCOST, which is excluded outright for containing net pay, so ERSI is
        # what a run counts as employer cost; calling it a detail of an
        # excluded total is what made the figure read zero. See test 15.
        for code in ('DEDAGG', 'GROSSAGG', 'REFUND', 'ERSI', 'SIBASE'):
            self.assertFalse(by_code[code].component_detail, code)
        # …and the working figure reaches the payslip as one, so a statement
        # neither prints "Salary for Insurance" as money nor counts it.
        self.assertEqual(by_code['SIBASE'].pay_role, 'info')
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

        `SIAMT` is inside `DEDAGG`, which is counted. A rule that only looked
        one level up would call a component countable because its immediate
        parent is not, and report the insurance twice.

        `SIBASE` used to be the third level of this chain. It is now a working
        figure (test 3b) and carries no money at all, so the chain it tests is
        SIAMT → DEDAGG.
        """
        self._classify()
        self.assertFalse(self.rules['DEDAGG'].net_role_detail)
        self.assertTrue(self.rules['SIAMT'].net_role_detail,
                        "SIAMT's money is inside DEDAGG, which is counted")

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

    # ------------------------------------------------------------------ 20
    def test_20_a_role_a_person_set_survives_a_reclassify(self):
        """`set_component_setup`'s docstring promised this and it was not true.

        `classify_net_roles` rewrote every role and every Subtotal flag on the
        scheme, so one press of Re-classify silently discarded every decision
        a person had made. Confidence cannot carry the distinction — the
        classifier marks its own confident answers `certain` too.
        """
        self._classify()
        refund = self.rules['REFUND']
        self.assertEqual(refund.net_role, 'earning')
        self.config.set_component_setup({'REFUND': {'pay_role': 'info'}})
        self.assertEqual(refund.net_role_source, 'user')
        self.config.reclassify_from_formulas()
        self.assertEqual(refund.net_role, 'info',
                         "a decision a person made is not a guess to re-derive")
        # …and everything else is still derived as before.
        self.assertEqual(self._role('BASE'), 'earning')
        self.assertEqual(self._role('PITAMT'), 'deduction')

    # ------------------------------------------------------------------ 21
    def test_21_the_subtotal_flag_rides_the_same_marker(self):
        self._classify()
        base = self.rules['BASE']
        self.assertTrue(base.net_role_detail)
        self.config.set_component_setup({'BASE': {'rollup': False}})
        self.assertEqual(base.net_role_source, 'user')
        self.config.reclassify_from_formulas()
        self.assertFalse(base.net_role_detail,
                         "the Subtotal flag is half of one decision, not a "
                         "separate one the classifier may overwrite")

    # ------------------------------------------------------------------ 22
    def test_22_clearing_the_role_hands_the_row_back(self):
        self._classify()
        refund = self.rules['REFUND']
        self.config.set_component_setup({'REFUND': {'pay_role': 'info'}})
        self.assertEqual(refund.net_role_source, 'user')
        self.config.set_component_setup({'REFUND': {'pay_role': ''}})
        self.assertFalse(refund.net_role_source)
        self.config.reclassify_from_formulas()
        self.assertEqual(refund.net_role, 'earning',
                         "'not set' means the classifier owns it again")

    # ------------------------------------------------------------------ 23
    def test_23_reclassify_reports_what_moved(self):
        """The board's button reports; a silent re-derive of 99 rows is not a
        thing anybody should press twice wondering if it worked."""
        self._classify()
        self.config.set_component_setup({'REFUND': {'pay_role': 'info'}})
        res = self.config.reclassify_from_formulas()
        self.assertEqual(res['kept'], 1)
        self.assertIn('changed', res)

    # ------------------------------------------------------------------ 24
    def test_24_a_draft_scheme_is_reported_as_draft_not_as_missing(self):
        """The difference between "there is no scheme" and "the scheme is in
        Draft" is an afternoon of assignment work versus one button.

        Every rung of `_find_formula_config` filters on `state = 'active'`, so
        a Draft scheme is invisible to all of them — and the message reported
        it ABSENT. On the reference tenant that produced a run of 36 payslips
        with no lines under a KPI band of zeros, over a scheme one lifecycle
        step from working.
        """
        from odoo.exceptions import UserError
        self.config.state = 'draft'
        employee = self.env['hr.employee'].create({'name': 'Stranded Person'})
        contract = self.env['hr.contract'].create({
            'name': 'Stranded contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'Stranded slip',
            'contract_id': contract.id, 'date_from': '2026-06-01',
            'date_to': '2026-06-30'})
        slip.struct_id = False
        self.assertIn(self.config, slip._inactive_formula_configs())
        with self.assertRaises(UserError) as caught:
            slip.compute_sheet()
        message = str(caught.exception)
        self.assertIn('Draft', message,
                      "the message must name the state that is blocking it")
        self.assertIn(self.config.name, message,
                      "…and the scheme, so there is nothing left to hunt for")
        self.assertNotIn('neither a salary structure', message)

    # ------------------------------------------------------------------ 25
    def test_25_a_running_total_is_not_an_earning(self):
        """rize, August 2026: one payslip read Net −₫149,519,958.

        The scheme carries TWO nets. `Thu nhập ròng VND` (Net Income VND) is
        gross less every deduction, and `Số tiền thực nhận VND` — the real net —
        is that plus a tax refund. Because the last step is a plain addition,
        Net Income flowed into net pay with sign +1 over one unscaled hop, the
        cheapest route there is, and the classifier called it an EARNING with
        the highest confidence it has.

        Everything feeding it was then "already counted inside Net Income VND",
        including the scheme's real gross. So the gross became a detail of a
        net, and a payslip added ₫34,390,042 of income against ₫183,910,000 of
        ceilings and bases.

        A figure that adds money and takes money off on the way to net pay is a
        step, not an amount. This miniature reproduces the shape exactly.
        """
        config = self.env['hr.formula.config'].create({
            'name': 'Two nets', 'code': 'TWONETS', 'country_code': 'VN'})
        other = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'OTH')], limit=1)
        spec = [
            ('A', 'PAYA', 'Salary', 'input', ''),
            ('B', 'PAYB', 'Allowance', 'input', ''),
            ('C', 'GROSSSUM', 'Total income', 'formula', '=A5+B5'),
            ('D', 'TAXAMT', 'Tax', 'input', ''),
            ('E', 'SUBNET', 'Net income', 'formula', '=C5-D5'),
            ('F', 'TAXBACK', 'Tax refund', 'input', ''),
            ('G', 'NETPAY', 'Net payment', 'formula', '=E5+F5'),
        ]
        rules, sequence = {}, 10
        for letter, code, name, ctype, formula in spec:
            vals = {'config_id': config.id, 'name': name, 'code': code,
                    'column_type': ctype, 'sequence': sequence,
                    'column_letter': letter, 'appears_on_payslip': True,
                    'category_id': other.id}
            if formula:
                vals['excel_formula'] = formula
            rules[code] = self.env['hr.formula.rule'].create(vals)
            sequence += 10
        config.invalidate_recordset()
        summary = config.classify_net_roles()[config.id]
        self.assertIsNone(summary['error'], summary.get('error'))

        self.assertEqual(rules['NETPAY'].net_role, 'net')
        self.assertEqual(rules['SUBNET'].net_role, 'info',
                         "a figure that both adds and takes off is a step")
        self.assertEqual(rules['GROSSSUM'].net_role, 'earning')
        self.assertFalse(rules['GROSSSUM'].net_role_detail,
                         "THE BUG: the real gross was a detail of the sub-net")
        self.assertEqual(rules['TAXAMT'].net_role, 'deduction')
        self.assertFalse(rules['TAXAMT'].net_role_detail)
        self.assertEqual(rules['TAXBACK'].net_role, 'earning')
        # Gross − deductions = net, which is the whole point.
        self.assertTrue(rules['PAYA'].net_role_detail)
        self.assertTrue(rules['PAYB'].net_role_detail)

    # ------------------------------------------------------------------ 26
    def test_26_a_plain_total_of_earnings_is_still_an_earning(self):
        """The guard on test 25: only a MIXED step is demoted.

        `GROSSAGG` and `DEDAGG` each add up components of one kind. Neither is
        a running total, and demoting either would empty a column.
        """
        self._classify()
        self.assertEqual(self._role('GROSSAGG'), 'earning')
        self.assertFalse(self.rules['GROSSAGG'].net_role_detail)
        self.assertEqual(self._role('DEDAGG'), 'deduction')
        self.assertFalse(self.rules['DEDAGG'].net_role_detail)

    # ------------------------------------------------------------------ 27
    def test_27_a_scheme_with_no_additive_route_is_left_alone(self):
        """The safety rail: never demote the last earning to nothing.

        `NETPAY = BASE * 0.9` reaches net pay only scaled, so the ingredient
        rule would take the one component this scheme has and report a gross of
        zero — a different wrong answer, not a right one. It stands down and
        asks for a person instead.
        """
        config = self.env['hr.formula.config'].create({
            'name': 'Scaled only', 'code': 'SCALEDONLY', 'country_code': 'VN'})
        other = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'OTH')], limit=1)
        base = self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Base', 'code': 'ONLYBASE',
            'column_type': 'input', 'sequence': 10, 'column_letter': 'A',
            'appears_on_payslip': True, 'category_id': other.id})
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Net Pay', 'code': 'NETPAY',
            'column_type': 'formula', 'sequence': 20, 'column_letter': 'B',
            'excel_formula': '=A5*0.9', 'appears_on_payslip': True,
            'category_id': other.id})
        config.invalidate_recordset()
        summary = config.classify_net_roles()[config.id]
        self.assertIsNone(summary['error'], summary.get('error'))
        self.assertEqual(base.net_role, 'earning',
                         "the scheme's only pay must not vanish")
        self.assertEqual(base.net_role_confidence, 'review',
                         "…but nobody should be told this was certain")

    # ------------------------------------------------------------------ 28
    def test_28_reclassify_declines_to_make_the_figures_worse(self):
        """The rail: the button measures its own answer before writing it.

        A scheme that expresses its deductions as NEGATIVE amounts added in
        reads, to a sign walk, as a scheme of nothing but earnings. On the
        reference demo world re-classifying would have turned ₫30.7bn of gross
        with ₫4.96bn of take-home into ₫24.8bn of gross, no deductions and no
        net at all — every figure on the pay run screen wrong, from one press.

        Here the same shape in miniature: the scheme HAS a sensible stored
        classification, and the walk would replace it with one where the run no
        longer reconciles. Nothing is written and the reason says so.
        """
        employee = self.env['hr.employee'].create({'name': 'Rail Person'})
        contract = self.env['hr.contract'].create({
            'name': 'Rail contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        run = self.env['hr.payslip.run'].create({'name': 'Rail run'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'Rail slip',
            'contract_id': contract.id, 'payslip_run_id': run.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30'})
        slip.formula_config_id = self.config.id
        self._classify()
        slip._create_payslip_lines_from_formulas(self.config.rule_ids, {
            'BASE': 9000.0, 'ALWONE': 500.0, 'ALWTWO': 0.0, 'GROSSAGG': 9500.0,
            'SICAP': 0.0, 'SIBASE': 9000.0, 'SIAMT': 945.0, 'PITAMT': 55.0,
            'DEDAGG': 1000.0, 'REFUND': 0.0, 'SWINGSRC': 0.0, 'SWINGADJ': 0.0,
            'NETPAY': 8500.0, 'ERSI': 1575.0, 'ERCOST': 10075.0,
            'INFOFIELD': 0.0})
        # 9500 − 1000 = 8500. The stored classification reconciles exactly.
        roles = {r.code: r.net_role for r in self.config.rule_ids}
        details = {r.code: r.net_role_detail for r in self.config.rule_ids}
        self.assertEqual(
            self.config._net_role_balance_gap(roles, details)[0], 0.0,
            "the fixture must start from figures that add up")

        # Now the answer the walk would give if it could not see the deduction:
        # every component an earning. The rail is asked directly, because that
        # is the unit under test, not the walk that feeds it.
        broken_roles = dict(roles, DEDAGG='earning', SIAMT='earning',
                            PITAMT='earning')
        gap, _gross = self.config._net_role_balance_gap(broken_roles, details)
        self.assertNotEqual(gap, 0.0,
                            "mis-filing the deduction must show up as a gap")

        # …and an IMPROVEMENT is never blocked, which is the case rize was in.
        self.assertIsNone(
            self.config._net_role_would_worsen(
                self.config._build_net_role_classification()['_classification']),
            "re-deriving the same good answer must not be refused")

    # ------------------------------------------------------------------ 29
    def test_29_a_scheme_with_no_run_yet_is_never_blocked(self):
        """No payslips means no evidence, and no evidence is not bad evidence.

        A brand-new tenant's first import is exactly what this whole feature is
        for; refusing it for want of a pay run would be backwards.
        """
        self.assertIsNone(
            self.config._net_role_would_worsen(
                self.config._build_net_role_classification()['_classification']))
        summary = self._classify()
        self.assertNotIn('blocked', summary)

    # ------------------------------------------------------------------ 30
    def test_30_money_with_no_net_pay_is_the_whole_run_unaccounted_for(self):
        """The hole an earlier draft of the rail left open.

        The demo world's formulas read as ₫24.8bn of gross, no deductions and
        no net at all. With "no net figure" treated as "nothing to measure",
        the rail called that unmeasurable and waved it through — the exact
        classification it exists to stop. A classification that finds money but
        no take-home has not failed to say anything; it has said something
        badly wrong.
        """
        employee = self.env['hr.employee'].create({'name': 'No Net Person'})
        contract = self.env['hr.contract'].create({
            'name': 'No net contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        run = self.env['hr.payslip.run'].create({'name': 'No net run'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'No net slip',
            'contract_id': contract.id, 'payslip_run_id': run.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30'})
        slip.formula_config_id = self.config.id
        self._classify()
        slip._create_payslip_lines_from_formulas(self.config.rule_ids, {
            'BASE': 9000.0, 'ALWONE': 500.0, 'ALWTWO': 0.0, 'GROSSAGG': 9500.0,
            'SICAP': 0.0, 'SIBASE': 9000.0, 'SIAMT': 945.0, 'PITAMT': 55.0,
            'DEDAGG': 1000.0, 'REFUND': 0.0, 'SWINGSRC': 0.0, 'SWINGADJ': 0.0,
            'NETPAY': 8500.0, 'ERSI': 1575.0, 'ERCOST': 10075.0,
            'INFOFIELD': 0.0})
        details = {r.code: r.net_role_detail for r in self.config.rule_ids}

        # Everything an earning, nothing a net — the demo world's shape.
        all_earnings = {r.code: 'earning' for r in self.config.rule_ids}
        measured = self.config._net_role_balance_gap(all_earnings, details)
        self.assertIsNotNone(
            measured, "money with no take-home is a finding, not a blank")
        self.assertNotEqual(measured[0], 0.0)

        # A classification that says nothing at all IS a blank, and stays one.
        nothing = {r.code: False for r in self.config.rule_ids}
        self.assertIsNone(self.config._net_role_balance_gap(nothing, details))

    # ------------------------------------------------------------------ 31
    def test_31_a_scheme_may_say_plus_and_mean_minus(self):
        """The reference demo world writes deductions as negatives, added in.

            SIEMP   = -round(min(BASIC, CAPLO) * EESI)
            FULLPAY = GROSS + SIEMP + HIEMP + UIEMP + PIT + LOANREP

        Read as arithmetic that is six earnings, and ₫25.7bn of insurance, tax
        and loan repayments classified as pay across 47 pay runs. A sign walk
        cannot know better — it reads the shape of the formula, never the size
        of the answer.

        The amounts are the evidence, and they are decisive: nothing added to
        somebody's pay is consistently negative. It is the same rule the
        employee's own pay statement has always used.
        """
        config = self.env['hr.formula.config'].create({
            'name': 'Negatives added in', 'code': 'NEGADD', 'country_code': 'VN'})
        other = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'OTH')], limit=1)
        spec = [
            ('A', 'PAY', 'Salary', 'input', ''),
            ('B', 'TAXOFF', 'Tax', 'input', ''),
            ('C', 'SWINGY', 'Adjustment', 'input', ''),
            ('D', 'TAKEHOME', 'Net pay', 'formula', '=A5+B5+C5'),
        ]
        rules, sequence = {}, 10
        for letter, code, name, ctype, formula in spec:
            vals = {'config_id': config.id, 'name': name, 'code': code,
                    'column_type': ctype, 'sequence': sequence,
                    'column_letter': letter, 'appears_on_payslip': True,
                    'category_id': other.id}
            if formula:
                vals['excel_formula'] = formula
            rule = self.env['hr.formula.rule'].create(vals)
            rule.salary_rule_id = self.env['hr.salary.rule'].create({
                'name': name, 'code': code, 'sequence': sequence,
                'category_id': other.id, 'condition_select': 'none',
                'amount_select': 'fix'}).id
            rules[code] = rule
            sequence += 10
        config.invalidate_recordset()

        # With no payslips, the formulas are all there is: everything is added
        # in, so everything reads as an earning.
        config.classify_net_roles()
        self.assertEqual(rules['TAXOFF'].net_role, 'earning',
                         "with no amounts to read, the formula is the only word")

        # Now give it a run. Tax is negative for everyone; the adjustment
        # swings both ways and must be left alone.
        run = self.env['hr.payslip.run'].create({'name': 'Negatives run'})
        for index, (pay, tax, swing) in enumerate(
                [(9000.0, -900.0, 50.0), (8000.0, -800.0, -30.0)]):
            employee = self.env['hr.employee'].create(
                {'name': 'Negatives Person %s' % index})
            contract = self.env['hr.contract'].create({
                'name': 'Negatives contract %s' % index,
                'employee_id': employee.id, 'wage': 10000.0,
                'state': 'open', 'date_start': '2020-01-01'})
            slip = self.env['hr.payslip'].create({
                'employee_id': employee.id, 'name': 'Negatives slip %s' % index,
                'contract_id': contract.id, 'payslip_run_id': run.id,
                'date_from': '2026-06-01', 'date_to': '2026-06-30'})
            slip.formula_config_id = config.id
            slip._create_payslip_lines_from_formulas(config.rule_ids, {
                'PAY': pay, 'TAXOFF': tax, 'SWINGY': swing,
                'TAKEHOME': pay + tax + swing})

        for rule in config.rule_ids:
            rule.net_role_source = 'auto'
        config.classify_net_roles()
        self.assertEqual(rules['TAKEHOME'].net_role, 'net')
        self.assertEqual(rules['TAXOFF'].net_role, 'deduction',
                         "added in, but never positive — it is a deduction")
        self.assertIn('amounts decide', rules['TAXOFF'].net_role_reason)
        self.assertEqual(rules['PAY'].net_role, 'earning')
        self.assertEqual(rules['SWINGY'].net_role, 'earning',
                         "a component that swings both ways is left as written")

    # ------------------------------------------------------------------ 32
    def test_32_a_positive_amount_is_never_evidence_of_an_earning(self):
        """The guard on test 31, and it caught a real one.

        The ORDINARY way to write a deduction is a positive number that the net
        formula SUBTRACTS — this fixture's `SIAMT` is 945 and `NETPAY` takes it
        off. A rule that read a positive amount as "therefore an earning" would
        turn every properly-written deduction in every scheme into pay. A first
        draft did exactly that and this fixture stopped it: the run went from
        reconciling to 2,000 out.

        Only "added in, yet never positive" is a contradiction worth acting on.
        """
        employee = self.env['hr.employee'].create({'name': 'Positive Person'})
        contract = self.env['hr.contract'].create({
            'name': 'Positive contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        run = self.env['hr.payslip.run'].create({'name': 'Positive run'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'Positive slip',
            'contract_id': contract.id, 'payslip_run_id': run.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30'})
        slip.formula_config_id = self.config.id
        self._classify()
        slip._create_payslip_lines_from_formulas(self.config.rule_ids, {
            'BASE': 9000.0, 'ALWONE': 500.0, 'ALWTWO': 0.0, 'GROSSAGG': 9500.0,
            'SICAP': 0.0, 'SIBASE': 9000.0, 'SIAMT': 945.0, 'PITAMT': 55.0,
            'DEDAGG': 1000.0, 'REFUND': 0.0, 'SWINGSRC': 0.0, 'SWINGADJ': 0.0,
            'NETPAY': 8500.0, 'ERSI': 1575.0, 'ERCOST': 10075.0,
            'INFOFIELD': 0.0})
        for rule in self.config.rule_ids:
            rule.net_role_source = 'auto'
        self._classify()
        for code in ('SIAMT', 'PITAMT', 'DEDAGG'):
            self.assertEqual(self._role(code), 'deduction',
                             "%s is positive AND subtracted — still a deduction"
                             % code)
        roles = {r.code: r.net_role for r in self.config.rule_ids}
        details = {r.code: r.net_role_detail for r in self.config.rule_ids}
        self.assertEqual(self.config._net_role_balance_gap(roles, details)[0],
                         0.0, "9,500 − 1,000 = 8,500, before and after")

    # ------------------------------------------------------------------ 33
    def test_33_two_components_in_the_net_category_is_not_a_coin_toss(self):
        """The demo world files both `FULLPAY` and `NET` under the NET category.

        `FULLPAY` is gross less deductions; `NET` is that less the mid-month
        advance already paid, and it is what lands in the bank. Taking the
        first one in sequence took FULLPAY — which made the REAL net pay a
        component that "contains net pay", i.e. an employer cost. The run then
        reported no take-home at all and the ₫19.8bn advance was a deduction of
        nothing.

        The component's own code says which is which.
        """
        config = self.env['hr.formula.config'].create({
            'name': 'Two in net', 'code': 'TWOINNET', 'country_code': 'VN'})
        cat = {c.code: c for c in self.env['hr.salary.rule.category'].search(
            [('code', 'in', ('OTH', 'NET'))])}
        spec = [
            ('A', 'PAYX', 'Salary', 'input', '', 'OTH'),
            ('B', 'ADVX', 'Advance already paid', 'input', '', 'OTH'),
            # FULLPAY first, exactly as the demo world orders them.
            ('C', 'FULLPAY', 'Full month pay', 'formula', '=A5', 'NET'),
            ('D', 'NET', 'Net payment', 'formula', '=C5-B5', 'NET'),
        ]
        rules, sequence = {}, 10
        for letter, code, name, ctype, formula, category in spec:
            vals = {'config_id': config.id, 'name': name, 'code': code,
                    'column_type': ctype, 'sequence': sequence,
                    'column_letter': letter, 'appears_on_payslip': True,
                    'category_id': cat[category].id}
            if formula:
                vals['excel_formula'] = formula
            rules[code] = self.env['hr.formula.rule'].create(vals)
            sequence += 10
        config.invalidate_recordset()
        summary = config.classify_net_roles()[config.id]
        self.assertIsNone(summary['error'], summary.get('error'))
        self.assertEqual(summary['net_code'], 'NET',
                         "the one named NET is the one that reaches the bank")
        self.assertEqual(rules['NET'].net_role, 'net')
        self.assertEqual(rules['ADVX'].net_role, 'deduction',
                         "an advance already paid reduces what is paid now")
        self.assertNotEqual(rules['NET'].net_role, 'employer_cost')

    # ------------------------------------------------------------------ 34
    def test_34_a_plus_with_a_negative_amount_is_still_a_subtraction(self):
        """`A - B` and `A + B` with B negative are the same subtraction.

        The demo world writes `FULLPAY = GROSS + SIEMP + ... + PIT`, where
        every deduction is a negative amount added in. Read by the plus signs
        alone that is a total of six earnings, so it was not recognised as a
        running total — and `GROSS` was then marked a detail OF it. Since
        FULLPAY is not itself on the payslip, the run reported a gross of ZERO
        against ₫4.96bn of take-home.
        """
        config = self.env['hr.formula.config'].create({
            'name': 'Plus means minus', 'code': 'PLUSMINUS',
            'country_code': 'VN'})
        cat = {c.code: c for c in self.env['hr.salary.rule.category'].search(
            [('code', 'in', ('OTH', 'NET'))])}
        spec = [
            ('A', 'PAYA', 'Salary', 'input', '', 'OTH'),
            ('B', 'TAXA', 'Tax', 'input', '', 'OTH'),
            ('C', 'GROSSA', 'Gross pay', 'formula', '=A5', 'OTH'),
            # Every deduction ADDED, exactly as the demo world writes it.
            ('D', 'FULLA', 'Full pay', 'formula', '=C5+B5', 'NET'),
            ('E', 'NET', 'Net payment', 'formula', '=D5', 'NET'),
        ]
        rules, sequence = {}, 10
        for letter, code, name, ctype, formula, category in spec:
            vals = {'config_id': config.id, 'name': name, 'code': code,
                    'column_type': ctype, 'sequence': sequence,
                    'column_letter': letter, 'appears_on_payslip': True,
                    'category_id': cat[category].id}
            if formula:
                vals['excel_formula'] = formula
            rule = self.env['hr.formula.rule'].create(vals)
            rule.salary_rule_id = self.env['hr.salary.rule'].create({
                'name': name, 'code': code, 'sequence': sequence,
                'category_id': cat[category].id, 'condition_select': 'none',
                'amount_select': 'fix'}).id
            rules[code] = rule
            sequence += 10
        config.invalidate_recordset()

        run = self.env['hr.payslip.run'].create({'name': 'Plus-minus run'})
        employee = self.env['hr.employee'].create({'name': 'Plus Minus Person'})
        contract = self.env['hr.contract'].create({
            'name': 'Plus-minus contract', 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01'})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'Plus-minus slip',
            'contract_id': contract.id, 'payslip_run_id': run.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30'})
        slip.formula_config_id = config.id
        slip._create_payslip_lines_from_formulas(config.rule_ids, {
            'PAYA': 9000.0, 'TAXA': -900.0, 'GROSSA': 9000.0,
            'FULLA': 8100.0, 'NET': 8100.0})
        config.classify_net_roles()

        self.assertEqual(rules['FULLA'].net_role, 'info',
                         "it adds pay and takes tax off — a running total")
        self.assertEqual(rules['GROSSA'].net_role, 'earning')
        self.assertFalse(rules['GROSSA'].net_role_detail,
                         "THE BUG: gross was a detail of a total nobody counts")
        self.assertEqual(rules['TAXA'].net_role, 'deduction')
        roles = {r.code: r.net_role for r in config.rule_ids}
        details = {r.code: r.net_role_detail for r in config.rule_ids}
        self.assertEqual(config._net_role_balance_gap(roles, details)[0], 0.0,
                         "9,000 − 900 = 8,100")

    # ------------------------------------------------------------------ 35
    def test_35_net_pay_named_in_a_sentence_is_still_net_pay(self):
        """rize's second Vietnam workbook: no Net category on anything, and the
        take-home is "Số tiền thực nhận VND (Net Payment VND)".

        The finder only knew bare names ("Net pay"), so it found nothing, the
        classification stopped before writing a single role, and the first run
        read ₫0 gross against ₫10.7bn of deductions. The same workbook has a
        "Net Income" step before it and the same figure again in USD — neither
        of those is what reaches the bank.
        """
        config = self.env['hr.formula.config'].create({
            'name': 'Sentence net', 'code': 'SENTNET', 'country_code': 'VN'})
        self.assertEqual(config.currency_id.name, 'VND')
        other = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'OTH')], limit=1)
        spec = [
            ('A', 'SALARYX', 'Lương tháng (Actual gross salary)', 'input', ''),
            ('B', 'PITX', 'Thuế TNCN (PIT)', 'input', ''),
            ('C', 'REFUNDX', 'Hoàn thuế TNCN (PIT refund)', 'input', ''),
            ('D', 'NETINC', 'Thu nhập ròng VND (Net Income VND)', 'formula',
             '=A5-B5'),
            ('E', 'NETPAYVND', 'Số tiền thực nhận VND (Net Payment VND)',
             'formula', '=D5+C5'),
            ('F', 'NETPAYUSD', 'Số tiền thực nhận USD (Net Payment USD)',
             'input', ''),
        ]
        rules, sequence = {}, 10
        for letter, code, name, ctype, formula in spec:
            vals = {'config_id': config.id, 'name': name, 'code': code,
                    'column_type': ctype, 'sequence': sequence,
                    'column_letter': letter, 'appears_on_payslip': True,
                    'category_id': other.id}
            if formula:
                vals['excel_formula'] = formula
            rules[code] = self.env['hr.formula.rule'].create(vals)
            sequence += 10
        config.invalidate_recordset()

        summary = config.classify_net_roles()[config.id]
        self.assertIsNone(summary['error'], summary.get('error'))
        self.assertEqual(summary['net_code'], 'NETPAYVND')
        self.assertEqual(rules['SALARYX'].net_role, 'earning')
        self.assertEqual(rules['PITX'].net_role, 'deduction')
        self.assertEqual(rules['REFUNDX'].net_role, 'earning')
        self.assertNotEqual(rules['NETPAYUSD'].net_role, 'net')

        # Two equally good answers are a question for a person, not a coin toss.
        rules['NETPAYUSD'].name = 'Số tiền thực nhận VND (Net Payment VND) 2'
        rules['NETPAYUSD'].write({'column_type': 'formula',
                                  'excel_formula': '=E5'})
        self.assertFalse(config._net_role_net_by_label(config._net_role_rules()))

        # And a person's own choice is the answer.
        rules['NETPAYUSD'].write({'net_role': 'net', 'net_role_source': 'user'})
        self.assertEqual(
            config._net_role_find_net_rule(config._net_role_rules()),
            rules['NETPAYUSD'])
