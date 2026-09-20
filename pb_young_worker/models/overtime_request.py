# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Gate 1 (HARD) — overtime is not permitted for banded workers.

Constrained on the model, so EVERY entry path is covered: the OT request form,
the Phase B grid upsert (which creates hr.overtime.request), and any RPC.
"""

from odoo import api, models, _
from odoo.exceptions import ValidationError


class OvertimeRequest(models.Model):
    _inherit = 'hr.overtime.request'

    def action_approve(self):
        # Review K-F7: approval writes none of the constraint's trigger fields,
        # so a submitted minor row that PREDATES the rule (or was filed while no
        # rule was active) would slip through — re-run the gate at decision time.
        self._pb_yw_block_minor_ot()
        return super().action_approve()

    @api.constrains('employee_id', 'date', 'overtime_type', 'planned_hours', 'actual_hours')
    def _pb_yw_block_minor_ot(self):
        Eng = self.env['pb.young.worker'].sudo()
        if not Eng._has_any_rule():
            return
        for rec in self:
            if not rec.employee_id or not rec.date:
                continue
            band = Eng.get_band(rec.employee_id, rec.date)
            if band and band.ot_blocked:
                raise ValidationError(_(
                    "Overtime is not permitted for workers under 18 "
                    "(Vietnam Labor Code). %(name)s is in the %(lo)s–%(hi)s age band.",
                    name=rec.employee_id.name, lo=band.age_min, hi=band.age_max))
