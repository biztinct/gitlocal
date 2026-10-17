# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``hr.shift.planning.grid`` — P2's ADDITIVE extension of the roster facade.

STRATEGY (P2 §3.2, binding)
---------------------------
This file may only ADD methods. `get_grid_data`, `quick_create_shift`,
`delete_shift`, `publish_shifts`, `copy_week`, `get_departments` and
`get_job_positions` keep their exact payload shapes.

P2's reason was that the legacy cockpit still consumed them. P7 deleted that
cockpit — and the rule survives it, for a better reason: those seven methods
are now the FACADE, the base every consumer of this model inherits, and their
shapes are read by `pb_schedule`'s own cockpit and by `pb_close._handoff`
(`_pb_rates`). "The old screen depends on it" was always the weaker argument;
"this is the published contract of a base model" is the real one.

`get_schedule_data` is therefore a NEW read model, not a patched one. It differs
from `get_grid_data` in four ways that matter:

  * it is CAPPED. The legacy grid searched every active employee and looped in
    Python; on this tenant that is 4 500 rows per render. `WF_ROW_CAP` (200,
    §2.6) applies, with the overflow REPORTED, and the employees the week is
    actually about — the ones with shifts in the window — sort first so the cap
    can never hide the roster you came to read;
  * SEARCH IS SERVER-SIDE. With a cap, a client-side `filteredEmployees` getter
    would search only the 200 rows that happened to survive it, which is worse
    than no search at all;
  * it carries the three P2 instruments (cost strip, coverage, warnings);
  * it takes its department/week from the shared `wf_context` (W4) — there is
    no private picker on the new cockpit, and no job filter (the legacy job
    dropdown was a second, unsynchronized context and it goes).

