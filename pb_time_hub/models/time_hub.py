# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.time.hub — RPC facade for the Time hub cockpit (Workforce P1a).

The Time hub is ONE surface with lens tabs over the attendance dataset: it
absorbs Timecards, Weekly Entry and Attendance Control. The lenses keep calling
their own facades (``hr.attendance.weekentry``, ``pb.attendance.flow``) — this
model only owns what is genuinely the HUB's: the exception ribbon that sits
above every lens, and the person drawer that any avatar in any lens opens.

THE PERSON-WEEK DATA CONTRACT (inherited by every future phase — do not drift)
---------------------------------------------------------------------------
For one employee-week, per day:

  ``sched``    hr.shift.planning ``planned_hours`` for that calendar day, over
               shifts in state published/completed. ``0`` when the day is
               unplanned — the drawer renders that as "—", never as a 0-hour
               shortfall, because "no shift" and "a 0 h shift" are different
               facts.
  ``entered``  the SAME number the Week-Grid lens edits: the wall-clock span
               ``check_out - check_in`` of the day's hr.attendance rows,
               computed by calling ``hr.attendance.weekentry._att_hours`` rather
               than re-deriving it, so the two surfaces can never disagree.
  ``actual``   the sum of Odoo's own ``worked_hours`` for the same rows.
  ``delta``    ``entered - sched``.

