# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Public-holiday overtime reads the real public holidays (ledger S5-3).

`hr.attendance.weekentry._holidays` reads `hr.holidays.public.line`, a model
from a version-16 module that does not exist here; it swallowed the error and
answered an empty set, so the weekly grid never offered public-holiday overtime
on a public holiday and always offered weekday overtime instead. Public
holidays on this version are COMPANY CLOSURES (`resource.calendar.leaves` with
no resource, written by the Holidays screen). This answers those, for the
companies the person using the grid is working in.

The original method is left in place underneath: if a later version ships the
old list again, its days are kept as well.
"""

from odoo import api, models


class AttendanceWeekEntryTimePay(models.TransientModel):
    _inherit = 'hr.attendance.weekentry'

    @api.model
    def _holidays(self, week_start, week_end):
        days = set(super()._holidays(week_start, week_end) or ())
        companies = self.env.companies or self.env.company
        try:
            found = self.env['pb.time.pay']._closure_days(
                companies, week_start, week_end)
        except Exception:                                   # noqa: BLE001
            return days
        for company_days in found.values():
            days |= set(company_days)
        return days
