# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T4 — contract extensions: one ask, one chaser.

Asking for an extension emails the manager, gives them a to-do and, if
nobody agrees it in time, emails them again with the HR team. With a live
route that asks the manager, the engine's "Your approval is needed" (and its
own reminder) is the one they get; the history line on the request stays;
the HR team still gets the overdue email. Without a route, or with the
switch off, everything is as before.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

ASK = 'pb_contract_lifecycle.mail_template_extension_ask'
OVERDUE = 'pb_contract_lifecycle.mail_template_extension_overdue'


@tagged('post_install', '-at_install')
class TestWf2p2bExtension(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.boss_user = Users.create({
            'name': 'P2b Ext Boss', 'login': 'p2b_ext_boss',
            'email': 'p2b.ext.boss@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.other_user = Users.create({
            'name': 'P2b Ext Other', 'login': 'p2b_ext_other',
            'email': 'p2b.ext.other@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.hr_user = Users.create({
            'name': 'P2b Ext HR', 'login': 'p2b_ext_hr',
            'email': 'p2b.ext.hr@example.com',
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'pb_lifecycle.group_lifecycle_manager').id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P2b Ext Boss',
                               'user_id': cls.boss_user.id,
                               'work_email': 'p2b.ext.boss@example.com',
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'P2b Ext Staff',
                                'parent_id': cls.boss.id,
                                'company_id': cls.company.id})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'P2b fixed term', 'employee_id': cls.staff.id,
            'company_id': cls.company.id, 'state': 'open', 'wage': 1000.0,
            'date_start': date.today() - timedelta(days=300),
            'date_end': date.today() + timedelta(days=40)})
        cls.env['ir.config_parameter'].sudo().set_param(
            'pb_contract_lifecycle.contract_mail', '1')

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _asked(self):
        review = self.env['pb.contract.review'].create({
            'contract_id': self.contract.id, 'company_id': self.company.id})
        ext = self.env['pb.contract.extension'].create({
            'review_id': review.id, 'reason': 'P2b keep them',
            'months': 6, 'company_id': self.company.id})
        ext.action_submit()
        self.sn_settle()
        self.assertEqual(ext.state, 'pending')
        return ext

    def _mails_to(self, ext, address):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.contract.extension'), ('res_id', '=', ext.id),
            ('email_to', 'ilike', address)])

    def _todo(self, ext):
        return self.sn_todos(ext, self.boss_user).filtered(
            lambda a: (a.summary or '').startswith('Agree the contract'))

    def test_wf2p2b_t4a_live_route_one_ask(self):
        self.sn_route('extension', self.boss_user)
        ext = self._asked()
        self.assertEqual(len(self.sn_your_turn(ext, self.boss_user)), 1)
        self.assertFalse(self._mails_to(ext, 'p2b.ext.boss@example.com'))
        self.assertFalse(self._todo(ext))
        self.assertTrue(ext.message_ids.filtered(
            lambda m: 'Asked.' in (m.body or '')), 'the history line stays')
        # overdue: one chaser for the manager (the engine's); HR still told
        ext.sudo().write({'approve_by': date.today() - timedelta(days=1)})
        self.env['pb.contract.extension']._escalate_overdue()
        overdue = self._mails_to(ext, 'p2b.ext.hr@example.com')
        self.assertEqual(len(overdue), 1)
        self.assertNotIn('p2b.ext.boss@example.com', overdue.email_to)
        self.assertTrue(ext.escalated)

    def test_wf2p2b_t4b_no_route_as_before(self):
        self.sn_no_route('extension')
        ext = self._asked()
        self.assertFalse(ext.approval_request_id)
        self.assertEqual(len(self._mails_to(
            ext, 'p2b.ext.boss@example.com')), 1)
        self.assertEqual(len(self._todo(ext)), 1)
        ext.sudo().write({'approve_by': date.today() - timedelta(days=1)})
        self.env['pb.contract.extension']._escalate_overdue()
        mails = self._mails_to(ext, 'p2b.ext.boss@example.com')
        self.assertEqual(len(mails), 2, 'ask + overdue, as before')

    def test_wf2p2b_t4c_switch_off_brings_it_back(self):
        self.sn_route('extension', self.boss_user)
        self.sn_switch(False)
        ext = self._asked()
        self.assertEqual(len(self.sn_your_turn(ext, self.boss_user)), 1)
        self.assertEqual(len(self._mails_to(
            ext, 'p2b.ext.boss@example.com')), 1)
        self.assertEqual(len(self._todo(ext)), 1)

    def test_wf2p2b_t4d_route_asks_someone_else(self):
        self.sn_route('extension', self.other_user)
        ext = self._asked()
        self.assertEqual(len(self._mails_to(
            ext, 'p2b.ext.boss@example.com')), 1)
        self.assertEqual(len(self._todo(ext)), 1)
