# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/expenses` — claim back what you paid for (ETP E1).

THE ROUTE IS THE GATE (ledger E-R2). The employee is re-resolved from the
SESSION on every request (`_ess_employee`, pb_me_portal); no route accepts an
employee id. A claim reached by id is browsed under sudo and used only when
its employee is one of the session's own (`_ess_own_employees`), else a styled
404 — for a GET and for every POST, before anything is written. The logic
lives in the `pb.me.expense` facade, which checks ownership against the
caller again and then works under sudo.

EVERY PAGE WORKS WITHOUT JAVASCRIPT (E-R8). The new-claim form is one plain
multipart POST: `action=send` sends it at once, `action=add` keeps it as a
draft and opens the claim page, whose own form adds the next receipt. The
script only makes it nicer (preview, amount formatting, more receipts in
place, Cmd/Ctrl+Enter). A refusal re-renders the same page with what was typed
kept and the reason in words — never a traceback, never a bare 500.
"""

import logging

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

from ..models.me_expense import (
    MAX_RECEIPTS, UPLOAD_MAX_BYTES, ExpenseRefusal,
)

_logger = logging.getLogger(__name__)

#: `?done=` keys the claim page has a toast for.
_DONE = ('sent', 'added', 'removed', 'withdrawn', 'reopened', 'already',
         'saved')
#: `?filter=` values of the list page.
_FILTERS = ('act', 'wait', 'done')


class PbMeExpensePortal(PbMePortal):

    # ------------------------------------------------------------ helpers
    def _ex_facade(self):
        return request.env['pb.me.expense']

    def _ex_claim(self, claim_id):
        """The claim as a SUDO record when it belongs to one of the
        session's own employees, else an empty recordset (the guard)."""
        Claim = request.env['pb.expense.claim'].sudo()
        try:
            claim = Claim.browse(int(claim_id)).exists()
        except (TypeError, ValueError):
            return Claim.browse()
        if claim and claim.employee_id in self._ess_own_employees():
            return claim
        return Claim.browse()

    def _ex_not_found(self):
        return request.render('pb_me_expense.portal_expense_missing',
                              {'page_name': 'expense_claim'}, status=404)

    def _ex_money_format(self, emp):
        """What the script needs to write an amount the way the reader's
        language does (thousands separators as they type)."""
        currency = emp.company_id.currency_id
        lang = request.env['res.lang']._lang_get(request.env.lang or 'en_US')
        return {
            'currency': currency,
            'decimals': currency.decimal_places,
            'symbol': currency.symbol or currency.name,
            'position': currency.position or 'after',
            'thousands': (lang.thousands_sep if lang else ',') or '',
            'decimal_point': (lang.decimal_point if lang else '.') or '.',
        }

    @staticmethod
    def _sfx(index):
        return '' if index == 0 else '_%s' % index

    def _ex_blocks(self, post):
        """The receipt blocks of a posted form, in order, with what was typed
        (``files`` are read separately)."""
        files = request.httprequest.files
        blocks = []
        for index in range(MAX_RECEIPTS):
            sfx = self._sfx(index)
            present = index == 0 or any(
                ('%s%s' % (key, sfx)) in post for key in ('amount', 'product_id', 'date')
            ) or files.get('receipt%s' % sfx)
            if not present:
                continue
            blocks.append({
                'idx': index,
                'n': len(blocks) + 1,
                'sfx': sfx,
                'amount': (post.get('amount%s' % sfx) or '').strip()[:32],
                'product_id': self._int(post.get('product_id%s' % sfx)),
                'date': (post.get('date%s' % sfx) or '').strip()[:10],
                'note': (post.get('note%s' % sfx) or '').strip()[:500],
                'company_card': bool(post.get('company_card%s' % sfx)),
            })
        return blocks

    @staticmethod
    def _int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _ex_file(self, sfx):
        """``(filename, bytes, declared type)`` of a block's file — the
        camera button and the file picker are two inputs for one receipt —
        read with a bound (E-R5), or None."""
        files = request.httprequest.files
        for name in ('receipt%s' % sfx, 'receipt_cam%s' % sfx):
            upload = files.get(name)
            if upload and upload.filename:
                data = upload.read(UPLOAD_MAX_BYTES + 1)
                return (upload.filename, data, upload.mimetype or '')
        return None

    def _ex_default_block(self, today):
        return {'idx': 0, 'n': 1, 'sfx': '', 'amount': '', 'product_id': 0,
                'date': fields.Date.to_string(today), 'note': '',
                'company_card': False}

    # ------------------------------------------------------ home counter
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'expense_count' in counters:
            emp = self._ess_employee()
            values['expense_count'] = self._ex_facade().waiting_on_you(emp) if emp else 0
        return values

    # =============================================================== list
    @http.route(['/my/expenses'], type='http', auth='user', website=True,
                methods=['GET'])
    def portal_my_expenses(self, filter=None, fresh=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        bucket = filter if filter in _FILTERS else 'all'
        data = self._ex_facade().list_data(emp, None if bucket == 'all' else bucket)
        values = {
            'page_name': 'expenses',
            'bucket': bucket,
            'counts': data['counts'],
            'paid_year': data['paid_year'],
            'cards': data['cards'],
            'fresh': self._int(fresh),
        }
        return request.render('pb_me_expense.portal_my_expenses', values)

    # ================================================================ new
    def _render_new(self, emp, blocks=None, error=None, error_n=None,
                    trip_id=None, status=200):
        facade = self._ex_facade()
        today = fields.Date.context_today(request.env.user)
        values = {
            'page_name': 'expenses_new',
            'categories': facade.categories(emp),
            'trips': facade.trips_for(emp),
            'trip_id': self._int(trip_id),
            'blocks': blocks or [self._ex_default_block(today)],
            'blank': dict(self._ex_default_block(today), sfx='__SFX__', n='__N__',
                          idx='__IDX__'),
            'today': fields.Date.to_string(today),
            'money': self._ex_money_format(emp),
            'error': error,
            'error_n': error_n,
            'max_receipts': MAX_RECEIPTS,
        }
        return request.render('pb_me_expense.portal_expense_new', values,
                              status=status)

    @http.route(['/my/expenses/new'], type='http', auth='user', website=True,
                methods=['GET'])
    def portal_my_expense_new(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._render_new(emp)

    @http.route(['/my/expenses/new'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_my_expense_create(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        facade = self._ex_facade()
        blocks = self._ex_blocks(post)
        trip_id = self._int(post.get('trip_id')) or None
        action = 'add' if post.get('action') == 'add' else 'send'
        # every receipt is checked BEFORE anything is created
        cleaned = []
        for block in blocks:
            receipt = self._ex_file(block['sfx'])
            try:
                facade.check_receipt(emp, receipt, block['amount'],
                                     block['product_id'], block['date'] or None,
                                     trip_id)
            except ExpenseRefusal as refusal:
                return self._render_new(emp, blocks, str(refusal),
                                        block['n'] if len(blocks) > 1 else None,
                                        trip_id)
            cleaned.append((block, receipt))
        try:
            # E-R2: the employee is the session's own (forced, never a form
            # value); the facade re-checks it against the caller, then sudo.
            with request.env.cr.savepoint():
                first, receipt = cleaned[0]
                claim = facade.new_claim(
                    emp, receipt, first['amount'], first['product_id'],
                    first['date'] or None, first['note'], first['company_card'],
                    trip_id)
                for block, receipt in cleaned[1:]:
                    facade.add_receipt(
                        claim, receipt, block['amount'], block['product_id'],
                        block['date'] or None, block['note'],
                        block['company_card'], trip_id)
        except (ExpenseRefusal, AccessError, UserError, ValidationError) as exc:
            _logger.info('pb_me_expense: a new claim was refused: %s', exc)
            return self._render_new(emp, blocks, str(exc), None, trip_id)
        url = '/my/expenses/%s' % claim.id
        if action == 'add':
            return request.redirect('%s?done=saved#pbex-add' % url)
        try:
            with request.env.cr.savepoint():
                facade.send(claim)
        except (UserError, ValidationError, AccessError) as exc:
            _logger.info('pb_me_expense: claim %s could not be sent: %s',
                         claim.id, exc)
            # the receipts are kept as a draft; the page says why it did
            # not go and what to do
            return self._render_claim(claim, send_error=str(exc))
        return request.redirect('%s?done=sent' % url)

    # ============================================================= claim
    def _render_claim(self, claim, done=None, error=None, send_error=None,
                      block=None, status=200):
        facade = self._ex_facade()
        emp = claim.employee_id
        page = facade.claim_page(claim)
        today = fields.Date.context_today(request.env.user)
        values = dict(page, **{
            'page_name': 'expense_claim',
            'done': done if done in _DONE else None,
            'error': error,
            'send_error': send_error,
            'categories': facade.categories(emp) if page['status']['can']['add'] else [],
            'block': block or self._ex_default_block(today),
            'today': fields.Date.to_string(today),
            'money': self._ex_money_format(emp),
            'ask_hr_url': '/my/ask-hr/new?category=other'
            if 'pb.ask.hr.ticket' in request.env else None,
        })
        return request.render('pb_me_expense.portal_expense_claim', values,
                              status=status)

    @http.route(['/my/expenses/<int:claim_id>'], type='http', auth='user',
                website=True, methods=['GET'])
    def portal_my_expense_claim(self, claim_id, done=None, **kw):
        claim = self._ex_claim(claim_id)
        if not claim:
            return self._ex_not_found()
        return self._render_claim(claim, done=done)

    @http.route(['/my/expenses/<int:claim_id>/receipt'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_expense_add(self, claim_id, **post):
        claim = self._ex_claim(claim_id)
        if not claim:
            return self._ex_not_found()
        facade = self._ex_facade()
        block = (self._ex_blocks(post) or [None])[0]
        receipt = self._ex_file('')
        if post.get('action') == 'send' and not receipt and not block['amount']:
            # "Send for approval" pressed with the add-a-receipt part left
            # empty: send what the claim already holds
            return self.portal_my_expense_send(claim_id)
        try:
            with request.env.cr.savepoint():
                facade.add_receipt(claim, receipt, block['amount'],
                                   block['product_id'], block['date'] or None,
                                   block['note'], block['company_card'])
        except (ExpenseRefusal, AccessError, UserError, ValidationError) as exc:
            _logger.info('pb_me_expense: a receipt was refused: %s', exc)
            return self._render_claim(claim, error=str(exc), block=block)
        if post.get('action') == 'send':
            return self.portal_my_expense_send(claim_id)
        return request.redirect('/my/expenses/%s?done=added' % claim.id)

    @http.route(['/my/expenses/<int:claim_id>/receipt/<int:expense_id>/remove'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_my_expense_remove(self, claim_id, expense_id, **post):
        claim = self._ex_claim(claim_id)
        if not claim:
            return self._ex_not_found()
        expense = request.env['hr.expense'].sudo().browse(expense_id).exists()
        if not expense or expense.pb_claim_id != claim:
            return self._ex_not_found()
        try:
            self._ex_facade().remove_receipt(claim, expense)
        except (ExpenseRefusal, AccessError, UserError, ValidationError) as exc:
            return self._render_claim(claim, error=str(exc))
        return request.redirect('/my/expenses/%s?done=removed' % claim.id)

    @http.route(['/my/expenses/<int:claim_id>/send'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_expense_send(self, claim_id, **post):
        claim = self._ex_claim(claim_id)
        if not claim:
            return self._ex_not_found()
        if claim.state != 'draft':
            return request.redirect('/my/expenses/%s?done=already' % claim.id)
        try:
            with request.env.cr.savepoint():
                self._ex_facade().send(claim)
        except (UserError, AccessError, ValidationError) as exc:
            _logger.info('pb_me_expense: claim %s could not be sent: %s',
                         claim.id, exc)
            return self._render_claim(claim, send_error=str(exc))
        return request.redirect('/my/expenses/%s?done=sent' % claim.id)

    @http.route(['/my/expenses/<int:claim_id>/withdraw'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_expense_withdraw(self, claim_id, **post):
        claim = self._ex_claim(claim_id)
        if not claim:
            return self._ex_not_found()
        try:
            done = 'withdrawn' if self._ex_facade().withdraw(claim) else 'already'
        except (UserError, AccessError, ValidationError) as exc:
            return self._render_claim(claim, error=str(exc))
        return request.redirect('/my/expenses/%s?done=%s' % (claim.id, done))

    @http.route(['/my/expenses/<int:claim_id>/reopen'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_expense_reopen(self, claim_id, **post):
        claim = self._ex_claim(claim_id)
        if not claim:
            return self._ex_not_found()
        try:
            done = 'reopened' if self._ex_facade().reopen(claim) else 'already'
        except (UserError, AccessError, ValidationError) as exc:
            return self._render_claim(claim, error=str(exc))
        return request.redirect('/my/expenses/%s?done=%s#pbex-add' % (claim.id, done))
