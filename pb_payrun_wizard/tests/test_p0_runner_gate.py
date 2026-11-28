# -*- coding: utf-8 -*-
"""PAYAI P0 — the Run Payroll door has a lock, and *Clean and Run* has rails.

Before this: `pb.payrun.wizard` is an AbstractModel (no ACL row), every public
method was callable by any authenticated session, and `prepare_run` /
`compute_batch` ran as sudo. The menu hid the screen; nothing else did.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP0RunnerGate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        base = [cls.env.ref('base.group_user').id]
        cls.officer = Users.create({
            'name': 'P0 officer', 'login': 'p0.officer@test.invalid',
            'company_id': cls.env.company.id,
            'company_ids': [(6, 0, cls.env.company.ids)],
            'group_ids': [(6, 0, base + [cls.env.ref(
                'pb_hr_payroll_base.group_payroll_base_officer').id])]})
        cls.plain = Users.create({
            'name': 'P0 plain', 'login': 'p0.plain@test.invalid',
            'company_id': cls.env.company.id,
            'company_ids': [(6, 0, cls.env.company.ids)],
            'group_ids': [(6, 0, base)]})
        cls.portal = Users.create({
            'name': 'P0 portal', 'login': 'p0.portal@test.invalid',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.Wizard = cls.env['pb.payrun.wizard']
        cls.Run = cls.env['hr.payslip.run']
        cls.employee = cls.env['hr.employee'].create({
            'name': 'P0 Person', 'company_id': cls.env.company.id})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'P0 contract', 'employee_id': cls.employee.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': cls.env.company.id})

    def _run(self, state='draft', slip_state='draft', ds='2026-06-01',
             de='2026-06-30', company=None):
        run = self.Run.create({'name': 'P0 %s' % state,
                               'date_start': ds, 'date_end': de})
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': 'P0 slip',
            'contract_id': self.contract.id, 'payslip_run_id': run.id,
            'date_from': ds, 'date_to': de,
            'company_id': (company or self.env.company).id})
        if slip_state != 'draft':
            slip.write({'state': slip_state})
        if state != 'draft':
            run.write({'state': state})       # test env is su: the seal opens
        return run

    # ------------------------------------------------------------ the lock
    def test_portal_sign_in_is_refused_at_the_door(self):
        with self.assertRaises(AccessError):
            self.Wizard.with_user(self.portal).get_defaults()
        with self.assertRaises(AccessError):
            self.Wizard.with_user(self.portal).prepare_run(
                {'date_start': '2026-06-01', 'date_end': '2026-06-30'})

    def test_internal_user_without_a_payroll_role_is_refused(self):
        self.assertFalse(self.Wizard._may_run_payroll(self.plain))
        for method, args in (('get_defaults', []),
                             ('prepare_run', [{'date_start': '2026-06-01',
                                               'date_end': '2026-06-30'}]),
                             ('compute_batch', [{'run_id': 0, 'emp_ids': []}]),
                             ('get_summary', [0]),
                             ('attach_spreadsheet', [0, 0, '', '', None, None]),
                             ('discard_empty_run', [0]),
                             ('submit_for_approval', [0])):
            with self.assertRaises(AccessError, msg=method):
                getattr(self.Wizard.with_user(self.plain), method)(*args)

    def test_the_payroll_officer_role_still_opens_the_door(self):
        self.assertTrue(self.Wizard._may_run_payroll(self.officer))
        defaults = self.Wizard.with_user(self.officer).get_defaults()
        self.assertIn('eligible', defaults)

    def test_a_role_granted_create_on_runs_passes_without_a_named_group(self):
        """Access-home roles grant rights, not group names: the right is the door."""
        group = self.env['res.groups'].create({'name': 'P0 run makers'})
        self.env['ir.model.access'].create({
            'name': 'p0 run makers', 'model_id': self.env.ref(
                'om_hr_payroll.model_hr_payslip_run').id,
            'group_id': group.id, 'perm_read': True, 'perm_write': True,
            'perm_create': True, 'perm_unlink': False})
        self.plain.write({'group_ids': [(4, group.id)]})
        self.assertTrue(self.Wizard._may_run_payroll(self.plain))

    # ------------------------------------------------------- the period
    def test_a_period_whose_first_day_is_after_its_last_is_refused(self):
        with self.assertRaises(UserError):
            self.Wizard._check_period('2026-06-30', '2026-06-01')
        with self.assertRaises(UserError):
            self.Wizard._check_period(None, '2026-06-30')
        with self.assertRaises(UserError):
            self.Wizard._check_period('2025-01-01', '2026-06-30')
        self.assertEqual(
            [str(d) for d in self.Wizard._check_period('2026-06-01', '2026-06-30')],
            ['2026-06-01', '2026-06-30'])

    # -------------------------------------------------- clean-and-run rails
    def test_a_draft_run_may_be_cleared(self):
        run = self._run()
        self.assertEqual(self.Wizard._clean_blockers(run), [])

    def test_finished_payroll_is_never_cleared(self):
        done = self._run(state='done', slip_state='done')
        pending = self._run(state='approval_pending')
        for run in (done, pending):
            if getattr(run, 'is_demo', False):
                self.skipTest('demo runs are clearable by design')
            blockers = self.Wizard._clean_blockers(run)
            self.assertTrue(blockers, run.state)
            self.assertIn(run.name, ' '.join(blockers))
            with self.assertRaises(UserError):
                self.Wizard.sudo()._clean_period(run.sudo())
            self.assertTrue(run.exists(), 'the run was deleted anyway')
        answer = self.Wizard._protected_answer(self.Wizard._clean_blockers(done))
        self.assertTrue(answer['blocked'])
        self.assertFalse(answer['needs_confirmation'])
        self.assertIn('Runs board', answer['message'])

    def test_prepare_run_answers_blocked_over_an_approved_month(self):
        configs = self.Wizard._formula_configs()
        if configs and len(configs) > 1:
            self.skipTest('this company runs several schemes; the scheme '
                          'question comes first here')
        done = self._run(state='done', slip_state='done')
        if getattr(done, 'is_demo', False):
            self.skipTest('demo runs are clearable by design')
        before = self.Run.search_count([])
        answer = self.Wizard.prepare_run({
            'name': 'P0 June again', 'date_start': '2026-06-01',
            'date_end': '2026-06-30', 'force_clean': True})
        self.assertTrue(answer.get('blocked'), answer)
        self.assertEqual(self.Run.search_count([]), before,
                         'force_clean created or deleted a run')
        self.assertTrue(done.exists())

    # --------------------------------------------- company scoping
    def test_another_companys_month_is_not_this_companys_duplicate(self):
        if 'company_id' in self.Run._fields:
            self.skipTest('runs carry a company on this build')
        other = self.env['res.company'].create({'name': 'P0 Other Co'})
        emp = self.env['hr.employee'].create({'name': 'P0 Other Person',
                                              'company_id': other.id})
        con = self.env['hr.contract'].create({
            'name': 'P0 other contract', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open', 'date_start': '2020-01-01', 'company_id': other.id})
        run = self.Run.create({'name': 'P0 other June',
                               'date_start': '2026-06-01', 'date_end': '2026-06-30'})
        self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'P0 other slip', 'contract_id': con.id,
            'payslip_run_id': run.id, 'date_from': '2026-06-01',
            'date_to': '2026-06-30', 'company_id': other.id})
        mine = self._run()
        # creating a company attaches it to the creator; ask as someone whose
        # switched-on companies are only the first one
        found = self.Wizard.with_context(
            allowed_company_ids=[self.env.company.id])._period_runs(
                '2026-06-01', '2026-06-30')
        self.assertIn(mine, found)
        self.assertNotIn(run, found, "another company's June was read as ours")
