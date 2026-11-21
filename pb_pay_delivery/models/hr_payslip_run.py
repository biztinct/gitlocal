# -*- coding: utf-8 -*-
"""Pay Runs cockpit launcher for the bespoke Pay & Deliver experience.

The board's legacy 'Bank file' + 'Email' buttons are folded into one
'Pay & Deliver' launcher (C18.42a — a legacy surface the phase builds on is
redesigned into the system). This returns the client action; the full-screen
OWL experience carries both lanes.
"""

from odoo import fields, models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    delivery_batch_ids = fields.One2many(
        'pb.payslip.delivery.batch', 'run_id', string='Payslip Deliveries')

    def action_pb_pay_deliver(self):
        """Open the full-screen Pay & Deliver experience for this run."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_pay_delivery',
            'params': {'run_id': self.id},
        }
