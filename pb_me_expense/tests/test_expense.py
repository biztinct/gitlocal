# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ETP E1 — the facade and the claim, without HTTP.

E1.1 categories · E1.2 a new claim (and the upload refusals) · E1.3 send ·
E1.4 the route (manager → finance; refuse; fix and resend = attempt 2) ·
E1.5 no manager · E1.6 take back · E1.7 the stock buttons · E1.8 ownership ·
E1.10 paid. The HTTP walk (E1.9) is in test_pages.py.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_me_expense.models.me_expense import (
    UPLOAD_MAX_BYTES, ExpenseRefusal,
)

from .common import PDF, PNG, ExpenseFixtures


@tagged('post_install', '-at_install')
class TestExpenseFacade(ExpenseFixtures, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._expense_fixtures('test_e1_facade')

    def _claims(self, emp=None):
        return self.Claim.sudo().search([('employee_id', '=', (emp or self.share_emp).id)])

    # ------------------------------------------------------------ E1.1
    def test_e1_1_categories(self):
        cats = self.facade().categories(self.share_emp)
        ids = {c['id'] for c in cats}
        self.assertIn(self.cat.id, ids, 'a shared expense category is offered')
        self.assertIn(self.cat2.id, ids)
        self.assertNotIn(self.priced.id, ids, 'a priced category (mileage) is left out')
        self.assertNotIn(self.foreign.id, ids, "another company's category is not offered")
        self.assertNotIn(self.not_expensable.id, ids)
        Product = self.env['product.product'].sudo()
        for row in cats:
            product = Product.browse(row['id'])
            self.assertTrue(product.can_be_expensed)
            self.assertIn(product.company_id.id, (False, self.share_emp.company_id.id))
        meals = next(c for c in cats if c['id'] == self.cat.id)
        self.assertEqual(meals['icon'], 'utensils', 'FOOD wears the utensils glyph')
        taxi = next(c for c in cats if c['id'] == self.cat2.id)
        self.assertEqual(taxi['icon'], 'receipt', 'anything else wears a receipt')
        # an own-company category is offered too
        own = self.env['product.product'].create({
            'name': 'E1 Own Company Snack', 'can_be_expensed': True,
            'company_id': self.share_emp.company_id.id})
        self.assertIn(own.id, {c['id'] for c in self.facade().categories(self.share_emp)})

    # ------------------------------------------------------------ E1.2
    def test_e1_2_new_claim_as_an_employee_login(self):
        claim = self.new_claim()
        self.assertEqual(claim.state, 'draft')
        self.assertEqual(claim.create_uid, self.share, 'sudo keeps the uid')
        self.assertTrue(claim.name.startswith('EXP/'), claim.name)
        self.assertEqual(len(claim.expense_ids), 1)
        exp = claim.expense_ids
        self.assertEqual(exp.employee_id, self.share_emp)
        self.assertEqual(exp.company_id, self.share_emp.company_id)
        self.assertEqual(exp.pb_claim_id, claim)
        self.assertEqual(exp.create_uid, self.share)
        self.assertEqual(exp.product_id, self.cat)
        self.assertEqual(exp.currency_id, self.share_emp.company_id.currency_id)
        self.assertEqual(exp.total_amount_currency, 150000)
        self.assertEqual(exp.payment_mode, 'own_account')
        self.assertEqual(exp.state, 'draft')
        self.assertFalse(exp.approval_state)
        att = exp.message_main_attachment_id
        self.assertTrue(att, 'the receipt is the main attachment')
        self.assertEqual((att.res_model, att.res_id), ('hr.expense', exp.id))
        self.assertEqual(att.mimetype, 'image/png')
        self.assertEqual(len(self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'hr.expense'), ('res_id', '=', exp.id)])), 1)
        self.assertEqual(claim.total, 150000)
        receipt = self.facade().claim_page(claim)['receipts'][0]
        self.assertIn('/web/image/%s/480x480?access_token=' % att.id, receipt['thumb'])
        self.assertIn('/web/content/%s?access_token=' % att.id, receipt['full'])
        # a typed amount with separators reads as the number
        claim2 = self.new_claim(amount='1,250,000')
        self.assertEqual(claim2.total, 1250000)
        # a PDF is a receipt too; a company card sets who paid
        claim3 = self.new_claim(receipt=('bill.pdf', PDF, 'application/pdf'), company_card=True)
        self.assertEqual(claim3.expense_ids.payment_mode, 'company_account')
        self.assertTrue(self.facade().claim_page(claim3)['receipts'][0]['is_pdf'])

    def test_e1_2b_refusals_create_nothing(self):
        before = len(self._claims())
        big = b'%PDF' + b'0' * (UPLOAD_MAX_BYTES - 3)
        self.assertEqual(len(big), UPLOAD_MAX_BYTES + 1)
        cases = [
            ('size', {'receipt': ('big.pdf', big, 'application/pdf')}),
            ('type', {'receipt': ('notes.txt', b'hello, this is text', 'image/png')}),
            ('amount', {'amount': 0}),
            ('amount', {'amount': 'abc'}),
            ('category', {'product': self.priced}),
            ('category', {'product': self.foreign}),
            ('date', {'date': self.today.replace(year=self.today.year + 1)}),
        ]
        for key, kw in cases:
            with self.subTest(key=key, kw=list(kw)):
                with self.assertRaises(ExpenseRefusal) as caught:
                    self.new_claim(**kw)
                self.assertEqual(caught.exception.key, key)
        with self.assertRaises(ExpenseRefusal) as caught:
            self.facade().new_claim(self.share_emp, None, 100, self.cat.id)
        self.assertEqual(caught.exception.key, 'nofile')
        self.assertIn('Add a photo or PDF of the receipt first', str(caught.exception))
        self.assertEqual(len(self._claims()), before, 'a refusal leaves nothing behind')

    def test_e1_2c_more_receipts_and_remove(self):
        claim = self.new_claim()
        self.facade().add_receipt(claim, ('taxi.pdf', PDF, 'application/pdf'), 85000,
                                  self.cat2.id, self.today, 'E1 taxi back')
        self.assertEqual(len(claim.expense_ids), 2)
        self.assertEqual(claim.total, 235000)
        taxi = claim.expense_ids.filtered(lambda e: e.product_id == self.cat2)
        att_id = taxi.message_main_attachment_id.id
        self.facade().remove_receipt(claim, taxi)
        self.assertEqual(len(claim.expense_ids), 1)
        self.assertFalse(self.env['ir.attachment'].sudo().browse(att_id).exists(),
                         'the file goes with its receipt')
        self.assertEqual(claim.total, 150000)

    # ------------------------------------------------------------ E1.3
    def test_e1_3_send(self):
        claim = self.new_claim()
        self.facade().send(claim)
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'submitted')
        self.assertTrue(claim.submitted_on)
        for exp in claim.expense_ids:
            self.assertEqual(exp.approval_state, 'submitted')
            self.assertEqual(exp.state, 'submitted')
        requests = self.env['biz.approval.request'].sudo().search(
            [('res_model', '=', 'pb.expense.claim'), ('res_id', '=', claim.id)])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.submitter_uid, self.share, 'the employee sent it in')
        self.assertEqual(requests.state, 'pending')
        with self.assertRaises(ExpenseRefusal) as caught:
            self.facade().send(claim)
        self.assertEqual(caught.exception.key, 'already')
        self.assertIn('already sent', str(caught.exception))
        empty = self.Claim.with_user(self.share).sudo().create({
            'employee_id': self.share_emp.id, 'company_id': self.share_emp.company_id.id})
        with self.assertRaises(UserError) as caught:
            self.facade().send(empty)
        self.assertIn('Add at least one receipt', str(caught.exception))
        self.assertEqual(empty.state, 'draft')

    # ------------------------------------------------------------ E1.4
    def test_e1_4_the_route_approve(self):
        claim = self.sent_claim()
        request = claim.sudo().approval_request_id
        steps = request.step_ids.filtered('included').sorted('sequence')
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].seat_ids.acting_user_id, self.manager, 'step one: their manager')
        self.assertEqual(steps[1].seat_ids.acting_user_id, self.finance, 'step two: the finance seat')
        status = self.facade().status(claim)
        self.assertEqual(status['step']['title'], steps[0].title)
        self.assertIn('E1 Manager Minh', status['step']['who'])

        self.decide(claim, self.manager)
        self.assertEqual(claim.state, 'submitted', 'still waiting: now with finance')
        self.assertEqual(steps[1].status, 'active')
        self.assertIn('E1 Finance Linh', self.facade().status(claim)['step']['who'])
        self.decide(claim, self.finance)
        self.assertEqual(claim.state, 'approved')
        self.assertEqual(request.state, 'applied')
        for exp in claim.expense_ids:
            self.assertEqual(exp.state, 'approved')
            self.assertEqual(exp.manager_id, self.finance, 'stock writes who approved it')
            self.assertTrue(exp.approval_date)
        self.assertEqual(self.facade().status(claim)['label'], 'Approved — being paid')

    def test_e1_4b_refuse_then_fix_and_resend(self):
        claim = self.sent_claim()
        self.decide(claim, self.manager, 'reject', 'E1: the photo is blurry')
        self.assertEqual(claim.state, 'refused')
        self.assertEqual(claim.refusal_reason, 'E1: the photo is blurry')
        for exp in claim.expense_ids:
            self.assertEqual(exp.state, 'refused')
        status = self.facade().status(claim)
        self.assertEqual((status['tone'], status['reason']), ('act', 'E1: the photo is blurry'))
        self.assertTrue(status['can']['reopen'])
        self.assertTrue(self.facade().reopen(claim))
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'draft')
        for exp in claim.expense_ids:
            self.assertEqual(exp.state, 'draft')
            self.assertFalse(exp.approval_state)
        self.assertEqual(self.facade().status(claim)['reason'], 'E1: the photo is blurry',
                         'the draft still says what to fix')
        self.assertFalse(self.facade().reopen(claim), 'a second press is a no-op')
        self.facade().send(claim)
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'submitted')
        self.assertEqual(claim.sudo().approval_request_id.attempt, 2, 'the engine counts it')
        self.assertFalse(claim.refusal_reason)

    def test_e1_4c_sent_back_is_a_draft_with_the_reason(self):
        claim = self.sent_claim()
        self.decide(claim, self.manager, 'return', 'E1: add the taxi too')
        self.assertEqual(claim.state, 'draft')
        self.assertEqual(claim.refusal_reason, 'E1: add the taxi too')
        self.assertFalse(claim.expense_ids.filtered('approval_state'))

    # ------------------------------------------------------------ E1.5
    def test_e1_5_no_manager_login_blocks_with_a_plain_sentence(self):
        self.share_emp.parent_id = False
        self.share_emp.expense_manager_id = False
        claim = self.sent_claim()
        request = claim.sudo().approval_request_id
        self.assertEqual(claim.state, 'submitted')
        self.assertEqual(request.state, 'blocked', 'the engine stops; it never skips the step')
        self.assertIn('No manager is recorded', request.block_reason)
        for exp in claim.expense_ids:
            self.assertEqual(exp.state, 'submitted', 'never approved by itself (ledger E1)')
        status = self.facade().status(claim)
        self.assertTrue(status['blocked'])
        self.assertEqual(status['label'], 'Waiting approval')
        self.assertIn('Nobody is set up to approve this yet. HR can fix the route.',
                      status['blocked_text'])
        # HR fixes the employee record; the engine's repair moves it on
        self.share_emp.parent_id = self.manager_emp
        self.Engine.sudo().repair(request)
        self.env.invalidate_all()
        self.assertEqual(request.state, 'pending')
        self.assertFalse(self.facade().status(claim)['blocked'])
        self.decide(claim, self.manager)
        self.decide(claim, self.finance)
        self.assertEqual(claim.state, 'approved')

    def test_e1_5b_the_expense_approver_on_the_employee_is_their_manager(self):
        self.share_emp.expense_manager_id = self.hr
        claim = self.sent_claim()
        step = claim.sudo().approval_request_id.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(step.seat_ids.acting_user_id, self.hr)

    # ------------------------------------------------------------ E1.6
    def test_e1_6_take_back(self):
        claim = self.sent_claim()
        request = claim.sudo().approval_request_id
        self.assertTrue(self.facade().withdraw(claim))
        self.env.invalidate_all()
        self.assertEqual(claim.state, 'draft')
        self.assertEqual(request.state, 'cancelled')
        for exp in claim.expense_ids:
            self.assertEqual(exp.state, 'draft')
        self.assertFalse(self.facade().withdraw(claim), 'already a draft')
        # approved → refused with words
        claim2 = self.sent_claim()
        self.decide(claim2, self.manager)
        self.decide(claim2, self.finance)
        with self.assertRaises(ExpenseRefusal) as caught:
            self.facade().withdraw(claim2)
        self.assertEqual(caught.exception.key, 'approved')
        self.assertEqual(claim2.state, 'approved')

    def test_e1_6b_withdrawn_from_the_inbox_is_mirrored(self):
        claim = self.sent_claim()
        request = claim.sudo().approval_request_id
        # the submitter withdraws from the inbox (engine.cancel), not the page
        self.Engine.with_user(self.share).sudo().cancel(request, 'E1 inbox withdraw')
        self.env.invalidate_all()
        self.assertEqual(claim.state, 'draft')
        self.assertFalse(claim.expense_ids.filtered('approval_state'))

    # ------------------------------------------------------------ E1.7
    def test_e1_7_stock_buttons(self):
        claim = self.sent_claim()
        exp = claim.expense_ids
        for method in ('action_approve', 'action_refuse', 'action_reset'):
            with self.subTest(method=method):
                with self.assertRaises(UserError) as caught:
                    getattr(exp.with_user(self.hr), method)()
                self.assertIn('This receipt is part of claim %s. Decide it from Approvals.'
                              % claim.name, str(caught.exception))
        self.assertEqual(exp.state, 'submitted')
        # an expense with no claim: stock behaviour, untouched
        plain = self.env['hr.expense'].create({
            'name': 'E1 plain stock expense', 'employee_id': self.plain_emp.id,
            'product_id': self.cat2.id, 'total_amount_currency': 7771,
            'company_id': self.company.id})
        plain.sudo().write({'approval_state': 'submitted'})
        plain.with_user(self.hr).action_approve()
        self.assertEqual(plain.state, 'approved')

    # ------------------------------------------------------------ E1.8
    def test_e1_8_ownership(self):
        theirs = self.new_claim(user=self.plain, emp=self.plain_emp, amount=99000)
        mine = self.new_claim()
        own = self.facade().own_claims(self.share_emp)
        self.assertIn(mine, own)
        self.assertNotIn(theirs, own)
        for call in (lambda: self.facade().send(theirs),
                     lambda: self.facade().withdraw(theirs),
                     lambda: self.facade().reopen(theirs),
                     lambda: self.facade().status(theirs),
                     lambda: self.facade().remove_receipt(theirs, theirs.expense_ids),
                     lambda: self.facade().add_receipt(theirs, ('x.png', PNG, 'image/png'),
                                                       10, self.cat.id),
                     lambda: self.facade().own_claims(self.plain_emp),
                     lambda: self.facade().new_claim(self.plain_emp, ('x.png', PNG, 'image/png'),
                                                     10, self.cat.id)):
            with self.assertRaises(AccessError):
                call()
        theirs.invalidate_recordset()
        self.assertEqual(theirs.state, 'draft')
        self.assertEqual(len(theirs.expense_ids), 1)
        # a receipt of another claim cannot be removed through mine
        with self.assertRaises(AccessError):
            self.facade().remove_receipt(mine, theirs.expense_ids)

    def test_e1_8b_backend_access(self):
        """No portal ACL row (E-R2); a full account reads only its own."""
        theirs = self.new_claim(user=self.plain, emp=self.plain_emp, amount=99000)
        mine = self.new_claim()
        with self.assertRaises(AccessError):
            self.Claim.with_user(self.share).search([])
        found = self.Claim.with_user(self.plain).search([])
        self.assertIn(theirs, found)
        self.assertNotIn(mine, found)
        portal = self.env.ref('base.group_portal')
        rows = self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', 'pb.expense.claim'), ('group_id', '=', portal.id)])
        self.assertFalse(rows)
        # a seat is a read and a write (the engine writes as the decider)
        claim = self.sent_claim()
        self.assertTrue(self.Claim.with_user(self.manager).search([('id', '=', claim.id)]))

    # ------------------------------------------------------------ E1.10
    def test_e1_10_paid(self):
        claim = self.sent_claim(company_card=True)
        self.decide(claim, self.manager)
        self.decide(claim, self.finance)
        self.assertEqual(claim.state, 'approved')
        journal = self.env['account.journal'].sudo().search(
            [('type', '=', 'general'), ('company_id', '=', self.company.id)], limit=1)
        self.assertTrue(journal, 'the clone has a miscellaneous journal')
        move = self.env['account.move'].sudo().create(
            {'move_type': 'entry', 'journal_id': journal.id})
        # stock: a company-paid expense with its journal entry reads "paid"
        # (`hr.expense._compute_state`); the write is the one stock's posting
        # makes (`expense_ids` on the entry writes `account_move_id`)
        claim.expense_ids.sudo().write({'account_move_id': move.id})
        self.env.invalidate_all()
        self.assertEqual(claim.expense_ids.state, 'paid')
        self.assertEqual(claim.state, 'paid')
        self.assertEqual(claim.paid_on, self.today)
        data = self.facade().list_data(self.share_emp)
        self.assertTrue(data['paid_year'])
        self.assertEqual(self.facade().status(claim)['label'], 'Paid')
        self.assertEqual(self.facade().steps(claim)[-1]['status'], 'done')

    # ----------------------------------------------------- home + My requests
    def test_e1_9a_home_hooks(self):
        Home = self.env['pb.me.home'].with_user(self.share)
        claim = self.sent_claim()
        rows = Home.get_my_requests(self.share_emp)['rows']
        row = next(r for r in rows if r['key'] == 'expense_claim' and r['id'] == claim.id)
        self.assertEqual((row['state_label'], row['tone']), ('Waiting approval', 'wait'))
        self.assertIn('1 receipt', row['title'])
        self.assertEqual(row['url'], '/my/expenses/%s' % claim.id)
        self.decide(claim, self.manager, 'reject', 'E1 no')
        rows = Home.get_my_requests(self.share_emp)['rows']
        row = next(r for r in rows if r['key'] == 'expense_claim' and r['id'] == claim.id)
        self.assertEqual((row['state_label'], row['tone']), ('Refused — your turn', 'act'))
        found = {}
        Home._pbme_needs_extra(self.share_emp, lambda key, n, url, **kw: found.update(
            {key: dict(kw, n=n, url=url)}))
        self.assertIn('expense_refused', found)
        self.assertEqual(found['expense_refused']['url'], '/my/expenses/%s' % claim.id)
        self.assertIn('fix and resend', found['expense_refused']['label'])
        self.assertEqual(self.facade().waiting_on_you(self.share_emp), 1)
