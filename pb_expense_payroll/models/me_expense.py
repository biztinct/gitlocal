# -*- coding: utf-8 -*-
"""The employee's own pages: where the money of a pay-run claim is.

`pb.me.expense.claim_page` already checked the claim is the caller's own
(`_own_claim`) and works under sudo; the dict it returns is the claim page's
template values, so one more key reaches the page without a controller."""
from odoo import api, models


class PbMeExpensePay(models.AbstractModel):
    _inherit = 'pb.me.expense'

    @api.model
    def claim_page(self, claim):
        page = super().claim_page(claim)
        own = page.get('claim')
        page['pb_pay'] = own._pb_pay_status() if own else None
        return page
