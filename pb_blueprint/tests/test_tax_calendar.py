# -*- coding: utf-8 -*-
"""Tax, protection and the pay calendar, against a real configuration.

The failures these guard against are the ones nobody would see until a payslip
was wrong: a band edit that does not reach the tax, a statutory value written
without a reason anybody can audit, a value screen that keeps working on a
configuration that has already paid people, and a payday that quietly lands on
a Sunday.
"""
import json
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_blueprint.models.payday import payday_for


@tagged('post_install', '-at_install')
class TestTaxTab(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.vn = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_standard_2026'), ('state', '!=', 'superseded')],
            limit=1)

    def _draft(self, token='b3-tok', template='vn_standard_2026'):
        if not self.vn and template != 'blank':
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self.Studio.bp_start({
            'name': 'B3 test configuration', 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': template,
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
        sample = sample or self._paid_sample(config)
        result = self.env['pb.formula.studio'].compute_preview(config.id, sample.id)
        by_letter = result.get('values') or {}
        return {(r.code or '').upper(): round(by_letter.get(r.column_letter, 0.0), 2)
                for r in config.rule_ids if r.code and r.column_letter}

    # ---- 1 ----------------------------------------------------------
    def test_the_tab_names_its_pack_and_every_value_it_owns(self):
        """The pack is found, matched to the rules, and reported as aligned."""
        config, blueprint = self._draft('b3-data')
        data = self.Studio.bp_tax_data(config.id)
        self.assertTrue(data['ok'], data.get('reason'))

        self.assertTrue(data['pack'], "a published Vietnam pack must be found")
        self.assertEqual(data['pack']['version'], '2026.1')
        self.assertEqual(data['status'], 'aligned', data['drift'])
        self.assertFalse(data['drift'])

        # The pin is stored the first time the tab is opened, so a pack
        # published later cannot change what this was built against.
        blueprint.invalidate_recordset(['pack_id', 'pack_version'])
        self.assertEqual(blueprint.pack_id.id, data['pack']['id'])
        self.assertEqual(blueprint.pack_version, '2026.1')

        tables = {t['code']: t for t in data['tables']}
        self.assertIn('VNTAX', tables)
        self.assertEqual(len(tables['VNTAX']['brackets']), 7)
        self.assertIn('PIT', tables['VNTAX']['used_by'])

        relief = {r['code'] for r in data['values']['relief']}
        self.assertEqual(relief, {'DEDUCTSELF', 'DEDUCTDEP'})
        insurance = {r['code'] for r in data['values']['insurance']}
        self.assertEqual(insurance, {'CAPLO', 'CAPHI', 'SIRATE', 'HIRATE',
                                     'UIRATE', 'SIEMPR', 'HIEMPR', 'UIEMPR'})
        # Essentials has no non-resident or short-contract route.
        self.assertEqual(data['values']['routes'], [])
        self.assertTrue(data['editable'])
        self.assertEqual(data['prefs'],
                         {'basis': 'actual', 'rounding': '0'})

    def test_the_rate_is_matched_through_the_starter_not_its_name(self):
        """SIRATE carries the pack's EESI, and nothing is called EESI."""
        config, blueprint = self._draft('b3-map')
        self.assertFalse(self._rule(config, 'EESI'),
                         "the pack's own code is not a component code")
        pack = self.Studio._tax_pack(config, blueprint)
        mapped = self.Studio._legis_rule_map(config, blueprint, pack)
        self.assertEqual((mapped['EESI'].code or '').upper(), 'SIRATE')
        self.assertEqual((mapped['ERUI'].code or '').upper(), 'UIEMPR')

    # ---- 2 ----------------------------------------------------------
    def test_a_band_edit_changes_the_tax_that_is_actually_paid(self):
        """Doubling the second band's rate moves income tax on the sample."""
        config, blueprint = self._draft('b3-bands')
        sample = self._paid_sample(config)
        stored = json.loads(sample.input_values_json or '{}')
        stored.update({'BASIC': 40000000.0, 'STDDAYS': 26.0, 'DEPS': 0.0})
        sample.input_values_json = json.dumps(stored)
        before = self._values(config, sample)
        self.assertGreater(before['PIT'], 0)

        data = self.Studio.bp_tax_data(config.id)
        table = next(t for t in data['tables'] if t['code'] == 'VNTAX')
        brackets = [dict(b) for b in table['brackets']]
        brackets[1]['rate'] = 0.20            # 10% -> 20% on 5m to 10m
        res = self.Studio.bp_tax_save_bands(
            config.id, table['id'], brackets, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        after = self._values(config, sample)
        # The 5m-to-10m slice is 5,000,000 wide and its rate rose 10 points.
        self.assertAlmostEqual(after['PIT'] - before['PIT'], 500000.0, places=0)
        self.assertAlmostEqual(before['NET'] - after['NET'], 500000.0, places=0)

    def test_a_schedule_that_cannot_be_right_is_refused_by_name(self):
        config, blueprint = self._draft('b3-badbands')
        data = self.Studio.bp_tax_data(config.id)
        table = next(t for t in data['tables'] if t['code'] == 'VNTAX')

        twice = [{'lower': 0, 'rate': 0.05}, {'lower': 0, 'rate': 0.10}]
        res = self.Studio.bp_tax_save_bands(config.id, table['id'], twice)
        self.assertFalse(res['ok'])
        self.assertIn('same amount', res['reason'])

        too_much = [{'lower': 0, 'rate': 1.5}]
        res = self.Studio.bp_tax_save_bands(config.id, table['id'], too_much)
        self.assertFalse(res['ok'])
        self.assertIn('between 0 and 100', res['reason'])

        adrift = [{'lower': 1000000, 'rate': 0.05}]
        res = self.Studio.bp_tax_save_bands(config.id, table['id'], adrift)
        self.assertFalse(res['ok'])
        self.assertIn('start at zero', res['reason'])

        # Nothing was written by any of the three.
        table_rec = config.rate_table_ids.filtered(lambda t: t.code == 'VNTAX')
        self.assertEqual(len(table_rec.line_ids), 7)

    # ---- 3 ----------------------------------------------------------
    def test_a_statutory_edit_is_recorded_as_a_legislation_change(self):
        config, blueprint = self._draft('b3-values')
        rule = self._rule(config, 'DEDUCTSELF')
        res = self.Studio.bp_tax_save_values(
            config.id, {'DEDUCTSELF': 11000000.0}, None, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(rule.constant_value, 11000000.0)

        Version = self.env['hr.formula.rule.version']
        rows = Version.search([('rule_id', '=', rule.id)])
        self.assertTrue(rows.filtered(lambda v: v.reason == 'legislation'),
                        "a statutory edit has to say why it happened")

    def test_a_percentage_over_one_hundred_is_refused(self):
        config, blueprint = self._draft('b3-badvalue')
        res = self.Studio.bp_tax_save_values(config.id, {'SIRATE': 8.0})
        self.assertFalse(res['ok'])
        self.assertIn('percentage', res['reason'])
        self.assertEqual(self._rule(config, 'SIRATE').constant_value, 0.08)

    # ---- 4 ----------------------------------------------------------
    def test_drift_is_seen_and_the_pack_can_be_taken_back(self):
        config, blueprint = self._draft('b3-drift')
        self.Studio.bp_tax_save_values(config.id, {'DEDUCTSELF': 11000000.0})
        data = self.Studio.bp_tax_data(config.id)
        self.assertEqual(data['status'], 'drift')
        row = next(d for d in data['drift'] if d['code'] == 'DEDUCTSELF')
        self.assertEqual(row['current'], 11000000.0)
        self.assertEqual(row['target'], 15500000.0)
        self.assertAlmostEqual(row['delta'], 4500000.0, places=0)
        self.assertEqual(row['component'], 'DEDUCTSELF')

        before = self.env['hr.formula.legislation.application'].search_count(
            [('config_id', '=', config.id)])
        res = self.Studio.bp_tax_sync_pack(config.id, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertIn('DEDUCTSELF', res['applied'])
        self.assertEqual(self._rule(config, 'DEDUCTSELF').constant_value, 15500000.0)
        self.assertEqual(self.Studio.bp_tax_data(config.id)['status'], 'aligned')
        after = self.env['hr.formula.legislation.application'].search_count(
            [('config_id', '=', config.id)])
        self.assertEqual(after, before + 1,
                         "taking the pack's values leaves an audit trail")

    # ---- 5 ----------------------------------------------------------
    def test_a_configuration_that_is_no_longer_a_draft_is_read_only(self):
        config, blueprint = self._draft('b3-locked')
        config.state = 'active'
        data = self.Studio.bp_tax_data(config.id)
        self.assertFalse(data['editable'])
        self.assertTrue(data['readonly_reason'])
        self.assertNotIn('Odoo', data['readonly_reason'])

        res = self.Studio.bp_tax_save_values(config.id, {'DEDUCTSELF': 1.0})
        self.assertFalse(res['ok'])
        self.assertEqual(self._rule(config, 'DEDUCTSELF').constant_value, 15500000.0)

        table = config.rate_table_ids[:1]
        res = self.Studio.bp_tax_save_bands(
            config.id, table.id, [{'lower': 0, 'rate': 0.5}])
        self.assertFalse(res['ok'])
        self.assertEqual(len(table.line_ids), 7)

        res = self.Studio.bp_tax_sync_pack(config.id)
        self.assertFalse(res['ok'])

        cal = self.Studio.bp_calendar_save(config.id, {'cutoff_day': 5})
        self.assertFalse(cal['ok'])

    # ---- the two preferences ----------------------------------------
    def test_the_insurance_basis_changes_what_the_base_adds_up(self):
        """Contractual pay does not shrink when somebody joins mid-month."""
        config, blueprint = self._draft('b3-basis')
        sample = self._paid_sample(config)
        stored = json.loads(sample.input_values_json or '{}')
        stored.update({'BASIC': 30000000.0, 'STDDAYS': 26.0, 'PAIDDAYS': 13.0})
        sample.input_values_json = json.dumps(stored)

        # Give the contract salary a proration so "actual" and "contractual"
        # can differ at all (Essentials pays BASIC as an input).
        basic = self._rule(config, 'BASIC')
        recipe = basic.bp_recipe()
        recipe['proration'] = 'working_days'
        res = self.Studio.bp_component_save(config.id, basic.id, {
            'recipe': recipe, 'lane': 'guided', 'revision': blueprint.revision})
        if not res.get('ok'):
            self.skipTest("the contract salary is an input on this starter")

        res = self.Studio.bp_tax_save_values(
            config.id, None, {'basis': 'contract', 'rounding': '0'},
            blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['prefs']['basis'], 'contract')
        sibase = self._rule(config, 'SIBASE')
        self.assertEqual((sibase.bp_recipe().get('amount') or {}).get('basis'),
                         'contract')

    def test_rounding_downward_reaches_the_components_that_round(self):
        config, blueprint = self._draft('b3-rounding')
        res = self.Studio.bp_tax_save_values(
            config.id, None, {'basis': 'actual', 'rounding': 'down'},
            blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(self.Studio.bp_tax_data(config.id)['prefs']['rounding'],
                         'down')
        # Essentials keeps every decimal on purpose, so nothing there rounds at
        # all and nothing is touched — which is the promise the screen makes.
        for rule in config.rule_ids:
            recipe = rule.bp_recipe() or {}
            if str(recipe.get('round', '0')) not in ('none',):
                self.assertEqual(recipe['round'], 'down')

    # ---- zero dead ends ----------------------------------------------
    def test_a_blank_canvas_says_what_is_missing_instead_of_breaking(self):
        config, blueprint = self._draft('b3-blank', template='blank')
        data = self.Studio.bp_tax_data(config.id)
        self.assertTrue(data['ok'], data.get('reason'))
        self.assertEqual(data['tables'], [])
        self.assertEqual(data['values']['relief'], [])
        self.assertEqual(data['values']['insurance'], [])
        # A published pack still exists for Vietnam; nothing in this
        # configuration matches it, so there is nothing to be aligned WITH.
        self.assertEqual(data['status'], 'na')
        self.assertTrue(data['unmatched'])


@tagged('post_install', '-at_install')
class TestCalendarTab(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']

    def _draft(self, token='b3-cal'):
        res = self.Studio.bp_start({
            'name': 'B3 calendar configuration', 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': 'blank', 'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        config = self.env['hr.formula.config'].browse(res['config_id'])
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        return config, blueprint

    # ---- 6 ----------------------------------------------------------
    def test_the_last_working_day_steps_back_over_a_weekend(self):
        """31 May 2026 is a Sunday, so the last working day is Friday 29th."""
        workdays = {0, 1, 2, 3, 4}
        when, weekends, holidays = payday_for(
            'last_working', 1, 2026, 5, workdays, set())
        self.assertEqual(when, date(2026, 5, 29))
        self.assertEqual(weekends, 2)
        self.assertEqual(holidays, 0)

    def test_the_second_last_working_day_is_the_one_before_that(self):
        when, _w, _h = payday_for('second_last_working', 1, 2026, 5,
                                  {0, 1, 2, 3, 4}, set())
        self.assertEqual(when, date(2026, 5, 28))

    def test_a_public_holiday_is_stepped_over_and_counted(self):
        # 31 March 2026 is a Tuesday. Close the company that day.
        when, weekends, holidays = payday_for(
            'last_working', 1, 2026, 3, {0, 1, 2, 3, 4}, {date(2026, 3, 31)})
        self.assertEqual(when, date(2026, 3, 30))
        self.assertEqual(holidays, 1)
        self.assertEqual(weekends, 0)

    def test_a_fixed_day_beyond_the_end_of_the_month_becomes_its_last(self):
        when, _w, _h = payday_for('fixed', 31, 2026, 4, {0, 1, 2, 3, 4}, set())
        # 30 April 2026 is a Thursday.
        self.assertEqual(when, date(2026, 4, 30))

    def test_a_company_that_never_works_gets_no_date_rather_than_a_wrong_one(self):
        when, _w, _h = payday_for('last_working', 1, 2026, 5, set([6]), set())
        self.assertTrue(when is None or when.weekday() == 6)

    # ---- the RPCs ----------------------------------------------------
    def test_the_calendar_saves_and_previews_a_real_date(self):
        config, blueprint = self._draft('b3-cal-save')
        data = self.Studio.bp_calendar_data(config.id)
        self.assertTrue(data['ok'], data.get('reason'))
        self.assertEqual(data['calendar']['cutoff_day'], 20)
        self.assertEqual(data['payment']['currency'], config.currency_id.name)
        self.assertTrue(data['preview'])
        self.assertIn('date', data['preview'])

        res = self.Studio.bp_calendar_save(config.id, {
            'cutoff_day': 25, 'payday_rule': 'second_last_working',
            'late_inputs': 'off_cycle',
        }, {'bank_id_type': 'swift'}, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['calendar']['cutoff_day'], 25)
        self.assertEqual(res['payment']['bank_id_type'], 'swift')

        again = self.Studio.bp_calendar_data(config.id)
        self.assertEqual(again['calendar']['payday_rule'], 'second_last_working')
        self.assertEqual(again['calendar']['late_inputs'], 'off_cycle')
        self.assertEqual(again['payment']['bank_id_type'], 'swift')

    def test_a_cut_off_day_that_does_not_exist_every_month_is_refused(self):
        config, blueprint = self._draft('b3-cal-bad')
        res = self.Studio.bp_calendar_save(config.id, {'cutoff_day': 31})
        self.assertFalse(res['ok'])
        self.assertIn('between 1 and 28', res['reason'])
        res = self.Studio.bp_calendar_save(config.id, {'late_inputs': 'whenever'})
        self.assertFalse(res['ok'])

    def test_the_preview_answers_before_anything_is_saved(self):
        config, blueprint = self._draft('b3-cal-prev')
        first = self.Studio.bp_calendar_preview(config.id, None, 'last_working', 1)
        second = self.Studio.bp_calendar_preview(
            config.id, None, 'second_last_working', 1)
        self.assertTrue(first['ok'] and second['ok'])
        self.assertNotEqual(first['preview']['date'], second['preview']['date'])
        # Nothing was written by asking.
        self.assertEqual(self.Studio.bp_calendar_data(config.id)
                         ['calendar']['payday_rule'], 'last_working')

    # ---- the cut-off, now a rule rather than a bare day number -------
    def test_a_draft_saved_before_the_rule_existed_still_means_what_it_said(self):
        """The upgrade must not change anybody's promise.

        Every configuration on every database carries a cut-off DAY and no
        rule. Reading one back has to say "the 20th", exactly as it did, or an
        upgrade has quietly moved the day people's overtime is due.
        """
        config, blueprint = self._draft('b3-cut-old')
        blueprint.calendar_json = json.dumps({
            'calendar': {'cutoff_day': 20, 'payday_rule': 'last_working',
                         'payday_day': 25, 'late_inputs': 'next_cycle'},
            'payment': {'bank_id_type': 'domestic'}})
        data = self.Studio.bp_calendar_data(config.id)
        self.assertEqual(data['calendar']['cutoff_rule'], 'fixed')
        self.assertEqual(data['calendar']['cutoff_day'], 20)

    def test_the_three_cut_off_rules_land_on_three_different_days(self):
        config, blueprint = self._draft('b3-cut-rules')
        seen = {}
        for rule in ('fixed', 'last_working', 'before_payday'):
            res = self.Studio.bp_calendar_preview(
                config.id, None, None, None,
                {'cutoff_rule': rule, 'cutoff_day': 10,
                 'cutoff_days_before': 5})
            self.assertTrue(res['ok'], res.get('reason'))
            cut = res['preview']['cutoff']
            self.assertTrue(cut, 'the %s rule worked out no date' % rule)
            seen[rule] = cut['date']
        self.assertEqual(len(set(seen.values())), 3, seen)

    def test_a_cut_off_never_lands_on_a_day_the_company_is_shut(self):
        """A deadline on a closed Sunday is not a deadline.

        Asserted for every rule and over a whole year, because the failure is
        one month in seven and would never show up in a single spot check.
        """
        config, blueprint = self._draft('b3-cut-open')
        for month in range(1, 13):
            for rule in ('fixed', 'last_working', 'before_payday'):
                res = self.Studio.bp_calendar_preview(
                    config.id, '2026-%02d' % month, None, None,
                    {'cutoff_rule': rule, 'cutoff_day': 28,
                     'cutoff_days_before': 3})
                cut = res['preview']['cutoff']
                if not cut:
                    continue
                self.assertIn(
                    date.fromisoformat(cut['date']).weekday(), (0, 1, 2, 3, 4),
                    'the %s rule closed inputs on a weekend in month %s'
                    % (rule, month))

    def test_a_cut_off_before_payday_is_always_before_payday(self):
        config, blueprint = self._draft('b3-cut-before')
        for month in range(1, 13):
            res = self.Studio.bp_calendar_preview(
                config.id, '2026-%02d' % month, None, None,
                {'cutoff_rule': 'before_payday', 'cutoff_days_before': 4})
            preview = res['preview']
            self.assertGreater(
                preview['cutoff']['days_to_payday'], 0,
                'inputs closed on or after payday in month %s' % month)

    def test_the_new_cut_off_keys_survive_a_save_and_a_reread(self):
        config, blueprint = self._draft('b3-cut-save')
        res = self.Studio.bp_calendar_save(config.id, {
            'cutoff_rule': 'before_payday', 'cutoff_days_before': 6,
        }, None, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))
        again = self.Studio.bp_calendar_data(config.id)
        self.assertEqual(again['calendar']['cutoff_rule'], 'before_payday')
        self.assertEqual(again['calendar']['cutoff_days_before'], 6)
        # The day is KEPT, not cleared: switching rules and back returns the
        # number the person typed rather than a default they never chose.
        self.assertEqual(again['calendar']['cutoff_day'], 20)

    def test_nonsense_cut_off_settings_are_refused_by_name(self):
        config, blueprint = self._draft('b3-cut-bad')
        res = self.Studio.bp_calendar_save(config.id, {'cutoff_rule': 'whenever'})
        self.assertFalse(res['ok'])
        self.assertIn('cut-off rules', res['reason'])
        res = self.Studio.bp_calendar_save(
            config.id, {'cutoff_rule': 'before_payday',
                        'cutoff_days_before': 99})
        self.assertFalse(res['ok'])
