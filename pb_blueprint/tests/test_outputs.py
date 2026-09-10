# -*- coding: utf-8 -*-
"""Steps 4 and 5 — the outputs table, the inspector, the catalogue, the checks.

Everything here runs against a REAL draft created through the journey's own
`bp_start`, on the Vietnam · Complete starter where it is installed, because a
hand-built fixture would prove the shape of a payload and nothing about the
product. Where the starter is absent the test says so and skips rather than
asserting something weaker under the same name.
"""
import json
import re

from odoo.tests import TransactionCase, tagged

#: Excel functions the display form legitimately contains. Anything else that
#: looks like a bare column letter in a generated formula is the bug this
#: catches: a person reading `=A+H` cannot tell what they are being paid.
FUNCTIONS = {
    'IF', 'AND', 'OR', 'NOT', 'MIN', 'MAX', 'ROUND', 'ROUNDDOWN', 'ROUNDUP',
    'SUM', 'ABS', 'INT', 'BRACKET', 'IFERROR', 'TRUE', 'FALSE',
}


@tagged('post_install', '-at_install')
class TestOutputsAndTests(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.template = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_complete_2026')], limit=1)

    def _draft(self, token, key='vn_complete_2026'):
        res = self.Studio.bp_start({
            'name': 'B5 %s' % token, 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': key, 'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        return self.env['hr.formula.config'].browse(res['config_id'])

    def _complete(self, token):
        if not self.template:
            self.skipTest("the Vietnam · Complete starter is not installed")
        return self._draft(token)

    # ==================================================================
    # 1 — the table
    # ==================================================================
    def test_the_table_holds_every_component_and_leads_with_the_finals(self):
        config = self._complete('b5-outputs-1')
        every = self.Studio.bp_outputs(config.id, None, 'all')
        self.assertTrue(every['ok'])
        self.assertEqual(len(every['rows']), len(config.rule_ids),
                         "the table is missing components")

        final = self.Studio.bp_outputs(config.id)
        self.assertEqual(final['filter'], 'final',
                         "Final outputs is the view somebody lands on")
        codes = {r['code'] for r in final['rows']}
        for wanted in ('NET', 'PIT', 'GROSS', 'EEDED', 'ERCOST'):
            self.assertIn(wanted, codes,
                          "%s is not among the final outputs" % wanted)

        # The strip and the table are two views of one answer.
        self.assertEqual(
            every['strip']['inputs'],
            sum(1 for r in every['rows']
                if r['column_type'] in ('input', 'constant')))
        self.assertEqual(
            every['strip']['rules'],
            sum(1 for r in every['rows'] if r['column_type'] == 'formula'))
        self.assertEqual(every['counts']['all'], len(every['rows']))

    def test_a_generated_calculation_reads_in_codes_and_never_in_letters(self):
        """BP-R4 in the other direction: letters are what the engine stores and
        codes are what a person reads. A single bare letter left in the display
        form is a formula nobody can check."""
        config = self._complete('b5-outputs-2')
        rows = self.Studio.bp_outputs(config.id, None, 'all')['rows']
        codes = {r['code'] for r in rows}
        tables = {(t.code or '').upper() for t in config.rate_table_ids}
        checked = 0
        for row in rows:
            if row['column_type'] != 'formula' or row['source'] != 'generated':
                continue
            checked += 1
            for token in re.findall(r'[A-Za-z][A-Za-z0-9]*',
                                    row['excel_codes'] or ''):
                upper = token.upper()
                if upper in FUNCTIONS or upper in tables or upper in codes:
                    continue
                self.fail("%s reads %r, which names neither a component nor a "
                          "function" % (row['code'], token))
        self.assertGreater(checked, 10, "nothing generated was checked")

    def test_the_filters_cut_the_same_rows_they_count(self):
        config = self._complete('b5-outputs-3')
        every = self.Studio.bp_outputs(config.id, None, 'all')
        for key, count in every['counts'].items():
            rows = self.Studio.bp_outputs(config.id, None, key)['rows']
            self.assertEqual(len(rows), count,
                             "the %s chip counts %s and shows %s"
                             % (key, count, len(rows)))

    def test_search_reaches_the_name_the_code_and_the_calculation(self):
        config = self._complete('b5-outputs-4')
        hits = self.Studio.bp_outputs(config.id, None, 'all', 'tax')['rows']
        self.assertTrue(hits, "searching for tax found nothing")
        for row in hits:
            haystack = ' '.join([row['name'], row['code'],
                                 row['excel_codes'] or '']).lower()
            self.assertIn('tax', haystack)
        self.assertFalse(
            self.Studio.bp_outputs(config.id, None, 'all', 'zzzzz')['rows'])

    # ==================================================================
    # 2 — the inspector
    # ==================================================================
    def test_what_feeds_a_value_and_what_it_feeds(self):
        config = self._complete('b5-detail-1')
        rule = config.rule_ids.filtered(lambda r: r.code == 'SIDED')
        self.assertTrue(rule, "the starter has no social-insurance deduction")
        detail = self.Studio.bp_output_detail(config.id, rule.id)
        self.assertTrue(detail['ok'])

        feeds_from = {f['code'] for f in detail['feeds_from']}
        self.assertIn('SIBASE', feeds_from)
        self.assertIn('SIRATE', feeds_from)
        feeds_into = {f['code'] for f in detail['feeds_into']}
        self.assertIn('EEDED', feeds_into)

        # Every direct dependency carries the value it has for this sample —
        # a list of names with no numbers explains nothing.
        for row in detail['feeds_from']:
            self.assertIn('value', row)

    def test_the_chain_is_bounded_and_says_how_much_it_left_out(self):
        config = self._complete('b5-detail-2')
        rule = config.rule_ids.filtered(lambda r: r.code == 'NET')
        detail = self.Studio.bp_output_detail(config.id, rule.id)
        chain = detail['chain']['from']
        self.assertLessEqual(len(chain['nodes']), 60,
                             "the chain is not bounded")
        self.assertGreaterEqual(chain['more'], 0)
        # Take-home pay reaches most of the configuration, so the walk is real.
        self.assertGreater(len(chain['nodes']), 5)

    def test_the_trace_names_what_the_calculation_read(self):
        """The engine's own replay only finds SPREADSHEET references (`A1`),
        and a guided formula is stored without row numbers — so the reads fall
        back to the dependency edges. Either way the sentence is complete."""
        config = self._complete('b5-detail-3')
        rule = config.rule_ids.filtered(lambda r: r.code == 'SIDED')
        detail = self.Studio.bp_output_detail(config.id, rule.id)
        trace = detail['trace']
        self.assertTrue(trace['available'])
        self.assertTrue(trace['reads'], "the trace says it read nothing")
        self.assertIn('SIBASE', {r['code'] for r in trace['reads']})
        self.assertIsNotNone(trace['value'])

    def test_an_input_is_not_pretended_to_have_a_calculation(self):
        config = self._complete('b5-detail-4')
        rule = config.rule_ids.filtered(
            lambda r: r.code == 'BASIC' and r.column_type == 'input')
        detail = self.Studio.bp_output_detail(config.id, rule.id)
        self.assertTrue(detail['ok'])
        self.assertFalse(detail['feeds_from'])
        self.assertTrue(detail['feeds_into'])
        self.assertFalse(detail['trace']['available'])

    # ==================================================================
    # 3 — the catalogue
    # ==================================================================
    def test_the_catalogue_is_readable_json_with_everything_in_it(self):
        config = self._complete('b5-export-1')
        res = self.Studio.bp_export_catalog(config.id)
        self.assertTrue(res['ok'])
        self.assertTrue(res['filename'].endswith('.json'))
        payload = json.loads(res['content'])
        self.assertEqual(len(payload['components']), len(config.rule_ids))
        self.assertEqual(len(payload['rate_tables']), len(config.rate_table_ids))
        self.assertTrue(payload['rate_tables'][0]['brackets'])
        self.assertTrue(payload['samples'])
        self.assertNotIn('odoo', res['content'].lower())
        # Both forms of every formula, so the file can be read AND replayed.
        salary = next(c for c in payload['components']
                      if c['code'] == 'SALARYPAID')
        self.assertTrue(salary['excel_codes'])
        self.assertTrue(salary['excel_letters'])
        self.assertNotEqual(salary['excel_codes'], salary['excel_letters'])

    def test_a_blank_configuration_exports_without_an_error(self):
        config = self._draft('b5-export-2', key='blank')
        res = self.Studio.bp_export_catalog(config.id)
        self.assertTrue(res['ok'])
        payload = json.loads(res['content'])
        self.assertEqual(payload['rate_tables'], [])
        outputs = self.Studio.bp_outputs(config.id)
        self.assertTrue(outputs['ok'])

    # ==================================================================
    # 4 — evidence
    # ==================================================================
    def test_the_evidence_key_is_stable_until_something_moves(self):
        config = self._complete('b5-evidence-1')
        first = self.Studio.bp_evidence(config.id)['hash']
        self.assertEqual(first, self.Studio.bp_evidence(config.id)['hash'],
                         "the key changed without anything changing")

        # A name is not a number: renaming must not cry stale.
        rule = config.rule_ids.filtered(lambda r: r.code == 'PHONEALLOW')
        rule.name = 'Telephone allowance'
        self.assertEqual(first, self.Studio.bp_evidence(config.id)['hash'])

        # A fixed value is.
        constant = config.rule_ids.filtered(lambda r: r.code == 'DEDUCTSELF')
        constant.constant_value = (constant.constant_value or 0) + 1
        second = self.Studio.bp_evidence(config.id)['hash']
        self.assertNotEqual(first, second)

        # So is a formula.
        formula = config.rule_ids.filtered(lambda r: r.code == 'PHONEALLOW')
        formula.excel_formula = '=ROUND(400000,0)'
        third = self.Studio.bp_evidence(config.id)['hash']
        self.assertNotEqual(second, third)

        # And so is a tax band.
        table = config.rate_table_ids[:1]
        if table and table.line_ids:
            table.line_ids[-1].rate = (table.line_ids[-1].rate or 0) + 1
            self.assertNotEqual(third, self.Studio.bp_evidence(config.id)['hash'])

    def test_running_the_checks_stamps_what_they_ran_against(self):
        config = self._complete('b5-evidence-2')
        before = self.Studio.bp_evidence(config.id)
        self.assertFalse(before['ever_run'])
        self.assertFalse(before['stale'])

        after = self.Studio.bp_run_checks(config.id)
        self.assertTrue(after['ok'])
        evidence = after['evidence']
        self.assertTrue(evidence['ever_run'])
        self.assertFalse(evidence['stale'])
        self.assertEqual(evidence['hash'], evidence['tests_hash'])
        self.assertTrue(evidence['run_at'])
        self.assertTrue(evidence['run_by'])

        # Move a band afterwards and the evidence says so, unprompted.
        table = config.rate_table_ids[:1]
        table.line_ids[1].rate = (table.line_ids[1].rate or 0) + 2
        later = self.Studio.bp_evidence(config.id)
        self.assertTrue(later['stale'],
                        "a changed band left the evidence looking fresh")

    # ==================================================================
    # 5 — verdicts
    # ==================================================================
    def test_the_starters_own_scenarios_pass_and_say_which_they_are(self):
        config = self._complete('b5-verdict-1')
        res = self.Studio.bp_run_checks(config.id)
        self.assertTrue(res['ok'])
        self.assertTrue(res['samples'])
        for row in res['samples']:
            self.assertEqual(row['kind'], 'starter')
            self.assertEqual(row['verdict'], 'passed',
                             "%s: %s" % (row['name'], row['reason']))
        self.assertEqual(res['tally']['attention'], 0)
        self.assertEqual(res['tally']['pending'], 0)

    def test_a_wrong_expectation_is_named_with_both_numbers(self):
        config = self._complete('b5-verdict-2')
        sample = config.sample_data_ids[0]
        expected = json.loads(sample.expected_values_json or '{}')
        self.assertIn('PIT', expected)
        expected['PIT'] = float(expected['PIT'] or 0) + 7500.0
        sample.expected_values_json = json.dumps(expected)

        res = self.Studio.bp_run_checks(config.id)
        row = next(r for r in res['samples'] if r['id'] == sample.id)
        self.assertEqual(row['verdict'], 'attention')
        self.assertIn('expected', row['reason'])
        self.assertTrue(row['discrepancies'])
        codes = {d['code'] for d in row['discrepancies']}
        self.assertIn('PIT', codes)
        self.assertEqual(res['tally']['attention'], 1)

    def test_a_number_nobody_agreed_to_is_pending_and_never_passed(self):
        config = self._complete('b5-verdict-3')
        sample = config.sample_data_ids[0]
        sample.expected_confirmed = False

        res = self.Studio.bp_run_checks(config.id)
        row = next(r for r in res['samples'] if r['id'] == sample.id)
        self.assertEqual(row['verdict'], 'pending')
        self.assertNotEqual(row['verdict'], 'passed')
        self.assertIn('Confirm', row['reason'])

        after = self.Studio.bp_confirm_expected(config.id, [sample.id])
        self.assertTrue(after['ok'])
        row = next(r for r in after['samples'] if r['id'] == sample.id)
        self.assertEqual(row['verdict'], 'passed')

    def test_confirming_a_scenario_with_nothing_expected_snapshots_first(self):
        """The only way to say "yes, this is right" about a scenario that was
        never given expectations."""
        config = self._complete('b5-verdict-4')
        res = self.Studio.bp_add_sample(config.id)
        self.assertTrue(res['ok'])
        sample = self.env['hr.formula.sample.data'].browse(res['sample_id'])

        rows = self.Studio.bp_tests(config.id)['samples']
        row = next(r for r in rows if r['id'] == sample.id)
        self.assertEqual(row['verdict'], 'not_run')
        self.assertEqual(row['kind'], 'yours')

        self.Studio.bp_run_checks(config.id)
        after = self.Studio.bp_confirm_expected(config.id, [sample.id])
        self.assertTrue(after['ok'], after.get('reason'))
        row = next(r for r in after['samples'] if r['id'] == sample.id)
        self.assertEqual(row['verdict'], 'passed')
        self.assertTrue(sample.expected_confirmed)
        self.assertTrue(json.loads(sample.expected_values_json or '{}'))

    # ==================================================================
    # 6 — boundary cases
    # ==================================================================
    def test_the_picks_are_the_edges_this_configuration_actually_branches_on(self):
        config = self._complete('b5-bound-1')
        res = self.Studio.bp_boundary_picks(config.id)
        self.assertTrue(res['ok'])
        recommended = [p for p in res['picks'] if p['recommended']]
        labels = ' | '.join(p['label'] for p in recommended)
        inputs = {p['input_code'] for p in recommended}

        self.assertIn('PAIDDAYS', inputs, labels)
        self.assertIn('DEPS', inputs, labels)
        self.assertIn('CONTRACTMTH', inputs, labels)
        self.assertIn('BASIC', inputs, labels)
        edges = {round(p['edge'], 2) for p in recommended
                 if p['input_code'] == 'BASIC'}
        self.assertIn(46800000.0, edges, "the insurance ceiling is not offered")
        self.assertIn(99200000.0, edges, "the unemployment ceiling is not offered")
        self.assertIn(5000000.0, edges, "the withholding threshold is not offered")
        for pick in res['picks']:
            self.assertTrue(pick['label'])
            self.assertTrue(pick['why'])
            self.assertFalse(pick['exists'])

    def test_adding_a_pick_creates_three_rows_and_a_second_press_creates_none(self):
        config = self._complete('b5-bound-2')
        picks = self.Studio.bp_boundary_picks(config.id)['picks']
        chosen = next(p for p in picks if p['input_code'] == 'PAIDDAYS')

        before = len(config.sample_data_ids)
        res = self.Studio.bp_add_boundaries(config.id, [chosen['key']])
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['created'], 3, "an edge is three rows, not one")
        config.invalidate_recordset(['sample_data_ids'])
        self.assertEqual(len(config.sample_data_ids), before + 3)

        generated = config.sample_data_ids.filtered(
            lambda s: s.source_type == 'generated')
        self.assertEqual(len(generated), 3)
        for sample in generated:
            self.assertFalse(sample.expected_confirmed,
                             "a generated row must start as a hypothesis")

        rows = self.Studio.bp_tests(config.id)['samples']
        boundary = [r for r in rows if r['kind'] == 'boundary']
        self.assertEqual(len(boundary), 3)
        for row in boundary:
            self.assertEqual(row['verdict'], 'pending')

        again = self.Studio.bp_add_boundaries(config.id, [chosen['key']])
        self.assertTrue(again['ok'])
        self.assertEqual(again['created'], 0)
        self.assertEqual(again['skipped'], 3)

        marked = next(p for p in self.Studio.bp_boundary_picks(config.id)['picks']
                      if p['key'] == chosen['key'])
        self.assertTrue(marked['exists'],
                        "an edge already covered is still offered as new")

    def test_an_edge_nobody_offered_is_refused(self):
        """Rule 9: the server decides what may be generated, not the browser."""
        config = self._complete('b5-bound-3')
        before = len(config.sample_data_ids)
        res = self.Studio.bp_add_boundaries(config.id, ['BASIC@999999999'])
        self.assertFalse(res['ok'])
        config.invalidate_recordset(['sample_data_ids'])
        self.assertEqual(len(config.sample_data_ids), before)

    # ==================================================================
    # 7 — coverage
    # ==================================================================
    def test_coverage_agrees_with_the_engines_own_answer(self):
        config = self._complete('b5-cover-1')
        mine = self.Studio.bp_tests(config.id)['coverage']
        theirs = self.env['pb.formula.studio'].get_test_coverage(config.id)
        self.assertEqual(mine['asserted'], len(theirs['asserted']))
        self.assertEqual(mine['exercised'], len(theirs['exercised']))
        self.assertEqual(mine['untested_count'], len(theirs['untested']))
        self.assertEqual(mine['pct'], theirs['pct'])
        self.assertEqual(mine['total'], theirs['formula_total'])

    # ==================================================================
    # 8 — guards
    # ==================================================================
    def test_a_stale_revision_changes_nothing(self):
        config = self._complete('b5-guard-1')
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        stale = blueprint.revision - 1

        before = len(config.sample_data_ids)
        picks = self.Studio.bp_boundary_picks(config.id)['picks']
        res = self.Studio.bp_add_boundaries(
            config.id, [picks[0]['key']], stale)
        self.assertFalse(res['ok'])
        self.assertTrue(res.get('conflict'))
        config.invalidate_recordset(['sample_data_ids'])
        self.assertEqual(len(config.sample_data_ids), before)

        run = self.Studio.bp_run_checks(config.id, stale)
        self.assertFalse(run['ok'])
        self.assertTrue(run.get('conflict'))

    def test_a_configuration_that_does_not_exist_is_refused_in_words(self):
        for method in ('bp_outputs', 'bp_tests', 'bp_evidence',
                       'bp_boundary_picks', 'bp_export_catalog'):
            res = getattr(self.Studio, method)(9999999)
            self.assertFalse(res['ok'])
            self.assertIn('no longer exists', res['reason'])

    def test_nothing_to_check_is_said_rather_than_crashed(self):
        config = self._draft('b5-guard-2', key='blank')
        config.sample_data_ids.unlink()
        res = self.Studio.bp_tests(config.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['samples'], [])
        self.assertEqual(res['checks'], 0)
        run = self.Studio.bp_run_checks(config.id)
        self.assertFalse(run['ok'])
        self.assertIn('nothing to check', run['reason'].lower())
