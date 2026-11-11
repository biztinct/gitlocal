# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P5a T3 (time off) and T4 (ribbon words).

D28: a time-off request sent back by an approver → one email to the employee
with the reason and a button; the engine's "Sent back to you" stops for the
person who sent it in; no address → the engine keeps it; switch off → the
engine's copy is back. Leftover of D22: the staff card ribbon says "Waiting
for approval" / "Second approval".
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

SUBJECT = 'Your time off request was sent back'


@tagged('post_install', '-at_install')
class TestWf2p5aTimeOff(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.boss_user = Users.create({
            'name': 'P5a Leave Boss', 'login': 'p5a_leave_boss',
            'email': 'p5a_leave_boss@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'P5a Leave Asker', 'login': 'p5a_leave_staff',
            'email': 'p5a_leave_staff@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P5a Leave Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({
            'name': 'P5a Leave Asker', 'user_id': cls.staff_user.id,
            'work_email': 'p5a.asker@example.com',
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id,
            'company_id': cls.company.id})
        cls.ltype = cls.env['hr.leave.type'].create({
            'name': 'P5a manager type', 'requires_allocation': False,
            'leave_validation_type': 'manager',
            'company_id': cls.company.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.sn_route('leave', self.boss_user)

    def _leave(self, weeks=1):
        anchor = date.today() + timedelta(days=7 * weeks)
        start = anchor - timedelta(days=anchor.weekday())
        leave = self.env['hr.leave'].with_user(self.staff_user).create({
            'holiday_status_id': self.ltype.id,
            'employee_id': self.staff.id,
            'request_date_from': start, 'request_date_to': start,
            'name': 'P5a time off'})
        self.sn_settle()
        return leave.sudo()

    def _send_back(self, leave, reason):
        request = leave.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, 'return', reason=reason)
        self.env.invalidate_all()

    def _mails(self, leave):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'hr.leave'), ('res_id', '=', leave.id),
            ('subject', '=', SUBJECT)])

    def test_wf2p5a_t3a_time_off_sent_back_email(self):
        leave = self._leave()
        self._send_back(leave, 'P5a: pick the week after')
        self.assertEqual(leave.state, 'refuse')
        mail = self._mails(leave)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, 'p5a.asker@example.com')
        self.assertIn('P5a: pick the week after', mail.body_html)
        self.assertIn('Open your requests', mail.body_html)
        self.assertIn('res_id=%s' % leave.id, mail.body_html)
        self.assertNotIn('odoo', ('%s %s' % (mail.subject, mail.body_html))
                         .lower().replace('/odoo/', ''))
        self.assertFalse(self.sn_requester(leave, 'returned'),
                         'the engine leaves its own copy out')
        # a retry of the hook never sends twice
        leave._approval_return(leave.approval_request_id, 'again')
        self.assertEqual(len(self._mails(leave)), 1)

    def test_wf2p5a_t3b_employee_home_login_goes_to_my_requests(self):
        leave = self._leave(weeks=2)
        # the person is an employee-home login (their request was made for
        # them; the email must still reach them and point at their page)
        self.staff_user.group_ids = [(6, 0, [self.env.ref('base.group_portal').id])]
        self.assertTrue(self.staff_user.share)
        self._send_back(leave, 'P5a: half day only')
        mail = self._mails(leave)
        self.assertEqual(len(mail), 1)
        self.assertIn('/my/requests', mail.body_html)

    def test_wf2p5a_t3c_no_address_engine_keeps_it(self):
        self.staff.work_email = False
        self.staff_user.partner_id.email = False
        self.staff.work_contact_id.email = False
        leave = self._leave(weeks=3)
        self._send_back(leave, 'P5a: no')
        self.assertFalse(self._mails(leave))
        self.assertEqual(len(self.sn_requester(leave, 'returned')), 1)

    def test_wf2p5a_t3d_switch_off_engine_copy_back(self):
        self.sn_switch(False)
        leave = self._leave(weeks=4)
        self._send_back(leave, 'P5a: switch off')
        self.assertEqual(len(self.sn_requester(leave, 'returned')), 1)
        self.assertEqual(len(self._mails(leave)), 1)

    def test_wf2p5a_t4a_card_ribbon_words(self):
        arch = self.env['hr.leave'].get_view(
            self.env.ref('hr_holidays.hr_leave_view_kanban').id,
            'kanban')['arch']
        self.assertIn('Waiting for approval', arch)
        self.assertIn('Second approval', arch)
        self.assertNotIn('title="To Approve"', arch)
        self.assertNotIn('title="To Validate"', arch)
