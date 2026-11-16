# -*- coding: utf-8 -*-
"""A claim against a trip with a cash advance: it waits for the settlement,
then pays only what the advance did not cover (no money paid twice)."""
from odoo import _, models


class PbExpenseClaimAdvance(models.Model):
    _inherit = 'pb.expense.claim'

    def _pb_trip_advances(self):
        self.ensure_one()
        trips = self.sudo().expense_ids.mapped('pb_trip_id')
        if not trips:
            return self.env['pb.trip.advance']
        return self.env['pb.trip.advance'].sudo().search([('trip_id', 'in', trips.ids)])

    def _pb_payable_amount(self):
        amount = super()._pb_payable_amount()
        offsets = self.env['pb.trip.advance.offset'].sudo().search(
            [('claim_id', '=', self.id)])
        if offsets:
            amount = self.currency_id.round(max(amount - sum(offsets.mapped('amount')), 0.0))
        return amount

    def _pb_pay_hold_reason(self):
        reason = super()._pb_pay_hold_reason()
        if reason:
            return reason
        given = self._pb_trip_advances().filtered(
            lambda a: a.state in ('given', 'waiting'))
        if given:
            return _("Waits until the cash advance of trip %s is settled; then only "
                     "what the advance did not cover is paid.", given[:1].trip_id.name)
        return ''
