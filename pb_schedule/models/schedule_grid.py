# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``hr.shift.planning.grid`` — P2's ADDITIVE extension of the roster facade.

STRATEGY (P2 §3.2, binding)
---------------------------
The legacy cockpit (`pb_hr_workforce/static/src/js/shift_planning_grid.js`) is
still registered and still works; it is retired by W18, not deleted. So this
file may only ADD methods. `get_grid_data`, `quick_create_shift`, `delete_shift`,
`publish_shifts`, `copy_week`, `get_departments` and `get_job_positions` keep
their exact payload shapes — the old screen consumes them until a later cleanup
phase removes it, and a "small improvement" to one of those dicts would break a
surface nobody is looking at.

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

from odoo import _, api, fields, models

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
    def _pb_shift_window(self, template, shift_date):
        """(start, end) naive datetimes for a template on a day.

        Byte-identical to `quick_create_shift`'s arithmetic (the base facade,
        :229-237) ON PURPOSE: the warning engine must predict exactly the row
        the create would write, or it would warn about a shift nobody is about
        to make. Template hours are wall-clock floats stored naive, which is the
        existing convention for this model and not P2's to change.
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
        return start_dt, end_dt

    @api.model
    def _pb_hhmm(self, dt):
        """"08:00" — 24h, tabular, unambiguous.

        The legacy grid printed `%I:%M%p` ("8am"), which is fine in an English
        roster and unreadable in a Vietnamese one; every other P0–P1 Workforce
        surface prints HH:MM and the strip's numbers line up under it.
        """
        return dt.strftime('%H:%M') if dt else ''

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
        stats = self._pb_stats(days, assigned, employees, week_start,
                               num_days, department_id)
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
    def _pb_stats(self, days, assigned, employees, week_start, num_days,
                  department_id):
        """Per-day hours/cost and the week's budget variance.

        Cost = Σ(planned_hours × rate). Actual cost is only reported for days
        that have already happened: a future day has no actual hours, and
        printing 0 next to a scheduled figure reads as "we spent nothing"
        rather than "this has not happened yet".
        """
        rates = self._pb_rates(employees.ids)
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
            row = Req.browse(int(requirement_id))
            row.write(clean)
            return row.id
        clean['company_id'] = (self.env.companies[:1] or self.env.company).id
        return Req.create(clean).id

    @api.model
    def delete_coverage_requirement(self, requirement_id):
        self._require_officer()
        row = self.env['hr.shift.coverage.requirement'].browse(
            int(requirement_id)).exists()
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
    def _pb_shift_card(self, shift, tmap, has_conflict):
        tmpl = tmap.get(shift.shift_template_id.id) or {}
        return {
            'id': shift.id,
            'template_id': shift.shift_template_id.id,
            'template_name': tmpl.get('name', ''),
            'template_code': tmpl.get('code', ''),
            'color': tmpl.get('color', 0),
            'shift_type': tmpl.get('shift_type', ''),
            'start': self._pb_hhmm(shift.start_datetime),
            'end': self._pb_hhmm(shift.end_datetime),
            'state': shift.state,
            'planned_hours': round(shift.planned_hours or 0.0, 2),
            'actual_hours': round(shift.actual_hours or 0.0, 2),
            'conflict': bool(has_conflict),
        }
