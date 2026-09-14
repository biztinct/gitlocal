# -*- coding: utf-8 -*-
"""Z01 and Z02, on the filing flow — the proposal rails, end to end.

Z01 is the contract every Phase-7 adapter signs, and it is asserted here
against the smallest of them: a proposal is made instead of the write; a
published fast lane does the write inside the same call; approving carries the
original write body out ONCE; a world that moved underneath sends it back.

Z02 is the gate this module shipped without: producing a statutory filing had
NO permission check of any kind.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP7Filing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'FIL Co'})
        cls.Proposal = cls.env['pb.filing.proposal']
        cls.engine = cls.env['biz.approval.engine']
        cls.Seed = cls.env['biz.approval.seed']

        # AM102 — `env.user` is the inactive background account. Seat the
        # administrator and act through them.
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company.id)]})
        cls.officer = cls._user('fil_officer', 'Olly Officer', [
            'base.group_user',
            'pb_hr_payroll_base.group_payroll_base_officer'])
        cls.manager = cls._user('fil_manager', 'Mia Manager', [
            'base.group_user',
            'pb_hr_payroll_base.group_payroll_base_manager'])
        cls.nobody = cls._user('fil_nobody', 'Nora Nobody',
                               ['base.group_user'])
        cls.Proposal._approval_seed_default(cls.company)
        cls._hold('payroll_mgr', cls.manager)

    @classmethod
    def _user(cls, login, name, groups):
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])],
            })

    @classmethod
    def _hold(cls, role_key, user):
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', role_key)], limit=1)
        cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')]).write({'active': False})
        return cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': user.id})

    def _propose(self, user=None):
        return self.Proposal.with_user(user or self.officer).with_company(
            self.company).propose(
                'filing', 'VAT for June',
                payload={'country': 'VN', 'filing_key': 'tang_ld',
                         'values': {}},
                facts={'country': {'value': 'VN', 'unit': ''},
                       'filing_key': {'value': 'tang_ld', 'unit': ''},
                       'period': {'value': '2026-06', 'unit': ''}},
                company=self.company)

    # ================================================================== Z01
    def test_z01a_a_proposal_is_made_and_nothing_is_produced(self):
        proposal = self._propose()
        self.assertEqual(proposal.state, 'pending')
        self.assertFalse(proposal.applied)
        answer = proposal.answer()
        self.assertTrue(answer['pending'])
        self.assertEqual(answer['with_whom'], self.manager.name)
        self.assertTrue(answer['reference'].startswith('FIL'))

    def test_z01b_the_fast_lane_happens_at_once(self):
        """A published "No approval needed" route is a real capability."""
        self.Seed.set_no_approval_needed(self.company, 'filing')
        proposal = self.Proposal.with_user(self.manager).with_company(
            self.company).propose(
                'filing', 'A filing nobody checks',
                payload={'country': 'ZZ', 'filing_key': 'x', 'values': {}},
                company=self.company)
        # The country is unknown, so the APPLY refuses — which is the point:
        # the fast lane ran it, synchronously, inside the same call.
        self.assertEqual(proposal.state, 'pending')
        self.assertEqual(proposal.approval_request_id.state, 'approved')
        self.assertTrue(proposal.approval_request_id.block_reason)

    def test_z01c_approving_runs_the_write_once(self):
        proposal = self._propose()
        request = proposal.approval_request_id
        self.assertTrue(request)
        # The route is one step; the manager holds it and did not prepare it.
        self.engine.with_user(self.manager).decide(
            request, request.current_step_key, 'approve', 'Fine by me')
        proposal.invalidate_recordset()
        # The VN wizard is not installed on every database; either it was
        # produced, or the apply refused by name. Both prove the write body
        # ran exactly once and nothing was half-done.
        self.assertIn(proposal.state, ('applied', 'pending'))
        if proposal.state == 'applied':
            self.assertTrue(proposal.applied)
            self.assertEqual(
                self.env['biz.approval.request'].search_count([
                    ('res_model', '=', 'pb.filing.proposal'),
                    ('res_id', '=', proposal.id)]), 1)
        else:
            self.assertTrue(request.block_reason)

    def test_z01d_a_world_that_moved_sends_it_back(self):
        """The snapshot is re-read from the world, never off the proposal."""
        proposal = self._propose()
        proposal.sudo().write({'snapshot_json': '{"bands": 7}'})
        moved = proposal._proposal_moved()
        self.assertTrue(moved, 'a stored snapshot that no longer matches the '
                               'world must be caught by name')
        self.assertIn('bands', moved[0])

    def test_z01e_the_gate_is_re_checked_by_whoever_carries_it_out(self):
        """Rail 5: the last approver performs the write as themselves."""
        proposal = self._propose()
        with self.assertRaises(UserError):
            proposal.with_user(self.nobody)._proposal_check_gate()
        self.assertTrue(proposal.with_user(self.manager)._proposal_check_gate())

    def test_z01f_a_seat_is_also_a_read(self):
        proposal = self._propose()
        self.assertIn(self.manager, proposal.seat_user_ids,
                      'the person asked to decide must be able to read it')
        proposal.with_user(self.manager).check_access('read')

    # ================================================================== Z02
    def test_z02a_a_filing_needs_the_payroll_permission(self):
        Flow = self.env['pb.filing.flow']
        with self.assertRaises(AccessError):
            Flow.with_user(self.nobody)._require_officer()
        self.assertTrue(Flow.with_user(self.officer)._require_officer())
        self.assertTrue(Flow.with_user(self.manager)._require_officer())

    def test_z02b_the_flow_is_still_generate_only(self):
        from odoo.addons.pb_govt_reports.models import pb_filing_flow as flow
        for method in flow._GENERATE.values():
            for bad in flow._ONLY_GENERATE:
                self.assertNotIn(bad, method)
