# -*- coding: utf-8 -*-
"""S06–S10 — a change to a live pay scheme is proposed, approved, then carried out.

Every case runs the REAL path: the engine's own `submit` and `decide`, as the
real acting user, and the actual door afterwards. A test that wrote the states
itself would prove nothing about the thing the phase exists for.

The studio half (merge, release, roll-back) lives in
`pb_formula_studio/tests/test_scheme_gate.py` — the doors are defined there and
a test for a door belongs beside it.
"""
from odoo.exceptions import UserError
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


def _fast():
    return {'key': 'fast', 'kind': 'fast', 'title': 'No approval needed',
            'who': {'mode': 'people', 'user_ids': []},
            'min_amount': 0, 'condition': None}


@tagged('post_install', '-at_install')
class SchemeProposalCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['biz.approval.engine']
        cls.Proposal = cls.env['pb.scheme.proposal']
        cls.process = cls.env['biz.approval.process']._by_key('scheme')
        cls.company = cls.env.company
        cls.owner = cls._user('sc_owner', 'Oscar Owner')
        cls.manager = cls._user('sc_manager', 'Priya Payroll')
        cls.director = cls._user('sc_director', 'Dana Director')

    @classmethod
    def _user(cls, login, name):
        groups = [cls.env.ref('base.group_user').id]
        for xmlid in ('pb_hr_payroll_formula.group_formula_manager',):
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups.append(group.id)
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)],
            })

    def setUp(self):
        super().setUp()
        if not self.process:
            self.skipTest('the approval catalogue is not installed here')

    # ------------------------------------------------------------ fixtures
    def _config(self, name='SC probe', code='SCPROBE', state='draft'):
        config = self.env['hr.formula.config'].create({
            'name': name, 'code': code, 'country_code': 'VN',
            'company_id': self.company.id, 'state': state})
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Basic', 'code': 'SCBASIC',
            'column_type': 'input', 'sequence': 10})
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Gross', 'code': 'SCGROSS',
            'column_type': 'formula', 'excel_formula': '=A1', 'sequence': 20})
        return config

    def _hold(self, role_key, user):
        role = self.env['biz.approval.role'].search(
            [('key', '=', role_key)], limit=1)
        if not role:
            self.skipTest("the '%s' responsibility is not here" % role_key)
        existing = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        if existing:
            existing.write({'user_id': user.id})
            return existing
        return self.env['biz.approval.responsibility'].sudo().create({
            'company_id': self.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': self.company.name,
            'user_id': user.id})

    def _bind(self, definition, scope_key='', name='SC route'):
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', scope_key), ('active', '=', True),
        ]).write({'active': False})
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
            'scope_key': scope_key,
            'scope_label': scope_key or self.company.name,
            'kind_key': 'any', 'workflow_id': workflow.id, 'mode': 'follow'})
        return workflow

    def _two_step(self):
        self._hold('payroll_mgr', self.manager)
        self._hold('director', self.director)
        return self._bind(_route([
            _step('s1', 'payroll_mgr', 'Payroll manager', kind='review'),
            _step('s2', 'director', 'Country director'),
        ]))

    def _no_route(self):
        """Retire every scheme-change binding for this company."""
        self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('active', '=', True)]).write({'active': False})

    def _decide(self, proposal, user, action='approve', reason='ok'):
        request = proposal.approval_request_id
        self.engine.with_user(user).decide(
            request.id, request.current_step_key, action, reason)
        proposal.invalidate_recordset()

    # ==================================================================
    # S07 — a proposal to put a scheme live
    # ==================================================================
    def test_s07_activate_needs_the_route_and_then_happens(self):
        self._two_step()
        config = self._config(state='validated')
        proposal = self.Proposal.propose(config, 'activate')
        proposal.action_submit()
        proposal.invalidate_recordset()
        self.assertEqual(proposal.state, 'pending')
        self.assertEqual(config.state, 'validated', 'nothing happened yet')

        self._decide(proposal, self.manager)
        self._decide(proposal, self.director)
        config.invalidate_recordset()
        self.assertEqual(proposal.state, 'applied')
        self.assertEqual(config.state, 'active')

    def test_s07_a_fast_lane_company_applies_in_one_step(self):
        self._bind(_route([_fast()]), name='SC fast')
        config = self._config(code='SCFAST', state='validated')
        proposal = self.Proposal.propose(config, 'activate')
        proposal.action_submit()
        proposal.invalidate_recordset()
        config.invalidate_recordset()
        self.assertEqual(proposal.state, 'applied')
        self.assertEqual(config.state, 'active')
        request = proposal.approval_request_id
        self.assertEqual(request.state, 'applied')
        self.assertTrue(
            any(row.get('code') == 'fast_lane'
                for row in (request.confirmations or [])),
            'the fast lane was not recorded as a confirmed choice')

    def test_s07_a_direct_press_with_no_route_still_leaves_a_record(self):
        self._no_route()
        config = self._config(code='SCOPEN', state='validated')
        config.action_activate()
        config.invalidate_recordset()
        self.assertEqual(config.state, 'active')
        row = self.Proposal.sudo().search(
            [('config_id', '=', config.id), ('kind', '=', 'activate')],
            limit=1)
        self.assertTrue(row, 'the change was not recorded anywhere')
        self.assertEqual(row.state, 'applied')

    # ==================================================================
    # S09 — every old door refuses without an approved proposal
    # ==================================================================
    def test_s09_activate_refuses_and_names_the_way_in(self):
        self._two_step()
        config = self._config(code='SCGATE', state='validated')
        with self.assertRaises(UserError) as caught:
            config.action_activate()
        self.assertIn('Propose for approval', str(caught.exception))
        config.invalidate_recordset()
        self.assertEqual(config.state, 'validated')

    def test_s09_archive_refuses_too(self):
        self._two_step()
        config = self._config(code='SCARCH', state='active')
        with self.assertRaises(UserError):
            config.action_archive()

    def test_s09_a_branch_is_scratch_work_and_can_be_discarded(self):
        """Retiring a BRANCH is not a change to anything anybody is paid by."""
        self._two_step()
        parent = self._config(code='SCPARENT', state='active')
        branch = parent.copy({
            'name': 'SC branch', 'code': 'SCBRANCH', 'state': 'draft',
            'parent_branch_id': parent.id, 'branch_state': 'open'})
        branch.action_archive()
        branch.invalidate_recordset()
        self.assertEqual(branch.state, 'archived')

    # ==================================================================
    # S08 — a live scheme is changed on a branch, not in place
    # ==================================================================
    def test_s08_a_money_edit_on_a_live_scheme_is_refused(self):
        self._two_step()
        config = self._config(code='SCLIVE', state='active')
        rule = config.rule_ids.filtered(lambda r: r.code == 'SCGROSS')
        with self.assertRaises(UserError) as caught:
            rule.excel_formula = '=A1*2'
        self.assertIn('branch', str(caught.exception).lower())

    def test_s08_renaming_a_component_on_a_live_scheme_is_free(self):
        """The gate is about the money, not about the words on a payslip."""
        self._two_step()
        config = self._config(code='SCNAME', state='active')
        rule = config.rule_ids.filtered(lambda r: r.code == 'SCGROSS')
        rule.name = 'Gross pay'
        self.assertEqual(rule.name, 'Gross pay')

    def test_s08_the_same_edit_on_a_branch_is_free(self):
        self._two_step()
        parent = self._config(code='SCBASE', state='active')
        branch = parent.copy({
            'name': 'SC work', 'code': 'SCWORK', 'state': 'draft',
            'parent_branch_id': parent.id, 'branch_state': 'open'})
        rule = branch.rule_ids.filtered(lambda r: r.code == 'SCGROSS')
        rule.excel_formula = '=A1*2'
        self.assertEqual(rule.excel_formula, '=A1*2')

    def test_s08_with_no_route_a_live_edit_is_free(self):
        self._no_route()
        config = self._config(code='SCFREE', state='active')
        rule = config.rule_ids.filtered(lambda r: r.code == 'SCGROSS')
        rule.excel_formula = '=A1*3'
        self.assertEqual(rule.excel_formula, '=A1*3')

    # ==================================================================
    # The seal
    # ==================================================================
    def test_the_content_stamp_ignores_a_rename_and_notices_a_formula(self):
        config = self._config(code='SCHASH')
        before = config._content_hash()
        config.rule_ids[0].name = 'Renamed'
        self.assertEqual(config._content_hash(), before,
                         'a rename moved the content stamp')
        config.rule_ids.filtered(
            lambda r: r.code == 'SCGROSS').excel_formula = '=A1+1'
        self.assertNotEqual(config._content_hash(), before)

    def test_a_scheme_that_moved_after_approval_is_not_carried_out(self):
        self._two_step()
        config = self._config(code='SCMOVED', state='validated')
        proposal = self.Proposal.propose(config, 'activate')
        proposal.action_submit()
        proposal.invalidate_recordset()
        # somebody edits the scheme while it is with the approver
        config.rule_ids.filtered(
            lambda r: r.code == 'SCGROSS').excel_formula = '=A1+99'
        self._decide(proposal, self.manager)
        self._decide(proposal, self.director)
        config.invalidate_recordset()
        self.assertNotEqual(proposal.state, 'applied')
        self.assertEqual(config.state, 'validated',
                         'a moved scheme was put live anyway')
        self.assertIn('changed after',
                      proposal.approval_request_id.block_reason or '')

    def test_the_blueprint_and_the_proposal_ask_the_same_question(self):
        """One hash, one answer (the blueprint now calls the shared one)."""
        Studio = self.env.get('pb.blueprint.studio')
        if Studio is None:
            self.skipTest('the guided setup is not installed here')
        config = self._config(code='SCONEHASH')
        self.assertEqual(Studio._evidence_hash(config), config._content_hash())

    # ==================================================================
    # S11 — the seed, and the catalogue row it repoints
    # ==================================================================
    def test_s11_the_catalogue_names_the_proposal(self):
        self.assertEqual(self.process.model_name, 'pb.scheme.proposal')
        self.assertTrue(self.process.connected)

    def test_s11_every_company_has_a_published_scheme_route(self):
        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        self.assertTrue(binding, 'the seed laid no company-wide route')

    def test_s11_the_seed_is_safe_to_run_again(self):
        before = self.env['biz.approval.workflow'].sudo().search_count([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id)])
        self.Proposal._approval_seed_default(self.company)
        after = self.env['biz.approval.workflow'].sudo().search_count([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id)])
        self.assertEqual(before, after)

    # ==================================================================
    # S10 — the payslip says which content computed it
    # ==================================================================
    def test_s10_a_computed_payslip_carries_the_scheme_content(self):
        config = self._config(code='SCSTAMP', state='active')
        self.env['hr.formula.config.milestone'].sudo().record(
            config, 'Activated v1')
        employee = self.env['hr.employee'].create({
            'name': 'SC subject', 'company_id': self.company.id})
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'SC slip',
            'date_from': '2026-03-01', 'date_to': '2026-03-31',
            'company_id': self.company.id,
            'calculation_method': 'formula',
            'formula_config_id': config.id})
        slip.compute_sheet_with_formulas()
        slip.invalidate_recordset()
        self.assertEqual(slip.formula_content_hash, config._content_hash())
        self.assertTrue(slip.formula_milestone_id,
                        'the payslip names no sealed content')

    # ==================================================================
    # The release row
    # ==================================================================
    def test_a_release_is_born_approved_and_can_name_its_proposal(self):
        config = self._config(code='SCREL')
        release = self.env['hr.formula.release'].create({
            'name': 'SC release', 'config_id': config.id})
        self.assertEqual(release.state, 'approved')
        self.assertFalse(release.proposal_id)
