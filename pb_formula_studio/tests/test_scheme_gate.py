# -*- coding: utf-8 -*-
"""S06 / S09 (studio half) — merge, release and roll-back go through a proposal.

The three doors are defined in this module, so the tests for them live beside
them. Everything runs the real path: `scheme_propose` makes the proposal and
sends it in, the engine's own `decide` approves it, and the door runs from the
apply — never from the test.
"""
from odoo.tests import TransactionCase, tagged


def _route(steps):
    return {
        'schema_version': 1,
        'steps': steps,
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': False,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


def _step(key, role, title, kind='approve'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'role', 'role': role, 'scope': 'company'},
            'min_amount': 0, 'condition': None}


@tagged('post_install', '-at_install')
class SchemeGateCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['biz.approval.engine']
        cls.Studio = cls.env['pb.formula.studio']
        cls.process = cls.env['biz.approval.process']._by_key('scheme')
        cls.company = cls.env.company
        # The person who approves a scheme change CARRIES IT OUT, as
        # themselves, and the apply re-checks their own rights on the scheme
        # (safety rail 7). An approver with no scheme rights is a real and
        # deliberate refusal — it is just not what these cases are about.
        groups = [cls.env.ref('base.group_user').id]
        manager = cls.env.ref('pb_hr_payroll_formula.group_formula_manager',
                              raise_if_not_found=False)
        if manager:
            groups.append(manager.id)
        cls.approver = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Ada Approver', 'login': 'sg_approver',
                'email': 'sg_approver@example.com',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)],
            })

    def setUp(self):
        super().setUp()
        if not self.process:
            self.skipTest('the approval catalogue is not installed here')

    # ------------------------------------------------------------ fixtures
    def _clear_payrun_gap(self, config):
        """`pb_payruns` refuses to activate a scheme whose PAY RUNS could not
        be approved (ledger AM35) — a different rail, and a true one. These
        cases are about the scheme-change route, so the pay-run one is filled
        in rather than worked around."""
        process = self.env['biz.approval.process']._by_key('payrun')
        if not process:
            return
        Role = self.env['biz.approval.role'].sudo()
        Responsibility = self.env['biz.approval.responsibility'].sudo()
        for key in ('payroll_mgr', 'hr_lead', 'finance', 'director',
                    'scheme_owner', 'approver'):
            role = Role.search([('key', '=', key)], limit=1)
            if not role:
                continue
            for scope in ('', 'scheme:%s' % config.id):
                held = Responsibility.search([
                    ('company_id', '=', self.company.id),
                    ('role_id', '=', role.id), ('scope_key', '=', scope),
                    ('active', '=', True)], limit=1)
                if held:
                    continue
                Responsibility.create({
                    'company_id': self.company.id, 'role_id': role.id,
                    'scope_key': scope,
                    'scope_label': scope or self.company.name,
                    'user_id': self.env.user.id})

    def _config(self, name, code, state='active'):
        config = self.env['hr.formula.config'].create({
            'name': name, 'code': code, 'country_code': 'VN',
            'company_id': self.company.id, 'state': state})
        self._clear_payrun_gap(config)
        # `category_id` is NOT NULL on `hr.payslip.line` — a component with no
        # category takes a computation down at INSERT time.
        category = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'BASIC')], limit=1) \
            or self.env['hr.salary.rule.category'].search([], limit=1)
        values = {'category_id': category.id} if category else {}
        self.env['hr.formula.rule'].create(dict(values, **{
            'config_id': config.id, 'name': 'Basic', 'code': 'SGBASIC',
            'column_type': 'input', 'sequence': 10}))
        self.env['hr.formula.rule'].create(dict(values, **{
            'config_id': config.id, 'name': 'Gross', 'code': 'SGGROSS',
            'column_type': 'formula', 'excel_formula': '=A1',
            'sequence': 20}))
        return config

    def _one_step_route(self):
        role = self.env['biz.approval.role'].search(
            [('key', '=', 'payroll_mgr')], limit=1)
        if not role:
            self.skipTest('the responsibility catalogue is not here')
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        if held:
            held.write({'user_id': self.approver.id})
        else:
            self.env['biz.approval.responsibility'].sudo().create({
                'company_id': self.company.id, 'role_id': role.id,
                'scope_key': '', 'scope_label': self.company.name,
                'user_id': self.approver.id})
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('active', '=', True)]).write({'active': False})
        workflow = self.env['biz.approval.workflow'].sudo().create({
            'name': 'SG route', 'company_id': self.company.id,
            'process_id': self.process.id,
            'owner_user_id': self.env.user.id})
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id, 'revision': 1, 'status': 'draft',
            'definition': _route([_step('s1', 'payroll_mgr',
                                        'Payroll manager')])})
        checks = self.engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'], checks['errors'])
        self.engine.publish(version.id, version.draft_revision, None, 'test',
                            [w['code'] for w in checks['warnings']])
        Binding.create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'scope_key': '', 'scope_label': self.company.name,
            'kind_key': 'any', 'workflow_id': workflow.id, 'mode': 'follow'})
        return workflow

    def _branch_with_a_change(self, parent, formula='=A1*2'):
        result = self.Studio.branch_create(parent.id, 'SG branch')
        self.assertTrue(result.get('ok'), result)
        branch = self.env['hr.formula.config'].browse(result['branch_id'])
        branch.rule_ids.filtered(
            lambda r: r.code == 'SGGROSS').excel_formula = formula
        return branch

    def _approve(self, proposal_id):
        proposal = self.env['pb.scheme.proposal'].browse(proposal_id)
        request = proposal.approval_request_id
        self.engine.with_user(self.approver).decide(
            request.id, request.current_step_key, 'approve', 'looks right')
        proposal.invalidate_recordset()
        return proposal

    # ==================================================================
    # S06 — a merge, proposed
    # ==================================================================
    def test_s06_a_merge_waits_for_its_approval_and_then_lands(self):
        self._one_step_route()
        parent = self._config('SG parent', 'SGPARENT')
        branch = self._branch_with_a_change(parent)

        result = self.Studio.scheme_propose(parent.id, 'merge',
                                            branch_id=branch.id)
        self.assertTrue(result.get('ok'), result)
        self.assertFalse(result['applied'])
        parent.invalidate_recordset()
        self.assertEqual(
            parent.rule_ids.filtered(lambda r: r.code == 'SGGROSS')
            .excel_formula, '=A1', 'the merge happened before anybody agreed')

        proposal = self._approve(result['proposal_id'])
        parent.invalidate_recordset()
        branch.invalidate_recordset()
        self.assertEqual(proposal.state, 'applied')
        self.assertEqual(
            parent.rule_ids.filtered(lambda r: r.code == 'SGGROSS')
            .excel_formula, '=A1*2')
        self.assertEqual(branch.branch_state, 'merged')
        self.assertTrue(proposal.applied_release_id,
                        'the merge sealed no release')

    def test_s06_a_branch_that_moved_after_approval_is_refused(self):
        self._one_step_route()
        parent = self._config('SG moved', 'SGMOVED')
        branch = self._branch_with_a_change(parent)
        result = self.Studio.scheme_propose(parent.id, 'merge',
                                            branch_id=branch.id)
        self.assertTrue(result.get('ok'), result)
        # the branch is edited again while the proposal is with the approver
        branch.rule_ids.filtered(
            lambda r: r.code == 'SGGROSS').excel_formula = '=A1*3'
        proposal = self._approve(result['proposal_id'])
        parent.invalidate_recordset()
        self.assertNotEqual(proposal.state, 'applied')
        self.assertEqual(
            parent.rule_ids.filtered(lambda r: r.code == 'SGGROSS')
            .excel_formula, '=A1')
        self.assertIn('changed after',
                      proposal.approval_request_id.block_reason or '')

    # ==================================================================
    # S09 — the doors refuse on their own
    # ==================================================================
    def test_s09_branch_merge_refuses_without_a_proposal(self):
        self._one_step_route()
        parent = self._config('SG direct', 'SGDIRECT')
        branch = self._branch_with_a_change(parent)
        with self.assertRaises(Exception) as caught:
            self.Studio.branch_merge(branch.id)
        self.assertIn('Propose for approval', str(caught.exception))

    def test_s09_release_approve_refuses_without_a_proposal(self):
        self._one_step_route()
        config = self._config('SG release', 'SGRELEASE')
        with self.assertRaises(Exception) as caught:
            self.Studio.release_approve(config.id, 'by hand')
        self.assertIn('Propose for approval', str(caught.exception))

    def test_s09_the_lifecycle_facade_answers_with_the_refusal(self):
        """`cfg_activate` catches the refusal and returns it — no traceback."""
        self._one_step_route()
        config = self._config('SG cfg', 'SGCFG', state='validated')
        result = self.Studio.cfg_activate(config.id)
        self.assertFalse(result.get('ok'))
        self.assertIn('Propose', result.get('msg') or '')
        config.invalidate_recordset()
        self.assertEqual(config.state, 'validated')

    # ==================================================================
    # The route, in words
    # ==================================================================
    def test_the_studio_can_say_what_pressing_a_button_will_do(self):
        self._one_step_route()
        config = self._config('SG words', 'SGWORDS')
        answer = self.Studio.scheme_route(config.id)
        self.assertTrue(answer['ok'])
        self.assertEqual(answer['mode'], 'steps')
        self.assertTrue(answer['msg'])

    def test_a_proposal_shows_up_in_the_list_the_chip_reads(self):
        self._one_step_route()
        parent = self._config('SG list', 'SGLIST')
        branch = self._branch_with_a_change(parent)
        self.Studio.scheme_propose(parent.id, 'merge', branch_id=branch.id)
        rows = self.Studio.scheme_proposals(parent.id)
        self.assertTrue(rows['ok'])
        self.assertTrue(rows['rows'])
        self.assertEqual(rows['rows'][0]['kind'], 'merge')
        self.assertTrue(rows['rows'][0]['request_id'])