NAME CLASH WARNING
------------------
There is a completely different model ALSO called `hr.shift.planning`, declared
by the `hr_shift` module (`hr_shift/models/shift_planning.py`:15). `pb_schedule`
must never depend on, import, or reason about it. Everything here means
`pb_hr_workforce`'s model.
"""

from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Shared row budget (§2.6) — mirrored from pb_wf_kit's WF_ROW_CAP export.
# pb_schedule/tests/test_static.py asserts the two still agree.
WF_ROW_CAP = 200

# The states a shift is "on the roster" in. `cancelled` is excluded everywhere:
# a cancelled shift is a decision, not a plan.
_LIVE_STATES = ('draft', 'published', 'completed')

_APPROVED_LEAVE_STATES = ('validate', 'validate1')
_PENDING_LEAVE_STATES = ('confirm',)


class ShiftPlanningGrid(models.TransientModel):
    _inherit = 'hr.shift.planning.grid'

    # ------------------------------------------------------------- helpers
    @api.model
    def _pb_company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _pb_shift_window(self, template, shift_date, tzname=False):
        """(start, end) UTC-naive datetimes for a template on a day.

        Byte-identical to `quick_create_shift`'s arithmetic (the base facade)
        ON PURPOSE: the warning engine must predict exactly the row the create
        would write, or it would warn about a shift nobody is about to make.

        P5 WP-0b: template hours are WALL-CLOCK floats ("08:00 means 8 in the
        morning where the employee is"), and `start_datetime` is an
        `fields.Datetime`, i.e. UTC by Odoo's contract. Those two facts were
        never reconciled — both this method and the base facade stored the wall
        clock verbatim, so on a UTC+7 tenant an 08:00 shift was persisted as
        08:00 UTC = 15:00 Ho Chi Minh City, which silently mis-answered every
        consumer that DOES localize (the lateness compute, `_save_reg`'s
        derived check-in, and now the roster's own printed times). The
        conversion happens here and in `quick_create_shift`, and nowhere else,
        so the two stay identical.
        """
        start_h = int(template.start_hour)
        start_m = int(round((template.start_hour % 1) * 60))
        end_h = int(template.end_hour)
        end_m = int(round((template.end_hour % 1) * 60))
        start_dt = datetime.combine(
            shift_date, datetime.min.time().replace(hour=start_h, minute=start_m))
        end_day = shift_date + timedelta(days=1) if template.is_overnight else shift_date
        end_dt = datetime.combine(
            end_day, datetime.min.time().replace(hour=end_h, minute=end_m))
        return self._pb_shift_utc(start_dt, end_dt, tzname=tzname or None)

    @api.model
    def _pb_hhmm(self, dt, tzname=False):
        """"08:00" — 24h, tabular, unambiguous, in the READER's wall clock.

        The legacy grid printed `%I:%M%p` ("8am"), which is fine in an English
        roster and unreadable in a Vietnamese one; every other P0–P1 Workforce
        surface prints HH:MM and the strip's numbers line up under it.

        P5 WP-0b: it also printed the STORED value, which is UTC. On the VN
        tenant every card on the roster therefore read 01:00 for an 08:00 shift
        — not a rounding error, a different shift. `tzname` is the employee's
        (W51 family: pb_today, pb_time_hub and the exception engine all
        localize before they say a time out loud). Omitted, the value is
        formatted as given, which is what a caller holding an already-local
        wall clock wants.
        """
        if not dt:
            return ''
        if tzname:
            dt = pytz.UTC.localize(dt).astimezone(pytz.timezone(tzname))
        return dt.strftime('%H:%M')

    @api.model
    def _pb_template_map(self):
        templates = self.env['hr.shift.template'].search([])
        return {t.id: {
            'id': t.id,
            'name': t.name or '',
            'code': t.code or '',
            'color': t.color or 0,
            'shift_type': t.shift_type or '',
            'start_hour': t.start_hour,
            'end_hour': t.end_hour,
            'duration': t.duration,
            'is_overnight': t.is_overnight,
        } for t in templates}

    # ------------------------------------------------------------- cohort
    @api.model
    def _pb_employees(self, department_id, search, shifts):
        """(recordset, truncated) — the roster's rows, capped and ordered.

        Order: people with a shift in the window first (that is what a roster
        is), then the rest of the scoped population, both alphabetically. The
        cap then bites on the tail, where the information is, rather than at
        "Anh" through "Bao".
        """
        domain = [('active', '=', True),
                  ('company_id', 'in', self._pb_company_ids())]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        q = (search or '').strip()
        if q:
            domain += ['|', ('name', 'ilike', q), ('job_title', 'ilike', q)]

        Emp = self.env['hr.employee']
        # A hard limit on the SEARCH too: `search(order='name')` over 4 500 rows
        # to then keep 200 of them is a full table read per keystroke.
        scheduled_ids = [e for e in shifts.mapped('employee_id').ids if e]
        with_shifts = Emp.search(
            domain + [('id', 'in', scheduled_ids)], order='name') if scheduled_ids else Emp
        room = WF_ROW_CAP - len(with_shifts)
        without = Emp
        if room > 0:
            without = Emp.search(
                domain + [('id', 'not in', with_shifts.ids)],
                order='name', limit=room + 1)
        total = Emp.search_count(domain)
        rows = with_shifts + without
        truncated = 0
        if len(rows) > WF_ROW_CAP:
            rows = rows[:WF_ROW_CAP]
        if total > len(rows):
            truncated = total - len(rows)
        return rows, truncated

    # =================================================== the read model
    @api.model
    def get_schedule_data(self, week_start_str, department_id=False,
                          num_days=7, search=''):
        """The Schedule cockpit's ONE read call.

        :param week_start_str: ISO Monday from `wf_context.weekStart`.
        :param department_id: from `wf_context.departmentId` (False = all).
        :param num_days: 7 or 14 — the fortnight toggle widens the window from
            the same context week; it is a local view choice, not a context one.
        :param search: from `wf_context.search`; filtered SERVER-side (see the
            module docstring — a client filter over a capped list is a lie).
        """
        self._require_officer()
        week_start = fields.Date.from_string(week_start_str)
        num_days = 14 if int(num_days or 7) == 14 else 7
        week_end = week_start + timedelta(days=num_days - 1)
        today = fields.Date.context_today(self)
        co_ids = self._pb_company_ids()

        days = []
        for i in range(num_days):
            d = week_start + timedelta(days=i)
            days.append({
                'date': d.isoformat(),
                'label': d.strftime('%a'),
                'day_num': d.day,
                'month': d.strftime('%b'),
                'dow': d.weekday(),
                'is_today': d == today,
                'is_past': d < today,
                'is_weekend': d.weekday() >= 5,
            })

        Shift = self.env['hr.shift.planning']
        window = [('date', '>=', week_start), ('date', '<=', week_end),
                  ('company_id', 'in', co_ids),
                  ('state', 'in', _LIVE_STATES)]
        all_shifts = Shift.search(window)
        if department_id:
            dept = int(department_id)
            scoped = all_shifts.filtered(
                lambda s: not s.employee_id or s.department_id.id == dept)
        else:
            scoped = all_shifts

        employees, truncated = self._pb_employees(department_id, search, scoped)

        # sudo on leave: the presence overlay is system-derived roster context.
        # Same rail the base facade documents at :64-68 and pb.today at :162 —
        # without it a planner who cannot read hr.leave.type crashes the whole
        # roster on the holiday_status_id dereference below.
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('state', 'in', _APPROVED_LEAVE_STATES + _PENDING_LEAVE_STATES),
            ('date_from', '<=', datetime.combine(week_end, datetime.max.time())),
            ('date_to', '>=', datetime.combine(week_start, datetime.min.time())),
        ]) if employees else self.env['hr.leave']

        tmap = self._pb_template_map()
        conflicts = self._detect_conflicts(scoped)
        conflict_shift_ids = set()
        for w in conflicts:
            conflict_shift_ids.add(w.get('shift_a_id'))
            conflict_shift_ids.add(w.get('shift_b_id'))

        by_emp = {}
        for s in scoped:
            if s.employee_id:
                by_emp.setdefault(s.employee_id.id, []).append(s)

        leaves_by_emp = {}
        for lv in leaves:
            lv_start = lv.date_from.date() if isinstance(lv.date_from, datetime) else lv.date_from
            lv_end = lv.date_to.date() if isinstance(lv.date_to, datetime) else lv.date_to
            cur = max(lv_start, week_start)
            stop = min(lv_end, week_end)
            bucket = leaves_by_emp.setdefault(lv.employee_id.id, {})
            while cur <= stop:
                approved = lv.state in _APPROVED_LEAVE_STATES
                prev = bucket.get(cur.isoformat())
                # an approved day beats a pending one on the same square
                if not prev or (approved and not prev['is_approved']):
                    bucket[cur.isoformat()] = {
                        'type': lv.holiday_status_id.name or _('Leave'),
                        'is_approved': approved,
                    }
                cur += timedelta(days=1)

        rows = []
        for emp in employees:
            emp_shifts = by_emp.get(emp.id) or []
            shifts_by_date = {}
            for s in emp_shifts:
                shifts_by_date.setdefault(s.date.isoformat(), []).append(
                    self._pb_shift_card(s, tmap, s.id in conflict_shift_ids))
            calendar = emp.resource_calendar_id
            contracted = (calendar.hours_per_week if calendar else 0.0) or 40.0
            if num_days == 14:
                contracted *= 2
            rows.append({
                'id': emp.id,
                'name': emp.name or '',
                'job_title': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                'total_hours': round(sum(s.planned_hours for s in emp_shifts), 1),
                'contracted_hours': round(contracted, 1),
                'shifts': shifts_by_date,
                'leaves': leaves_by_emp.get(emp.id) or {},
            })

        open_by_date = {}
        for s in scoped.filtered(lambda x: not x.employee_id):
            open_by_date.setdefault(s.date.isoformat(), []).append(
                self._pb_shift_card(s, tmap, False))

        assigned = scoped.filtered(lambda s: s.employee_id)
        stats = self._pb_stats(days, assigned, week_start, num_days,
                               department_id)
        return {
            'stats': stats,
            'coverage': self._pb_coverage(days, scoped, department_id),
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'num_days': num_days,
            'days': days,
            'employees': rows,
            'open_shifts': open_by_date,
            'templates': sorted(tmap.values(), key=lambda t: (t['start_hour'], t['name'])),
            'conflicts': conflicts,
            'truncated': truncated,
            'row_cap': WF_ROW_CAP,
            'counts': {
                'shifts': len(assigned),
                'draft': len(assigned.filtered(lambda s: s.state == 'draft')),
                'published': len(assigned.filtered(lambda s: s.state == 'published')),
                'completed': len(assigned.filtered(lambda s: s.state == 'completed')),
                'open': len(scoped) - len(assigned),
                'conflicts': len(conflicts),
            },
        }

    # ============================================== WP-3: cost & budget
    @api.model
    def _pb_rates(self, employee_ids):
        """{employee_id: hourly rate} — AGGREGATE INPUT ONLY.

        sudo, behind `_require_officer()`, exactly as the base facade's leave
        read is documented (C18.73: the sudo lives behind an EXPLICIT gate,
        never behind the accident of a missing ACL). An attendance officer
        cannot read `hr.contract.wage`, and they must not learn it here either
        — so the individual rates never leave this method. Everything the
        cockpit receives is a day total or a week total (W12).
        """
        if not employee_ids:
            return {}
        contracts = self.env['hr.contract'].sudo().search(
            [('employee_id', 'in', list(employee_ids)), ('state', '=', 'open')],
            order='date_start desc, id desc')
        rates = {}
        for c in contracts:
            eid = c.employee_id.id
            if eid in rates:
                continue                  # the most recent running contract wins
            rates[eid] = c._pb_hourly_rate()
        return rates

    @api.model
    def _pb_budget_rows(self, week_start, num_days, department_id):
        """The budget rows covering the span, most specific scope first.

        A budget is a WEEKLY figure, so a fortnight compares against the sum of
        the two weeks it spans — and reports how many of them were actually
        budgeted, because comparing a two-week roster against one week's money
        is exactly the kind of quiet halving that makes people distrust a
        dashboard.
        """
        Budget = self.env['pb.schedule.budget']
        mondays = [week_start + timedelta(days=7 * i)
                   for i in range(0, max(1, num_days // 7))]
        dept = int(department_id) if department_id else False
        rows = Budget.search([
            ('company_id', 'in', self._pb_company_ids()),
            ('week_start', 'in', mondays),
            ('department_id', '=', dept),
        ])
        return rows, len(mondays)

    @api.model
    def _pb_stats(self, days, assigned, week_start, num_days, department_id):
        """Per-day hours/cost and the week's budget variance.

        Cost = Σ(planned_hours × rate). Actual cost is only reported for days
        that have already happened: a future day has no actual hours, and
        printing 0 next to a scheduled figure reads as "we spent nothing"
        rather than "this has not happened yet".
        """
        # The rate cohort is EVERY employee with a shift in the span, NOT the
        # capped page of rows. `assigned` is already scope-filtered, so a
        # roster whose 201st person is off-screen still costs what it costs —
        # keying the rates off `employees` would have silently zeroed their
        # hours and counted them as "no rate" the moment the cap bit.
        rates = self._pb_rates(assigned.employee_id.ids)
        by_day = {d['date']: {'hours': 0.0, 'cost': 0.0, 'actual_cost': 0.0,
                              'actual_hours': 0.0, 'shifts': 0}
                  for d in days}
        no_rate = set()
        for s in assigned:
            key = s.date.isoformat()
            slot = by_day.get(key)
            if slot is None:
                continue
            rate = rates.get(s.employee_id.id) or 0.0
            if not rate:
                no_rate.add(s.employee_id.id)
            slot['shifts'] += 1
            slot['hours'] += s.planned_hours or 0.0
            slot['cost'] += (s.planned_hours or 0.0) * rate
            slot['actual_hours'] += s.actual_hours or 0.0
            slot['actual_cost'] += (s.actual_hours or 0.0) * rate

        day_stats = []
        for d in days:
            slot = by_day[d['date']]
            day_stats.append({
                'date': d['date'],
                'shifts': slot['shifts'],
                'hours': round(slot['hours'], 1),
                'cost': round(slot['cost'], 2),
                # only settled days carry an actual figure
                'actual_cost': round(slot['actual_cost'], 2) if d['is_past'] else None,
                'actual_hours': round(slot['actual_hours'], 1) if d['is_past'] else None,
            })

        budget_rows, weeks = self._pb_budget_rows(
            week_start, num_days, department_id)
        budget = None
        if budget_rows:
            budget = {
                'amount': round(sum(budget_rows.mapped('amount')), 2),
                'weeks_budgeted': len(budget_rows),
                'weeks_in_span': weeks,
                # the row the dialog edits is the CONTEXT week's row
                'id': next((b.id for b in budget_rows
                            if b.week_start == week_start), False),
            }

        currency = (self.env.companies[:1] or self.env.company).currency_id
        return {
            'days': day_stats,
            'total_hours': round(sum(x['hours'] for x in day_stats), 1),
            'total_cost': round(sum(x['cost'] for x in day_stats), 2),
            'actual_cost': round(sum(x['actual_cost'] or 0.0
                                     for x in day_stats), 2),
            'no_rate': len(no_rate),
            'budget': budget,
            'can_edit_budget': self.env['pb.schedule.budget']._pb_can_edit(),
            'currency': {
                'name': currency.name or 'USD',
                'symbol': currency.symbol or '',
                'position': currency.position or 'after',
                'decimals': currency.decimal_places,
            },
        }

    # ============================================== WP-6: templates drawer
    @api.model
    def get_templates(self, week_start_str, num_days=7, department_id=False):
        """The shift library, with how much each template is used this span.

        The "Shift Templates" rail item retires into this drawer (§3.9, W18).
        Editing still happens on the NATIVE form — a bespoke editor for a
        five-field configuration model would be a second source of truth for
        `duration`, whose compute already lives on the model.
        """
        self._require_officer()
        week_start = fields.Date.from_string(week_start_str)
        num_days = 14 if int(num_days or 7) == 14 else 7
        week_end = week_start + timedelta(days=num_days - 1)

        domain = [('date', '>=', week_start), ('date', '<=', week_end),
                  ('company_id', 'in', self._pb_company_ids()),
                  ('state', 'in', _LIVE_STATES)]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        usage = {}
        for group in self.env['hr.shift.planning'].read_group(
                domain, ['id'], ['shift_template_id']):
            tid = group['shift_template_id'] and group['shift_template_id'][0]
            if tid:
                usage[tid] = group['shift_template_id_count']

        templates = self.env['hr.shift.template'].search([])
        return {
            'rows': [{
                'id': t.id,
                'name': t.name or '',
                'code': t.code or '',
                'color': t.color or 0,
                'shift_type': t.shift_type or '',
                'type_label': dict(
                    t._fields['shift_type'].selection).get(t.shift_type, ''),
                'start': self._pb_float_hhmm(t.start_hour),
                'end': self._pb_float_hhmm(t.end_hour),
                'duration': round(t.duration or 0.0, 2),
                'is_overnight': t.is_overnight,
                'usage': usage.get(t.id, 0),
            } for t in templates],
            'span_label': '%s → %s' % (week_start.isoformat(),
                                       week_end.isoformat()),
        }

    @api.model
    def _pb_float_hhmm(self, value):
        """8.5 -> "08:30". The template's hours are floats, not datetimes."""
        h = int(value or 0)
        m = int(round(((value or 0) % 1) * 60))
        return '%02d:%02d' % (h, m)

    # ============================================== WP-5: edit-time warnings
    #
    # SEVERITIES (binding, P2 §3.6)
    #   block  the server WILL refuse this. Today that is exactly one rule —
    #          pb_young_worker's night ban — and the UI mirrors it so the
    #          planner is told before the save instead of after it. The server
    #          constraint remains the real guard; this is a courtesy, not a
    #          replacement.
    #   warn   a real problem a human should look at: an overlap, or a day the
    #          person is on approved leave. Never blocking.
    #   info   context: a leave request that is still pending.
    #
    # OT ceilings are ADVISORY BY DESIGN and can never be `block`. Overflow
    # above a ceiling becomes bonus hours (Phase K); a roster that refused to
    # schedule at 90% of a monthly cap would be wrong about the business rule,
    # not strict about it.

    @api.model
    def _pb_leave_map(self, employee_ids, date_from, date_to):
        """{(employee_id, iso_date): 'approved'|'pending'} over a window.

        sudo for the same reason the roster's overlay is sudo — leave presence
        is system-derived context, and a planner without `hr.leave.type` read
        must still be warned that they are rostering someone who is away.
        """
        out = {}
        if not employee_ids:
            return out
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', list(employee_ids)),
            ('state', 'in', _APPROVED_LEAVE_STATES + _PENDING_LEAVE_STATES),
            ('date_from', '<=', datetime.combine(date_to, datetime.max.time())),
            ('date_to', '>=', datetime.combine(date_from, datetime.min.time())),
        ])
        for lv in leaves:
            lv_start = lv.date_from.date() if isinstance(lv.date_from, datetime) else lv.date_from
            lv_end = lv.date_to.date() if isinstance(lv.date_to, datetime) else lv.date_to
            cur = max(lv_start, date_from)
            stop = min(lv_end, date_to)
            kind = 'approved' if lv.state in _APPROVED_LEAVE_STATES else 'pending'
            while cur <= stop:
                key = (lv.employee_id.id, cur.isoformat())
                if out.get(key) != 'approved':
                    out[key] = kind
                cur += timedelta(days=1)
        return out

    @api.model
    def _pb_ceilings(self, employee_ids, ref_date):
        """The RPC-safe OT budget payload, batched.

        `pb.ot.ceiling._allowance` / `_split` are PRIVATE; the supported door is
        `hr.attendance.weekentry.get_ot_ceilings` (attendance_weekentry.py:333),
        which is what the Overtime Desk uses too. Going through it is what keeps
        this warning and the OT Desk's red-pulse KPI talking about one number.
        """
        if not employee_ids:
            return {}
        try:
            return self.env['hr.attendance.weekentry'].get_ot_ceilings(
                list(employee_ids), ref_date.isoformat())
        except Exception:
            # A ceiling read must never be able to stop a roster from loading.
            return {}

    @api.model
    def _pb_shift_windows(self, employee_ids, date_from, date_to):
        """{employee_id: [(start, end, shift_id)]} for the overlap test."""
        out = {}
        if not employee_ids:
            return out
        shifts = self.env['hr.shift.planning'].search([
            ('employee_id', 'in', list(employee_ids)),
            ('date', '>=', date_from - timedelta(days=1)),
            ('date', '<=', date_to + timedelta(days=1)),
            ('state', 'in', _LIVE_STATES),
        ])
        for s in shifts:
            if s.start_datetime and s.end_datetime:
                out.setdefault(s.employee_id.id, []).append(
                    (s.start_datetime, s.end_datetime, s.id))
        return out

    @api.model
    def _pb_young_worker_block(self, employee, day, template):
        """Mirror pb_young_worker's ValidationError, or None. Never raises.

        The module is NOT a dependency (§3.1): it is probed, and a tenant
        without it simply gets no such warning. The wording is deliberately the
        same as the constraint's — a planner should not read two different
        sentences about one law.
        """
        if 'pb.young.worker' not in self.env:
            return None
        try:
            Eng = self.env['pb.young.worker'].sudo()
            if not Eng._has_any_rule():
                return None
            band = Eng.get_band(employee, day)
            if not (band and band.night_blocked):
                return None
            rule = Eng._rule_for_company(employee.company_id)
            if not (rule and Eng._shift_hits_night(
                    template, rule.night_from, rule.night_to)):
                return None
            return _(
                "Night work is not permitted for workers under 18 "
                "(Vietnam Labor Code). %(name)s cannot be assigned the "
                "%(shift)s shift, which falls in the %(a)02.0f:00–%(b)02.0f:00 "
                "night window.",
                name=employee.name,
                shift=template.name or template.code,
                a=rule.night_from, b=rule.night_to)
        except Exception:
            # A probe that throws must degrade to silence, not to a broken
            # modal — the server constraint is still the real guard.
            return None

    @api.model
    def _pb_check(self, employee, day, template, windows, leaves, ceilings,
                  exclude_shift_id=False):
        """The warning worker. Pure read; caches are passed in so a 400-shift
        Copy Week is a handful of queries rather than 1 600."""
        warnings = []
        tzname = self._pb_shift_tzname(employee)
        start, end = self._pb_shift_window(template, day, tzname)

        # --- overlap (the same question `_detect_conflicts` asks) -----------
        # Both sides are now UTC — the candidate window because
        # `_pb_shift_window` converts, the stored ones because that is what the
        # column holds — so the comparison is apples to apples for the first
        # time, and the printed times are put back into the employee's clock.
        for (o_start, o_end, o_id) in windows.get(employee.id, []):
            if exclude_shift_id and o_id == exclude_shift_id:
                continue
            if o_start < end and start < o_end:
                warnings.append({
                    'severity': 'warn', 'code': 'overlap',
                    'text': _("%(name)s already has a shift that overlaps "
                              "%(a)s–%(b)s on this day.",
                              name=employee.name,
                              a=self._pb_hhmm(o_start, tzname),
                              b=self._pb_hhmm(o_end, tzname)),
                })
                break

        # --- leave ----------------------------------------------------------
        kind = leaves.get((employee.id, day.isoformat()))
        if kind == 'approved':
            warnings.append({
                'severity': 'warn', 'code': 'leave_approved',
                'text': _("%s is on approved leave that day.", employee.name),
            })
        elif kind == 'pending':
            warnings.append({
                'severity': 'info', 'code': 'leave_pending',
                'text': _("%s has a leave request awaiting approval that day.",
                          employee.name),
            })

        # --- young worker (the only hard rule) ------------------------------
        yw = self._pb_young_worker_block(employee, day, template)
        if yw:
            warnings.append({'severity': 'block', 'code': 'young_worker_night',
                             'text': yw})

        # --- OT ceiling: ADVISORY, matching ot_desk.py:184's 90% ------------
        ceil = ceilings.get(employee.id) or {}
        cap = ceil.get('cap_month') or 0.0
        used = ceil.get('mtd') or 0.0
        if cap and used >= 0.9 * cap:
            warnings.append({
                'severity': 'warn', 'code': 'ot_ceiling',
                'text': _("%(name)s has used %(used).1f of %(cap).1f overtime "
                          "hours this month. Overflow becomes bonus hours.",
                          name=employee.name, used=used, cap=cap),
            })
        return warnings

    @api.model
    def check_shift(self, employee_id, date_str, template_id,
                    exclude_shift_id=False):
        """Would this assignment be a problem? (P2 §3.6)

        :return: ``{'warnings': [{severity, code, text}], 'blocked': bool}``
        """
        self._require_officer()
        employee = self.env['hr.employee'].browse(int(employee_id)).exists()
        template = self.env['hr.shift.template'].browse(int(template_id)).exists()
        day = fields.Date.from_string(date_str)
        if not (employee and template and day):
            return {'warnings': [], 'blocked': False}
        warnings = self._pb_check(
            employee, day, template,
            self._pb_shift_windows([employee.id], day, day),
            self._pb_leave_map([employee.id], day, day),
            self._pb_ceilings([employee.id], day),
            exclude_shift_id=exclude_shift_id)
        return {
            'warnings': warnings,
            'blocked': any(w['severity'] == 'block' for w in warnings),
        }

    @api.model
    def check_day(self, employee_id, date_str, template_ids):
        """Every template's verdict for one square, in ONE round trip.

        The quick-create modal marks each template tile before it is clicked —
        a warning that only appears after you have committed is a receipt, not
        a warning.
        """
        self._require_officer()
        employee = self.env['hr.employee'].browse(int(employee_id)).exists()
        day = fields.Date.from_string(date_str)
        out = {'by_template': {}, 'context': []}
        if not (employee and day):
            return out
        windows = self._pb_shift_windows([employee.id], day, day)
        leaves = self._pb_leave_map([employee.id], day, day)
        ceilings = self._pb_ceilings([employee.id], day)
        templates = self.env['hr.shift.template'].browse(
            [int(t) for t in (template_ids or [])]).exists()
        seen_context = set()
        for tmpl in templates:
            warns = self._pb_check(employee, day, tmpl, windows, leaves, ceilings)
            out['by_template'][str(tmpl.id)] = warns
            # leave / ceiling do not depend on the template: hoist them once so
            # the modal states them at the top instead of on every tile
            for w in warns:
                if w['code'] in ('leave_approved', 'leave_pending', 'ot_ceiling') \
                        and w['code'] not in seen_context:
                    seen_context.add(w['code'])
                    out['context'].append(w)
        for key, warns in out['by_template'].items():
            out['by_template'][key] = [
                w for w in warns if w['code'] not in seen_context]
        return out

    # =============================== WP-5: Copy Week, revalidate-on-paste
    @api.model
    def copy_week_checked(self, source_week_str, target_week_str,
                          department_id=False, num_days=7):
        """Copy a span forward, REFUSING the targets that would be a problem.

        The legacy `copy_week` pasted everything unconditionally: it happily
        rostered people onto approved leave, onto shifts they already had, and
        onto nights a young worker is legally barred from — the last of which
        the ORM then refused, aborting the WHOLE paste with a validation error
        and no report of what had happened.

        This one validates every target first and returns a skip report. It
        does NOT stop at the first problem, because "why did nothing copy" is
        the question the old behaviour left you with.

        Skipped: anything with a `block` or a `warn`. `info` (a pending leave
        request) is not enough to refuse a paste — it is context, and refusing
        on it would make the button useless in any team with open requests.
        """
        self._require_officer()
        source_start = fields.Date.from_string(source_week_str)
        target_start = fields.Date.from_string(target_week_str)
        num_days = 14 if int(num_days or 7) == 14 else 7
        delta = target_start - source_start

        domain = [('date', '>=', source_start),
                  ('date', '<=', source_start + timedelta(days=num_days - 1)),
                  ('company_id', 'in', self._pb_company_ids()),
                  ('state', 'in', _LIVE_STATES)]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        sources = self.env['hr.shift.planning'].search(domain, order='date, id')
        if not sources:
            return {'created': 0, 'skipped': [], 'considered': 0,
                    'target_start': target_start.isoformat()}

        emp_ids = [e for e in sources.mapped('employee_id').ids if e]
        t_from = target_start
        t_to = target_start + timedelta(days=num_days - 1)
        windows = self._pb_shift_windows(emp_ids, t_from, t_to)
        leaves = self._pb_leave_map(emp_ids, t_from, t_to)
        ceilings = self._pb_ceilings(emp_ids, t_to)

        created, skipped = 0, []
        for src in sources:
            employee = src.employee_id
            template = src.shift_template_id
            if not (employee and template):
                continue
            target_day = src.date + delta
            warns = self._pb_check(employee, target_day, template,
                                   windows, leaves, ceilings)
            hard = [w for w in warns if w['severity'] in ('block', 'warn')]
            if hard:
                skipped.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'date': target_day.isoformat(),
                    'template': template.name or template.code or '',
                    'reasons': [w['text'] for w in hard],
                    'severity': 'block' if any(
                        w['severity'] == 'block' for w in hard) else 'warn',
                })
                continue
            start, end = self._pb_shift_window(
                template, target_day, self._pb_shift_tzname(employee))
            self.env['hr.shift.planning'].create({
                'employee_id': employee.id,
                'shift_template_id': template.id,
                'date': target_day,
                'start_datetime': start,
                'end_datetime': end,
                'state': 'draft',
            })
            # a shift created THIS pass is a conflict for the next one — the
            # legacy loop happily pasted two identical shifts onto one person
            windows.setdefault(employee.id, []).append((start, end, 0))
            created += 1

        return {
            'created': created,
            'skipped': skipped,
            'considered': len(sources),
            'target_start': target_start.isoformat(),
        }

    # ================================================== WP-4: coverage
    @api.model
    def _pb_coverage(self, days, scoped, department_id):
        """Required vs scheduled per day. See shift_coverage.py for the rules.

        Returns `None` when the scope has stated no requirements at all — an
        absent rule must produce an absent chip, not a rose gap against an
        implied zero.
        """
        Req = self.env['hr.shift.coverage.requirement']
        co_ids = self._pb_company_ids()
        dept = int(department_id) if department_id else False
        dates = [fields.Date.from_string(d['date']) for d in days]

        rows = Req.search([
            ('company_id', 'in', co_ids),
            ('department_id', 'in', ([dept, False] if dept else [False])),
            '|', ('date', 'in', dates), ('date', '=', False),
        ])
        if not rows:
            return None

        # Rule 1 — specific scope beats general, per (weekday/date, template).
        dept_rows = rows.filtered(lambda r: r.department_id.id == dept) if dept \
            else rows.browse()
        company_rows = rows.filtered(lambda r: not r.department_id)
        scoped_rows = dept_rows if dept_rows else company_rows

        # index by (template_id, key) where key is ('d', date) or ('w', weekday)
        by_key = {}
        for r in scoped_rows:
            tid = r.template_id.id or False
            key = ('d', r.date) if r.date else ('w', r.weekday)
            by_key[(tid, key)] = r.required_headcount

        # supply: draft + published only (§3.5 rule 4)
        planned = scoped.filtered(lambda s: s.state in ('draft', 'published'))
        supply_total, supply_tmpl = {}, {}
        for s in planned:
            iso = s.date.isoformat()
            supply_total[iso] = supply_total.get(iso, 0) + 1
            k = (iso, s.shift_template_id.id)
            supply_tmpl[k] = supply_tmpl.get(k, 0) + 1

        out = {}
        any_rule = False
        for d in days:
            day = fields.Date.from_string(d['date'])
            wd = str(day.weekday())

            def required_for(tid):
                # Rule 2 — the date row is the exception and wins outright.
                if (tid, ('d', day)) in by_key:
                    return by_key[(tid, ('d', day))]
                return by_key.get((tid, ('w', wd)))

            per_template = []
            for tid in {k[0] for k in by_key if k[0]}:
                need = required_for(tid)
                if need is None:
                    continue
                have = supply_tmpl.get((d['date'], tid), 0)
                per_template.append({
                    'template_id': tid,
                    'required': need,
                    'scheduled': have,
                    'gap': max(0, need - have),
                })

            # Rule 3 — a day-total row is authoritative; otherwise the sum.
            day_total = required_for(False)
            if day_total is None and per_template:
                day_total = sum(p['required'] for p in per_template)
            if day_total is None:
                out[d['date']] = None
                continue

            any_rule = True
            have = supply_total.get(d['date'], 0)
            gap = day_total - have
            out[d['date']] = {
                'required': day_total,
                'scheduled': have,
                'gap': max(0, gap),
                'surplus': max(0, -gap),
                'state': 'gap' if gap > 0 else ('exact' if gap == 0 else 'surplus'),
                'per_template': sorted(per_template,
                                       key=lambda p: p['template_id']),
            }
        return out if any_rule else None

    @api.model
    def get_coverage_requirements(self, department_id=False):
        """The rows the coverage drawer edits, most specific scope first."""
        self._require_officer()
        Req = self.env['hr.shift.coverage.requirement']
        dept = int(department_id) if department_id else False
        rows = Req.search([
            ('company_id', 'in', self._pb_company_ids()),
            ('department_id', 'in', ([dept, False] if dept else [False])),
        ])
        weekdays = dict(Req._fields['weekday'].selection)
        return {
            'can_edit': Req._pb_can_edit(),
            'rows': [{
                'id': r.id,
                'department_id': r.department_id.id or False,
                'department_name': r.department_id.name or '',
                'weekday': r.weekday or False,
                'weekday_label': weekdays.get(r.weekday, ''),
                'date': r.date.isoformat() if r.date else False,
                'template_id': r.template_id.id or False,
                'template_name': r.template_id.name or '',
                'required_headcount': r.required_headcount,
                'label': r._pb_label(),
            } for r in rows],
            'weekdays': [{'value': v, 'label': lbl} for v, lbl in
                         Req._fields['weekday'].selection],
        }

    @api.model
    def save_coverage_requirement(self, vals, requirement_id=False):
        """Create or update ONE requirement row. Manager-gated on the model."""
        self._require_officer()
        Req = self.env['hr.shift.coverage.requirement']
        clean = {
            'department_id': int(vals.get('department_id') or 0) or False,
            'weekday': vals.get('weekday') or False,
            'date': vals.get('date') or False,
            'template_id': int(vals.get('template_id') or 0) or False,
            'required_headcount': int(vals.get('required_headcount') or 0),
        }
        if requirement_id:
            row = self._pb_own_requirement(requirement_id)
            if not row:
                # `write()` on an EMPTY recordset is a silent success — an
                # out-of-scope id would look like a saved edit that never
                # happened. A bad request has to say so.
                raise UserError(_(
                    "That coverage requirement is not available in this "
                    "company."))
            row.write(clean)
            return row.id
        clean['company_id'] = (self.env.companies[:1] or self.env.company).id
        return Req.create(clean).id

    @api.model
    def _pb_own_requirement(self, requirement_id):
        """Resolve a requirement id INSIDE the caller's company scope.

        `browse(id)` from an RPC argument is a cross-company door: the manager
        gate on the model asks "may you edit coverage", never "may you edit
        THIS company's coverage", and this model carries no record rule. The
        cockpit only ever offers ids it just sent, so scoping here costs
        nothing and closes the hand-crafted-request case.
        """
        return self.env['hr.shift.coverage.requirement'].search([
            ('id', '=', int(requirement_id)),
            ('company_id', 'in', self._pb_company_ids()),
        ], limit=1)

    @api.model
    def delete_coverage_requirement(self, requirement_id):
        self._require_officer()
        row = self._pb_own_requirement(requirement_id)
        if not row:
            return False
        row.unlink()
        return True

    # --------------------------------------------------------- budget CRUD
    @api.model
    def set_budget(self, week_start_str, department_id, amount):
        """Create or update the budget row for (company, department, week).

        The manager gate lives on the MODEL (`pb.schedule.budget._pb_check_edit`)
        so this facade cannot become a way around it.
        """
        self._require_officer()
        Budget = self.env['pb.schedule.budget']
        week_start = Budget._monday(fields.Date.from_string(week_start_str))
        dept = int(department_id) if department_id else False
        company = self.env.companies[:1] or self.env.company
        existing = Budget.search([
            ('company_id', '=', company.id),
            ('department_id', '=', dept),
            ('week_start', '=', week_start),
        ], limit=1)
        value = float(amount or 0.0)
        if existing:
            existing.write({'amount': value})
            return existing.id
        return Budget.create({
            'company_id': company.id,
            'department_id': dept,
            'week_start': week_start,
            'amount': value,
        }).id

    @api.model
    def clear_budget(self, week_start_str, department_id):
        """Remove the budget row for a scope+week. Returns how many went."""
        self._require_officer()
        Budget = self.env['pb.schedule.budget']
        week_start = Budget._monday(fields.Date.from_string(week_start_str))
        dept = int(department_id) if department_id else False
        rows = Budget.search([
            ('company_id', 'in', self._pb_company_ids()),
            ('department_id', '=', dept),
            ('week_start', '=', week_start),
        ])
        n = len(rows)
        rows.unlink()
        return n

    @api.model
    def _pb_shift_card(self, shift, tmap, has_conflict, tzname=False):
        tmpl = tmap.get(shift.shift_template_id.id) or {}
        # WP-0b: the card prints the EMPLOYEE's wall clock, not the stored UTC.
        tzname = tzname or self._pb_shift_tzname(shift.employee_id or None)
        return {
            'id': shift.id,
            'template_id': shift.shift_template_id.id,
            'template_name': tmpl.get('name', ''),
            'template_code': tmpl.get('code', ''),
            'color': tmpl.get('color', 0),
            'shift_type': tmpl.get('shift_type', ''),
            'start': self._pb_hhmm(shift.start_datetime, tzname),
            'end': self._pb_hhmm(shift.end_datetime, tzname),
            'state': shift.state,
            'planned_hours': round(shift.planned_hours or 0.0, 2),
            'actual_hours': round(shift.actual_hours or 0.0, 2),
            'conflict': bool(has_conflict),
        }
