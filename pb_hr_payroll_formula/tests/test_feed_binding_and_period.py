# -*- coding: utf-8 -*-
"""Two defects a pay run could not see, and neither of which raised anything.

The July 2026 ABM run computed 0 payslips. Two independent causes, both silent:

  1. **The scheme was never bound to its connector.** `payroll_import_batch
     ._transform_data_to_formula_inputs` applies a connector's field mappings
     only when `config.connector_id` is set — its own comment says "the
     connector is reachable via `config.connector_id`, which is what makes the
     single gate sufficient". Nothing ever set it. ABM had **25 confirmed Zoho
     wires** onto "AB Mauri Payroll" and a null binding, so the board reported
     25 mapped and the run behaved as though the connector did not exist.

  2. **No window reached the vendor.** The cockpit's per-feed Sync called
     `action_pull_endpoint(ep.id)` with no period, and the model falls back to
     the CURRENT calendar month. Every staged row on ABM was stamped
     `2026-08-01 → 2026-08-31` while the run being prepared was July's.
     Attendance, overtime and leave were a month out and nothing said so.

Both classes are the same shape: a correct-looking screen over an answer about
the wrong thing. The tests below pin the repair for each.
"""
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeConnectorBinding(TransactionCase):

    def setUp(self):
        super().setUp()
        self.connector = self.env['hr.integration.connector'].create({
            'name': 'Binding probe', 'connector_type': 'zoho',
        })
        self.config = self.env['hr.formula.config'].create({
            'name': 'Binding probe scheme', 'country_code': 'VN',
        })
        self.rule = self.env['hr.formula.rule'].create({
            'config_id': self.config.id,
            'name': 'Base salary', 'code': 'BASESAL',
            'column_type': 'input',
        })

    def _wire(self, source='Salary', connector=None):
        return self.env['hr.integration.field.mapping'].create({
            'connector_id': (connector or self.connector).id,
            'source_field': source,
            'target_rule_id': self.rule.id,
        })

    def test_the_first_wire_binds_the_scheme_to_its_connector(self):
        """The defect, stated as its repair.

        Before this, a scheme could carry a full board of confirmed wires and a
        null `connector_id`, and every wire was skipped at run time.
        """
        self.assertFalse(self.config.connector_id)
        self._wire()
        self.assertEqual(self.config.connector_id, self.connector)

    def test_an_existing_binding_is_never_overwritten(self):
        """A scheme deliberately pointed somewhere stays pointed there."""
        other = self.env['hr.integration.connector'].create({
            'name': 'Deliberate choice', 'connector_type': 'excel',
        })
        self.config.connector_id = other.id
        self._wire()
        self.assertEqual(self.config.connector_id, other)

    def test_a_wire_with_no_target_binds_nothing(self):
        """A severed or unrouted wire must not bind a scheme it cannot name."""
        self.env['hr.integration.field.mapping'].create({
            'connector_id': self.connector.id, 'source_field': 'Orphan',
        })
        self.assertFalse(self.config.connector_id)

    # ------------------------------------------------------- the third rail
    def test_an_unbound_scheme_resolves_from_its_own_wires(self):
        """`create` binds going in; this heals a scheme that got past it.

        A row written by SQL, a restore, or any future path that clears the
        field must not be able to put a scheme back into the silence.
        """
        self._wire()
        self.config.connector_id = False
        self.assertEqual(self.config._resolve_feed_connector(), self.connector)
        # Resolving BINDS, so the answer is visible on the record afterwards
        # instead of being recomputed differently later.
        self.assertEqual(self.config.connector_id, self.connector)

    def test_a_scheme_with_no_wires_resolves_to_nothing(self):
        """No wires is not a defect, and must not invent a connector."""
        self.assertFalse(self.config._resolve_feed_connector())

    def test_the_busiest_connector_wins_a_shared_scheme(self):
        """The run-time gate can honour one; choosing in silence is the bug."""
        other = self.env['hr.integration.connector'].create({
            'name': 'Second source', 'connector_type': 'excel',
        })
        self._wire('A')
        self._wire('B')
        self._wire('C', connector=other)
        self.config.connector_id = False
        self.assertEqual(self.config._resolve_feed_connector(), self.connector)


