# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P5a T2 — D28: Expenses tells the employee a claim was sent back.

One email with the reason and "Open your claim", to staff and employee-home
logins alike; once per send-back (a retry never sends twice); sent in again
and sent back again → told again; the engine's own "Sent back to you" stops
for the person who sent it in; the kill switch brings the engine's copy back;
a claim with nowhere to send keeps the engine's copy.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

from .common import ExpenseFixtures

SUBJECT = 'Your expense claim was sent back'
BANNED = ('odoo', 'odoobot')


@tagged('post_install', '-at_install')
class TestWf2p5aExpenseReturned(SingleNoticeMixin, ExpenseFixtures,
                                TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._expense_fixtures('test_p5a_exp')
        cls.share_emp.work_email = 'quinn.p5a@example.com'
        cls.plain_emp.work_email = 'plain.p5a@example.com'

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _mails(self, claim):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.expense.claim'), ('res_id', '=', claim.id),
            ('subject', '=', SUBJECT)])

    def _clean(self, mail):
        text = ('%s %s' % (mail.subject or '', mail.body_html or '')).lower()
        for word in BANNED:
            self.assertNotIn(word, text)

    def test_wf2p5a_t2a_staff_login_reason_button_once(self):
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self.decide(claim, self.manager, 'return', 'P5a: add the taxi receipt')
        self.assertEqual(claim.state, 'draft')
        mail = self._mails(claim)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, 'plain.p5a@example.com')
        self.assertIn('P5a: add the taxi receipt', mail.body_html)
        self.assertIn('The reason given', mail.body_html)
        self.assertIn('Open your claim', mail.body_html)
        self.assertIn('/my/expenses/%s' % claim.id, mail.body_html)
        self._clean(mail)
        self.assertFalse(self.sn_requester(claim, 'returned'),
                         'the engine leaves its own copy out')
        # a retry never sends twice
        claim.sudo()._pb_tell_employee('returned')
        self.assertEqual(len(self._mails(claim)), 1)
        # sent in again, sent back again: told again
        self.facade(self.plain).send(claim)
        claim.invalidate_recordset()
        self.assertFalse(claim.sudo().pb_told_returned_at)
        self.decide(claim, self.manager, 'return', 'P5a: and the hotel')
        self.assertEqual(len(self._mails(claim)), 2)

    def test_wf2p5a_t2b_employee_home_login(self):
        claim = self.sent_claim(company_card=True)
        self.decide(claim, self.manager, 'return', 'P5a: wrong date')
        mail = self._mails(claim)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, 'quinn.p5a@example.com')
        self.assertIn('P5a: wrong date', mail.body_html)

    def test_wf2p5a_t2c_switch_off_engine_copy_back(self):
        self.sn_switch(False)
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self.decide(claim, self.manager, 'return', 'P5a: blurry')
        self.assertEqual(len(self.sn_requester(claim, 'returned')), 1)
        self.assertEqual(len(self._mails(claim)), 1)

    def test_wf2p5a_t2d_no_address_engine_keeps_it(self):
        self.plain_emp.work_email = False
        self.plain.partner_id.email = False
        self.plain_emp.work_contact_id.email = False
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self.decide(claim, self.manager, 'return', 'P5a: blurry')
        self.assertFalse(self._mails(claim))
        self.assertEqual(len(self.sn_requester(claim, 'returned')), 1,
                         'nobody would hear it otherwise')

    def test_wf2p5a_t2e_words_in_three_languages(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['res.lang']._activate_lang('id_ID')
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        for lang in ('en_US', 'vi_VN', 'id_ID'):
            rec = claim.sudo().with_context(lang=lang)
            subject = rec._pb_mail_subject('returned')
            body = str(rec._pb_mail_body('returned'))
            self.assertTrue(subject)
            if lang != 'en_US':
                self.assertNotEqual(subject, SUBJECT)
            for word in BANNED:
                self.assertNotIn(word, ('%s %s' % (subject, body)).lower())

    def test_wf2p5a_t2f_contract_lists_the_sent_back_email(self):
        caps = self.env['pb.expense.claim']._workflow_capabilities()
        self.assertTrue([e for e in caps['effects']
                         if e['stage'] == 'draft' and e['kind'] == 'message'
                         and 'sent back' in e['text']])
