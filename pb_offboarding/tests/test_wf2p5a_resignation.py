# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P5a T3 (resignations) — D28: sent back is emailed by
offboarding itself.

Sent back through a live route → one email to the employee with the reason
and "Open my resignation", once; the engine's own "Sent back to you" stops
when the employee sent it in themselves; resignation emails switched off → no
email and the engine keeps its copy.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

SUBJECT = 'Your resignation was sent back to you'


@tagged('post_install', '-at_install')
class TestWf2p5aResignation(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.boss_user = Users.create({
            'name': 'P5a Res Boss', 'login': 'p5a_res_boss',
            'email': 'p5a.res.boss@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'P5a Res Staff', 'login': 'p5a_res_staff',
            'email': 'p5a.res.staff@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P5a Res Boss',
                               'user_id': cls.boss_user.id,
                               'work_email': 'p5a.res.boss@example.com',
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'P5a Res Staff',
                                'user_id': cls.staff_user.id,
                                'parent_id': cls.boss.id,
                                'work_email': 'p5a.res.staff@example.com',
                                'company_id': cls.company.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_offboarding.resign_mail', '1')
        self.sn_route('resign', self.boss_user)

    def _filed(self):
        res = self.env['pb.resignation'].create({
            'employee_id': self.staff.id, 'company_id': self.company.id,
            'reason_text': 'P5a moving on',
            'requested_lwd': date.today() + timedelta(days=30)})
        res.action_submit()
        self.sn_settle()
        self.assertEqual(res.state, 'submitted')
        return res

    def _send_back(self, res, reason):
        request = res.sudo().approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, 'return', reason)
        self.env.invalidate_all()

    def _mails(self, res):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.resignation'), ('res_id', '=', res.id),
            ('subject', '=', SUBJECT)])

    def test_wf2p5a_t3h_resignation_sent_back_email(self):
        res = self._filed()
        self._send_back(res, 'P5a: please confirm the last day')
        self.assertNotEqual(res.state, 'submitted')
        mail = self._mails(res)
        self.assertEqual(len(mail), 1)
        self.assertIn('p5a.res.staff@example.com', mail.email_to)
        self.assertIn('P5a: please confirm the last day', mail.body_html)
        self.assertIn('/my/resignation', mail.body_html)
        self.assertNotIn('odoo', mail.body_html.lower())
        # a retried hook never sends twice
        res.sudo()._approval_return(res.sudo().approval_request_id, 'x')
        self.assertEqual(len(self._mails(res)), 1)

    def test_wf2p5a_t3i_engine_copy_stops_for_the_employee_themselves(self):
        res = self._filed()
        request = res.sudo().approval_request_id
        # the person it is about sent it in (as from their own page)
        request.sudo().submitter_uid = self.staff_user
        self._send_back(res, 'P5a: themselves')
        self.assertFalse(self.sn_requester(res, 'returned'))
        self.assertEqual(len(self._mails(res)), 1)

    def test_wf2p5a_t3j_emails_off_engine_keeps_it(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_offboarding.resign_mail', '0')
        res = self._filed()
        request = res.sudo().approval_request_id
        request.sudo().submitter_uid = self.staff_user
        self._send_back(res, 'P5a: off')
        self.assertFalse(self._mails(res))
        self.assertEqual(len(self.sn_requester(res, 'returned')), 1)
