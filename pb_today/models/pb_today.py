# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.today — RPC facade for the Today triage board (Workforce P1b).

Today replaces TWO surfaces: the Live Attendance feed (``hr.attendance.live``,
a Deputy-style status board that could only be looked at) and the Workforce
Dashboard (a Chart.js-in-a-form analytics page). It folds in the driver map as
a card. What it is NOT is a reporting screen: deep analytics live in Insights /
Explorer, so this facade ships counts and PEOPLE, never a series.

WHAT THE TILES MEAN (the contract every later phase inherits)
-------------------------------------------------------------
The five states are the legacy Live-Attendance definitions, unchanged:

  ``on_shift``     the person has an open punch (checked in, not out)
  ``checked_out``  the person's last punch of the day is closed
  ``on_leave``     an approved (``validate`` / ``validate1``) leave covers the day
  ``not_started``  none of the above — expected, no punch
  ``late``         a CROSS-CUT, not a bucket: it overlaps ``on_shift`` /
                   ``checked_out`` / ``not_started`` and is never added to the
                   total. See the grace note below.

``total`` = on_shift + checked_out + not_started + on_leave, always.

THE COHORT (deliberate change from the legacy board — see the P1b report)
------------------------------------------------------------------------
Live Attendance took EVERY active employee in the database and looped over them
in Python. On a 4 500-employee tenant that is thousands of rows of "not started"
that nobody is triaging, and one board render per RPC that walks the whole HR
table. Today scopes to the people the DAY is actually about:

    employees with a published/completed shift on the day
  ∪ employees who punched on the day
  ∪ employees on approved leave on the day

which is the same shape as ``pb.attendance.flow._cohort`` (shift-in-window ∪
open punches) — chosen on purpose, so the Today tiles and the Exceptions queue
are talking about the same population rather than two different ones.

GRACE / "LATE" (§2.5 — Today and Exceptions must never disagree)
----------------------------------------------------------------
Late is resolved from ``pb.attendance.rule`` through
``_grace_for_company`` — the company-else-GLOBAL two-search — which is the SAME
source ``hr.shift.planning._compute_compliance_status`` (patched by
pb_attendance_flow) uses, and therefore the same source the exception engine
consumes. Concretely:

  * a shift whose arrival is known (``actual_check_in``, else the day's first
    punch) is late when it is more than ``grace_in_minutes`` past
    ``start_datetime`` — byte-identical to the ``compliance_status == 'late'``
    branch, so an employee flagged here is flagged by the exception engine too;
  * a shift with NO arrival yet is late only when the board's day IS today and
    the clock has already passed ``start + grace``. That case has no exception
    row yet (the engine only calls it ``missing_punch`` once the shift has
    ended) — it is the live half of the board, and it is why Today exists.

The legacy board hardcoded a 10-minute tolerance here and therefore disagreed
with every other Workforce surface by five minutes; that is now impossible.
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Officer-and-up, matching pb.time.hub. The attendance groups nest
# own_reader < officer < user < manager, so the officer group covers every
# working tier. Live Attendance was ALSO officer-gated; the Workforce Dashboard
# was not, and folding its counts in here narrows them on purpose.
_OFFICER_GROUP = 'hr_attendance.group_hr_attendance_officer'

_PLANNED_STATES = ('published', 'completed')
_APPROVED_LEAVE_STATES = ('validate', 'validate1')

# Shared row budget (§2.6). The JS mirror is WF_ROW_CAP in
# pb_wf_kit/static/src/js/wf_rows.js — the two must stay equal, and
# pb_today/tests/test_static.py asserts they do.
WF_ROW_CAP = 200

# Row order when the cap bites: the people who need a decision survive it.
_STATE_RANK = {
    'not_started': 0,
    'on_shift': 1,
    'checked_out': 2,
    'on_leave': 3,
}


