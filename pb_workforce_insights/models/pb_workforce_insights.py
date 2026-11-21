# -*- coding: utf-8 -*-
"""pb.workforce.insights — the Workforce Analytics cockpit facade (Phase O).

What this replaces
------------------
The "Workforce Analytics" sidebar slot used to hold ``pb_demo``'s 45-line
``pb.demo.analytics``: nine CSS-``div`` bar charts, no filters, no hover, no
drill, no export, a hardcoded ₫ symbol and a hardcoded "Jan–Jul" chart title.
It was injected into the sidebar imperatively by ``pb_demo/hooks.py`` **with no
group restriction**, and — the part that actually mattered — every one of its
SQL slices carried a demo-only equality filter on the employee join, so on any
real customer database it rendered completely empty while looking like a
working feature. (The literal token is deliberately not written here: test 07
greps this module for it.)

Doctrine (identical to pb.insights / pb.explorer)
-------------------------------------------------
* **Read-only.** No create/write/unlink anywhere in this file (asserted at the
  source by ``test_05``).
* **Gate first, then sudo the reads** (C18.17/65/73) — the gate set is broader
  than the underlying ACLs, so the board is collected under ``sudo()`` BEHIND
  ``_require()``.
* **Company scoping survives sudo** (C18.11/18) via ``env.companies``.
* **Soft deps never crash** — attendance, overtime and leave are each probed;
  a missing phase yields ``None`` and the tile says so instead of erroring.
* **Money comes from the FACT TABLES**, never from ``hr_payslip_line``
  (C18.89) — which is also what makes cost-per-head here agree with the
  Explorer to the cent (``test_06`` asserts the parity).
* **No ``is_demo`` filter. Ever.** ``test_07`` greps this module for it.
"""

import logging
import time
from datetime import date, timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

_GATE_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_analytics_user',
    'pb_hr_payroll_base.group_payroll_super_admin',
)

# ---------------------------------------------------------------- bounds
_EMP_SCAN = 2000       # attendance cohort ceiling — SURFACED, never silent
_DRILL_IDS = 400       # ids shipped per drill; the overflow is SURFACED
_DEPT_ROWS = 12        # ranked department rows
_WEEKS = 8             # attendance / overtime trend length

_KIND_LABELS = {
    'missing_punch': 'Missing punch',
    'missing_checkout': 'Open checkout',
    'late': 'Late in',
    'early_leave': 'Early leave',
}
_OT_TYPE_LABELS = {'weekday': 'Weekday', 'weekend': 'Weekend',
                   'holiday': 'Holiday', 'night': 'Night'}


