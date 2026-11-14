# -*- coding: utf-8 -*-
"""WDGAP PR-B — a loan or a salary advance, and every repayment of it.

THE BALANCE IS DERIVED, NEVER TYPED (R3): ``amount − sum(paid repayments)``.
No write path sets it; it is a stored compute of the repayment lines so the
board can sort and filter on it.

ONE INSTALMENT PER LOAN PER PAY MONTH (R1): a repayment taken by a pay run is
a ``payroll`` line keyed (loan, pay month); at most one of them is live
(``reserved`` or ``paid``) at a time — a partial unique index, the last line of
defence behind the row lock the pay-run seam takes (``loan_payroll.py``).

NEVER MORE THAN IS OWED (R2): what a pay run may take is
``amount − paid − held by OTHER payslips`` (``_available``), read under a
``FOR UPDATE`` lock on the loan when a payslip really computes, and a
repayment made outside payroll larger than that is refused.

Life of a loan::

    draft ──send──▶ waiting ──approved──▶ running ◀──resume── paused
      ▲                │                    │  ▲                 ▲
      └── sent back ───┘                    │  └── pause ────────┘
                       └─▶ refused          ▼ balance reaches 0
                                          closed  (re-opens if a paid
                                                   payslip is cancelled)
    any open state ──cancel (with a reason)──▶ cancelled
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, float_round
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

#: The pay team (WDGAP PR-B §9): officers raise and run loans; managers are
#: the legacy ladder's approver (a published route replaces that ladder).
GROUP_OFFICER = 'pb_hr_payroll_base.group_payroll_base_officer'
GROUP_MANAGER = 'pb_hr_payroll_base.group_payroll_base_manager'

KINDS = [('loan', 'Loan'), ('advance', 'Salary advance')]
STATES = [
    ('draft', 'Being prepared'),
    ('waiting', 'Waiting for approval'),
    ('running', 'Running'),
    ('paused', 'Paused'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
    ('refused', 'Not approved'),
]
PLAN_MODES = [('amount', 'An amount each month'),
              ('months', 'A number of months')]
ON_LEAVING = [('take_rest', 'Take the rest from the final pay'),
              ('leave_open', 'Leave it open')]

#: Repayment lines a pay run holds or has paid — at most one per loan+month.
LIVE_LINE_STATES = ('reserved', 'paid')
#: Payslip states that mean "this payslip has been paid".
DONE_SLIP_STATES = ('done', 'paid')
#: Loans a pay run may take an instalment for.
TAKING_STATES = ('running',)
#: Loans that still owe something and can be changed by the pay team.
OPEN_STATES = ('running', 'paused')


def month_of(day):
    day = fields.Date.to_date(day) if day else None
    return day.replace(day=1) if day else None


def _units(value, currency):
    """An amount as a whole number of the currency's smallest unit (₫1,
    0.01 USD). Plan maths is done in these, so no float ever drifts a cent."""
    try:
        value = float(value or 0.0)
    except (TypeError, ValueError):
        return 0
    rounding = currency.rounding or 0.01
    return int(float_round(value / rounding, precision_digits=0))


def _money_of(units, currency):
    return currency.round(units * (currency.rounding or 0.01))


class PbLoan(models.Model):
    _name = 'pb.loan'
    _description = 'Loan or salary advance'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'id desc'
    _rec_name = 'name'

    #: The legacy ladder, used only while a company has no published loan
    #: route (the post-init hook lays one for every company, so normally the
    #: engine decides). Sending in is the pay team's (ACL); agreeing is the
    #: payroll manager's, because money leaves the company.
    _approval_transitions = {
        ('draft', 'waiting'): None,
        ('waiting', 'running'): GROUP_MANAGER,
        ('waiting', 'refused'): GROUP_MANAGER,
    }
    _approval_dead_states = ('refused', 'cancelled', 'closed')

    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default='/', index=True)
    employee_id = fields.Many2one('hr.employee', string='Who it is for',
                                  required=True, index=True,
                                  ondelete='restrict', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True,
                                 default=lambda self: self.env.company)
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    kind = fields.Selection(KINDS, string='Kind', required=True,
                            default='loan', tracking=True)
    amount = fields.Monetary(string='Amount', required=True,
                             currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="The person's pay currency: instalments are taken only by a "
             "pay scheme that pays in this currency.")
    reason = fields.Text(string='Why', required=True, tracking=True)
    first_month = fields.Date(
        string='First pay month', required=True, tracking=True,
        help='The first pay month an instalment is taken in. Any day of the '
             'month will do — it is the month that matters.')
    plan_mode = fields.Selection(PLAN_MODES, string='Paid back as',
                                 required=True, default='amount')
    plan_amount = fields.Monetary(
        string='Each month', currency_field='currency_id', tracking=True,
        help='What each regular pay run takes. The last instalment takes '
             'whatever is left.')
    plan_months = fields.Integer(string='Number of months', tracking=True)
    on_leaving = fields.Selection(
        ON_LEAVING, string='If the person leaves', required=True,
        default='take_rest', tracking=True)
    state = fields.Selection(STATES, string='Status', default='draft',
                             required=True, index=True, tracking=True,
                             copy=False)
    repayment_ids = fields.One2many('pb.loan.repayment', 'loan_id',
                                    string='Repayments', copy=False)
    repaid = fields.Monetary(string='Repaid so far', compute='_compute_balance',
                             store=True, currency_field='currency_id')
    balance = fields.Monetary(string='Left to repay', compute='_compute_balance',
                              store=True, currency_field='currency_id')
    in_payrun = fields.Monetary(string='In a pay run now',
                                compute='_compute_next',
                                currency_field='currency_id')
    next_amount = fields.Monetary(string='Next instalment', compute='_compute_next',
                                  currency_field='currency_id')
    next_month = fields.Date(string='Next pay month', compute='_compute_next')
    months_left = fields.Integer(string='Months left', compute='_compute_next')
    pause_reason = fields.Char(string='Why it is paused', readonly=True,
                               copy=False)
    closed_on = fields.Date(string='Closed on', readonly=True, copy=False)
    requested_by_user_id = fields.Many2one(
        'res.users', string='Raised by', readonly=True, copy=False,
        default=lambda self: self.env.user)

    _amount_positive = models.Constraint(
        'CHECK(amount > 0)', 'A loan needs an amount above zero.')

    # =================================================================
    # Computes
    # =================================================================
    @api.depends('amount', 'repayment_ids.state', 'repayment_ids.amount')
    def _compute_balance(self):
        for loan in self:
            paid = sum(line.amount for line in loan.repayment_ids
                       if line.state == 'paid')
            currency = loan.currency_id or loan.company_id.currency_id
            paid = currency.round(paid) if currency else paid
            loan.repaid = paid
            balance = (loan.amount or 0.0) - paid
            loan.balance = currency.round(balance) if currency else balance

    @api.depends('state', 'balance', 'plan_amount', 'first_month',
                 'repayment_ids.state', 'repayment_ids.amount',
                 'repayment_ids.pay_month')
    def _compute_next(self):
        today = month_of(fields.Date.context_today(self))
        for loan in self:
            held = sum(line.amount for line in loan.repayment_ids
                       if line.state == 'reserved')
            loan.in_payrun = held
            available = loan._available()
            plan = loan.plan_amount or 0.0
            if loan.state not in OPEN_STATES and loan.state not in ('draft', 'waiting'):
                loan.next_amount = 0.0
                loan.next_month = False
                loan.months_left = 0
                continue
            taken = loan.repayment_ids.filtered(
                lambda l: l.kind == 'payroll' and l.state in LIVE_LINE_STATES)
            start = month_of(loan.first_month) or today
            if taken:
                after = max(taken.mapped('pay_month')) + relativedelta(months=1)
                start = max(start, after)
            if loan.state in OPEN_STATES:
                start = max(start, today)
            loan.next_month = start
            if loan.state in ('draft', 'waiting'):
                available = loan.amount or 0.0
            loan.next_amount = min(plan, available) if plan > 0 else 0.0
            loan.months_left = loan._months_for(available)

    def _months_for(self, remaining):
        """How many instalments `remaining` still is, at this plan."""
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        plan_units = _units(self.plan_amount, currency)
        left_units = _units(remaining, currency)
        if plan_units <= 0 or left_units <= 0:
            return 0
        return -(-left_units // plan_units)

    def _available(self, exclude_slip_id=None, exclude_line_ids=()):
        """What may still be taken: amount − paid − held by other payslips.

        R2: never more than is owed. `exclude_slip_id` leaves out what THIS
        payslip already holds (a recompute reuses its own reservation)."""
        self.ensure_one()
        held = 0.0
        paid = 0.0
        for line in self.repayment_ids:
            if line.id in exclude_line_ids:
                continue
            if line.state == 'paid':
                paid += line.amount
            elif line.state == 'reserved':
                if exclude_slip_id and line.payslip_id.id == exclude_slip_id:
                    continue
                held += line.amount
        currency = self.currency_id or self.company_id.currency_id
        return max(currency.round((self.amount or 0.0) - paid - held), 0.0)

    # =================================================================
    # The plan (by amount or by months — the other is worked out)
    # =================================================================
    @api.model
    def _plan_numbers(self, amount, mode, plan_amount, plan_months, currency):
        """`(each month, number of months, last instalment)` for a plan.

        By months: each month is the amount divided by the months, rounded UP
        to the currency's smallest unit, so the last instalment takes the
        remainder and is never larger than the others. By amount: the months
        are worked out. Currency rounding only — never Python `round()` on
        money (C12)."""
        currency = currency or self.env.company.currency_id
        units = _units(amount, currency)
        if units <= 0:
            return 0.0, 0, 0.0
        if mode == 'months':
            months = max(1, int(plan_months or 1))
            each_units = -(-units // months)            # ceiling, in whole units
        else:
            each_units = _units(plan_amount, currency)
            if each_units <= 0:
                return 0.0, 0, 0.0
        each_units = min(each_units, units)
        months = -(-units // each_units)
        last_units = units - each_units * (months - 1)
        return (_money_of(each_units, currency), months,
                _money_of(last_units, currency))

    @api.model
    def _plan_vals(self, vals, loan=None):
        """Fill in the half of the plan the person did not type."""
        get = lambda k: vals[k] if k in vals else (loan[k] if loan else False)  # noqa: E731
        currency = self.env['res.currency'].browse(
            vals.get('currency_id') or (loan.currency_id.id if loan else False)
        ) or self.env.company.currency_id
        if loan and not vals.get('currency_id'):
            currency = loan.currency_id or currency
        mode = get('plan_mode') or 'amount'
        each, months, _last = self._plan_numbers(
            get('amount'), mode, get('plan_amount'), get('plan_months'), currency)
        out = dict(vals)
        if mode == 'months':
            out['plan_amount'] = each
        else:
            out['plan_months'] = months
        return out

    def _schedule(self, start=None, remaining=None):
        """`[(month, amount)]` — the plan from `start` (default: the next
        month) for `remaining` (default: what is still available)."""
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        remaining = self._available() if remaining is None else remaining
        start = month_of(start) or self.next_month or month_of(self.first_month)
        plan = self.plan_amount or 0.0
        out = []
        if plan <= 0 or not start:
            return out
        month = start
        guard = 0
        while float_compare(remaining, 0.0, precision_rounding=currency.rounding) > 0 \
                and guard < 600:
            take = currency.round(min(plan, remaining))
            out.append((month, take))
            remaining = currency.round(remaining - take)
            month = month + relativedelta(months=1)
            guard += 1
        return out

    # =================================================================
    # Create / write
    # =================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('first_month'):
                vals['first_month'] = month_of(vals['first_month'])
            if vals.get('employee_id') and not vals.get('company_id'):
                emp = self.env['hr.employee'].sudo().browse(vals['employee_id'])
                vals['company_id'] = emp.company_id.id or self.env.company.id
            if (vals.get('name') or '/') == '/':
                vals['name'] = seq.next_by_code('pb.loan') or '/'
            vals = self._plan_vals(vals)
            prepared.append(vals)
        loans = super().create(prepared)
        loans._check_plan()
        return loans

    #: Fields that define what was agreed; changed only while being prepared.
    _AGREED = ('employee_id', 'amount', 'currency_id', 'first_month', 'plan_mode',
               'plan_amount', 'plan_months', 'kind', 'company_id')

    def write(self, vals):
        touched = set(vals) & set(self._AGREED)
        if touched and not self.env.context.get('pb_loans_internal'):
            for loan in self:
                if loan.state != 'draft':
                    raise UserError(_(
                        "%(ref)s has been sent in, so what was agreed cannot be "
                        "changed. Cancel it and raise a new one instead.",
                        ref=loan.name))
        if 'first_month' in vals and vals['first_month']:
            vals = dict(vals, first_month=month_of(vals['first_month']))
        if touched & {'amount', 'plan_mode', 'plan_amount', 'plan_months', 'currency_id'}:
            for loan in self:
                super(PbLoan, loan).write(self._plan_vals(vals, loan))
            self._check_plan()
            return True
        return super().write(vals)

    def unlink(self):
        for loan in self:
            if loan.state != 'draft' or loan.repayment_ids:
                raise UserError(_(
                    "Only a loan that is still being prepared can be deleted. "
                    "Cancel %s instead, with a reason.", loan.name))
        return super().unlink()

    def _check_plan(self):
        for loan in self:
            if (loan.plan_amount or 0.0) <= 0:
                raise ValidationError(_(
                    "Say how much is paid back each month, or over how many months."))
            if loan.plan_mode == 'months' and (loan.plan_months or 0) < 1:
                raise ValidationError(_("Paid back over at least one month."))

    # =================================================================
    # Words
    # =================================================================
    def _money(self, value, currency=None):
        currency = currency or (self[:1].currency_id if self else False) \
            or self.env.company.currency_id
        try:
            value = float(value or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        return formatLang(self.env, value, currency_obj=currency)

    @api.model
    def _month_label(self, month):
        month = fields.Date.to_date(month) if month else None
        return format_date(self.env, month, date_format='MMMM y') if month else ''

    def _kind_label(self):
        self.ensure_one()
        return dict(self._fields['kind']._description_selection(self.env)).get(
            self.kind, '')

    def _state_label(self):
        self.ensure_one()
        return dict(self._fields['state']._description_selection(self.env)).get(
            self.state, '')

    def _plan_sentence(self):
        """"6 instalments of ₫1,000,000 from March 2026, the last ₫500,000"."""
        self.ensure_one()
        each, months, last = self._plan_numbers(
            self.amount, self.plan_mode, self.plan_amount, self.plan_months,
            self.currency_id)
        start = self._month_label(self.first_month)
        if months <= 1:
            return _("All of it in the %(month)s pay run.", month=start)
        if float_compare(last, each, precision_rounding=self.currency_id.rounding) == 0:
            return _("%(n)s instalments of %(each)s, from the %(month)s pay run.",
                     n=months, each=self._money(each), month=start)
        return _("%(n)s instalments of %(each)s from the %(month)s pay run; the "
                 "last one is %(last)s.", n=months, each=self._money(each),
                 month=start, last=self._money(last))

    def _plan_short(self):
        """"4 × ₫2,250,000" — for a chip (the inbox cuts long ones)."""
        self.ensure_one()
        each, months, last = self._plan_numbers(
            self.amount, self.plan_mode, self.plan_amount, self.plan_months,
            self.currency_id)
        if months > 1 and float_compare(last, each,
                                        precision_rounding=self.currency_id.rounding):
            return _("%(n)s × %(each)s, last %(last)s", n=months - 1,
                     each=self._money(each), last=self._money(last))
        return _("%(n)s × %(each)s", n=months, each=self._money(each))

    def _post(self, body):
        """A chatter line that never sends an email."""
        for loan in self:
            loan.sudo().with_context(mail_notrack=True).message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_note')

    # =================================================================
    # Rights
    # =================================================================
    @api.model
    def _may_manage(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin() or user.has_group(GROUP_OFFICER)
                    or user.has_group(GROUP_MANAGER))

    @api.model
    def _require_manage(self):
        if not self._may_manage():
            raise AccessError(_("Loans are looked after by the pay team."))

    # =================================================================
    # The moves (each with a reason where the handover asks for one)
    # =================================================================
    def action_submit(self):
        self._require_manage()
        for loan in self:
            if loan.state != 'draft':
                raise UserError(_("%s has already been sent in.", loan.name))
            loan._check_plan()
            loan._advance_state('waiting')
        return True

    def action_approve(self):
        for loan in self:
            loan._advance_state('running')
        return True

    def action_refuse(self, note=False):
        return self.action_refuse_chain(note=note)

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'running':
            for loan in self:
                loan._post(_("Approved. Repayments start in the %(month)s pay run: "
                             "%(plan)s", month=loan._month_label(loan.first_month),
                             plan=loan._plan_sentence()))
        return res

    def _need_reason(self, reason):
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_("Say why, in a few words."))
        return reason

    def action_pause(self, reason):
        self._require_manage()
        reason = self._need_reason(reason)
        for loan in self:
            if loan.state != 'running':
                raise UserError(_("Only a running loan can be paused."))
            loan._chain_state_write('paused')
            loan.sudo().write({'pause_reason': reason})
            loan._post(_("Paused: %s. No instalment is taken until it is "
                         "resumed; the plan moves on by a month for each month "
                         "missed.", reason))
        return True

    def action_resume(self, reason=None):
        self._require_manage()
        for loan in self:
            if loan.state != 'paused':
                raise UserError(_("Only a paused loan can be resumed."))
            loan._chain_state_write('running')
            loan.sudo().write({'pause_reason': False})
            loan._post(_("Resumed: %s", (reason or '').strip()) if (reason or '').strip()
                       else _("Resumed. The next regular pay run takes an instalment."))
            loan._check_closed()
        return True

    def action_cancel(self, reason):
        self._require_manage()
        reason = self._need_reason(reason)
        for loan in self:
            if loan.state not in ('draft', 'waiting', 'running', 'paused'):
                raise UserError(_("%s is already closed.", loan.name))
            held = loan.repayment_ids.filtered(lambda l: l.state == 'reserved')
            if held:
                raise UserError(_(
                    "An instalment of %(amount)s is in pay run %(run)s, which is "
                    "not finished. Finish that pay run, or calculate it again "
                    "after pausing this loan, then cancel.",
                    amount=loan._money(sum(held.mapped('amount'))),
                    run=held[:1]._run_label()))
            left = loan.balance if loan.state in OPEN_STATES else 0.0
            loan._chain_state_write('cancelled')
            if left > 0 and loan.repaid > 0:
                loan._post(_("Cancelled: %(why)s. %(left)s was left unpaid and will "
                             "not be collected.", why=reason, left=loan._money(left)))
            else:
                loan._post(_("Cancelled: %s", reason))
        return True

    def action_record_repayment(self, amount, reason, reference=None, on_date=None):
        """A repayment made outside payroll (cash, a bank transfer)."""
        self._require_manage()
        self.ensure_one()
        reason = self._need_reason(reason)
        loan = self.sudo()
        if loan.state not in OPEN_STATES:
            raise UserError(_("Only a running or paused loan can be paid back."))
        self.env.cr.execute('SELECT id FROM pb_loan WHERE id = %s FOR UPDATE', (loan.id,))
        loan.invalidate_recordset()
        currency = loan.currency_id
        try:
            amount = currency.round(float(amount or 0.0))
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            raise UserError(_("A repayment needs an amount above zero."))
        available = loan._available()
        if float_compare(amount, available, precision_rounding=currency.rounding) > 0:
            held = loan.in_payrun
            if held:
                raise UserError(_(
                    "%(amount)s is more than is left to repay. %(left)s is left, "
                    "and %(held)s of that is already in a pay run, so at most "
                    "%(max)s can be recorded now.", amount=loan._money(amount),
                    left=loan._money(loan.balance), held=loan._money(held),
                    max=loan._money(available)))
            raise UserError(_("%(amount)s is more than is left to repay (%(left)s).",
                              amount=loan._money(amount), left=loan._money(available)))
        day = fields.Date.to_date(on_date) if on_date else fields.Date.context_today(self)
        line = self.env['pb.loan.repayment'].sudo().create({
            'loan_id': loan.id, 'kind': 'manual', 'state': 'paid',
            'amount': amount, 'pay_month': month_of(day), 'paid_on': day,
            'reason': reason, 'reference': (reference or '').strip() or False,
            'recorded_by': self.env.uid,
        })
        loan._post(_("%(amount)s paid back outside payroll: %(why)s%(ref)s. "
                     "%(left)s left to repay.", amount=loan._money(amount),
                     why=reason, ref=(' (%s)' % line.reference) if line.reference else '',
                     left=loan._money(loan.balance)))
        loan._touch()
        loan._check_closed()
        return line

    def action_settle(self, reason, reference=None):
        """Settle now: record what is still available as paid outside payroll."""
        self._require_manage()
        self.ensure_one()
        loan = self.sudo()
        available = loan._available()
        if available <= 0:
            if loan.in_payrun:
                raise UserError(_("Everything left is already in a pay run. It is "
                                  "settled when that pay run is finished."))
            raise UserError(_("Nothing is left to repay."))
        return self.action_record_repayment(available, reason, reference)

    # =================================================================
    # Closes itself at zero, re-opens when money comes back
    # =================================================================
    def _check_closed(self):
        for loan in self.sudo():
            currency = loan.currency_id
            nothing_left = float_compare(loan.balance, 0.0,
                                         precision_rounding=currency.rounding) <= 0
            held = loan.repayment_ids.filtered(lambda l: l.state == 'reserved')
            if loan.state in OPEN_STATES and nothing_left and not held:
                loan._chain_state_write('closed')
                loan.write({'closed_on': fields.Date.context_today(loan),
                            'pause_reason': False})
                loan._post(_("Repaid in full: %s. Closed.", loan._money(loan.amount)))
            elif loan.state == 'closed' and not nothing_left:
                loan._chain_state_write('running')
                loan.write({'closed_on': False})
                loan._post(_("Open again: %s is left to repay because a payment "
                             "was taken back.", loan._money(loan.balance)))

    def _touch(self):
        """Bump the loan rows so a concurrent pay run waiting on their lock
        retries instead of reading a stale balance (R1/R2)."""
        if self.ids:
            self.env.cr.execute(
                'UPDATE pb_loan SET write_date = (now() at time zone \'UTC\') '
                'WHERE id IN %s', (tuple(self.ids),))

    # =================================================================
    # Engine words (inbox, route builder)
    # =================================================================
    def _chain_title(self):
        self.ensure_one()
        return _("%(kind)s for %(who)s", kind=self._kind_label(),
                 who=self.employee_id.sudo().name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'kind': {'value': self.kind or '', 'unit': ''},
            'amount': {'value': float(self.amount or 0.0),
                       'unit': self.currency_id.name or ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'kind': {'type': 'selection', 'label': _('Loan or salary advance')},
            'amount': {'type': 'decimal', 'label': _('Amount')},
        }

    def _chain_kind_key(self):
        self.ensure_one()
        return self.kind or 'any'

    @api.model
    def _chain_kinds(self):
        return [{'key': key, 'label': label} for key, label in
                self._fields['kind']._description_selection(self.env)]

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Amount'), 'value': self._money(self.amount)},
            {'label': _('Paid back'), 'value': self._plan_short()},
            {'label': _('First pay month'), 'value': self._month_label(self.first_month)},
            {'label': _('If the person leaves'),
             'value': dict(self._fields['on_leaving']._description_selection(
                 self.env)).get(self.on_leaving, '')},
        ]
        return {'title': self._chain_title(), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.reason or '')[:240]}


class PbLoanRepayment(models.Model):
    _name = 'pb.loan.repayment'
    _description = 'Loan repayment'
    _order = 'pay_month desc, id desc'

    loan_id = fields.Many2one('pb.loan', string='Loan', required=True,
                              index=True, ondelete='cascade', readonly=True)
    employee_id = fields.Many2one(related='loan_id.employee_id', store=True,
                                  index=True, string='Employee')
    company_id = fields.Many2one(related='loan_id.company_id', store=True,
                                 index=True, string='Company')
    currency_id = fields.Many2one(related='loan_id.currency_id', string='Currency')
    pay_month = fields.Date(string='Pay month', required=True, index=True,
                            readonly=True)
    amount = fields.Monetary(string='Amount', required=True, readonly=True,
                             currency_field='currency_id')
    kind = fields.Selection([('payroll', 'Taken in a pay run'),
                             ('manual', 'Paid outside payroll')],
                            string='How', required=True, default='payroll',
                            readonly=True)
    state = fields.Selection([('reserved', 'In a pay run'),
                              ('paid', 'Paid'),
                              ('released', 'Not taken')],
                             string='Status', required=True, default='reserved',
                             index=True, readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', index=True,
                                 ondelete='set null', readonly=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run', index=True,
                             ondelete='set null', readonly=True)
    paid_on = fields.Date(string='Paid on', readonly=True)
    reason = fields.Char(string='Why', readonly=True)
    reference = fields.Char(string='Reference', readonly=True)
    recorded_by = fields.Many2one('res.users', string='Recorded by', readonly=True)
    note = fields.Char(string='What happened', readonly=True)

    _one_per_month = models.UniqueIndex(
        "(loan_id, pay_month) WHERE kind = 'payroll' AND state IN ('reserved', 'paid')",
        "This loan already has an instalment for that pay month.")
    _amount_positive = models.Constraint(
        'CHECK(amount > 0)', 'A repayment needs an amount above zero.')

    def _run_label(self):
        self.ensure_one()
        run = self.run_id or self.payslip_id.payslip_run_id
        if run:
            return run.name or ''
        return self.payslip_id.name or ''

    def write(self, vals):
        # Only this module's own code moves a repayment (under sudo, with the
        # key below). A JSON-RPC call cannot set the context key's VALUE to
        # this object, so the guard cannot be forged from outside.
        if self.env.context.get('pb_loans_line_write') is not _LINE_TOKEN \
                and not self.env.su:
            raise AccessError(_("Repayments are recorded by the system."))
        return super().write(vals)

    def _write_line(self, vals):
        return self.with_context(pb_loans_line_write=_LINE_TOKEN).sudo().write(vals)


#: Server-only sentinel for a sanctioned repayment write (see `write`).
_LINE_TOKEN = object()
