# -*- coding: utf-8 -*-
"""RD54/RD56 — the records come into step without anybody remembering to.

THE HOLE THIS FILLS. A pay run with no spreadsheet wrote nothing to any
record. The reference tenant runs payroll from a connected system and uploads
no file, so its 152 contracts kept the value they were created with — one
person's ₫12,500,000 — while the payslips correctly paid 29 different salaries.
Nothing was broken; the writeback simply belonged to a step that tenant never
took.

Three doors now reach it, and they all reach the SAME writeback:

  * the scheduled fetch, when the connector opts in;
  * "Update records now" on the connector;
  * "Update records" on the pay run's Pay data step, when there is no file.

WHAT THEY MUST NEVER DO IS MAKE PAYROLL. `create_payslips = False` is the whole
guard, and it is the batch's own flag rather than a new one. A person must never
find a pay run they did not start.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRd54RecordRefresh(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Batch = cls.env['hr.payroll.import.batch']

    def _wired(self):
        conn = self.Connector.create({'name': 'RD54', 'connector_type': 'demo'})
        cfg = self.env['hr.formula.config'].create({
            'name': 'RD54 scheme', 'code': 'RD54', 'country_code': 'VN',
            'state': 'active', 'connector_id': conn.id,
        })
        return conn, cfg

    # =====================================================================
    # 1 — a refresh writes records and never payroll
    # =====================================================================
    def test_01a_the_refresh_asks_for_no_payslips(self):
        """The one guard that keeps this safe, asserted on the batch itself."""
        conn, _cfg = self._wired()
        seen = {}

        def capture(self):
            seen['create_payslips'] = self.create_payslips
            seen['source_type'] = self.source_type
            return True

        self.patch(type(self.Batch), 'action_load_from_data_store',
                   lambda self: True)
        self.patch(type(self.Batch), 'action_match_employees', lambda self: True)
        self.patch(type(self.Batch), 'action_process', capture)

        conn._rd54_writeback_from_store(None, None)

        self.assertIs(seen.get('create_payslips'), False,
                      "a record refresh that made payslips would hand somebody "
                      "a pay run they never started")
        self.assertEqual(seen.get('source_type'), 'api_data_store')

    def test_01aa_a_refresh_creates_nobody(self):
        """RD57 — updating records must not invent people or contracts.

        `auto_create_*` defaults to ON, so the first live run stood ready to
        create an employee and a contract for any row it could not match — from
        a button called "update records", and from a schedule running at 2am.
        A refresh updates what exists; creating is a decision somebody takes on
        a load they are watching.
        """
        conn, _cfg = self._wired()
        seen = {}

        def capture(self):
            seen['employees'] = self.auto_create_employees
            seen['contracts'] = self.auto_create_contracts
            return True

        self.patch(type(self.Batch), 'action_load_from_data_store',
                   lambda self: True)
        self.patch(type(self.Batch), 'action_match_employees', lambda self: True)
        self.patch(type(self.Batch), 'action_process', capture)

        conn._rd54_writeback_from_store(None, None)

        self.assertIs(seen.get('employees'), False)
        self.assertIs(seen.get('contracts'), False)

    def test_01ab_no_period_is_given_unless_the_caller_meant_one(self):
        """RD57 — the store is filtered by period, and a guessed month finds
        nothing.

        The first live run asked for JULY while the salary rows had been pulled
        for JUNE, and failed with "no extracted data" having looked straight
        past 608 good rows. Master data is not period-shaped.
        """
        conn, _cfg = self._wired()
        seen = {}

        def capture(self):
            seen['from'] = self.date_from
            seen['to'] = self.date_to
            return True

        self.patch(type(self.Batch), 'action_load_from_data_store',
                   lambda self: True)
        self.patch(type(self.Batch), 'action_match_employees', lambda self: True)
        self.patch(type(self.Batch), 'action_process', capture)

        conn._rd54_writeback_from_store(None, None)
        self.assertFalse(seen.get('from'), "no period means no period filter")
        self.assertFalse(seen.get('to'))

        # …and a caller that DOES mean a period still gets one: the cron has
        # just pulled exactly that month.
        from datetime import date
        conn._rd54_writeback_from_store(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(seen.get('from'), date(2026, 7, 1))
        self.assertEqual(seen.get('to'), date(2026, 7, 31))

    def test_01b_it_reuses_the_ONE_writeback_rather_than_writing_a_second(self):
        import inspect
        from odoo.addons.pb_hr_payroll_formula.models import integration_cron
        src = inspect.getsource(
            integration_cron.HrIntegrationConnector._rd54_writeback_from_store)
        self.assertIn('action_process', src)
        for forbidden in ('_update_contract_from_raw_data',
                          '_update_employee_from_raw_data',
                          '_sync_employee_bank_account'):
            self.assertNotIn(forbidden, src,
                             "the writeback seams are called by action_process; "
                             "reaching past it would be a second answer to "
                             "'what does this field become'")

    def test_01c_a_scheme_that_uses_no_connection_says_so(self):
        conn = self.Connector.create({'name': 'RD54 bare',
                                      'connector_type': 'demo'})
        conn._rd54_writeback_from_store(None, None)
        self.assertIn('nothing to map', conn.cron_writeback_last_result)

    def test_01d_a_failure_is_recorded_not_swallowed(self):
        conn, _cfg = self._wired()

        def boom(self):
            raise RuntimeError('the store said no')

        self.patch(type(self.Batch), 'action_load_from_data_store', boom)
        conn._rd54_writeback_from_store(None, None)
        self.assertIn('could not', conn.cron_writeback_last_result.lower())
        self.assertIn('the store said no', conn.cron_writeback_last_result)

    # =====================================================================
    # 2 — the schedule only writes when asked to
    # =====================================================================
    def test_02a_fetching_and_writing_are_separate_switches(self):
        """Somebody may reasonably want fresh data without changed records."""
        conn, _cfg = self._wired()
        conn.cron_pull_enabled = True
        self.assertFalse(conn.cron_writeback_enabled)
        called = []
        self.patch(type(self.Connector), 'action_pull_data',
                   lambda self, **kw: True)
        self.patch(type(self.Connector), '_rd54_writeback_from_store',
                   lambda self, a, b: called.append(1))
        self.patch(type(self.Connector), '_mapped_feed_kinds',
                   lambda self: ['salary'])

        self.Connector.cron_pull_previous_month()

        self.assertEqual(called, [], "fetching must not write on its own")

    def test_02b_with_both_on_the_records_are_written(self):
        conn, _cfg = self._wired()
        conn.write({'cron_pull_enabled': True, 'cron_writeback_enabled': True})
        called = []
        self.patch(type(self.Connector), 'action_pull_data',
                   lambda self, **kw: True)
        self.patch(type(self.Connector), '_rd54_writeback_from_store',
                   lambda self, a, b: called.append(1))
        self.patch(type(self.Connector), '_mapped_feed_kinds',
                   lambda self: ['salary'])

        self.Connector.cron_pull_previous_month()

        self.assertEqual(len(called), 1)

    # =====================================================================
    # 3 — the pay run's button
    # =====================================================================
    def test_03a_the_wizard_button_reaches_the_same_refresh(self):
        conn, cfg = self._wired()
        called = []
        self.patch(type(self.Connector), '_rd54_writeback_from_store',
                   lambda self, a, b: called.append((a, b)) or True)

        out = self.env['pb.payrun.wizard'].update_records_from_feed(
            {'config_id': cfg.id, 'date_start': '2026-06-01',
             'date_end': '2026-06-30'})

        self.assertTrue(out['ok'])
        self.assertEqual(called, [('2026-06-01', '2026-06-30')],
                         "the period the run is for, not a guessed month")

    def test_03b_a_scheme_with_no_connection_is_told_plainly(self):
        cfg = self.env['hr.formula.config'].create({
            'name': 'RD54 no conn', 'code': 'RD54NC', 'country_code': 'VN',
            'state': 'active'})
        out = self.env['pb.payrun.wizard'].update_records_from_feed(
            {'config_id': cfg.id})
        self.assertFalse(out['ok'])
        self.assertIn('not linked', out['msg'])

    def test_03c_a_broken_refresh_never_breaks_the_step(self):
        """The Pay data step must survive a connector having a bad day."""
        conn, cfg = self._wired()

        def boom(self, a, b):
            raise RuntimeError('nope')

        self.patch(type(self.Connector), '_rd54_writeback_from_store', boom)
        out = self.env['pb.payrun.wizard'].update_records_from_feed(
            {'config_id': cfg.id})
        self.assertFalse(out['ok'])
        self.assertIn('could not be updated', out['msg'])

    # =====================================================================
    # 3b — a refresh must not become "the newest batch" (RD59)
    # =====================================================================
    def test_03d_a_refresh_is_not_the_run_s_pay_data(self):
        """The collateral this caused, pinned.

        Employment-status chips and the value-kind samples both read "the
        newest batch". A record refresh IS a batch, so the moment one ran the
        Run Payroll wizard began reading statuses from the refresh's payload
        instead of the month's pay data — every chip collapsed to "Not stated"
        and 160 people were offered with no way to exclude leavers, on a screen
        that had been filtering correctly an hour before.

        `create_payslips` is the honest test: a batch that produced no payslips
        is not the batch this run's numbers came from.
        """
        import inspect
        from odoo.addons.pb_hr_payroll_formula.models import formula_config
        for fn in (formula_config.HrFormulaConfig.employee_signal_map,
                   formula_config.HrFormulaConfig._value_kind_samples):
            src = inspect.getsource(fn)
            self.assertIn("('create_payslips', '=', True)", src,
                          "%s must ignore record refreshes" % fn.__name__)

    def test_03e_the_signal_map_skips_a_refresh_batch(self):
        """Behaviour, not just the source: the refresh must not win."""
        conn, cfg = self._wired()
        Batch = self.env['hr.payroll.import.batch']
        pay = Batch.create({
            'name': 'RD59 pay data', 'source_type': 'excel',
            'formula_config_id': cfg.id, 'create_payslips': True})
        refresh = Batch.create({
            'name': 'RD59 refresh', 'source_type': 'api_data_store',
            'connector_id': conn.id, 'formula_config_id': cfg.id,
            'create_payslips': False})
        self.assertGreater(refresh.id, pay.id, "the refresh is newer")
        found = self.env['hr.payroll.import.batch'].sudo().search(
            [('formula_config_id', '=', cfg.id),
             ('create_payslips', '=', True)], order='id desc', limit=1)
        self.assertEqual(found, pay,
                         "the newest PAY DATA batch, not the newest batch")

    # =====================================================================
    # 4 — the wizard stops re-fetching what is already here (RD55)
    # =====================================================================
    def test_04a_data_pulled_after_the_period_ended_is_fresh(self):
        conn, _cfg = self._wired()
        Store = self.env['hr.api.data.store']
        ep = self.env['hr.integration.endpoint'].create({
            'connector_id': conn.id, 'name': 'salary', 'data_type': 'salary',
            'code': 'rd55_sal'})
        Store.create({'connector_id': conn.id, 'endpoint_id': ep.id,
                      'data_type': 'salary', 'raw_payload': {},
                      'state': 'extracted'})
        Wizard = self.env['pb.payrun.wizard']
        # the period ended long ago, so today's row is after it
        self.assertTrue(Wizard._rd55_feed_is_fresh(
            conn, ep.id, {'date_end': '2020-01-31'}))

    def test_04b_data_older_than_the_period_end_is_NOT_fresh(self):
        """A pull made mid-month saw a month that had not finished."""
        conn, _cfg = self._wired()
        ep = self.env['hr.integration.endpoint'].create({
            'connector_id': conn.id, 'name': 'salary', 'data_type': 'salary',
            'code': 'rd55_sal2'})
        self.env['hr.api.data.store'].create({
            'connector_id': conn.id, 'endpoint_id': ep.id,
            'data_type': 'salary', 'raw_payload': {}, 'state': 'extracted'})
        Wizard = self.env['pb.payrun.wizard']
        self.assertFalse(Wizard._rd55_feed_is_fresh(
            conn, ep.id, {'date_end': '2099-12-31'}))

    def test_04c_no_period_means_fetch(self):
        """Any doubt at all is answered by fetching. A wasted pull costs a
        minute; a skipped one costs a pay run on last month's numbers."""
        conn, _cfg = self._wired()
        self.assertFalse(self.env['pb.payrun.wizard']._rd55_feed_is_fresh(
            conn, 0, {}))
