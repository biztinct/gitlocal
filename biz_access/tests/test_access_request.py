# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Approval Matrix P6 — Q09: a role grant that somebody agreed to.

The board's three doors are unchanged. What is tested here is the question in
front of them: with a route published the press makes a request and writes
nothing; the change happens when the route says yes; and the person who says
yes is the person who makes it, so one who cannot manage access is refused by
name rather than having it done for them.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.pb_access_request import (
    ROLES_PROCESS_KEY,
)


@tagged('post_install', '-at_install')
class TestAccessRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Access = cls.env['pb.access']
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        manage = cls.env.ref('biz_access.group_access_manager')

        cls.asker = Users.create({
            'name': 'Access Asker', 'login': 'p6_access_asker',
            'group_ids': [(6, 0, [internal.id, manage.id])]})
        cls.approver = Users.create({
            'name': 'Access Approver', 'login': 'p6_access_approver',
            'group_ids': [(6, 0, [internal.id, manage.id])]})
        cls.target = Users.create({
            'name': 'Access Target', 'login': 'p6_access_target',
            'group_ids': [(6, 0, [internal.id])]})

        cls.ability_group = cls.env['res.groups'].create(
            {'name': 'P6 access ability group'})
        cls.ability = cls.env['pb.role.ability'].create({
            'name': 'P6 ability', 'group_ids': [(6, 0,
                                                 [cls.ability_group.id])]})
        cls.profile = cls.env['pb.role.profile'].create({
            'name': 'P6 role', 'ability_ids': [(6, 0, [cls.ability.id])]})

        cls.env['pb.access.request']._approval_seed_default(cls.company)
        role = cls.env['biz.approval.role'].search(
            [('key', '=', 'approver')], limit=1)
        cls.env['biz.approval.responsibility'].search([
            ('company_id', '=', cls.company.id),
            ('role_id', '=', role.id)]).write({'active': False})
        cls.env['biz.approval.responsibility'].create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': cls.approver.id})

    def _bindings(self):
        process = self.env['biz.approval.process']._by_key(ROLES_PROCESS_KEY)
        return self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', process.id)])

    # ==================================================================
    def test_q09a_a_grant_is_asked_for_and_nothing_is_written_yet(self):
        answer = self.Access.with_user(self.asker).grant(
            self.profile.id, self.target.id, 'They joined the team.')
        self.assertTrue(answer.get('pending'), answer)
        self.assertNotIn(self.ability_group,
                         self.target.sudo().all_group_ids,
                         'nothing may be written before somebody agrees')
        record = self.env['pb.access.request'].sudo().browse(
            answer['access_request_id'])
        self.assertEqual(record.state, 'pending')
        self.assertEqual(record.kind, 'grant')

    def test_q09b_approving_it_writes_the_role_and_its_trail(self):
        answer = self.Access.with_user(self.asker).grant(
            self.profile.id, self.target.id, 'They joined the team.')
        record = self.env['pb.access.request'].sudo().browse(
            answer['access_request_id'])
        request = record.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.approver).decide(
            request.id, step.key, 'approve')

        self.target.invalidate_recordset(['group_ids'])
        self.assertIn(self.ability_group, self.target.sudo().all_group_ids)
        record.invalidate_recordset()
        self.assertEqual(record.state, 'applied')
        self.assertTrue(self.env['pb.access.delegation'].sudo().search([
            ('delegate_user_id', '=', self.target.id),
            ('profile_ids', 'in', self.profile.id)]),
            'the board\'s own audit row is still written')

    def test_q09c_turning_it_down_writes_nothing(self):
        answer = self.Access.with_user(self.asker).grant(
            self.profile.id, self.target.id, 'Maybe not.')
        record = self.env['pb.access.request'].sudo().browse(
            answer['access_request_id'])
        request = record.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.approver).decide(
            request.id, step.key, 'reject', 'Not for this role.')
        record.invalidate_recordset()
        self.assertEqual(record.state, 'rejected')
        self.assertNotIn(self.ability_group,
                         self.target.sudo().all_group_ids)

    def test_q09d_without_a_route_the_press_still_writes_at_once(self):
        self._bindings().write({'active': False})
        try:
            answer = self.Access.with_user(self.asker).grant(
                self.profile.id, self.target.id, 'Straight through.')
            self.assertFalse(answer.get('pending'))
            self.target.invalidate_recordset(['group_ids'])
            self.assertIn(self.ability_group,
                          self.target.sudo().all_group_ids)
        finally:
            self._bindings().write({'active': True})

    def test_q09e_an_approver_who_cannot_manage_access_is_named(self):
        """Safety rail 7: the last approver carries it out as themselves."""
        plain = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Plain Approver', 'login': 'p6_access_plain',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        role = self.env['biz.approval.role'].search(
            [('key', '=', 'approver')], limit=1)
        self.env['biz.approval.responsibility'].search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', role.id)]).write({'user_id': plain.id})

        answer = self.Access.with_user(self.asker).grant(
            self.profile.id, self.target.id, 'They joined.')
        record = self.env['pb.access.request'].sudo().browse(
            answer['access_request_id'])
        request = record.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(plain).decide(
            request.id, step.key, 'approve')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        self.assertIn(plain.name, request.block_reason or '')
        self.assertNotIn(self.ability_group,
                         self.target.sudo().all_group_ids)

    def test_q09f_a_grant_that_would_do_nothing_is_still_refused_at_once(self):
        self.target.sudo().write(
            {'group_ids': [(4, self.ability_group.id)]})
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.Access.with_user(self.asker).grant(
                self.profile.id, self.target.id, 'Again?')
