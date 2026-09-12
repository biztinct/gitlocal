# -*- coding: utf-8 -*-
"""A pay run on the approval engine.

Replaces `test_approval_chain.py` and `test_officer_tier_switch.py`, which
tested a ladder that no longer exists. Every case here runs the REAL path — the
engine's own `submit` and `decide` as the real acting user — because the whole
point of the phase is that nothing about who signs a pay run off is written in
this module any more.

WHAT HAD TO BE FABRICATED. There is no payroll demo data on the local runtime,
so each case builds the minimum by hand: one company, two employees in two
departments, a salary rule to hang lines off, and payslips whose category-coded
lines make the totals real. The approval side is built through the engine's own
public API (a workflow, a published version, a binding, responsibilities), which
is exactly what the seed does on a real install.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


def _route(steps):
    return {
        'schema_version': 1,
        'steps': steps,
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': False,
            'self_exception': {'enabled': False},
            # 'different' and 'reason' are the only two the schema knows;
            # every step here is decided by a different person anyway.
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


def _step(key, role, title, kind='approve', scope='company'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'role', 'role': role, 'scope': scope},
            'min_amount': 0, 'condition': None}


def _fast():
    return {'key': 'fast', 'kind': 'fast', 'title': 'No approval needed',
            'who': {'mode': 'people', 'user_ids': []},
            'min_amount': 0, 'condition': None}


@tagged('post_install', '-at_install')
class PayrunApprovalCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['biz.approval.engine']
        cls.Run = cls.env['hr.payslip.run']
        cls.process = cls.env['biz.approval.process']._by_key('payrun')
        if not cls.process:
            cls.skip_all = True
            return
        cls.skip_all = False
        cls.company = cls.env.company
        cls.rule = cls.env['hr.salary.rule'].search([], limit=1)

        cls.hr_dept = cls.env['hr.department'].create(
            {'name': 'AP Retail', 'company_id': cls.company.id})
        cls.other_dept = cls.env['hr.department'].create(
            {'name': 'AP Factory', 'company_id': cls.company.id})

        cls.preparer = cls._user('ap_preparer', 'Pat Preparer')
        cls.hr = cls._user('ap_hr', 'Hana HR')
        cls.finance = cls._user('ap_finance', 'Finn Finance')

        cls.emp_a = cls._employee('AP Alpha', cls.hr_dept)
        cls.emp_b = cls._employee('AP Bravo', cls.hr_dept)

    @classmethod
    def _user(cls, login, name):
        """An approver who can actually OPEN a pay run.

        Configuring a person never grants access (ledger): holding a
        responsibility is not the same as being allowed to read the thing. The
        engine re-checks the record's own access before it accepts a decision,
        so an approver with no pay-run access is refused — correctly. These
        fixtures therefore carry the officer role, which is what a real
        approver would be given in Access.
        """
        groups = [cls.env.ref('base.group_user').id]
        officer = cls.env.ref(
            'pb_hr_payroll_base.group_payroll_base_officer',
            raise_if_not_found=False)
        if officer:
            groups.append(officer.id)
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)],
            })

    @classmethod
    def _employee(cls, name, department):
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id,
            'department_id': department.id})
        cls.env['hr.contract'].create({
            'name': '%s contract' % name, 'employee_id': employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': cls.company.id})
        return employee

    def setUp(self):
        super().setUp()
        if self.skip_all:
            self.skipTest('the approval catalogue is not installed here')

    # ------------------------------------------------------------ fixtures
    def _category(self, code):
        found = self.env['hr.salary.rule.category'].search(
            [('code', '=', code)], limit=1)
        if not found:
            self.skipTest("no '%s' salary-rule category in this database" % code)
        return found

    def _run(self, name='AP June'):
        return self.Run.create({
            'name': name, 'date_start': '2026-06-01', 'date_end': '2026-06-30'})

    def _slip(self, run, employee, net=1000.0, config=None):
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', employee.id)], limit=1)
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'AP slip %s' % employee.name,
            'contract_id': contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id,
            'payslip_run_id': run.id,
        })
        if config is not None and 'formula_config_id' in slip._fields:
            slip.formula_config_id = config.id
        self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'name': 'NET', 'code': 'NET',
            'amount': net, 'quantity': 1.0, 'rate': 100.0,
            'employee_id': employee.id, 'contract_id': contract.id,
            'category_id': self._category('NET').id,
            'salary_rule_id': self.rule.id,
        })
        return slip

    def _config(self, Config, name, code, **extra):
        """A pay scheme. `country_code` is required on this model, and a
        fixture that leaves it out fails on the database constraint rather
        than on anything the case is about."""
        values = {'name': name, 'code': code,
                  'company_id': self.company.id}
        if 'country_code' in Config._fields:
            values['country_code'] = (
                self.company.country_id.code or 'VN')
        values.update(extra)
        return Config.create(values)

    def _hold(self, role_key, user, scope_key=''):
        role = self.env['biz.approval.role'].search(
            [('key', '=', role_key)], limit=1)
        if not role:
            self.skipTest("the '%s' responsibility is not in this database"
                          % role_key)
        existing = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', scope_key), ('active', '=', True)], limit=1)
        if existing:
            existing.write({'user_id': user.id})
            return existing
        return self.env['biz.approval.responsibility'].sudo().create({
            'company_id': self.company.id, 'role_id': role.id,
            'scope_key': scope_key, 'scope_label': scope_key or self.company.name,
            'user_id': user.id})

    def _bind(self, definition, scope_key='', kind_key='any',
              name='AP route'):
        """A published route, bound where the test needs it.

        Any binding this company already has for the same place is retired
        first: the engine treats two live bindings on one scope as a structural
        error, which is exactly right and exactly not what a test means to
        create when it replaces the seeded default.
        """
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', scope_key),
            ('kind_key', '=', kind_key),
            ('active', '=', True)]).write({'active': False})
        workflow = self.env['biz.approval.workflow'].sudo().create({
            'name': name, 'company_id': self.company.id,
            'process_id': self.process.id,
            'owner_user_id': self.env.user.id})
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id, 'revision': 1, 'status': 'draft',
            'definition': definition})
        checks = self.engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'], checks['errors'])
        self.engine.publish(version.id, version.draft_revision, None, 'test',
                            [w['code'] for w in checks['warnings']])
        Binding.create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'scope_key': scope_key, 'scope_label': scope_key or self.company.name,
            'kind_key': kind_key, 'workflow_id': workflow.id, 'mode': 'follow'})
        return workflow

    def _two_step_route(self):
        self._hold('hr_lead', self.hr)
        self._hold('finance', self.finance)
        return self._bind(_route([
            _step('s1', 'hr_lead', 'HR review', kind='review'),
            _step('s2', 'finance', 'Finance approval'),
        ]))

    def _submit(self, run, user=None):
        user = user or self.env.user
        return self.engine.with_user(user).submit(run.with_user(user))

    # =================================================================== R01
    def test_r01_submitting_freezes_the_run(self):
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a, net=1000.0)
        self._slip(run, self.emp_b, net=2000.0)

        payload = self._submit(run)
        self.assertEqual(payload['state'], 'pending')
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending')
        self.assertTrue(all(s.state == 'verify' for s in run.slip_ids))
        self.assertTrue(run.pb_source_revision)

        request = run.approval_request_id
        self.assertEqual(request.facts['net_total']['value'], 3000.0)
        self.assertEqual(request.facts['payslip_count']['value'], 2)
        self.assertEqual(request.facts['employee_count']['value'], 2)
        self.assertEqual(request.amount, 3000.0)
        # A UNIT IS A WORD, NOT A TYPE (ledger AM25).
        self.assertEqual(request.facts['net_total']['unit'],
                         self.company.currency_id.name)
        self.assertEqual(request.facts['payslip_count']['unit'], '')

    def test_r01b_an_empty_run_cannot_be_sent_in(self):
        self._two_step_route()
        run = self._run()
        with self.assertRaises(UserError):
            self._submit(run)

    # =================================================================== R02
    def test_r02_a_mixed_run_is_refused_and_splits_conserving_everything(self):
        if 'formula_config_id' not in self.env['hr.payslip']._fields:
            self.skipTest('the formula engine is not installed here')
        self._two_step_route()
        Config = self.env['hr.formula.config']
        retail = self._config(Config, 'AP Retail scheme', 'APRETAIL')
        factory = self._config(Config, 'AP Factory scheme', 'APFACTORY')
        run = self._run()
        self._slip(run, self.emp_a, net=1000.0, config=retail)
        self._slip(run, self.emp_b, net=2000.0, config=factory)

        with self.assertRaises(UserError):
            self._submit(run)

        before_net = run.pb_total_net
        before_slips = set(run.slip_ids.ids)
        run_id = run.id
        result = run.action_split_review_groups()

        children = self.Run.browse(result['domain'][0][2])
        self.assertEqual(len(children), 2)
        # every payslip once, and only once
        after_slips = set()
        for child in children:
            self.assertFalse(after_slips & set(child.slip_ids.ids),
                             'a payslip landed in two runs')
            after_slips |= set(child.slip_ids.ids)
        self.assertEqual(after_slips, before_slips)
        # and the money adds back up
        self.assertAlmostEqual(
            sum(child.pb_total_net for child in children), before_net, 2)
        # the source is gone, not left empty
        self.assertFalse(self.Run.browse(run_id).exists())
        # each child is submittable on its own
        for child in children:
            self.engine.submit(child)
            child.invalidate_recordset()
            self.assertEqual(child.state, 'approval_pending')

    def test_r02b_a_homogeneous_run_refuses_to_split(self):
        run = self._run()
        self._slip(run, self.emp_a)
        self._slip(run, self.emp_b)
        with self.assertRaises(UserError):
            run.action_split_review_groups()

    # =================================================================== R03
    def test_r03_the_whole_route_finishes_the_run(self):
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a, net=1000.0)
        self._submit(run)
        request = run.approval_request_id

        self.engine.with_user(self.hr).decide(request.id, 's1', 'approve')
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending',
                         'one approval out of two must not finish a run')

        self.engine.with_user(self.finance).decide(request.id, 's2', 'approve')
        run.invalidate_recordset()
        request.invalidate_recordset()
        self.assertEqual(run.state, 'done')
        self.assertTrue(all(s.state == 'done' for s in run.slip_ids))
        self.assertEqual(request.state, 'applied')

    def test_r03b_a_second_apply_changes_nothing(self):
        """Idempotent, because the engine may retry a blocked apply."""
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a)
        self._submit(run)
        request = run.approval_request_id
        self.engine.with_user(self.hr).decide(request.id, 's1', 'approve')
        self.engine.with_user(self.finance).decide(request.id, 's2', 'approve')
        run.invalidate_recordset()
        self.assertTrue(run._approval_apply(request))
        self.assertEqual(run.state, 'done')

    # =================================================================== R04
    def test_r04_sending_it_back_makes_it_editable_again(self):
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a)
        self._submit(run)
        request = run.approval_request_id

        self.engine.with_user(self.hr).decide(
            request.id, 's1', 'return', reason='The overtime is wrong')
        run.invalidate_recordset()
        self.assertEqual(run.state, 'draft')
        self.assertTrue(all(s.state == 'draft' for s in run.slip_ids))
        self.assertEqual(run.pb_return_note, 'The overtime is wrong')
        self.assertEqual(run.pb_return_uid, self.hr)

        self._submit(run)
        run.invalidate_recordset()
        self.assertEqual(run.approval_request_id.attempt, 2)
        self.assertFalse(run.pb_return_note,
                         'the note is cleared when the run is sent in again')

    # =================================================================== R05
    def test_r05_a_run_whose_numbers_moved_cannot_be_applied(self):
        self._two_step_route()
        run = self._run()
        slip = self._slip(run, self.emp_a, net=1000.0)
        self._submit(run)
        request = run.approval_request_id

        # somebody edits the pay data while the approval is open
        slip.line_ids[0].write({'amount': 9999.0})
        slip.line_ids[0].flush_recordset()
        run.invalidate_recordset()

        self.engine.with_user(self.hr).decide(request.id, 's1', 'approve')
        self.engine.with_user(self.finance).decide(request.id, 's2', 'approve')
        run.invalidate_recordset()
        request.invalidate_recordset()
        self.assertNotEqual(run.state, 'done',
                            'an approval must not cover numbers that moved')
        self.assertEqual(request.state, 'approved')
        self.assertTrue(request.block_reason)

    def test_r05b_the_stamp_survives_the_freeze(self):
        """Sending a run in stamps every payslip with a new write_date. A
        revision that counted that would differ from itself immediately."""
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a)
        before = run._pb_source_revision()
        self._submit(run)
        run.invalidate_recordset()
        self.assertEqual(run._pb_source_revision(), before)

    # =================================================================== R06
    def test_r06_a_payslip_cannot_be_finished_behind_its_run(self):
        self._two_step_route()
        run = self._run()
        slip = self._slip(run, self.emp_a)
        self._submit(run)
        with self.assertRaises(UserError):
            slip.action_payslip_done()

    def test_r06e_nor_on_a_run_nobody_has_even_sent_in(self):
        """The bank export pays every payslip in state `done`, so a DRAFT run
        is the more dangerous half of this rail, not the safer one."""
        run = self._run()
        slip = self._slip(run, self.emp_a)
        with self.assertRaises(UserError):
            slip.action_payslip_done()
        with self.assertRaises(UserError):
            slip.action_payslip_level2_done()

    def test_r06f_a_payslip_with_no_run_is_untouched(self):
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', self.emp_a.id)], limit=1)
        loose = self.env['hr.payslip'].create({
            'employee_id': self.emp_a.id, 'name': 'AP loose',
            'contract_id': contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id})
        loose.action_payslip_done()
        self.assertNotEqual(loose.state, 'draft')

    def test_r06b_a_raw_state_write_is_refused(self):
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a)
        with self.assertRaises(AccessError):
            run.with_user(self.preparer).write({'state': 'done'})

    def test_r06c_a_run_cannot_be_created_already_approved(self):
        with self.assertRaises(AccessError):
            self.Run.with_user(self.preparer).create({
                'name': 'Born done', 'date_start': '2026-06-01',
                'date_end': '2026-06-30', 'state': 'done'})

    def test_r06d_the_old_ladder_methods_refuse(self):
        run = self._run()
        self._slip(run, self.emp_a)
        with self.assertRaises(UserError):
            run.action_payslip_run_level1_done()
        with self.assertRaises(UserError):
            run.action_payslip_run_level2_done()

    # =================================================================== R07
    def test_r07_a_fast_lane_applies_at_once(self):
        self._bind(_route([_fast()]), name='AP fast lane')
        run = self._run()
        self._slip(run, self.emp_a)
        self._submit(run)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'done')
        self.assertEqual(run.approval_request_id.state, 'applied')

    def test_r07b_a_run_with_no_route_at_all_is_refused(self):
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([('company_id', '=', self.company.id),
                        ('process_id', '=', self.process.id),
                        ('active', '=', True)]).write({'active': False})
        run = self._run()
        self._slip(run, self.emp_a)
        with self.assertRaises(UserError):
            self._submit(run)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'draft',
                         'a refused submission leaves the run alone')

    # =================================================================== R08
    def test_r08_an_exact_kind_beats_any_kind(self):
        if 'formula_config_id' not in self.env['hr.payslip']._fields:
            self.skipTest('the formula engine is not installed here')
        self._hold('hr_lead', self.hr)
        self._hold('finance', self.finance)
        self._bind(_route([_step('s1', 'hr_lead', 'Any kind', kind='review')]),
                   kind_key='any', name='AP any kind')
        self._bind(_route([_step('s1', 'finance', 'Final settlement only')]),
                   kind_key='full_final', name='AP final settlement')

        config = self._config(self.env['hr.formula.config'], 'AP leavers',
                              'APLEAVE', cycle_type='full_final')
        run = self._run()
        self._slip(run, self.emp_a, config=config)
        if 'pb_formula_config_id' in run._fields:
            run.pb_formula_config_id = config.id
        self._submit(run)
        self.assertEqual(run.approval_request_id.version_id.workflow_id.name,
                         'AP final settlement')

    # =================================================================== R09
    def test_r09_analytics_can_no_longer_finish_a_pay_run(self):
        """Read as TEXT, not imported: the analytics module is not a dependency
        of this one and may not be installed, and the claim being made is about
        what the file says rather than about what is loaded."""
        import os
        here = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        path = os.path.join(here, 'payroll_analytics_approval', 'models',
                            'payroll_analytics.py')
        if not os.path.exists(path):
            self.skipTest('the analytics module is not in this checkout')
        # Comments stripped first: the block that was removed is DESCRIBED in
        # a comment where it used to be, and a check that could not tell the
        # two apart would fail on the explanation of its own fix.
        code = '\n'.join(
            line for line in open(path, encoding='utf-8').read().splitlines()
            if not line.lstrip().startswith('#'))
        self.assertNotIn('runs_to_finalize', code,
                         'the analytics screen must not finish a pay run')
        self.assertNotIn('action_payslip_run_level2_done', code)

    # =================================================================== R11
    def test_r11_the_seeded_route_is_the_one_the_company_had(self):
        """Day one behaves like day zero: a published route, bound company-wide,
        with the old groups' holders in its seats."""
        company = self.env['res.company'].create({'name': 'AP Seedco'})
        self.Run._approval_seed_default(company)
        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', ''), ('active', '=', True)])
        self.assertEqual(len(binding), 1)
        version = binding.workflow_id.published_version_id
        self.assertTrue(version, 'the default route must be published')
        titles = [s['title'] for s in version.definition['steps']]
        self.assertEqual(titles,
                         ['Payroll check', 'HR lead review', 'Finance approval'])
        # and running it twice creates exactly one of everything
        self.Run._approval_seed_default(company)
        self.assertEqual(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', company.id),
            ('process_id', '=', self.process.id), ('active', '=', True)]), 1)

    def test_r11b_the_migration_refuses_to_run_over_a_mid_chain_run(self):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'migrations', '19.0.2.0.0', 'pre-retire_tier_chain.py')
        spec = importlib.util.spec_from_file_location('pb_retire', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        run = self._run('AP stuck')
        self.env.cr.execute(
            "UPDATE hr_payslip_run SET state = 'level1' WHERE id = %s",
            (run.id,))
        with self.assertRaises(Exception) as caught:
            module.migrate(self.env.cr, '19.0.1.19.0')
        self.assertIn('AP stuck', str(caught.exception))
        self.env.cr.execute(
            "UPDATE hr_payslip_run SET state = 'draft' WHERE id = %s",
            (run.id,))

    # ------------------------------------------------------ the board reads
    def test_the_board_only_offers_what_the_model_has(self):
        from odoo.addons.pb_payruns.models import pb_payruns as board
        states = set(dict(self.Run._fields['state'].selection))
        self.assertEqual(states,
                         {'draft', 'approval_pending', 'done', 'cancel'})
        self.assertTrue(set(board.STAGE_ORDER) <= states)

    def test_awaiting_me_finds_the_run_i_have_to_decide(self):
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a)
        self._submit(run)
        found = self.Run.with_user(self.hr).search(
            [('pb_awaiting_me', '=', True)])
        self.assertIn(run.id, found.ids)
        self.assertNotIn(
            run.id,
            self.Run.with_user(self.finance).search(
                [('pb_awaiting_me', '=', True)]).ids,
            'a later step is not yet anybody\'s to decide')

    def test_rejecting_a_pending_run_withdraws_its_approval(self):
        self._two_step_route()
        run = self._run()
        self._slip(run, self.emp_a)
        self._submit(run)
        request = run.approval_request_id
        run.with_context(pb_reject_note='Wrong month').action_payslip_run_cancel()
        run.invalidate_recordset()
        request.invalidate_recordset()
        self.assertEqual(run.state, 'cancel')
        self.assertEqual(run.pb_reject_note, 'Wrong month')
        self.assertEqual(request.state, 'cancelled')
