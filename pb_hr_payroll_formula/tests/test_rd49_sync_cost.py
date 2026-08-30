# -*- coding: utf-8 -*-
"""RD49 — stop paying for data nothing reads, and stop paying for it at run time.

The Zoho pull asks about ONE EMPLOYEE AT A TIME and makes up to three requests
each — salary, attendance, leave. For 152 people that is 456 sequential HTTP
round trips, and it happens while somebody is sitting in the Run Payroll wizard
waiting for it.

Two changes, and they are independent:

  * **Ask for less.** On the reference tenant NO component maps a leave field,
    yet leave was pulled for every employee every time: 152 requests, a third of
    the total, for data no formula could ever read. The fetch now takes the set
    of feed kinds the connector's ACTIVE wires point at.
  * **Ask earlier.** A scheduled job fetches the previous month on the 5th, so
    the run reads data that is already there.

THE RAIL ON BOTH: *never guess a smaller set from missing information.* No
wires, or wires with no endpoint, means "cannot tell" and everything is
fetched — which is exactly what happened before either change existed. A slower
sync costs minutes; a missing feed costs a payslip computed on nothing.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRd49SyncCost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Endpoint = cls.env['hr.integration.endpoint']
        cls.Mapping = cls.env['hr.integration.field.mapping']

    def _connector(self, name='RD49'):
        return self.Connector.create({'name': name, 'connector_type': 'demo'})

    def _rule(self, code):
        cfg = self.env['hr.formula.config'].search([], limit=1) or \
            self.env['hr.formula.config'].create({
                'name': 'RD49 cfg', 'code': 'RD49CFG', 'country_code': 'VN'})
        return self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': code, 'code': code,
            'column_type': 'input'})

    def _wire(self, connector, data_type, code, active_state='active'):
        ep = self.Endpoint.create({
            'connector_id': connector.id, 'name': '%s feed' % data_type,
            'data_type': data_type, 'code': 'rd49_%s_%s' % (data_type, code),
        })
        return self.Mapping.create({
            'connector_id': connector.id, 'endpoint_id': ep.id,
            'target_rule_id': self._rule(code).id,
            'source_field': 'F_%s' % code, 'active_state': active_state,
        })

    # =====================================================================
    # 1 — which kinds are worth fetching
    # =====================================================================
    def test_01a_only_the_kinds_the_wires_point_at(self):
        conn = self._connector()
        self._wire(conn, 'employee', 'EMPCODE')
        self._wire(conn, 'salary', 'BASEPAY')
        self._wire(conn, 'attendance', 'WORKHOURS')

        kinds = conn._mapped_feed_kinds()

        self.assertEqual(kinds, ['attendance', 'employee', 'salary'])
        self.assertNotIn('leave', kinds,
                         "no component reads a leave field — that is 152 "
                         "requests a sync on the reference tenant")

    def test_01b_an_unconfirmed_wire_does_not_buy_a_feed(self):
        """Only 'active' wires are load-bearing (F114/D114.2), here too."""
        conn = self._connector()
        self._wire(conn, 'salary', 'BASEPAY')
        self._wire(conn, 'leave', 'LEAVEDAYS', active_state='suggested')
        self.assertEqual(conn._mapped_feed_kinds(), ['salary'])

    def test_01c_no_wires_means_FETCH_EVERYTHING_not_nothing(self):
        """The rail. Missing information is not permission to fetch less."""
        conn = self._connector()
        self.assertEqual(conn._mapped_feed_kinds(), [],
                         "empty is the signal for 'cannot tell'; the caller "
                         "reads it as 'fetch everything', which is what "
                         "happened before this existed")

    def test_01d_the_zoho_fetch_honours_the_set(self):
        """Asserted on the implementation, which is where the requests are made."""
        from odoo.addons.pb_hr_payroll_formula.integrations import zoho_connector
        import inspect
        src = inspect.getsource(zoho_connector.ZohoConnector.fetch_payroll_data)
        self.assertIn('kinds', src)
        # …and the default still fetches all three, so an untaught caller is
        # unaffected.
        self.assertIn("{'salary', 'attendance', 'leave'}", src)

    def test_01e_a_connector_that_cannot_take_the_argument_is_not_given_it(self):
        """Seven connectors implement this; most still take three arguments.

        A keyword they do not declare would turn a saving into a TypeError in
        the middle of a sync.
        """
        import inspect
        from odoo.addons.pb_hr_payroll_formula.models import integration_connector
        src = inspect.getsource(
            integration_connector.HrIntegrationConnector.fetch_payroll_data)
        self.assertIn('inspect.signature', src)
        self.assertIn("'kinds' in params", src)

    # =====================================================================
    # 2 — the schedule
    # =====================================================================
    def test_02a_the_previous_month_including_across_a_year_end(self):
        C = self.Connector
        self.assertEqual(C._rd49_previous_month(date(2026, 8, 30)),
                         (date(2026, 7, 1), date(2026, 7, 31)))
        self.assertEqual(C._rd49_previous_month(date(2026, 1, 5)),
                         (date(2025, 12, 1), date(2025, 12, 31)),
                         "January must reach back into last year")
        self.assertEqual(C._rd49_previous_month(date(2024, 3, 5)),
                         (date(2024, 2, 1), date(2024, 2, 29)),
                         "and February must know about leap years")

    def test_02aa_the_schedule_lands_on_the_5th_at_two_in_the_morning(self):
        from datetime import datetime
        C = self.Connector
        # before the 5th → this month's 5th
        self.assertEqual(C._rd49_next_fifth(datetime(2026, 8, 2, 11, 0)),
                         datetime(2026, 8, 5, 2, 0))
        # on the 5th but after 02:00 → next month's
        self.assertEqual(C._rd49_next_fifth(datetime(2026, 8, 5, 9, 30)),
                         datetime(2026, 9, 5, 2, 0))
        # December rolls the year
        self.assertEqual(C._rd49_next_fifth(datetime(2026, 12, 20, 0, 0)),
                         datetime(2027, 1, 5, 2, 0))

    def test_02ab_the_cron_record_exists_and_is_valid_for_odoo_19(self):
        """`numbercall` and `doall` are gone from `ir.cron` in Odoo 19.

        Leaving one in the data file aborts the ENTIRE module load with
        `ValueError: Invalid field 'numbercall' in 'ir.cron'` — and takes every
        module co-upgraded in the same command down with it. Asserted on the
        record rather than on the file, so it fails for the right reason.
        """
        cron = self.env.ref('pb_hr_payroll_formula.ir_cron_pull_previous_month')
        self.assertTrue(cron.active)
        self.assertEqual(cron.interval_type, 'months')
        self.assertEqual(cron.interval_number, 1)
        self.assertIn('cron_pull_previous_month', cron.code)
        for gone in ('numbercall', 'doall'):
            self.assertNotIn(gone, cron._fields)

    def test_02b_the_job_does_nothing_until_a_connector_opts_in(self):
        conn = self._connector()
        self._wire(conn, 'salary', 'BASEPAY')
        self.assertFalse(conn.cron_pull_enabled,
                         "a schedule that reaches into somebody's HR system is "
                         "opt-in, per connector")
        self.Connector.cron_pull_previous_month()
        self.assertFalse(conn.cron_pull_last_run)

    def test_02c_a_connector_with_no_wires_is_skipped_and_says_so(self):
        conn = self._connector()
        conn.cron_pull_enabled = True
        self.Connector.cron_pull_previous_month()
        self.assertTrue(conn.cron_pull_last_run, "it looked, and recorded that")
        self.assertIn('Skipped', conn.cron_pull_last_result)

    def test_02d_one_connector_s_failure_does_not_stop_the_others(self):
        """A sync that did no work must not look like one that did."""
        broken = self._connector('RD49 broken')
        broken.cron_pull_enabled = True
        self._wire(broken, 'salary', 'BROKENPAY')
        healthy = self._connector('RD49 healthy')
        healthy.cron_pull_enabled = True
        self._wire(healthy, 'salary', 'HEALTHYPAY')

        def boom(self, *args, **kwargs):
            if self.name == 'RD49 broken':
                raise RuntimeError('the HR system said no')
            return True

        self.patch(type(self.Connector), 'action_pull_data', boom)
        self.Connector.cron_pull_previous_month()

        self.assertIn('Could not fetch', broken.cron_pull_last_result)
        self.assertIn('the HR system said no', broken.cron_pull_last_result)
        self.assertIn('Fetched', healthy.cron_pull_last_result,
                      "the next connector still ran")

    def test_02e_the_roster_is_always_fetched(self):
        """Other feeds join to the employee feed; without it they attach to nobody."""
        conn = self._connector()
        conn.cron_pull_enabled = True
        self._wire(conn, 'attendance', 'WORKHOURS')     # no employee wire
        asked = {}

        def record(self, data_types=None, **kwargs):
            asked['types'] = data_types
            return True

        self.patch(type(self.Connector), 'action_pull_data', record)
        self.Connector.cron_pull_previous_month()

        self.assertIn('employee', asked['types'])
        self.assertIn('attendance', asked['types'])
        self.assertNotIn('leave', asked['types'])

    def test_02g_the_outcome_is_recorded_as_a_state_not_only_prose(self):
        """RD53 — "did it fail?" must be answerable without reading a sentence."""
        conn = self._connector()
        conn.cron_pull_enabled = True
        self.Connector.cron_pull_previous_month()
        self.assertEqual(conn.cron_pull_last_state, 'skipped')

        healthy = self._connector('RD53 ok')
        healthy.cron_pull_enabled = True
        self._wire(healthy, 'salary', 'RD53PAY')
        self.patch(type(self.Connector), 'action_pull_data',
                   lambda self, **kw: True)
        self.Connector.cron_pull_previous_month()
        self.assertEqual(healthy.cron_pull_last_state, 'ok')

    def test_02h_running_it_by_hand_needs_the_switch_on_first(self):
        """What you test must be what the schedule will do."""
        from odoo.exceptions import UserError
        conn = self._connector()
        self._wire(conn, 'salary', 'RD53PAY2')
        with self.assertRaises(UserError):
            conn.action_fetch_last_month_now()

    def test_02i_the_status_call_answers_the_whole_question_at_once(self):
        status = self.Connector.rd53_fetch_status()
        self.assertTrue(status['scheduled'])
        self.assertTrue(status['next_run'])
        self.assertIsInstance(status['connectors'], list)

    def test_02f_the_job_never_computes_payroll(self):
        """Nobody should find a pay run they did not start."""
        import inspect
        from odoo.addons.pb_hr_payroll_formula.models import integration_cron
        src = inspect.getsource(integration_cron.HrIntegrationConnector)
        for forbidden in ('compute_sheet', 'create_and_compute',
                          'hr.payslip', 'payslip_run'):
            self.assertNotIn(forbidden, src)
