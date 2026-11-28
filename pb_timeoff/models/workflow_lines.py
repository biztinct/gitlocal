# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What Time off tells Workflow Studio about a request's days (WF2 P6a).

"Repeat for each…" in Workflow Studio can run a group of steps once per day
of a time-off request ("day 2 of 5 · Tue 17 Nov"). Studio never walks a
request's fields itself: it reads the days through this door. A day is a
working day of the employee's own schedule, counted the way the request's own
duration is counted (the request's own absence left out, public holidays
included only when the kind of time off says so); a request with no working
schedule falls back to every calendar day it covers.

Read only: nothing here changes a request or a balance. Same shape as the
expense receipts door (`pb_me_expense/models/workflow_lines.py`). Duck-typed,
so this module still does not depend on Studio. Method-only file, loaded by a
restart (no version bump, ledger G29).
"""

from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.misc import format_date

#: A request never has more lines than this read back (Studio caps a repeat
#: at 200; reading one more lets it say "more than the limit").
MAX_LINES = 201


class HrLeaveWorkflowLines(models.Model):
    _inherit = 'hr.leave'

    @api.model
    def _workflow_capabilities(self):
        caps = super()._workflow_capabilities()
        _ = self.env._
        caps['lines'] = [{
            'key': 'days', 'label': _('Days'), 'singular': _('day'),
            'fields': [
                {'key': 'date', 'label': _('Date'), 'type': 'date'},
                {'key': 'hours', 'label': _('Hours'), 'type': 'number'},
            ],
        }]
        return caps

    def _pb_request_days(self):
        """[(date, hours)] of this request, oldest first."""
        self.ensure_one()
        leave = self.sudo()
        start, end = leave.request_date_from, leave.request_date_to or leave.request_date_from
        if not start or not end or end < start:
            return []
        employee = leave.employee_id
        calendar = leave.resource_calendar_id or employee.resource_calendar_id or leave.company_id.resource_calendar_id
        if employee and calendar and leave.date_from and leave.date_to:
            domain = [('time_type', '=', 'leave'), ('company_id', 'in', [leave.company_id.id or employee.company_id.id]),
                      '|', ('holiday_id', '=', False), ('holiday_id', '!=', leave.id)]
            keep_holidays = bool(leave.holiday_status_id.include_public_holidays_in_duration)
            per_day = employee.with_context(compute_leaves=not keep_holidays)._list_work_time_per_day(
                leave.date_from, leave.date_to, calendar=calendar, domain=domain).get(employee.id) or []
            days = [(d, h) for d, h in per_day if start <= d <= end]
            if days:
                return days[:MAX_LINES]
        out, day = [], start
        while day <= end and len(out) < MAX_LINES:
            out.append((day, 0.0))
            day += timedelta(days=1)
        return out

    def _pb_day_row(self, day, hours):
        return {'id': fields.Date.to_string(day),
                'name': format_date(self.env, day, date_format='EEE d MMM'),
                'values': {'date': fields.Date.to_string(day), 'hours': round(float(hours or 0.0), 2)}}

    def _workflow_lines(self, key):
        """[{id, name, values}] — one per day of the request (id = the date)."""
        self.ensure_one()
        if key != 'days':
            return []
        return [self._pb_day_row(d, h) for d, h in self._pb_request_days()]

    def _workflow_line(self, key, line_id):
        """One day's row, read again now; None when the request no longer
        covers it (its dates were changed)."""
        self.ensure_one()
        if key != 'days':
            return None
        return next((self._pb_day_row(d, h) for d, h in self._pb_request_days()
                     if fields.Date.to_string(d) == str(line_id)), None)
