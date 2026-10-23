# -*- coding: utf-8 -*-
"""A workbook's own calculations, opened in the guided setup.

Two promises, both broken on a live Rize Vietnam configuration on 2026-09-18
and both of a kind that is invisible until somebody is paid:

* **Opening a component and saving it must not change what the component IS.**
  A rule imported from a workbook has a calculation but no sentence, so the
  dialog opened on the blank default — "an approved amount", a number somebody
  types in. Saving without touching anything made that false description true,
  and every later "Refresh the rules" then reported
  ``This rule needs an input that does not exist yet: LUONGBAOHIIN`` — an entry
  column invented from the component's own code, which nothing had created.
  Three components on that configuration were relabelled this way in one
  sitting.

* **"Refresh the rules" must re-read the categories too.** It re-worked the
  arithmetic only. Naming the net-pay component — which can only be done
  outside the wizard — left every tab on the Pay rules step showing the stale
  reading, with no button anywhere that would refresh it. The workaround was to
  open an unrelated component and save it, which is what caused the first bug.
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestImportedExcelComponents(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.vn = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_standard_2026'), ('state', '!=', 'superseded')],
            limit=1)

    def _draft(self, token):
        if not self.vn:
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self.Studio.bp_start({
            'name': 'Imported-Excel test configuration',
            'country_code': 'VN',
            'cycle_type': 'regular',
            'template_key': 'vn_standard_2026',
            'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        config = self.env['hr.formula.config'].browse(res['config_id'])
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        return config, blueprint

    def _imported(self, config, code='IMPORTEDCMP'):
        """A component exactly as a workbook import leaves one: a formula of its
        own, no sentence, nothing generated."""
        res = self.env['pb.formula.studio'].add_component(config.id, {
            'name': 'Imported component', 'code': code, 'column_type': 'formula',
        })
        rule = self.env['hr.formula.rule'].browse(res.get('rule_id') or 0)
        self.assertTrue(rule.exists(), res)
        basic = config.rule_ids.filtered(
            lambda r: (r.code or '').upper() == 'BASIC')[:1]
        self.assertTrue(basic, "the pack must have a BASIC component")
        rule.write({
            'excel_formula': '=%s2*0.1' % basic.column_letter,
            'bp_recipe_json': False,
            'bp_generated_formula': False,
            'bp_formula_source': 'manual',
        })
        return rule

    # ---- 1 ----------------------------------------------------------
    def test_01_opening_an_imported_component_does_not_call_it_a_typed_amount(self):
        """The dialog must open describing what the component actually is."""
        config, _bp = self._draft('imp-open')
        rule = self._imported(config)

        opened = self.Studio.bp_component_get(rule.id)
        self.assertTrue(opened['ok'], opened.get('reason'))
        self.assertFalse(opened['has_recipe'])
        self.assertEqual(
            (opened['recipe'].get('amount') or {}).get('kind'), 'manual',
            "an imported workbook formula is 'written as Excel', never 'an "
            "approved amount'")

    # ---- 2 ----------------------------------------------------------
    def test_02_a_component_with_no_formula_still_opens_on_the_blank_default(self):
        """The fix is scoped to components that carry their own calculation; a
        brand-new empty one must still start where it always did."""
        config, _bp = self._draft('imp-blank')
        res = self.env['pb.formula.studio'].add_component(config.id, {
            'name': 'Fresh', 'code': 'FRESHCMP', 'column_type': 'formula'})
        rule = self.env['hr.formula.rule'].browse(res.get('rule_id') or 0)
        rule.write({'excel_formula': '', 'bp_recipe_json': False})

        opened = self.Studio.bp_component_get(rule.id)
        self.assertEqual(
            (opened['recipe'].get('amount') or {}).get('kind'), 'input')

    # ---- 3 ----------------------------------------------------------
    def test_03_saving_from_the_excel_tab_leaves_the_calculation_alone(self):
        """The Excel tab says "nothing will rewrite it". The stored sentence has
        to say the same, whatever the Guided tab was showing when it opened."""
        config, blueprint = self._draft('imp-save')
        rule = self._imported(config)
        before = rule.excel_formula

        # The dialog posts back the sentence it was handed. Simulate the worst
        # case: the blank guided default, the exact payload that broke Rize.
        saved = self.Studio.bp_component_save(config.id, rule.id, {
            'name': rule.name, 'lane': 'excel',
            'excel_codes': '=BASIC*0.1',
            'recipe': {'v': 1, 'group': 'earning', 'audience': 'all',
                       'amount': {'kind': 'input'}, 'proration': 'none',
                       'frequency': 'monthly', 'sign': 1, 'round': '0'},
            'revision': blueprint.revision})
        self.assertTrue(saved['ok'], saved.get('reason'))

        rule.invalidate_recordset()
        stored = json.loads(rule.bp_recipe_json or '{}')
        self.assertEqual((stored.get('amount') or {}).get('kind'), 'manual')
        self.assertEqual(rule.bp_formula_source, 'manual')
        self.assertTrue(rule.excel_formula, "the calculation must survive")
        self.assertEqual(rule._normalize_excel_formula(rule.excel_formula),
                         rule._normalize_excel_formula(before))

    # ---- 4 ----------------------------------------------------------
    def test_04_saving_it_leaves_nothing_for_refresh_to_complain_about(self):
        """The symptom the owner actually saw: save succeeds, then every later
        refresh reports a missing input."""
        config, blueprint = self._draft('imp-quiet')
        rule = self._imported(config)

        saved = self.Studio.bp_component_save(config.id, rule.id, {
            'name': rule.name, 'lane': 'excel',
            'excel_codes': '=BASIC*0.1',
            'recipe': {'v': 1, 'group': 'earning', 'audience': 'all',
                       'amount': {'kind': 'input'}, 'proration': 'none',
                       'frequency': 'monthly', 'sign': 1, 'round': '0'},
            'revision': blueprint.revision})
        self.assertTrue(saved['ok'], saved.get('reason'))
        self._assert_no_problem_about(saved['problems'], rule.code)

        blueprint.invalidate_recordset()
        again = self.Studio.bp_regenerate(config.id, blueprint.revision)
        self.assertTrue(again['ok'], again.get('reason'))
        self._assert_no_problem_about(again['problems'], rule.code)

    def _assert_no_problem_about(self, problems, code):
        mine = [p for p in (problems or [])
                if (p.get('code') or '').upper() == (code or '').upper()]
        self.assertFalse(mine, "unexpected complaint: %s" % mine)

    # ---- 5 ----------------------------------------------------------
    def test_05_refresh_the_rules_re_reads_the_categories(self):
        """Name the net-pay component behind the wizard's back, press Refresh,
        and the reading must be up to date — with no other button pressed."""
        config, blueprint = self._draft('imp-refresh')
        net = config.rule_ids.filtered(
            lambda r: (r.code or '').upper() == 'NET')[:1]
        self.assertTrue(net, "the pack must have a NET component")

        # Break the reading the way a stale configuration is broken: no
        # component claims to be net pay, so nothing can be classified.
        config.rule_ids.write({'net_role': False})
        net_category = net.category_id
        net.write({'category_id': False, 'code': 'TAKEHOME'})
        config.invalidate_recordset()
        self.assertFalse(
            any(r.net_role == 'net' for r in config.rule_ids),
            "the reading must actually be stale before the refresh")

        # Put the answer back, the way the grid does — outside the wizard.
        net.write({'category_id': net_category.id})

        blueprint.invalidate_recordset()
        res = self.Studio.bp_regenerate(config.id, blueprint.revision)
        self.assertTrue(res['ok'], res.get('reason'))

        config.invalidate_recordset()
        roles = [r.net_role for r in config.rule_ids]
        self.assertIn('net', roles,
                      "Refresh the rules must re-read what each component does "
                      "to net pay, not only the arithmetic")
        self.assertIn('deduction', roles,
                      "a Vietnam pack with no deductions means the walk never ran")
