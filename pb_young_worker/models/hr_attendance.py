# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Gate 2 (HARD) — a banded worker's daily hours are capped.

Constrained on hr.attendance so the cap holds for every source (kiosk, systray,
Phase A GPS, Phase B grid). Only the local day of the punch is summed, and only
when a band exists — the general population pays one cheap short-circuit. The
WEEKLY cap is NOT enforced per-punch (perf + partial-week semantics); it lives
in the grid save path (attendance_weekentry.py) and the payroll advisory.
"""

from odoo import api, models, _
from odoo.exceptions import ValidationError


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _pb_yw_check_daily_cap(self):
        Eng = self.env['pb.young.worker'].sudo()
        if not Eng._has_any_rule():
            return
        seen = set()
        for att in self:
            if not att.check_in or not att.employee_id:
                continue
            emp = att.employee_id
            d = Eng._local_date(emp, att.check_in)
            key = (emp.id, d)
            if key in seen:
                continue
            seen.add(key)
            band = Eng.get_band(emp, d)
            if not band:
                continue
            res = Eng.check_day_hours(emp, d)
            if not res['ok']:
                raise ValidationError(_(
                    "%(name)s is under 18: daily working time is capped at "
                    "%(cap).0f h (Vietnam Labor Code). This day totals %(actual).1f h.",
                    name=emp.name, cap=res['cap'], actual=res['actual']))
