# -*- coding: utf-8 -*-
"""The claim's side of "claims paid in pay" (WDGAP S6-C, owner ruling E6).

THE ROUTE IS STAMPED WHEN THE CLAIM IS APPROVED. `pb_pay_route` is written
once, at approval, from the company's setting at that moment. A company that
changes its setting later does not move claims already approved (so a claim
is never paid by both, nor by neither). An empty stamp (every claim approved
before this module) means "by finance" — today's behaviour.

"PAID" FOR A PAY-RUN CLAIM IS READ FROM THE PAYSLIP, never from the
expenses: `_sync_paid` (stock accounting) leaves those claims alone, and the
stock "Post" of their receipts refuses (`hr_expense.py`), so finance cannot
pay them a second time.

WHAT IS PAID. The receipts the person paid themselves (`own_account`); a
receipt paid with a company card was never the person's money. A trip's cash
advance may cover part of it (`pb_trip_advance` overrides
`_pb_payable_amount` and `_pb_pay_hold_reason`).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

from .common import LIVE_STATES, PAY_ROUTES, TOKEN_KEY, WRITE_TOKEN

_logger = logging.getLogger(__name__)

#: The claim fields only this module writes (under the server token).
_GUARDED = frozenset({'pb_pay_route'})
#: The pay team (may mark a claim paid in a pay data file).
PAY_TEAM_GROUPS = ('pb_hr_payroll_base.group_payroll_base_officer',
                   'pb_hr_payroll_base.group_payroll_base_manager',
                   'om_hr_payroll.group_hr_payroll_user')


def month_words(env, day):
    """'November 2026' in the reader's language."""
    return format_date(env, day, date_format='MMMM y') if day else ''


