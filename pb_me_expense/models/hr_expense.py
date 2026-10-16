# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The one field this module adds to a stock model, and two small guards.

* `pb_claim_id` — which claim a receipt rides in (D1). `ondelete='set null'`:
  deleting a claim never deletes an expense finance may already have posted.
* The stock Approve / Refuse / Reset buttons on an expense whose claim has an
  OPEN approval request refuse with one plain sentence (D3, precedent
  pb_timeoff's routed buttons): the claim is decided as a whole, from the
  approvals inbox. Without an open request stock behaviour is untouched.
* "Paid" is read from the expenses: a write that can change an expense's
  status (its approval, its journal entry) asks the claims it touches to look
  again (`pb.expense.claim._sync_paid`, cheap — approved claims only).
"""

from odoo import fields, models
from odoo.exceptions import UserError

#: Writes that can move an expense's computed `state` towards "paid".
_STATE_INPUTS = frozenset({'state', 'approval_state', 'account_move_id'})


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    pb_claim_id = fields.Many2one(
        'pb.expense.claim', string='Expense claim', index=True,
        ondelete='set null', copy=False, readonly=True)

    # ------------------------------------------------------------- guards
    def _pb_claim_in_approval(self):
        """The first claim among these expenses that is waiting on its
        approval route, or an empty recordset."""
        for claim in self.sudo().mapped('pb_claim_id'):
            if claim._chain_open_request():
                return claim
        return self.env['pb.expense.claim']

    def _pb_refuse_stock_button(self):
        claim = self._pb_claim_in_approval()
        if claim:
            raise UserError(self.env._(
                "This receipt is part of claim %s. Decide it from Approvals.",
                claim.name))

    def action_approve(self):
        self._pb_refuse_stock_button()
        return super().action_approve()

    def action_refuse(self):
        self._pb_refuse_stock_button()
        return super().action_refuse()

    def action_reset(self):
        self._pb_refuse_stock_button()
        return super().action_reset()

    # ----------------------------------------------------------- paid sync
    def write(self, vals):
        res = super().write(vals)
        if _STATE_INPUTS & set(vals):
            claims = self.sudo().mapped('pb_claim_id').filtered(
                lambda c: c.state == 'approved')
            if claims:
                claims._sync_paid()
        return res
