# -*- coding: utf-8 -*-
"""TIERS T2 — Employee or Staff, switched on the People lens.

T2.11 the people list and the employee passport; T2.12 the switch both ways,
with roles ending through the board's own path or refused while role changes
need approval; T2.13 the refusals (ledger T-R12: refused, never forced).
"""

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountType(TransactionCase):

    def setUp(self):
        super().setUp()
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.stamp = stamp
        self.Users = self.env['res.users'].with_context(no_reset_password=True)
        self.Emp = self.env['hr.employee']
        self.g_user = self.env.ref('base.group_user')
        self.g_portal = self.env.ref('base.group_portal')
        self.Access = type(self.env['pb.access'])

        self.manager = self._login('mgr', [self.g_user, self.env.ref(
            'biz_access.group_access_manager')])
        self.mgr = self.env['pb.access'].with_user(self.manager)

        self.plain = self._login('plain', [self.g_user])
        self.plain_emp = self.Emp.create({'name': 'ZZ T2 Plain',
                                          'user_id': self.plain.id})
        self.lead = self._login('lead', [self.g_user])
        lead_emp = self.Emp.create({'name': 'ZZ T2 Lead',
                                    'user_id': self.lead.id})
        self.Emp.create({'name': 'ZZ T2 Report', 'parent_id': lead_emp.id})

        self.share = self._login('share', [self.g_portal])
        self.share_emp = self.Emp.create({'name': 'ZZ T2 Share',
                                          'user_id': self.share.id})
        self.vendor = self._login('vendor', [self.g_portal])

        gate = self.env['res.groups'].create({'name': 'ZZ T2 Gate %s' % stamp})
        ability = self.env['pb.role.ability'].create({
            'technical_key': 'zz-t2-gate-%s' % stamp, 'name': 'ZZ T2 Gate',
            'area': 'system', 'description': 'A throwaway ability for a test.',
            'group_ids': [(6, 0, gate.ids)]})
        self.role = self.env['pb.role.profile'].create({
            'name': 'ZZ T2 Role %s' % stamp, 'area': 'system',
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, ability.ids)]})
        self.gate = gate

    def _login(self, tag, groups):
        return self.Users.create({
            'name': 'ZZ T2 %s' % tag.title(),
            'login': 'zz.t2.%s.%s@example.com' % (tag, self.stamp),
            'email': 'zz.t2.%s.%s@example.com' % (tag, self.stamp),
            'group_ids': [(6, 0, [g.id for g in groups])]})

    def _audit(self, user, origin='account_switch'):
        return self.env['pb.access.delegation'].sudo().search([
            ('delegate_user_id', '=', user.id), ('origin', '=', origin)])

    def _route(self, live):
        return patch.object(self.Access, '_roles_route_live',
                            return_value=live)

    # ------------------------------------------------------------ T2.11
    def test_t2_11_people_and_the_employee_passport(self):
        rows = {r['id']: r for r in self.mgr.people()}
        self.assertIn(self.share.id, rows)
        self.assertEqual(rows[self.share.id]['kind'], 'employee')
        self.assertTrue(rows[self.share.id]['has_employee'])
        self.assertNotIn(self.vendor.id, rows,
                         'a share login without an employee is not a colleague')
        self.assertEqual(rows[self.plain.id]['kind'], 'staff')

        pack = self.mgr.passport(self.share.id)
        head = pack['header']
        self.assertEqual(head['kind'], 'employee')
        self.assertTrue(head['has_employee'])
        self.assertEqual(pack['roles'], [])
        self.assertEqual(pack['rail'], [])
        self.assertEqual(head['switch']['to'], 'staff')
        self.assertTrue(head['switch']['allowed'], head['switch']['why'])
        self.assertTrue(pack['can_manage'])
        # the companion read beside the passport opens nothing for them
        self.assertEqual(self.mgr.surface_access(
            [{'key': 'k', 'groups': ['base.group_user']}], self.share.id),
            {'k': {'allowed': False, 'parent': ''}})
        # and every role operation still refuses an employee login
        with self.assertRaises(UserError):
            self.mgr.grant(self.role.id, self.share.id)

        staff_head = self.mgr.passport(self.plain.id)['header']
        self.assertEqual(staff_head['kind'], 'staff')
        self.assertEqual(staff_head['switch']['to'], 'employee')
        self.assertTrue(staff_head['switch']['allowed'],
                        staff_head['switch']['why'])

    # ------------------------------------------------------------ T2.12
    def test_t2_12_both_ways(self):
        with self._route(False):
            res = self.mgr.set_account_type(self.plain.id, 'employee', 'T2')
        self.assertTrue(res['ok'])
        self.assertEqual(res['kind'], 'employee')
        self.plain.invalidate_recordset()
        self.assertTrue(self.plain.share)
        self.assertEqual(self.plain.group_ids, self.g_portal)
        if hasattr(self.plain, '_pb_portal_only'):
            self.assertTrue(self.plain._pb_portal_only())
        row = self._audit(self.plain)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.state, 'revoked')
        self.assertEqual(row.reason, 'T2')
        self.assertEqual(row.delegator_user_id, self.manager)
        # the person is still on the list, now as an employee login
        rows = {r['id']: r for r in self.mgr.people()}
        self.assertEqual(rows[self.plain.id]['kind'], 'employee')

        res = self.mgr.set_account_type(self.plain.id, 'staff')
        self.assertTrue(res['ok'])
        self.plain.invalidate_recordset()
        self.assertFalse(self.plain.share)
        self.assertEqual(self.plain.group_ids, self.g_user)
        self.assertEqual(len(self._audit(self.plain)), 2)

    def test_t2_12b_roles_end_through_the_board(self):
        self.env['pb.access']._assign_role(self.role, self.plain, 'Fixture')
        source = self.env['pb.role.assignment'].sudo().search([
            ('user_id', '=', self.plain.id), ('profile_id', '=', self.role.id),
            ('active', '=', True)])
        self.assertTrue(source)
        self.assertIn(self.gate, self.plain.all_group_ids)
        head = self.mgr.passport(self.plain.id)['header']
        with self._route(False):
            self.assertEqual(
                self.mgr._account_switch_preview(self.plain)['roles_ending'], 1)
            res = self.mgr.set_account_type(self.plain.id, 'employee')
        self.assertIn('1 role ended', res['message'])
        source.invalidate_recordset()
        self.assertFalse(source.active)
        self.assertTrue(self._audit(self.plain, 'board_removal'))
        self.assertTrue(self._audit(self.plain))
        self.plain.invalidate_recordset()
        self.assertTrue(self.plain.share)
        self.assertNotIn(self.gate, self.plain.all_group_ids)
        self.assertEqual(head['kind'], 'staff')

    def test_t2_12c_refused_while_role_changes_need_approval(self):
        self.env['pb.access']._assign_role(self.role, self.plain, 'Fixture')
        with self._route(True):
            preview = self.mgr._account_switch_preview(self.plain)
            self.assertFalse(preview['allowed'])
            self.assertEqual(preview['why'], 'Remove their roles first.')
            with self.assertRaisesRegex(UserError, '(?i)remove their roles first'):
                self.mgr.set_account_type(self.plain.id, 'employee')
        self.plain.invalidate_recordset()
        self.assertFalse(self.plain.share)
        self.assertTrue(self.env['pb.role.assignment'].sudo().search_count([
            ('user_id', '=', self.plain.id), ('active', '=', True)]))
        self.assertFalse(self._audit(self.plain))

    # ------------------------------------------------------------ T2.13
    def test_t2_13_refusals(self):
        with self.assertRaisesRegex(UserError, 'own account'):
            self.mgr.set_account_type(self.manager.id, 'employee')
        with self.assertRaisesRegex(UserError, 'administrator'):
            self.mgr.set_account_type(
                self.env.ref('base.user_admin').id, 'employee')
        with self.assertRaisesRegex(UserError, '1 person reports to'):
            self.mgr.set_account_type(self.lead.id, 'employee')
        with self.assertRaisesRegex(UserError, "not a person's login"):
            self.mgr.set_account_type(
                self.env.ref('base.public_user').id, 'staff')
        with self.assertRaisesRegex(UserError, 'not linked to an employee'):
            self.mgr.set_account_type(self.vendor.id, 'staff')
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(self.plain).set_account_type(
                self.share.id, 'staff')
        with self.assertRaises(UserError):
            self.mgr.set_account_type(self.plain.id, 'boss')
        for user in (self.lead, self.plain, self.vendor):
            user.invalidate_recordset()
        self.assertFalse(self.lead.share)
        self.assertFalse(self.plain.share)
        self.assertTrue(self.vendor.share)
        # the preview says the same thing the switch would
        why = self.mgr._account_switch_preview(self.lead)['why']
        self.assertIn('1 person reports to', why)

    def test_t2_13b_an_open_decision_keeps_the_full_login(self):
        if 'biz.approval.request.seat' not in self.env:
            self.skipTest('the approvals engine is not installed')
        env = self.env(context=dict(self.env.context, tracking_disable=True,
                                    mail_create_nolog=True, mail_notrack=True))
        process = env['biz.approval.process'].sudo().create({
            'key': 'test_tiers_t2_probe_%s' % self.stamp, 'name': 'T2 probe'})
        request = env['biz.approval.request'].sudo().create({
            'title': 'T2 probe', 'process_id': process.id,
            'company_id': env.company.id,
            'res_model': 'res.users', 'res_id': self.plain.id})
        step = env['biz.approval.request.step'].sudo().create({
            'request_id': request.id, 'key': 'probe'})
        env['biz.approval.request.seat'].sudo().create({
            'step_id': step.id, 'key': 'probe',
            'acting_user_id': self.plain.id, 'status': 'open'})
        with self.assertRaisesRegex(UserError, '1 decision is waiting'):
            self.mgr.set_account_type(self.plain.id, 'employee')
        self.plain.invalidate_recordset()
        self.assertFalse(self.plain.share)

    def test_t2_13c_promoting_needs_nothing_more(self):
        res = self.mgr.set_account_type(self.share.id, 'staff', 'Now in HR')
        self.assertTrue(res['ok'])
        self.share.invalidate_recordset()
        self.assertFalse(self.share.share)
        self.assertEqual(self.share.group_ids, self.g_user)
        self.assertEqual(self._audit(self.share).state, 'active')
        # idempotent: asking again changes nothing and says so
        again = self.mgr.set_account_type(self.share.id, 'staff')
        self.assertIn('already has a full login', again['message'])
        self.assertEqual(len(self._audit(self.share)), 1)

    # TIERS T4 follow-up — a permission given by hand keeps the full login
    def test_t4_a_permission_given_by_hand_keeps_the_full_login(self):
        by_hand = self._login('byhand', [self.g_user,
                                         self.env.ref('hr.group_hr_user')])
        self.Emp.create({'name': 'ZZ T4 By Hand', 'user_id': by_hand.id})
        why = self.mgr._switch_refusal(by_hand, 'employee')
        self.assertIn('by hand', why)
        self.assertIn(self.env.ref('hr.group_hr_user').full_name, why)
        preview = self.mgr._account_switch_preview(by_hand)
        self.assertFalse(preview['allowed'])
        with self.assertRaises(UserError):
            self.mgr.set_account_type(by_hand.id, 'employee')
        self.assertFalse(by_hand.share)

        multi = self._login('multi', [self.g_user, self.env.ref(
            'base.group_multi_company')])
        self.Emp.create({'name': 'ZZ T4 Multi', 'user_id': multi.id})
        self.assertEqual(self.mgr._switch_refusal(multi, 'employee'), '')

        # A group that came through a role is not "by hand": the role ends
        # with the switch, and the switch is still offered.
        self.env['pb.access'].sudo()._assign_role(self.role, self.plain)
        self.assertFalse(self.mgr._hand_given_groups(self.plain))
