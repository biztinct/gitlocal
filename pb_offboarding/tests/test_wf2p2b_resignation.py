# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T6, T11 — resignations.

T6: "has handed in their resignation" goes to the manager and the HR team.
With a live route the engine tells the person it asks first; the email then
leaves out exactly that person — the rest of the HR team still gets it.
T11: an agreed resignation emails the employee itself, so the engine leaves
its own "Approved" out when the employee sent it in.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)


@tagged('post_install', '-at_install')
class TestWf2p2bResignation(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        lifecycle = cls.env.ref('pb_lifecycle.group_lifecycle_manager')
        cls.boss_user = Users.create({
            'name': 'P2b Res Boss', 'login': 'p2b_res_boss',
            'email': 'p2b.res.boss@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.hr_user = Users.create({
            'name': 'P2b Res HR', 'login': 'p2b_res_hr',
            'email': 'p2b.res.hr@example.com',
            'group_ids': [(6, 0, [internal.id, lifecycle.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P2b Res Boss',
                               'user_id': cls.boss_user.id,
                               'work_email': 'p2b.res.boss@example.com',
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'P2b Res Staff',
                                'parent_id': cls.boss.id,
                                'work_email': 'p2b.res.staff@example.com',
                                'company_id': cls.company.id})
        cls.env['ir.config_parameter'].sudo().set_param(
            'pb_offboarding.resign_mail', '1')

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _filed(self):
        res = self.env['pb.resignation'].create({
            'employee_id': self.staff.id, 'company_id': self.company.id,
            'reason_text': 'P2b moving on',
            'requested_lwd': date.today() + timedelta(days=30)})
        res.action_submit()
        self.sn_settle()
        self.assertEqual(res.state, 'submitted')
        return res

    def _mails_to(self, res, address):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.resignation'), ('res_id', '=', res.id),
            ('email_to', 'ilike', address)])

    def test_wf2p2b_t6a_live_route_manager_told_once_hr_still_told(self):
        self.sn_route('resign', self.boss_user)
        res = self._filed()
        self.assertEqual(len(self.sn_your_turn(res, self.boss_user)), 1)
        self.assertFalse(self._mails_to(res, 'p2b.res.boss@example.com'))
        self.assertEqual(len(self._mails_to(res, 'p2b.res.hr@example.com')), 1)

    def test_wf2p2b_t6b_no_route_as_before(self):
        self.sn_no_route('resign')
        res = self._filed()
        mail = self._mails_to(res, 'p2b.res.boss@example.com')
        self.assertEqual(len(mail), 1)
        self.assertIn('p2b.res.hr@example.com', mail.email_to)

    def test_wf2p2b_t6c_switch_off_brings_it_back(self):
        self.sn_route('resign', self.boss_user)
        self.sn_switch(False)
        res = self._filed()
        self.assertEqual(len(self._mails_to(
            res, 'p2b.res.boss@example.com')), 1)

    def test_wf2p2b_t11_the_employee_hears_approved_from_offboarding(self):
        res = self.env['pb.resignation'].create({
            'employee_id': self.staff.id, 'company_id': self.company.id,
            'reason_text': 'P2b', 'requested_lwd': date.today()})
        engine = self.env['biz.approval.engine']
        request = self.env['biz.approval.request'].new({
            'submitter_uid': self.boss_user.id,
            'subject_uids': [self.boss_user.id]})
        self.assertTrue(engine._area_tells_requester(request, res, 'approved'))
        self.assertFalse(engine._area_tells_requester(request, res, 'rejected'))
        # WF2 P5a (D28): sent back is offboarding's own email now
        self.assertTrue(engine._area_tells_requester(request, res, 'returned'))
        # emails switched off in Offboarding: the engine keeps its copy
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_offboarding.resign_mail', '0')
        self.assertFalse(engine._area_tells_requester(request, res, 'approved'))
