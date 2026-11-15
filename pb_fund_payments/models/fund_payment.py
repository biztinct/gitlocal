# -*- coding: utf-8 -*-
"""What the company owes one fund or office for one pay month — and the proof
it was paid.

THE AMOUNT OWED IS DERIVED, NEVER TYPED (R1). It is the sum of the payee's pay
items on the FINISHED payslips of the month (state done/paid, every kind of
run — regular, top-up, Extra run — and payslips on hold too: the contribution
is owed whether or not the person has been paid). The pay month is the month
the payslip's period ENDS in, the same date the Pay runs board files a run
under. A line is read by its component link — the payslip's pay scheme plus
the line's code, which is how a payslip line names the component it came from
— and counted by its size, as the run's own Deductions / Employer cost figures
count it (one pay-band rule: money taken off is taken off, however the scheme
signs it). The only human figures are the paid amount and the note that
explains a difference.

NEVER TWO CURRENCIES (R2). A row is (payee, month, currency); a payee whose
items come from schemes paying in two currencies gets two rows. The live rows
carry a partial unique index on exactly that triple (R4).

WHAT AN APPROVAL COVERS STAYS PUT (R3). Working the month out again updates
the rows still "to pay"; a row waiting for approval, approved or paid keeps the
figures it was sent in with and only records the latest reading beside them —
the board then shows "figures changed since approval: +1,250,000". Changing an
approved or paid row takes "Reopen", with a reason, and it goes through
approval again. Marking a row paid needs the receipt.

Every write to a business field goes through this file's own methods (a
context token); anything else is refused, so no screen and no import can type
a figure.

Life of a row::

    to pay ──send──▶ waiting for approval ──approved──▶ approved ──mark paid──▶ paid
       ▲                    │ sent back / turned down /            │               │
       └────────────────────┘ withdrawn                            └── reopen ◀────┘
                                                                     (reason; back to "to pay")
    to pay ──nothing owed any more──▶ cancelled
"""
import base64
import calendar
import hashlib
import json
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
FUNDPAY_PROCESS_KEY = 'fundpay'

#: The context key every legitimate write carries.
TOKEN = 'pb_fund_payments_token'

STATES = [
    ('to_pay', 'To pay'),
    ('waiting', 'Waiting for approval'),
    ('approved', 'Approved, not paid'),
    ('paid', 'Paid'),
    ('cancelled', 'Cancelled'),
]
LIVE_STATES = ('to_pay', 'waiting', 'approved', 'paid')
#: Rows whose figures are what somebody sent in or approved (R3).
FROZEN_STATES = ('waiting', 'approved', 'paid')
UNPAID_STATES = ('to_pay', 'waiting', 'approved')
#: Payslip states that mean "finished".
DONE_SLIP_STATES = ('done', 'paid')

#: Fields a person may never write directly.
FREE_FIELDS = frozenset({'seat_user_ids'})


def month_of(day):
    day = fields.Date.to_date(day) if day else None
    return day.replace(day=1) if day else None


def due_date_for(month, due_day):
    """Day `due_day` of the month after `month`, clamped to that month."""
    nxt = month + relativedelta(months=1)
    last = calendar.monthrange(nxt.year, nxt.month)[1]
    return nxt.replace(day=max(1, min(int(due_day or 15), last)))


