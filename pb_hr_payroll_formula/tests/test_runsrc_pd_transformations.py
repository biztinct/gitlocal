# -*- coding: utf-8 -*-
"""RUNSRC Phase D — the pay run's own numbers, inside a transformation rule.

The handover numbers fourteen cases and every test below states its number in
its docstring. Numbers 7, 10, 13 and 14 belong to other modules (the composer's
picker, the contract drawer, the translations, the white-label grep) and live
in `pb_integrations/tests/test_runsrc_pd_composer.py`,
`pb_contracts/tests/test_cd2_fills_from.py` and this file's `test_14`.

THE ONE PROPERTY EVERYTHING HERE PROTECTS. A transformation rule must never
work to a different standard-working-days number from the payslip beside it.
Test 5 asserts exactly that, against the two code paths as they really are
rather than against a constant.
"""
import datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import pay_period

# 1-31 August 2036 has 21 Monday-to-Friday days. Counted by hand: the 1st is a
# Friday, so the weekdays are the 1st, 4-8, 11-15, 18-22 and 25-29.
#
# WHY 2036 AND NOT THE MONTH THE FEATURE WAS BUILT FOR. `_period_std_days`
# searches the database for the pay run or pay-data load behind the period it
# is given, and `rztest` is a real-data clone whose August 2026 really does
# have both (ledger RS19: its ten failures are its DATA, not its code). A
# fixture period no customer can own is the only way these cases answer the
# same on all six databases. The arithmetic is identical — August 2036 has the
# same 21 Monday-to-Friday days as the August 2026 the owner will check on
# screen.
AUG_FROM = datetime.date(2036, 8, 1)
AUG_TO = datetime.date(2036, 8, 31)
AUG_STD = 21.0


