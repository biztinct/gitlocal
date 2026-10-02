# -*- coding: utf-8 -*-
"""The Excel-workbook starting point, driven all the way through.

B1 proved the return DOOR — the one line of ours in the chain — and could not
prove the journey through the review itself, because the review needs a Primary
Key Column that exists in every selected worksheet and this repository's only
payroll workbooks are templates with no usable employee-id column. B6 ships a
workbook that has one (`tools/gen_fixture_workbook.py` builds it) and drives the
whole review here, through the wizard's own methods, in the order the screen
presses them.

What this holds:

* a workbook chosen as the starting point creates an EMPTY draft, so nothing
  from a starter is mixed into somebody's own components;
* the review's seven states walk to the end without a person;
* the components arrive, with their Excel formulas, as `manual` rules — nothing
  the guided setup wrote, and the Components tab says so honestly;
* the last action of the import is the journey again, on the Pay rules step,
  carrying the draft.
"""
import base64
from pathlib import Path

from odoo.tests import TransactionCase, tagged

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'small_payroll.xlsx'

#: What the workbook says, and what each column becomes.
INPUT_HEADERS = ('Basic Salary', 'Allowance', 'Days Worked')
FORMULA_HEADERS = ('Gross Pay', 'Insurance', 'Net Pay')


@tagged('post_install', '-at_install')
class TestWorkbookRoundTrip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.Wizard = cls.env['hr.formula.multisheet.import.wizard']

    def _draft(self, token):
        res = self.Studio.bp_start({
            'name': 'B6 workbook %s' % token, 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': 'excel', 'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        return self.env['hr.formula.config'].browse(res['config_id'])

    def _run_review(self, config, key='Employee ID'):
        """Every press the review needs, in the order the screen makes them."""
        wizard = self.Wizard.with_context(
            pb_blueprint_return=True, pbfs_studio_import=True).create({
                'config_id': config.id,
                'import_file': base64.b64encode(FIXTURE.read_bytes()),
                'import_filename': 'small_payroll.xlsx',
                'primary_key_column': key,
            })
        wizard.action_analyze_file()
        self.assertEqual(wizard.state, 'select_sheets')
        self.assertEqual(len(wizard.available_sheet_ids), 1)
        wizard.action_process_sheets()
        self.assertEqual(wizard.state, 'select_columns')
        wizard.action_configure_order()
        wizard.action_process_with_resolution()
        self.assertEqual(wizard.state, 'review_components')
        wizard.action_detect_missing_fields()
        if wizard.state == 'map_missing':
            wizard.action_skip_missing()
        self.assertEqual(wizard.state, 'confirm')
        return wizard

    # ==================================================================
    def test_the_workbook_starting_point_creates_an_empty_draft(self):
        config = self._draft('b6-wb-empty')
        self.assertFalse(config.rule_ids,
                         "the workbook route seeds nothing — the workbook is "
                         "the starting point")
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)])
        self.assertEqual(blueprint.template_key, 'excel')
        self.assertTrue(config.sample_data_ids,
                        "the pay panel still has somebody in it")

    def test_the_review_reads_the_workbook_and_offers_its_columns(self):
        config = self._draft('b6-wb-review')
        wizard = self._run_review(config)
        headers = {c.original_header for c in wizard.component_preview_ids}
        for wanted in INPUT_HEADERS + FORMULA_HEADERS:
            self.assertIn(wanted, headers,
                          "the review did not offer “%s”" % wanted)
        kinds = {c.original_header: c.column_type
                 for c in wizard.component_preview_ids}
        for header in FORMULA_HEADERS:
            self.assertEqual(kinds[header], 'formula',
                             "“%s” is a calculation in the workbook" % header)
        for header in INPUT_HEADERS:
            self.assertEqual(kinds[header], 'input')

    def test_the_import_creates_the_components_and_returns_to_the_journey(self):
        config = self._draft('b6-wb-import')
        wizard = self._run_review(config)
        chosen = len(wizard.component_preview_ids.filtered('include_in_import'))
        self.assertTrue(chosen, "nothing was offered to import")

        result = wizard.action_execute_import()
        config.invalidate_recordset()
        self.assertEqual(len(config.rule_ids), chosen,
                         "every chosen column became a component")

        by_name = {r.name: r for r in config.rule_ids}
        gross = next((r for n, r in by_name.items() if n == 'Gross Pay'), None)
        self.assertTrue(gross, "the workbook's Gross Pay column is missing")
        self.assertEqual(gross.column_type, 'formula')
        self.assertTrue(gross.excel_formula,
                        "the calculation came across, not just the number")
        self.assertTrue(gross.python_formula,
                        "the engine can read what the workbook wrote")

        # Nothing here came from a sentence: an imported rule is somebody's own
        # Excel, and the Components tab has to say so rather than offering to
        # "restore" a guided version that never existed (B2 defect 8).
        for rule in config.rule_ids:
            self.assertEqual(rule.bp_formula_source or 'manual', 'manual')
            self.assertFalse(rule.bp_recipe_json or '',
                             "%s was given a rule nobody chose" % rule.code)

        # And the last thing the import does is open the journey again.
        chain = (result or {}).get('params', {}).get('next') or {}
        while chain.get('params', {}).get('next'):
            chain = chain['params']['next']
        found = self._find_journey(result)
        self.assertTrue(found, "the import did not come back to the journey")
        self.assertEqual(found.get('tag'), 'pb_blueprint')
        signal = dict(found.get('params') or {})
        signal.update(found.get('context') or {})
        self.assertEqual(signal.get('config_id'), config.id)

        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)])
        self.assertEqual(blueprint.step, 'rules',
                         "the return lands on Pay rules, with the components")

    def _find_journey(self, action, depth=0):
        """The journey action, wherever the chain buried it."""
        if not isinstance(action, dict) or depth > 6:
            return None
        if action.get('tag') == 'pb_blueprint':
            return action
        params = action.get('params') or {}
        for key in ('next', 'next_action'):
            found = self._find_journey(params.get(key), depth + 1)
            if found:
                return found
        return self._find_journey(action.get('next_action'), depth + 1)

    def test_a_workbook_import_leaves_the_components_tab_honest(self):
        """The imported rules must render — an imported workbook is the case
        with no recipes at all, and every summary line still has to say
        something true about each row."""
        config = self._draft('b6-wb-tab')
        wizard = self._run_review(config)
        wizard.action_execute_import()
        config.invalidate_recordset()

        res = self.Studio.bp_components(config.id)
        self.assertTrue(res['ok'])
        rows = [row for rows in res['groups'].values() for row in rows]
        self.assertEqual(len(rows), len(config.rule_ids))
        for row in rows:
            self.assertTrue(row['summary'], "%s says nothing" % row['code'])
            self.assertEqual(row['source'], 'manual')
