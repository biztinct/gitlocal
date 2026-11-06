# -*- coding: utf-8 -*-
"""The Pay rules step against a real configuration.

The promises here are the ones whose failure would be invisible until somebody
was paid the wrong amount: that the backfill reproduces the rule pack's own
numbers, that a formula somebody typed is never overwritten, that a preview
leaves nothing behind, and that removing a component tells you who was using it.
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComponentsRpc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.Rule = cls.env['hr.formula.rule']
        cls.vn = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_standard_2026'), ('state', '!=', 'superseded')],
            limit=1)

    def _draft(self, token='b2-tok', template='vn_standard_2026'):
        if not self.vn and template != 'blank':
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self.Studio.bp_start({
            'name': 'B2 test configuration',
            'country_code': 'VN',
            'cycle_type': 'regular',
            'template_key': template,
            'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        config = self.env['hr.formula.config'].browse(res['config_id'])
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        return config, blueprint

    def _rule(self, config, code):
        return config.rule_ids.filtered(lambda r: (r.code or '').upper() == code)

    def _paid_sample(self, config):
        """A sample employee who is actually PAID something.

        A rule pack's certification suite leads with its boundary cases — the
        Vietnam pack's first sample is "Zero income" — so `sample_data_ids[0]`
        is a column of zeroes and every "did the number change" assertion
        written against it passes for the wrong reason.
        """
        best, best_pay = config.sample_data_ids[:1], -1.0
        for sample in config.sample_data_ids:
            values = json.loads(sample.input_values_json or '{}')
            try:
                pay = float(values.get('BASIC') or 0.0)
            except (TypeError, ValueError):
                pay = 0.0
            if pay > best_pay:
                best, best_pay = sample, pay
        return best

    def _values(self, config, sample=None):
        """What every component pays a sample employee, by code."""
        sample = sample or self._paid_sample(config)
        result = self.env['pb.formula.studio'].compute_preview(config.id, sample.id)
        by_letter = result.get('values') or {}
        return {(r.code or '').upper(): round(by_letter.get(r.column_letter, 0.0), 2)
                for r in config.rule_ids if r.code and r.column_letter}

    # ---- 8 ----------------------------------------------------------
    def test_backfill_keeps_every_number_the_pack_produced(self):
        """The whole point of the backfill: same numbers, readable rules."""
        config, blueprint = self._draft('b2-backfill')
        before = self._values(config)
        self.assertTrue(before.get('NET'), "the pack must pay somebody something")

        # bp_start already backfilled; assert it happened and is idempotent.
        recipes = config.rule_ids.filtered(lambda r: r.bp_recipe_json)
        self.assertTrue(recipes, "the starter's components must carry rules")
        generated = config.rule_ids.filtered(
            lambda r: r.bp_formula_source == 'generated')
        self.assertTrue(generated)

        listing = self.Studio.bp_components(config.id)
        self.assertTrue(listing['ok'], listing.get('reason'))
        after = self._values(config)
        for code, value in before.items():
            self.assertAlmostEqual(
                after.get(code), value, places=2,
                msg="%s moved from %s to %s after the backfill"
                    % (code, value, after.get(code)))

        # And every certification test the pack ships still passes.
        report = self.env['pb.formula.studio'].run_tests(config.id)
        failed = report.get('failed')
        if failed is None:
            failed = len([r for r in (report.get('results') or [])
                          if r.get('verdict') == 'fail'])
        self.assertEqual(failed, 0, "the pack's own checks must still pass: %s"
                                    % report)

    def test_the_five_groups_are_populated_and_totals_are_locked(self):
        config, blueprint = self._draft('b2-groups')
        res = self.Studio.bp_components(config.id)
        groups = res['groups']
        self.assertTrue(groups['earning'], "the pack pays somebody")
        self.assertTrue(groups['deduction'])
        self.assertTrue(groups['benefit'])
        self.assertTrue(groups['helper'])
        self.assertTrue(groups['total'])
        self.assertEqual(res['counts']['included'], len(config.rule_ids))
        for row in groups['total'] + groups['helper']:
            self.assertTrue(row['locked'], "%s must not be removable" % row['code'])
        for row in groups['earning']:
            self.assertFalse(row['locked'])
        # Every row says something readable about itself.
        for rows in groups.values():
            for row in rows:
                self.assertTrue(row['summary'])
                self.assertIn(row['health'], ('ok', 'review', 'problem'))
                self.assertTrue(row['health_text'])

    # ---- 9 ----------------------------------------------------------
    def test_a_hand_written_formula_is_never_overwritten(self):
        config, blueprint = self._draft('b2-manual')
        sided = self._rule(config, 'SIDED')
        self.assertEqual(sided.bp_formula_source, 'generated')
        generated = sided.bp_generated_formula

        # A plain ORM write — the grid, a bulk save, an import.
        sided.write({'excel_formula': '=Y1*K1*2'})
        self.assertEqual(sided.bp_formula_source, 'manual',
                         "any other formula belongs to the person who wrote it")

        res = self.Studio.bp_regenerate(config.id, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        sided.invalidate_recordset()
        self.assertEqual(
            sided._normalize_excel_formula(sided.excel_formula), '=Y*K*2',
            "regeneration must leave a typed formula alone")
        self.assertEqual(sided.bp_generated_formula, generated,
                         "but it still records what the sentence would produce")

    # ---- 10 ---------------------------------------------------------
    def test_restore_guided_puts_the_sentence_back(self):
        config, blueprint = self._draft('b2-restore')
        sided = self._rule(config, 'SIDED')
        generated = sided.bp_generated_formula
        sided.write({'excel_formula': '=Y1*K1*2'})
        self.assertEqual(sided.bp_formula_source, 'manual')

        blueprint.invalidate_recordset()
        res = self.Studio.bp_component_restore_guided(sided.id, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        sided.invalidate_recordset()
        self.assertEqual(sided.bp_formula_source, 'generated')
        self.assertEqual(sided.excel_formula, generated)

    # ---- 11 ---------------------------------------------------------
    def test_removing_a_component_regenerates_or_refuses_by_name(self):
        config, blueprint = self._draft('b2-exclude')
        bonus = self._rule(config, 'BONUS')
        gross = self._rule(config, 'GROSS')
        # Read the letter BEFORE the row goes: a deleted record raises on any
        # field access, and the assertion after the removal needs it.
        letter = bonus.column_letter
        self.assertIn(letter, gross._normalize_excel_formula(gross.excel_formula))

        res = self.Studio.bp_component_exclude(
            config.id, [bonus.id], False, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        gross.invalidate_recordset()
        self.assertNotIn(letter,
                         gross._normalize_excel_formula(gross.excel_formula or ''))
        self.assertIn('GROSS', res['regenerated'])

        # Now make something depend on ALLOWIN by hand, and try again.
        blueprint.invalidate_recordset()
        allowin = self._rule(config, 'ALLOWIN')
        otpay = self._rule(config, 'OTPAY')
        otpay.write({'excel_formula': '=V1*(D1*S1)+%s1' % allowin.column_letter})
        self.assertEqual(otpay.bp_formula_source, 'manual')
        res = self.Studio.bp_component_exclude(
            config.id, [allowin.id], False, blueprint.revision)
        self.assertFalse(res['ok'])
        self.assertIn('OTPAY', res['reason'])
        self.assertIn('OTPAY', res['blocked_by'])
        self.assertTrue(allowin.exists(), "a refused removal removes nothing")

    def test_a_total_cannot_be_removed(self):
        config, blueprint = self._draft('b2-locked')
        net = self._rule(config, 'NET')
        res = self.Studio.bp_component_exclude(
            config.id, [net.id], False, blueprint.revision)
        self.assertFalse(res['ok'])
        self.assertIn('NET', res['reason'] + ' '.join(res.get('blocked_by') or []))
        self.assertTrue(net.exists())

    # ---- 12 ---------------------------------------------------------
    def test_restoring_a_starter_component_brings_its_rule_back(self):
        config, blueprint = self._draft('b2-include')
        bonus = self._rule(config, 'BONUS')
        old_letter = bonus.column_letter
        self.Studio.bp_component_exclude(config.id, [bonus.id], False,
                                         blueprint.revision)
        blueprint.invalidate_recordset()
        listing = self.Studio.bp_components(config.id)
        self.assertIn('BONUS', [r['code'] for r in listing['removed']])

        res = self.Studio.bp_component_include(config.id, 'BONUS',
                                               blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        back = self._rule(config, 'BONUS')
        self.assertTrue(back.bp_recipe_json, "it comes back with its rule")
        self.assertNotEqual(back.column_letter, old_letter,
                            "a letter is never reused")
        gross = self._rule(config, 'GROSS')
        self.assertIn(back.column_letter,
                      gross._normalize_excel_formula(gross.excel_formula))

    def test_restoring_something_the_starter_no_longer_has(self):
        config, blueprint = self._draft('b2-include-miss')
        res = self.Studio.bp_component_include(config.id, 'NOSUCHTHING',
                                               blueprint.revision)
        self.assertFalse(res['ok'])
        self.assertIn('NOSUCHTHING', res['reason'])

    # ---- 13 ---------------------------------------------------------
    def test_a_preview_never_persists(self):
        config, blueprint = self._draft('b2-preview')
        before = len(config.rule_ids)
        recipe = {'v': 1, 'group': 'earning', 'audience': 'all',
                  'amount': {'kind': 'fixed', 'value': 2000000},
                  'proration': 'none', 'frequency': 'monthly', 'sign': 1,
                  'round': '0',
                  'treatment': {'cash': 'cash', 'tax': 'taxable',
                                'insurance': 'excluded'}}
        res = self.Studio.bp_recipe_preview(
            config.id, None, recipe=recipe, sample_id=False,
            name='Site allowance', code='SITEALLOW', group='earning')
        self.assertTrue(res['ok'], res.get('message'))
        self.assertTrue(res['valid'], res.get('message'))
        self.assertEqual(res['value'], 2000000)
        config.invalidate_recordset(['rule_ids'])
        self.assertEqual(len(config.rule_ids), before,
                         "a preview must leave the configuration untouched")
        self.assertFalse(self._rule(config, 'SITEALLOW'))

        # And saving the same rule produces the same number.
        blueprint.invalidate_recordset()
        saved = self.Studio.bp_component_save(config.id, None, {
            'name': 'Site allowance', 'code': 'SITEALLOW', 'group': 'earning',
            'lane': 'guided', 'recipe': recipe,
            'revision': blueprint.revision})
        self.assertTrue(saved['ok'], saved.get('reason'))
        values = self._values(config)
        self.assertEqual(values.get('SITEALLOW'), 2000000)

    def test_an_invalid_formula_is_refused_and_changes_nothing(self):
        config, blueprint = self._draft('b2-bad')
        sided = self._rule(config, 'SIDED')
        before = sided.excel_formula
        res = self.Studio.bp_component_save(config.id, sided.id, {
            'name': sided.name, 'group': 'deduction', 'lane': 'excel',
            'excel_codes': '=MIN(SIBASE,', 'revision': blueprint.revision})
        self.assertFalse(res['ok'])
        sided.invalidate_recordset()
        self.assertEqual(sided.excel_formula, before)

    def test_the_excel_lane_speaks_codes_both_ways(self):
        config, blueprint = self._draft('b2-excel')
        sided = self._rule(config, 'SIDED')
        opened = self.Studio.bp_component_get(sided.id)
        self.assertTrue(opened['ok'])
        self.assertIn('SIBASE', opened['display_formula'])
        self.assertIn('SIRATE', opened['display_formula'])

        res = self.Studio.bp_component_save(config.id, sided.id, {
            'name': sided.name, 'group': 'deduction', 'lane': 'excel',
            'excel_codes': '=MIN(SIBASE,CAPLO)*SIRATE',
            'revision': blueprint.revision})
        self.assertTrue(res['ok'], res.get('reason'))
        sided.invalidate_recordset()
        stored = sided._normalize_excel_formula(sided.excel_formula)
        self.assertNotIn('SIBASE', stored, "the engine stores letters (BP-R4)")
        self.assertEqual(sided.bp_formula_source, 'manual')

    # ---- 15 ---------------------------------------------------------
    def test_a_stale_revision_is_refused(self):
        config, blueprint = self._draft('b2-rev')
        sided = self._rule(config, 'SIDED')
        res = self.Studio.bp_component_save(config.id, sided.id, {
            'name': sided.name, 'group': 'deduction', 'lane': 'guided',
            'recipe': sided.bp_recipe(),
            'revision': blueprint.revision - 5})
        self.assertFalse(res['ok'])
        self.assertTrue(res.get('conflict'))

    def test_another_companys_configuration_is_refused_plainly(self):
        config, blueprint = self._draft('b2-company')
        other = self.env['res.company'].create({'name': 'B2 Other Company'})
        config.sudo().company_id = other
        res = self.Studio.bp_components(config.id)
        self.assertFalse(res['ok'])
        self.assertIn('B2 Other Company', res['reason'])
        for word in ('Odoo', 'hr.formula', 'Traceback'):
            self.assertNotIn(word, res['reason'])

    def test_helper_inputs_reach_every_sample_employee(self):
        config, blueprint = self._draft('b2-helpers')
        samples = len(config.sample_data_ids)
        self.assertTrue(samples)
        recipe = {'v': 1, 'group': 'earning', 'audience': 'all',
                  'amount': {'kind': 'hourly', 'rate_pct': 200},
                  'proration': 'none', 'frequency': 'monthly', 'sign': 1,
                  'round': '0',
                  'treatment': {'cash': 'cash', 'tax': 'taxable',
                                'insurance': 'excluded'}}
        res = self.Studio.bp_component_save(config.id, None, {
            'name': 'Weekend overtime', 'code': 'WEEKENDOT',
            'group': 'earning', 'lane': 'guided', 'recipe': recipe,
            'revision': blueprint.revision})
        self.assertTrue(res['ok'], res.get('reason'))
        hours = self._rule(config, 'WEEKENDOTHRS')
        self.assertTrue(hours, "the sentence's hours input must be created")
        self.assertEqual(hours.column_type, 'input')
        self.assertFalse(hours.appears_on_payslip)
        self.assertNotIn('_', hours.code)
        self.assertNotIn(hours.name.lower(), ('weekendothrs',),
                         "a helper is named in words, not in its code")
        for sample in config.sample_data_ids:
            stored = json.loads(sample.input_values_json or '{}')
            self.assertIn('WEEKENDOTHRS', stored,
                          "every sample gets the new input, or it reads zero "
                          "for a reason nobody can see")

    def test_a_helper_is_never_summed_into_a_total(self):
        config, blueprint = self._draft('b2-helper-group')
        gross_before = self._values(config).get('GROSS')
        recipe = {'v': 1, 'group': 'earning', 'audience': 'all',
                  'amount': {'kind': 'fixed', 'value': 1000000},
                  'proration': 'none', 'frequency': 'monthly', 'sign': 1,
                  'round': '0',
                  'treatment': {'cash': 'cash', 'tax': 'annual_cap',
                                'cap': 5000000.0, 'insurance': 'excluded'}}
        res = self.Studio.bp_component_save(config.id, None, {
            'name': 'Uniform allowance', 'code': 'UNIFORM',
            'group': 'earning', 'lane': 'guided', 'recipe': recipe,
            'revision': blueprint.revision})
        self.assertTrue(res['ok'], res.get('reason'))
        helper = self._rule(config, 'UNIFORMTX')
        self.assertTrue(helper, "a capped exemption needs its taxable part")
        listing = self.Studio.bp_components(config.id)
        codes = {r['code'] for r in listing['groups']['earning']}
        self.assertIn('UNIFORM', codes)
        self.assertNotIn('UNIFORMTX', codes,
                         "the taxable part is plumbing, not an earning")
        values = self._values(config)
        self.assertAlmostEqual(values.get('GROSS'),
                               (gross_before or 0) + 1000000, places=2)

    def test_which_tab_was_open_is_remembered(self):
        config, blueprint = self._draft('b2-tab')
        res = self.Studio.bp_set_tab(config.id, 'calendar')
        self.assertTrue(res['ok'])
        blueprint.invalidate_recordset()
        self.assertEqual(blueprint.ui().get('rules_tab'), 'calendar')
        loaded = self.Studio.bp_load(config.id)
        self.assertEqual(loaded['blueprint']['ui'].get('rules_tab'), 'calendar')

    def test_a_blank_canvas_says_so_rather_than_breaking(self):
        config, blueprint = self._draft('b2-blank', template='blank')
        res = self.Studio.bp_components(config.id)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['counts']['included'], 0)
        self.assertEqual(res['removed'], [])