class PbExpenseClaimPay(models.Model):
    _inherit = 'pb.expense.claim'

    pb_pay_route = fields.Selection(
        PAY_ROUTES, string='Paid back', readonly=True, copy=False, index=True,
        help='Set when the claim is approved, from the company\'s setting at '
             'that moment. Empty: by finance.')
    pb_payline_ids = fields.One2many(
        'pb.expense.payline', 'claim_id', string='Paid back in pay',
        readonly=True)
    pb_pay_words = fields.Char(
        string='Where the money is', compute='_compute_pb_pay_words')

    # ------------------------------------------------------------ guards
    def write(self, vals):
        if _GUARDED & set(vals) and \
                self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("How a claim is paid back is set by the system "
                                "when it is approved."))
        return super().write(vals)

    def _pb_write(self, vals):
        return self.with_context(**{TOKEN_KEY: WRITE_TOKEN}).sudo().write(vals)

    # ------------------------------------------------------------ approval
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            for claim in self.sudo():
                route = claim.company_id.pb_claims_paid_by or 'finance'
                if claim.pb_pay_route != route:
                    claim._pb_write({'pb_pay_route': route})
        return res

    # ------------------------------------------------------------ the money
    def _pb_pays_in_run(self):
        self.ensure_one()
        return self.pb_pay_route == 'payrun'

    def _pb_own_total(self):
        """What the person paid themselves (company-card receipts left out)."""
        self.ensure_one()
        exps = self.sudo().expense_ids.filtered(
            lambda e: e.payment_mode != 'company_account')
        return self.currency_id.round(sum(exps.mapped('total_amount_currency')))

    def _pb_payable_amount(self):
        """What the pay run pays back for this claim (hook: a trip's cash
        advance covers part of it — `pb_trip_advance`)."""
        self.ensure_one()
        return self._pb_own_total()

    def _pb_pay_hold_reason(self):
        """'' when a pay run may take this claim, else why not (a sentence).
        Hook: a claim against a trip whose cash advance is not settled yet
        waits (`pb_trip_advance`)."""
        self.ensure_one()
        return ''

    def _pb_live_payline(self):
        self.ensure_one()
        return self.sudo().pb_payline_ids.filtered(
            lambda l: l.state in LIVE_STATES)[:1]

    # ------------------------------------------------------------ paid
    def _sync_paid(self):
        """Stock accounting never moves a pay-run claim to Paid: its payslip
        does (`pb.expense.payline`)."""
        return super(PbExpenseClaimPay, self.filtered(
            lambda c: c.pb_pay_route != 'payrun'))._sync_paid()

    def _pb_set_paid(self, day=None):
        for claim in self.sudo().filtered(lambda c: c.state == 'approved'):
            claim._chain_engine_write('paid')
            claim.write({'paid_on': day or fields.Date.context_today(claim)})
            claim._chain_log('approved', 'paid', '')

    def _pb_set_unpaid(self):
        """A finished payslip set back, or a paid one cancelled: the claim is
        approved and not paid again."""
        for claim in self.sudo().filtered(lambda c: c.state == 'paid'):
            claim._chain_engine_write('approved')
            claim.write({'paid_on': False})
            claim._chain_log('paid', 'approved', '')

    # ------------------------------------------------------------ words
    @api.model
    def _pb_money(self, amount, currency):
        return formatLang(self.env, amount or 0.0, currency_obj=currency)

    def _pb_pay_status(self):
        """Where the money of an approved / paid pay-run claim is, in plain
        words, for both screens:

        {'route', 'step': 'waiting' | 'held' | 'run' | 'paid' | 'file' |
        'covered', 'amount', 'month', 'run', 'me', 'staff'} — or None for a
        claim finance pays (today's words stay)."""
        self.ensure_one()
        claim = self.sudo()
        if claim.pb_pay_route != 'payrun' or claim.state not in ('approved', 'paid'):
            return None
        env = self.env
        line = claim._pb_live_payline()
        amount = claim._pb_money(line.amount if line else claim._pb_payable_amount(),
                                 claim.currency_id)
        out = {'route': 'payrun', 'amount': amount, 'month': '', 'run': ''}
        if line and line.kind == 'advance':
            out.update(step='covered',
                       me=_("Covered by your trip's cash advance. Nothing more "
                            "comes in your pay for it."),
                       staff=_("Covered by the trip's cash advance"))
            return out
        if line and line.kind == 'file':
            month = month_words(env, line.paid_on)
            out.update(step='paid', month=month,
                       me=_("Paid with your %s pay.", month) if month else _("Paid with your pay."),
                       staff=_("Paid in the pay data file (%s)", line.paid_on and
                               format_date(env, line.paid_on) or ''))
            return out
        if line:
            month = month_words(env, line.pay_month)
            run = line.run_id.name or line.payslip_id.name or ''
            out.update(month=month, run=run)
            if line.state == 'paid':
                out.update(step='paid',
                           me=_("Paid in your %s pay. It is a separate line on "
                                "that payslip, with no tax.", month),
                           staff=_("Paid in pay run %s", run))
            else:
                out.update(step='run',
                           me=_("In your %s pay. It shows as a separate line on "
                                "that payslip, with no tax.", month),
                           staff=_("In pay run %s (not finished yet)", run))
            return out
        held = claim._pb_pay_hold_reason()
        if held:
            out.update(step='held', me=held, staff=held)
            return out
        out.update(step='waiting',
                   me=_("It is paid back in your next pay, as a separate line "
                        "with no tax."),
                   staff=_("To pay in the next regular pay run"))
        return out

    @api.depends('state', 'pb_pay_route')
    def _compute_pb_pay_words(self):
        for claim in self:
            status = claim._pb_pay_status() if claim.id else None
            claim.pb_pay_words = status['staff'] if status else ''

    # ------------------------------------------------------------ file schemes
    def action_pb_paid_in_file(self):
        """The pay team says: this claim was included in the pay data file.
        A scheme paid from a pay data file never takes a claim by itself, so
        this is how such a claim reads "Paid"."""
        user = self.env.user
        if not (user._is_admin() or any(user.has_group(g) for g in PAY_TEAM_GROUPS
                                         if self.env.ref(g, raise_if_not_found=False))):
            raise AccessError(_("Only the pay team can say a claim was paid in the "
                                "pay data file."))
        Line = self.env['pb.expense.payline'].sudo()
        today = fields.Date.context_today(self)
        for claim in self.sudo():
            if claim.state != 'approved' or claim.pb_pay_route != 'payrun':
                raise UserError(_("Only an approved claim that is paid back in pay "
                                  "can be marked as paid in the pay data file."))
            if claim._pb_live_payline():
                raise UserError(_("Claim %s is already in a pay run, so it is paid "
                                  "there.", claim.name))
            amount = claim._pb_payable_amount()
            if claim.currency_id.compare_amounts(amount, 0.0) <= 0:
                raise UserError(_("Claim %s has nothing left to pay back.", claim.name))
            Line._pb_create({'claim_id': claim.id, 'amount': amount, 'kind': 'file',
                             'state': 'paid', 'paid_on': today,
                             'pay_month': today.replace(day=1),
                             'note': _("Included in the pay data file by %s.",
                                       user.name)})
            claim._pb_set_paid(today)
            claim.message_post(body=_("Paid back in the pay data file (marked by %s).",
                                      user.name))
        return True
