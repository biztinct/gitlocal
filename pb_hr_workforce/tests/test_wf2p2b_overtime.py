# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T3 — overtime: the line manager is told once.

The overtime form gives the line manager a to-do on "Send", and with a live
route the approval engine tells them too. With a route that asks the line
manager, only the engine's notice stays; without a route, or with the switch
`biz_approval.single_notice` off, the to-do is exactly as before.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)


@tagged('post_install', '-at_install')
class TestWf2p2bOvertime(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        officer = cls.env.ref('hr_attendance.group_hr_attendance_officer')
        manager = cls.env.ref('hr_attendance.group_hr_attendance_manager')
        cls.boss_user = Users.create({
            'name': 'P2b OT Boss', 'login': 'p2b_ot_boss',
            'group_ids': [(6, 0, [internal.id, officer.id, manager.id])]})
        cls.other_user = Users.create({
            'name': 'P2b OT Other', 'login': 'p2b_ot_other',
            'group_ids': [(6, 0, [internal.id, officer.id, manager.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P2b OT Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'P2b OT Asker',
                                'parent_id': cls.boss.id,
                                'company_id': cls.company.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _sent(self):
        req = self.env['hr.overtime.request'].sudo().create({
            'employee_id': self.staff.id, 'date': date.today(),
            'overtime_type': 'weekday', 'planned_hours': 2.0,
            'actual_hours': 2.0, 'reason': 'P2b overtime'})
        self.assertEqual(req.manager_id, self.boss)
        req.action_submit()
        self.sn_settle()
        self.assertEqual(req.state, 'submitted')
        return req

    def _todo(self, req):
        return self.sn_todos(req, self.boss_user).filtered(
            lambda a: (a.summary or '').startswith('Overtime Request to Approve'))

    def test_wf2p2b_t3a_live_route_manager_told_once(self):
        self.sn_route('overtime', self.boss_user)
        req = self._sent()
        self.assertTrue(req.approval_request_id)
        self.assertEqual(len(self.sn_your_turn(req, self.boss_user)), 1)
        self.assertFalse(self._todo(req))

    def test_wf2p2b_t3b_no_route_as_before(self):
        self.sn_no_route('overtime')
        req = self._sent()
        self.assertFalse(req.approval_request_id)
        self.assertEqual(len(self._todo(req)), 1)

    def test_wf2p2b_t3c_switch_off_brings_it_back(self):
        self.sn_route('overtime', self.boss_user)
        self.sn_switch(False)
        req = self._sent()
        self.assertEqual(len(self.sn_your_turn(req, self.boss_user)), 1)
        self.assertEqual(len(self._todo(req)), 1)

    def test_wf2p2b_t3d_route_asks_someone_else(self):
        self.sn_route('overtime', self.other_user)
        req = self._sent()
        self.assertEqual(len(self._todo(req)), 1)
