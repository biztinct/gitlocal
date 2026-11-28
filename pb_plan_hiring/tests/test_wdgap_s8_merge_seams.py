# -*- coding: utf-8 -*-
"""WDGAP Step 8 merge seam e: S8-C pause hiring × S8-C plan → draft hiring requests.

M5  a paused TEAM: its plan line says why and makes nothing, the other line is made.
M6  a role paused on its own (team open): pressing the plan's button for that line
    and an open one is refused with the plain pause sentence, and NOTHING is left
    behind (the open line's request is not half-made either).
M7  a paused COMPANY: every line of the plan says so and nothing is made.
"""
from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_s8m')
class TestS8MergePlanPause(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        if 'pb_hiring_paused' not in env['hr.job']._fields:
            return
        cls.co = env['res.company'].create({'name': 'S8M Plan Company'})
        cls.lead = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'S8M Plan Lead', 'login': 's8m.planlead@example.com',
            'email': 's8m.planlead@example.com', 'company_id': cls.co.id,
            'company_ids': [(6, 0, [cls.co.id])],
            'group_ids': [(6, 0, [env.ref(g).id for g in (
                'base.group_user', 'pb_hiring.group_hiring_manager',
                'pb_decision_room.group_decision_manager')])]})
        Dept = env['hr.department'].sudo()
        cls.shop = Dept.create({'name': 'S8M Shop', 'company_id': cls.co.id})
        cls.office = Dept.create({'name': 'S8M Office', 'company_id': cls.co.id})
        Job = env['hr.job'].sudo()
        cls.cashier = Job.create({'name': 'S8M Cashier', 'company_id': cls.co.id,
                                  'department_id': cls.shop.id})
        cls.clerk = Job.create({'name': 'S8M Clerk', 'company_id': cls.co.id,
                                'department_id': cls.office.id})
        cls.plan = env['pb.decision.plan'].sudo().create({
            'name': 'S8M Plan 2027', 'company_id': cls.co.id, 'scope_kind': 'company',
            'scope_ref': str(cls.co.id), 'status': 'approved',
            'decided_at': datetime(2026, 11, 15, 9, 0),
            'state': {'moves': [
                {'team': 't%s' % cls.shop.id, 'role': 'r%s' % cls.cashier.id, 'n': 2,
                 'month': 3},
                {'team': 't%s' % cls.office.id, 'role': 'r%s' % cls.clerk.id, 'n': 1,
                 'month': 4},
            ]}})
        cls.k_shop = 't%s|r%s|3' % (cls.shop.id, cls.cashier.id)
        cls.k_office = 't%s|r%s|4' % (cls.office.id, cls.clerk.id)

    def setUp(self):
        super().setUp()
        if 'pb_hiring_paused' not in self.env['hr.job']._fields:
            self.skipTest('organisation module not installed')

    def _plan(self):
        return self.env['pb.decision.plan'].with_user(self.lead).with_context(
            allowed_company_ids=[self.co.id])

    def _reqs(self):
        return self.env['pb.hiring.requisition'].sudo().with_context(
            active_test=False).search([('pb_plan_id', '=', self.plan.id)])

    def _line(self, data, key):
        return next(l for l in data['lines'] if l['key'] == key)

    def test_m5_paused_team_line_refused_other_made(self):
        self.shop.sudo().write({'pb_hiring_pause': True,
                                'pb_hiring_pause_reason': 'S8M budget review'})
        data = self._plan().pb_get_hiring_lines(self.plan.id)
        shop = self._line(data, self.k_shop)
        self.assertFalse(shop['can_make'])
        self.assertIn('S8M budget review', shop['why'])
        res = self._plan().pb_make_hiring_requests(
            self.plan.id, [{'key': self.k_shop}, {'key': self.k_office}])
        self.assertEqual((res['made'], res['skipped']), (1, 1))
        reqs = self._reqs()
        self.assertEqual(reqs.mapped('pb_plan_line_key'), [self.k_office])
        self.assertEqual(reqs.request_state, 'writing')

    def test_m6_paused_role_refuses_the_press_and_leaves_nothing(self):
        self.cashier.sudo().write({'pb_hiring_pause_self': True,
                                   'pb_hiring_pause_reason_self': 'S8M role on hold'})
        self.assertTrue(self.cashier.pb_hiring_paused)
        before = self.env['pb.hiring.requisition'].sudo().search_count([])
        with self.assertRaises(UserError) as caught:
            with self.env.cr.savepoint():
                self._plan().pb_make_hiring_requests(
                    self.plan.id, [{'key': self.k_office}, {'key': self.k_shop}])
        self.assertIn('paused', str(caught.exception).lower())
        self.assertEqual(self.env['pb.hiring.requisition'].sudo().search_count([]), before,
                         "nothing half-made")
        self.assertFalse(self._reqs())

    def test_m7_paused_company(self):
        self.co.sudo().write({'pb_hiring_pause': True,
                              'pb_hiring_pause_reason': 'S8M company freeze'})
        data = self._plan().pb_get_hiring_lines(self.plan.id)
        self.assertTrue(all(not l['can_make'] for l in data['lines']))
        res = self._plan().pb_make_hiring_requests(
            self.plan.id, [{'key': self.k_shop}, {'key': self.k_office}])
        self.assertEqual(res['made'], 0)
        self.assertFalse(self._reqs())
