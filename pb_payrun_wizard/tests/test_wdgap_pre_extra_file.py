# -*- coding: utf-8 -*-
"""WDGAP PR-E (E1) — an Extra run that loads a pay data file keeps only the
people picked. Handover `docs/handovers/wdgap/WDGAP_PR_E_HANDOVER.md` §E1.

Fixture: one company, one live end-of-month scheme whose "Meal Allowance"
reads a spreadsheet column; four people with contracts (Ann, Bob, Cat, Dan),
and a pay data file for Ann, Bob, Cat and somebody nobody knows (Eve).

  E1.1  extra + file keeps the picked person only: one payslip, the other
        rows taken out before anything is processed, nobody created;
  E1.2  a person picked who is not in the file: named before computing
        (pay-data step) and in the answer; computed the regular path's way
        for anybody the file leaves out (from their contract, no file);
  E1.3  Regular and Top-up runs with the same file: byte-identical to the
        code before PR-E (GOLDEN, recorded on origin/19.1);
  E1.4  the picks live on the run; an Extra run naming nobody is refused
        with nothing created;
  E1.5  the mid-month advance: an Extra run's payslip whose file path took
        the advance off is flagged on the run's review; a regular run is not.
"""
import base64
import io
import json
import logging
import os

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


class _ExtraFileFixture(TransactionCase):

    def setUp(self):
        super().setUp()
        Run = self.env['hr.payslip.run']
        if 'pb_run_kind' not in Run._fields or 'extra' not in dict(
                Run._fields['pb_run_kind'].selection):
            self.skipTest('This build has no Extra run.')
        if 'hr.payroll.import.batch' not in self.env:
            self.skipTest('No pay data file path on this build.')
        self.company = self.env['res.company'].create(
            {'name': 'Extra file test company'})
        self.env = self.env(context=dict(self.env.context,
                                         allowed_company_ids=self.company.ids))
        self.Run = self.env['hr.payslip.run']
        self.Slip = self.env['hr.payslip']
        self.Wizard = self.env['pb.payrun.wizard']
        self.Batch = self.env['hr.payroll.import.batch']
        self.Employee = self.env['hr.employee']
        # The file becomes payslips on the press (the business published "no
        # approval needed" for pay data in this company), as on most tenants.
        Seed = self.env.get('biz.approval.seed')
        if Seed is not None:
            for key in ('loads', 'runonly'):
                Seed.sudo().set_no_approval_needed(self.company, key)
        self.config = self.env['hr.formula.config'].create({
            'name': 'Extra File Payroll', 'code': 'XFILEPROBE',
            'state': 'active', 'country_code': 'VN',
            'cycle_type': 'end_cycle', 'company_id': self.company.id})
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        self.meal = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'MEALALLOW',
            'name': 'Meal Allowance', 'column_type': 'input', 'sequence': 1,
            'default_value': 0.0, 'appears_on_payslip': True,
            'category_id': category.id})
        self.meal.set_source_binding('excel', 'Meal Allowance')
        self.ann = self._person('XF Ann', 'XF001')
        self.bob = self._person('XF Bob', 'XF002')
        self.cat = self._person('XF Cat', 'XF003')
        self.dan = self._person('XF Dan', 'XF004')
        self.vals = {'name': 'Extra run — bonus — 14 Aug 2026',
                     'date_start': '2026-08-01', 'date_end': '2026-08-31',
                     'formula_config_id': self.config.id}

    def _person(self, name, code):
        employee = self.env['hr.employee'].create({
            'name': name, 'company_id': self.company.id, 'barcode': code})
        self.env['hr.contract'].create({
            'name': '%s contract' % name, 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id})
        return employee

    @staticmethod
    def _xlsx(headers, rows):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Sheet1'
        ws.append(list(headers))
        for row in rows:
            ws.append(list(row))
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue()).decode()

    def _file(self):
        return self._xlsx(
            ['Employee Code', 'Employee Name', 'Meal Allowance'],
            [['XF001', 'XF Ann', 100000], ['XF002', 'XF Bob', 200000],
             ['XF003', 'XF Cat', 300000], ['XF999', 'XF Eve', 400000]])

    def _prepare(self, kind, people=None):
        vals = dict(self.vals, run_kind=kind)
        if kind != 'extra':
            vals['name'] = 'August %s' % kind
        if people is not None:
            vals['employee_ids'] = [p.id for p in people]
        prep = self.Wizard.prepare_run(vals)
        self.assertTrue(prep.get('run_id'), prep)
        return prep

    def _attach(self, prep, one_time=False):
        return self.Wizard.attach_spreadsheet(
            prep['run_id'], self.config.id, self._file(), 'august.xlsx',
            '2026-08-01', '2026-08-31', one_time)

    @staticmethod
    def _meal(slip):
        try:
            return float(json.loads(slip.formula_input_values or '{}')
                         .get('MEALALLOW') or 0.0)
        except (TypeError, ValueError):
            return None


