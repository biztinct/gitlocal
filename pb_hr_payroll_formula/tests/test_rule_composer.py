# -*- coding: utf-8 -*-
"""Integrations Cycle 8 — a transformation rule is a sentence, and it computes.

Every assertion here is an assertion of a NUMBER, never of a shape. That is
W137's lesson, learned on this exact model: `_execute_for_records` wraps each
rule in `except Exception` and writes `default_value`, so a broken rule does
not raise — it answers `0.0`, which is a perfectly well-shaped float. A test
that asserted "no exception" passed for four cycles while every python rule on
every database returned its default.

The suites, in the order the handover numbers them:

  1  the guided engine — every operator, both joins, the nested source, each
     unit conversion, and the legacy leniency for malformed values;
  2  PARITY — all eight ABM rules, legacy path == guided path, on fixtures
     that reproduce the real payload shapes (rejected overtime rows, dependants
     with no PIT number, an "H:MM" that is not one). This suite ships and is
     green BEFORE the migration flips anything;
  3  the Excel lane — bracket refs, the function set, the hardening;
  5  `last_error` — written on failure, cleared on the next success;
  6  preview == execution — the traced twin and the engine, same numbers;
  7  the assistant — a proposal naming a field that does not exist is rejected
     WHOLE, and the deterministic floor answers with `source='deterministic'`.

(4 and 8 are the RPC gates and the composer's behaviour; they live in
`pb_integrations/tests/test_rule_composer_rpc.py` and the JS suite, because
that is where the code they guard lives.)
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.formula_engine import rule_formula
from odoo.addons.pb_hr_payroll_formula.formula_engine.excel_semantics import (
    UnsafeFormulaError,
)
from odoo.addons.pb_hr_payroll_formula.models.api_transformation_rule import (
    plain_summary_for,
)

# The six overtime bands, as the legacy application computed them.
OT_BANDS = ('150%', '200%', '210%', '270%', '300%', '390%')

# One overtime payload that exercises every way a row can be excluded: the
# wrong band, an unapproved request, a missing hour count and an hour count
# that is not a number at all.
OT_ROWS = [
    {'OT_Type': '150%', 'ApprovalStatus': 'Approved', 'Actual_Pay_Hour': 4},
    {'OT_Type': '150%', 'ApprovalStatus': 'Approved', 'Actual_Pay_Hour': '2.5'},
    {'OT_Type': '150%', 'ApprovalStatus': 'Rejected', 'Actual_Pay_Hour': 8},
    {'OT_Type': '150%', 'ApprovalStatus': 'Pending', 'Actual_Pay_Hour': 16},
    {'OT_Type': '200%', 'ApprovalStatus': 'Approved', 'Actual_Pay_Hour': 3},
    {'OT_Type': '300%', 'ApprovalStatus': 'Approved', 'Actual_Pay_Hour': 1.25},
    {'OT_Type': '150%', 'ApprovalStatus': 'Approved', 'Actual_Pay_Hour': None},
    {'OT_Type': '150%', 'ApprovalStatus': 'Approved', 'Actual_Pay_Hour': 'n/a'},
    {'OT_Type': '390%', 'ApprovalStatus': 'Approved'},
]

DEPENDANTS = [
    {'Dependent_Name': 'A', 'Dependent_PIT_Number': '8001'},
    {'Dependent_Name': 'B', 'Dependent_PIT_Number': ''},
    {'Dependent_Name': 'C', 'Dependent_PIT_Number': '8003'},
    {'Dependent_Name': 'D'},
]

# `totalWorkedHours` is an integer count of SECONDS despite its name;
# `paidLeaveHours` is an "H:MM" string. Row 3 is malformed in both halves and
# must contribute exactly nothing while the rest of the month still counts.
ATTENDANCE_ROWS = [
    {'totalWorkedHours': 28800, 'paidLeaveHours': '1:30'},   # 8 + 1.5
    {'totalWorkedHours': '3600', 'paidLeaveHours': ''},      # 1
    {'totalWorkedHours': 'absent', 'paidLeaveHours': 'x:y'},  # 0
    {'totalWorkedHours': 1800, 'paidLeaveHours': '0:30'},    # 0.5 + 0.5
]
ATTENDANCE_TOTAL = 8 + 1.5 + 1 + 0.5 + 0.5


@tagged('post_install', '-at_install')
class TestRuleComposer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Store = cls.env['hr.api.data.store']
        cls.Rule = cls.env['hr.api.transformation.rule']

    # ------------------------------------------------------------ fixtures
    def _connector(self, name='IG-C8'):
        return self.Connector.create({'name': name, 'connector_type': 'zoho'})

    def _store(self, conn, data_type, payload, ext_id='IGC8-1'):
        return self.Store.create({
            'connector_id': conn.id, 'data_type': data_type,
            'employee_external_id': ext_id, 'raw_payload': payload,
            'extracted_data': payload, 'state': 'extracted',
        })

    def _rows(self, conn, data_type, payloads):
        recs = self.Store.browse()
        for payload in payloads:
            recs |= self._store(conn, data_type, payload)
        return recs

    def _rule(self, conn, **vals):
        base = {'connector_id': conn.id, 'name': 'R', 'output_key': 'RKEY',
                'rule_type': 'count', 'source_data_type': 'custom',
                'builder_mode': 'guided'}
        base.update(vals)
        return self.Rule.create(base)

    # ==================================================================== 1
    def test_01_every_operator_answers_a_number(self):
        """All nine comparisons, on typical AND edge values.

        The edge that matters is the LAST pair: `"9" > "10"` is True as text
        and False as a number, and a payload delivers both sides as text.
        """
        conn = self._connector()
        rows = self._rows(conn, 'custom', [
            {'band': '150%', 'state': 'Approved', 'hours': 4, 'note': 'night shift'},
            {'band': '200%', 'state': 'Approved', 'hours': '9', 'note': ''},
            {'band': '150%', 'state': 'Rejected', 'hours': '10'},
        ])
        cases = [
            ({'field': 'band', 'op': 'is', 'value': '150%'}, 2),
            ({'field': 'band', 'op': 'is_not', 'value': '150%'}, 1),
            ({'field': 'note', 'op': 'contains', 'value': 'NIGHT'}, 1),
            ({'field': 'note', 'op': 'present'}, 1),
            ({'field': 'note', 'op': 'blank'}, 2),
            ({'field': 'hours', 'op': 'gt', 'value': '9'}, 1),
            ({'field': 'hours', 'op': 'gte', 'value': '9'}, 2),
            ({'field': 'hours', 'op': 'lt', 'value': '9'}, 1),
            ({'field': 'hours', 'op': 'lte', 'value': '9'}, 2),
        ]
        for condition, expected in cases:
            rule = self._rule(conn, rule_type='count', filter_conditions={
                'join': 'all', 'rows': [condition]})
            self.assertEqual(
                rule._execute_single({'custom': rows}, rows[0]), float(expected),
                "%s %s matched the wrong rows" % (condition['field'], condition['op']))

    def test_01b_all_and_any_are_different_questions(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', [
            {'band': '150%', 'state': 'Approved'},
            {'band': '150%', 'state': 'Rejected'},
            {'band': '200%', 'state': 'Approved'},
        ])
        both = [{'field': 'band', 'op': 'is', 'value': '150%'},
                {'field': 'state', 'op': 'is', 'value': 'Approved'}]
        self.assertEqual(
            self._rule(conn, filter_conditions={'join': 'all', 'rows': both})
                ._execute_single({'custom': rows}, rows[0]), 1.0)
        self.assertEqual(
            self._rule(conn, filter_conditions={'join': 'any', 'rows': both})
                ._execute_single({'custom': rows}, rows[0]), 3.0)
        # No conditions keeps everything — an empty filter is not a filter.
        self.assertEqual(
            self._rule(conn, filter_conditions={'join': 'all', 'rows': []})
                ._execute_single({'custom': rows}, rows[0]), 3.0)

    def test_01c_each_unit_converts_and_a_bad_value_is_skipped(self):
        """Every `contains` conversion, and the assertion the efbb64b5 lesson
        demands: the answer is a NUMBER, and it is not zero."""
        conn = self._connector()
        rows = self._rows(conn, 'custom', [
            {'secs': 3600, 'hm': '1:30', 'mins': 90, 'days': 2, 'num': '1.5'},
            {'secs': 'x', 'hm': 'x:y', 'mins': None, 'days': 'x', 'num': 'x'},
        ])
        expected = {'secs': ('seconds', 1.0), 'hm': ('hmm', 1.5),
                    'mins': ('minutes', 1.5), 'days': ('days', 2.0),
                    'num': ('number', 1.5)}
        for field, (unit, want) in expected.items():
            rule = self._rule(conn, rule_type='sum',
                              value_steps=[{'field': field, 'contains': unit}])
            got = rule._execute_single({'custom': rows}, rows[0])
            self.assertEqual(got, want, "%s as %s" % (field, unit))
            self.assertNotEqual(got, 0.0, "a skipped bad value must not zero the sum")

    def test_01d_two_steps_inside_one_record_are_added(self):
        """The shape no single-field aggregate can express, and the reason
        WORKEDHRS was a python program."""
        conn = self._connector()
        rows = self._rows(conn, 'attendance', ATTENDANCE_ROWS)
        rule = self._rule(conn, rule_type='sum', source_data_type='attendance',
                          value_steps=[{'field': 'totalWorkedHours', 'contains': 'seconds'},
                                       {'field': 'paidLeaveHours', 'contains': 'hmm'}])
        self.assertEqual(rule._execute_single({'attendance': rows}, rows[0]),
                         ATTENDANCE_TOTAL)

    def test_01e_the_nested_source_walks_into_the_record(self):
        conn = self._connector()
        emp = self._store(conn, 'employee', {
            'EmployeeID': 'E1',
            'tabularSections': {'Dependent and Dependent Health Insurance': DEPENDANTS},
        })
        rule = self._rule(
            conn, rule_type='count', source_data_type='employee',
            record_source='nested',
            nested_table_path='tabularSections.Dependent and Dependent Health Insurance',
            filter_conditions={'join': 'all', 'rows': [
                {'field': 'Dependent_PIT_Number', 'op': 'present'}]})
        self.assertEqual(rule._execute_single({'employee': emp}, emp), 2.0,
                         "only the dependants carrying a PIT number are counted")
        # And the assertion that justifies the whole `nested` source: counting
        # RECORDS answers 1 for an employee with four dependants.
        flat = self._rule(conn, rule_type='count', source_data_type='employee')
        self.assertEqual(flat._execute_single({'employee': emp}, emp), 1.0)

    def test_01f_a_table_path_containing_a_dot_is_tried_whole_first(self):
        conn = self._connector()
        emp = self._store(conn, 'employee', {'Dep.Rows': [{'x': 1}, {'x': 2}]})
        rule = self._rule(conn, rule_type='count', source_data_type='employee',
                          record_source='nested', nested_table_path='Dep.Rows')
        self.assertEqual(rule._execute_single({'employee': emp}, emp), 2.0)

    def test_01g_min_max_and_average_over_records(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', [{'v': 4}, {'v': '2'}, {'v': 'x'}, {'v': 9}])
        steps = [{'field': 'v', 'contains': 'number'}]
        self.assertEqual(self._rule(conn, rule_type='min', value_steps=steps)
                         ._execute_single({'custom': rows}, rows[0]), 2.0)
        self.assertEqual(self._rule(conn, rule_type='max', value_steps=steps)
                         ._execute_single({'custom': rows}, rows[0]), 9.0)
        self.assertEqual(self._rule(conn, rule_type='avg', value_steps=steps)
                         ._execute_single({'custom': rows}, rows[0]), 5.0,
                         "the unreadable value is SKIPPED, not counted as a 0")

    def test_01h_nothing_matching_returns_the_rule_s_own_default(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', [{'v': 1}])
        rule = self._rule(conn, rule_type='sum', default_value=-1.0,
                          value_steps=[{'field': 'ghost', 'contains': 'number'}])
        self.assertEqual(rule._execute_single({'custom': rows}, rows[0]), -1.0)

    # ==================================================================== 2
    #
    # PARITY. Each case builds the LEGACY rule exactly as the shipped catalogue
    # spells it and the GUIDED rule the migration will produce, runs both over
    # the same store rows, and asserts the two numbers are equal AND correct.
    # An equality alone would pass if both were broken.

    def _legacy_ot(self, conn, band):
        return self._rule(
            conn, builder_mode='python', rule_type='sum',
            output_key='OTHRS%s' % band.rstrip('%'),
            aggregate_field='Actual_Pay_Hour',
            filter_expression=(
                "rec.get('OT_Type') == '%s' and "
                "rec.get('ApprovalStatus') == 'Approved'" % band))

    def _guided_ot(self, conn, band):
        return self._rule(
            conn, builder_mode='guided', rule_type='sum',
            output_key='GOTHRS%s' % band.rstrip('%'),
            filter_conditions={'join': 'all', 'rows': [
                {'field': 'OT_Type', 'op': 'is', 'value': band},
                {'field': 'ApprovalStatus', 'op': 'is', 'value': 'Approved'}]},
            value_steps=[{'field': 'Actual_Pay_Hour', 'contains': 'number'}])

    def test_02_the_six_overtime_bands_are_identical_before_and_after(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', OT_ROWS)
        expected = {'150%': 6.5, '200%': 3.0, '210%': 0.0,
                    '270%': 0.0, '300%': 1.25, '390%': 0.0}
        for band in OT_BANDS:
            legacy = self._legacy_ot(conn, band)._execute_single({'custom': rows}, rows[0])
            guided = self._guided_ot(conn, band)._execute_single({'custom': rows}, rows[0])
            self.assertEqual(legacy, guided, "band %s diverged" % band)
            self.assertEqual(guided, expected[band],
                             "band %s is not the number the legacy computed" % band)

    def test_02b_depcount_is_identical_before_and_after(self):
        conn = self._connector()
        emp = self._store(conn, 'employee', {
            'EmployeeID': 'E1',
            'tabularSections': {'Dependent and Dependent Health Insurance': DEPENDANTS},
        })
        legacy = self._rule(
            conn, builder_mode='python', rule_type='python',
            output_key='DEPCOUNT', source_data_type='employee',
            python_code="deps = 0\n"
                        "for r in records:\n"
                        "    rows = (r.get('tabularSections') or {}).get("
                        "'Dependent and Dependent Health Insurance') or []\n"
                        "    for d in rows:\n"
                        "        if d.get('Dependent_PIT_Number'):\n"
                        "            deps = deps + 1\n"
                        "result = deps\n")
        guided = self._rule(
            conn, builder_mode='guided', rule_type='count',
            output_key='GDEPCOUNT', source_data_type='employee',
            record_source='nested',
            nested_table_path='tabularSections.Dependent and Dependent Health Insurance',
            filter_conditions={'join': 'all', 'rows': [
                {'field': 'Dependent_PIT_Number', 'op': 'present'}]})
        self.assertEqual(legacy._execute_single({'employee': emp}, emp), 2)
        self.assertEqual(guided._execute_single({'employee': emp}, emp), 2.0)

    def test_02c_workedhrs_is_identical_before_and_after(self):
        conn = self._connector()
        rows = self._rows(conn, 'attendance', ATTENDANCE_ROWS)
        legacy = self._rule(
            conn, builder_mode='python', rule_type='python',
            output_key='WORKEDHRS', source_data_type='attendance',
            python_code="total = 0.0\n"
                        "for r in records:\n"
                        "    worked = str(r.get('totalWorkedHours') or 0).strip()\n"
                        "    secs = float(worked) if worked.replace('.', '', 1)"
                        ".isdigit() else 0.0\n"
                        "    parts = str(r.get('paidLeaveHours') or '').split(':')\n"
                        "    if len(parts) == 2 and parts[0].strip().isdigit() "
                        "and parts[1].strip().isdigit():\n"
                        "        secs = secs + int(parts[0].strip()) * 3600 + "
                        "int(parts[1].strip()) * 60\n"
                        "    total = total + secs / 3600.0\n"
                        "result = total\n")
        guided = self._rule(
            conn, builder_mode='guided', rule_type='sum',
            output_key='GWORKEDHRS', source_data_type='attendance',
            value_steps=[{'field': 'totalWorkedHours', 'contains': 'seconds'},
                         {'field': 'paidLeaveHours', 'contains': 'hmm'}])
        legacy_value = legacy._execute_single({'attendance': rows}, rows[0])
        guided_value = guided._execute_single({'attendance': rows}, rows[0])
        self.assertEqual(legacy_value, guided_value)
        self.assertEqual(guided_value, ATTENDANCE_TOTAL)
        self.assertNotEqual(guided_value, 0.0)

    def test_02d_the_excel_lane_reaches_the_same_number(self):
        """The third column of the parity table: WORKEDHRS as a formula."""
        conn = self._connector()
        rows = self._rows(conn, 'attendance', ATTENDANCE_ROWS)
        excel = self._rule(
            conn, builder_mode='excel', rule_type='sum',
            output_key='XWORKEDHRS', source_data_type='attendance',
            excel_formula='[totalWorkedHours]/3600 + HOURS([paidLeaveHours])')
        self.assertEqual(excel._execute_single({'attendance': rows}, rows[0]),
                         ATTENDANCE_TOTAL)

    # ==================================================================== 3
    def test_03_bracket_refs_resolve_exactly_then_leniently(self):
        row = {'Actual_Pay_Hour': '2.5', 'OT Type': '150%', 'n': 12}
        for text, want in (('[Actual_Pay_Hour]*2', 5.0),
                           ('[actual pay hour]*2', 5.0),
                           ('[n]+1', 13.0),
                           ('[missing]+1', 1.0)):
            code, refs = rule_formula.compile_rule_formula(text)
            self.assertEqual(rule_formula.eval_rule_formula(code, refs, row), want, text)

    def test_03b_an_unknown_reference_is_refused_at_compile_time(self):
        with self.assertRaises(rule_formula.RuleFormulaError):
            rule_formula.compile_rule_formula('[ghost]+1', known_paths=['real'])
        # and the same name, spelled differently, is accepted
        rule_formula.compile_rule_formula('[o t type]', known_paths=['OT_Type'])

    def test_03c_every_supported_function_runs_through_the_rule_path(self):
        row = {'a': '10', 'b': '3', 'hm': '7:30', 'blank': ''}
        cases = {
            'SUM([a],[b])': 13.0, 'MIN([a],[b])': 3.0, 'MAX([a],[b])': 10.0,
            'AVERAGE([a],[b])': 6.5, 'COUNT([a],[b],[blank])': 2.0,
            'ROUND(2.5,0)': 3.0, 'ROUNDUP(1.2,1)': 1.2, 'ROUNDDOWN(-1.8,0)': -1.0,
            'CEILING(147,100)': 200.0, 'FLOOR(147,100)': 100.0,
            'ABS(0-[b])': 3.0, 'INT(2.9)': 2.0,
            'IF([a]>[b],1,2)': 1.0, 'IFERROR(1/0,-1)': -1.0,
            'NOT(ISBLANK([blank]))': 0.0, 'AND([a],[b])': 1.0, 'OR([blank],[a])': 1.0,
            'EXACT([a],"10")': 1.0, 'ISBLANK([blank])': 1.0,
            'HOURS([hm])': 7.5, 'MINUTES(90)': 1.5, 'SECONDS(3600)': 1.0,
            'NUMBER("1.234,50")': 1234.5,
        }
        for text, want in cases.items():
            code, refs = rule_formula.compile_rule_formula(text)
            self.assertEqual(rule_formula.eval_rule_formula(code, refs, row), want, text)
        self.assertEqual(len(cases), len(rule_formula.SUPPORTED_FUNCTIONS),
                         "every supported function needs a case in this test")

    def test_03d_the_hardening_refuses_what_it_exists_to_refuse(self):
        for text in ("__import__('os')", 'env.cr.execute("x")', 'self.sudo()',
                     'lambda: 1', '(1).__class__', 'FOO([a])', '1 & 2',
                     '[a', 'bareword+1', 'IF(1)', ''):
            with self.assertRaises((rule_formula.RuleFormulaError, UnsafeFormulaError),
                                   msg='%r was not refused' % text):
                rule_formula.compile_rule_formula(text)

    def test_03e_if_does_not_evaluate_the_branch_it_did_not_choose(self):
        """Eager branches would make this raise and drop the row — a wrong
        answer that looks exactly like a right one."""
        code, refs = rule_formula.compile_rule_formula(
            'IF([h]=0, 0, 100/[h])')
        self.assertEqual(rule_formula.eval_rule_formula(code, refs, {'h': 0}), 0.0)
        self.assertEqual(rule_formula.eval_rule_formula(code, refs, {'h': 4}), 25.0)

    def test_03f_a_broken_formula_surfaces_as_a_rule_error_not_a_zero(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', [{'v': 1}])
        rule = self._rule(conn, builder_mode='excel', rule_type='sum',
                          excel_formula='[v] + NOPE([v])')
        with self.assertRaises(rule_formula.RuleFormulaError):
            rule._execute_single({'custom': rows}, rows[0])

    # ==================================================================== 5
    def test_05_a_failure_is_written_down_and_a_success_clears_it(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', [{'v': 1}])
        rule = self._rule(conn, builder_mode='excel', rule_type='sum',
                          output_key='BROKEN', excel_formula='NOPE([v])')

        rule._execute_for_records(rows)
        self.assertTrue(rule.last_error, "the failure must be recorded on the rule")
        self.assertTrue(rule.last_error_at)
        self.assertEqual(rows[0].computed_data.get('BROKEN'), rule.default_value,
                         "and the value still falls back, as it always did")

        rule.write({'excel_formula': '[v]'})
        rule._execute_for_records(rows)
        self.assertFalse(rule.last_error, "a success clears the flag")
        self.assertFalse(rule.last_error_at)
        self.assertEqual(rows[0].computed_data.get('BROKEN'), 1.0)

    # ==================================================================== 6
    def test_06_the_traced_twin_and_the_engine_are_the_same_code(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', OT_ROWS)
        rule = self._guided_ot(conn, '150%')

        executed = rule._execute_single({'custom': rows}, rows[0])
        trace = rule.preview_on_records([r.extracted_data for r in rows], rows[0])

        self.assertEqual(trace['result'], executed,
                         "preview and execution must be one code path")
        self.assertEqual(trace['records_in'], len(OT_ROWS))
        self.assertEqual(trace['matched'], 4,
                         "four rows are approved 150%, two of them unreadable")
        self.assertEqual(trace['valued'], 2)
        self.assertEqual(len([r for r in trace['rows'] if r['kept']]), 4)

    def test_06b_the_trace_carries_only_the_fields_the_rule_mentions(self):
        conn = self._connector()
        rows = self._rows(conn, 'custom', [dict(OT_ROWS[0], noise='x' * 200)])
        trace = self._guided_ot(conn, '150%').preview_on_records(
            [r.extracted_data for r in rows], rows[0])
        keys = {c['k'] for c in trace['rows'][0]['cells']}
        self.assertEqual(keys, {'OT_Type', 'ApprovalStatus', 'Actual_Pay_Hour'})

    def test_06c_a_draft_can_be_previewed_without_ever_being_saved(self):
        """The composer previews a rule that does not exist yet. `new()` gives
        it the real engine and no row — and no `last_error` write either."""
        conn = self._connector()
        draft = self.Rule.new({
            'connector_id': conn.id, 'name': 'draft', 'output_key': 'DRAFT',
            'builder_mode': 'guided', 'rule_type': 'sum',
            'source_data_type': 'custom',
            'value_steps': [{'field': 'Actual_Pay_Hour', 'contains': 'number'}],
            'filter_conditions': {'join': 'all', 'rows': [
                {'field': 'ApprovalStatus', 'op': 'is', 'value': 'Approved'}]},
        })
        trace = draft.preview_on_records(OT_ROWS)
        self.assertEqual(trace['result'], 4 + 2.5 + 3 + 1.25)
        self.assertEqual(self.Rule.search_count([('output_key', '=', 'DRAFT')]), 0)

    # ==================================================================== 7
    def test_07_a_proposal_naming_a_field_nobody_has_is_rejected_whole(self):
        catalog = [{'path': 'Actual_Pay_Hour', 'label': 'Actual Pay Hour',
                    'feed_type': 'custom', 'sample': '4'},
                   {'path': 'OT_Type', 'label': 'OT Type',
                    'feed_type': 'custom', 'sample': '150%'}]
        Assistant = self.env['hr.api.rule.assistant']

        good = Assistant._validate({
            'rule_type': 'sum', 'source_data_type': 'custom',
            'value_steps': [{'field': 'actual pay hour', 'contains': 'number'}],
            'filter_conditions': {'join': 'all', 'rows': [
                {'field': 'OT_Type', 'op': 'is', 'value': '150%'}]},
            'name': 'OT 150', 'output_key': 'OT150',
        }, catalog, ['custom'])
        self.assertTrue(good)
        self.assertEqual(good['value_steps'][0]['field'], 'Actual_Pay_Hour',
                         "a loose spelling is snapped to the catalogue's own")

        for poisoned in (
            {'value_steps': [{'field': 'Invented_Field', 'contains': 'number'}]},
            {'filter_conditions': {'join': 'all', 'rows': [
                {'field': 'Ghost', 'op': 'is', 'value': 'x'}]}},
            {'rule_type': 'python'},
            {'source_data_type': 'nowhere'},
            {'value_steps': [{'field': 'OT_Type', 'contains': 'furlongs'}]},
        ):
            data = {'rule_type': 'sum', 'source_data_type': 'custom',
                    'value_steps': [{'field': 'Actual_Pay_Hour', 'contains': 'number'}],
                    'filter_conditions': {'join': 'all', 'rows': []},
                    'name': 'x', 'output_key': 'X'}
            data.update(poisoned)
            self.assertIsNone(Assistant._validate(data, catalog, ['custom']),
                              "%s must reject the WHOLE proposal" % poisoned)

    def test_07b_with_no_key_the_deterministic_floor_answers_and_says_so(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_formula_studio.llm_api_key', '')
        catalog = [{'path': 'Actual_Pay_Hour', 'label': 'Actual Pay Hour',
                    'feed_type': 'custom', 'sample': '4'},
                   {'path': 'OT_Type', 'label': 'OT Type',
                    'feed_type': 'custom', 'sample': '150%'}]
        out = self.env['hr.api.rule.assistant'].propose(
            'sum Actual Pay Hour where OT Type is 150%', catalog, ['custom'])
        self.assertTrue(out['ok'])
        self.assertEqual(out['source'], 'deterministic',
                         "an unavailable assistant must SAY it fell back")
        spec = out['spec']
        self.assertEqual(spec['rule_type'], 'sum')
        self.assertEqual(spec['builder_mode'], 'guided')
        self.assertEqual([s['field'] for s in spec['value_steps']], ['Actual_Pay_Hour'])
        self.assertEqual(spec['filter_conditions']['rows'][0]['field'], 'OT_Type')
        self.assertEqual(spec['filter_conditions']['rows'][0]['value'], '150%')

    def test_07c_proposing_never_writes_a_rule(self):
        before = self.Rule.with_context(active_test=False).search_count([])
        self.env['hr.api.rule.assistant'].propose(
            'count everything', [{'path': 'x', 'label': 'x',
                                  'feed_type': 'custom'}], ['custom'])
        self.assertEqual(
            self.Rule.with_context(active_test=False).search_count([]), before)

    # =============================================== the sentence, and the name
    def test_09_the_summary_reads_as_a_sentence_and_never_names_the_platform(self):
        conn = self._connector()
        rule = self._guided_ot(conn, '150%')
        # The feed is named by its LABEL, not by its technical code: the
        # sentence is read by a payroll manager, and "Custom / Other" is what
        # every other surface in the product calls that feed. Asserted in full
        # rather than by fragment, because the whole point of the field is that
        # it reads as one sentence.
        self.assertEqual(
            rule.plain_summary,
            'Adds up Actual_Pay_Hour over Custom / Other records where OT_Type '
            'is 150% and ApprovalStatus is Approved')

        python_rule = self._rule(conn, builder_mode='python', rule_type='python',
                                 output_key='PY', python_code='result = 1')
        self.assertEqual(
            python_rule.plain_summary,
            'Advanced rule (Python), maintained by your administrator')

        for text in (rule.plain_summary, python_rule.plain_summary,
                     plain_summary_for(self._rule(conn, rule_type='count',
                                                  output_key='CNT'))):
            self.assertNotIn('odoo', (text or '').lower(),
                             "no user-visible string may name the platform")

    # ==================================================================== 4b
    #
    # THE MIGRATION. `_convert` is imported and driven directly rather than
    # asserted about: an idempotency claim that is not executed twice is a
    # paragraph, and the second run is the one that can go wrong.

    def _legacy_shaped_rules(self, conn):
        """The eight, spelled exactly as Cycle 3 shipped them."""
        made = self.Rule.browse()
        for band in OT_BANDS:
            made |= self._legacy_ot(conn, band)
        made |= self._rule(
            conn, builder_mode='python', rule_type='python',
            output_key='DEPCOUNT', source_data_type='employee',
            python_code="deps = 0\n"
                        "for r in records:\n"
                        "    rows = (r.get('tabularSections') or {}).get("
                        "'Dependent and Dependent Health Insurance') or []\n"
                        "    for d in rows:\n"
                        "        if d.get('Dependent_PIT_Number'):\n"
                        "            deps = deps + 1\n"
                        "result = deps\n")
        made |= self._rule(
            conn, builder_mode='python', rule_type='python',
            output_key='WORKEDHRS', source_data_type='attendance',
            python_code="total = 0.0\n"
                        "for r in records:\n"
                        "    worked = str(r.get('totalWorkedHours') or 0).strip()\n"
                        "result = total\n")
        return made

    def test_04_the_migration_converts_the_eight_and_is_safe_to_run_twice(self):
        from odoo.modules.module import get_module_path
        import importlib.util
        import os
        path = os.path.join(
            get_module_path('pb_hr_payroll_formula'), 'migrations',
            '19.0.1.60.0', 'post-rules_become_sentences.py')
        spec = importlib.util.spec_from_file_location('ig_c8_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        conn = self._connector('IG-C8 migration')
        rules = self._legacy_shaped_rules(conn)

        changed, skipped, _ = migration._convert(rules, 'rule')
        self.assertEqual(changed, 8, "all eight should convert")
        self.assertEqual(skipped, 0)
        for rule in rules:
            self.assertEqual(rule.builder_mode, 'guided', rule.output_key)
            self.assertTrue(rule.plain_summary, rule.output_key)
        # The provenance is KEPT — deleting it would delete the answer to
        # "is the sentence really what the legacy did?".
        by_key = {r.output_key: r for r in rules}
        self.assertTrue(by_key['OTHRS150'].filter_expression)
        self.assertTrue(by_key['DEPCOUNT'].python_code)
        self.assertEqual(by_key['DEPCOUNT'].rule_type, 'count')
        self.assertEqual(by_key['WORKEDHRS'].rule_type, 'sum')

        # RUN IT AGAIN. Nothing may change, and nothing may be re-converted.
        changed2, skipped2, _ = migration._convert(rules, 'rule')
        self.assertEqual(changed2, 0, "a second -u must be a no-op")
        self.assertEqual(skipped2, 8)

    def test_04c_a_retuned_rule_is_left_exactly_as_it_is(self):
        """Create-only doctrine, one layer over: a rule that silently reverts
        to the vendor's arithmetic is a payslip that silently changes."""
        from odoo.modules.module import get_module_path
        import importlib.util
        import os
        path = os.path.join(
            get_module_path('pb_hr_payroll_formula'), 'migrations',
            '19.0.1.60.0', 'post-rules_become_sentences.py')
        spec = importlib.util.spec_from_file_location('ig_c8_migration2', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        conn = self._connector('IG-C8 retuned')
        rule = self._legacy_ot(conn, '150%')
        rule.write({'filter_expression': "rec.get('OT_Type') == '150%'"})
        changed, skipped, _ = migration._convert(rule, 'rule')
        self.assertEqual(changed, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(rule.builder_mode, 'python',
                         "an operator's edit survives the migration")

    def test_09b_the_template_and_its_rule_describe_themselves_identically(self):
        template = self.env['hr.api.transformation.rule.template'].create({
            'connector_type': 'demo', 'name': 'T', 'output_key': 'TKEY',
            'rule_type': 'count', 'source_data_type': 'custom',
            'builder_mode': 'guided',
            'filter_conditions': {'join': 'all', 'rows': [
                {'field': 'state', 'op': 'is', 'value': 'ok'}]},
        })
        conn = self.Connector.create({'name': 'IG-C8 demo', 'connector_type': 'demo'})
        conn.action_sync_transformation_rules()
        rule = conn.transformation_rule_ids.filtered(
            lambda r: r.output_key == 'TKEY')
        self.assertTrue(rule, "the template must instantiate")
        self.assertEqual(rule.builder_mode, 'guided')
        self.assertEqual(rule.filter_conditions, template.filter_conditions)
        self.assertEqual(rule.plain_summary, template.plain_summary)
