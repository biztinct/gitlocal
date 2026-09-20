# -*- coding: utf-8 -*-
"""RD60 — the collateral of a record refresh, found by the owner rather than by us.

RD54 gave the connected system a way to update Payobook's records without a pay
run. It works. What nobody accounted for is that it does so by CREATING A BATCH,
and "the newest batch" turned out to be load-bearing in four separate places.
Within one afternoon on the reference tenant:

  * the Run Payroll wizard's Include chips collapsed to a single "Not stated"
    and offered all 160 people with no way to exclude leavers;
  * the Mapping board opened on the connected system's columns instead of the
    columns the last run was mapped from;
  * the Journey view narrated a payload that produced no payslip as "the last
    pay run";
  * two empty draft batches were left behind by refreshes that failed on
    "nothing staged to load", and went on standing in front of the pay data in
    every picker.

And one deeper fault the refresh only revealed: Zoho spells the employee key
`EmployeeID` in its employee form and `Employee_ID` in its salary form, so the
same 152 people were staged under 304 external ids and arrived as 304 half-empty
rows.

THE SHAPE OF THE FIX. Employment status and worked hours had been read as one
thing from one batch, and they are not one thing:

    HOURS  belong to a PERIOD — only this run's own pay data may say them.
    STATUS belongs to a PERSON — the newest statement wins, whoever made it,
           read per person; silence is silence, not an assertion.

Pinning both to the newest PAY DATA (the first attempt) was wrong in the
opposite direction: it landed on a twelve-row correction file that named a
status for four people and said nothing about the other 148 — same empty chips.
Both directions are tested below, because the fix has to survive both.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRd60SignalAndIdentity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Line = cls.env['hr.payroll.import.line']

    # ------------------------------------------------------------------
    # fixtures
    # ------------------------------------------------------------------
    def _scheme(self):
        cfg = self.env['hr.formula.config'].create({
            'name': 'RD60 scheme', 'code': 'RD60', 'country_code': 'VN',
            'state': 'active'})
        self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Employee Status', 'code': 'RDSTATUS',
            'column_type': 'input', 'payroll_signal': 'employment_status'})
        self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Worked Hours', 'code': 'RDHOURS',
            'column_type': 'input', 'payroll_signal': 'worked_hours'})
        return cfg

    def _people(self, n=3):
        return self.env['hr.employee'].create(
            [{'name': 'RD60 person %d' % i} for i in range(n)])

    def _batch(self, cfg, name, pay_data, rows):
        """`rows` is `[(employee, {raw key: value}), …]`."""
        batch = self.Batch.create({
            'name': name, 'source_type': 'excel' if pay_data else 'api_data_store',
            'formula_config_id': cfg.id, 'create_payslips': pay_data,
            'state': 'done'})
        import json
        self.Line.create([{
            'batch_id': batch.id, 'sequence': i + 1,
            'employee_id': emp.id, 'state': 'draft',
            'raw_data_json': json.dumps(raw),
        } for i, (emp, raw) in enumerate(rows)])
        return batch

    # =====================================================================
    # 1 — status is about a person, hours are about a period
    # =====================================================================
    def test_01a_a_refresh_may_still_say_who_is_employed(self):
        """The first fix over-corrected; this is the line it must not cross.

        A refresh is not the run's pay data — but it IS the connected system
        stating who works here, and on a tenant that uploads no spreadsheet it
        is the only thing that ever says so.
        """
        cfg, (a, b, _c) = self._scheme(), self._people()
        self._batch(cfg, 'pay data', True, [
            (a, {'Worked Hours': 160}), (b, {'Worked Hours': 150})])
        self._batch(cfg, 'refresh', False, [
            (a, {'Employee Status': 'Active'}),
            (b, {'Employee Status': 'Resigned'})])

        signals = cfg.employee_signal_map()

        self.assertEqual(signals[a.id]['status'], 'Active')
        self.assertEqual(signals[b.id]['status'], 'Resigned')
        self.assertEqual(
            {o['label'] for o in cfg.employment_status_options()},
            {'Active', 'Resigned'},
            "the chips the owner lost")

    def test_01b_hours_come_from_the_run_and_from_nowhere_else(self):
        """A pull made on another day is not evidence about this month."""
        cfg, (a, _b, _c) = self._scheme(), self._people()
        self._batch(cfg, 'pay data', True, [(a, {'Worked Hours': 160})])
        self._batch(cfg, 'refresh', False, [
            (a, {'Employee Status': 'Active', 'Worked Hours': 999})])

        self.assertEqual(cfg.employee_signal_map()[a.id]['hours'], 160.0,
                         "the refresh must not be able to say how many hours "
                         "somebody worked in the run's period")

    def test_01c_a_twelve_row_correction_file_does_not_blank_the_roster(self):
        """The over-correction, pinned as behaviour.

        A small file for a handful of people is a correction, not a new roster.
        Everybody it does not mention keeps the status the last source gave.
        """
        cfg, (a, b, c) = self._scheme(), self._people()
        self._batch(cfg, 'full roster', False, [
            (a, {'Employee Status': 'Active'}),
            (b, {'Employee Status': 'Active'}),
            (c, {'Employee Status': 'Resigned'})])
        # …and then today's correction file, newest, naming one person.
        self._batch(cfg, 'correction', True, [(a, {'Employee Status': 'LONG LEAVE'})])

        signals = cfg.employee_signal_map()

        self.assertEqual(signals[a.id]['status'], 'LONG LEAVE',
                         "the newest statement about A wins")
        self.assertEqual(signals[b.id]['status'], 'Active',
                         "B is not mentioned in the correction — that is "
                         "silence, not 'B has no status'")
        self.assertEqual(signals[c.id]['status'], 'Resigned')

    def test_01d_a_silent_payload_never_overwrites_one_that_spoke(self):
        """The exact shape of the live failure: a salary-only pull.

        The newest refresh on the reference tenant carried `Employee_ID` and
        `Base_Salary` and nothing else — no names, no statuses. Read as "the
        newest batch" it turned 152 known statuses into 152 blanks.
        """
        cfg, (a, b, _c) = self._scheme(), self._people()
        self._batch(cfg, 'full pull', False, [
            (a, {'Employee Status': 'Active'}),
            (b, {'Employee Status': 'Terminated'})])
        self._batch(cfg, 'salary only', False, [
            (a, {'Base Salary': 19510000}), (b, {'Base Salary': 12500000})])

        signals = cfg.employee_signal_map()
        self.assertEqual(signals[a.id]['status'], 'Active')
        self.assertEqual(signals[b.id]['status'], 'Terminated')

    def test_01e_an_empty_string_is_silence_too(self):
        """`""` is what a spreadsheet's blank cell arrives as."""
        cfg, (a, _b, _c) = self._scheme(), self._people()
        self._batch(cfg, 'older', False, [(a, {'Employee Status': 'Active'})])
        self._batch(cfg, 'newer', True, [(a, {'Employee Status': '   '})])
        self.assertEqual(cfg.employee_signal_map()[a.id]['status'], 'Active')

    def test_01f_the_scan_is_bounded(self):
        """Drawing four chips must not walk a year of history."""
        from odoo.addons.pb_hr_payroll_formula.models import formula_config
        self.assertIsInstance(formula_config._SIGNAL_STATUS_BATCH_SCAN, int)
        self.assertLessEqual(formula_config._SIGNAL_STATUS_BATCH_SCAN, 20)

    # =====================================================================
    # 2 — one person is one row, however the feed spells their id
    # =====================================================================
    def test_02a_two_spellings_of_one_key_fold_into_one_person(self):
        """Zoho's employee form says `EmployeeID`, its salary form `Employee_ID`."""
        groups = self.Batch._store_groups_by_person({
            '11094': {'EmployeeID': '11094', 'Employeestatus': 'Active'},
            '811648000007178001': {'Employee_ID': '11094',
                                   'Base_Salary': 19510000},
        })
        self.assertEqual(len(groups), 1,
                         "304 import lines for 152 people is what this prevents")
        _primary, members = groups[0]
        self.assertEqual(len(members), 2)

    def test_02b_two_different_people_stay_two_people(self):
        groups = self.Batch._store_groups_by_person({
            'x': {'EmployeeID': '11094'}, 'y': {'EmployeeID': '11095'}})
        self.assertEqual(len(groups), 2)

    def test_02c_rows_with_no_code_are_never_merged(self):
        """Two people we cannot name must not become one on the strength of
        both being anonymous."""
        groups = self.Batch._store_groups_by_person({
            'ext-1': {'totalWorkedHours': 160},
            'ext-2': {'totalWorkedHours': 150},
        })
        self.assertEqual(len(groups), 2)

    def test_02d_the_fold_keeps_the_order_it_met_people_in(self):
        groups = self.Batch._store_groups_by_person({
            'b': {'EmployeeID': '2'}, 'a': {'EmployeeID': '1'}})
        self.assertEqual([g[0] for g in groups], ['b', 'a'])

    # =====================================================================
    # 3 — a refresh does not stand in front of the pay data
    # =====================================================================
    def test_03a_a_failed_refresh_leaves_no_empty_draft_behind(self):
        conn = self.env['hr.integration.connector'].create({
            'name': 'RD60 conn', 'connector_type': 'demo'})
        self.env['hr.formula.config'].create({
            'name': 'RD60 wired', 'code': 'RD60W', 'country_code': 'VN',
            'state': 'active', 'connector_id': conn.id})
        before = self.Batch.search_count([])

        def refuse(self):
            from odoo.exceptions import UserError
            raise UserError("No extracted data found in the API Data Store.")

        self.patch(type(self.Batch), 'action_load_from_data_store', refuse)
        self.assertFalse(conn._rd54_writeback_from_store(None, None))

        self.assertEqual(self.Batch.search_count([]), before,
                         "the husk of a refresh that did nothing went on "
                         "appearing in every batch picker as 'the newest batch'")
        self.assertIn('Could not update records', conn.cron_writeback_last_result)

    def test_03b_the_journey_run_lane_wants_a_batch_that_made_payroll(self):
        """Asserted here rather than in the studio's own suite because this is
        where the cause lives: the studio module is optional, so the test skips
        rather than fails where it is not installed."""
        if 'pb.formula.studio' not in self.env:
            self.skipTest("pb_formula_studio is not installed")
        import inspect
        studio = self.env['pb.formula.studio']
        src = inspect.getsource(type(studio)._journey_run_lane)
        self.assertIn("('create_payslips', '=', True)", src,
                      "the run lane narrated a record refresh as 'the last run'")