@tagged('post_install', '-at_install', 'wdgap_pre')
class TestExtraRunFile(_ExtraFileFixture):

    # ============================================================ E1.1
    def test_e1_1_extra_run_keeps_only_the_people_picked(self):
        people_before = self.Employee.with_context(active_test=False).search_count([])
        prep = self._prepare('extra', [self.ann])
        run = self.Run.browse(prep['run_id'])
        self.assertEqual(run.pb_extra_employee_ids, self.ann)
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['created'], 1)
        self.assertEqual(run.slip_ids.mapped('employee_id'), self.ann)
        self.assertEqual(self._meal(run.slip_ids), 100000.0)
        # the other rows were taken out of the batch before processing
        batch = self.Batch.browse(res['batch_id'])
        self.assertEqual(batch.import_line_ids.mapped('employee_id'), self.ann)
        self.assertEqual(res['rows'], 1)
        # nobody else got a payslip anywhere, nobody was created
        for other in (self.bob, self.cat):
            self.assertFalse(self.Slip.search([('employee_id', '=', other.id)]))
        self.assertEqual(
            self.Employee.with_context(active_test=False).search_count([]),
            people_before, 'an extra run created somebody from the file')
        self.assertFalse(res['created_employees'])
        # the calm line
        extra = res['extra']
        self.assertEqual((extra['rows'], extra['kept'], extra['picked']), (4, 1, 1))
        self.assertEqual(extra['sentence'],
                         'This file has 4 people. This extra run keeps the 1 you picked.')
        self.assertFalse(extra['warning'])
        self.assertEqual(extra['advance'], 0)
        # the compute that follows pays nobody twice, and nobody else
        self.Wizard.compute_batch(prep)
        run.invalidate_recordset()
        self.assertEqual(run.slip_ids.mapped('employee_id'), self.ann)
        self.assertEqual(len(run.slip_ids), 1)

    def test_e1_1b_this_run_only_mode_keeps_only_the_picks_too(self):
        prep = self._prepare('extra', [self.bob, self.cat])
        res = self._attach(prep, one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        run = self.Run.browse(prep['run_id'])
        self.assertEqual(sorted(run.slip_ids.mapped('employee_id').ids),
                         sorted((self.bob | self.cat).ids))
        # the stranger is not "not in Payobook yet": not this run's business
        self.assertEqual(res['unmatched_count'], 0)
        self.assertEqual(res['extra']['sentence'],
                         'This file has 4 people. This extra run keeps the 2 you picked.')

    # ============================================================ E1.2
    def test_e1_2_a_person_picked_who_is_not_in_the_file_is_named(self):
        # before computing: the pay-data step's own check (creates nothing)
        counts = (self.Batch.search_count([]),
                  self.env['hr.payroll.import.line'].search_count([]))
        pre = self.Wizard.preflight_spreadsheet(
            self.config.id, self._file(), 'august.xlsx',
            [self.ann.id, self.dan.id])
        self.assertTrue(pre['ok'], pre.get('msg'))
        self.assertEqual(pre['extra']['absent'], ['XF Dan'])
        self.assertEqual((pre['extra']['rows'], pre['extra']['kept']), (4, 1))
        self.assertIn('XF Dan is not in this file', pre['extra']['warning'])
        self.assertIn('regular run', pre['extra']['warning'])
        self.assertEqual(counts, (self.Batch.search_count([]),
                                  self.env['hr.payroll.import.line'].search_count([])))
        # without people the pre-flight answers exactly as before
        self.assertNotIn('extra', self.Wizard.preflight_spreadsheet(
            self.config.id, self._file(), 'august.xlsx'))

        prep = self._prepare('extra', [self.ann, self.dan])
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['extra']['absent'], ['XF Dan'])
        self.assertEqual(res['created'], 1)
        # the regular path's treatment of somebody the file leaves out: the
        # wizard's compute works their payslip out without the file
        self.Wizard.compute_batch(prep)
        run = self.Run.browse(prep['run_id'])
        self.assertEqual(sorted(run.slip_ids.mapped('employee_id').ids),
                         sorted((self.ann | self.dan).ids))
        dan_slip = run.slip_ids.filtered(lambda s: s.employee_id == self.dan)
        self.assertTrue(dan_slip.line_ids, 'Dan was given an empty payslip')
        self.assertEqual(self._meal(dan_slip), 0.0, 'Dan has no file value')
        self.assertFalse(self.env['hr.payroll.import.line'].search(
            [('payslip_id', '=', dan_slip.id)]))

    def test_e1_2b_nobody_picked_is_in_the_file(self):
        prep = self._prepare('extra', [self.dan])
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['created'], 0)
        self.assertEqual(res['extra']['sentence'],
                         'This file has 4 people. Nobody you picked is in it.')
        self.assertIn('XF Dan', res['extra']['warning'])

    # ============================================================ E1.3
    def _signature(self, kind):
        prep = self._prepare(kind)
        res = self._attach(prep)
        run = self.Run.browse(prep['run_id'])
        return {
            'ok': res['ok'], 'rows': res['rows'], 'created': res['created'],
            'matched': res['matched'],
            'created_employees': res['created_employees'],
            'errors': len(res['errors']),
            'fed': sorted(res['fed_components']),
            'keys': sorted(res),
            'slips': sorted((s.employee_id.name, self._meal(s))
                            for s in run.slip_ids),
            'lines': len(self.Batch.browse(res['batch_id']).import_line_ids),
        }

    def test_e1_3_regular_and_topup_are_what_they_were(self):
        sig = {'regular': self._signature('regular')}
        sig['topup'] = self._signature('topup')
        sig = json.loads(json.dumps(sig))
        if os.environ.get('PRE_GOLDEN_RECORD'):
            _logger.warning('PRE_E1_GOLDEN=%s', json.dumps(sig, sort_keys=True))
            return
        self.assertEqual(sig, GOLDEN_E1)

    # ============================================================ E1.4
    def test_e1_4_an_extra_run_naming_nobody_is_refused(self):
        run = self.Run.create({
            'name': 'Extra run made elsewhere', 'date_start': '2026-08-01',
            'date_end': '2026-08-31', 'pb_run_kind': 'extra',
            'pb_formula_config_id': self.config.id})
        before = self.Batch.search_count([])
        res = self.Wizard.attach_spreadsheet(
            run.id, self.config.id, self._file(), 'august.xlsx',
            '2026-08-01', '2026-08-31')
        self.assertFalse(res['ok'])
        self.assertIn('pick the people', res['msg'])
        self.assertEqual(self.Batch.search_count([]), before)
        self.assertFalse(run.slip_ids)

    def test_e1_4b_the_older_door_stores_the_picks_too(self):
        before = set(self.Run.search([]).ids)
        self.Wizard.create_and_compute(dict(
            self.vals, run_kind='extra', employee_ids=[self.cat.id]))
        made = self.Run.search([('id', 'not in', list(before))])
        self.assertEqual(made.pb_extra_employee_ids, self.cat)
        # a regular run stores nobody
        prep = self._prepare('regular')
        self.assertFalse(self.Run.browse(prep['run_id']).pb_extra_employee_ids)


