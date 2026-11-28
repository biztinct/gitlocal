# -*- coding: utf-8 -*-
"""The "Why?" window behind Reject on the run form and the kanban.

LEARN REFRESH step 6: a rejected pay run always carries its reason. The board
asks in the card; the two older doors open this window. It holds nothing of
its own — it hands the reason to `action_payslip_run_cancel`, which does the
checking (state, write access) and the writing.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class PbPayrunReject(models.TransientModel):
    _name = 'pb.payrun.reject'
    _description = 'Reject a pay run'

    run_id = fields.Many2one('hr.payslip.run', string='Pay run',
                             required=True, readonly=True, ondelete='cascade')
    run_name = fields.Char(related='run_id.name', string='Run')
    reason = fields.Text(string='Why?', required=True)

    def action_confirm(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(_("Say why the pay run is rejected."))
        self.run_id.with_context(pb_reject_note=reason).action_payslip_run_cancel()
        return {'type': 'ir.actions.act_window_close'}
