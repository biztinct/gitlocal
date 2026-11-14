# -*- coding: utf-8 -*-
"""WDGAP PR-D T9 — the demo's division run path honours an Extra run.

The demo overrides `prepare_run` / `compute_batch` / `create_and_compute`
and never calls super on its division path, so everything the wizard learned
about an Extra run has to be said here too:

* the people picked (`employee_ids`) are the people paid — on every kind of
  run; an Extra run with nobody, or with somebody the division does not pay,
  is refused before anything is made;
* an Extra run never meets the division's other runs (no "already has",
  no clear) and never repays the month's loan instalment nor recovers the
  mid-month advance a second time — those belong to the regular run;
* a Regular demo run computes exactly what it always did (R5).

A division scheme of its own (three inputs and one formula) stands in for the
generated world, so the test runs on any database with `pb_demo` installed.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_prd')
class TestDemoExtraRun(TransactionCase):

    def setUp(self):
        super().setUp()
        Run = self.env['hr.payslip.run']
        if 'pb_run_kind' not in Run._fields \
                or 'extra' not in dict(Run._fields['pb_run_kind'].selection):
            self.skipTest('This build has no Extra run.')
        if 'division' not in self.env['hr.employee']._fields:
            self.skipTest('Employees carry no division on this build.')
        self.Wizard = self.env['pb.payrun.wizard']
        self.Run = Run
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        self.config = self.env['hr.formula.config'].create({
            'name': 'PRD Demo Retail End', 'code': 'PRDDEMORETAILEND',
            'state': 'active', 'country_code': 'VN', 'is_demo': True,
            'pb_division': 'retail', 'cycle_type': 'end_cycle',
            'company_id': self.env.company.id})
        Rule = self.env['hr.formula.rule']
        rules = {}
        for seq, code in enumerate(('BASIC', 'INLOAN', 'ADVPAY'), start=1):
            rules[code] = Rule.create({
                'config_id': self.config.id, 'name': code, 'code': code,
                'column_type': 'input', 'sequence': seq, 'default_value': 0.0,
                'appears_on_payslip': True, 'category_id': category.id})
        letters = {c: r.column_letter for c, r in rules.items()}
        Rule.create({
            'config_id': self.config.id, 'name': 'PRD take-home', 'code': 'NET',
            'column_type': 'formula', 'sequence': 9,
            'excel_formula': '=%s-%s-%s' % (letters['BASIC'], letters['INLOAN'],
                                           letters['ADVPAY']),
            'appears_on_payslip': True, 'category_id': category.id})
        self.ann = self._person('PRD Demo Ann', 10000000.0, loan=100000.0)
        self.bob = self._person('PRD Demo Bob', 20000000.0)
        self.vals = {'date_start': '2026-08-01', 'date_end': '2026-08-31',
                     'formula_config_id': self.config.id}

    def _person(self, name, wage, loan=0.0):
        employee = self.env['hr.employee'].create({
            'name': name, 'company_id': self.env.company.id,
            'division': 'retail', 'is_demo': True})
        self.env['hr.contract'].create({
            'name': '%s contract' % name, 'employee_id': employee.id,
            'wage': wage, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.env.company.id})
        if loan:
            self.env['hr.loan'].create({
                'name': 'PRD loan', 'employee_id': employee.id,
                'principal_amount': loan * 10, 'installment_amount': loan,
                'state': 'running'})
        return employee

    def _compute(self, kind, people, name):
        vals = dict(self.vals, name=name, run_kind=kind,
                    employee_ids=[p.id for p in people])
        prep = self.Wizard.prepare_run(vals)
        self.assertTrue(prep.get('run_id'), prep)
        self.assertEqual(prep.get('division'), 'retail')
        # the screen sends back exactly the payload; here: only our people
        prep = dict(prep, emp_ids=[e for e in prep['emp_ids']
                                   if e in [p.id for p in people]])
        self.Wizard.compute_batch(prep)
        return self.Run.browse(prep['run_id']), prep

    @staticmethod
    def _net(slip):
        return sum(slip.line_ids.filtered(lambda l: l.code == 'NET').mapped('total'))

    # ------------------------------------------------------------------ T9
    def test_t9_an_extra_demo_run_pays_one_person_once(self):
        run, prep = self._compute('extra', self.ann, 'Extra run — PRD — 14 Aug 2026')
        self.assertEqual(prep['emp_ids'], [self.ann.id])
        self.assertEqual(run.pb_run_kind, 'extra')
        self.assertTrue(run.is_demo)
        self.assertEqual(len(run.slip_ids), 1)
        slip = run.slip_ids
        self.assertEqual(slip.employee_id, self.ann)
        self.assertIn('Extra run — PRD — 14 Aug 2026', slip.name)
        # the month's loan instalment is the regular run's, not this one's
        self.assertEqual(self._net(slip), 10000000.0)

    def test_t9_the_regular_demo_run_is_unchanged(self):
        """R5 golden: loan instalment taken, everybody in the division."""
        vals = dict(self.vals, name='Demo Payroll August')
        prep = self.Wizard.prepare_run(vals)
        self.assertIn(self.ann.id, prep['emp_ids'])
        self.assertIn(self.bob.id, prep['emp_ids'])
        prep = dict(prep, emp_ids=[self.ann.id, self.bob.id])
        self.Wizard.compute_batch(prep)
        run = self.Run.browse(prep['run_id'])
        self.assertEqual(run.pb_run_kind, 'regular')
        by_person = {s.employee_id: self._net(s) for s in run.slip_ids}
        self.assertEqual(by_person[self.ann], 9900000.0)
        self.assertEqual(by_person[self.bob], 20000000.0)
        golden = sorted((s.employee_id.id, l.code, l.total)
                        for s in run.slip_ids for l in s.line_ids)
        # an Extra run beside it changes none of it, and is not "already there"
        extra, eprep = self._compute('extra', self.ann, 'Extra run — PRD')
        self.assertFalse(eprep.get('needs_confirmation'))
        self.assertTrue(run.exists())
        self.assertEqual(sorted((s.employee_id.id, l.code, l.total)
                                for s in run.slip_ids for l in s.line_ids), golden)
        # and a second regular run still asks, about the regular run only
        again = self.Wizard.prepare_run(vals)
        self.assertTrue(again.get('needs_confirmation'))
        self.Wizard.prepare_run(dict(vals, force_clean=True))
        self.assertTrue(extra.exists())
        self.assertEqual(len(extra.slip_ids), 1)

    def test_t9_the_demo_path_honours_the_people_picked(self):
        prep = self.Wizard.prepare_run(dict(
            self.vals, name='Demo Payroll August', employee_ids=[self.bob.id]))
        self.assertEqual(prep['emp_ids'], [self.bob.id])

    def test_t9_extra_refusals_on_the_demo_path(self):
        before = self.Run.search_count([])
        with self.assertRaises(UserError):
            self.Wizard.prepare_run(dict(self.vals, name='Extra run — PRD',
                                         run_kind='extra', employee_ids=[]))
        with self.assertRaises(UserError):
            self.Wizard.prepare_run(dict(self.vals, name='',
                                         run_kind='extra',
                                         employee_ids=[self.ann.id]))
        outsider = self.env['hr.employee'].create({
            'name': 'PRD Not In Retail', 'company_id': self.env.company.id,
            'division': 'it', 'is_demo': True})
        with self.assertRaises(UserError) as caught:
            self.Wizard.prepare_run(dict(
                self.vals, name='Extra run — PRD', run_kind='extra',
                employee_ids=[self.ann.id, outsider.id]))
        self.assertIn('PRD Not In Retail', str(caught.exception))
        self.assertEqual(self.Run.search_count([]), before)

    def test_t9_the_older_door_runs_an_extra_demo_run(self):
        summary = self.Wizard.create_and_compute(dict(
            self.vals, name='Extra run — PRD — old door', run_kind='extra',
            employee_ids=[self.bob.id]))
        run = self.Run.browse(summary['run_id'])
        self.assertEqual(run.pb_run_kind, 'extra')
        self.assertEqual(run.slip_ids.employee_id, self.bob)
