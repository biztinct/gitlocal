# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP QF3 (handover cases 10 + the adapter facts) — a leave request
withdrawn on the approvals screen is a cancelled leave, not a leave stuck
"Waiting for approval" with nobody left to decide it. And the adapter's text
facts: the part of the day, the documents."""

import base64
from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_qf3')
class TestWdgapQf3Withdraw(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.boss_user = Users.create({
            'name': 'QF3 TO Boss', 'login': 'qf3_to_boss',
            'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'QF3 TO Staff', 'login': 'qf3_to_staff',
            'group_ids': [(6, 0, [internal.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'QF3 TO Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({
            'name': 'QF3 TO Staff', 'user_id': cls.staff_user.id,
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id,
            'company_id': cls.company.id})
        cls.env['hr.leave']._approval_seed_default(cls.company)
        cls.half = cls.env['hr.leave.type'].create({
            'name': 'QF3 TO Half', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'company_id': cls.company.id})
        cls.hours = cls.env['hr.leave.type'].create({
            'name': 'QF3 TO Hours', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'hour',
            'company_id': cls.company.id})
        anchor = date.today() + timedelta(days=14)
        cls.mon = anchor - timedelta(days=anchor.weekday())

    def _leave(self, lt=None, **extra):
        vals = {'holiday_status_id': (lt or self.half).id,
                'employee_id': self.staff.id,
                'request_date_from': self.mon, 'request_date_to': self.mon,
                'name': 'QF3'}
        vals.update(extra)
        return self.env['hr.leave'].with_user(self.staff_user).create(vals)

    def test_10a_the_engine_withdraw_cancels_the_leave(self):
        leave = self._leave()
        request = leave.sudo().approval_request_id
        self.assertEqual(request.state, 'pending')
        self.env['biz.approval.engine'].with_user(self.staff_user).cancel(
            request.id, 'Not needed')
        leave.invalidate_recordset()
        request.invalidate_recordset()
        self.assertEqual(request.state, 'cancelled')
        self.assertEqual(leave.sudo().state, 'cancel')
        open_seats = request.step_ids.seat_ids.filtered(
            lambda s: s.status == 'open')
        self.assertFalse(open_seats)

    def test_10b_the_inbox_cancel_does_the_same(self):
        Inbox = self.env.get('pb.approval.inbox')
        if Inbox is None:
            self.skipTest('the approvals screen is not installed')
        leave = self._leave(request_date_from=self.mon + timedelta(days=1),
                            request_date_to=self.mon + timedelta(days=1))
        request = leave.sudo().approval_request_id
        Inbox.with_user(self.staff_user).cancel(request.id, 'Changed my mind')
        leave.invalidate_recordset()
        self.assertEqual(leave.sudo().state, 'cancel')

    def test_10c_an_approved_leave_is_not_touched_by_the_hook(self):
        leave = self._leave(request_date_from=self.mon + timedelta(days=2),
                            request_date_to=self.mon + timedelta(days=2))
        leave.with_user(self.boss_user).action_approve()
        leave.invalidate_recordset()
        self.assertEqual(leave.sudo().state, 'validate')
        leave.sudo()._approval_withdraw(None, 'late')
        self.assertEqual(leave.sudo().state, 'validate')

    def test_facts_part_of_day_and_documents(self):
        leave = self._leave(request_date_from_period='am',
                            request_date_to_period='am')
        self.env['ir.attachment'].sudo().create({
            'name': 'a.pdf', 'datas': base64.b64encode(b'%PDF-1.4\n%%EOF'),
            'res_model': 'hr.leave', 'res_id': leave.id})
        leave = leave.sudo()
        chips = {c['label']: c['value']
                 for c in leave._approval_detail(None)['chips']}
        self.assertEqual(chips['Part of the day'], 'Half day, morning')
        self.assertEqual(chips['Documents'], '1 document attached')
        self.assertEqual(leave._approval_card_count(None), 'Half a day')
        hours = self._leave(self.hours,
                            request_date_from=self.mon + timedelta(days=3),
                            request_date_to=self.mon + timedelta(days=3),
                            request_hour_from=9.5, request_hour_to=11.0).sudo()
        self.assertEqual(hours._pb_day_part_label(), '09:30 to 11:00')
        self.assertEqual(hours._approval_card_count(None), '1.5 hours')
        whole = self._leave(request_date_from=self.mon + timedelta(days=4),
                            request_date_to=self.mon + timedelta(days=4)).sudo()
        self.assertEqual(whole._pb_day_part_label(), '')
        self.assertNotIn('Part of the day',
                         [c['label'] for c in whole._approval_detail(None)['chips']])
