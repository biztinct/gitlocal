# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.attendance.exception.engine — the read-only exception feed (Phase G §3).

A per-day feed of attendance exceptions computed from PUBLISHED shifts + raw
attendances, MINUS approved-trip days, MINUS validated-leave days, MINUS days
before the employee's first contract day. It CONSUMES hr.shift.planning's own
``compliance_status`` (config-driven since Phase G) for late/early — it does not
re-derive the tolerance math — and NEVER writes anything (safety rail 3).

Batched like ``pb.young.worker.check_period``: one search per model over the
whole cohort, folded in Python. All methods are ``@api.model``.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

# kinds surfaced by the feed (icons/labels live in the cockpit)
KIND_MISSING_PUNCH = 'missing_punch'
KIND_MISSING_CHECKOUT = 'missing_checkout'
KIND_LATE = 'late'
KIND_EARLY = 'early_leave'


class PbAttendanceExceptionEngine(models.AbstractModel):
    _name = 'pb.attendance.exception.engine'
    _description = 'Attendance Exception Engine (read-only feed)'

    # ------------------------------------------------------------- helpers
    @api.model
    def _trip_days(self, employee_ids, df, dt):
        """{emp_id: set(iso)} of APPROVED trip days — soft-hook (module stays
        installable without pb_business_trip)."""
        if 'pb.business.trip' in self.env:
            return self.env['pb.business.trip']._get_trip_day_map(
                employee_ids, df, dt)
        return {}

    @api.model
    def _leave_days(self, employee_ids, df, dt):
        """{emp_id: set(iso)} of VALIDATED leave days overlapping [df, dt]."""
        out = defaultdict(set)
        if 'hr.leave' not in self.env:
            return out
        # leaves carry datetimes; compare against the whole last day
        start_dt = datetime.combine(df, time.min)
        end_dt = datetime.combine(dt, time.max)
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', end_dt), ('date_to', '>=', start_dt),
        ])
        for lv in leaves:
            d0 = max(lv.date_from.date(), df)
            d1 = min(lv.date_to.date(), dt)
            cur = d0
            while cur <= d1:
                out[lv.employee_id.id].add(cur.isoformat())
                cur += timedelta(days=1)
        return out

    @api.model
    def _first_contract_day(self, employee_ids):
        """{emp_id: date} of the employee's earliest contract start — days
        before it are never 'missing', the person had not joined."""
        out = {}
        if 'hr.contract' not in self.env:
            return out
        rows = self.env['hr.contract'].sudo().search_read(
            [('employee_id', 'in', employee_ids), ('date_start', '!=', False)],
            ['employee_id', 'date_start'], order='date_start')
        for r in rows:
            eid = r['employee_id'][0] if r['employee_id'] else False
            if eid and eid not in out:  # first (earliest) wins
                out[eid] = r['date_start']
        return out

    # --------------------------------------------------------- the feed
    @api.model
    def _get_exceptions(self, employees, date_from, date_to):
        """Exception rows for `employees` over [date_from, date_to].

        Row = {employee_id, name, avatar_url, date, kind, shift_id, shift_code,
        detail, minutes}. Read-only.

        Underscore-private (C18.32, review G-C1): every read below is sudo, so
        an RPC-reachable name would hand any authenticated session the whole
        cohort's attendance story. Callers (this module's cockpit, pb_insights,
        pb_workforce_insights, pb_team) gate themselves first.
        """
        if not isinstance(employees, models.BaseModel):
            employees = self.env['hr.employee'].browse(
                [int(e) for e in (employees or [])])
        employees = employees.exists()
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to)
        if not employees or not df or not dt:
            return []
        emp_ids = employees.ids
        now = fields.Datetime.now()

        trip_map = self._trip_days(emp_ids, df, dt)
        leave_map = self._leave_days(emp_ids, df, dt)
        first_contract = self._first_contract_day(emp_ids)
        Rule = self.env['pb.attendance.rule']
        threshold_cache = {}  # company_id -> open_checkout_hours

        def open_hours(company):
            cid = company.id if company else False
            if cid not in threshold_cache:
                threshold_cache[cid] = Rule._grace_for_company(company)[2]
            return threshold_cache[cid]

        def excluded(emp_id, iso):
            return (iso in trip_map.get(emp_id, ())
                    or iso in leave_map.get(emp_id, ()))

        # --- batch read: published shifts (1 query) ---
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('date', '>=', df), ('date', '<=', dt),
            ('state', '=', 'published'),
        ])

        # --- batch read: attendances in the window + a day of slack EACH side
        # (an employee-local day maps to the previous OR next UTC day depending
        # on the tz offset — review G-M5) ---
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('check_in', '>=', datetime.combine(df - timedelta(days=1), time.min)),
            ('check_in', '<=', datetime.combine(dt + timedelta(days=1), time.max)),
        ])
        # Punch days are keyed by the EMPLOYEE-LOCAL date, not the UTC date
        # (review G-M5): in VN (UTC+7) a 05:58 local punch lands on the previous
        # UTC day, and UTC keying would invent exactly the missing_punch that
        # C18.49 forbids. Shift dates are already local calendar days.
        tz_cache = {}

        def local_day(emp, dt_utc):
            tzinfo = tz_cache.get(emp.id)
            if tzinfo is None:
                try:
                    tzinfo = pytz.timezone(emp.tz or 'UTC')
                except Exception:
                    tzinfo = pytz.UTC
                tz_cache[emp.id] = tzinfo
            return pytz.UTC.localize(dt_utc).astimezone(tzinfo).date()

        att_days = defaultdict(list)  # (emp_id, iso) -> [attendance]
        for a in atts:
            att_days[(a.employee_id.id,
                      local_day(a.employee_id, a.check_in).isoformat())].append(a)

        emp_by_id = {e.id: e for e in employees}
        rows = []

        def add(emp, d, kind, detail, minutes=0, shift=None):
            rows.append({
                'employee_id': emp.id,
                'name': emp.name,
                'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                'date': d.isoformat(),
                'kind': kind,
                'shift_id': shift.id if shift else False,
                'shift_code': (shift.shift_template_id.code if shift
                               and shift.shift_template_id else ''),
                'detail': detail,
                'minutes': int(round(minutes)),
            })

        # --- shift-derived exceptions (missing punch / late / early leave) ---
        for shift in shifts:
            emp = shift.employee_id
            d = shift.date
            iso = d.isoformat()
            if excluded(emp.id, iso):
                continue
            fc = first_contract.get(emp.id)
            if fc and d < fc:
                continue
            status = shift.compliance_status
            day_atts = att_days.get((emp.id, iso), [])
            if status == 'absent':
                # a punch may exist but be unlinked to the shift — only a truly
                # punchless day is a missing punch (never invent an absence)
                if not day_atts:
                    add(emp, d, KIND_MISSING_PUNCH,
                        _("No punch against the published %s shift.",
                          shift.shift_template_id.code or _('scheduled')),
                        shift=shift)
            elif status == 'late' and shift.actual_check_in and shift.start_datetime:
                mins = (shift.actual_check_in - shift.start_datetime).total_seconds() / 60.0
                add(emp, d, KIND_LATE,
                    _("Checked in %(m)d min after the shift start.", m=round(mins)),
                    minutes=mins, shift=shift)
            elif status == 'early_leave' and shift.actual_check_out and shift.end_datetime:
                mins = (shift.end_datetime - shift.actual_check_out).total_seconds() / 60.0
                add(emp, d, KIND_EARLY,
                    _("Left %(m)d min before the shift end.", m=round(mins)),
                    minutes=mins, shift=shift)

        # --- missing check-out: a still-open punch older than the threshold ---
        for a in atts:
            if a.check_out or not a.check_in:
                continue
            d = local_day(a.employee_id, a.check_in)
            if not (df <= d <= dt):
                continue
            emp = a.employee_id
            hours_open = (now - a.check_in).total_seconds() / 3600.0
            if hours_open >= open_hours(emp.company_id):
                add(emp, d, KIND_MISSING_CHECKOUT,
                    _("Punch open %(h)d h with no check-out.", h=round(hours_open)))

        rows.sort(key=lambda r: (r['date'], r['name']), reverse=True)
        return rows