@tagged('post_install', '-at_install', 'wdgap_pre')
class TestExtraRunAdvance(_ExtraFileFixture):
    """E1.5 — an end-of-month scheme with a mid-month advance."""

    def setUp(self):
        super().setUp()
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        self.advpay = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'ADVPAY',
            'name': 'Advance paid', 'column_type': 'input', 'sequence': 2,
            'default_value': 0.0, 'appears_on_payslip': True,
            'category_id': category.id})
        mid = self.env['hr.formula.config'].create({
            'name': 'Extra File Mid-Month', 'code': 'XFILEMID',
            'country_code': 'VN', 'cycle_type': 'mid_cycle',
            'company_id': self.company.id})
        mid_adv = self.env['hr.formula.rule'].create({
            'config_id': mid.id, 'code': 'ADVPAY', 'name': 'Advance',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'category_id': category.id})
        self.env['hr.payroll.cycle.component.mapping'].create({
            'mid_cycle_config_id': mid.id,
            'end_cycle_config_id': self.config.id,
            'mid_component_id': mid_adv.id, 'end_component_id': self.advpay.id})
        mid_batch = self.Batch.create({
            'name': 'August mid-month', 'source_type': 'excel',
            'formula_config_id': mid.id, 'payroll_period': 'custom',
            'date_from': '2026-08-01', 'date_to': '2026-08-15'})
        mid_batch.write({'state': 'done'})
        self.env['hr.payroll.cycle.carryover'].create({
            'employee_id': self.ann.id, 'formula_config_id': mid.id,
            'source_component_id': mid_adv.id, 'amount': 3000000.0,
            'company_id': self.company.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-15',
            'import_batch_id': mid_batch.id, 'state': 'posted'})

    def _advance(self, slip):
        return float(json.loads(slip.formula_input_values or '{}')
                     .get('ADVPAY') or 0.0)

    def test_e1_5_the_extra_payslip_that_takes_the_advance_is_flagged(self):
        prep = self._prepare('extra', [self.ann])
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        run = self.Run.browse(prep['run_id'])
        slip = run.slip_ids
        # what happens today, said plainly in the report: the pay data file
        # path takes the advance off this extra payslip too
        self.assertEqual(self._advance(slip), 3000000.0)
        self.assertEqual(res['extra']['advance'], 1)
        self.assertIn('mid-month advance', res['extra']['advance_sentence'])
        row = run.pb_review_flags()[slip.id]
        self.assertTrue(row['flag'])
        self.assertIn('This file also takes the mid-month advance; check it has '
                      'not been taken already', row['reason'])

    def test_e1_5b_a_regular_run_is_not_flagged_for_the_advance(self):
        prep = self._prepare('regular')
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertNotIn('extra', res)
        run = self.Run.browse(prep['run_id'])
        slip = run.slip_ids.filtered(lambda s: s.employee_id == self.ann)
        self.assertEqual(self._advance(slip), 3000000.0)
        row = run.pb_review_flags()[slip.id]
        self.assertNotIn('mid-month advance', row.get('reason') or '')
        self.assertFalse(row.get('advance'))

    def test_e1_5c_an_extra_payslip_without_the_advance_is_not_flagged(self):
        prep = self._prepare('extra', [self.bob])
        res = self._attach(prep)
        self.assertEqual(res['extra']['advance'], 0)
        run = self.Run.browse(prep['run_id'])
        row = run.pb_review_flags()[run.slip_ids.id]
        self.assertNotIn('mid-month advance', row.get('reason') or '')