@tagged('post_install', '-at_install')
class TestPullPeriodReachesTheVendor(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Cockpit = self.env['pb.import.connector.cockpit']
        self.connector = self.env['hr.integration.connector'].create({
            'name': 'Period probe', 'connector_type': 'zoho',
        })

    # -------------------------------------------------- the window, validated
    def test_a_stated_period_is_passed_through_verbatim(self):
        start, end = self.Cockpit._period('2026-07-01', '2026-07-31')
        self.assertEqual((start, end), (date(2026, 7, 1), date(2026, 7, 31)))

    def test_no_period_leaves_the_model_its_own_default(self):
        self.assertEqual(self.Cockpit._period(None, None), (None, None))
        # A HALF-given window is the dangerous case: applying one end of it
        # would pull a different span than the one on screen.
        self.assertEqual(self.Cockpit._period('2026-07-01', None), (None, None))

    def test_a_backwards_or_absurd_window_is_refused(self):
        with self.assertRaises(ValidationError):
            self.Cockpit._period('2026-07-31', '2026-07-01')
        with self.assertRaises(ValidationError):
            self.Cockpit._period('2020-01-01', '2026-07-01')
        with self.assertRaises(ValidationError):
            self.Cockpit._period('not-a-date', '2026-07-31')

    # ------------------------------------------- what the feed then remembers
    def test_a_feed_records_the_window_it_was_asked_for(self):
        """`last_sync` says when we asked; this says what we asked FOR.

        Two different facts. Only one of them was ever recorded, which is why a
        feed full of August rows was indistinguishable from a correct one
        during a July run.
        """
        endpoint = self.env['hr.integration.endpoint'].create({
            'connector_id': self.connector.id,
            'name': 'Attendance summary', 'code': 'probeatt',
            'data_type': 'attendance', 'operation': 'attendance_summary',
            'path': 'attendance/getSummaryReport',
        })
        self.connector._stamp_endpoint(
            'attendance', 'success',
            period_from=date(2026, 7, 1), period_to=date(2026, 7, 31))
        endpoint.invalidate_recordset()
        self.assertEqual(endpoint.last_period_from, date(2026, 7, 1))
        self.assertEqual(endpoint.last_period_to, date(2026, 7, 31))

        row = self.Cockpit._endpoint_row(endpoint)
        self.assertEqual(row['period_label'], 'Jul 2026')
        # Dated feeds carry the flag the card reads; a feed whose answer does
        # not depend on the window must not claim a period at all.
        self.assertTrue(row['period_scoped'])

    def test_state_feeds_are_not_period_scoped(self):
        """Employees and salary return current state, whatever month you ask."""
        endpoint = self.env['hr.integration.endpoint'].create({
            'connector_id': self.connector.id,
            'name': 'Employees', 'code': 'probeemp',
            'data_type': 'employee', 'operation': 'employee',
            'path': 'forms/employee/getRecords',
        })
        self.assertFalse(self.Cockpit._endpoint_row(endpoint)['period_scoped'])

    def test_a_whole_month_reads_as_a_month_and_a_part_month_does_not(self):
        self.assertEqual(
            self.Cockpit._period_label(date(2026, 7, 1), date(2026, 7, 31)),
            'Jul 2026')
        self.assertEqual(
            self.Cockpit._period_label(date(2026, 7, 1), date(2026, 8, 15)),
            '01 Jul – 15 Aug 2026')
        self.assertEqual(self.Cockpit._period_label(False, False), '')

    def test_the_offered_period_remembers_the_last_one_pulled(self):
        """A connector being worked on for July keeps saying July.

        Rolling silently to the current month the moment the calendar does is
        how the wrong window gets pulled by someone who did check the screen.
        """
        self.env['hr.integration.endpoint'].create({
            'connector_id': self.connector.id,
            'name': 'Attendance summary', 'code': 'probeatt2',
            'data_type': 'attendance', 'operation': 'attendance_summary',
            'last_sync': '2026-08-26 12:00:00',
            'last_period_from': '2026-07-01', 'last_period_to': '2026-07-31',
        })
        offered = self.Cockpit._default_pull_period(self.connector)
        self.assertEqual((offered['from'], offered['to']),
                         ('2026-07-01', '2026-07-31'))
        self.assertEqual(offered['label'], 'Jul 2026')

    def test_with_no_history_the_current_month_is_offered(self):
        offered = self.Cockpit._default_pull_period(self.connector)
        today = date.today()
        self.assertEqual(offered['from'], str(today.replace(day=1)))
