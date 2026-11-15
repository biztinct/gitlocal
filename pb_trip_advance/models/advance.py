# -*- coding: utf-8 -*-
"""`pb.trip.advance` — one trip's cash advance: given, claimed against,
settled, taken back.

THE ARITHMETIC (settlement). A = the advance. U = what the person claimed for
the trip that is still to pay them (approved claims, receipts they paid
themselves, tagged to the trip, not paid yet). Claims already paid back
before the settlement are not set against the advance: that money already
reached the person.
  * U ≥ A — the advance was spent: the claims are set against it, oldest
    first, up to A; the rest of the claims (U − A) is paid as usual.
  * U < A — every such claim is covered; A − U is UNSPENT and is taken back
    from the person's next regular pay (or recorded as paid back in cash).

A claim fully covered by the advance reads "Covered by your trip's cash
advance" (it is paid); one partly covered pays only what is left.

TAKEN BACK ONCE. A pay run holds what it takes (`pb.trip.advance.recovery`,
reserved → paid / given back, the claims' pattern); the advance closes itself
when nothing is left.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

from odoo.addons.pb_expense_payroll.models.common import (DONE_STATES, LIVE_STATES,
                                                          TOKEN_KEY, WRITE_TOKEN)

_logger = logging.getLogger(__name__)

ADVANCE_STATES = [
    ('given', 'Given'),
    ('settled', 'Settled — being taken back'),
    ('closed', 'Closed'),
]
RECOVER_HOW = [
    ('pay', 'From the next pay'),
    ('cash', 'Paid back by the person'),
]
#: Who may record an advance as given, settle it, or record a cash repayment.
ADVANCE_GROUPS = ('hr_expense.group_hr_expense_manager',
                  'om_hr_payroll.group_hr_payroll_manager',
                  'pb_hr_payroll_base.group_payroll_base_manager',
                  'pb_hr_payroll_base.group_payroll_base_officer',
                  'account.group_account_invoice')


def can_manage(env):
    user = env.user
    if user._is_admin():
        return True
    return any(env.ref(x, raise_if_not_found=False) and user.has_group(x)
               for x in ADVANCE_GROUPS)


class PbTripAdvance(models.Model):
    _name = 'pb.trip.advance'
    _description = 'Trip cash advance'
    _inherit = ['mail.thread']
    _order = 'id desc'

    trip_id = fields.Many2one('pb.business.trip', string='Trip', required=True,
                              index=True, ondelete='restrict', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  index=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  readonly=True)
    amount = fields.Monetary(string='Advance given', readonly=True)
    state = fields.Selection(ADVANCE_STATES, string='Status', default='given',
                             required=True, index=True, readonly=True, tracking=True)
    given_on = fields.Date(string='Given on', readonly=True)
    given_ref = fields.Char(string='Reference', readonly=True)
    given_by = fields.Many2one('res.users', string='Recorded by', readonly=True)
    settled_on = fields.Date(string='Settled on', readonly=True)
    settled_by = fields.Many2one('res.users', string='Settled by', readonly=True)
    claimed = fields.Monetary(string='Claimed against it', readonly=True)
    unspent = fields.Monetary(string='Not spent', readonly=True)
    extra_due = fields.Monetary(string='Spent above the advance', readonly=True)
    recover_how = fields.Selection(RECOVER_HOW, string='Taken back', readonly=True)
    offset_ids = fields.One2many('pb.trip.advance.offset', 'advance_id',
                                 string='Claims set against it', readonly=True)
    recovery_ids = fields.One2many('pb.trip.advance.recovery', 'advance_id',
                                   string='Taken back', readonly=True)
    recovered = fields.Monetary(string='Taken back so far', compute='_compute_left',
                                store=True)
    left = fields.Monetary(string='Still to take back', compute='_compute_left',
                           store=True)

    _one_per_trip = models.UniqueIndex('(trip_id)',
                                       'This trip already has its cash advance recorded.')

    @api.depends('unspent', 'recovery_ids.state', 'recovery_ids.amount')
    def _compute_left(self):
        for adv in self:
            paid = sum(adv.recovery_ids.filtered(lambda l: l.state == 'paid').mapped('amount'))
            adv.recovered = paid
            adv.left = max((adv.unspent or 0.0) - paid, 0.0)

    # ------------------------------------------------------------ guards
    def write(self, vals):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN and not self.env.su:
            raise AccessError(_("A trip's cash advance is recorded from the trip."))
        return super().write(vals)

    def _w(self, vals):
        return self.with_context(**{TOKEN_KEY: WRITE_TOKEN}).sudo().write(vals)

    # ------------------------------------------------------------ words
    def _money(self, amount):
        self.ensure_one()
        return formatLang(self.env, amount or 0.0, currency_obj=self.currency_id)

    # ------------------------------------------------------------ the claims
    def _trip_claims(self):
        """The claims with a receipt tagged to this trip."""
        self.ensure_one()
        exps = self.env['hr.expense'].sudo().search([('pb_trip_id', '=', self.trip_id.id),
                                                      ('pb_claim_id', '!=', False)])
        return exps.mapped('pb_claim_id').filtered(lambda c: c.company_id == self.company_id)

    def _claim_trip_own(self, claim):
        """What the person paid themselves on this trip, in this claim."""
        exps = claim.sudo().expense_ids.filtered(
            lambda e: e.pb_trip_id == self.trip_id and e.payment_mode != 'company_account')
        return claim.currency_id.round(sum(exps.mapped('total_amount_currency')))

    def _settle_preview(self):
        """{'claims': [(claim, own)], 'claimed', 'unspent', 'extra_due',
        'waiting': claims still waiting approval, 'drafts': draft claims}."""
        self.ensure_one()
        claims = self._trip_claims()
        open_claims = claims.filtered(
            lambda c: c.state == 'approved' and not c._pb_live_payline())
        rows = [(c, self._claim_trip_own(c)) for c in open_claims.sorted('id')]
        rows = [(c, a) for c, a in rows if a > 0]
        claimed = self.currency_id.round(sum(a for _c, a in rows))
        amount = self.amount or 0.0
        return {
            'claims': rows, 'claimed': claimed,
            'unspent': self.currency_id.round(max(amount - claimed, 0.0)),
            'extra_due': self.currency_id.round(max(claimed - amount, 0.0)),
            'waiting': claims.filtered(lambda c: c.state == 'submitted'),
            'drafts': claims.filtered(lambda c: c.state in ('draft', 'refused')),
        }

    # ------------------------------------------------------------ settle
    def _settle(self, recover_how='pay'):
        self.ensure_one()
        if not can_manage(self.env):
            raise AccessError(_("Only finance or the pay team can settle a cash advance."))
        if self.state != 'given':
            raise UserError(_("This cash advance is already settled."))
        if recover_how not in ('pay', 'cash'):
            raise UserError(_("Choose how the unspent part comes back."))
        preview = self._settle_preview()
        if preview['waiting']:
            raise UserError(_(
                "Decide the claims for this trip that are still waiting approval "
                "first: %s.", ', '.join(preview['waiting'].mapped('name'))))
        Offset = self.env['pb.trip.advance.offset'].sudo()
        Payline = self.env['pb.expense.payline'].sudo()
        room = self.amount or 0.0
        today = fields.Date.context_today(self)
        for claim, own in preview['claims']:
            if room <= 0:
                break
            part = self.currency_id.round(min(own, room))
            room = self.currency_id.round(room - part)
            Offset.with_context(**{TOKEN_KEY: WRITE_TOKEN}).create(
                {'advance_id': self.id, 'claim_id': claim.id, 'amount': part})
            claim.invalidate_recordset()
            if claim.currency_id.compare_amounts(claim._pb_payable_amount(), 0.0) <= 0:
                # nothing left to pay the person for this claim: it is covered
                Payline._pb_create({'claim_id': claim.id, 'amount': part,
                                    'kind': 'advance', 'state': 'paid', 'paid_on': today,
                                    'pay_month': today.replace(day=1),
                                    'note': _("Covered by the cash advance of %s.",
                                              self.trip_id.name)})
                claim._pb_set_paid(today)
        vals = {'state': 'settled' if preview['unspent'] > 0 else 'closed',
                'settled_on': today, 'settled_by': self.env.uid,
                'claimed': preview['claimed'], 'unspent': preview['unspent'],
                'extra_due': preview['extra_due'],
                'recover_how': recover_how if preview['unspent'] > 0 else False}
        self._w(vals)
        if preview['unspent'] > 0:
            how = (_("It is taken back from %s's next regular pay.", self.employee_id.name)
                   if recover_how == 'pay' else
                   _("%s pays it back directly.", self.employee_id.name))
            body = _("Settled: %(claimed)s claimed against an advance of %(amount)s; "
                     "%(unspent)s was not spent. %(how)s",
                     claimed=self._money(preview['claimed']),
                     amount=self._money(self.amount), unspent=self._money(preview['unspent']),
                     how=how)
        else:
            body = _("Settled: %(claimed)s claimed against an advance of %(amount)s. "
                     "Nothing to take back.", claimed=self._money(preview['claimed']),
                     amount=self._money(self.amount))
        self.message_post(body=body)
        self.trip_id.sudo().message_post(body=body)
        return True

    def _record_cash(self, amount, day=None, ref=''):
        self.ensure_one()
        if not can_manage(self.env):
            raise AccessError(_("Only finance or the pay team can record a repayment."))
        if self.state != 'settled':
            raise UserError(_("Nothing is waiting to be paid back on this advance."))
        held = sum(self.recovery_ids.filtered(lambda l: l.state == 'reserved').mapped('amount'))
        can = self.currency_id.round(self.left - held)
        amount = self.currency_id.round(amount or 0.0)
        if amount <= 0 or self.currency_id.compare_amounts(amount, can) > 0:
            raise UserError(_("Type an amount above zero and no more than %s (what is "
                              "still to be paid back and not already in a pay run).",
                              self._money(can)))
        self.env['pb.trip.advance.recovery']._pb_create({
            'advance_id': self.id, 'amount': amount, 'kind': 'cash', 'state': 'paid',
            'paid_on': day or fields.Date.context_today(self),
            'note': ref or _("Paid back directly")})
        self.message_post(body=_("%(amount)s paid back directly (%(ref)s).",
                                 amount=self._money(amount), ref=ref or '-'))
        self._check_closed()
        return True

    def _check_closed(self):
        for adv in self.sudo():
            adv.invalidate_recordset(['recovered', 'left'])
            if adv.state == 'settled' and adv.currency_id.compare_amounts(adv.left, 0.0) <= 0:
                adv._w({'state': 'closed'})
            elif adv.state == 'closed' and adv.currency_id.compare_amounts(adv.left, 0.0) > 0:
                adv._w({'state': 'settled'})

    # ------------------------------------------------------------ the person
    @api.model
    def my_advances(self, employee):
        """Rows for the person's OWN pages, or None for anybody else's."""
        if not employee or employee._name != 'hr.employee':
            return None
        employee = employee.sudo()[:1]
        if not employee or employee.user_id.id != self.env.uid:
            return None
        advs = self.sudo().search([('employee_id', '=', employee.id),
                                   ('state', 'in', ('given', 'settled'))], order='id desc')
        rows = []
        for adv in advs:
            if adv.state == 'given':
                words = _("Claim your receipts for this trip; they are set against the "
                          "advance when the trip is settled.")
            elif adv.recover_how == 'cash':
                words = _("%s was not spent. Please pay it back to finance.",
                          adv._money(adv.left))
            else:
                held = adv.recovery_ids.filtered(lambda l: l.state == 'reserved')
                if held:
                    words = _("%(amount)s comes off your %(month)s pay.",
                              amount=adv._money(sum(held.mapped('amount'))),
                              month=format_date(self.env, held[:1].pay_month,
                                                date_format='MMMM y'))
                else:
                    words = _("%s was not spent. It comes off your next pay.",
                              adv._money(adv.left))
            rows.append({'id': adv.id, 'trip': adv.trip_id.name or '',
                         'where': adv.trip_id.destination_city or '',
                         'state': adv.state, 'amount': adv._money(adv.amount),
                         'claimed': adv._money(adv.claimed) if adv.state != 'given' else '',
                         'left': adv._money(adv.left) if adv.state == 'settled' else '',
                         'words': words})
        return {'rows': rows, 'count': len(rows)}


class PbTripAdvanceOffset(models.Model):
    _name = 'pb.trip.advance.offset'
    _description = 'Claim set against a trip cash advance'

    advance_id = fields.Many2one('pb.trip.advance', required=True, index=True,
                                 ondelete='cascade', readonly=True)
    claim_id = fields.Many2one('pb.expense.claim', required=True, index=True,
                               ondelete='cascade', readonly=True)
    currency_id = fields.Many2one(related='advance_id.currency_id')
    company_id = fields.Many2one(related='advance_id.company_id', store=True)
    amount = fields.Monetary(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("A trip's cash advance is recorded from the trip."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("A trip's cash advance is recorded from the trip."))
        return super().write(vals)


class PbTripAdvanceRecovery(models.Model):
    _name = 'pb.trip.advance.recovery'
    _description = 'Unspent trip advance taken back'
    _order = 'id desc'

    advance_id = fields.Many2one('pb.trip.advance', required=True, index=True,
                                 ondelete='cascade', readonly=True)
    employee_id = fields.Many2one(related='advance_id.employee_id', store=True, index=True)
    company_id = fields.Many2one(related='advance_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='advance_id.currency_id', store=True)
    amount = fields.Monetary(readonly=True)
    kind = fields.Selection([('payroll', 'From pay'), ('cash', 'Paid back directly')],
                            required=True, default='payroll', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', index=True, ondelete='set null', readonly=True)
    run_id = fields.Many2one('hr.payslip.run', index=True, ondelete='set null', readonly=True)
    pay_month = fields.Date(readonly=True)
    state = fields.Selection([('reserved', 'In a pay run'), ('paid', 'Taken back'),
                              ('released', 'Given back')], required=True,
                             default='reserved', index=True, readonly=True)
    paid_on = fields.Date(readonly=True)
    note = fields.Char(readonly=True)

    _one_per_month = models.UniqueIndex(
        "(advance_id, pay_month) WHERE kind = 'payroll' AND state IN ('reserved', 'paid')",
        "This advance is already taken back in that pay month.")
    _amount_positive = models.Constraint('CHECK(amount > 0)',
                                         'What is taken back must be above zero.')

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("What is taken back from pay is recorded by the system."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("What is taken back from pay is recorded by the system."))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("What is taken back from pay is recorded by the system."))
        return super().unlink()

    @api.model
    def _pb_create(self, vals):
        return self.with_context(**{TOKEN_KEY: WRITE_TOKEN}).sudo().create(vals)

    def _pb_write(self, vals):
        return self.with_context(**{TOKEN_KEY: WRITE_TOKEN}).sudo().write(vals)

    def _pb_release(self, why):
        lines = self.sudo().filtered(lambda l: l.state in LIVE_STATES and l.kind == 'payroll')
        if lines:
            lines._pb_write({'state': 'released', 'paid_on': False,
                             'note': _("Given back: %s.", why)})
            lines.advance_id._check_closed()

    @api.model
    def _pb_slips_follow(self, slips, before, state):
        lines = self.sudo().search([('payslip_id', 'in', slips.ids), ('kind', '=', 'payroll'),
                                    ('state', 'in', LIVE_STATES)])
        if not lines:
            return
        if state in DONE_STATES:
            todo = lines.filtered(lambda l: l.state == 'reserved')
            todo._pb_write({'state': 'paid', 'paid_on': fields.Date.context_today(self)})
        elif state == 'cancel':
            lines._pb_release(_("payslip cancelled"))
        else:
            undone = lines.filtered(lambda l: l.state == 'paid'
                                    and before.get(l.payslip_id.id) in DONE_STATES)
            undone._pb_write({'state': 'reserved', 'paid_on': False})
        lines.advance_id._check_closed()

    @api.model
    def _pb_slips_gone(self, slips, why):
        if slips:
            self.sudo().search([('payslip_id', 'in', slips.ids), ('kind', '=', 'payroll'),
                                ('state', 'in', LIVE_STATES)])._pb_release(why)