``entered`` and ``actual`` deliberately differ (C18, Sudima E): Odoo 19's
``worked_hours`` subtracts the calendar lunch break while the grid round-trips
a lossless span, so an 8 h entry can read back as 7.0 actual. Showing both
side by side is the POINT of the drawer — it is where an officer sees why a
timesheet and a payslip disagree. Days are keyed by ``check_in.date()``, again
matching the Week-Grid lens exactly.
"""

from datetime import date, datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Officer-and-up. `group_hr_attendance_user` ("Officer: Manage all attendances")
# and `group_hr_attendance_manager` both IMPLY `group_hr_attendance_officer`, so
# testing the officer group alone covers all three tiers — and matches the
# Weekly Entry persona this hub replaces. Timecards was previously ungated;
# folding it in here is a deliberate narrowing.
_OFFICER_GROUP = 'hr_attendance.group_hr_attendance_officer'

# Kind → human phrase for the ribbon sentence. Ordered: what blocks payroll
# first, what is merely a tolerance breach after.
_KIND_PHRASE = (
    ('missing_punch', 'missing punch', 'missing punches'),
    ('missing_checkout', 'missing punch-out', 'missing punch-outs'),
    ('late', 'late vs shift', 'late vs shift'),
    ('early_leave', 'early departure', 'early departures'),
)

# OT type → pbim semantic tone (W1 chart order: indigo, amber, blue, rose).
_OT_TONE = {
    'weekday': 'amber',
    'weekend': 'rose',
    'holiday': 'cyan',
    'night': 'indigo',
    'extended': 'amber',
}

_PLANNED_STATES = ('published', 'completed')


class PbTimeHub(models.AbstractModel):
    _name = 'pb.time.hub'
    _description = 'Time Hub Cockpit'

    # ------------------------------------------------------------- access
    @api.model
    def _require_officer(self):
        u = self.env.user
        if not (u.has_group(_OFFICER_GROUP) or u.has_group('base.group_system')):
            raise AccessError(_("The Time hub is restricted to attendance officers."))

    @api.model
    def _company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    # ------------------------------------------------------------- helpers
    @api.model
    def _monday(self, week_start):
        """Delegated to the Week-Grid facade so the hub and the lens can never
        disagree about which Monday a week starts on."""
        return self.env['hr.attendance.weekentry']._monday(week_start)

    @api.model
    def _week_days(self, df):
        return [df + timedelta(days=i) for i in range(7)]

    # =========================================================== ribbon
    @api.model
    def get_hub_summary(self, department_id=False, week_start=False):
        """Ribbon sentence + per-lens badge counts for the context week.

        The exception engine's ``_get_exceptions`` is deliberately
        underscore-private (security fix G-C1): every read inside it is sudo, so
        an RPC-reachable name would hand any authenticated session the whole
        cohort's attendance story. We gate FIRST and then call it — and we reach
        it through ``pb.attendance.flow._cohort`` with the same window and
        department the Exceptions lens uses, so the ribbon's count and the
        board's count are the same number by construction rather than by luck.
        """
        self._require_officer()
        df = self._monday(week_start)
        dt = df + timedelta(days=6)

        Flow = self.env['pb.attendance.flow']
        emps, truncated = Flow._cohort(df, dt, department_id)
        rows = self.env['pb.attendance.exception.engine']._get_exceptions(
            emps, df, dt) if emps else []

        by_kind = {}
        for r in rows:
            by_kind[r['kind']] = by_kind.get(r['kind'], 0) + 1

        total = len(rows)
        parts = []
        for kind, one, many in _KIND_PHRASE:
            n = by_kind.get(kind)
            if n:
                parts.append('%s %s' % (n, one if n == 1 else many))

        if total:
            head = (_("1 entry needs review") if total == 1
                    else _("%s entries need review", total))
            text = '%s — %s' % (head, ' · '.join(parts)) if parts else head
            tone = 'amber'
        else:
            text = _("Nothing needs review this week.")
            tone = 'green'

        return {
            'week_start': df.isoformat(),
            'week_end': dt.isoformat(),
            'open_exceptions': total,
            'by_kind': by_kind,
            'truncated': truncated,
            'ribbon': {'tone': tone, 'text': text},
            # per-lens badge counts; a lens absent from this dict shows no badge
            'lens_counts': {'exceptions': total},
        }

    # ====================================================== person drawer
    @api.model
    def get_person_week(self, employee_id, week_start=False):
        """One employee's week — see the data contract in the module docstring.

        Returns ``{}`` for an unknown employee or one outside ``env.companies``:
        the drawer is reachable from a typeahead, and a cross-company id must
        not leak a name, a schedule or an hours total through it.
        """
        self._require_officer()
        try:
            emp_id = int(employee_id)
        except (TypeError, ValueError):
            return {}
        emp = self.env['hr.employee'].sudo().browse(emp_id).exists()
        if not emp:
            return {}
        # company_id may legitimately be unset (a shared employee record)
        if emp.company_id and emp.company_id.id not in self._company_ids():
            return {}

        df = self._monday(week_start)
        dt = df + timedelta(days=6)
        days = self._week_days(df)
        WeekEntry = self.env['hr.attendance.weekentry']

        # --- planned: one query -------------------------------------------
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date', '>=', df), ('date', '<=', dt),
            ('state', 'in', _PLANNED_STATES),
        ])
        sched_by_day, planned_by_day = {}, {}
        for s in shifts:
            iso = s.date.isoformat()
            sched_by_day[iso] = sched_by_day.get(iso, 0.0) + (s.planned_hours or 0.0)
            planned_by_day.setdefault(iso, []).append(s)

        # --- worked: one query. Keyed by check_in.date() — IDENTICAL to the
        # Week-Grid lens (attendance_weekentry.get_week_entries), so `entered`
        # here is literally the cell the officer edits over there.
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', emp.id),
            ('check_in', '>=', datetime.combine(df, time.min)),
            ('check_in', '<=', datetime.combine(dt, time.max)),
        ])
        att_by_day = {}
        for a in atts:
            att_by_day.setdefault(a.check_in.date().isoformat(), []).append(a)

        trip_days = self._trip_days(emp, df, dt)
        holidays = WeekEntry._holidays(df, dt)
        today = date.today()

        out_days = []
        t_sched = t_actual = t_entered = 0.0
        for d in days:
            iso = d.isoformat()
            day_atts = att_by_day.get(iso, [])
            sched = round(sched_by_day.get(iso, 0.0), 2)
            entered = round(sum(WeekEntry._att_hours(a) for a in day_atts), 2)
            actual = round(sum(a.worked_hours or 0.0 for a in day_atts), 2)
            delta = round(entered - sched, 2)

            flags = []
            if iso in trip_days:
                flags.append('trip')
            if d in holidays:
                flags.append('holiday')
            if d.weekday() >= 5:
                flags.append('weekend')
            if not planned_by_day.get(iso):
                flags.append('unplanned')
            elif not day_atts and d <= today:
                flags.append('missing')
            if any(not a.check_out for a in day_atts):
                flags.append('open')
            if len(day_atts) > 1:
                flags.append('multi')
            if sched and delta > 0.01:
                flags.append('over')
            elif sched and delta < -0.01:
                flags.append('under')

            t_sched += sched
            t_actual += actual
            t_entered += entered
            out_days.append({
                'date': iso,
                'label': d.strftime('%a %d'),
                'is_today': d == today,
                # `planned` distinguishes "no shift" (sched is meaningless, the
                # drawer shows "—") from "a shift worth 0 h".
                'planned': bool(planned_by_day.get(iso)),
                'sched': sched,
                'actual': actual,
                'entered': entered,
                'delta': delta,
                'flags': flags,
            })

        return {
            'employee': self._employee_card(emp),
            'week_start': df.isoformat(),
            'week_end': dt.isoformat(),
            'days': out_days,
            'totals': {
                'sched': round(t_sched, 2),
                'actual': round(t_actual, 2),
                'entered': round(t_entered, 2),
                'delta': round(t_entered - t_sched, 2),
            },
            'ot': self._ot_chips(emp, df, dt),
            'compliance': self._compliance_chip(shifts),
        }

    # ------------------------------------------------------------- pieces
    @api.model
    def _employee_card(self, emp):
        return {
            'id': emp.id,
            'name': emp.name,
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
            'dept': emp.department_id.name if emp.department_id else '',
            # `barcode` is groups="hr.group_hr_user"; this whole facade is
            # officer-gated and reads sudo, so the badge is safe to surface.
            'badge': emp.barcode or '',
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'on_shift_now': self._on_shift_now(emp),
        }

    @api.model
    def _on_shift_now(self, emp):
        now = fields.Datetime.now()
        return bool(self.env['hr.shift.planning'].sudo().search_count([
            ('employee_id', '=', emp.id),
            ('state', 'in', _PLANNED_STATES),
            ('start_datetime', '<=', now), ('end_datetime', '>=', now),
        ]))

    @api.model
    def _trip_days(self, emp, df, dt):
        """{iso} of approved trip days — soft-hook, the hub stays installable
        without pb_business_trip (same pattern as the exception engine)."""
        if 'pb.business.trip' not in self.env:
            return set()
        try:
            return set(self.env['pb.business.trip']._get_trip_day_map(
                [emp.id], df, dt).get(emp.id, ()))
        except Exception:                            # pragma: no cover
            return set()

    @api.model
    def _ot_chips(self, emp, df, dt):
        """The week's overtime, by type, as drawer chips."""
        reqs = self.env['hr.overtime.request'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date', '>=', df), ('date', '<=', dt),
        ])
        cfg_by_type = {}
        for c in self.env['hr.overtime.config'].sudo().search([('active', '=', True)]):
            cfg_by_type.setdefault(c.overtime_type, c)

        agg = {}
        for r in reqs:
            t = r.overtime_type
            slot = agg.setdefault(t, {'hours': 0.0, 'pending': 0})
            slot['hours'] += (r.actual_hours or r.approved_hours or 0.0)
            if r.state in ('draft', 'submitted'):
                slot['pending'] += 1

        chips = []
        for t, slot in agg.items():
            if not slot['hours']:
                continue
            cfg = cfg_by_type.get(t)
            chips.append({
                'type': t,
                'label': (cfg.rate_display if cfg and cfg.rate_display else t.title()),
                'hours': round(slot['hours'], 2),
                'pending': slot['pending'],
                'tone': _OT_TONE.get(t, 'amber'),
            })
        chips.sort(key=lambda c: -c['hours'])
        return chips

    @api.model
    def _compliance_chip(self, shifts):
        """On-time share of the week's planned shifts, or None when unplanned."""
        judged = shifts.filtered(
            lambda s: s.compliance_status in ('on_time', 'late', 'early_leave',
                                              'absent', 'overtime'))
        if not judged:
            return None
        ok = len(judged.filtered(
            lambda s: s.compliance_status in ('on_time', 'overtime')))
        return {'pct': int(round(100.0 * ok / len(judged))), 'of': len(judged)}
