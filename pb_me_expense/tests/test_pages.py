# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ETP E1.9 (and the HTTP halves of E1.2, E1.8, E1.10) — the pages over HTTP,
as an employee login AND as a full account (T-R6)."""
import re
from urllib.parse import urlparse

from odoo import fields, http
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import formatLang

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _pin_dbfilter

from .common import PASSWORD, PNG, ExpenseFixtures


def _path(url):
    return urlparse(url).path


@tagged('post_install', '-at_install')
class TestExpensePages(ExpenseFixtures, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls._expense_fixtures('test_e1_http', PASSWORD)

    # ------------------------------------------------------------ helpers
    def _post(self, url, data=None, files=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, files=files, timeout=60)

    def _text(self, response):
        return (response.text or '').replace('&#39;', "'").replace('&amp;', '&')

    def _money(self, amount):
        return formatLang(self.env, amount, currency_obj=self.company.currency_id)

    def _claims(self, emp):
        self.env.invalidate_all()
        return self.Claim.sudo().search([('employee_id', '=', emp.id)])

    # --------------------------------------------------------- the walk
    def _flow(self, user, password, emp):
        self.authenticate(user.login, password)
        today = fields.Date.to_string(fields.Date.context_today(user))

        page = self.url_open('/my/expenses', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('No claims yet.', page.text)
        self.assertIn('Snap a receipt and we take it from there.', page.text)

        new = self.url_open('/my/expenses/new', timeout=60)
        self.assertEqual(new.status_code, 200)
        text = self._text(new)
        self.assertIn('pbex-drop-zone', text)
        self.assertIn('Snap or choose a receipt', text)
        self.assertIn('name="receipt"', text)
        self.assertIn('capture="environment"', text, 'the camera button')
        cats = self.Facade.with_user(user).categories(emp)
        self.assertEqual(len(re.findall(r'name="product_id"', text)), len(cats),
                         'one chip per category in the first receipt')
        self.assertIn('name="amount"', text)
        self.assertTrue(re.search(r'name="date"[^>]*value="%s"' % today, text)
                        or re.search(r'value="%s"[^>]*name="date"' % today, text),
                        'the date defaults to today')
        has_trip = bool(self.Facade.with_user(user).trips_for(emp))
        if self.bridge and has_trip:
            self.assertIn('Which trip was this for?', text)
        else:
            self.assertNotIn('Which trip was this for?', text)

        # no file → the same page with the reason, nothing created, typed kept
        refused = self._post('/my/expenses/new', {
            'amount': '120000', 'product_id': self.cat.id, 'date': today,
            'note': 'E1 kept note', 'action': 'send'})
        self.assertEqual(refused.status_code, 200)
        self.assertIn('Add a photo or PDF of the receipt first.', self._text(refused))
        self.assertIn('E1 kept note', refused.text, 'the typed note is kept (T25)')
        self.assertIn('value="120000"', refused.text)
        self.assertFalse(self._claims(emp))

        response = self._post('/my/expenses/new', {
            'amount': '120000', 'product_id': self.cat.id, 'date': today,
            'note': 'E1 lunch', 'action': 'send',
            'employee_id': self.plain_emp.id if emp != self.plain_emp else self.share_emp.id,
        }, files={'receipt': ('lunch.png', PNG, 'image/png')})
        self.assertEqual(response.status_code, 200)
        claim = self._claims(emp)
        self.assertEqual(len(claim), 1, 'a forged employee_id is ignored')
        self.assertEqual(claim.create_uid, user)
        self.assertEqual(claim.state, 'submitted')
        self.assertEqual(_path(response.url), '/my/expenses/%s' % claim.id)
        self.assertIn('done=sent', response.url)
        text = self._text(response)
        thumb = re.search(r'/web/image/(\d+)/480x480\?access_token=([\w-]+)', text)
        self.assertTrue(thumb, 'the receipt thumbnail carries its token')
        image = self.url_open(thumb.group(0), timeout=60)
        self.assertEqual(image.status_code, 200)
        self.assertTrue(image.headers.get('Content-Type', '').startswith('image/'))
        full = re.search(r'/web/content/(\d+)\?access_token=([\w-]+)', text)
        self.assertEqual(self.url_open(full.group(0), timeout=60).status_code, 200)
        self.assertIn(self._money(120000), text)
        self.assertIn('pbex-pill--wait', text)
        self.assertIn('Waiting approval', text)
        step = claim.approval_request_id.step_ids.filtered(lambda s: s.status == 'active')
        self.assertIn(step.title, text, 'the step name is on the page')
        self.assertIn('E1 Manager Minh', text)
        self.assertIn('Sent to E1 Manager Minh', text, 'the toast names who has it')

        listing = self._text(self.url_open('/my/expenses', timeout=60))
        self.assertIn('/my/expenses/%s' % claim.id, listing)
        self.assertIn('E1 Meals', listing)
        self.assertIn('1 waiting', listing.replace('<b>', '').replace('</b>', ''))

        home = self._text(self.url_open('/my', timeout=60))
        self.assertIn('Claim back what you paid for', home, 'the Expenses tile')
        self.assertIn('expense_count', home)
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['expense_count']})
        self.assertEqual(counters.get('expense_count'), 0)

        # refused by the manager → home Needs you, My requests "your turn"
        self.decide(claim, self.manager, 'reject', 'E1: the date is cut off')
        home = self._text(self.url_open('/my', timeout=60))
        self.assertIn('1 expense claim refused — fix and resend', home)
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['expense_count']})
        self.assertEqual(counters.get('expense_count'), 1)
        mine = self._text(self.url_open('/my/requests', timeout=60))
        self.assertIn('Refused — your turn', mine)
        self.assertIn('pbme-rq-pill--act', mine)
        page = self._text(self.url_open('/my/expenses/%s' % claim.id, timeout=60))
        self.assertIn('Refused. Here is why:', page)
        self.assertIn('E1: the date is cut off', page)
        self.assertIn('Fix and resend', page)

        # fix and resend → attempt 2 → approved: My requests "ok"
        reopened = self._post('/my/expenses/%s/reopen' % claim.id)
        self.assertEqual(reopened.status_code, 200)
        self.assertIn('done=reopened', reopened.url)
        self.assertEqual(self._claims(emp).state, 'draft')
        added = self._post('/my/expenses/%s/receipt' % claim.id, {
            'amount': '30000', 'product_id': self.cat2.id, 'date': today, 'action': 'add'},
            files={'receipt': ('taxi.png', PNG, 'image/png')})
        self.assertIn('done=added', added.url)
        self.assertEqual(len(self._claims(emp).expense_ids), 2)
        sent = self._post('/my/expenses/%s/send' % claim.id)
        self.assertIn('done=sent', sent.url)
        claim = self._claims(emp)
        self.assertEqual(claim.approval_request_id.attempt, 2)
        self.decide(claim, self.manager)
        self.decide(claim, self.finance)
        self.assertEqual(self._claims(emp).state, 'approved')
        mine = self._text(self.url_open('/my/requests', timeout=60))
        self.assertIn('Approved — being paid', mine)
        self.assertIn('pbme-rq-pill--ok', mine)
        return claim

    def test_e1_9_flow_for_an_employee_login(self):
        self._flow(self.share, PASSWORD, self.share_emp)

    def test_e1_9b_flow_for_a_full_account(self):
        self._flow(self.plain, self.plain_password, self.plain_emp)

    # -------------------------------------------------- E1.8 over HTTP
    def test_e1_8_another_persons_claim_is_a_404(self):
        theirs = self.new_claim(user=self.plain, emp=self.plain_emp, amount=99000)
        self.authenticate(self.share.login, PASSWORD)
        page = self.url_open('/my/expenses/%s' % theirs.id, timeout=60)
        self.assertEqual(page.status_code, 404)
        self.assertIn('We could not find that claim', page.text)
        base = '/my/expenses/%s' % theirs.id
        for url in (base + '/send', base + '/withdraw', base + '/reopen',
                    base + '/receipt', base + '/receipt/%s/remove' % theirs.expense_ids.id):
            with self.subTest(url=url):
                response = self._post(url, {'amount': '1', 'product_id': self.cat.id},
                                      files={'receipt': ('x.png', PNG, 'image/png')}
                                      if url.endswith('/receipt') else None)
                self.assertEqual(response.status_code, 404)
        self.env.invalidate_all()
        self.assertEqual(theirs.state, 'draft')
        self.assertEqual(len(theirs.expense_ids), 1)
        self.assertEqual(self.url_open('/my/expenses/999999999', timeout=60).status_code, 404)

    # ----------------------------------------------- refusals over HTTP
    def test_e1_9c_refusals_render_the_page(self):
        self.authenticate(self.share.login, PASSWORD)
        today = fields.Date.to_string(self.today)
        wrong = self._post('/my/expenses/new', {
            'amount': '50000', 'product_id': self.cat.id, 'date': today, 'action': 'send'},
            files={'receipt': ('notes.txt', b'plain words', 'text/plain')})
        self.assertEqual(wrong.status_code, 200)
        self.assertIn('A receipt can be a photo (JPG, PNG or WEBP) or a PDF.', self._text(wrong))
        zero = self._post('/my/expenses/new', {
            'amount': '0', 'product_id': self.cat.id, 'date': today, 'action': 'send'},
            files={'receipt': ('a.png', PNG, 'image/png')})
        self.assertIn('Type how much you paid', self._text(zero))
        self.assertFalse(self._claims(self.share_emp))
        # "add another" without a script: a draft, then the claim page
        draft = self._post('/my/expenses/new', {
            'amount': '50000', 'product_id': self.cat.id, 'date': today, 'action': 'add'},
            files={'receipt': ('a.png', PNG, 'image/png')})
        claim = self._claims(self.share_emp)
        self.assertEqual(claim.state, 'draft')
        self.assertIn('done=saved', draft.url)
        self.assertIn('Saved as a draft', self._text(draft))
        self.assertIn('action="/my/expenses/%s/receipt"' % claim.id, draft.text)
        # two receipts in one post (the script's "Add another receipt")
        two = self._post('/my/expenses/new', {
            'amount': '10000', 'product_id': self.cat.id, 'date': today,
            'amount_1': '20000', 'product_id_1': self.cat2.id, 'date_1': today,
            'action': 'send'},
            files={'receipt': ('a.png', PNG, 'image/png'),
                   'receipt_1': ('b.png', PNG, 'image/png')})
        self.assertIn('done=sent', two.url)
        claims = self._claims(self.share_emp)
        multi = claims.filtered(lambda c: c.state == 'submitted')
        self.assertEqual(len(multi.expense_ids), 2)
        self.assertEqual(multi.total, 30000)
        # the second receipt's error names it
        bad = self._post('/my/expenses/new', {
            'amount': '10000', 'product_id': self.cat.id, 'date': today,
            'amount_1': '20000', 'date_1': today, 'action': 'send'},
            files={'receipt': ('a.png', PNG, 'image/png'),
                   'receipt_1': ('b.png', PNG, 'image/png')})
        self.assertIn('Receipt 2:', self._text(bad))
        self.assertIn('Pick what the receipt was for.', self._text(bad))
        # take back over HTTP
        back = self._post('/my/expenses/%s/withdraw' % multi.id)
        self.assertIn('done=withdrawn', back.url)
        self.assertEqual(self._claims(self.share_emp).filtered(
            lambda c: c.id == multi.id).state, 'draft')
        # "Send for approval" on the claim page with the add-a-receipt part
        # left empty sends what the claim holds (found by the browser walk)
        resent = self._post('/my/expenses/%s/receipt' % multi.id,
                            {'action': 'send', 'date': today, 'amount': ''})
        self.assertIn('done=sent', resent.url)
        self.assertEqual(self._claims(self.share_emp).filtered(
            lambda c: c.id == multi.id).state, 'submitted')

    # ---------------------------------------------- blocked, in words
    def test_e1_5_blocked_says_so_on_the_page(self):
        self.share_emp.parent_id = False
        self.share_emp.expense_manager_id = False
        claim = self.sent_claim()
        self.assertEqual(claim.sudo().approval_request_id.state, 'blocked')
        self.authenticate(self.share.login, PASSWORD)
        page = self._text(self.url_open('/my/expenses/%s' % claim.id, timeout=60))
        self.assertIn('Nobody is set up to approve this yet. HR can fix the route.', page)
        self.assertIn('Waiting approval', page)
        if 'pb.ask.hr.ticket' in self.env:
            self.assertIn('/my/ask-hr/new', page)

    # ------------------------------------------------- E1.10 over HTTP
    def test_e1_10_paid_strip(self):
        claim = self.sent_claim(company_card=True, amount=64000)
        self.decide(claim, self.manager)
        self.decide(claim, self.finance)
        journal = self.env['account.journal'].sudo().search(
            [('type', '=', 'general'), ('company_id', '=', self.company.id)], limit=1)
        move = self.env['account.move'].sudo().create({'move_type': 'entry',
                                                       'journal_id': journal.id})
        claim.expense_ids.sudo().write({'account_move_id': move.id})
        self.authenticate(self.share.login, PASSWORD)
        listing = self._text(self.url_open('/my/expenses', timeout=60))
        self.assertIn('paid this year', listing)
        self.assertIn(self._money(64000), listing)
        self.assertIn('pbex-pill--ok', listing)
