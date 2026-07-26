# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.insights — the executive Analytics cockpit facade (Sudima Phase M).

An AbstractModel (no table) that returns ONE payload for the whole board:
hero + 6-month cost story (from the STORED ``pb_total_*`` run roll-ups), a
payslip-truth department leaderboard, the statutory split, a soft-dep workforce
pulse row, read-only ``payroll.analytics`` snapshots and the report gallery that
replaces the retired ``pb_hr_payroll_analytics`` menu forest.

Doctrine
--------
* **Read-only** (safety rail 1): this module performs ZERO writes. There is no
  ``create``/``write``/``unlink``/``action_*`` anywhere in it — grep-assertable,
  and asserted by ``test_06``.
* **Gate first, then sudo the reads** (C18.65 / C18.73): the gate group set is
  broader than the union of the underlying models' ACLs (C18.75 — the pb_*
  payroll ladder holds no ``hr.payslip`` ACL at all), so the board is collected
  under ``sudo()`` BEHIND ``_require()``. Company scoping survives sudo because
  ``env.companies`` is unchanged, and every SQL statement carries an explicit
  ``company_id IN %s`` (C18.11/18).
* **Soft-deps never crash** (safety rail 3): each pulse tile is model- and
  field-existence checked and returns ``None`` when its phase is not deployed.
* **Performance is a feature** (safety rail 2): hero + trend read the STORED,
  indexed ``pb_total_net/gross`` (``pb_payruns/models/hr_payslip_run.py:87-97``)
  — the old per-run ``read_group`` loop is gone. Every other section is ONE
  bounded SQL/read_group. Per-section timings ride in the payload.
