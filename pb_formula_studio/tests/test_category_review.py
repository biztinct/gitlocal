# -*- coding: utf-8 -*-
"""NETROLE P2 — the import ends with a category conversation, not a guess.

Two seams are under test here.

The CHAIN: an import used to finish with a notification whose `next` opened the
people-mapping board. It now finishes by asking what each component turned out
to be — and carries the old chain through, so nothing that used to happen
stops. A scheme with nothing to say chains exactly what it chained before.

The SURFACE: `category_review_data` is the whole dialog in one payload —
grouped rows, the sentence behind each one, and the tick each row arrives with.
The tick is the part worth testing, because it is a promise: a category the
user's own spreadsheet band already claimed is never silently overruled.

The fixture is ABM's shape in miniature, with two deliberate defects:
`SEVERANCEPAY` sits under a "Deductions" band while the formula ADDS it to net,
and the two hour columns are filed as Allowances — which is exactly where the
first pass over ABM's live scheme put them.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCategoryReview(TransactionCase):

    def setUp(self):
        super().setUp()
        Category = self.env['hr.salary.rule.category']
        for code in ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP', 'OTH'):
            if not Category.search([('code', '=', code)], limit=1):
                Category.create({'name': code.title(), 'code': code})
        self.other = Category.search([('code', '=', 'OTH')], limit=1)
        self.alw = Category.search([('code', '=', 'ALW')], limit=1)
        self.config = self._make_config('Category review miniature', 'CATREVMINI', [
            # letter, code,       name,                  type,     formula, band, category
            ('A', 'BASESALARY', 'Base Salary', 'input', '', 'Earnings', None),
            ('B', 'MEALALLOW', 'Meal Allowance', 'input', '', 'Allowances', None),
            ('C', 'STANWORKHOUR', 'Standard Working Hour', 'input', '', '', 'ALW'),
            ('D', 'ACTUWORKHOUR', 'Actual Working Hours', 'input', '', '', 'ALW'),
            ('E', 'SEVERANCEPAY', 'Severance Payment', 'input', '', 'Deductions', None),
            ('F', 'ACTUBASIC', 'Actual Basic salary', 'formula',
             '=ROUND(A5/C5*D5,0)', '', None),
            ('G', 'GROSSPAY', 'Actual Total Income', 'formula',
             '=F5+B5+E5', 'Earnings', None),
            ('H', 'SOCIALINS8', 'Social Ins. - 8%', 'formula', '=A5*8%',
             'Deductions', None),
            ('I', 'TOTALDEDUCT', 'Total Deduction', 'formula', '=H5',
             'Deductions', None),
            ('J', 'NETPAY', 'Net Pay', 'formula', '=G5-I5', 'Earnings', None),
        ])

    def _make_config(self, name, code, spec):
        config = self.env['hr.formula.config'].create({
            'name': name, 'code': code, 'country_code': 'VN'})
        Category = self.env['hr.salary.rule.category']
        self.rules = getattr(self, 'rules', {})
        sequence = 10
        for letter, rcode, rname, ctype, formula, band, cat in spec:
            category = (Category.search([('code', '=', cat)], limit=1)
                        if cat else self.other)
            vals = {
                'config_id': config.id, 'name': rname, 'code': rcode,
                'column_type': ctype, 'sequence': sequence,
                'column_letter': letter, 'category_id': category.id,
            }
            if formula:
                vals['excel_formula'] = formula
            if band:
                vals['component_type'] = band
            rule = self.env['hr.formula.rule'].create(vals)
            rule.salary_rule_id = self.env['hr.salary.rule'].create({
                'name': rname, 'code': rcode, 'sequence': sequence,
                'category_id': self.other.id, 'condition_select': 'none',
                'amount_select': 'fix'}).id
            self.rules[rcode] = rule
            sequence += 10
        config.invalidate_recordset()
        return config

    def _data(self, config=None):
        return self.env['pb.formula.studio'].category_review_data(
            (config or self.config).id)

    def _row(self, data, code):
        for group in data['groups']:
            for row in group['rows']:
                if row['code'] == code:
                    return group['key'], row
        self.fail("no review row for %s" % code)

    # ------------------------------------------------------------------ 1
    def test_01_an_import_ends_at_the_review(self):
        """The completion action is the seam both single-sheet paths funnel
        through; the review takes over its `next` and carries the old one."""
        wizard = self.env['hr.formula.import.wizard'].create({
            'config_id': self.config.id})
        action = wizard._import_completion_action(self.config.rule_ids,
                                                 ['8 rules imported'])
        self.assertEqual(action['tag'], 'display_notification')
        nxt = action['params'].get('next')
        self.assertTrue(nxt, "the review was not chained")
        self.assertEqual(nxt['tag'], 'pb_category_review')
        self.assertEqual(nxt['params']['config_id'], self.config.id)
        self.assertNotIn('Odoo', action['params']['message'])

    # ------------------------------------------------------------------ 1b
    def test_01b_a_scheme_with_nothing_to_say_chains_what_it_always_did(self):
        already = self._make_config('Already filed', 'CATREVDONE', [
            ('A', 'PAYBASIC', 'Base Salary', 'input', '', '', None),
            ('B', 'PAYNET', 'Net Pay', 'formula', '=A5', '', None),
        ])
        # File it the way the formulas read it, then ask again.
        already.classify_net_roles()
        already.apply_suggested_categories()
        wizard = self.env['hr.formula.import.wizard'].create({
            'config_id': already.id})
        action = wizard._import_completion_action(already.rule_ids, ['2 rules'])
        self.assertIsNone(action['params'].get('next'),
                          "nothing to suggest, so nothing should be chained")

    # ------------------------------------------------------------------ 2
    def test_02_a_scheme_with_no_net_pay_still_imports(self):
        """A classification that cannot reach a conclusion must never fail the
        import — and the one thing it cannot conclude is a question the review
        asks rather than swallows."""
        netless = self._make_config('Netless scheme', 'CATREVNONET', [
            ('A', 'ALPHAONE', 'Alpha', 'input', '', '', None),
            ('B', 'BETATWO', 'Beta', 'formula', '=A5*2', '', None),
        ])
        wizard = self.env['hr.formula.import.wizard'].create({
            'config_id': netless.id})
        action = wizard._import_completion_action(netless.rule_ids, ['2 rules'])
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(action['params']['type'], 'success')
        nxt = action['params'].get('next')
        self.assertTrue(nxt)
        self.assertEqual(nxt['tag'], 'pb_category_review')

        data = self._data(netless)
        self.assertTrue(data['error'])
        self.assertNotIn('Odoo', data['error'])
        codes = {c['code'] for c in data['net_candidates']}
        self.assertIn('BETATWO', codes)

        # ...and naming it makes the scheme readable.
        beta = netless.rule_ids.filtered(lambda r: r.code == 'BETATWO')
        after = self.env['pb.formula.studio'].category_review_set_net(
            netless.id, beta.id)
        self.assertFalse(after['error'])
        self.assertEqual(after['net_code'], 'BETATWO')

    # ------------------------------------------------------------------ 3
    def test_03_the_payload_holds_both_opinions(self):
        data = self._data()
        self.assertFalse(data['error'])
        self.assertEqual(data['net_code'], 'NETPAY')

        group, row = self._row(data, 'SEVERANCEPAY')
        self.assertEqual(group, 'review',
                         "a band that contradicts the formula needs a person")
        self.assertEqual(row['role'], 'earning')
        self.assertEqual(row['suggested'], 'ALW')
        self.assertTrue(row['band_conflict'])
        self.assertIn('Deductions', row['band_conflict_text'])

        _g, agreeing = self._row(data, 'SOCIALINS8')
        self.assertFalse(agreeing['band_conflict'])
        self.assertEqual(agreeing['suggested'], 'DED')

    # ------------------------------------------------------------------ 4
    def test_04_apply_writes_exactly_the_rows_you_ticked(self):
        data = self._data()
        _g, meal = self._row(data, 'MEALALLOW')
        before = {code: rule.category_id.code
                  for code, rule in self.rules.items()}
        applied = self.env['pb.formula.studio'].category_review_apply(
            self.config.id, [meal['id']])
        self.assertEqual(applied['applied'], 1)
        self.assertEqual(self.rules['MEALALLOW'].category_id.code, 'ALW')
        self.assertEqual(self.rules['MEALALLOW'].salary_rule_id.category_id.code,
                         'ALW', "the shadow salary rule moves with the rule")
        for code, rule in self.rules.items():
            if code == 'MEALALLOW':
                continue
            self.assertEqual(rule.category_id.code, before[code], code)

    # ------------------------------------------------------------------ 5
    def test_05_the_default_tick_never_overrules_a_persons_own_coding(self):
        data = self._data()
        _g, conflicted = self._row(data, 'SEVERANCEPAY')
        self.assertFalse(conflicted['accept'],
                         "their band disagrees — the math wins by a click only")
        _g, certain = self._row(data, 'SOCIALINS8')
        self.assertEqual(certain['confidence'], 'certain')
        self.assertTrue(certain['accept'])
        # An hour count filed as an Allowance — the live ABM defect — arrives
        # ticked: the label and the arithmetic both say it counts, and the move
        # it proposes is out of pay and into information.
        group, hours = self._row(data, 'STANWORKHOUR')
        self.assertEqual(group, 'info')
        self.assertTrue(hours['quantity'])
        self.assertEqual(hours['current'], 'ALW')
        self.assertEqual(hours['suggested'], 'OTH')
        self.assertTrue(hours['accept'])

        # ...and the policy itself, stated as a table rather than inferred.
        studio = self.env['pb.formula.studio']
        matrix = [
            ({'changes': False, 'confidence': 'certain'}, False),
            ({'changes': True, 'band_conflict': True, 'confidence': 'certain'}, False),
            ({'changes': True, 'confidence': 'review'}, False),
            ({'changes': True, 'confidence': 'review', 'quantity': True}, False),
            ({'changes': True, 'confidence': 'likely', 'quantity': True,
              'current_category': 'ALW'}, True),
            ({'changes': True, 'confidence': 'certain'}, True),
            ({'changes': True, 'confidence': 'likely', 'band_kind': 'deduction'}, True),
            ({'changes': True, 'confidence': 'likely', 'current_category': 'OTH'}, True),
            ({'changes': True, 'confidence': 'likely', 'current_category': 'ALW'}, False),
        ]
        for row, expected in matrix:
            self.assertEqual(studio._category_review_checked(row), expected, row)

    # ------------------------------------------------------------------ 5b
    def test_05b_a_row_that_already_matches_is_not_a_row(self):
        """Applying once empties the dialog — the second visit is the green
        "everything already matches" state, not a list of no-ops."""
        data = self._data()
        every = [row['id'] for group in data['groups'] for row in group['rows']]
        self.env['pb.formula.studio'].category_review_apply(
            self.config.id, every)
        after = self._data()
        self.assertFalse(
            [r for g in after['groups'] for r in g['rows'] if r['changes']],
            "nothing should still want to move")
        self.assertTrue(after['agree_count'])

    # ------------------------------------------------------------------ 6
    def test_06_reading_the_review_writes_no_categories(self):
        before = {r.id: r.category_id.id for r in self.config.rule_ids}
        self._data()
        self._data()
        self.assertEqual(
            before, {r.id: r.category_id.id for r in self.config.rule_ids})
