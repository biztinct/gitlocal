# -*- coding: utf-8 -*-
"""The Vietnam · Complete starter, and the compiler pieces it needed.

Two kinds of promise:

* **the arithmetic** — the five people in the starter's own test suite come out
  at the numbers they were signed off at, through the real engine, and the
  guided setup's regeneration does not change a single one of them;
* **the shape** — every code satisfies the template registry's contract, the
  income-tax routes take the right branch for the right person, a shared
  benefit produces both halves, and a plan total is never counted twice.
"""
import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_blueprint.models import recipe_compiler as rc
from odoo.addons.pb_blueprint.models.recipe_schema import validate_recipe

TEMPLATE = 'vn_complete_2026'


@tagged('post_install', '-at_install')
class TestVnComplete(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.tpl = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', TEMPLATE)], limit=1)

    def _draft(self, token='b3-complete'):
        res = self.Studio.bp_start({
            'name': 'B3 complete configuration', 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': TEMPLATE, 'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        config = self.env['hr.formula.config'].browse(res['config_id'])
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        return config, blueprint

    def _rule(self, config, code):
        return config.rule_ids.filtered(lambda r: (r.code or '').upper() == code)

    def _values(self, config, sample):
        result = self.env['pb.formula.studio'].compute_preview(config.id, sample.id)
        by_letter = result.get('values') or {}
        return {(r.code or '').upper(): round(by_letter.get(r.column_letter, 0.0), 2)
                for r in config.rule_ids if r.code and r.column_letter}

    # ---- 8 ----------------------------------------------------------
    def test_the_starter_exists_and_keeps_the_registry_contract(self):
        self.assertTrue(self.tpl, "Vietnam · Complete must be installed")
        self.assertEqual(self.tpl.country_code, 'VN')
        self.assertEqual(self.tpl.version, '2026.1')
        comps = self.tpl._components()
        self.assertEqual(len(comps), 93)
        codes = [c['code'] for c in comps] + [
            t['code'] for t in self.tpl._rate_tables()]
        # The contract that makes the converter safe: no code inside another.
        for a in codes:
            self.assertNotIn('_', a)
            for b in codes:
                if a != b:
                    self.assertNotIn(a, b, "%s is inside %s" % (a, b))
        # Every component carries the sentence it was compiled from.
        self.assertTrue(all(c.get('recipe') for c in comps))
        # A starter may not ship the per-component helpers (they contain their
        # parent's code); the guided setup creates them at seed time.
        self.assertNotIn('OTWDHRS', codes)
        self.assertNotIn('UNIFORMYTD', codes)

    def test_every_recipe_it_ships_is_one_the_server_accepts(self):
        comps = self.tpl._components()
        known = {c['code'] for c in comps}
        tables = {t['code'] for t in self.tpl._rate_tables()}
        for comp in comps:
            clean = validate_recipe(comp['recipe'], {
                'codes': known, 'rate_tables': tables, 'self_code': comp['code']})
            self.assertEqual(clean['group'], comp['recipe']['group'])

    def test_the_certification_suite_passes_through_the_real_engine(self):
        """The gate that blocks the install if a number ever moves."""
        report = self.tpl.run_certification(raise_on_fail=False)
        self.assertTrue(report['passed'],
                        "failing checks: %s" % (report['failed'] or report['log']))
        self.assertEqual(report['total'], 5)

    def test_a_guided_draft_reproduces_the_certified_numbers(self):
        """Seeding, provisioning helpers and regenerating changes nothing."""
        config, blueprint = self._draft('b3-complete-cert')
        broken = config.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and not r.python_formula)
        self.assertFalse(broken, broken.mapped('code'))

        by_name = {s.name: s for s in config.sample_data_ids}
        for test in self.tpl._sample_tests():
            sample = by_name.get(test['name'])
            self.assertTrue(sample, "the persona %s must be seeded" % test['name'])
            values = self._values(config, sample)
            for code, expected in (test.get('expected') or {}).items():
                self.assertAlmostEqual(
                    values.get(code, 0.0), float(expected), delta=1.0,
                    msg="%s / %s after the guided setup" % (test['name'], code))

    def test_the_five_people_are_the_ones_the_report_names(self):
        names = [t['name'] for t in self.tpl._sample_tests()]
        self.assertEqual(names, [
            'Full month · local', 'Joined mid-month',
            'Foreign · not tax resident', 'Short contract',
            'Enrolled in private health'])

    # ---- 7 ----------------------------------------------------------
    def test_income_tax_takes_the_route_that_fits_the_person(self):
        """Resident, non-resident and short contract, on one component."""
        config, blueprint = self._draft('b3-routes')
        base = {'BASIC': 30000000.0, 'STDDAYS': 26.0, 'PAIDDAYS': 26.0,
                'HOURSDAY': 8.0, 'PAYMONTH': 3.0, 'DEPS': 1.0, 'ISLOCAL': 1.0,
                'ISINSURED': 1.0, 'ISUNION': 0.0, 'ISRESIDENT': 1.0,
                'CONTRACTMTH': 12.0, 'TAXCOMMIT': 0.0}
        sample = self.env['hr.formula.sample.data'].create({
            'config_id': config.id, 'name': 'route probe',
            'input_values_json': json.dumps(base)})

        resident = self._values(config, sample)
        self.assertAlmostEqual(resident['PIT'], 315000.0, delta=1.0)

        sample.input_values_json = json.dumps(dict(base, ISRESIDENT=0.0))
        nonres = self._values(config, sample)
        # 20% of assessable pay, no relief, whatever the bands say.
        self.assertAlmostEqual(nonres['PIT'], 0.2 * nonres['ASSESSPAY'], delta=1.0)

        sample.input_values_json = json.dumps(
            dict(base, CONTRACTMTH=2.0, ISINSURED=0.0))
        short = self._values(config, sample)
        self.assertAlmostEqual(short['PIT'], 0.1 * short['ASSESSPAY'], delta=1.0)

        # The commitment says "this is my only income": nothing is withheld.
        sample.input_values_json = json.dumps(
            dict(base, CONTRACTMTH=2.0, ISINSURED=0.0, TAXCOMMIT=1.0))
        committed = self._values(config, sample)
        self.assertEqual(committed['PIT'], 0.0)

        # Below the threshold nothing is withheld either.
        sample.input_values_json = json.dumps(
            dict(base, BASIC=3000000.0, CONTRACTMTH=2.0, ISINSURED=0.0))
        small = self._values(config, sample)
        self.assertLess(small['ASSESSPAY'], 5000000.0)
        self.assertEqual(small['PIT'], 0.0)

    def test_a_plan_total_is_shown_but_never_charged_twice(self):
        config, blueprint = self._draft('b3-plan')
        sample = config.sample_data_ids.filtered(
            lambda s: s.name == 'Full month · local')[:1]
        values = self._values(config, sample)
        parts = values['SICOMP'] + values['HICOMP'] + values['UICOMP']
        self.assertAlmostEqual(values['SHUILOCAL'], parts, delta=1.0)
        self.assertAlmostEqual(
            values['ERCOST'], values['GROSS'] + parts, delta=1.0,
            msg="the roll-up must not be added on top of what it rolls up")
        ercost = self._rule(config, 'ERCOST')
        self.assertNotIn(self._rule(config, 'SHUILOCAL').column_letter,
                         self.Studio._display_formula(config, ercost.excel_formula))

    def test_a_shared_benefit_produces_both_halves(self):
        """A plan the employee pays 30% of is two lines, from one sentence."""
        config, blueprint = self._draft('b3-share')
        rule = self._rule(config, 'PRIVHLTHEE')
        recipe = rule.bp_recipe()
        recipe['treatment']['employer_share_pct'] = 70.0
        res = self.Studio.bp_component_save(config.id, rule.id, {
            'recipe': recipe, 'lane': 'guided', 'revision': blueprint.revision})
        self.assertTrue(res['ok'], res.get('reason'))

        share = self._rule(config, 'PRIVHLTHEEEE')
        self.assertTrue(share, "the employee's share has to exist as its own line")
        self.assertEqual(share.bp_recipe()['group'], 'deduction')

        sample = self.env['hr.formula.sample.data'].create({
            'config_id': config.id, 'name': 'share probe',
            'input_values_json': json.dumps({
                'BASIC': 30000000.0, 'STDDAYS': 26.0, 'PAIDDAYS': 26.0,
                'HOURSDAY': 8.0, 'PAYMONTH': 3.0, 'ISLOCAL': 1.0,
                'ISINSURED': 1.0, 'ISRESIDENT': 1.0, 'CONTRACTMTH': 12.0,
                'ENROLHLTH': 1.0, 'HLTHEEAMT': 1000000.0})})
        values = self._values(config, sample)
        self.assertAlmostEqual(values['PRIVHLTHEE'], 700000.0, delta=1.0)
        self.assertAlmostEqual(values['PRIVHLTHEEEE'], 300000.0, delta=1.0)

    def test_union_dues_stop_at_their_ceiling(self):
        config, blueprint = self._draft('b3-union')
        sample = self.env['hr.formula.sample.data'].create({
            'config_id': config.id, 'name': 'union probe',
            'input_values_json': json.dumps({
                'BASIC': 30000000.0, 'STDDAYS': 26.0, 'PAIDDAYS': 26.0,
                'HOURSDAY': 8.0, 'PAYMONTH': 3.0, 'ISLOCAL': 1.0,
                'ISINSURED': 1.0, 'ISUNION': 1.0, 'ISRESIDENT': 1.0,
                'CONTRACTMTH': 12.0})})
        values = self._values(config, sample)
        # 0.5% of 30,000,000 is 150,000, under the 253,000 ceiling.
        self.assertAlmostEqual(values['UNIONDUES'], 150000.0, delta=1.0)
        self.assertAlmostEqual(values['UNIONER'], 600000.0, delta=1.0)

        sample.input_values_json = json.dumps({
            'BASIC': 90000000.0, 'STDDAYS': 26.0, 'PAIDDAYS': 26.0,
            'HOURSDAY': 8.0, 'PAYMONTH': 3.0, 'ISLOCAL': 1.0, 'ISINSURED': 1.0,
            'ISUNION': 1.0, 'ISRESIDENT': 1.0, 'CONTRACTMTH': 12.0})
        capped = self._values(config, sample)
        # The base is capped at 46,800,000 and the dues at 253,000.
        self.assertAlmostEqual(capped['UNIONDUES'], 233999.0, delta=1.0)

    # ---- 9 ----------------------------------------------------------
    def test_a_library_component_can_be_taken_out_and_put_back(self):
        config, blueprint = self._draft('b3-inout')
        for code in ('OTWD', 'PRIVHLTHDEP'):
            rule = self._rule(config, code)
            self.assertTrue(rule, code)
            res = self.Studio.bp_component_exclude(
                config.id, [rule.id], False, blueprint.revision)
            self.assertTrue(res['ok'], "%s: %s" % (code, res.get('reason')))
            self.assertFalse(self._rule(config, code))

            res = self.Studio.bp_component_include(
                config.id, code, blueprint.revision)
            self.assertTrue(res['ok'], "%s: %s" % (code, res.get('reason')))
            back = self._rule(config, code)
            self.assertTrue(back)
            self.assertTrue(back.bp_recipe(), "it comes back with its sentence")

    def test_the_components_tab_groups_the_whole_library(self):
        config, blueprint = self._draft('b3-groups')
        listing = self.Studio.bp_components(config.id)
        self.assertTrue(listing['ok'], listing.get('reason'))
        groups = listing['groups']
        codes = {g: {r['code'] for r in rows} for g, rows in groups.items()}
        self.assertIn('SALARYPAID', codes['earning'])
        self.assertIn('OTHOL', codes['earning'])
        self.assertIn('PIT', codes['deduction'])
        self.assertIn('SHUILOCAL', codes['benefit'])
        self.assertIn('NET', codes['total'])
        self.assertIn('BASIC', codes['helper'])
        self.assertEqual(len(codes['earning']), 24)
        self.assertEqual(len(codes['deduction']), 8)

    def test_the_employer_paid_tax_is_raised_as_a_decision_not_hidden(self):
        config, blueprint = self._draft('b3-review')
        listing = self.Studio.bp_components(config.id)
        rows = {r['code']: r for rows in listing['groups'].values() for r in rows}
        health = rows['PRIVHLTHEE']
        self.assertEqual(health['health'], 'review')
        self.assertTrue(any(item['code'] == 'employer_tax'
                            for item in health['review']))
        self.assertIn('employer', health['health_text'].lower())

        overtime = rows['OTWD']
        self.assertTrue(any(item['code'] == 'ot_scope'
                            for item in overtime['review']))


@tagged('post_install', '-at_install')
class TestCompilerExtensions(TransactionCase):
    """The pure compiler, with no database in the way."""

    def _ctx(self, codes, recipes=None, types=None, groups=None):
        letters = {}
        for i, code in enumerate(codes):
            letters[code] = chr(ord('A') + i)
        return rc.Ctx({
            'letters': letters, 'recipes': recipes or {}, 'groups': groups or {},
            'types': types or {}, 'order': list(codes),
            'rate_tables': {'VNTAX'}, 'self_code': '', 'contract_code': 'BASIC'})

    def test_the_tax_routes_degrade_to_the_bands_when_nothing_else_exists(self):
        ctx = self._ctx(['TAXABLE', 'PIT'])
        ctx['self_code'] = 'PIT'
        formula, needs = rc.compile_recipe({
            'group': 'deduction', 'round': 'none',
            'amount': {'kind': 'pit_vn', 'table': 'VNTAX', 'base': 'TAXABLE'},
        }, ctx)
        self.assertEqual(needs, [])
        self.assertEqual(formula, '=ROUND(BRACKET(VNTAX,A),0)')

    def test_rounding_downward_uses_the_engines_own_function(self):
        ctx = self._ctx(['BASIC', 'X'], types={'BASIC': 'input'})
        ctx['self_code'] = 'X'
        formula, _needs = rc.compile_recipe({
            'group': 'earning', 'round': 'down',
            'amount': {'kind': 'contract'},
        }, ctx)
        self.assertEqual(formula, '=ROUNDDOWN(A,0)')

    def test_a_named_input_is_used_instead_of_the_conventional_one(self):
        ctx = self._ctx(['HRSWD', 'BASIC', 'STDDAYS', 'HOURSDAY', 'OTWD'],
                        types={'BASIC': 'input'})
        ctx['self_code'] = 'OTWD'
        formula, needs = rc.compile_recipe({
            'group': 'earning', 'round': '0',
            'amount': {'kind': 'hourly', 'rate_pct': 150.0},
            'inputs': {'hours': 'HRSWD'},
        }, ctx)
        self.assertEqual(needs, [])
        self.assertIn('A*', formula)          # HRSWD, not OTWDHRS

    def test_a_correction_that_follows_the_original_does_not_add_it_again(self):
        """The bug this replaced would have taxed a whole salary twice."""
        recipes = {'SALARYPAID': {'group': 'earning',
                                  'treatment': {'tax': 'taxable'}}}
        ctx = self._ctx(['SALARYPAID', 'ADJADD'], recipes=recipes)
        ctx['self_code'] = 'ADJADD'
        formula, _needs = rc.taxable_helper_formula({
            'group': 'earning',
            'amount': {'kind': 'input'},
            'treatment': {'tax': 'inherit', 'source_code': 'SALARYPAID'},
        }, ctx)
        self.assertIsNone(formula, "a taxable original needs no helper at all")

        recipes['SALARYPAID']['treatment']['tax'] = 'exempt'
        formula, _needs = rc.taxable_helper_formula({
            'group': 'earning',
            'amount': {'kind': 'input'},
            'treatment': {'tax': 'inherit', 'source_code': 'SALARYPAID'},
        }, ctx)
        self.assertEqual(formula, '=0')

    def test_two_conditions_at_once_compile_to_one_test(self):
        ctx = self._ctx(['ISLOCAL', 'ISINSURED', 'UIBASE', 'UIRATE', 'UIDED'])
        ctx['self_code'] = 'UIDED'
        formula, needs = rc.compile_recipe({
            'group': 'deduction', 'audience': 'local_insured', 'round': '0',
            'amount': {'kind': 'percent_of', 'base': 'UIBASE',
                       'rate_code': 'UIRATE'},
        }, ctx)
        self.assertEqual(needs, [])
        self.assertIn('AND(A=1,B=1)', formula)

    def test_a_ceiling_stops_an_amount_growing(self):
        ctx = self._ctx(['SIBASE', 'UNIONRATE', 'UNIONCAP', 'UNIONDUES'])
        ctx['self_code'] = 'UNIONDUES'
        formula, _needs = rc.compile_recipe({
            'group': 'deduction', 'round': 'none',
            'amount': {'kind': 'percent_of', 'base': 'SIBASE',
                       'rate_code': 'UNIONRATE', 'max': 'UNIONCAP'},
        }, ctx)
        self.assertEqual(formula, '=MIN((A*B),C)')

    def test_a_payment_the_scheme_decides_waits_to_be_told(self):
        ctx = self._ctx(['BASIC', 'PAIDVAR', 'VARPAY'], types={'BASIC': 'input'})
        ctx['self_code'] = 'VARPAY'
        formula, _needs = rc.compile_recipe({
            'group': 'earning', 'frequency': 'scheme', 'round': '0',
            'amount': {'kind': 'percent_contract', 'percent': 10.0},
            'inputs': {'run': 'PAIDVAR'},
        }, ctx)
        self.assertEqual(formula, '=ROUND(IF(B=1,(A*10/100),0),0)')

    def test_the_insurance_base_can_read_the_contract_instead(self):
        recipes = {'SALARYPAID': {'group': 'earning',
                                  'treatment': {'insurance': 'included'}}}
        groups = {'SALARYPAID': 'earning'}
        ctx = self._ctx(['BASIC', 'SALARYPAID', 'CAPLO', 'SIBASE'],
                        recipes=recipes, groups=groups, types={'BASIC': 'input'})
        ctx['self_code'] = 'SIBASE'
        actual, _n = rc.compile_recipe({
            'group': 'total', 'round': 'none',
            'amount': {'kind': 'insurance_base', 'cap': 'CAPLO',
                       'basis': 'actual'}}, ctx)
        self.assertEqual(actual, '=MIN(B,C)')
        contract, _n = rc.compile_recipe({
            'group': 'total', 'round': 'none',
            'amount': {'kind': 'insurance_base', 'cap': 'CAPLO',
                       'basis': 'contract'}}, ctx)
        self.assertEqual(contract, '=MIN(A,C)')
