# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Approval Matrix P6 — Q06: overtime on the engine.

Two promises are being kept here. The first is that the same buttons — the
form's, and the week grid's bulk approve — drive the published route. The
second is the one that would be easy to break: the approved/bonus split is
recomputed and SEALED when the whole route says yes, not when the first
person in it does.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_workforce.models.overtime_request_approval import (
    OVERTIME_PROCESS_KEY,
)


@tagged('post_install', '-at_install')
class TestOvertimeApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        officer = cls.env.ref('hr_attendance.group_hr_attendance_officer')

        cls.boss_user = Users.create({
            'name': 'OT Boss', 'login': 'p6_ot_boss',
            'group_ids': [(6, 0, [internal.id, officer.id])]})
        cls.staff_user = Users.create({
            'name': 'OT Asker', 'login': 'p6_ot_staff',
            'group_ids': [(6, 0, [internal.id])]})

        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'OT Boss', 'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'OT Asker',
                                'user_id': cls.staff_user.id,
                                'parent_id': cls.boss.id,
                                'company_id': cls.company.id})
        cls.env['hr.overtime.request']._approval_seed_default(cls.company)

    def _ot(self, hours=2.0):
        return self.env['hr.overtime.request'].sudo().create({
            'employee_id': self.staff.id,
            'date': date.today(),
            'overtime_type': 'weekday',
            'planned_hours': hours, 'actual_hours': hours,
            'reason': 'P6 overtime',
        })

    # ==================================================================
    def test_q06a_submitting_asks_the_manager(self):
        req = self._ot()
        req.action_submit()
        self.assertEqual(req.state, 'submitted')
        request = req.approval_request_id
        self.assertTrue(request, 'submitting must send it in')
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(step.seat_ids.acting_user_id, self.boss_user)

    def test_q06b_the_split_is_written_when_the_route_says_yes(self):
        req = self._ot(hours=2.0)
        req.action_submit()
        self.assertFalse(req.approved_hours,
                         'nothing may be sealed before the route agrees')
        req.with_user(self.boss_user).action_approve()
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.approved_hours + req.bonus_hours, 2.0)
        self.assertEqual(req.approval_request_id.state, 'applied')

    def test_q06c_a_refusal_zeroes_the_hours(self):
        req = self._ot()
        req.action_submit()
        req.with_user(self.boss_user).action_refuse()
        req.invalidate_recordset()
        self.assertEqual(req.state, 'refused')
        self.assertFalse(req.approved_hours)
        self.assertEqual(req.approval_request_id.state, 'rejected')

    def test_q06d_the_grid_bulk_approve_goes_through_the_route(self):
        req = self._ot()
        req.action_submit()
        self.env['hr.attendance.weekentry'].with_user(
            self.boss_user).approve_requests([req.id])
        req.invalidate_recordset()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.approval_request_id.state, 'applied')

    def test_q06e_the_facts_a_route_may_ask_about(self):
        process = self.env['biz.approval.process']._by_key(
            OVERTIME_PROCESS_KEY)
        self.assertEqual(process.model_name, 'hr.overtime.request')
        caps = self.env['hr.overtime.request']._approval_capabilities()
        for key in ('hours', 'ot_type', 'year_to_date_hours', 'over_ceiling'):
            self.assertIn(key, caps['facts'])

    def test_q06f_an_easy_one_is_only_easy_while_it_is_waiting(self):
        """The batch verdict moved here when the team queue was retired."""
        req = self._ot()
        self.assertFalse(req._approval_batch_safe(False),
                         'a draft is not waiting for anybody')
        req.action_submit()
        self.assertTrue(req._approval_batch_safe(False))
        req.sudo().write({'actual_hours': 3.5})     # a human edited it
        self.assertFalse(req._approval_batch_safe(False))