class PbWorkforceInsights(models.AbstractModel):
    _name = 'pb.workforce.insights'
    _description = 'Payobook Workforce Insights — read-only cockpit facade'

    # ------------------------------------------------------------- access
    @api.model
    def _require(self):
        u = self.env.user
        if u.has_group('base.group_system'):
            return
        for g in _GATE_GROUPS:
            try:
                if u.has_group(g):
                    return
            except (ValueError, KeyError):     # group xmlid absent on this DB
                continue
        raise AccessError(_("Workforce Insights is restricted to payroll "
                            "analytics managers."))

    def _co_ids(self):
        return tuple(self.env.companies.ids or [self.env.company.id])

    @staticmethod
    def _safe(fn, default=None):
        try:
            return fn()
        except Exception as e:                  # noqa: BLE001 — board must render
            _logger.warning('Workforce Insights section failed: %s', e)
            return default

    # -------------------------------------------------------------- board
    @api.model
    def get_board(self, months=3, division=None, department_id=None):
        """The whole cockpit in ONE payload."""
        self._require()
        t0 = time.monotonic()
        months = months if months in (1, 3, 6, 12) else 3
        department_id = int(department_id) if department_id else None
        division = division or None
        su = self.sudo()

        today = date.today()
        start = self._window_start(months)
        timings = {}

        def timed(key, fn, default=None):
            t = time.monotonic()
            out = self._safe(fn, default)
            timings[key] = round((time.monotonic() - t) * 1000, 1)
            return out

        scope = {'start': start, 'today': today, 'division': division,
                 'department_id': department_id}

        headcount = timed('headcount', lambda: su._headcount(scope), default={})
        attendance = timed('attendance', lambda: su._attendance(scope))
        overtime = timed('overtime', lambda: su._overtime(scope))
        leave = timed('leave', lambda: su._leave(scope))
        cost = timed('cost', lambda: su._cost_per_head(scope), default={})

        timings['total'] = round((time.monotonic() - t0) * 1000, 1)
        return {
            'currency': self.env.company.currency_id.symbol or '',
            'company': self.env.company.name,
            'months': months,
            'today': today.isoformat(),
            'date_from': start.isoformat(),
            'filters': {'division': division, 'department_id': department_id},
            'options': su._filter_options(),
            'headcount': headcount,
            'attendance': attendance,
            'overtime': overtime,
            'leave': leave,
            'cost': cost,
            'timings': timings,
        }

    @staticmethod
    def _window_start(months):
        first = date.today().replace(day=1)
        y, m = first.year, first.month - (months - 1)
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1)

    # ------------------------------------------------------------ filters
    def _filter_options(self):
        """Values actually present in the facts — never a hardcoded list."""
        out = {'division': [], 'department_id': []}
        self.env.cr.execute(
            "SELECT DISTINCT division FROM pb_fact_line "
            "WHERE company_id IN %s AND division <> ''", (self._co_ids(),))
        out['division'] = [{'value': r[0], 'label': r[0].replace('_', ' ').title()}
                           for r in self.env.cr.fetchall()]
        out['division'].sort(key=lambda x: x['label'])

        self.env.cr.execute(
            "SELECT DISTINCT department_id FROM pb_fact_line "
            "WHERE company_id IN %s AND department_id IS NOT NULL",
            (self._co_ids(),))
        depts = self.env['hr.department'].browse(
            [r[0] for r in self.env.cr.fetchall()]).exists()
        out['department_id'] = sorted(
            [{'value': d.id, 'label': d.display_name} for d in depts],
            key=lambda x: x['label'] or '')
        return out

    def _fact_where(self, scope, alias=''):
        """Shared WHERE for the fact tables. Every value bound."""
        p = ('%s.' % alias) if alias else ''
        clauses = ['%scompany_id IN %%s' % p, '%smonth >= %%s' % p]
        params = [self._co_ids(), scope['start']]
        if scope['division']:
            clauses.append('%sdivision = %%s' % p)
            params.append(scope['division'])
        if scope['department_id']:
            clauses.append('%sdepartment_id = %%s' % p)
            params.append(scope['department_id'])
        return ' AND '.join(clauses), params

    def _employee_scope(self):
        """Employees in scope for the operational (non-payroll) sections."""
        dom = [('company_id', 'in', list(self._co_ids()))]
        return dom

    # ---------------------------------------------------------- headcount
    def _headcount(self, scope):
        """Who was actually PAID, month by month — payroll basis.

        Deliberately not an HR-contract basis: ``departure_date`` is not
        maintained on this data, so an HR-basis leaver count reads zero and
        lies. Paid-this-month/not-paid-last-month is a fact.
        """
        where, params = self._fact_where(scope)
        self.env.cr.execute("""
            SELECT month, COUNT(DISTINCT employee_id)
              FROM pb_fact_emp WHERE %s
             GROUP BY month ORDER BY month
        """ % where, params)
        series = [{'month': str(m), 'label': self._mlabel(m), 'count': int(c or 0)}
                  for m, c in self.env.cr.fetchall()]

        # joiners / leavers between the last two months in the window
        movement = {'joiners': 0, 'leavers': 0, 'matched': 0,
                    'from': '', 'to': '', 'partial': False}
        if len(series) >= 2:
            prev_m, cur_m = series[-2]['month'], series[-1]['month']
            sets = {}
            for key, month in (('prev', prev_m), ('cur', cur_m)):
                self.env.cr.execute(
                    "SELECT DISTINCT employee_id FROM pb_fact_emp "
                    "WHERE %s AND month = %%s" % where, params + [month])
                sets[key] = {r[0] for r in self.env.cr.fetchall()}
            # Is the newest month still running? Comparing a half-finished
            # month against a complete one manufactures thousands of phantom
            # "leavers" — everyone whose run simply has not happened yet. The
            # number is not wrong, it is MEANINGLESS, and presenting it without
            # saying so is the same failure as the legacy 10000% variance.
            month_start = scope['today'].replace(day=1)
            partial = str(cur_m)[:10] == month_start.isoformat()
            movement = {
                'joiners': len(sets['cur'] - sets['prev']),
                'leavers': len(sets['prev'] - sets['cur']),
                'matched': len(sets['cur'] & sets['prev']),
                'joiner_ids': sorted(sets['cur'] - sets['prev'])[:_DRILL_IDS],
                'leaver_ids': sorted(sets['prev'] - sets['cur'])[:_DRILL_IDS],
                'from': series[-2]['label'], 'to': series[-1]['label'],
                'partial': partial,
            }

        # department mix on the newest month in scope
        by_dept = []
        if series:
            self.env.cr.execute("""
                SELECT department_id, COUNT(DISTINCT employee_id)
                  FROM pb_fact_emp WHERE %s AND month = %%s
                 GROUP BY department_id ORDER BY 2 DESC LIMIT %%s
            """ % where, params + [series[-1]['month'], _DEPT_ROWS])
            raw = self.env.cr.fetchall()
            names = {d.id: d.display_name for d in
                     self.env['hr.department'].browse(
                         [r[0] for r in raw if r[0]]).exists()}
            by_dept = [{'id': did, 'name': names.get(did) or _('Unassigned'),
                        'count': int(c or 0)} for did, c in raw]

        return {'series': series, 'movement': movement, 'by_dept': by_dept,
                'latest': series[-1]['count'] if series else 0,
                'basis': 'payroll'}

    @staticmethod
    def _mlabel(m):
        months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
        if isinstance(m, date):
            return '%s %s' % (months[m.month - 1], m.year)
        return str(m)[:7]

    # --------------------------------------------------------- attendance
    def _attendance(self, scope):
        """Exception trend + worst departments. Soft dep on pb_attendance_flow.

        Uses the SAME engine as the Insights pulse, so the two surfaces cannot
        drift apart and disagree about the same week.
        """
        if 'pb.attendance.exception.engine' not in self.env:
            return None
        today = scope['today']
        start = max(scope['start'], today - timedelta(weeks=_WEEKS))
        emps = self._attendance_cohort(scope, start, today)
        if not emps:
            return {'total': 0, 'by_kind': [], 'weeks': [], 'by_dept': [],
                    'employees': 0, 'capped': False,
                    'date_from': start.isoformat(), 'date_to': today.isoformat()}
        capped = len(emps) > _EMP_SCAN
        cohort = self.env['hr.employee'].browse(sorted(emps)[:_EMP_SCAN])
        rows = self.env['pb.attendance.exception.engine']._get_exceptions(
            cohort, start, today)

        kinds, by_week, kind_emp = {}, {}, {}
        for r in rows:
            kind = r.get('kind') or 'other'
            kinds[kind] = kinds.get(kind, 0) + 1
            emp = r.get('employee_id')
            emp = emp[0] if isinstance(emp, (list, tuple)) else emp
            if emp:
                kind_emp.setdefault(kind, set()).add(emp)
            raw = r.get('date')
            day = raw if isinstance(raw, date) else None
            if day is None and raw:
                try:
                    day = date.fromisoformat(str(raw)[:10])
                except ValueError:
                    day = None
            if day:
                monday = day - timedelta(days=day.weekday())
                by_week[monday] = by_week.get(monday, 0) + 1

        weeks = []
        cursor = start - timedelta(days=start.weekday())
        while cursor <= today:
            weeks.append({'week': cursor.isoformat(),
                          'label': cursor.strftime('%d %b'),
                          'count': by_week.get(cursor, 0)})
            cursor += timedelta(days=7)

        dept_of = {e.id: e.department_id for e in cohort}
        dept_counts = {}
        for kind, ids in kind_emp.items():
            for eid in ids:
                dep = dept_of.get(eid)
                key = dep.id if dep else 0
                dept_counts[key] = dept_counts.get(key, 0) + 1
        names = {d.id: d.display_name for d in
                 self.env['hr.department'].browse(
                     [k for k in dept_counts if k]).exists()}
        by_dept = sorted(
            [{'id': k, 'name': names.get(k) or _('Unassigned'), 'count': v}
             for k, v in dept_counts.items()],
            key=lambda r: -r['count'])[:_DEPT_ROWS]

        return {
            'total': len(rows),
            'by_kind': sorted(
                [{'key': k, 'label': _(_KIND_LABELS.get(k, k)), 'count': v,
                  'employee_ids': sorted(kind_emp.get(k, ()))[:_DRILL_IDS],
                  'overflow': max(0, len(kind_emp.get(k, ())) - _DRILL_IDS)}
                 for k, v in kinds.items()], key=lambda r: -r['count']),
            'weeks': weeks, 'by_dept': by_dept,
            'employees': len(cohort), 'capped': capped,
            'date_from': start.isoformat(), 'date_to': today.isoformat(),
        }

    def _attendance_cohort(self, scope, start, today):
        """Employees with a shift or a punch in the window."""
        emp_ids = set()
        dom = self._employee_scope()
        if scope['department_id']:
            dom = dom + [('department_id', '=', scope['department_id'])]
        allowed = set(self.env['hr.employee'].search(dom).ids)
        if 'hr.shift.planning' in self.env:
            for s in self.env['hr.shift.planning'].search_read(
                    [('date', '>=', start), ('date', '<=', today),
                     ('state', '=', 'published')],
                    ['employee_id'], limit=_EMP_SCAN * 4):
                if s['employee_id']:
                    emp_ids.add(s['employee_id'][0])
        for a in self.env['hr.attendance'].search_read(
                [('check_in', '>=', '%s 00:00:00' % start),
                 ('check_in', '<=', '%s 23:59:59' % today)],
                ['employee_id'], limit=_EMP_SCAN * 4):
            if a['employee_id']:
                emp_ids.add(a['employee_id'][0])
        return emp_ids & allowed

    # ----------------------------------------------------------- overtime
    def _overtime(self, scope):
        """OT hours by type and week + ceiling utilisation. Soft dep."""
        if 'hr.overtime.request' not in self.env:
            return None
        OT = self.env['hr.overtime.request']
        today = scope['today']
        start = max(scope['start'], today - timedelta(weeks=_WEEKS))
        dom = [('date', '>=', start), ('date', '<=', today),
               ('state', '=', 'approved'),
               ('employee_id.company_id', 'in', list(self._co_ids()))]
        if scope['department_id']:
            dom.append(('employee_id.department_id', '=', scope['department_id']))

        by_type, total = [], 0.0
        for g in OT.read_group(dom, ['approved_hours:sum'], ['overtime_type']):
            hours = g.get('approved_hours') or 0.0
            total += hours
            by_type.append({'key': g.get('overtime_type') or '',
                            'label': _(_OT_TYPE_LABELS.get(g.get('overtime_type'),
                                                           g.get('overtime_type') or '—')),
                            'hours': round(hours, 2)})
        by_type.sort(key=lambda r: -r['hours'])

        weeks = {}
        has_bonus = 'bonus_hours' in OT._fields
        fields_to_read = ['date', 'approved_hours'] + (
            ['bonus_hours'] if has_bonus else [])
        bonus_total = 0.0
        for rec in OT.search_read(dom, fields_to_read, limit=20000):
            d = rec['date']
            d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
            monday = d - timedelta(days=d.weekday())
            slot = weeks.setdefault(monday, {'approved': 0.0, 'bonus': 0.0})
            slot['approved'] += rec.get('approved_hours') or 0.0
            if has_bonus:
                slot['bonus'] += rec.get('bonus_hours') or 0.0
                bonus_total += rec.get('bonus_hours') or 0.0
        week_series = []
        cursor = start - timedelta(days=start.weekday())
        while cursor <= today:
            slot = weeks.get(cursor, {'approved': 0.0, 'bonus': 0.0})
            week_series.append({'week': cursor.isoformat(),
                                'label': cursor.strftime('%d %b'),
                                'approved': round(slot['approved'], 2),
                                'bonus': round(slot['bonus'], 2)})
            cursor += timedelta(days=7)

        # ceiling utilisation — the ONE limit source is pb.ot.ceiling (C18.55c)
        cap, near, near_ids = 0.0, 0, []
        month_start = today.replace(day=1)
        if 'pb.ot.ceiling' in self.env:
            cap = self.env['pb.ot.ceiling']._for_company(
                self.env.company).monthly_cap or 0.0
        # Utilisation is measured against the employees who ACTUALLY WORKED
        # overtime this month, not the whole payroll. Dividing a handful of
        # hours by (cap x total headcount) always rounds to 0% and tells you
        # nothing — the question is "how close to the limit are the people
        # doing overtime", not "how much overtime could the company legally
        # absorb".
        ot_employees, month_hours = 0, 0.0
        if cap > 0:
            mdom = [d for d in dom if d[0] != 'date']
            mdom += [('date', '>=', month_start), ('date', '<=', today)]
            for g in OT.read_group(mdom, ['approved_hours:sum'], ['employee_id']):
                hours = g.get('approved_hours') or 0.0
                if hours <= 0:
                    continue
                ot_employees += 1
                month_hours += hours
                if hours >= cap * 0.9:
                    near += 1
                    emp = g.get('employee_id')
                    if emp and len(near_ids) < _DRILL_IDS:
                        near_ids.append(emp[0] if isinstance(emp, (list, tuple))
                                        else emp)
        return {'total': round(total, 2), 'by_type': by_type,
                'weeks': week_series, 'bonus_total': round(bonus_total, 2),
                'has_bonus': has_bonus,
                'cap': cap, 'near_cap': near, 'near_cap_ids': near_ids,
                'ot_employees': ot_employees,
                'month_hours': round(month_hours, 2),
                'date_from': start.isoformat(), 'date_to': today.isoformat()}

    # -------------------------------------------------------------- leave
    def _leave(self, scope):
        """Out today, awaiting approval, and absence days by month. Soft dep."""
        if 'hr.leave' not in self.env:
            return None
        Leave = self.env['hr.leave']
        today = scope['today']
        co = [('employee_id.company_id', 'in', list(self._co_ids()))]
        if scope['department_id']:
            co.append(('employee_id.department_id', '=', scope['department_id']))

        out_today = Leave.search(
            co + [('state', '=', 'validate'),
                  ('request_date_from', '<=', today),
                  ('request_date_to', '>=', today)], limit=1000)
        pending = Leave.search_count(
            co + [('state', 'in', ('confirm', 'validate1'))])

        by_type, by_month = [], {}
        taken = Leave.search(
            co + [('state', '=', 'validate'),
                  ('request_date_from', '>=', scope['start'])], limit=20000)
        type_days = {}
        for lv in taken:
            days = lv.number_of_days or 0.0
            name = lv.holiday_status_id.display_name or _('Unspecified')
            type_days[name] = type_days.get(name, 0.0) + days
            anchor = lv.request_date_from
            if anchor:
                key = anchor.replace(day=1)
                by_month[key] = by_month.get(key, 0.0) + days
        by_type = sorted([{'label': k, 'days': round(v, 1)}
                          for k, v in type_days.items()],
                         key=lambda r: -r['days'])[:8]
        months = sorted(by_month)
        return {
            'out_today': len(out_today),
            'out_today_ids': out_today[:_DRILL_IDS].mapped('employee_id').ids,
            'pending': pending,
            'by_type': by_type,
            'by_month': [{'month': m.isoformat(), 'label': self._mlabel(m),
                          'days': round(by_month[m], 1)} for m in months],
            'total_days': round(sum(by_month.values()), 1),
        }

    # ------------------------------------------------------- cost per head
    def _cost_per_head(self, scope):
        """Cost per employee by department, read from the FACT TABLES.

        Same source and same arithmetic as the Analytics Explorer's
        ``cost_per_head`` measure, so the two surfaces agree to the cent —
        ``test_06`` asserts it. Cost and headcount are divided per department,
        never averaged from pre-averaged numbers.
        """
        where, params = self._fact_where(scope)
        self.env.cr.execute("""
            SELECT department_id, SUM(amount)
              FROM pb_fact_line
             WHERE %s AND category_type IN ('basic', 'allowance', 'employer_cost')
             GROUP BY department_id
        """ % where, params)
        cost = {r[0]: float(r[1] or 0.0) for r in self.env.cr.fetchall()}
        self.env.cr.execute("""
            SELECT department_id, COUNT(DISTINCT employee_id)
              FROM pb_fact_emp WHERE %s GROUP BY department_id
        """ % where, params)
        heads = {r[0]: int(r[1] or 0) for r in self.env.cr.fetchall()}

        names = {d.id: d.display_name for d in
                 self.env['hr.department'].browse(
                     [k for k in cost if k]).exists()}
        rows = []
        for did, amount in cost.items():
            n = heads.get(did, 0)
            rows.append({'id': did or 0, 'drillable': bool(did),
                         'name': names.get(did) or _('Unassigned'),
                         'cost': round(amount, 2), 'heads': n,
                         'per_head': round(amount / n, 2) if n else 0.0})
        rows.sort(key=lambda r: -r['per_head'])
        total_cost = sum(cost.values())
        total_heads = sum(heads.values())
        return {'rows': rows[:_DEPT_ROWS],
                'hidden': max(0, len(rows) - _DEPT_ROWS),
                'total_cost': round(total_cost, 2),
                'company_per_head': round(total_cost / total_heads, 2)
                                    if total_heads else 0.0}
