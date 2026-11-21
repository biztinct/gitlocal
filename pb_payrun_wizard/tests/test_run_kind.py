# -*- coding: utf-8 -*-
"""PRS P3 (owner ruling R8) — a pay run is Regular or a Top-up.

docs/handovers/payrunscreen/PRS_P3_HANDOVER.md, T21 and the binding safety
rail. The wizard writes the kind the person picked on BOTH create paths
(`prepare_run`, the chunked one the screen uses, and the older
`create_and_compute`). And because the period guard, *Clean and Run* and the
loose-payslip adoption all used to treat any run over the same dates as "this
month's payroll", **choosing Top-up must never clean, delete or adopt
payslips from a Regular run**: a top-up's guard and clean see top-ups only,
and a top-up adopts nothing. R9 (follow-up): the mirror — a Regular run's
guard and clean see Regular runs only, so it never clears a top-up.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRunKind(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Run = self.env['hr.payslip.run']
        if 'pb_run_kind' not in self.Run._fields:
            self.skipTest('pb_payruns (the kind of run) is not installed here.')
        # The native, scheme-free path, isolated from installed client schemes
        # exactly as test_run_adopts_the_period does.
        self.company = self.env['res.company'].create({'name': 'Run kind test company'})
        self.env = self.env(context=dict(self.env.context,
                                         allowed_company_ids=self.company.ids))
        self.Run = self.env['hr.payslip.run']
        self.Wizard = self.env['pb.payrun.wizard']
        self.employee = self.env['hr.employee'].create({
            'name': 'Kind Person', 'company_id': self.company.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'Kind contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id})
        self.category = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'NET')], limit=1) \
            or self.env['hr.salary.rule.category'].search([], limit=1)
        self.salary_rule = self.env['hr.salary.rule'].search([], limit=1)
        self.vals = {'name': 'Probe August', 'date_start': '2026-08-01',
                     'date_end': '2026-08-31'}

    # ------------------------------------------------------------ fixtures
    def _slip(self, run=None, lines=True):
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': 'August slip',
            'contract_id': self.contract.id,
            'payslip_run_id': run.id if run else False,
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'company_id': self.company.id})
        if lines:
            self.env['hr.payslip.line'].create({
                'slip_id': slip.id, 'name': 'Net pay', 'code': 'NETPAY',
                'amount': 1000.0, 'quantity': 1.0, 'rate': 100.0,
                'employee_id': slip.employee_id.id,
                'contract_id': slip.contract_id.id,
                'category_id': self.category.id,
                'salary_rule_id': self.salary_rule.id})
        return slip

    def _august(self, kind='regular', name='August regular'):
        run = self.Run.create({'name': name, 'date_start': '2026-08-01',
                               'date_end': '2026-08-31', 'pb_run_kind': kind})
        self._slip(run)
        return run

    # ================================================================ T21
    def test_t21_prepare_run_writes_the_kind_picked(self):
        top = self.Wizard.prepare_run(dict(self.vals, run_kind='topup'))
        self.assertEqual(self.Run.browse(top['run_id']).pb_run_kind, 'topup')
        # no key at all (PayAI, every caller before R8) is a Regular run
        plain = self.Wizard.prepare_run(dict(self.vals, name='Probe August 2',
                                             date_start='2026-09-01',
                                             date_end='2026-09-30'))
        self.assertEqual(self.Run.browse(plain['run_id']).pb_run_kind, 'regular')

    def test_t21_create_and_compute_writes_the_kind_picked(self):
        # nothing to compute here (no structure), but the run is created first
        before = set(self.Run.search([]).ids)
        self.Wizard.create_and_compute(dict(self.vals, run_kind='topup'))
        made = self.Run.search([('id', 'not in', list(before))])
        self.assertEqual(len(made), 1)
        self.assertEqual(made.pb_run_kind, 'topup')

    def test_t21_an_unknown_kind_is_a_regular_run(self):
        prep = self.Wizard.prepare_run(dict(self.vals, run_kind='bonus'))
        self.assertEqual(self.Run.browse(prep['run_id']).pb_run_kind, 'regular')

    # ======================================================= safety rail
    def test_a_topup_does_not_meet_the_months_regular_run(self):
        regular = self._august()
        prep = self.Wizard.prepare_run(dict(self.vals, run_kind='topup'))
        # no "this month's payroll already exists", no Clean and Run offer
        self.assertFalse(prep.get('needs_confirmation'))
        self.assertTrue(prep.get('run_id'))
        self.assertTrue(regular.exists())
        self.assertEqual(len(regular.slip_ids), 1)

    def test_a_topup_with_force_clean_never_clears_a_regular_run(self):
        regular = self._august()
        slip = regular.slip_ids
        for path in ('prepare_run', 'create_and_compute'):
            getattr(self.Wizard, path)(dict(self.vals, run_kind='topup',
                                            force_clean=True))
            self.assertTrue(regular.exists(), path)
            self.assertTrue(slip.exists(), path)
            self.assertEqual(slip.payslip_run_id, regular, path)

    def test_a_topup_never_adopts_the_months_loose_payslips(self):
        loose = self._slip()
        prep = self.Wizard.prepare_run(dict(self.vals, run_kind='topup'))
        self.assertEqual(prep['adopted'], 0)
        self.assertFalse(loose.payslip_run_id)
        self.assertIn(self.employee.id, prep['emp_ids'])
        plan = self.Wizard.plan_preview(dict(self.vals, run_kind='topup'))
        self.assertEqual(plan['adopt'], 0)

    def test_a_second_topup_asks_and_clears_only_the_topup(self):
        regular = self._august()
        topup = self._august('topup', name='August awards')
        prep = self.Wizard.prepare_run(dict(self.vals, run_kind='topup'))
        self.assertTrue(prep.get('needs_confirmation'))
        self.assertEqual(prep.get('kind'), 'exists')
        self.assertIn('top-up', prep['message'])
        self.assertIn('August awards', prep['message'])
        self.assertNotIn('August regular', prep['message'])
        plan = self.Wizard.plan_preview(dict(self.vals, run_kind='topup'))
        self.assertEqual([r['id'] for r in plan['existing']], [topup.id])
        again = self.Wizard.prepare_run(dict(self.vals, run_kind='topup',
                                             force_clean=True))
        self.assertTrue(again.get('run_id'))
        self.assertFalse(topup.exists())
        self.assertTrue(regular.exists())
        self.assertEqual(len(regular.slip_ids), 1)

    # ----------------------------- R9: a Regular run ignores top-ups
    def test_a_regular_run_does_not_meet_the_months_topup(self):
        """R9 (owner, 2026-11-04): the mirror of the top-up rail. Making the
        regular month after a top-up asks nothing about the top-up."""
        topup = self._august('topup', name='August awards')
        for vals in (dict(self.vals), dict(self.vals, run_kind='regular')):
            plan = self.Wizard.plan_preview(vals)
            self.assertEqual(plan['existing'], [])
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertFalse(prep.get('needs_confirmation'))
        self.assertEqual(self.Run.browse(prep['run_id']).pb_run_kind, 'regular')
        self.assertTrue(topup.exists())
        self.assertEqual(len(topup.slip_ids), 1)

    def test_a_regular_run_with_force_clean_never_clears_a_topup(self):
        topup = self._august('topup', name='August awards')
        slip = topup.slip_ids
        for path in ('prepare_run', 'create_and_compute'):
            getattr(self.Wizard, path)(dict(self.vals, force_clean=True))
            self.assertTrue(topup.exists(), path)
            self.assertTrue(slip.exists(), path)
            self.assertEqual(slip.payslip_run_id, topup, path)

    def test_a_second_regular_run_asks_and_clears_only_the_regular(self):
        regular = self._august()
        topup = self._august('topup', name='August awards')
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertTrue(prep.get('needs_confirmation'))
        self.assertIn('August regular', prep['message'])
        self.assertNotIn('August awards', prep['message'])
        again = self.Wizard.prepare_run(dict(self.vals, force_clean=True))
        self.assertTrue(again.get('run_id'))
        self.assertFalse(regular.exists())
        self.assertTrue(topup.exists())
        self.assertEqual(len(topup.slip_ids), 1)

    def test_the_clean_itself_refuses_the_other_kind(self):
        """A second rail behind the guard: whatever reaches `_clean_period`
        with a kind, the other kind is never cleared."""
        regular = self._august()
        topup = self._august('topup', name='August awards')
        self.Wizard.sudo()._clean_period((regular | topup).sudo(), kind='regular')
        self.assertFalse(regular.exists())
        self.assertTrue(topup.exists())
        again = self._august()
        self.Wizard.sudo()._clean_period((again | topup).sudo(), kind='topup')
        self.assertTrue(again.exists())
        self.assertFalse(topup.exists())

    def test_regular_adoption_and_the_kind_blind_answer_are_unchanged(self):
        """Loose payslips belong to no run, so a Regular run still adopts
        them (as before); `_period_runs` with no kind is still kind-blind
        for direct callers."""
        topup = self._august('topup', name='August awards')
        self.assertEqual(self.Wizard._period_runs('2026-08-01', '2026-08-31'),
                         topup)
        loose = self._slip()
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertEqual(prep['adopted'], 1)
        self.assertEqual(loose.payslip_run_id.id, prep['run_id'])

    def test_the_first_step_offers_the_choice(self):
        self.assertTrue(self.Wizard.get_defaults().get('run_kinds'))
