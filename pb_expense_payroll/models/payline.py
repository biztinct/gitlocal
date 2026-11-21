# -*- coding: utf-8 -*-
"""`pb.expense.payline` — one claim, paid back once.

Cloned from the loans' repayment line (`pb_loans/models/loan.py`
`pb.loan.repayment`): a claim is HELD by the payslip that computed it
(`reserved`), PAID when that payslip is finished, held again when the payslip
is set back, and GIVEN BACK (`released`) when the payslip or its run is
cancelled or deleted, or the payslip is recomputed without it. One live line
per claim, whatever happens — a partial unique index the database enforces.

Kinds: `payroll` (a regular pay run took it), `file` (the pay team included
it in a pay data file), `advance` (a trip's cash advance covered all of it —
`pb_trip_advance`).

Only this module's own code writes a line (the server token in the context);
nobody — not even the pay team — edits one by hand.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .common import DONE_STATES, LIVE_STATES, TOKEN_KEY, WRITE_TOKEN

PAYLINE_STATES = [
    ('reserved', 'In a pay run'),
    ('paid', 'Paid'),
    ('released', 'Given back'),
]
PAYLINE_KINDS = [
    ('payroll', 'Pay run'),
    ('file', 'Pay data file'),
    ('advance', 'Trip cash advance'),
]


class PbExpensePayline(models.Model):
    _name = 'pb.expense.payline'
    _description = 'Expense claim paid back in pay'
    _order = 'id desc'

    claim_id = fields.Many2one('pb.expense.claim', string='Claim', required=True,
                               index=True, ondelete='cascade', readonly=True)
    employee_id = fields.Many2one(related='claim_id.employee_id', store=True,
                                  index=True, string='Employee')
    company_id = fields.Many2one(related='claim_id.company_id', store=True,
                                 index=True, string='Company')
    currency_id = fields.Many2one(related='claim_id.currency_id', store=True,
                                  string='Currency')
    amount = fields.Monetary(string='Amount', currency_field='currency_id',
                             readonly=True)
    kind = fields.Selection(PAYLINE_KINDS, string='How', required=True,
                            default='payroll', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', index=True,
                                 ondelete='set null', readonly=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run', index=True,
                             ondelete='set null', readonly=True)
    pay_month = fields.Date(string='Pay month', readonly=True)
    state = fields.Selection(PAYLINE_STATES, string='Status', required=True,
                             default='reserved', index=True, readonly=True)
    paid_on = fields.Date(string='Paid on', readonly=True)
    note = fields.Char(string='Note', readonly=True)

    _one_live_per_claim = models.UniqueIndex(
        "(claim_id) WHERE state IN ('reserved', 'paid')",
        "This claim is already being paid back.")
    _amount_not_negative = models.Constraint(
        'CHECK(amount >= 0)', 'A claim paid back cannot be below zero.')

    # ------------------------------------------------------------ guards
    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("Claims paid back in pay are recorded by the system."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("Claims paid back in pay are recorded by the system."))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get(TOKEN_KEY) is not WRITE_TOKEN:
            raise AccessError(_("Claims paid back in pay are recorded by the system."))
        return super().unlink()

    @api.model
    def _pb_create(self, vals):
        return self.with_context(**{TOKEN_KEY: WRITE_TOKEN}).sudo().create(vals)

    def _pb_write(self, vals):
        return self.with_context(**{TOKEN_KEY: WRITE_TOKEN}).sudo().write(vals)

    # ------------------------------------------------------------ follow
    @api.model
    def _pb_slips_follow(self, slips, before, state):
        """A payslip changed state: its claims follow (paid / held again /
        given back)."""
        lines = self.sudo().search([('payslip_id', 'in', slips.ids),
                                    ('kind', '=', 'payroll'),
                                    ('state', 'in', LIVE_STATES)])
        if not lines:
            return
        today = fields.Date.context_today(self)
        if state in DONE_STATES:
            todo = lines.filtered(lambda l: l.state == 'reserved')
            if todo:
                todo._pb_write({'state': 'paid', 'paid_on': today})
                todo.claim_id._pb_set_paid(today)
        elif state == 'cancel':
            lines._pb_release(_("payslip cancelled"))
        else:
            undone = lines.filtered(lambda l: l.state == 'paid'
                                    and before.get(l.payslip_id.id) in DONE_STATES)
            if undone:
                undone._pb_write({'state': 'reserved', 'paid_on': False})
                undone.claim_id._pb_set_unpaid()

    @api.model
    def _pb_slips_gone(self, slips, why):
        if slips:
            self.sudo().search([('payslip_id', 'in', slips.ids), ('kind', '=', 'payroll'),
                                ('state', 'in', LIVE_STATES)])._pb_release(why)

    def _pb_release(self, why):
        lines = self.sudo().filtered(lambda l: l.state in LIVE_STATES
                                     and l.kind == 'payroll')
        if not lines:
            return
        paid_claims = lines.filtered(lambda l: l.state == 'paid').claim_id
        lines._pb_write({'state': 'released', 'paid_on': False,
                         'note': _("Given back: %s.", why)})
        paid_claims._pb_set_unpaid()

    # ------------------------------------------------------------ words
    def _pb_run_label(self):
        self.ensure_one()
        return self.run_id.name or self.payslip_id.name or ''
