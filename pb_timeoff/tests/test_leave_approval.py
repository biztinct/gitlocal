# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Approval Matrix P6 — Q05: time off on the engine.

The promise being tested is that the DEFAULT route says exactly what the leave
type already said. A type approved by the manager goes to the manager; one
approved by an officer goes to the HR lead; one approved by both goes to both,
in that order; and one approved by nobody never reaches a route at all,
because the time-off module approves it the moment it is created.
"""

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_timeoff.models.hr_leave_approval import LEAVE_PROCESS_KEY


@tagged('post_install', '-at_install')
class TestLeaveApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        officer = cls.env.ref('hr_holidays.group_hr_holidays_user')

        cls.boss_user = Users.create({
            'name': 'Leave Boss', 'login': 'p6_leave_boss',
            'group_ids': [(6, 0, [internal.id])]})
        cls.hr_user = Users.create({
            'name': 'Leave Officer', 'login': 'p6_leave_officer',
            'group_ids': [(6, 0, [internal.id, officer.id])]})
        cls.staff_user = Users.create({
            'name': 'Leave Asker', 'login': 'p6_leave_staff',
            'group_ids': [(6, 0, [internal.id])]})

        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'Leave Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({
            'name': 'Leave Asker', 'user_id': cls.staff_user.id,
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id,
            'company_id': cls.company.id})

        cls.env['hr.leave']._approval_seed_default(cls.company)
        role = cls.env['biz.approval.role'].search(
            [('key', '=', 'hr_lead')], limit=1)
        cls.env['biz.approval.responsibility'].search([
            ('company_id', '=', cls.company.id),
            ('role_id', '=', role.id)]).write({'active': False})
        cls.env['biz.approval.responsibility'].create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': cls.hr_user.id})

    def _type(self, validation):
        return self.env['hr.leave.type'].create({
            'name': 'P6 %s' % validation,
            'requires_allocation': False,
            'leave_validation_type': validation,
            'company_id': self.company.id,
        })

    def _leave(self, leave_type, days=1):
        start = date.today() + timedelta(days=14)
        return self.env['hr.leave'].with_user(self.staff_user).create({
            'holiday_status_id': leave_type.id,
            'employee_id': self.staff.id,
            'request_date_from': start,
            'request_date_to': start + timedelta(days=days - 1),
            'name': 'P6 time off',
        })

    # ==================================================================
    def test_q05a_a_manager_type_goes_to_the_manager_and_nobody_else(self):
        leave = self._leave(self._type('manager'))
        request = leave.approval_request_id
        self.assertTrue(request, 'confirming must send it in')
        included = request.step_ids.filtered('included')
        self.assertEqual(len(included), 1)
        self.assertEqual(included.seat_ids.acting_user_id, self.boss_user)

        leave.with_user(self.boss_user).action_approve()
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'validate')
        self.assertEqual(request.state, 'applied')

    def test_q05b_an_officer_type_goes_to_the_hr_lead(self):
        leave = self._leave(self._type('hr'))
        request = leave.approval_request_id
        included = request.step_ids.filtered('included')
        self.assertEqual(len(included), 1)
        self.assertEqual(included.seat_ids.acting_user_id, self.hr_user)

    def test_q05c_both_means_both_in_order(self):
        leave = self._leave(self._type('both'))
        request = leave.approval_request_id
        included = request.step_ids.filtered('included').sorted('sequence')
        self.assertEqual(len(included), 2)
        self.assertEqual(included[0].seat_ids.acting_user_id, self.boss_user)
        self.assertEqual(included[1].seat_ids.acting_user_id, self.hr_user)

        leave.with_user(self.boss_user).action_approve()
        leave.invalidate_recordset()
        self.assertNotEqual(leave.state, 'validate',
                            'one yes of two is not an approval')
        leave.with_user(self.hr_user).action_approve()
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'validate')

    def test_q05d_a_refusal_refuses_the_leave(self):
        leave = self._leave(self._type('manager'))
        request = leave.approval_request_id
        leave.with_user(self.boss_user).action_refuse()
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'refuse')
        self.assertEqual(request.state, 'rejected')

    def test_q05e_a_type_nobody_approves_never_reaches_a_route(self):
        leave = self._leave(self._type('no_validation'))
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'validate',
                         'the time-off module approves these itself')
        self.assertFalse(leave.approval_request_id,
                         'and nothing is asked of anybody')

    def test_q05f_an_approver_without_the_time_off_role_is_told_by_name(self):
        """Safety rail 4: the last approver records the leave AS THEMSELVES."""
        leave = self._leave(self._type('manager'))
        request = leave.approval_request_id
        # the manager holds no holidays group at all
        self.assertFalse(self.boss_user.has_group(
            'hr_holidays.group_hr_holidays_user'))
        leave.with_user(self.boss_user).action_approve()
        request.invalidate_recordset()
        self.assertEqual(request.state, 'approved',
                         'the decision stands…')
        self.assertIn(self.boss_user.name, request.block_reason or '',
                      '…and the reason it could not be carried out names them')
        leave.invalidate_recordset()
        self.assertNotEqual(leave.state, 'validate')

    def test_q05g_the_catalogue_row_and_the_facts(self):
        process = self.env['biz.approval.process']._by_key(LEAVE_PROCESS_KEY)
        self.assertEqual(process.model_name, 'hr.leave')
        caps = self.env['hr.leave']._approval_capabilities()
        for key in ('days', 'leave_type', 'is_unpaid',
                    'overlaps_payroll_cutoff', 'validation_type'):
            self.assertIn(key, caps['facts'])

    def test_q05h_a_leave_cannot_be_sent_in_twice(self):
        leave = self._leave(self._type('manager'))
        with self.assertRaises(UserError):
            self.env['biz.approval.engine'].submit(leave)
