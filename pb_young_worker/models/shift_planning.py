# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Gate 3 (HARD) — a banded worker may not be assigned a night shift.

Constrained on hr.shift.planning: if the band blocks night work and the shift
template's local-hour window overlaps the company's protected night window, the
assignment is refused. A cancelled shift never blocks.
"""

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ShiftPlanning(models.Model):
    _inherit = 'hr.shift.planning'

    @api.constrains('employee_id', 'date', 'shift_template_id', 'state')
    def _pb_yw_block_minor_night(self):
        Eng = self.env['pb.young.worker'].sudo()
        if not Eng._has_any_rule():
            return
        for rec in self:
            if rec.state == 'cancelled':
                continue
            if not rec.employee_id or not rec.date or not rec.shift_template_id:
                continue
            band = Eng.get_band(rec.employee_id, rec.date)
            if not (band and band.night_blocked):
                continue
            rule = Eng._rule_for_company(rec.employee_id.company_id)
            if rule and Eng._shift_hits_night(rec.shift_template_id, rule.night_from, rule.night_to):
                raise ValidationError(_(
                    "Night work is not permitted for workers under 18 "
                    "(Vietnam Labor Code). %(name)s cannot be assigned the "
                    "%(shift)s shift, which falls in the %(a)02.0f:00–%(b)02.0f:00 "
                    "night window.",
                    name=rec.employee_id.name,
                    shift=rec.shift_template_id.name or rec.shift_template_id.code,
                    a=rule.night_from, b=rule.night_to))
