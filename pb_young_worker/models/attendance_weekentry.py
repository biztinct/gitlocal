# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Gate 4 — the Phase B Weekly-Entry grid.

Two published Phase B seams, no grid internals touched (§ binding non-goal):
  * get_week_entries → for banded employees populate row `flags` (is_minor +
    band caps) and lock every OT measure (editable:false + shield reason).
  * _save_reg → before a REG write, re-check the ISO-week cap including the
    pending delta; a violating cell returns 'week_cap' and other cells commit.

The daily cap and the OT block are already enforced by the model constraints
(hr.attendance / hr.overtime.request); this adds only the weekly cap, which is
deliberately not enforced per-punch.
"""

from odoo import api, fields, models, _


class AttendanceWeekEntry(models.TransientModel):
    _inherit = 'hr.attendance.weekentry'

    @api.model
    def get_week_entries(self, week_start_str=False, department_id=False, search=False):
        data = super().get_week_entries(week_start_str, department_id, search)
        Eng = self.env['pb.young.worker'].sudo()
        if not Eng._has_any_rule():
            return data
        week_start = data.get('week_start')
        week_date = fields.Date.from_string(week_start) if week_start else None
        if not week_date:
            return data
        emp_ids = [r['id'] for r in data.get('rows', [])]
        emps = {e.id: e for e in self.env['hr.employee'].sudo().browse(emp_ids)}
        lock_reason = _("Overtime is not permitted for workers under 18.")
        for row in data.get('rows', []):
            emp = emps.get(row['id'])
            if not emp:
                continue
            band = Eng.get_band(emp, week_date)
            if not band:
                continue
            # merge, never replace: other overlays (e.g. the trip badge flags)
            # populate the same dict below us in the MRO
            row.setdefault('flags', {}).update(
                {'is_minor': True, 'band': band._caps()})
            # lock every OT chip measure in every cell (REG stays editable, the
            # weekly cap is enforced on save)
            for cell in row.get('cells', {}).values():
                for key, measure in cell.get('measures', {}).items():
                    if key == 'reg':
                        continue
                    measure['editable'] = False
                    measure['locked_minor'] = True
                    if not measure.get('lock_reason'):
                        measure['lock_reason'] = lock_reason
        return data

    def _save_reg(self, emp, d, hours, token, att_map, shift_map):
        Eng = self.env['pb.young.worker'].sudo()
        band = Eng.get_band(emp, d)
        if band and hours and hours > 0:
            Att = self.env['hr.attendance'].sudo()
            cur_day = sum(Eng._att_hours(a) for a in att_map.get((emp.id, d), Att.browse()))
            # only a positive delta is gated: an already-over-cap week (historic
            # data, pre-rule) must stay reducible — report, don't retro-enforce
            if hours > cur_day:
                chk = Eng.check_week_hours(emp, d, extra=hours - cur_day)
                if not chk['ok']:
                    return False, 'week_cap'
        return super()._save_reg(emp, d, hours, token, att_map, shift_map)
