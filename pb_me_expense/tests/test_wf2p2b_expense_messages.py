# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T12 — Expenses tells the employee: approved, refused, paid.

One email each, to the employee's work address (an employee-home login and a
staff login alike), in their language, with the reason / the amount and the
date filled in and one button to the claim; never twice for one decision; a
new decision after "fix and resend" is told again; nothing for a claim that
did not move; the engine leaves its own "Approved" / "Turned down" out for
the person who sent it in.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

from .common import ExpenseFixtures

APPROVED = 'pb_me_expense.mail_template_claim_approved'
REFUSED = 'pb_me_expense.mail_template_claim_refused'
PAID = 'pb_me_expense.mail_template_claim_paid'
BANNED = ('odoo', 'odoobot')


@tagged('post_install', '-at_install')
class TestWf2p2bExpenseMessages(SingleNoticeMixin, ExpenseFixtures,
                                TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._expense_fixtures('test_p2b_exp')
        cls.share_emp.work_email = 'quinn.share@example.com'
        cls.plain_emp.work_email = 'plain.person@example.com'

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _mails(self, claim, subject):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.expense.claim'), ('res_id', '=', claim.id),
            ('subject', '=', subject)])

    def _approve(self, claim):
        self.decide(claim, self.manager)
        self.decide(claim, self.finance)
        self.assertEqual(claim.state, 'approved')

    def _pay(self, claim):
        journal = self.env['account.journal'].sudo().search(
            [('type', '=', 'general'), ('company_id', '=', self.company.id)],
            limit=1)
        move = self.env['account.move'].sudo().create(
            {'move_type': 'entry', 'journal_id': journal.id})
        claim.expense_ids.sudo().write({'account_move_id': move.id})
        self.env.invalidate_all()
        self.assertEqual(claim.state, 'paid')

    def _clean(self, mail):
        text = ('%s %s' % (mail.subject or '', mail.body_html or '')).lower()
        for word in BANNED:
            self.assertNotIn(word, text)

    # ------------------------------------------------------------- T12
    def test_wf2p2b_t12a_approved_to_an_employee_home_login(self):
        claim = self.sent_claim(company_card=True)
        self._approve(claim)
        mails = self._mails(claim, 'Your expense claim was approved')
        self.assertEqual(len(mails), 1)
        mail = mails
        self.assertEqual(mail.email_to, 'quinn.share@example.com')
        self.assertIn(claim.name, mail.body_html)
        self.assertIn('/my/expenses/%s' % claim.id, mail.body_html)
        self.assertIn('Open your claim', mail.body_html)
        self._clean(mail)
        self.assertTrue(claim.sudo().pb_told_approved_at)
        # a retry never sends twice
        claim.sudo()._pb_tell_employee('approved')
        claim.sudo()._after_approval_transition('approved')
        self.assertEqual(len(self._mails(
            claim, 'Your expense claim was approved')), 1)
        # paid: amount and date, once
        self._pay(claim)
        paid = self._mails(claim, 'Your expense claim was paid')
        self.assertEqual(len(paid), 1)
        self.assertIn(claim.name, paid.body_html)
        self._clean(paid)
        claim.sudo()._sync_paid()
        self.assertEqual(len(self._mails(
            claim, 'Your expense claim was paid')), 1)

    def test_wf2p2b_t12b_a_staff_login_and_the_engine_copy(self):
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self._approve(claim)
        self.assertEqual(len(self._mails(
            claim, 'Your expense claim was approved')), 1)
        self.assertFalse(self.sn_requester(claim, 'approved'),
                         'the engine leaves its own copy out')
        # switch off: the engine tells again (and Expenses still does)
        self.sn_switch(False)
        other = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self._approve(other)
        self.assertEqual(len(self.sn_requester(other, 'approved')), 1)
        self.assertEqual(len(self._mails(
            other, 'Your expense claim was approved')), 1)

    def test_wf2p2b_t12c_refused_with_the_reason_and_told_again(self):
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self.decide(claim, self.manager, 'reject', 'P2b: the photo is blurry')
        self.assertEqual(claim.state, 'refused')
        mails = self._mails(claim, 'Your expense claim was refused')
        self.assertEqual(len(mails), 1)
        self.assertIn('P2b: the photo is blurry', mails.body_html)
        self.assertIn('The reason given', mails.body_html)
        self._clean(mails)
        self.assertFalse(self.sn_requester(claim, 'rejected'))
        # fix and send again, refused again: a NEW decision is told
        self.facade(self.plain).reopen(claim)
        self.facade(self.plain).send(claim)
        claim.invalidate_recordset()
        self.decide(claim, self.manager, 'reject', 'P2b: still blurry')
        self.assertEqual(len(self._mails(
            claim, 'Your expense claim was refused')), 2)

    def test_wf2p2b_t12d_sent_back_stays_the_engines(self):
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self.decide(claim, self.manager, 'return', 'P2b: add the taxi')
        self.assertEqual(claim.state, 'draft')
        self.assertEqual(len(self.sn_requester(claim, 'returned')), 1)
        self.assertFalse(self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.expense.claim'), ('res_id', '=', claim.id),
            ('subject', 'like', 'Your expense claim')]))

    def test_wf2p2b_t12e_no_address_no_mail_and_the_engine_keeps_it(self):
        self.plain_emp.work_email = False
        self.plain.partner_id.email = False
        self.plain_emp.work_contact_id.email = False
        claim = self.sent_claim(user=self.plain, emp=self.plain_emp)
        self._approve(claim)
        self.assertFalse(self._mails(claim, 'Your expense claim was approved'))
        self.assertEqual(len(self.sn_requester(claim, 'approved')), 1,
                         'nobody would hear it otherwise')

    def test_wf2p2b_t12f_nothing_for_a_claim_that_did_not_move(self):
        claim = self.sent_claim()
        # a claim already approved before this code (no stamp): reading it,
        # listing it, syncing it sends nothing
        claim.sudo()._chain_engine_write('approved')
        self.facade().status(claim)
        self.facade().list_data(self.share_emp)
        claim.sudo()._sync_paid()
        self.assertFalse(self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.expense.claim'), ('res_id', '=', claim.id)]))

    def test_wf2p2b_t12g_in_the_employees_language(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.share.lang = 'vi_VN'
        claim = self.sent_claim(company_card=True)
        self.assertEqual(claim.sudo()._pb_mail_lang(), 'vi_VN')
        self._approve(claim)
        mail = self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.expense.claim'), ('res_id', '=', claim.id)])
        self.assertEqual(len(mail), 1)
        self.assertNotEqual(mail.subject, 'Your expense claim was approved')
        self.assertIn('Đề nghị hoàn chi phí', mail.subject)
        self._clean(mail)
        # and in Indonesian
        self.env['res.lang']._activate_lang('id_ID')
        for lang in ('en_US', 'vi_VN', 'id_ID'):
            rec = claim.sudo().with_context(lang=lang)
            for result in ('approved', 'refused', 'paid'):
                text = '%s %s' % (rec._pb_mail_subject(result),
                                  rec._pb_mail_body(result))
                for word in BANNED:
                    self.assertNotIn(word, text.lower())

    def test_wf2p2b_t12h_contract_lists_the_three_messages(self):
        caps = self.env['pb.expense.claim']._workflow_capabilities()
        rows = [(e['stage'], e['kind'], e['audience']) for e in caps['effects']
                if 'email' in e['text']]
        self.assertIn(('approved', 'message', 'requester'), rows)
        self.assertIn(('refused', 'message', 'requester'), rows)
        self.assertIn(('paid', 'message', 'requester'), rows)

    def test_wf2p2b_t14_claim_page_word(self):
        labels = self.env['pb.me.expense']._labels()
        self.assertEqual(labels['refused'][0], 'Refused — your turn')
        self.assertEqual(labels['approved'][0], 'Approved — being paid')