class PbFundPayment(models.Model):
    _name = 'pb.fund.payment'
    _description = 'Payment to a fund or office'
    _inherit = ['mail.thread', 'biz.approval.adapter.mixin',
                'pb.money.approval.mixin']
    _order = 'month desc, payee_id, id'

    _approval_process_key = FUNDPAY_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    payee_id = fields.Many2one('pb.fund.payee', string='Pay to', required=True,
                               index=True, ondelete='restrict', readonly=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    month = fields.Date(string='Pay month', required=True, index=True, readonly=True,
                        help="The first day of the month the payslips' periods end in.")
    state = fields.Selection(STATES, default='to_pay', required=True, index=True,
                             readonly=True, copy=False)

    # ---------------------------------------------------- the figures (R1)
    amount_employee = fields.Monetary(string='Employee share', readonly=True,
                                      currency_field='currency_id')
    amount_employer = fields.Monetary(string='Employer share', readonly=True,
                                      currency_field='currency_id')
    amount_owed = fields.Monetary(string='Owed', readonly=True,
                                  currency_field='currency_id')
    head_count = fields.Integer(string='People', readonly=True)
    slip_ids = fields.Many2many('hr.payslip', 'pb_fund_payment_slip_rel',
                                'payment_id', 'slip_id', string='Payslips',
                                readonly=True, copy=False)
    breakdown_json = fields.Text(readonly=True, copy=False,
                                 help="Per pay item: scheme, code, share, amount, people.")
    due_date = fields.Date(string='Due by', readonly=True, index=True)
    worked_out_on = fields.Datetime(readonly=True, copy=False)
    worked_out_by = fields.Many2one('res.users', readonly=True, copy=False)

    # ------------------------------------- the latest reading (after a freeze)
    live_owed = fields.Monetary(string='Latest reading', readonly=True,
                                currency_field='currency_id', copy=False)
    live_head_count = fields.Integer(readonly=True, copy=False)
    live_diff = fields.Monetary(string='Changed since approval', readonly=True,
                                currency_field='currency_id', copy=False)
    figures_changed = fields.Boolean(string='Figures changed since approval',
                                     readonly=True, index=True, copy=False)

    # ---------------------------------------------------------------- paid
    approved_on = fields.Datetime(readonly=True, copy=False)
    paid_on = fields.Date(string='Paid on', readonly=True, copy=False)
    paid_amount = fields.Monetary(string='Paid', readonly=True, copy=False,
                                  currency_field='currency_id')
    paid_difference = fields.Monetary(string='Difference', compute='_compute_difference',
                                      currency_field='currency_id')
    difference_note = fields.Text(string='Why the amount differs', readonly=True, copy=False)
    payment_reference = fields.Char(string='Payment reference', readonly=True, copy=False)
    evidence_attachment_id = fields.Many2one('ir.attachment', string='Receipt',
                                             readonly=True, copy=False, ondelete='restrict')
    paid_by = fields.Many2one('res.users', readonly=True, copy=False)
    reopen_reason = fields.Text(readonly=True, copy=False)
    is_late = fields.Boolean(string='Past its due date', compute='_compute_is_late')

    seat_user_ids = fields.Many2many(
        'res.users', 'pb_fund_payment_seat_rel', 'payment_id', 'user_id',
        string='Asked to decide', copy=False)

    _payee_month_currency_live = models.UniqueIndex(
        '(payee_id, month, currency_id) WHERE state != \'cancelled\'',
        'This fund already has a payment for that month in that currency.')

    # ================================================================ computes
    @api.depends('payee_id.name', 'month')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s · %s' % (rec.payee_id.name or '', self._month_label(rec.month))

    @api.depends('paid_amount', 'amount_owed', 'state')
    def _compute_difference(self):
        for rec in self:
            rec.paid_difference = (rec.paid_amount - rec.amount_owed) \
                if rec.state == 'paid' else 0.0

    @api.depends('state', 'due_date', 'paid_on')
    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.due_date or rec.state == 'cancelled':
                rec.is_late = False
            elif rec.state == 'paid':
                rec.is_late = bool(rec.paid_on and rec.paid_on > rec.due_date)
            else:
                rec.is_late = today > rec.due_date

    # ============================================================ the guard
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(TOKEN):
            raise UserError(_(
                "Fund and tax payments are worked out from finished payslips on "
                "the Fund & tax payments board; they cannot be typed in."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(TOKEN):
            blocked = [k for k in vals if k not in FREE_FIELDS
                       and not k.startswith(('message_', 'activity_', 'website_message'))]
            if blocked:
                raise UserError(_(
                    "Fund and tax payments are changed only from the Fund & tax "
                    "payments board: the amount owed comes from the payslips, and "
                    "an approved or paid payment changes only by reopening it."))
        return super().write(vals)

    def _w(self):
        """This recordset, allowed to write its own fields."""
        return self.sudo().with_context(**{TOKEN: True})

    # ============================================================ helpers
    @api.model
    def _month_label(self, month):
        month = fields.Date.to_date(month) if month else None
        return format_date(self.env, month, date_format='MMMM y') if month else ''

    def _money(self, value, currency=None):
        currency = currency or (self[:1].currency_id if self else False) \
            or self.env.company.currency_id
        try:
            value = float(value or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        return formatLang(self.env, value, currency_obj=currency)

    def _signed_money(self, value):
        self.ensure_one()
        text = self._money(abs(value))
        return ('+' if value > 0 else '−') + text if value else text

    def _state_label(self):
        self.ensure_one()
        return dict(self._fields['state']._description_selection(self.env)).get(
            self.state, '')

    def _breakdown(self):
        self.ensure_one()
        try:
            data = json.loads(self.breakdown_json or '[]')
        except (TypeError, ValueError):
            data = []
        return data if isinstance(data, list) else []

    def _log(self, body):
        """One line in the row's own history. A note: nobody is emailed."""
        for rec in self:
            rec.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')

    # ================================================================ reading
    @api.model
    def _pb_read(self, payees, month):
        """THE ONE READING (R6). For each payee, what its items add up to on the
        finished payslips of `month`, per currency.

        {(payee id, currency id): {'employee', 'employer', 'slips': set,
          'people': set, 'items': {rule id: {...}}}}

        One SQL read over the payslip lines of the chosen items, so a month of
        a big tenant is one query, not a walk through every payslip.
        """
        month = month_of(month)
        payees = payees.sudo()
        out = {}
        if not payees or not month:
            return out
        items = payees.mapped('item_ids').filtered(lambda i: i.rule_id and i.config_id)
        if not items:
            return out
        by_key = {}
        for item in items:
            by_key.setdefault((item.config_id.id, item.code), []).append(item)
        configs = items.mapped('config_id')
        currency_of = {c.id: (c.currency_id or c.company_id.currency_id) for c in configs}
        codes = sorted({i.code for i in items if i.code})
        nxt = month + relativedelta(months=1)
        self.env['hr.payslip'].flush_model(['state', 'date_to', 'company_id',
                                            'formula_config_id', 'employee_id'])
        self.env['hr.payslip.line'].flush_model(['slip_id', 'code', 'total'])
        self.env.cr.execute("""
            SELECT s.id, s.employee_id, s.formula_config_id, s.company_id,
                   l.code, COALESCE(l.total, 0)
              FROM hr_payslip_line l
              JOIN hr_payslip s ON s.id = l.slip_id
             WHERE s.state IN %s
               AND s.date_to >= %s AND s.date_to < %s
               AND s.formula_config_id IN %s
               AND s.company_id IN %s
               AND l.code IN %s
        """, (DONE_SLIP_STATES, month, nxt, tuple(configs.ids),
              tuple(payees.mapped('company_id').ids), tuple(codes)))
        for slip_id, emp_id, config_id, company_id, code, total in self.env.cr.fetchall():
            for item in by_key.get((config_id, code), []):
                payee = item.payee_id
                if payee.company_id.id != company_id:
                    continue
                currency = currency_of.get(config_id)
                row = out.setdefault((payee.id, currency.id), {
                    'employee': 0.0, 'employer': 0.0, 'slips': set(),
                    'people': set(), 'items': {}, 'currency': currency})
                amount = abs(total or 0.0)
                row[item.share] += amount
                row['slips'].add(slip_id)
                if amount:
                    row['people'].add(emp_id)
                it = row['items'].setdefault(item.rule_id.id, {
                    'rule_id': item.rule_id.id, 'config_id': config_id,
                    'code': code, 'name': item.rule_id.name or code,
                    'scheme': item.config_id.name or '', 'share': item.share,
                    'amount': 0.0, 'people': set()})
                it['amount'] += amount
                if amount:
                    it['people'].add(emp_id)
        for row in out.values():
            cur = row['currency']
            row['employee'] = cur.round(row['employee'])
            row['employer'] = cur.round(row['employer'])
        return out

    @api.model
    def _pb_figures(self, row):
        """The values a reading writes onto a row."""
        cur = row['currency']
        items = sorted(row['items'].values(), key=lambda it: (
            it['share'] != 'employee', it['scheme'], it['name']))
        breakdown = [dict(it, amount=cur.round(it['amount']), people=len(it['people']))
                     for it in items]
        return {
            'amount_employee': row['employee'],
            'amount_employer': row['employer'],
            'amount_owed': cur.round(row['employee'] + row['employer']),
            'head_count': len(row['people']),
            'slip_ids': [(6, 0, sorted(row['slips']))],
            'breakdown_json': json.dumps(breakdown),
        }

    # ================================================================ work out
    @api.model
    def pb_work_out(self, month, companies=None):
        """"Work out what we owe for <month>" — idempotent (R4).

        Creates a row for a payee and currency that has something owed and no
        live row yet; updates the figures of rows still "to pay"; records the
        latest reading beside rows that are waiting, approved or paid (R3);
        cancels a "to pay" row nothing is owed on any more. Returns counts.
        """
        self.require_pay(_('working out what is owed'))
        month = month_of(month)
        if not month:
            raise UserError(_("Pick the pay month first."))
        companies = companies or self.env.companies
        Payee = self.env['pb.fund.payee']
        payees = Payee.search([('company_id', 'in', companies.ids)])
        reading = self._pb_read(payees, month)
        rows = self.search([('company_id', 'in', companies.ids),
                            ('month', '=', month), ('state', '!=', 'cancelled')])
        live = {(r.payee_id.id, r.currency_id.id): r for r in rows}
        now = fields.Datetime.now()
        stats = {'created': 0, 'updated': 0, 'unchanged': 0, 'changed': 0,
                 'cancelled': 0, 'payees': len(payees)}
        for (payee_id, currency_id), row in sorted(reading.items()):
            payee = Payee.browse(payee_id)
            figures = self._pb_figures(row)
            rec = live.pop((payee_id, currency_id), None)
            if rec is None:
                if float_is_zero(figures['amount_owed'],
                                 precision_rounding=row['currency'].rounding):
                    continue
                vals = dict(figures, payee_id=payee_id, company_id=payee.company_id.id,
                            currency_id=currency_id, month=month,
                            due_date=due_date_for(month, payee.due_day),
                            worked_out_on=now, worked_out_by=self.env.uid,
                            live_owed=figures['amount_owed'],
                            live_head_count=figures['head_count'])
                rec = self.with_context(**{TOKEN: True}).sudo().create(vals)
                rec._log(_("Worked out from %(n)s finished payslips: %(amount)s owed.",
                           n=len(row['slips']), amount=rec._money(rec.amount_owed)))
                stats['created'] += 1
                continue
            stats[rec._pb_refresh(figures, now)] += 1
        # Live rows the reading no longer finds anything for.
        for rec in live.values():
            if rec.state == 'to_pay':
                rec._w().write({'state': 'cancelled', 'live_owed': 0.0,
                                'live_head_count': 0})
                rec._log(_("Cancelled: the finished payslips of %s no longer owe "
                           "this fund anything.", self._month_label(month)))
                stats['cancelled'] += 1
            else:
                empty = {'amount_employee': 0.0, 'amount_employer': 0.0,
                         'amount_owed': 0.0, 'head_count': 0,
                         'slip_ids': [(6, 0, [])], 'breakdown_json': '[]'}
                stats[rec._pb_refresh(empty, now)] += 1
        return stats

    def _pb_refresh(self, figures, now=None):
        """Bring one row up to the latest reading. 'updated' / 'unchanged' /
        'changed' (frozen row whose payslips moved)."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        cur = self.currency_id
        if self.state == 'to_pay':
            same = (float_compare(self.amount_owed, figures['amount_owed'],
                                  precision_rounding=cur.rounding) == 0
                    and float_compare(self.amount_employee, figures['amount_employee'],
                                      precision_rounding=cur.rounding) == 0
                    and self.head_count == figures['head_count']
                    and sorted(self.slip_ids.ids) == sorted(figures['slip_ids'][0][2]))
            vals = dict(figures, live_owed=figures['amount_owed'],
                        live_head_count=figures['head_count'], live_diff=0.0,
                        figures_changed=False, worked_out_on=now,
                        worked_out_by=self.env.uid,
                        due_date=due_date_for(self.month, self.payee_id.due_day))
            self._w().write(vals)
            if same:
                return 'unchanged'
            self._log(_("Worked out again: %s owed.", self._money(self.amount_owed)))
            return 'updated'
        # FROZEN (R3): the figures stay; the latest reading sits beside them.
        diff = cur.round(figures['amount_owed'] - self.amount_owed)
        changed = not float_is_zero(diff, precision_rounding=cur.rounding) \
            or figures['head_count'] != self.head_count
        was = self.figures_changed
        self._w().write({'live_owed': figures['amount_owed'],
                         'live_head_count': figures['head_count'],
                         'live_diff': diff, 'figures_changed': changed})
        if changed and (not was or float_compare(diff, self.live_diff,
                                                 precision_rounding=cur.rounding)):
            self._log(_("The payslips changed after this payment was sent for "
                        "approval: they now add up to %(now)s (%(diff)s). The "
                        "approved figures were not changed.",
                        now=self._money(figures['amount_owed']),
                        diff=self._signed_money(diff)))
        return 'changed' if changed else 'unchanged'

    def _pb_refresh_from_reading(self):
        """Work this one row out again (before sending it in, after reopening)."""
        self.ensure_one()
        reading = self._pb_read(self.payee_id, self.month)
        row = reading.get((self.payee_id.id, self.currency_id.id))
        if row:
            figures = self._pb_figures(row)
        else:
            figures = {'amount_employee': 0.0, 'amount_employer': 0.0,
                       'amount_owed': 0.0, 'head_count': 0,
                       'slip_ids': [(6, 0, [])], 'breakdown_json': '[]'}
        return self._pb_refresh(figures)

    # ================================================================= moves
    def action_submit(self):
        """Send this payment for approval (never in bulk: a money process)."""
        self.ensure_one()
        self.require_pay(_('sending a fund payment for approval'))
        if self.state != 'to_pay':
            raise UserError(_("Only a payment that is still to pay can be sent "
                              "for approval."))
        self._pb_refresh_from_reading()
        if self.state != 'to_pay':
            raise UserError(_("Nothing is owed to this fund for that month any more."))
        return self.env['biz.approval.engine'].submit(self)

    def action_withdraw(self, reason=None):
        """Take back a payment that is waiting for approval."""
        self.ensure_one()
        if self.state != 'waiting' or not self.approval_request_id:
            raise UserError(_("This payment is not waiting for approval."))
        return self.env['biz.approval.engine'].cancel(
            self.approval_request_id, reason or _("Withdrawn from the board"))

    def action_mark_paid(self, paid_on=None, paid_amount=None, reference=None,
                         attachment_id=None, note=None):
        """Record the payment. The receipt is required (R3); a paid amount
        that differs from what is owed needs a note."""
        self.ensure_one()
        self.require_pay(_('marking a fund payment as paid'))
        if self.state != 'approved':
            raise UserError(_("Only an approved payment can be marked as paid."))
        attachment = self.env['ir.attachment'].sudo().browse(
            int(attachment_id or 0)).exists()
        if not attachment or attachment.res_model != self._name \
                or attachment.res_id != self.id:
            raise UserError(_("Attach the receipt or the bank confirmation first — "
                              "a payment is marked as paid only with its proof."))
        try:
            amount = float(paid_amount) if paid_amount not in (None, '', False) \
                else self.amount_owed
        except (TypeError, ValueError):
            raise UserError(_("Type the amount that was paid as a number."))
        cur = self.currency_id
        amount = cur.round(amount)
        if amount <= 0:
            raise UserError(_("The amount paid must be above zero."))
        note = (note or '').strip()
        if float_compare(amount, self.amount_owed, precision_rounding=cur.rounding) \
                and not note:
            raise UserError(_(
                "%(paid)s was paid but %(owed)s is owed. Say why the amounts "
                "differ, in a few words.", paid=self._money(amount),
                owed=self._money(self.amount_owed)))
        day = fields.Date.to_date(paid_on) if paid_on else fields.Date.context_today(self)
        if day > fields.Date.context_today(self):
            raise UserError(_("The payment date cannot be in the future."))
        self._w().write({
            'state': 'paid', 'paid_on': day, 'paid_amount': amount,
            'payment_reference': (reference or '').strip()[:120] or False,
            'evidence_attachment_id': attachment.id,
            'difference_note': note or False, 'paid_by': self.env.uid,
        })
        self._log(_("Marked as paid: %(amount)s on %(day)s%(ref)s.",
                    amount=self._money(amount),
                    day=format_date(self.env, day, date_format='d MMM y'),
                    ref=(_(" · reference %s", self.payment_reference)
                         if self.payment_reference else '')))
        self.audit(self, 'paid_on', _('Fund payment paid'), '',
                   '%s · %s' % (self._money(amount), self.payment_reference or ''))
        return True

    def action_reopen(self, reason=None):
        """An approved or paid payment can only change by being reopened: it
        goes back to "to pay", is worked out again, and needs a new approval."""
        self.ensure_one()
        self.require_pay(_('reopening a fund payment'))
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_("Say why this payment is being reopened."))
        if self.state not in ('approved', 'paid'):
            raise UserError(_("Only an approved or paid payment can be reopened."))
        before = self.state
        before_line = _("%(state)s · %(owed)s owed%(paid)s", state=self._state_label(),
                        owed=self._money(self.amount_owed),
                        paid=(_(" · %(amount)s paid on %(day)s", amount=self._money(self.paid_amount),
                                day=format_date(self.env, self.paid_on))
                              if before == 'paid' else ''))
        self._w().write({
            'state': 'to_pay', 'reopen_reason': reason, 'approved_on': False,
            'paid_on': False, 'paid_amount': 0.0, 'payment_reference': False,
            'evidence_attachment_id': False, 'difference_note': False,
            'paid_by': False, 'figures_changed': False, 'live_diff': 0.0,
        })
        self._log(_("Reopened: %(why)s. It was %(before)s; it needs a new approval.",
                    why=reason, before=before_line))
        self.audit(self, 'state', _('Fund payment reopened'), before, 'to_pay')
        self._pb_refresh_from_reading()
        return True

    @api.model
    def pb_attach_evidence(self, payment_id, name, data_b64, mimetype=None):
        """Store the receipt on the payment (before it is marked paid)."""
        self.require_pay(_('attaching a receipt'))
        rec = self.browse(int(payment_id or 0)).exists()
        if not rec:
            raise UserError(_("This payment no longer exists."))
        rec.check_access('read')
        if rec.state not in ('approved', 'paid'):
            raise UserError(_("A receipt is attached once the payment is approved."))
        try:
            raw = base64.b64decode(data_b64 or '', validate=True)
        except Exception:   # noqa: BLE001
            raise UserError(_("That file could not be read."))
        if not raw:
            raise UserError(_("That file is empty."))
        if len(raw) > 15 * 1024 * 1024:
            raise UserError(_("That file is larger than 15 MB."))
        att = self.env['ir.attachment'].sudo().create({
            'name': (name or _('Receipt'))[:200],
            'datas': base64.b64encode(raw),
            'res_model': self._name, 'res_id': rec.id,
            'mimetype': mimetype or False,
        })
        return {'id': att.id, 'name': att.name}

    # ================================================================ adapter
    def _approval_revision(self):
        # Read for the engine, never for the reader: a seat may hold no
        # payroll role at all (AM40/AM60) and still decide.
        self.ensure_one()
        rec = self.sudo()
        return self._approval_revision_of([
            rec.payee_id.id, str(rec.month), rec.currency_id.id,
            round(float(rec.amount_employee or 0.0), 2),
            round(float(rec.amount_employer or 0.0), 2), rec.head_count,
            hashlib.sha256(','.join(str(i) for i in sorted(rec.slip_ids.ids))
                           .encode()).hexdigest()[:16]])

    def _approval_validate(self):
        self.ensure_one()
        if self.state != 'to_pay':
            raise UserError(_("This payment has already been sent in."))
        if float_is_zero(self.amount_owed, precision_rounding=self.currency_id.rounding):
            raise UserError(_("Nothing is owed on this payment."))
        return True

    def _approval_context(self):
        self.ensure_one()
        self = self.sudo()      # read for the engine (AM40): a seat may hold no payroll role
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        makers = {u for u in (self.worked_out_by.id, self.create_uid.id) if u}
        return {
            'company_id': company.id,
            'title': _("Pay %(payee)s · %(month)s", payee=self.payee_id.name or '',
                       month=self._month_label(self.month)),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': 'any',
            'facts': {
                'amount': {'value': float(self.amount_owed or 0.0),
                           'unit': currency.name or ''},
                'people': {'value': self.head_count, 'unit': ''},
                'employee_share': {'value': float(self.amount_employee or 0.0),
                                   'unit': currency.name or ''},
                'employer_share': {'value': float(self.amount_employer or 0.0),
                                   'unit': currency.name or ''},
            },
            'amount': float(self.amount_owed or 0.0),
            'currency_id': currency.id,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._approval_revision(),
            'evidence': [
                {'key': 'from_payslips',
                 'name': _('Worked out from finished payslips'),
                 'ok': bool(self.slip_ids),
                 'note': _("%s payslips", len(self.slip_ids))},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'amount': {'type': 'decimal', 'label': _('Amount'), 'unit': 'currency'},
                'people': {'type': 'int', 'label': _('People')},
                'employee_share': {'type': 'decimal', 'label': _('Employee share'),
                                   'unit': 'currency'},
                'employer_share': {'type': 'decimal', 'label': _('Employer share'),
                                   'unit': 'currency'},
            },
            'kinds': [],
            'evidence': [{'key': 'from_payslips',
                          'label': _('Worked out from finished payslips')}],
            'scope_levels': [],
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        return []

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.head_count == 1:
            return _("1 person")
        return _("%s people", self.head_count)

    def _approval_detail(self, request):
        """Per pay item: employee share, employer share — the question an
        approver asks ("what am I agreeing to send, and to whom")."""
        self.ensure_one()
        self = self.sudo()      # the approver may hold no payroll role (AM60)
        rows = []
        for it in self._breakdown():
            amount = self._money(it.get('amount') or 0.0)
            employee = it.get('share') == 'employee'
            rows.append({
                'head': it.get('name') or it.get('code') or '',
                'sub': it.get('scheme') or '',
                'cells': [amount if employee else '—', '—' if employee else amount,
                          str(it.get('people') or 0)],
                'tone': '',
            })
        payee = self.payee_id.sudo()
        chips = [
            {'label': _('Pay to'), 'value': payee.name or ''},
            {'label': _('Pay month'), 'value': self._month_label(self.month)},
            {'label': _('Due by'), 'value': format_date(self.env, self.due_date,
                                                        date_format='d MMM y')
             if self.due_date else ''},
            {'label': _('People'), 'value': str(self.head_count)},
            {'label': _('Employee share'), 'value': self._money(self.amount_employee)},
            {'label': _('Employer share'), 'value': self._money(self.amount_employer)},
        ]
        if payee.reference_text:
            chips.append({'label': _('Reference to quote'), 'value': payee.reference_text})
        return {
            'title': _('What is being paid'),
            'columns': [_('Employee share'), _('Employer share'), _('People')],
            'rows': rows,
            'chips': chips,
            'note': (_("Worked out from %s finished payslips of the month.",
                       len(self.slip_ids))),
        }

    def _approval_freeze(self, request):
        self.ensure_one()
        self._w().write({'state': 'waiting', 'figures_changed': False, 'live_diff': 0.0,
                         'live_owed': self.amount_owed,
                         'live_head_count': self.head_count})
        self._log(_("Sent for approval: %s owed.", self._money(self.amount_owed)))
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        if self.state == 'waiting':
            self._w().write({'state': 'to_pay'})
            self._log(_("Sent back: %s", reason or _('no reason given')))
        return True

    def _approval_reject(self, request, reason):
        """Turned down. The money is still owed — the row goes back to "to pay"
        and says so; it is never cancelled by a refusal."""
        self.ensure_one()
        if self.state == 'waiting':
            self._w().write({'state': 'to_pay'})
            self._log(_("Not approved: %s. The money is still owed; send it again "
                        "when it is right.", reason or _('no reason given')))
        return True

    def _approval_withdraw(self, request, reason):
        self.ensure_one()
        if self.state == 'waiting':
            self._w().write({'state': 'to_pay'})
            self._log(_("Withdrawn: %s", reason or _('no reason given')))
        return True

    def _approval_apply(self, request):
        """Approved: the pay team may now pay it.

        Idempotent. Deliberately NOT gated on the Pay & Deliver role (unlike a
        payment release): nothing leaves the company at this moment — the
        money moves when somebody records the payment with its receipt, and
        THAT is gated (`action_mark_paid`).
        """
        self.ensure_one()
        if self.state in ('approved', 'paid'):
            return True
        if self.state != 'waiting':
            raise UserError(_("This payment is no longer waiting for approval."))
        self._w().write({'state': 'approved', 'approved_on': fields.Datetime.now()})
        self._log(_("Approved: %s may now be paid.", self._money(self.amount_owed)))
        return True

    # ======================================================== native fallback
    def action_open_lines(self):
        """The payslip lines behind the figure, as a list."""
        self.ensure_one()
        pairs = {(it.get('config_id'), it.get('code')) for it in self._breakdown()}
        lines = self.env['hr.payslip.line']
        if self.slip_ids and pairs:
            lines = self.env['hr.payslip.line'].search([
                ('slip_id', 'in', self.slip_ids.ids),
                ('code', 'in', sorted({c for _cfg, c in pairs if c}))])
            lines = lines.filtered(
                lambda l: (l.slip_id.formula_config_id.id, l.code) in pairs)
        view = self.env.ref('pb_fund_payments.view_pb_fund_payment_line_list',
                            raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payslip lines behind %s', self.name or ''),
            'res_model': 'hr.payslip.line',
            'view_mode': 'list',
            'views': [[view.id if view else False, 'list']],
            'domain': [('id', 'in', lines.ids)],
            'target': 'current',
            'context': {'create': False, 'edit': False, 'delete': False},
        }


class BizApprovalRequestSeatFund(models.Model):
    """A seat on a fund-payment request is also a read of that payment (AM60),
    the money-out records' rule, for this module's own model."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.fund.payment' or not request.res_id:
                continue
            record = self.env['pb.fund.payment'].sudo().browse(request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats
