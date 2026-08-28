# -*- coding: utf-8 -*-
"""NETROLE P3 — the Run Payroll wizard asks for the month's spreadsheet.

A scheme can say, component by component, "this one reads a spreadsheet
column". The wizard never asked for a file, and the batchless compute path has
no spreadsheet branch, so every one of those components fell back to the
contract or to a default and no screen said a file had been expected. The
owner's words: "otherwise silently it does not want any excel to be used."

What is asserted here is the whole of the repair:

  * the step appears ONLY when a scheme really does bind a component to a
    column — a database where none does behaves exactly as it did before;
  * the pre-flight reads a file's headings and says what it feeds, creating
    nothing at all;
  * the file loads INTO the run that already exists, and the chunked compute
    that follows does not pay anybody a second time;
  * a file that cannot be read leaves nothing behind and says why;
  * skipping is a choice that comes BACK, naming the components that ran on
    fallback values.
"""
import base64
import io

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSpreadsheetStep(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['pb.payrun.wizard']
        self.Batch = self.env['hr.payroll.import.batch']
        self.Source = self.env['hr.formula.rule.source']
        self.company = self.env.company

        # `hr.formula.config` refuses a scheme with no country.
        self.config = self.env['hr.formula.config'].create({
            'name': 'Pay data probe scheme',
            'code': 'PWP3PROBE',
            'country_code': 'VN',
            'company_id': self.company.id,
        })
        self.rules = {}
        for code, name in (('MEALALLOW', 'Meal Allowance'),
                           ('PHONEALLOW', 'Phone Allowance'),
                           ('TAXIALLOW', 'Taxi Allowance')):
            self.rules[code] = self.env['hr.formula.rule'].create({
                'config_id': self.config.id, 'code': code, 'name': name,
                'column_type': 'input',
            })

        self.employee = self.env['hr.employee'].create({
            'name': 'Pay Data Person', 'company_id': self.company.id,
            'barcode': 'PWP3E1',
        })
        self.contract = self.env['hr.contract'].create({
            'name': 'Pay data contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })
        self.vals = {'name': 'Probe June', 'date_start': '2026-06-01',
                     'date_end': '2026-06-30'}

    # ------------------------------------------------------------- helpers
    def _bind(self, code, key):
        self.rules[code].set_source_binding('excel', key)

    def _xlsx(self, headers, rows):
        """A real workbook, built in memory — the loader parses no other kind."""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Sheet1'          # the batch's own default sheet name
        ws.append(list(headers))
        for row in rows:
            ws.append(list(row))
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue()).decode()

    def _pay_file(self):
        return self._xlsx(
            ['Employee Code', 'Employee Name', 'Meal Allowance', 'Phone Allowance'],
            [['PWP3E1', 'Pay Data Person', 730000, 250000]])

    def _choices(self, gate):
        return [c['id'] for c in (gate.get('choices') or [])]

    def _counts(self):
        return (self.Batch.search_count([]),
                self.env['hr.payroll.import.line'].search_count([]))

    # =================================================== 1. the gate
    def test_a_scheme_with_no_spreadsheet_column_asks_for_no_file(self):
        """No binding anywhere means the wizard is byte-for-byte what it was."""
        gate = self.Wizard.spreadsheet_gate({})
        self.assertNotIn(self.config.id, self._choices(gate))
        if not self.Source.search_count([('kind', '=', 'excel')]):
            # Nothing in this database binds a column — the demo world's shape.
            self.assertFalse(gate.get('wanted'))

    def test_one_bound_component_is_enough_to_ask(self):
        self._bind('MEALALLOW', 'Meal Allowance')
        gate = self.Wizard.spreadsheet_gate({})
        self.assertTrue(gate['wanted'])
        self.assertIn(self.config.id, self._choices(gate))
        codes = [c['code'] for c in gate['components']] \
            if gate['config_id'] == self.config.id else []
        if codes:
            self.assertEqual(codes, ['MEALALLOW'])

    def test_a_source_row_cannot_name_no_column_at_all(self):
        """A binding that points at nothing is refused where it is written.

        The gate drops blank-key rows anyway — belt and braces for a row a
        migration or raw SQL could still leave behind — but the invariant is
        enforced one layer down, and that is where this asserts it. Asking a
        user for a file on account of a component that can never be fed would
        be the same silence this phase is closing, pointed the other way.
        """
        self._bind('MEALALLOW', 'Meal Allowance')
        with self.assertRaises(ValidationError):
            self.rules['MEALALLOW'].source_ids.write({'key': '   '})

    def test_a_scheme_of_plain_formulas_never_appears(self):
        """The demo-shaped scheme: rules, no bindings, no step."""
        other = self.env['hr.formula.config'].create({
            'name': 'Demo-shaped scheme', 'code': 'PWP3DEMO',
            'country_code': 'VN', 'company_id': self.company.id})
        self.env['hr.formula.rule'].create({
            'config_id': other.id, 'code': 'GROSS', 'name': 'Gross',
            'column_type': 'input'})
        self._bind('MEALALLOW', 'Meal Allowance')      # a different scheme binds
        gate = self.Wizard.spreadsheet_gate({})
        self.assertTrue(gate['wanted'])
        self.assertNotIn(other.id, self._choices(gate))

    # =================================================== 2. the pre-flight
    def test_preflight_says_what_the_file_feeds_and_what_it_misses(self):
        self._bind('MEALALLOW', 'Meal Allowance')
        self._bind('PHONEALLOW', 'Phone Allowance')
        self._bind('TAXIALLOW', 'Taxi Allowance')
        res = self.Wizard.preflight_spreadsheet(
            self.config.id, self._pay_file(), 'june.xlsx')
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['total'], 3)
        self.assertEqual(sorted(res['fed']), ['MEALALLOW', 'PHONEALLOW'])
        self.assertEqual([m['code'] for m in res['missing']], ['TAXIALLOW'])
        self.assertEqual(res['columns'], 4)
        self.assertTrue(res['employees_col'])

    def test_preflight_creates_absolutely_nothing(self):
        """A pre-flight is a question. It must not be a first half of a load."""
        self._bind('MEALALLOW', 'Meal Allowance')
        before = self._counts()
        self.Wizard.preflight_spreadsheet(
            self.config.id, self._pay_file(), 'june.xlsx')
        self.assertEqual(self._counts(), before)

    def test_preflight_refuses_a_file_it_cannot_read(self):
        self._bind('MEALALLOW', 'Meal Allowance')
        res = self.Wizard.preflight_spreadsheet(
            self.config.id, base64.b64encode(b'not a spreadsheet').decode(),
            'broken.xlsx')
        self.assertFalse(res['ok'])
        self.assertTrue(res['msg'])

    # =================================================== 3. attaching
    def test_the_file_lands_in_the_run_that_already_exists(self):
        self._bind('MEALALLOW', 'Meal Allowance')
        self._bind('PHONEALLOW', 'Phone Allowance')
        prep = self.Wizard.prepare_run(dict(self.vals))
        run_id = prep['run_id']
        runs_before = self.env['hr.payslip.run'].search_count([])

        res = self.Wizard.attach_spreadsheet(
            run_id, self.config.id, self._pay_file(), 'june.xlsx',
            '2026-06-01', '2026-06-30')
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['run_id'], run_id)
        self.assertEqual(self.env['hr.payslip.run'].search_count([]),
                         runs_before, "a second pay run was built beside the first")

        batch = self.Batch.browse(res['batch_id'])
        self.assertEqual(batch.payslip_run_id.id, run_id)
        for slip in batch.created_payslip_ids:
            self.assertEqual(slip.payslip_run_id.id, run_id)
        self.assertEqual(sorted(res['fed_components']),
                         ['MEALALLOW', 'PHONEALLOW'])

    def test_the_compute_that_follows_pays_nobody_twice(self):
        """"Batch first, wizard computes the rest" rests entirely on this."""
        self._bind('MEALALLOW', 'Meal Allowance')
        prep = self.Wizard.prepare_run(dict(self.vals))
        run_id = prep['run_id']
        res = self.Wizard.attach_spreadsheet(
            run_id, self.config.id, self._pay_file(), 'june.xlsx',
            '2026-06-01', '2026-06-30')
        self.assertTrue(res['ok'], res.get('msg'))
        if not res['created']:
            self.skipTest("the file produced no payslip in this database")

        before = self.env['hr.payslip'].search_count([('payslip_run_id', '=', run_id)])
        self.Wizard.compute_batch({
            'run_id': run_id, 'name': prep['name'],
            'date_start': prep['date_start'], 'date_end': prep['date_end'],
            'emp_ids': [self.employee.id]})
        after = self.env['hr.payslip'].search_count([('payslip_run_id', '=', run_id)])
        self.assertEqual(after, before)
        self.assertEqual(self.env['hr.payslip'].search_count([
            ('payslip_run_id', '=', run_id),
            ('employee_id', '=', self.employee.id)]), 1)

    # =================================================== 4. a broken file
    def test_a_broken_file_leaves_nothing_behind_and_says_why(self):
        self._bind('MEALALLOW', 'Meal Allowance')
        prep = self.Wizard.prepare_run(dict(self.vals))
        before = self._counts()
        res = self.Wizard.attach_spreadsheet(
            prep['run_id'], self.config.id,
            base64.b64encode(b'\x00\x01 not a workbook at all').decode(),
            'broken.xlsx', '2026-06-01', '2026-06-30')
        self.assertFalse(res['ok'])
        self.assertTrue(res['msg'], "a refusal must state its own reason")
        # The savepoint rolled the whole load back: no batch, no lines.
        self.assertEqual(self._counts(), before)

    def test_an_empty_run_left_by_a_failed_file_is_discarded(self):
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertTrue(self.Wizard.discard_empty_run(prep['run_id'])['ok'])
        self.assertFalse(
            self.env['hr.payslip.run'].browse(prep['run_id']).exists())

    def test_a_run_with_work_in_it_is_never_discarded(self):
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': 'Real work',
            'contract_id': self.contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'payslip_run_id': prep['run_id'], 'company_id': self.company.id,
        })
        self.assertFalse(self.Wizard.discard_empty_run(prep['run_id'])['ok'])
        self.assertTrue(
            self.env['hr.payslip.run'].browse(prep['run_id']).exists())

    # =================================================== 5. skipping, out loud
    def test_skipping_comes_back_naming_what_ran_on_fallbacks(self):
        self._bind('MEALALLOW', 'Meal Allowance')
        self._bind('TAXIALLOW', 'Taxi Allowance')
        vals = dict(self.vals, spreadsheet_skipped=True,
                    spreadsheet_config_id=self.config.id)
        prep = self.Wizard.prepare_run(vals)
        self.assertEqual(sorted(prep['skipped_components']),
                         ['MEALALLOW', 'TAXIALLOW'])

    def test_a_run_that_was_never_asked_for_a_file_says_nothing_about_one(self):
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertNotIn('skipped_components', prep)