#: Recorded on origin/19.1 (4c9c82a40, before PR-E), same fixture, with
#: PRE_GOLDEN_RECORD=1.
GOLDEN_E1 = {'regular': {'created': 3,
             'created_employees': 0,
             'errors': 1,
             'fed': ['MEALALLOW'],
             'keys': ['batch_id',
                      'created',
                      'created_employees',
                      'errors',
                      'fed_components',
                      'filename',
                      'matched',
                      'ok',
                      'one_time',
                      'pending',
                      'request_id',
                      'rows',
                      'run_id',
                      'unmatched',
                      'unmatched_count',
                      'with_whom'],
             'lines': 4,
             'matched': 3,
             'ok': True,
             'rows': 4,
             'slips': [['XF Ann', 100000.0],
                       ['XF Bob', 200000.0],
                       ['XF Cat', 300000.0]]},
 'topup': {'created': 3,
           'created_employees': 0,
           'errors': 1,
           'fed': ['MEALALLOW'],
           'keys': ['batch_id',
                    'created',
                    'created_employees',
                    'errors',
                    'fed_components',
                    'filename',
                    'matched',
                    'ok',
                    'one_time',
                    'pending',
                    'request_id',
                    'rows',
                    'run_id',
                    'unmatched',
                    'unmatched_count',
                    'with_whom'],
           'lines': 4,
           'matched': 3,
           'ok': True,
           'rows': 4,
           'slips': [['XF Ann', 100000.0],
                     ['XF Bob', 200000.0],
                     ['XF Cat', 300000.0]]}}
