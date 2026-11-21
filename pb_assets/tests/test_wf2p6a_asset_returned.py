# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P6a (D28, equipment): an equipment request sent back by an
approver → one email to the employee with the reason and a button, in their
own language; the engine's "Sent back to you" stops for the person who sent it
in; no address → the engine keeps it; switch off → the engine's copy is back
(the email still goes). Same cases as P5a's time off T3."""

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

TEMPLATE = 'pb_assets.mail_template_asset_request_returned'


@tagged('post_install', '-at_install')
class TestWf2p6aAssetReturned(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        asker = cls.env.ref('pb_assets.group_assets_user')
        cls.boss_user = Users.create({
            'name': 'P6a Equipment Boss', 'login': 'p6a_asset_boss',
            'email': 'p6a_asset_boss@example.com', 'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'P6a Equipment Asker', 'login': 'p6a_asset_staff',
            'email': 'p6a_asset_staff@example.com', 'group_ids': [(6, 0, [internal.id, asker.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P6a Equipment Boss', 'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({'name': 'P6a Equipment Asker', 'user_id': cls.staff_user.id,
                                'work_email': 'p6a.asker@example.com', 'parent_id': cls.boss.id,
                                'company_id': cls.company.id})
        cls.category = cls.env['pb.asset.category'].create({'name': 'P6a Laptop', 'code': 'P6AL'})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.sn_route('assets', self.boss_user)

    def _request(self):
        req = self.env['pb.asset.request'].with_user(self.staff_user).create({
            'employee_id': self.staff.id, 'category_id': self.category.id,
            'justification': 'P6a: the old one will not charge.'})
        req.with_user(self.staff_user).action_submit()
        self.sn_settle()
        return req.sudo()

    def _send_back(self, req, reason):
        request = req.approval_request_id
        self.assertTrue(request, 'a live route sends the request in')
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, 'return', reason=reason)
        self.env.invalidate_all()

    def _mails(self, req):
        return self.sn_mails(req, TEMPLATE)

    def test_wf2p6a_e6_equipment_sent_back_email(self):
        req = self._request()
        self._send_back(req, 'P6a: a spare is free')
        self.assertEqual(req.state, 'draft')
        mail = self._mails(req)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, 'p6a.asker@example.com')
        self.assertIn('P6a: a spare is free', mail.body_html)
        self.assertIn('Open your requests', mail.body_html)
        self.assertIn('P6a Laptop', mail.body_html)
        self.assertIn('res_id=%s' % req.id, mail.body_html)
        self.assertNotIn('odoo', ('%s %s' % (mail.subject, mail.body_html)).lower().replace('/odoo/', ''))
        self.assertFalse(self.sn_requester(req, 'returned'), 'the engine leaves its own copy out')
        req._approval_return(req.approval_request_id, 'again')
        self.assertEqual(len(self._mails(req)), 1)

    def test_wf2p6a_e7_employee_home_login_goes_to_my_requests(self):
        req = self._request()
        self.staff_user.group_ids = [(6, 0, [self.env.ref('base.group_portal').id])]
        self._send_back(req, 'P6a: other model')
        mail = self._mails(req)
        self.assertEqual(len(mail), 1)
        self.assertIn('/my/requests', mail.body_html)

    def test_wf2p6a_e8_no_address_engine_keeps_it(self):
        self.staff.work_email = False
        self.staff_user.partner_id.email = False
        self.staff.work_contact_id.email = False
        req = self._request()
        self._send_back(req, 'P6a: no')
        self.assertFalse(self._mails(req))
        self.assertEqual(len(self.sn_requester(req, 'returned')), 1)

    def test_wf2p6a_e9_switch_off_engine_copy_back(self):
        self.sn_switch(False)
        req = self._request()
        self._send_back(req, 'P6a: switch off')
        self.assertEqual(len(self.sn_requester(req, 'returned')), 1)
        self.assertEqual(len(self._mails(req)), 1)

    def test_wf2p6a_e10_in_the_employee_language(self):
        langs = self.env['res.lang'].sudo().search([('code', 'in', ['vi_VN', 'id_ID']), ('active', '=', True)])
        if not langs:
            self.skipTest('Vietnamese and Indonesian are not installed here')
        expected = {'vi_VN': 'Yêu cầu thiết bị của bạn đã bị trả lại', 'id_ID': 'Permintaan perangkat Anda dikembalikan'}
        for lang in langs:
            self.staff_user.lang = lang.code
            req = self._request()
            self._send_back(req, 'P6a: %s' % lang.code)
            mail = self.sn_mails(req)  # any subject: it is not the English one
            self.assertEqual(len(mail), 1)
            self.assertEqual(mail.subject, expected[lang.code])
