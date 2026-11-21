# -*- coding: utf-8 -*-
"""Finance never pays a receipt the pay run pays back (no double payment).

A receipt the person paid themselves (`own_account`) whose claim is paid back
in the pay run cannot be posted to accounting: stock "Post" refuses with one
plain sentence. Company-card receipts are company money and are posted as
today. Claims finance pays (the default) are untouched.
"""
from odoo import _, models
from odoo.exceptions import UserError


class HrExpenseClaimsPay(models.Model):
    _inherit = 'hr.expense'

    def _pb_paid_in_pay(self):
        return self.sudo().filtered(
            lambda e: e.payment_mode != 'company_account' and e.pb_claim_id
            and e.pb_claim_id.pb_pay_route == 'payrun')

    def action_post(self):
        in_pay = self._pb_paid_in_pay()
        if in_pay:
            raise UserError(_(
                "%(receipt)s is part of claim %(claim)s, which is paid back in the "
                "pay run. Finance does not pay it.",
                receipt=in_pay[0].name or '', claim=in_pay[0].pb_claim_id.name or ''))
        return super().action_post()
