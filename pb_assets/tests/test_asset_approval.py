# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Approval Matrix P6 — an asset request on the engine, and off it.

The asset request is the reference case for the shim every chain consumer
shares (`biz_approval_workflow/models/chain_shim.py`), so this suite proves
the SHIM through it: dormant without a route, the same buttons driving the
route with one, the record's own status following the route, a refusal, and a
cancel that does not leave somebody holding a decision about a request that no
longer exists.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_assets.models.asset_request_approval import (
    ASSETS_PROCESS_KEY,
)


@tagged('post_install', '-at_install')
class TestAssetApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        hr_user = cls.env.ref('hr.group_hr_user')
        equip = cls.env.ref('pb_assets.group_assets_manager')

        cls.boss_user = Users.create({
            'name': 'Asset Boss', 'login': 'p6_asset_boss',
            'group_ids': [(6, 0, [internal.id, hr_user.id])]})
        cls.equip_user = Users.create({
            'name': 'Equipment Desk', 'login': 'p6_asset_equip',
            'group_ids': [(6, 0, [internal.id, equip.id])]})
        cls.staff_user = Users.create({
            'name': 'Asset Asker', 'login': 'p6_asset_staff',
            'group_ids': [(6, 0, [internal.id])]})

        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'Asset Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'Asset Asker',
                                'user_id': cls.staff_user.id,
                                'parent_id': cls.boss.id,
                                'company_id': cls.company.id})
        cls.category = cls.env['pb.asset.category'].create(
            {'name': 'P6 Laptop', 'code': 'P6LT'})

        # The route this phase ships, laid explicitly: a suite must never
        # depend on which migration happened to run on the database it is
        # given (ledger AM70).
        cls.env['pb.asset.request']._approval_seed_default(cls.company)
        cls.process = cls.env['biz.approval.process']._by_key(
            ASSETS_PROCESS_KEY)
        role = cls.env['biz.approval.role'].search(
            [('key', '=', 'equipment')], limit=1)
        cls.env['biz.approval.responsibility'].search([
            ('company_id', '=', cls.company.id),
            ('role_id', '=', role.id)]).write({'active': False})
        cls.env['biz.approval.responsibility'].create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': cls.equip_user.id})

    # ------------------------------------------------------------- helpers
    def _request(self, user=None):
        return self.env['pb.asset.request'].with_user(
            user or self.staff_user).create({
                'employee_id': self.staff.id,
                'category_id': self.category.id,
                'justification': 'The old one will not charge.',
            })

    def _bindings(self):
        return self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id)])

    # ==================================================================
    # Q01 — dormant with no route
    # ==================================================================
    def test_q01_without_a_route_the_old_ladder_is_untouched(self):
        self._bindings().write({'active': False})
        req = self._request()
        req.action_submit()
        self.assertEqual(req.state, 'submitted')
        self.assertFalse(req.approval_request_id,
                         'nothing may be sent in when no route is published')
        req.with_user(self.boss_user).action_manager_approve()
        self.assertEqual(req.state, 'manager_approved')
        req.with_user(self.equip_user).action_final_approve()
        self.assertEqual(req.state, 'approved')
        self._bindings().write({'active': True})

    # ==================================================================
    # Q02 — the same buttons, driving the route
    # ==================================================================
    def test_q02_the_route_drives_the_same_buttons(self):
        req = self._request()
        req.action_submit()

        engine_request = req.approval_request_id
        self.assertTrue(engine_request, 'submitting must create a request')
        self.assertEqual(engine_request.state, 'pending')
        self.assertEqual(req.state, 'submitted')
        steps = engine_request.step_ids.filtered('included').sorted('sequence')
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].status, 'active')
        self.assertEqual(steps[0].seat_ids.acting_user_id, self.boss_user,
                         'step one is the asker\'s own manager')
        self.assertEqual(steps[1].seat_ids.acting_user_id, self.equip_user)

        # the manager's own button is a decision on the live route
        req.with_user(self.boss_user).action_manager_approve()
        self.assertEqual(req.state, 'manager_approved',
                         'the record follows the route it was given')
        self.assertEqual(engine_request.state, 'pending')
        self.assertEqual(steps[1].status, 'active')

        req.with_user(self.equip_user).action_final_approve()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(engine_request.state, 'applied')

    def test_q02b_somebody_with_no_seat_cannot_press_the_button(self):
        req = self._request()
        req.action_submit()
        with self.assertRaises(AccessError):
            req.with_user(self.equip_user).action_manager_approve()

    # ==================================================================
    # Q03 — refusing
    # ==================================================================
    def test_q03_a_refusal_closes_the_request_and_the_record(self):
        req = self._request()
        req.action_submit()
        req.with_user(self.boss_user).action_refuse_chain('Not this quarter.')
        self.assertEqual(req.state, 'refused')
        self.assertEqual(req.approval_request_id.state, 'rejected')

    # ==================================================================
    # Q04 — leaving the ladder by another door
    # ==================================================================
    def test_q04_cancelling_the_record_withdraws_the_open_request(self):
        req = self._request()
        req.action_submit()
        engine_request = req.approval_request_id
        self.assertEqual(engine_request.state, 'pending')
        req.action_cancel()
        self.assertEqual(req.state, 'cancelled')
        engine_request.invalidate_recordset()
        self.assertEqual(engine_request.state, 'cancelled',
                         'no request may be left waiting for a record that '
                         'has left the route')
        self.assertTrue(engine_request.return_note,
                        'the withdrawal must say why')

    def test_q04b_resetting_to_draft_withdraws_it_too(self):
        req = self._request()
        req.action_submit()
        engine_request = req.approval_request_id
        req.action_reset_to_draft()
        engine_request.invalidate_recordset()
        self.assertEqual(req.state, 'draft')
        self.assertEqual(engine_request.state, 'cancelled')

    # ==================================================================
    # Q11 — the catalogue, the facts and the route
    # ==================================================================
    def test_q11_the_catalogue_row_names_the_record_that_holds_a_request(self):
        self.assertEqual(self.process.model_name, 'pb.asset.request')

    def test_q11b_the_route_ships_published_and_bound(self):
        binding = self._bindings().filtered(
            lambda b: b.active and b.scope_key == '')
        self.assertTrue(binding, 'every company must ship a default route')
        self.assertEqual(binding[0].workflow_id.published_version_id.status,
                         'published')

    def test_q11c_a_second_submission_is_refused(self):
        req = self._request()
        req.action_submit()
        with self.assertRaises(UserError):
            req.action_submit()

    def test_q11d_the_facts_the_route_may_ask_about_are_declared(self):
        caps = self.env['pb.asset.request']._approval_capabilities()
        for key in ('category', 'spare_available', 'country'):
            self.assertIn(key, caps['facts'])
        req = self._request()
        facts = req._chain_facts()
        self.assertEqual(set(facts), set(caps['facts']),
                         'a fact nobody declared cannot be conditioned on, '
                         'and a declared fact nobody sends is a dead choice')