@tagged('post_install', '-at_install')
class TestRunsrcPdTransformations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Store = cls.env['hr.api.data.store']
        cls.Rule = cls.env['hr.api.transformation.rule']
        cls.Run = cls.env['hr.payslip.run']

    # ------------------------------------------------------------ fixtures
    def _connector(self, name='RUNSRC-D'):
        return self.Connector.create({'name': name, 'connector_type': 'zoho'})

    def _store(self, conn, data_type, payload, ext_id='RSD-1',
               period_from=AUG_FROM, period_to=AUG_TO):
        return self.Store.create({
            'connector_id': conn.id, 'data_type': data_type,
            'employee_external_id': ext_id, 'raw_payload': payload,
            'extracted_data': payload, 'state': 'extracted',
            'period_from': period_from, 'period_to': period_to,
        })

    def _rule(self, conn, **vals):
        base = {'connector_id': conn.id, 'name': 'R', 'output_key': 'RKEY',
                'rule_type': 'sum', 'source_data_type': 'attendance',
                'builder_mode': 'excel'}
        base.update(vals)
        return self.Rule.create(base)

    def _run(self, days, date_from=AUG_FROM, date_to=AUG_TO):
        run = self.Run.create({
            'name': 'RUNSRC D run', 'date_start': date_from,
            'date_end': date_to, 'pb_std_work_days': days,
        })
        # `create` fills the Mon-Fri default when the value is falsy (Phase B),
        # so a fixture that wants a stored ZERO has to write it afterwards.
        if run.pb_std_work_days != days:
            run.pb_std_work_days = days
        return run

    # ==================================================================== 1
    def test_01_the_six_numbers_are_in_the_python_namespace(self):
        """Test 1 — the six are there, and correctly valued for a period."""
        conn = self._connector()
        row = self._store(conn, 'attendance', {'LOPDays': 1})
        rule = self._rule(
            conn, builder_mode='python', rule_type='python',
            output_key='PYNS',
            python_code=("result = (paymonth * 1000000 + payyear * 100 "
                         "+ paydays)"))
        # 8 * 1e6 + 2036 * 100 + 31
        self.assertEqual(rule._execute_single({'attendance': row}, row),
                         8 * 1000000 + 2036 * 100 + 31)

        for name in pay_period.NAMESPACE_NAMES:
            probe = self._rule(conn, builder_mode='python', rule_type='python',
                               output_key='PY' + name.upper(),
                               python_code='result = %s' % name)
            value = probe._execute_single({'attendance': row}, row)
            self.assertIsInstance(value, float, name)

        expected = {'paymonth': 8.0, 'payyear': 2036.0, 'paydays': 31.0,
                    'stddays': AUG_STD, 'startday': 1.0, 'endday': 31.0}
        context = self.Rule._period_context(row)
        self.assertEqual(context['values'], expected)

    # ==================================================================== 2
    def test_02_stddays_is_the_number_typed_on_the_run(self):
        """Test 2 — a run exists and says 20, so the rule reads 20."""
        conn = self._connector()
        row = self._store(conn, 'attendance', {'LOPDays': 1})
        self._run(20.0)
        context = self.Rule._period_context(row)
        self.assertEqual(context['std_days'], 20.0)
        self.assertEqual(context['std_source'], 'run')

        rule = self._rule(conn, excel_formula='[stddays]')
        self.assertEqual(rule._execute_single({'attendance': row}, row), 20.0)

    # ==================================================================== 3
    def test_03_stddays_falls_back_to_the_monday_to_friday_count(self):
        """Test 3 — no run for this period, so the honest default answers."""
        conn = self._connector()
        row = self._store(conn, 'attendance', {'LOPDays': 1})
        context = self.Rule._period_context(row)
        self.assertEqual(context['std_days'], AUG_STD)
        self.assertEqual(context['std_source'], 'default')

        rule = self._rule(conn, excel_formula='[stddays]')
        self.assertEqual(rule._execute_single({'attendance': row}, row),
                         AUG_STD)

    # ==================================================================== 4
    def test_04_stddays_is_never_zero_and_never_negative(self):
        """Test 4 — whatever is stored, and however the dates read."""
        conn = self._connector()
        row = self._store(conn, 'attendance', {'LOPDays': 1})
        for stored in (0.0, -5.0, -0.5):
            run = self._run(stored)
            context = self.Rule._period_context(row)
            self.assertEqual(
                context['std_days'], AUG_STD,
                "%s on the run must read as 'nobody said'" % stored)
            self.assertEqual(context['std_source'], 'default')
            run.unlink()

        # A period that runs backwards answers nothing rather than a negative.
        backwards = self._store(conn, 'attendance', {'LOPDays': 1},
                                ext_id='RSD-BACK',
                                period_from=AUG_TO, period_to=AUG_FROM)
        context = self.Rule._period_context(backwards)
        self.assertIsNone(context['std_days'])
        self.assertNotIn('stddays', context['values'])

        # And nothing in the namespace is ever <= 0 where it is present.
        for name, value in self.Rule._period_context(row)['values'].items():
            self.assertGreater(value, 0, name)

    # ==================================================================== 5
    def test_05_a_rule_and_the_payslip_beside_it_agree(self):
        """Test 5 — THE forbidden outcome, asserted.

        The two paths are written independently — the payslip resolver asks its
        own run, the transformation finds the load or run behind its period —
        so this compares the numbers they actually produce rather than two
        copies of one constant.
        """
        conn = self._connector()
        row = self._store(conn, 'attendance', {'LOPDays': 1})
        run = self._run(19.5)

        rule = self._rule(conn, excel_formula='[stddays]')
        from_rule = rule._execute_single({'attendance': row}, row)

        # What the payslip path reads for the same period, through the very
        # helper `hr_payslip_formula` calls.
        from_payslip = run._pb_standard_work_days()
        self.assertEqual(from_rule, from_payslip)
        self.assertEqual(from_rule, 19.5)

        # And with nobody having said: both fall to the same Mon-Fri count.
        run.pb_std_work_days = 0.0
        self.assertIsNone(run._pb_standard_work_days())
        self.assertEqual(
            rule._execute_single({'attendance': row}, row),
            pay_period.default_standard_work_days(AUG_FROM, AUG_TO))

    # ==================================================================== 6
    def test_06_the_trace_says_which_number_and_where_it_came_from(self):
        """Test 6 — §4.1's safety half: the tester tells the reader."""
        conn = self._connector()
        row = self._store(conn, 'attendance', {'LOPDays': 1})
        rule = self._rule(conn, excel_formula='IFERROR([LOPDays]/[stddays], 0)')

        trace = rule.preview_on_records([row.extracted_data], row)
        self.assertIn('period', trace)
        self.assertEqual(trace['period']['std_days'], AUG_STD)
        self.assertEqual(trace['period']['std_source'], 'default')
        note = trace['period']['note']
        self.assertIn('21', note)
        self.assertIn('Monday', note)

        self._run(20.0)
        trace = rule.preview_on_records([row.extracted_data], row)
        self.assertEqual(trace['period']['std_source'], 'run')
        self.assertIn('20', trace['period']['note'])
        self.assertIn('pay run', trace['period']['note'])

    # ==================================================================== 8
    def test_08_the_unpaid_leave_rule_computes(self):
        """Test 8 — the worked example, on the real abm payload shape.

        The row is `hr_api_data_store` id shape from the live abm database:
        Tran Tuan, August 2026, LOPDays 1, and the payload's own
        `expectedWorkingDays` independently says 21.
        """
        conn = self._connector()
        payload = {'name': 'Tran Tuan', 'LOPDays': 1, 'LOPHours': '09:00',
                   'totalDays': 31, 'expectedWorkingDays': 21,
                   'totalPayableDays': 19}
        row = self._store(conn, 'attendance', payload)
        rule = self._rule(conn, output_key='UNPAIDSHARE',
                          excel_formula='IFERROR([LOPDays]/[stddays], 0)')

        # The payload's own expectation and the run's default agree.
        self.assertEqual(float(payload['expectedWorkingDays']), AUG_STD)
        self.assertAlmostEqual(
            rule._execute_single({'attendance': row}, row), 1.0 / 21.0, 9)

        # And a holiday month set by hand on the run moves it, with nothing
        # else changing.
        self._run(20.0)
        self.assertAlmostEqual(
            rule._execute_single({'attendance': row}, row), 1.0 / 20.0, 9)

    # ==================================================================== 9
    def test_09_no_dates_and_a_backwards_period_do_not_raise(self):
        """Test 9 — degrade, never crash."""
        conn = self._connector()
        blank = self._store(conn, 'attendance', {'LOPDays': 2},
                            ext_id='RSD-BLANK',
                            period_from=False, period_to=False)
        backwards = self._store(conn, 'attendance', {'LOPDays': 2},
                                ext_id='RSD-BACK2',
                                period_from=AUG_TO, period_to=AUG_FROM)
        rule = self._rule(conn, excel_formula='IFERROR([LOPDays]/[stddays], 0)')

        # No dates at all — the today-based fallback the python lane has always
        # used, so the rule still answers a number.
        self.assertIsInstance(
            rule._execute_single({'attendance': blank}, blank), float)
        # Backwards — `stddays` is simply absent, IFERROR takes the zero.
        self.assertEqual(
            rule._execute_single({'attendance': backwards}, backwards), 0.0)
        # And the guided lane over the same records.
        guided = self._rule(conn, builder_mode='guided', output_key='GD',
                            excel_formula=False,
                            value_steps=[{'field': 'stddays',
                                          'contains': 'number'}])
        self.assertIsInstance(
            guided._execute_single({'attendance': backwards}, backwards),
            float)

    # =================================================================== 11
    def test_11_template_twin_parity(self):
        """Test 11 — nothing new is stored on the rule, so nothing is missing
        from the template.

        Phase D adds no column to `hr.api.transformation.rule`: the six numbers
        are a NAMESPACE, resolved at run time from the period in front of the
        engine. This asserts that, so a later phase that does add a column has
        to come back and look at `_COPIED`.
        """
        Template = self.env['hr.api.transformation.rule.template']
        copied = set(Template._COPIED)
        rule_fields = set(self.Rule._fields)
        template_fields = set(Template._fields)
        shared = (rule_fields & template_fields) - {
            'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
            'display_name', '__last_update', 'plain_summary', 'active',
            'last_error', 'last_error_at', 'name', 'consumed_field_paths',
        }
        missing = {f for f in shared if f not in copied and f not in (
            'connector_id', 'connector_type', 'is_legacy_abm', 'sequence',
            'description', 'output_key')}
        self.assertFalse(
            missing,
            "these fields exist on both models but are not copied: %s" % missing)

    # =================================================================== 12
    def test_12_pay_neutrality_no_existing_rule_changes(self):
        """Test 12 — every rule that does not name one of the six is untouched.

        The safety property is in `resolve_ref`: `extra` is consulted only
        after the record has been asked and answered nothing, so a reference
        that resolved before resolves to the same value now. This proves it on
        the real ABM shapes, including a row where a field is MISSING (the only
        case the new argument can reach at all).
        """
        conn = self._connector()
        rows = self.Store.browse()
        for payload in (
                {'OT_Type': '150%', 'ApprovalStatus': 'Approved',
                 'Actual_Pay_Hour': 4},
                {'OT_Type': '150%', 'ApprovalStatus': 'Approved',
                 'Actual_Pay_Hour': '2.5'},
                {'OT_Type': '150%', 'ApprovalStatus': 'Rejected',
                 'Actual_Pay_Hour': 8},
                {'OT_Type': '150%', 'ApprovalStatus': 'Approved'},
        ):
            rows |= self._store(conn, 'custom', payload, ext_id='RSD-OT')

        guided = self._rule(
            conn, source_data_type='custom', builder_mode='guided',
            output_key='OTHRS150', rule_type='sum',
            filter_conditions={'join': 'all', 'rows': [
                {'field': 'OT_Type', 'op': 'is', 'value': '150%'},
                {'field': 'ApprovalStatus', 'op': 'is', 'value': 'Approved'}]},
            value_steps=[{'field': 'Actual_Pay_Hour', 'contains': 'number'}])
        self.assertEqual(guided._execute_single({'custom': rows}, rows[0]), 6.5)

        # The SAME sentence in the other lane reaches the same number, which
        # is the parity `test_rule_composer` proves for all eight ABM rules and
        # which this phase must not have moved.
        excel = self._rule(
            conn, source_data_type='custom', output_key='OTX',
            filter_conditions={'join': 'all', 'rows': [
                {'field': 'OT_Type', 'op': 'is', 'value': '150%'},
                {'field': 'ApprovalStatus', 'op': 'is', 'value': 'Approved'}]},
            excel_formula='[Actual_Pay_Hour]')
        self.assertEqual(excel._execute_single({'custom': rows}, rows[0]), 6.5)

        # A rule naming a field NOTHING has, and that is not one of the six,
        # still contributes nothing rather than finding a period value.
        ghost = self._rule(
            conn, source_data_type='custom', output_key='GHOST',
            builder_mode='guided', rule_type='sum',
            value_steps=[{'field': 'nosuchfield', 'contains': 'number'}])
        self.assertEqual(ghost._execute_single({'custom': rows}, rows[0]), 0.0)

    # =================================================================== 12b
    def test_12b_a_record_field_always_beats_the_period(self):
        """Test 12 (the shadowing half) — the record wins, every time."""
        conn = self._connector()
        row = self._store(conn, 'attendance', {'stddays': 17, 'LOPDays': 1})
        rule = self._rule(conn, excel_formula='[stddays]')
        self.assertEqual(rule._execute_single({'attendance': row}, row), 17.0)

        # Even spelled differently: `resolve_ref` asks the record twice before
        # it asks the period once.
        other = self._store(conn, 'attendance', {'Std Days': 16},
                            ext_id='RSD-SPELL')
        self.assertEqual(rule._execute_single({'attendance': other}, other),
                         16.0)

    # =================================================================== 14
    def test_14_no_user_visible_string_names_the_platform(self):
        """Test 14 — the white-label rule, on everything this phase added."""
        strings = [self.Rule._period_note(21.0, 'run'),
                   self.Rule._period_note(21.0, 'load'),
                   self.Rule._period_note(21.0, 'default'),
                   self.Rule._period_note(None, '')]
        strings += [o['label'] for o in self.Rule.period_operands()]
        strings.append(self.Rule._fields['python_code'].help or '')
        for text in strings:
            self.assertNotIn('odoo', (text or '').lower(), text)

    # ------------------------------------------------- the naming contract
    def test_15_the_operand_names_are_the_period_codes(self):
        """Not numbered in the handover, but the drift guard §4.3 asks for.

        The picker's names and the resolver's codes are the SAME list, in the
        same order, lower-cased — never a second typing of six words.
        """
        self.assertEqual([o['name'] for o in self.Rule.period_operands()],
                         list(pay_period.NAMESPACE_NAMES))
        self.assertEqual(
            pay_period.NAMESPACE_NAMES,
            tuple(c.lower() for c in pay_period.PERIOD_CODES))
        for operand in self.Rule.period_operands():
            self.assertTrue(operand['label'], operand['name'])