class PbToday(models.AbstractModel):
    _name = 'pb.today'
    _description = 'Today Triage Board'

    # ------------------------------------------------------------- access
    @api.model
    def _require_officer(self):
        u = self.env.user
        if not (u.has_group(_OFFICER_GROUP) or u.has_group('base.group_system')):
            raise AccessError(_("The Today board is restricted to attendance officers."))

    @api.model
    def _company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    # ------------------------------------------------------------ helpers
    @api.model
    def _tzinfo(self, emp):
        """Display timezone for one employee's clock times.

        The employee's own tz first (a multi-site tenant has people on several),
        then the officer's, then UTC. Never the naive UTC value straight out of
        the column — the legacy board did that and printed 01:00 for an 08:00
        Vietnamese shift.
        """
        name = (emp.tz if emp else None) or self.env.user.tz or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:                                     # pragma: no cover
            return pytz.UTC

    @api.model
    def _hhmm(self, dt_utc, tzinfo):
        if not dt_utc:
            return ''
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).strftime('%H:%M')

    # =========================================================== the board
    @api.model
    def get_today_data(self, department_id=False, day=False):
        """Tiles + people rows for one calendar day.

        `day` defaults to today; the context bar's day pill is its only caller
        in P1b (§2.3 — the Today board is the `day` context's exclusive owner).
        Rows are capped at WF_ROW_CAP with the overflow REPORTED, never silently
        dropped; the tiles are always computed over the WHOLE cohort, so a
        truncated list can never make the counts lie.
        """
        self._require_officer()
        d = fields.Date.to_date(day) or fields.Date.context_today(self)
        today = fields.Date.context_today(self)
        is_today = d == today
        now = fields.Datetime.now()

        co_ids = self._company_ids()
        day_start = datetime.combine(d, time.min)
        day_end = datetime.combine(d, time.max)

        # --- three cohort queries -----------------------------------------
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('company_id', 'in', co_ids),
            ('date', '=', d),
            ('state', 'in', _PLANNED_STATES),
        ])
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id.company_id', 'in', co_ids),
            ('check_in', '>=', day_start), ('check_in', '<=', day_end),
        ], order='check_in')
        # sudo on leave: the presence strip is system-derived context, and
        # without it a viewer lacking hr.leave.type read crashes the whole
        # board on the holiday_status_id dereference. The legacy Live
        # Attendance feed documented the same rail; that file was deleted in P7,
        # so the reasoning lives here now rather than behind a dead reference.
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id.company_id', 'in', co_ids),
            ('state', 'in', _APPROVED_LEAVE_STATES),
            ('date_from', '<=', day_end), ('date_to', '>=', day_start),
        ])

        emp_ids = set(shifts.mapped('employee_id').ids)
        emp_ids |= set(atts.mapped('employee_id').ids)
        emp_ids |= set(leaves.mapped('employee_id').ids)
        emps = self.env['hr.employee'].sudo().browse(sorted(emp_ids)).exists()
        emps = emps.filtered('active')
        if department_id:
            emps = emps.filtered(
                lambda e: e.department_id.id == int(department_id))

        if not emps:
            return self._empty(d, is_today, now)

        keep = set(emps.ids)
        shifts = shifts.filtered(lambda s: s.employee_id.id in keep)
        atts = atts.filtered(lambda a: a.employee_id.id in keep)
        leaves = leaves.filtered(lambda lv: lv.employee_id.id in keep)

        shift_by_emp, att_by_emp, leave_by_emp = {}, {}, {}
        for s in shifts:
            shift_by_emp.setdefault(s.employee_id.id, []).append(s)
        for a in atts:
            att_by_emp.setdefault(a.employee_id.id, []).append(a)
        for lv in leaves:
            leave_by_emp.setdefault(lv.employee_id.id, lv)

        grace_cache = {}

        def grace_in(company):
            cid = company.id if company else False
            if cid not in grace_cache:
                grace_cache[cid] = self.env['pb.attendance.rule']._grace_for_company(
                    company)[0]
            return grace_cache[cid]

        rows = []
        tiles = {'total': 0, 'on_shift': 0, 'checked_out': 0,
                 'not_started': 0, 'on_leave': 0, 'late': 0}

        for emp in emps:
            row = self._row(emp, shift_by_emp.get(emp.id) or [],
                            att_by_emp.get(emp.id) or [],
                            leave_by_emp.get(emp.id),
                            grace_in(emp.company_id), now, is_today)
            rows.append(row)
            tiles['total'] += 1
            tiles[row['state']] += 1
            if row['is_late']:
                tiles['late'] += 1

        # Interest order: unresolved first, worst lateness first inside a state.
        rows.sort(key=lambda r: (not r['is_late'], -r['minutes_late'],
                                 _STATE_RANK.get(r['state'], 9), r['name'] or ''))
        truncated = 0
        if len(rows) > WF_ROW_CAP:
            truncated = len(rows) - WF_ROW_CAP
            rows = rows[:WF_ROW_CAP]

        return {
            'day': d.isoformat(),
            'is_today': is_today,
            'tiles': tiles,
            'rows': rows,
            'truncated': truncated,
            'updated_at': self._hhmm(now, self._tzinfo(None)),
            # a board with nobody scheduled is a different story from a board
            # where everyone is in; the cockpit picks its empty state from this
            'has_shifts': bool(shifts),
        }

    @api.model
    def _empty(self, d, is_today, now):
        return {
            'day': d.isoformat(),
            'is_today': is_today,
            'tiles': {'total': 0, 'on_shift': 0, 'checked_out': 0,
                      'not_started': 0, 'on_leave': 0, 'late': 0},
            'rows': [],
            'truncated': 0,
            'updated_at': self._hhmm(now, self._tzinfo(None)),
            'has_shifts': False,
        }

    # --------------------------------------------------------------- a row
    @api.model
    def _row(self, emp, day_shifts, day_atts, leave, grace_minutes, now, is_today):
        tzinfo = self._tzinfo(emp)
        shift = day_shifts[0] if day_shifts else None
        # `atts` came back ordered by check_in, so the first is the arrival and
        # the last carries the day's current open/closed state.
        first = day_atts[0] if day_atts else None
        last = day_atts[-1] if day_atts else None

        if last and not last.check_out:
            state = 'on_shift'
        elif last:
            state = 'checked_out'
        elif leave:
            state = 'on_leave'
        else:
            state = 'not_started'

        is_late, minutes_late = self._lateness(
            shift, first, grace_minutes, now, is_today, state)

        shift_label = ''
        if shift:
            code = (shift.shift_template_id.name if shift.shift_template_id else '')
            window = '%s–%s' % (self._hhmm(shift.start_datetime, tzinfo),
                                self._hhmm(shift.end_datetime, tzinfo))
            shift_label = ('%s · %s' % (code, window)) if code else window

        return {
            'id': emp.id,
            'name': emp.name or '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
            'dept': emp.department_id.name if emp.department_id else '',
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'shift_label': shift_label,
            'shift_start': self._hhmm(shift.start_datetime, tzinfo) if shift else '',
            'check_in': self._hhmm(first.check_in, tzinfo) if first else '',
            'check_out': self._hhmm(last.check_out, tzinfo) if (last and last.check_out) else '',
            'state': state,
            'is_late': is_late,
            'minutes_late': minutes_late,
            'leave_type': (leave.holiday_status_id.name or _('Leave')) if leave else '',
            # the two row doors need to know whether a correction makes sense
            'can_correct': state in ('not_started',) or is_late,
        }

    @api.model
    def _lateness(self, shift, first_att, grace_minutes, now, is_today, state):
        """(is_late, minutes_late) — see the grace contract in the docstring."""
        if state == 'on_leave' or not shift or not shift.start_datetime:
            return (False, 0)
        arrival = shift.actual_check_in or (first_att.check_in if first_att else None)
        if arrival:
            mins = (arrival - shift.start_datetime).total_seconds() / 60.0
            if mins > grace_minutes:
                return (True, int(round(mins)))
            return (False, 0)
        # No arrival at all. Only the LIVE day can be "late but still coming";
        # a past day with no punch is a missing punch, which is the exception
        # engine's story, not this tile's.
        if is_today:
            mins = (now - shift.start_datetime).total_seconds() / 60.0
            if mins > grace_minutes:
                return (True, int(round(mins)))
        return (False, 0)