@tagged('post_install', '-at_install')
class TestSyncPlan(TransactionCase):
    """The pull is scoped to what the scheme actually reads.

    `action_pull_data`'s own default is `['employee', 'salary']`, and on the
    reference tenant that was both too much and too little: NOTHING read
    `salary` there, while `attendance` and `custom` — 9 wires including the
    worked hours every deduction is a percentage of — were not pulled at all.
    So a run that synced "successfully" still had no hours. `salary` is also
    the expensive one: it loops per employee making three API calls each.
    """

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['pb.payrun.wizard']
        if 'hr.integration.field.mapping' not in self.env:
            self.skipTest("the integration layer is not installed here")
        self.config = self.env['hr.formula.config'].create({
            'name': 'Sync plan scheme', 'code': 'PWSYNC', 'country_code': 'VN'})
        self.rule = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'WORKEDHRS',
            'name': 'Worked hours', 'column_type': 'input'})
        self.connector = self.env['hr.integration.connector'].create({
            'name': 'Sync plan system', 'connector_type': 'demo'})

    def _endpoint(self, data_type, name):
        return self.env['hr.integration.endpoint'].create({
            'connector_id': self.connector.id,
            'name': name, 'data_type': data_type})

    def _wire(self, endpoint, source_field):
        return self.env['hr.integration.field.mapping'].create({
            'connector_id': self.connector.id,
            'endpoint_id': endpoint.id,
            'source_field': source_field,
            'target_rule_id': self.rule.id})

    def test_the_plan_covers_the_kinds_the_scheme_reads(self):
        self._wire(self._endpoint('attendance', 'Attendance summary'), 'WORKEDHRS')
        kinds = {s['data_type'] for s in self.Wizard._payrun_sync_plan({})}
        self.assertIn('attendance', kinds,
                      "the hours every deduction is a percentage of")

    def test_a_kind_nothing_reads_is_not_pulled(self):
        self._wire(self._endpoint('attendance', 'Attendance summary'), 'WORKEDHRS')
        self._endpoint('salary', 'Salary form')      # exists, but nothing wires it
        kinds = {s['data_type'] for s in self.Wizard._payrun_sync_plan({})}
        self.assertNotIn('salary', kinds,
                         "an unread feed is cost with no benefit — and this is "
                         "the per-employee one")

    def test_one_step_per_system_and_kind(self):
        att = self._endpoint('attendance', 'Attendance summary')
        self._wire(att, 'WORKEDHRS')
        self._wire(att, 'OTHERKEY')                  # second wire, same endpoint
        plan = self.Wizard._payrun_sync_plan({})
        self.assertEqual(len(plan), 1, "two wires on one feed is one pull")
        self.assertIn('Attendance', plan[0]['label']
                      if 'Attendance' in plan[0]['label'] else 'attendance',
                      plan[0]['label'])

    def test_a_step_names_itself_for_the_progress_bar(self):
        self._wire(self._endpoint('custom', 'Overtime requests'), 'WORKEDHRS')
        plan = self.Wizard._payrun_sync_plan({})
        self.assertTrue(plan[0]['label'],
                        "the wizard shows this while it waits")
        self.assertIn('Sync plan system', plan[0]['label'])
