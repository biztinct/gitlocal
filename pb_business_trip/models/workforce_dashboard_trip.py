# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from odoo import fields, models


class WorkforceDashboardTrip(models.TransientModel):
    """Count employees on an authorized trip as PRESENT (C18.4) — they are
    'Business Trip (Present)', not absent. Adjusts the base absence/presence
    KPIs via the trip-day helper without materializing any attendance."""
    _inherit = 'hr.workforce.dashboard'

    def _compute_kpis(self):
        super()._compute_kpis()
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = today_start + timedelta(days=1)
        for rec in self:
            employees = self.env['hr.employee'].search(rec._get_employee_domain())
            if not employees:
                continue
            trip_map = self.env['pb.business.trip']._get_trip_day_map(
                employees.ids, today, today)
            trip_set = {eid for eid, days in trip_map.items() if days}
            if not trip_set:
                continue
            # employees who are on a trip but did NOT physically punch today
            checked_in = self.env['hr.attendance'].sudo().search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', today_start), ('check_in', '<', today_end),
            ]).mapped('employee_id')
            extra = trip_set - set(checked_in.ids)
            if not extra:
                continue
            present = rec.present_today + len(extra)
            rec.present_today = present  # keep the KPI trio consistent
            rec.absent_today = max(0, rec.total_employees - present)
            rec.presence_rate = (present / rec.total_employees * 100
                                 ) if rec.total_employees else 0
