# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time

import pytz

from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Marks attendance rows SYNTHESIZED by the Weekly Entry grid. Only 'grid'
    # rows may be adjusted/unlinked by the grid — real device/kiosk punches
    # (blank source) are never mutated or destroyed (Phase-B safety rail 2).
    pb_entry_source = fields.Selection(
        [('grid', 'Week grid')],
        string='Entry Source', index=True,
        help='Set when a record is created by the Weekly Entry grid; blank for '
             'device/kiosk/manual punches which the grid must never overwrite.')

    # ------------------------------------------------------------------
    #  THE DAY OF A PUNCH (CLOCK-1, ledger rule 11)
    #
    #  A day is the EMPLOYEE-LOCAL calendar day of check_in everywhere: the
    #  Week Grid, the person drawer, the weekly packet, the freeze, the CLOSE
    #  lock and the exception feed. Before CLOCK-1 the grid / packet / freeze
    #  keyed by the stored UTC `check_in.date()`, so in Vietnam (UTC+7) a 06:30
    #  check-in (23:30 UTC the day before) landed on the previous day — and on
    #  the previous WEEK on a Monday. Device punches make that the common case.
    #
    #  The tz order is IDENTICAL to `pb.wf.lock._local_day`
    #  (pb_close/models/wf_lock.py): employee tz → company calendar tz → UTC.
    #  These helpers live here, the lowest module in the attendance chain, so
    #  every caller above (pb_attendance_flow, pb_time_hub, pb_timesheet_approval,
    #  pb_clock) can use the one answer.
    # ------------------------------------------------------------------
    @api.model
    def _pb_local_tz(self, employee, _cache=None):
        """The pytz zone that defines `employee`'s calendar day."""
        cache = _cache if _cache is not None else {}
        key = employee.id if employee else 0
        tzinfo = cache.get(key)
        if tzinfo is None:
            name = False
            if employee:
                try:
                    emp = employee.sudo()
                    name = emp.tz or emp.company_id.resource_calendar_id.tz
                except Exception:  # noqa: BLE001 — a vanished id reads as UTC
                    name = False
            try:
                tzinfo = pytz.timezone(name or 'UTC')
            except Exception:  # noqa: BLE001 — an odd tz string must not break a day
                tzinfo = pytz.UTC
            cache[key] = tzinfo
        return tzinfo

    @api.model
    def _pb_local_day_of(self, employee, dt_utc, _cache=None):
        """The employee-local calendar day of a naive-UTC datetime."""
        if not dt_utc:
            return False
        tzinfo = self._pb_local_tz(employee, _cache)
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).date()

    def _pb_local_day(self, _cache=None):
        """The employee-local calendar day of this row's check_in.

        `_cache` is a dict the caller keeps across a loop so the zone is looked
        up once per employee, not once per row.
        """
        self.ensure_one()
        return self._pb_local_day_of(self.employee_id, self.check_in, _cache)

    @api.model
    def _pb_week_window_utc(self, employees, week_start, week_end):
        """(start_utc, end_utc), naive UTC, wide enough to hold every punch whose
        LOCAL day is in [week_start, week_end] for any of `employees`.

        Exact union over the distinct zones of the employees (DST-safe: each
        bound is localised on its own date). Callers MUST still bucket by
        `_pb_local_day()` and drop days outside the range — the window is a
        search bound, not a day key.
        """
        week_start = fields.Date.to_date(week_start)
        week_end = fields.Date.to_date(week_end)
        cache = {}
        zones = {}
        for emp in (employees or self.env['hr.employee']):
            tzinfo = self._pb_local_tz(emp, cache)
            zones[tzinfo.zone] = tzinfo
        if not zones:
            zones = {'UTC': pytz.UTC}
        starts, ends = [], []
        for tzinfo in zones.values():
            lo = tzinfo.localize(datetime.combine(week_start, time.min))
            hi = tzinfo.localize(datetime.combine(week_end, time.max))
            starts.append(lo.astimezone(pytz.UTC).replace(tzinfo=None))
            ends.append(hi.astimezone(pytz.UTC).replace(tzinfo=None))
        return min(starts), max(ends)
