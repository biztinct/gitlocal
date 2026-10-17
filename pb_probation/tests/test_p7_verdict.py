# -*- coding: utf-8 -*-
"""Z04 — pass is immediate; fail, extend and terminate travel a route.

The thing being proved is a RULING, not a mechanism: the manager who runs a
probation review keeps the decision that somebody passed, because that is
their job and adding a second signature to it would be a gate nobody asked
for. The three verdicts that change what happens to a person's employment are
the ones somebody else sees.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_probation.models.verdict_approval import (
    HELD_VERDICTS, VERDICT_WRITE, propose_verdict,
)


@tagged('post_install', '-at_install')
class TestP7Verdict(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'VER Co'})
        cls.Proposal = cls.env['pb.verdict.proposal']
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company.id)]})
        cls.lead = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Hana HR', 'login': 'ver_hr',
                'email': 'ver_hr@example.com',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                      cls.env.ref('hr.group_hr_user').id])],
            })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Thao Staff', 'company_id': cls.company.id})
        cls.Proposal._approval_seed_default(cls.company)
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', 'lifecycle')], limit=1)
        cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.company.id),
            ('role_id', '=', role.id)]).write({'active': False})
        cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': cls.lead.id})

    def _review(self):
        return self.env['pb.probation.review'].sudo().create({
            'employee_id': self.employee.id,
            'company_id': self.company.id,
        })

    # ------------------------------------------------------------ Z04
    def test_z04a_pass_is_not_a_held_verdict(self):
        self.assertNotIn('pass', HELD_VERDICTS)
        review = self._review()
        self.assertIsNone(
            propose_verdict(review, 'pass', {'args': {}}),
            'passing probation stays the manager\'s own decision')

    def test_z04b_fail_extend_and_terminate_are_routed(self):
        for verdict in ('fail', 'extend', 'terminate'):
            review = self._review()
            answer = propose_verdict(
                review.with_user(self.lead), verdict, {'args': {}})
            self.assertTrue(answer, '%s should be proposed' % verdict)
            self.assertEqual(answer['kind'], verdict)
            self.assertFalse(answer['applied'])

    def test_z04c_the_approved_verdict_does_not_propose_itself_again(self):
        review = self._review()
        self.assertIsNone(
            propose_verdict(
                review.with_context(**{VERDICT_WRITE: True}), 'fail',
                {'args': {}}),
            'the approved apply calls straight back in and must go through')

    def test_z04d_the_route_asks_the_lifecycle_team_only_for_a_fail(self):
        workflow = self.env['biz.approval.workflow'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id.key', '=', 'verdict')], limit=1)
        self.assertTrue(workflow, 'the verdict route should be seeded')
        version = workflow.published_version_id
        self.assertTrue(version)
        steps = version.definition['steps']
        self.assertEqual(steps[0]['who']['mode'], 'manager')
        condition = steps[1]['condition']
        self.assertEqual(condition['fact'], 'verdict')
        self.assertEqual(sorted(condition['value']), ['fail', 'terminate'])

    def test_z04e_the_proposal_knows_whose_manager_to_ask(self):
        boss = self.env['hr.employee'].create({
            'name': 'Minh Manager', 'company_id': self.company.id,
            'user_id': self.lead.id})
        self.employee.write({'parent_id': boss.id})
        review = self._review()
        answer = propose_verdict(review.with_user(self.lead), 'fail',
                                 {'args': {}})
        proposal = self.Proposal.sudo().browse(answer['proposal_id'])
        self.assertEqual(proposal._approval_manager_uids(), self.lead.ids,
                         'the manager comes off the record, not off a login')