"""

import json
import logging
import time
from datetime import date, timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- access
# The board gate. Deliberately a SUPERSET of the retired analytics menus'
# groups (base_manager | super_admin): the sidebar item that launches this
# cockpit is also visible to `group_payroll_analytics_user`, and a visible
# launcher that always raises AccessError is a bug (C18.9). analytics_manager
# and final_approver both imply base_manager, so three entries cover the ladder.
_GATE_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_analytics_user',
    'pb_hr_payroll_base.group_payroll_super_admin',
)
# The bonus-hours tile carries Phase K's own viewer tier.
_BONUS_GROUPS = (
    'om_hr_payroll.group_hr_payroll_manager',
    'pb_hr_payroll_base.group_payroll_super_admin',
)

# ---------------------------------------------------------------- bounds
_RUN_SCAN = 120          # newest runs scanned before the company filter
_SPARK_RUNS = 12         # hero sparkline length
_DEPT_ROWS = 10          # department leaderboard rows
_TREND_RUNS = 18         # cost-story columns (the overflow is SURFACED, never silent)
_SNAPSHOTS = 8           # payroll.analytics cards
_PULSE_EMPS = 2000       # hard cap on the exception-engine cohort (surfaced)

# Statutory buckets read from `hr.salary.rule.category.category_type`
# (pb_hr_payroll_base/models/hr_payroll_structure_base.py:224) — country
# agnostic, unlike a code list. VN demo: INS -> social_security,
# INSCO/COMP -> employer_cost, TAX -> tax.
_CAT_EMPLOYEE = 'social_security'
_CAT_EMPLOYER = 'employer_cost'
_CAT_TAX = 'tax'
# Legacy fallback for structures whose categories are untyped: the om_hr_payroll
# country-module contribution CODES (what pb_insights read before Phase M).
_LEGACY_CONTRIB_CODES = ['SI_EMP', 'SI_COMP', 'HI_EMP', 'HI_COMP',
                         'UI_EMP', 'UI_COMP']

# Report gallery.
#
# Phase N replaced the thirteen legacy cards. Every one of them was dead:
# hardcoded sample KPIs (hr_analytics_dashboard.py:179-240), twelve chart
# canvases whose JS is commented out of the manifest, statutory totals that can
# never be non-zero (hr_analytics_statutory_contrib.py:244 sums a dict holding
# a string inside a swallowed except), generation that cannot run on Odoo 19
# (:405 reads the removed address_home_id), a compliance flag that is literally
# `return False` (:483), a card pointing at the wrong model, an always-empty
# TransientModel seeded with random.randint, and `bank.export.log`, which has
# no writer ANYWHERE in this repository and is therefore empty by construction.
#
# The gallery now opens the Analytics Explorer on a named LENS — each one a
# live, editable query over the derived fact tables. The `lens` key is passed
# to the cockpit as a context param; entries with an xmlid still resolve the
# classic way, so genuinely useful destinations (the real payslip-line pivot)
# keep their place.
REPORT_LENSES = [
    ('cost', 'Personnel Costs',
     'Total cost of employment by department, month by month', 'wallet'),
    ('statutory', 'Statutory Contributions',
     'Employee and employer contributions and tax withheld', 'shield'),
    ('movement', 'Workforce Movement',
     'Headcount actually paid, by department and period', 'users'),
    ('perhead', 'Cost per Head',
     'Cost per employee by department — the fairest comparison', 'gauge'),
    ('benefits', 'Benefits & Allowances',
     'What the allowance budget is actually spent on', 'heart'),
    ('yoy', 'Year on Year',
     'Total cost of employment across years, by division', 'calendar'),
    ('mix', 'Structure Mix',
     'How gross pay is composed — basic versus everything else', 'layers'),
    ('tax', 'Tax & Deductions',
     'What is withheld, by department and period', 'target'),
    ('components', 'Component Explorer',
     'Every pay component, ranked — the payslip-line pivot, live', 'grid'),
]

# Classic act_window destinations still worth surfacing. Only entries that
# RESOLVE at runtime are shown; an unresolvable xmlid is skipped and logged
# (test 7). `pb_hr_flow.action_hr_payslip_line_analytics` is the richest
# payslip-line pivot in the codebase and previously had ZERO entry points.
REPORT_CANDIDATES = [
    ('pb_hr_flow.action_hr_payslip_line_analytics',
     'Payslip Line Pivot', 'Pivot every payslip line by component', 'grid'),
    ('payroll_analytics_approval.action_payroll_analytics_comparison',
     'Period Comparison', 'Month-over-month component comparison', 'trending'),
]


class PbInsights(models.AbstractModel):
    _name = 'pb.insights'
    _description = 'Payobook Insights — executive analytics cockpit'

    # ------------------------------------------------------------- access
    @api.model
    def _require(self):
        """First line of every public method. Raises for anyone outside the
        analytics tier (the launcher is hidden from them by the sidebar item's
        own groups — this is the enforcement, C18.9)."""
        u = self.env.user
        if u.has_group('base.group_system'):
            return
        for g in _GATE_GROUPS:
            try:
                if u.has_group(g):
                    return
            except (ValueError, KeyError):     # group xmlid absent on this DB
                continue
        raise AccessError(_("Insights is restricted to payroll analytics managers."))

    @api.model
    def _can_bonus(self):
        """Phase-K bonus-hours viewer tier (mirrors the Bonus review surface)."""
        u = self.env.user
        if u.has_group('base.group_system'):
            return True
        for g in _BONUS_GROUPS:
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    # ------------------------------------------------------------ helpers
    def _co_ids(self):
        """Every SELECTED company (C18.11/18 — render them all)."""
        return tuple(self.env.companies.ids or [self.env.company.id])

    @staticmethod
    def _safe(fn, default=None):
        try:
            return fn()
        except Exception as e:                      # noqa: BLE001 - board must render
            _logger.warning("Insights section failed: %s", e)
            return default

    def _runs(self, date_from=None, limit=None):
        """Company-scoped payslip runs, newest first.

        ``hr.payslip.run`` has NO ``company_id`` in this om_hr_payroll
        (C18.43) — the pre-Phase-M code searched one and silently swallowed the
        ValueError, so the whole 'latest run' branch was dead. Scope through the
        run's PAYSLIPS instead, with one indexed lookup on the scanned window.
        """
        Run = self.env['hr.payslip.run']
        dom = [('date_end', '>=', date_from)] if date_from else []
        runs = Run.search(dom, order='date_end desc, id desc', limit=_RUN_SCAN)
        if not runs:
            return Run
        self.env.cr.execute(
            "SELECT DISTINCT payslip_run_id FROM hr_payslip "
            "WHERE payslip_run_id IN %s AND company_id IN %s AND state != 'cancel'",
            (tuple(runs.ids), self._co_ids()))
        allowed = {r[0] for r in self.env.cr.fetchall()}
        runs = runs.filtered(lambda r: r.id in allowed)
        return runs[:limit] if limit else runs

    def _employer_cost(self, run_ids):
        """{run_id: employer contribution total} — ONE bounded SQL.

        Deliberately called for the HERO RUN ONLY (and therefore for a single
        run's payslips, which the ``payslip_run_id`` / ``slip_id`` indexes serve
        in ~40 ms). There is no stored per-run employer total: pb_payruns rolls
        up NET/GROSS/DED only, and the employer categories (INSCO / COMP) are
        not in its bucket list. Measured on the live demo world (2026-07-25,
        711k payslip lines): 1 run 40 ms · 6 runs 1.28 s · 39 runs (a 6-month
        window = every payslip in the database) 11.3 s, and NO index fixes the
        39-run case — it is a full-table aggregate by definition (a
        (category_id, slip_id) index was built and measured: still 10.5 s, the
        planner correctly keeps the sequential scan).

        That is why the cost story below charts NET and GROSS from the STORED
        roll-ups and shows total cost on the hero only. Making it a third
        per-run SERIES needs a stored ``pb_total_employer`` on
        ``hr.payslip.run`` — one extra CASE arm in the roll-up SQL that
        pb_payruns already runs, so effectively free — but a new stored field
        is an explicit Phase-M non-goal. Reported, not smuggled in (C18.68).
        """
        if not run_ids:
            return {}
        self.env.cr.execute("""
            SELECT p.payslip_run_id, COALESCE(SUM(pl.total), 0)
            FROM hr_payslip_line pl
            JOIN hr_payslip p ON p.id = pl.slip_id AND p.state != 'cancel'
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE p.payslip_run_id IN %s AND p.company_id IN %s
              AND c.category_type = %s
            GROUP BY p.payslip_run_id
        """, (tuple(run_ids), self._co_ids(), _CAT_EMPLOYER))
        return {rid: abs(total or 0.0) for rid, total in self.env.cr.fetchall()}

    def _dept_source(self):
        """SQL fragment resolving an employee's department, or None.

        ``hr.employee.department_id`` is a NON-STORED delegate of ``hr.version``
        in Odoo 19 (C18.56) — there is no such column on ``hr_employee`` on this
        server. The stored anchor is ``hr_employee.current_version_id``. Probe
        the FIELD (not the column: a legacy DB may keep a dead column).
        """
        Emp = self.env['hr.employee']
        f = Emp._fields.get('department_id')
        if f is not None and f.store:
            return 'e.department_id'
        cur = Emp._fields.get('current_version_id')
        if cur is not None and cur.store and 'hr.version' in self.env:
            return 'v.department_id'
        return None

    # Run-state chips. Translated at read time (the dict is a module-level
    # constant, so `_()` here would freeze the language at import).
    _STATE_LABELS = {
        'draft': 'Draft', 'level0': 'Officer', 'level1': 'HR',
        'level2': 'Finance', 'done': 'Approved', 'cancel': 'Rejected',
    }

    def _run_point(self, run, employer=None):
        """One chart point from the STORED roll-ups.

        ``employer``/``cost`` are None unless an employer-cost map is supplied
        (hero only — see _employer_cost). They are NEVER silently equal to
        gross: a consumer that reads `cost` must be able to tell "not computed"
        from "no employer contributions".
        """
        name = run.name or ''
        gross = run.pb_total_gross or 0.0
        employer_total = employer.get(run.id, 0.0) if employer is not None else None
        return {
            'id': run.id,
            'name': name,
            'label': name if len(name) <= 26 else (name[:25] + '…'),
            'date': str(run.date_end or run.date_start or ''),
            'net': run.pb_total_net or 0.0,
            'gross': gross,
            'employer': employer_total,
            'cost': None if employer_total is None else gross + employer_total,
            'count': run.pb_employee_count or 0,
            'state': run.state or 'draft',
            'state_label': _(self._STATE_LABELS.get(run.state or 'draft', run.state or '')),
        }

    # -------------------------------------------------------------- board
    @api.model
    def get_insights(self, months=6):
        """The whole board in ONE payload. Read-only.

        ``months`` bounds the cost story window (3 / 6 / 12).
        """
        self._require()               # real-user gate…
        su = self.sudo()              # …then collect the board sudo (C18.65/73)
        try:
            months = max(1, min(24, int(months or 6)))
        except (TypeError, ValueError):
            months = 6

        t0 = time.monotonic()
        timings = {}

        def timed(key, fn, default=None):
            t = time.monotonic()
            out = su._safe(fn, default)
            timings[key] = round((time.monotonic() - t) * 1000, 1)
            return out

        window = su._window_start(months)
        # ONE company-scoped run read serves hero, sparkline, trend and the
        # department basis — newest first (test 2: the query count does not grow
        # with the number of runs in the window).
        runs = timed('runs', lambda: su._runs(), default=su.env['hr.payslip.run'])
        in_window = runs.filtered(
            lambda r: r.date_end and r.date_end >= window)
        # the hero run is the newest company-scoped run — it stands even when
        # the window itself is empty (a quiet quarter still gets a headline)
        latest = runs[:1]

        hero = timed('hero', lambda: su._hero(runs), default={})
        trend = timed('trend', lambda: su._trend(in_window, months), default={})
        departments = timed('departments', lambda: su._departments(runs), default={})
        statutory = timed('statutory', lambda: su._statutory(latest), default={})
        pulse = timed('pulse', lambda: su._pulse(), default={})
        snapshots = timed('snapshots', lambda: su._snapshots(), default=[])
        reports = timed('reports', lambda: su._reports(), default=[])

        company = self.env.company
        timings['total'] = round((time.monotonic() - t0) * 1000, 1)
        return {
            'currency': company.currency_id.symbol or '',
            'company': company.name,
            'companies': self.env.companies.mapped('name'),
            'months': months,
            'today': date.today().isoformat(),
            'can_bonus': su._can_bonus(),
            'hero': hero,
            'trend': trend,
            'departments': departments,
            'statutory': statutory,
            'pulse': pulse,
            'snapshots': snapshots,
            'reports': reports,
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

    # --------------------------------------------------------------- hero
    def _hero(self, runs):
        """Headline NET + delta vs the previous run + a 12-run sparkline.

        Every figure is a STORED roll-up read (``pb_total_*``) — no payslip-line
        aggregation happens here (test 2 asserts the query count stays flat).
        """
        spark = [{'label': (r.name or '')[:22], 'date': str(r.date_end or ''),
                  'net': r.pb_total_net or 0.0}
                 for r in reversed(runs[:_SPARK_RUNS])]
        headcount = self.env['hr.employee'].search_count(
            [('company_id', 'in', list(self._co_ids())), ('active', '=', True)])

        out = {
            'run_name': '', 'run_state': '', 'run_state_label': '',
            'run_date': '', 'net': 0.0, 'gross': 0.0, 'employees_paid': 0,
            'delta_pct': None, 'month': '', 'month_net': 0.0,
            'prev_month': '', 'prev_month_net': 0.0,
            'avg_cost': 0.0, 'employer_total': 0.0,
            'headcount': headcount, 'spark': spark,
        }
        if not runs:
            return out
        run = runs[0]
        employer = self._employer_cost(run.ids)
        point = self._run_point(run, employer)
        out.update({
            'run_id': run.id,
            'run_name': point['name'], 'run_state': point['state'],
            'run_state_label': point['state_label'], 'run_date': point['date'],
            'net': point['net'], 'gross': point['gross'],
            'employees_paid': point['count'],
            'employer_total': point['employer'],
            'avg_cost': (point['cost'] / point['count']) if point['count'] else 0.0,
        })
        # Month-over-month, not run-over-run. Consecutive runs are different
        # DIVISIONS and different cycles here (a 900-slip end run next to a
        # 40-slip mid-cycle advance), so a run-to-run delta reads +2270% and
        # means nothing. The month totals are summed from the same STORED
        # roll-ups already in memory — zero extra queries — and the UI prints
        # both months and both figures, so the number is traceable.
        by_month = {}
        for r in runs:
            ref = r.date_end or r.date_start
            if ref:
                key = (ref.year, ref.month)
                by_month[key] = by_month.get(key, 0.0) + (r.pb_total_net or 0.0)
        ref = run.date_end or run.date_start
        if ref:
            cur = (ref.year, ref.month)
            prev = (cur[0] - 1, 12) if cur[1] == 1 else (cur[0], cur[1] - 1)
            cur_total = by_month.get(cur, 0.0)
            prev_total = by_month.get(prev, 0.0)
            out['month'] = date(cur[0], cur[1], 1).isoformat()
            out['prev_month'] = date(prev[0], prev[1], 1).isoformat()
            out['month_net'] = cur_total
            out['prev_month_net'] = prev_total
            if prev_total:
                out['delta_pct'] = round(
                    (cur_total - prev_total) / abs(prev_total) * 100.0, 1)
        return out

    # -------------------------------------------------------------- trend
    def _trend(self, runs, months):
        """The cost story: NET and GROSS per run, straight off the STORED
        roll-ups — ZERO queries beyond the single run read (safety rail 2).

        The newest ``_TREND_RUNS`` runs of the window are charted; anything
        beyond that is reported in ``hidden`` so the UI can say so out loud
        (a silent top-N reads as "everything", which it is not).
        """
        shown = runs[:_TREND_RUNS]              # newest first…
        ordered = list(reversed(shown))         # …oldest -> newest for the chart
        points = [self._run_point(r) for r in ordered]
        peak = max([p['gross'] for p in points], default=0.0)
        return {
            'points': points,
            'max': peak or 1.0,
            'months': months,
            'window_from': self._window_start(months).isoformat(),
            'hidden': max(0, len(runs) - len(shown)),
            'scanned': len(runs),
            'totals': {
                'net': sum(p['net'] for p in points),
                'gross': sum(p['gross'] for p in points),
                'runs': len(points),
            },
        }

    # -------------------------------------------------------- departments
    def _departments(self, runs):
        """NET by department for the latest DONE run (payslip truth).

        Falls back to the open-contract wage read_group when no done run exists
        — flagged ``approx: True`` so the UI can badge it.
        """
        done = runs.filtered(lambda r: r.state == 'done')[:1]
        col = self._dept_source()
        if done and col:
            run = done[0]
            join = ('LEFT JOIN hr_version v ON v.id = e.current_version_id'
                    if col.startswith('v.') else '')
            self.env.cr.execute("""
                SELECT {col} AS dept_id,
                       COUNT(DISTINCT p.employee_id) AS headcount,
                       COALESCE(SUM(pl.total), 0) AS net
                FROM hr_payslip_line pl
                JOIN hr_payslip p ON p.id = pl.slip_id AND p.state != 'cancel'
                JOIN hr_salary_rule_category c ON c.id = pl.category_id
                JOIN hr_employee e ON e.id = p.employee_id
                {join}
                WHERE p.payslip_run_id = %s AND p.company_id IN %s
                  AND c.code = 'NET'
                GROUP BY 1
            """.format(col=col, join=join), (run.id, self._co_ids()))
            raw = self.env.cr.fetchall()
            names = {}
            dept_ids = [r[0] for r in raw if r[0]]
            if dept_ids:
                # department names are translated (jsonb) — read them through
                # the ORM rather than picking a language out of SQL
                for d in self.env['hr.department'].browse(dept_ids).exists():
                    names[d.id] = d.name
            rows = [{
                'id': did or 0,
                'name': names.get(did) or _('Unassigned'),
                'net': float(net or 0.0),
                'count': int(head or 0),
                'per_head': (float(net or 0.0) / head) if head else 0.0,
            } for did, head, net in raw]
            rows.sort(key=lambda r: -r['net'])
            top = rows[:_DEPT_ROWS]
            return {
                'rows': top,
                'max': max([r['net'] for r in top], default=0.0) or 1.0,
                'max_head': max([r['per_head'] for r in top], default=0.0) or 1.0,
                'approx': False,
                'basis': 'payslip',
                'run_name': run.name or '',
                'total': sum(r['net'] for r in rows),
                'hidden': max(0, len(rows) - len(top)),
            }
        return self._departments_approx()

    def _departments_approx(self):
        """Contract-wage approximation — the pre-Phase-M basis, kept as the
        no-done-run fallback and BADGED as approximate in the UI."""
        dom = [('company_id', 'in', list(self._co_ids())), ('state', '=', 'open')]
        rows = []
        for g in self.env['hr.contract'].read_group(dom, ['wage:sum'], ['department_id']):
            dep = g.get('department_id')
            count = g.get('department_id_count') or g.get('__count') or 0
            wage = g.get('wage') or 0.0
            rows.append({
                'id': dep[0] if dep else 0,
                'name': dep[1] if dep else _('Unassigned'),
                'net': wage, 'count': count,
                'per_head': (wage / count) if count else 0.0,
            })
        rows.sort(key=lambda r: -r['net'])
        top = rows[:_DEPT_ROWS]
        return {
            'rows': top,
            'max': max([r['net'] for r in top], default=0.0) or 1.0,
            'max_head': max([r['per_head'] for r in top], default=0.0) or 1.0,
            'approx': True,
            'basis': 'contract',
            'run_name': '',
            'total': sum(r['net'] for r in rows),
            'hidden': max(0, len(rows) - len(top)),
        }

    # ---------------------------------------------------------- statutory
    def _statutory(self, latest):
        """Employee vs employer contribution split for the latest run."""
        out = {'employee': 0.0, 'employer': 0.0, 'tax': 0.0, 'total': 0.0,
               'rows': [], 'run_name': '', 'basis': 'category'}
        if not latest:
            return out
        run = latest[0]
        out['run_name'] = run.name or ''
        self.env.cr.execute("""
            SELECT c.category_type, pl.code, COALESCE(SUM(pl.total), 0)
            FROM hr_payslip_line pl
            JOIN hr_payslip p ON p.id = pl.slip_id AND p.state != 'cancel'
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE p.payslip_run_id = %s AND p.company_id IN %s
              AND c.category_type IN %s
            GROUP BY 1, 2
        """, (run.id, self._co_ids(), (_CAT_EMPLOYEE, _CAT_EMPLOYER, _CAT_TAX)))
        raw = self.env.cr.fetchall()
        if not raw:
            return self._statutory_legacy(run, out)
        legs = {_CAT_EMPLOYEE: 'employee', _CAT_EMPLOYER: 'employer', _CAT_TAX: 'tax'}
        for cat, code, total in raw:
            leg = legs.get(cat)
            amount = abs(total or 0.0)
            if not leg or not amount:
                continue
            out[leg] += amount
            out['rows'].append({'code': code or '—', 'leg': leg, 'amount': amount})
        out['rows'].sort(key=lambda r: -r['amount'])
        out['total'] = out['employee'] + out['employer']
        return out

    def _statutory_legacy(self, run, out):
        """Untyped-category fallback: the om_hr_payroll country-module CODES."""
        out['basis'] = 'code'
        groups = self.env['hr.payslip.line'].read_group(
            [('slip_id.payslip_run_id', '=', run.id),
             ('code', 'in', _LEGACY_CONTRIB_CODES)], ['total:sum'], ['code'])
        for g in groups:
            code = g.get('code') or ''
            amount = abs(g.get('total') or 0.0)
            if not amount:
                continue
            leg = 'employee' if code.endswith('_EMP') else 'employer'
            out[leg] += amount
            out['rows'].append({'code': code, 'leg': leg, 'amount': amount})
        out['rows'].sort(key=lambda r: -r['amount'])
        out['total'] = out['employee'] + out['employer']
        return out

    # -------------------------------------------------------------- pulse
    def _pulse(self):
        """Workforce pulse row — every tile soft-dep gated (safety rail 3).

        A tile is ``None`` when its phase is not deployed; the UI renders a
        quiet "not installed" ghost rather than a gap.
        """
        return {
            'attendance': self._safe(self._pulse_attendance),
            'leave': self._safe(self._pulse_leave),
            'ot': self._safe(self._pulse_ot),
            'bonus': self._safe(self._pulse_bonus),
        }

    def _pulse_attendance(self):
        """This-week exception counts by kind (Phase G engine)."""
        if 'pb.attendance.exception.engine' not in self.env:
            return None
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        co_ids = list(self._co_ids())
        # Bound the cohort to employees who CAN produce an exception this week:
        # every row the engine emits originates from a published shift or from
        # an attendance in the window (attendance_exception.py:146-190), so this
        # is the same answer for a fraction of the work on a 4.5k-employee world.
        emp_ids = set()
        if 'hr.shift.planning' in self.env:
            shifts = self.env['hr.shift.planning'].search_read(
                [('date', '>=', monday), ('date', '<=', today),
                 ('state', '=', 'published'),
                 ('employee_id.company_id', 'in', co_ids)],
                ['employee_id'], limit=_PULSE_EMPS * 4)
            emp_ids |= {s['employee_id'][0] for s in shifts if s['employee_id']}
        atts = self.env['hr.attendance'].search_read(
            [('check_in', '>=', '%s 00:00:00' % (monday - timedelta(days=1))),
             ('check_in', '<=', '%s 23:59:59' % today),
             ('employee_id.company_id', 'in', co_ids)],
            ['employee_id'], limit=_PULSE_EMPS * 4)
        emp_ids |= {a['employee_id'][0] for a in atts if a['employee_id']}
        capped = len(emp_ids) > _PULSE_EMPS
        employees = self.env['hr.employee'].browse(sorted(emp_ids)[:_PULSE_EMPS])
        rows = self.env['pb.attendance.exception.engine'].get_exceptions(
            employees, monday, today) if employees else []
        kinds = {'missing_punch': 0, 'missing_checkout': 0, 'late': 0, 'early_leave': 0}
        for r in rows:
            if r.get('kind') in kinds:
                kinds[r['kind']] += 1
        return {
            'total': len(rows), 'kinds': kinds, 'employees': len(employees),
            'date_from': monday.isoformat(), 'date_to': today.isoformat(),
            'capped': capped,
        }

    def _pulse_leave(self):
        """On leave today + waiting on an approval decision."""
        if 'hr.leave' not in self.env:
            return None
        Leave = self.env['hr.leave']
        today = date.today()
        co = [('employee_id.company_id', 'in', list(self._co_ids()))]
        out_today = Leave.search(
            co + [('state', '=', 'validate'),
                  ('request_date_from', '<=', today),
                  ('request_date_to', '>=', today)], limit=200)
        pending = Leave.search_count(
            co + [('state', 'in', ('confirm', 'validate1'))])
        cards = [{'id': lv.employee_id.id, 'name': lv.employee_id.name,
                  'avatar_url': '/web/image/hr.employee/%s/avatar_128' % lv.employee_id.id}
                 for lv in out_today[:8]]
        return {'out_today': len(out_today), 'pending': pending, 'cards': cards,
                'overflow': max(0, len(out_today) - len(cards))}

    def _month_bounds(self):
        today = date.today()
        start = today.replace(day=1)
        end = (date(today.year + 1, 1, 1) if today.month == 12
               else date(today.year, today.month + 1, 1)) - timedelta(days=1)
        return start, end, today

    _OT_TYPE_LABELS = {'weekday': 'Weekday', 'weekend': 'Weekend',
                       'holiday': 'Holiday', 'night': 'Night'}

    def _pulse_ot(self):
        """MTD approved OT by type + employees near their monthly ceiling."""
        if 'hr.overtime.request' not in self.env:
            return None
        OT = self.env['hr.overtime.request']
        start, end, _today = self._month_bounds()
        dom = [('date', '>=', start), ('date', '<=', end),
               ('state', '=', 'approved'),
               ('employee_id.company_id', 'in', list(self._co_ids()))]
        by_type = []
        total = 0.0
        for g in OT.read_group(dom, ['approved_hours:sum'], ['overtime_type']):
            hours = g.get('approved_hours') or 0.0
            total += hours
            by_type.append({
                'key': g.get('overtime_type') or '',
                'label': self._OT_TYPE_LABELS.get(g.get('overtime_type'),
                                                  g.get('overtime_type') or '—'),
                'hours': round(hours, 2),
            })
        by_type.sort(key=lambda r: -r['hours'])

        # near-ceiling: per-employee MTD vs the company monthly cap. The cap is
        # the ONE limit source, pb.ot.ceiling (C18.55c); 0 == not enforced.
        near, cap = 0, 0.0
        per_emp = OT.read_group(dom, ['approved_hours:sum'], ['employee_id'])
        if 'pb.ot.ceiling' in self.env:
            cap = self.env['pb.ot.ceiling']._for_company(self.env.company).monthly_cap or 0.0
            if cap > 0:
                near = sum(1 for g in per_emp
                           if (g.get('approved_hours') or 0.0) >= cap * 0.9)
        return {'total': round(total, 2), 'by_type': by_type[:4],
                'cap': cap, 'near_cap': near, 'employees': len(per_emp),
                'date_from': start.isoformat(), 'date_to': end.isoformat()}

    def _pulse_bonus(self):
        """MTD bonus hours (Phase K). Present only when the viewer holds the
        payroll-manager tier AND the field exists on this deployment."""
        if 'hr.overtime.request' not in self.env:
            return None
        OT = self.env['hr.overtime.request']
        if 'bonus_hours' not in OT._fields:
            return None                        # pre-Phase-K server
        if not self._can_bonus():
            return None                        # gated out for this viewer
        start, end, _today = self._month_bounds()
        dom = [('date', '>=', start), ('date', '<=', end),
               ('state', '=', 'approved'),
               ('employee_id.company_id', 'in', list(self._co_ids())),
               ('bonus_hours', '>', 0)]
        groups = OT.read_group(dom, ['bonus_hours:sum'], [])
        hours = (groups and groups[0].get('bonus_hours')) or 0.0
        return {'hours': round(hours, 2),
                'requests': OT.search_count(dom),
                'date_from': start.isoformat(), 'date_to': end.isoformat()}

    # ---------------------------------------------------------- snapshots
    _SNAP_STATES = {'draft': 'Draft', 'ready': 'Ready for approval',
                    'approved': 'Approved', 'exported': 'Exported'}

    def _snapshots(self):
        """Latest ``payroll.analytics`` rows — READ ONLY.

        The model's own queries are not company-scoped (a known risk documented
        in the handover §2); the filter is applied HERE: a snapshot is shown
        when its payslip batch belongs to a selected company, or — for the
        legacy rows that carry no batch — when a selected company actually ran
        payroll over the same period.
        """
        if 'payroll.analytics' not in self.env:
            return []
        rows = self.env['payroll.analytics'].search(
            [], order='date_from desc, id desc', limit=_SNAPSHOTS * 3)
        if not rows:
            return []
        run_ids = [r.payslip_run_id.id for r in rows if r.payslip_run_id]
        allowed_runs = set()
        if run_ids:
            self.env.cr.execute(
                "SELECT DISTINCT payslip_run_id FROM hr_payslip "
                "WHERE payslip_run_id IN %s AND company_id IN %s",
                (tuple(run_ids), self._co_ids()))
            allowed_runs = {r[0] for r in self.env.cr.fetchall()}
        orphan_periods = set()
        orphan_dates = [r.date_from for r in rows
                        if not r.payslip_run_id and r.date_from]
        if orphan_dates:
            self.env.cr.execute(
                "SELECT DISTINCT date_from FROM hr_payslip "
                "WHERE company_id IN %s AND date_from IN %s",
                (self._co_ids(), tuple(orphan_dates)))
            orphan_periods = {r[0] for r in self.env.cr.fetchall()}

        out = []
        for rec in rows:
            if rec.payslip_run_id:
                if rec.payslip_run_id.id not in allowed_runs:
                    continue
            elif not (rec.date_from and rec.date_from in orphan_periods):
                continue
            anomalies = 0
            if rec.anomaly_alerts:
                try:
                    parsed = json.loads(rec.anomaly_alerts)
                    anomalies = len(parsed) if isinstance(parsed, (list, tuple)) \
                        else len(parsed.get('alerts', []) or [])
                except (ValueError, TypeError, AttributeError):
                    anomalies = 0
            out.append({
                'id': rec.id,
                'period': rec.period_name or '—',
                'country': rec.country or '',
                'state': rec.state or 'draft',
                'state_label': _(self._SNAP_STATES.get(rec.state or 'draft', rec.state or '')),
                'date_from': str(rec.date_from or ''),
                'date_to': str(rec.date_to or ''),
                'employees': rec.total_employees or 0,
                'total': rec.total_payroll or 0.0,
                'variance': rec.variance_percentage or 0.0,
                'anomalies': anomalies,
                'run_name': rec.payslip_run_id.name if rec.payslip_run_id else '',
                'structure': rec.salary_structure_name or '',
            })
            if len(out) >= _SNAPSHOTS:
                break
        return out

    # ------------------------------------------------------------ reports
    def _reports(self):
        """Resolve the gallery.

        Lens cards come first — they open the Analytics Explorer on a live,
        editable query. Classic act_window destinations follow, and only if
        they actually resolve on this database.
        """
        out = []
        explorer = self.env.ref('pb_explorer.action_pb_explorer',
                                raise_if_not_found=False)
        if explorer:
            for lens, label, desc, icon in REPORT_LENSES:
                out.append({'xmlid': 'pb_explorer.action_pb_explorer',
                            'lens': lens, 'label': _(label), 'desc': _(desc),
                            'icon': icon})
        for xmlid, label, desc, icon in REPORT_CANDIDATES:
            action = self.env.ref(xmlid, raise_if_not_found=False)
            if not action:
                _logger.info("Insights: report action %s is not installed — "
                             "skipped from the gallery.", xmlid)
                continue
            # _(<variable>) is not auto-extractable, but the runtime lookup is
            # by VALUE — the i18n/vi_VN.po ships each of these msgids.
            out.append({'xmlid': xmlid, 'label': _(label), 'desc': _(desc),
                        'icon': icon})
        return out

    # ----------------------------------------------------- back-compat RPC
    @api.model
    def get_insights_data(self):
        """Pre-Phase-M entry point, kept so a stale browser bundle still
        renders instead of erroring. Returns the new payload."""
        return self.get_insights()
