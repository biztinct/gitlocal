# -*- coding: utf-8 -*-
"""Two schemes in one month are two payrolls, not a duplicate.

Reported live on the `rize` tenant, 2026-09-22. That company runs a Vietnam
payroll and an India payroll. August's India run existed; starting August's
Vietnam run was answered with **"This month's payroll already exists. Would you
like to clear existing payroll data and run payroll again?"** — and pressing
*Clean and Run* would have deleted the India run and all 27 of its payslips,
because `_clean_period` is handed exactly what the guard found.

The guard asked "is there any run over these dates?". It now asks "is there a
run over these dates **for this scheme**?", and a run that names no scheme at
all is still reported — it cannot be shown to belong elsewhere, and warning is
the safe side of that guess.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTwoSchemesOneMonth(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['pb.payrun.wizard']
        self.Run = self.env['hr.payslip.run']
        self.company = self.env.company
        if 'pb_formula_config_id' not in self.Run._fields:
            self.skipTest('This build has no scheme on the run.')
        Config = self.env.get('hr.formula.config')
        if Config is None:
            self.skipTest('This build has no payroll schemes.')
        self.vn = Config.create({'name': 'Probe Vietnam Payroll',
                                 'state': 'active',
                                 'company_id': self.company.id})
        self.india = Config.create({'name': 'Probe India Payroll',
                                    'state': 'active',
                                    'company_id': self.company.id})
        self.employee = self.env['hr.employee'].create({
            'name': 'Two Scheme Person', 'company_id': self.company.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'Two scheme contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })

    def _run_for(self, config, name='August'):
        """An August run that belongs to `config` and holds one payslip."""
        run = self.Run.create({
            'name': name, 'date_start': '2026-08-01', 'date_end': '2026-08-31',
            'pb_formula_config_id': config.id if config else False,
        })
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': '%s slip' % name,
            'contract_id': self.contract.id, 'payslip_run_id': run.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'company_id': self.company.id,
        })
        return run

    # ------------------------------------------------- the reported bug
    def test_another_schemes_month_is_not_this_schemes_duplicate(self):
        self._run_for(self.india)
        found = self.Wizard._period_runs('2026-08-01', '2026-08-31',
                                         config=self.vn)
        self.assertFalse(found, "India's August was read as Vietnam's.")

    def test_the_same_scheme_twice_in_a_month_still_warns(self):
        self._run_for(self.vn)
        found = self.Wizard._period_runs('2026-08-01', '2026-08-31',
                                         config=self.vn)
        self.assertEqual(len(found), 1)

    def test_a_run_that_names_no_scheme_still_warns(self):
        """It cannot be shown to belong elsewhere, so it is reported."""
        self._run_for(None)
        found = self.Wizard._period_runs('2026-08-01', '2026-08-31',
                                         config=self.vn)
        self.assertEqual(len(found), 1)

    def test_with_no_scheme_asked_for_every_run_is_still_found(self):
        """The old, unscoped answer is what a caller with no scheme gets."""
        self._run_for(self.india)
        found = self.Wizard._period_runs('2026-08-01', '2026-08-31')
        self.assertEqual(len(found), 1)

    def test_the_scheme_is_read_from_the_payslips_when_the_run_is_silent(self):
        """Older runs only carry the scheme on what is inside them."""
        if 'formula_config_id' not in self.env['hr.payslip']._fields:
            self.skipTest('This build has no scheme on the payslip.')
        run = self._run_for(None)
        run.slip_ids.write({'formula_config_id': self.india.id})
        found = self.Wizard._period_runs('2026-08-01', '2026-08-31',
                                         config=self.vn)
        self.assertFalse(found, "A run whose payslips are India's is not Vietnam's.")

    # ------------------------------------------------- what the person reads
    def test_the_question_names_the_payroll_it_would_clear(self):
        runs = self._run_for(self.vn, name='Probe Vietnam Payroll · August 2026')
        msg = self.Wizard._exists_message(runs, self.vn)
        # it names the scheme, names the run, and promises the other payroll
        self.assertIn('Probe Vietnam Payroll', msg)
        self.assertIn('August 2026', msg)
        self.assertIn('another payroll scheme', msg)
