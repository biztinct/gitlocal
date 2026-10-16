# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.me.expense` — everything the expense pages do, callable without HTTP.

THE GUARD FIRST, THEN SUDO (ledger E-R2/E-R3). Every method takes the
caller's own employee or claim and checks it against the CALLER (`env.uid`):
the employee's login must be the caller. Only then does it switch to sudo,
because an employee login holds no right on claims, expenses or attachments.
`sudo()` keeps the uid, so `create_uid`, the engine's submitter and the
message author stay the employee.

A WHITELIST OF WHAT A FORM MAY SET. A receipt is a file, an amount, a
category, a date, a note, "paid with a company card" and (soft) a trip. The
employee, the company, the currency, the claim and every status are set here,
never read from a request.

REFUSALS ARE PLAIN SENTENCES. `ExpenseRefusal` carries a short key (for the
page and the tests) and the sentence a person reads.
"""

import base64
import logging
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

#: How big one receipt file may be (E-R5).
UPLOAD_MAX_BYTES = 10 * 1024 * 1024
#: The kinds of file a receipt may be (E-R5), decided from the file's own
#: first bytes — never from what the browser says it is.
MIME_OK = ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')
#: How many receipts one claim may carry.
MAX_RECEIPTS = 20
#: How far back an approved trip is still offered on a new claim (D8).
TRIP_DAYS_BACK = 60
#: A claim's state → the filter it counts under on the list page.
BUCKETS = {'draft': 'act', 'refused': 'act', 'submitted': 'wait',
           'approved': 'done', 'paid': 'done'}
#: Category code → the glyph its chip wears (D7); anything else: a receipt.
CATEGORY_ICONS = {'FOOD': 'utensils', 'TRANS & ACC': 'car', 'COMM': 'phone',
                  'GIFT': 'gift'}


class ExpenseRefusal(UserError):
    """A refusal with a short key the page and the tests can tell apart."""

    def __init__(self, key, message):
        super().__init__(message)
        self.key = key


def sniff_mimetype(data):
    """The kind of file from its first bytes; '' when it is none we take."""
    head = bytes(data[:16]) if data else b''
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head.startswith(b'%PDF'):
        return 'application/pdf'
    return ''


class PbMeExpense(models.AbstractModel):
    _name = 'pb.me.expense'
    _description = 'Expenses on the employee pages'

    # =================================================================
    #  guards
    # =================================================================
    @api.model
    def _own_employee(self, emp):
        """``emp`` (sudo) when its login is the caller, else AccessError."""
        emp = emp.sudo()[:1] if isinstance(emp, models.BaseModel) else \
            self.env['hr.employee'].sudo().browse()
        if not emp or not emp.user_id or emp.user_id.id != self.env.uid:
            raise AccessError(self.env._("That is not your employee record."))
        return emp

    @api.model
    def _own_claim(self, claim):
        """``claim`` (sudo) when it is the caller's own, else AccessError."""
        claim = claim.sudo().exists()[:1] if isinstance(claim, models.BaseModel) \
            else self.env['pb.expense.claim'].sudo().browse()
        if not claim or claim.employee_id.user_id.id != self.env.uid:
            raise AccessError(self.env._("We could not find that claim."))
        return claim

    # =================================================================
    #  small helpers
    # =================================================================
    @api.model
    def _money(self, amount, currency):
        return formatLang(self.env, amount or 0.0, currency_obj=currency)

    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _trip_bridge(self):
        """Is the trip ↔ expense bridge installed (D8, soft)?"""
        return ('pb_trip_id' in self.env['hr.expense']._fields
                and 'pb.business.trip' in self.env)

    @api.model
    def parse_amount(self, value, currency):
        """A typed amount as a float, or None. Accepts what the page sends —
        thousands separators as the reader's language writes them — and a
        plain number. A currency without decimals (the dong) reads every dot
        and comma as a thousands separator."""
        if isinstance(value, (int, float)):
            return float(value)
        text = re.sub(r'[^\d.,\-]', '', str(value or ''))
        if not text or not re.search(r'\d', text):
            return None
        if currency.decimal_places == 0:
            text = text.replace(',', '').replace('.', '')
        else:
            lang = self.env['res.lang']._lang_get(self.env.lang or 'en_US')
            thousands = (lang.thousands_sep if lang else ',') or ''
            decimal = (lang.decimal_point if lang else '.') or '.'
            if thousands:
                text = text.replace(thousands, '')
            if decimal != '.':
                text = text.replace(decimal, '.')
            if text.count('.') > 1:
                head, _sep, tail = text.rpartition('.')
                text = head.replace('.', '') + '.' + tail
        try:
            amount = float(text)
        except ValueError:
            return None
        return amount if amount < 1e13 else None

    # =================================================================
    #  what the form offers
    # =================================================================
    @api.model
    def _category_products(self, emp):
        emp = self._own_employee(emp)
        company = emp.company_id
        Product = self.env['product.product'].sudo().with_company(company)
        products = Product.search([
            ('can_be_expensed', '=', True),
            ('company_id', 'in', [False, company.id]),
        ], order='name, id')
        # A product with a cost is priced per unit (Mileage): quantity × cost,
        # not "type what you paid" — left out of this release (ledger E5).
        return products.filtered(lambda p: not p.standard_price)

    @api.model
    def categories(self, emp):
        """The chips of the new-claim form (D7): ``[{id, name, code, icon}]``."""
        return [{
            'id': p.id,
            'name': p.name,
            'code': p.default_code or '',
            'icon': CATEGORY_ICONS.get((p.default_code or '').upper(), 'receipt'),
        } for p in self._category_products(emp)]

    @api.model
    def trips_for(self, emp):
        """The person's own approved trips that ended no more than 60 days ago
        (D8). Empty when the trip bridge is not installed."""
        emp = self._own_employee(emp)
        if not self._trip_bridge():
            return []
        since = self._today() - timedelta(days=TRIP_DAYS_BACK)
        trips = self.env['pb.business.trip'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'approved'),
            ('date_to', '>=', since)], order='date_from desc, id desc')
        rows = []
        for trip in trips:
            where = trip.destination_city or trip.destination_country_id.name or ''
            rows.append({
                'id': trip.id, 'name': trip.name, 'where': where,
                'from': trip.date_from, 'to': trip.date_to,
            })
        return rows

    # =================================================================
    #  one receipt: check, then create
    # =================================================================
    @api.model
    def check_receipt(self, emp, receipt, amount, product_id, date=None,
                      trip_id=None):
        """Every check a receipt must pass, before anything is created.
        Returns the cleaned values; raises `ExpenseRefusal` with the reason."""
        _ = self.env._
        emp = self._own_employee(emp)
        currency = emp.company_id.currency_id
        if not receipt or not receipt[1]:
            raise ExpenseRefusal('nofile', _(
                "Add a photo or PDF of the receipt first."))
        filename, data, _declared = (tuple(receipt) + (None, None, None))[:3]
        if len(data) > UPLOAD_MAX_BYTES:
            raise ExpenseRefusal('size', _(
                "That file is over 10 MB. Try a smaller photo, or a PDF of "
                "the page."))
        mimetype = sniff_mimetype(data)
        if mimetype not in MIME_OK:
            raise ExpenseRefusal('type', _(
                "A receipt can be a photo (JPG, PNG or WEBP) or a PDF. Choose "
                "another file."))
        value = self.parse_amount(amount, currency)
        if value is None or currency.compare_amounts(value, 0.0) <= 0:
            raise ExpenseRefusal('amount', _(
                "Type how much you paid. It has to be more than zero."))
        value = currency.round(value)
        try:
            product_id = int(product_id or 0)
        except (TypeError, ValueError):
            product_id = 0
        product = self._category_products(emp).filtered(
            lambda p: p.id == product_id)
        if not product:
            raise ExpenseRefusal('category', _(
                "Pick what the receipt was for."))
        today = self._today()
        try:
            when = fields.Date.to_date(date) if date else today
        except (TypeError, ValueError):
            when = None
        if not when:
            raise ExpenseRefusal('date', _(
                "That date could not be read. Pick the day on the receipt."))
        if when > today:
            raise ExpenseRefusal('date', _(
                "The receipt date cannot be in the future."))
        trip = None
        if trip_id:
            try:
                trip_id = int(trip_id)
            except (TypeError, ValueError):
                trip_id = 0
            if trip_id:
                allowed = {t['id'] for t in self.trips_for(emp)}
                if trip_id not in allowed:
                    raise ExpenseRefusal('trip', _(
                        "Pick one of your own approved trips, or leave it "
                        "empty."))
                trip = self.env['pb.business.trip'].sudo().browse(trip_id)
        name = (filename or '').strip().replace('/', '-')[-120:] or (
            'receipt.pdf' if mimetype == 'application/pdf' else 'receipt.jpg')
        return {'filename': name, 'data': data, 'mimetype': mimetype,
                'amount': value, 'product': product, 'date': when,
                'trip': trip}

    @api.model
    def _create_receipt(self, claim, clean, note=None, company_card=False):
        """One receipt = one stock expense (D6), then its file: the
        attachment is created bound to the expense that now exists and set
        as its main attachment (ledger E4). The caller holds the savepoint."""
        emp = claim.employee_id
        company = emp.company_id
        note = (note or '').strip()
        product = clean['product']
        name = note[:80] or '%s · %s' % (product.name,
                                         format_date(self.env, clean['date']))
        vals = {
            'name': name,
            'date': clean['date'],
            'employee_id': emp.id,
            'company_id': company.id,
            'product_id': product.id,
            'currency_id': company.currency_id.id,
            'total_amount_currency': clean['amount'],
            'payment_mode': 'company_account' if company_card else 'own_account',
            'description': note or False,
            'pb_claim_id': claim.id,
        }
        trip = clean.get('trip')
        if trip is None and self._trip_bridge():
            # a receipt added later rides with the claim's trip, if it has one
            trip = claim.expense_ids.mapped('pb_trip_id')[:1] or None
        if trip and self._trip_bridge():
            vals['pb_trip_id'] = trip.id
        expense = self.env['hr.expense'].sudo().with_company(company).create(vals)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': clean['filename'],
            'datas': base64.b64encode(clean['data']),
            'mimetype': clean['mimetype'],
            'res_model': 'hr.expense',
            'res_id': expense.id,
        })
        expense._message_set_main_attachment_id(attachment, force=True)
        return expense

    # =================================================================
    #  the claim's life
    # =================================================================
    @api.model
    def new_claim(self, emp, receipt=None, amount=None, product_id=None,
                  date=None, note=None, company_card=False, trip_id=None):
        """A draft claim with its first receipt. Nothing is created when a
        check fails (one savepoint)."""
        emp = self._own_employee(emp)
        clean = self.check_receipt(emp, receipt, amount, product_id, date,
                                   trip_id)
        with self.env.cr.savepoint():
            claim = self.env['pb.expense.claim'].sudo().create({
                'employee_id': emp.id,
                'company_id': emp.company_id.id,
            })
            self._create_receipt(claim, clean, note, company_card)
        return claim

    @api.model
    def add_receipt(self, claim, receipt=None, amount=None, product_id=None,
                    date=None, note=None, company_card=False, trip_id=None):
        """One more receipt on a draft claim."""
        _ = self.env._
        claim = self._own_claim(claim)
        if claim.state != 'draft':
            raise ExpenseRefusal('locked', _(
                "This claim is already sent. Take it back first to change "
                "it."))
        if len(claim.expense_ids) >= MAX_RECEIPTS:
            raise ExpenseRefusal('count', _(
                "A claim can carry up to %s receipts. Send this one and start "
                "a new claim for the rest.", MAX_RECEIPTS))
        clean = self.check_receipt(claim.employee_id, receipt, amount,
                                   product_id, date, trip_id)
        with self.env.cr.savepoint():
            expense = self._create_receipt(claim, clean, note, company_card)
        return expense

    @api.model
    def remove_receipt(self, claim, expense):
        """Take a receipt off a draft claim (its file goes with it)."""
        _ = self.env._
        claim = self._own_claim(claim)
        if claim.state != 'draft':
            raise ExpenseRefusal('locked', _(
                "This claim is already sent. Take it back first to change "
                "it."))
        expense = expense.sudo().exists() if isinstance(expense, models.BaseModel) \
            else self.env['hr.expense'].sudo().browse()
        if not expense or expense.pb_claim_id != claim:
            raise AccessError(_("That receipt is not on this claim."))
        with self.env.cr.savepoint():
            self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'hr.expense'),
                ('res_id', '=', expense.id)]).unlink()
            expense.unlink()
        return True

    @api.model
    def _ensure_route(self, claim):
        """A company created after install has no expense route yet: lay the
        default one the first time somebody there sends a claim (idempotent).
        Without a route the claim's own fallback ladder applies."""
        if claim._engine_managed():
            return True
        try:
            with self.env.cr.savepoint():
                self.env['pb.expense.claim'].sudo()._approval_seed_default(
                    claim.company_id)
        except Exception:               # noqa: BLE001 — never block a send
            _logger.warning('pb_me_expense: no expense route could be laid '
                            'for %s', claim.company_id.name, exc_info=True)
        return claim._engine_managed()

    @api.model
    def send(self, claim):
        """Send a draft claim for approval (D3): every expense is marked
        submitted under sudo (never stock `action_submit`, ledger E1) and the
        claim goes to the engine. One savepoint: a refusal leaves the claim a
        draft with its expenses untouched."""
        _ = self.env._
        claim = self._own_claim(claim)
        if claim.state != 'draft':
            raise ExpenseRefusal('already', _(
                "This claim is already sent. You can see where it is below."))
        claim._check_ready()
        self._ensure_route(claim)
        with self.env.cr.savepoint():
            claim.expense_ids.write({'approval_state': 'submitted',
                                     'manager_id': False})
            claim.write({'refusal_reason': False})
            claim.action_submit()
        claim.invalidate_recordset()
        return claim

    @api.model
    def withdraw(self, claim):
        """Take a sent claim back (D5): the open request is withdrawn
        through the engine, the claim and its expenses are drafts again
        (`pb.expense.claim._approval_withdraw`). False when it is already a
        draft."""
        _ = self.env._
        claim = self._own_claim(claim)
        if claim.state == 'draft':
            return False
        if claim.state in ('approved', 'paid'):
            raise ExpenseRefusal('approved', _(
                "This claim is already approved, so it cannot be taken back. "
                "If something is wrong, ask HR."))
        if claim.state == 'refused':
            raise ExpenseRefusal('refused', _(
                "This claim was refused. Use Fix and resend to change it."))
        request = claim._chain_open_request()
        with self.env.cr.savepoint():
            if request:
                self.env['biz.approval.engine'].sudo().cancel(
                    request.sudo(),
                    _("Taken back by %s", claim.employee_id.name or ''))
            else:
                claim._approval_withdraw(None, '')
        claim.invalidate_recordset()
        return True

    @api.model
    def reopen(self, claim):
        """Fix and resend (D4): a refused claim becomes a draft again; its
        expenses lose their refusal. The reason stays on the claim so the
        page can say what to fix. False when it is already a draft."""
        _ = self.env._
        claim = self._own_claim(claim)
        if claim.state == 'draft':
            return False
        if claim.state != 'refused':
            raise ExpenseRefusal('not_refused', _(
                "Only a refused claim can be fixed and sent again."))
        with self.env.cr.savepoint():
            claim._chain_engine_write('draft')
            claim._chain_log('refused', 'draft', '')
            claim._pb_back_to_draft()
        return True

    # =================================================================
    #  reading
    # =================================================================
    @api.model
    def own_claims(self, emp, bucket=None):
        """The person's claims, newest first; ``bucket`` keeps one filter
        (`act` / `wait` / `done`)."""
        emp = self._own_employee(emp)
        claims = self.env['pb.expense.claim'].sudo().search(
            [('employee_id.user_id', '=', self.env.uid),
             ('employee_id', '=', emp.id)])
        claims.filtered(lambda c: c.state == 'approved')._sync_paid()
        if bucket in ('act', 'wait', 'done'):
            claims = claims.filtered(lambda c: BUCKETS.get(c.state) == bucket)
        return claims

    @api.model
    def _labels(self):
        _ = self.env._
        return {
            'draft': (_('Draft'), 'off'),
            'submitted': (_('Waiting approval'), 'wait'),
            'approved': (_('Approved — being paid'), 'ok'),
            'paid': (_('Paid'), 'ok'),
            'refused': (_('Refused — see why'), 'act'),
        }

    @api.model
    def status(self, claim):
        """Where a claim is, in plain words:
        ``{state, label, tone, step, reason, blocked, blocked_text, can}``.
        ``step`` is ``{title, who}`` while it waits on somebody."""
        _ = self.env._
        claim = self._own_claim(claim)
        claim._sync_paid()
        state = claim.state
        label, tone = self._labels().get(state, (state, 'off'))
        open_request = claim._chain_open_request()
        blocked = bool(open_request and open_request.state == 'blocked')
        step = None
        if state == 'submitted':
            active = open_request.step_ids.filtered(
                lambda s: s.status == 'active').sorted('sequence')[:1] \
                if open_request else None
            if active:
                who = ', '.join(sorted({n for n in active.seat_ids.mapped(
                    'acting_user_id.name') if n}))
                step = {'title': active.title or '', 'who': who}
            elif not open_request:
                # no route published: the claim's own ladder (HR approver)
                step = {'title': _('your HR team'), 'who': ''}
        n = len(claim.expense_ids)
        return {
            'state': state,
            'label': label,
            'tone': tone,
            'step': step,
            'reason': (claim.refusal_reason or '') if state in ('refused', 'draft') else '',
            'blocked': blocked,
            'blocked_text': _("Nobody is set up to approve this yet. HR can "
                              "fix the route.") if blocked else '',
            'attempt': claim.approval_request_id.attempt or 0,
            'can': {
                'add': state == 'draft' and n < MAX_RECEIPTS,
                'remove': state == 'draft',
                'send': state == 'draft' and n > 0,
                'withdraw': state == 'submitted',
                'reopen': state == 'refused',
            },
        }

    @api.model
    def steps(self, claim):
        """The route of the latest request as stepper rows
        ``[{title, status, who}]`` (status: done / current / pending /
        blocked / refused / skipped). Empty for a draft."""
        _ = self.env._
        claim = self._own_claim(claim)
        request = claim.approval_request_id
        if not request or claim.state == 'draft':
            return []
        rows = [{'title': _('Sent'), 'status': 'done', 'who': ''}]
        status_map = {'done': 'done', 'active': 'current', 'pending': 'pending',
                      'blocked': 'blocked', 'skipped': 'skipped',
                      'returned': 'refused'}
        for step in request.sudo().step_ids.filtered('included').sorted('sequence'):
            if step.kind in ('notify', 'fast'):
                continue
            status = status_map.get(step.status, 'pending')
            if any(seat.status == 'rejected' for seat in step.seat_ids):
                status = 'refused'
            who = ', '.join(sorted({n for n in step.seat_ids.mapped(
                'acting_user_id.name') if n}))
            rows.append({'title': step.title or '', 'status': status, 'who': who})
        if claim.state in ('approved', 'paid'):
            rows.append({'title': _('Paid'),
                         'status': 'done' if claim.state == 'paid' else 'current',
                         'who': ''})
        elif claim.state == 'submitted':
            rows.append({'title': _('Paid'), 'status': 'pending', 'who': ''})
        return rows

    # ----------------------------------------------------------- payloads
    @api.model
    def _receipt_payload(self, expense):
        """One receipt card: tokened links for every kind of login (E-R6)."""
        attachment = expense.message_main_attachment_id or expense.attachment_ids[:1]
        token = attachment.sudo().generate_access_token()[0] if attachment else ''
        is_pdf = bool(attachment) and attachment.mimetype == 'application/pdf'
        return {
            'id': expense.id,
            'name': expense.name or '',
            'category': expense.product_id.name or '',
            'icon': CATEGORY_ICONS.get((expense.product_id.default_code or '').upper(),
                                       'receipt'),
            'date': expense.date,
            'amount': self._money(expense.total_amount_currency, expense.currency_id),
            'note': expense.description or '',
            'company_card': expense.payment_mode == 'company_account',
            'has_file': bool(attachment),
            'is_pdf': is_pdf,
            'filename': (attachment.name or '') if attachment else '',
            'thumb': ('/web/image/%s/480x480?access_token=%s' % (attachment.id, token))
            if attachment and not is_pdf else '',
            'full': ('/web/content/%s?access_token=%s' % (attachment.id, token))
            if attachment else '',
        }

    @api.model
    def claim_card(self, claim):
        """One card on the list page."""
        claim = self._own_claim(claim)
        label, tone = self._labels().get(claim.state, (claim.state, 'off'))
        exps = claim.expense_ids.sorted('id')
        first = next((e for e in exps if e.message_main_attachment_id), exps[:1])
        receipt = self._receipt_payload(first) if first else None
        return {
            'id': claim.id,
            'name': claim.name,
            'title': ', '.join(dict.fromkeys(
                p for p in exps.mapped('product_id.name') if p)) or claim.name,
            'n': len(exps),
            'amount': self._money(claim.total, claim.currency_id),
            'state': claim.state,
            'label': label,
            'tone': tone,
            'date': (claim.submitted_on or claim.create_date),
            'thumb': receipt['thumb'] if receipt else '',
            'is_pdf': receipt['is_pdf'] if receipt else False,
            'url': '/my/expenses/%s' % claim.id,
        }

    @api.model
    def list_data(self, emp, bucket=None):
        """The list page: the strip, the filter counts and the cards."""
        claims = self.own_claims(emp)
        counts = {'act': 0, 'wait': 0, 'done': 0, 'all': len(claims)}
        for claim in claims:
            counts[BUCKETS.get(claim.state, 'done')] += 1
        year = self._today().year
        paid = {}
        for claim in claims.filtered(lambda c: c.state == 'paid'
                                     and c.paid_on and c.paid_on.year == year):
            paid[claim.currency_id] = paid.get(claim.currency_id, 0.0) + claim.total
        shown = claims
        if bucket in ('act', 'wait', 'done'):
            shown = claims.filtered(lambda c: BUCKETS.get(c.state) == bucket)
        return {
            'counts': counts,
            # never one total over two currencies: one figure per currency
            'paid_year': ' + '.join(self._money(v, c) for c, v in paid.items()),
            'cards': [self.claim_card(c) for c in shown],
        }

    @api.model
    def claim_page(self, claim):
        """Everything the claim page draws."""
        claim = self._own_claim(claim)
        exps = claim.expense_ids.sorted('id')
        trips = exps.mapped('pb_trip_id') if self._trip_bridge() else None
        return {
            'claim': claim,
            'id': claim.id,
            'name': claim.name,
            'total': self._money(claim.total, claim.currency_id),
            'receipts': [self._receipt_payload(e) for e in exps],
            'status': self.status(claim),
            'steps': self.steps(claim),
            'trip': ', '.join(trips.mapped('name')) if trips else '',
            'submitted_on': claim.submitted_on,
            'decided_on': claim.decided_on,
            'paid_on': claim.paid_on,
        }

    @api.model
    def waiting_on_you(self, emp):
        """How many claims wait on the person (drafts and refused) — the
        home tile's count."""
        return len(self.own_claims(emp, 'act'))
