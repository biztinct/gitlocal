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
from odoo.exceptions import AccessError, UserError

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
_DRILL_IDS = 400         # ids shipped for a tile drill; the overflow is SURFACED

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

# Phase O retired the report GALLERY that used to live here.
#
# Phase N had replaced thirteen legacy cards with nine Explorer lens cards.
# Those nine turned out to be a verbatim copy of the Explorer's own lens grid,
# so the board shipped a duplicate menu while every real number on it was
# unclickable. Drill-through replaced the gallery entirely (see ``_explorer``),
# and the two genuinely useful classic destinations it also carried — the
# pb_hr_flow payslip-line pivot and Period Comparison — moved into
# ``pb_explorer._classic`` so nothing lost its route.


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
        explorer = timed('explorer', lambda: su._explorer(),
                         default={'available': False, 'xmlid': ''})

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
            'explorer': explorer,
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
                # Employees with no department resolve to id 0, which is falsy
                # — the old drill early-returned on it, so the row looked
                # clickable and silently did nothing. Marked explicitly so the
                # UI can render it inert instead of lying.
                'drillable': bool(did),
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
                'run_id': run.id,
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
                'drillable': bool(dep),
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
               'rows': [], 'run_name': '', 'basis': 'category',
               'run_id': False, 'month': ''}
        if not latest:
            return out
        run = latest[0]
        out['run_name'] = run.name or ''
        # Drill keys: which run these figures belong to, so a click on an arc,
        # a legend row or a code chip can open that exact question.
        out['run_id'] = run.id
        anchor = run.date_start or run.date_end
        out['month'] = anchor.replace(day=1).isoformat() if anchor else ''
        out['legs'] = {'employee': _CAT_EMPLOYEE, 'employer': _CAT_EMPLOYER,
                       'tax': _CAT_TAX}
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
            out['rows'].append({'code': code or '—', 'leg': leg,
                                'amount': amount, 'category_type': cat})
        out['rows'].sort(key=lambda r: -r['amount'])
        out['total'] = out['employee'] + out['employer']
        # The template shows the first 8 chips; say how many are hidden rather
        # than letting codes 9+ vanish without a trace.
        out['rows_hidden'] = max(0, len(out['rows']) - 8)
        return out

    def _statutory_legacy(self, run, out):
        """Untyped-category fallback: the om_hr_payroll country-module CODES.
        Same scope as the primary SQL (review M-1): selected companies only,
        cancelled slips excluded."""
        out['basis'] = 'code'
        groups = self.env['hr.payslip.line'].read_group(
            [('slip_id.payslip_run_id', '=', run.id),
             ('slip_id.company_id', 'in', list(self._co_ids())),
             ('slip_id.state', '!=', 'cancel'),
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
        rows = self.env['pb.attendance.exception.engine']._get_exceptions(
            employees, monday, today) if employees else []
        kinds = {'missing_punch': 0, 'missing_checkout': 0, 'late': 0, 'early_leave': 0}
        # Per-DAY counts drive the tile's micro-chart, and the employee ids
        # behind each kind make the tile drillable. Both used to be thrown
        # away one line after the engine returned them (Phase N audit), which
        # is why every pulse tile was a dead click target.
        by_day = {}
        kind_emp = {k: set() for k in kinds}
        for r in rows:
            kind = r.get('kind')
            if kind in kinds:
                kinds[kind] += 1
                emp = r.get('employee_id')
                if emp:
                    kind_emp[kind].add(emp[0] if isinstance(emp, (list, tuple)) else emp)
            day = str(r.get('date') or '')[:10]
            if day:
                by_day[day] = by_day.get(day, 0) + 1
        span = []
        cursor = monday
        while cursor <= today:
            iso = cursor.isoformat()
            span.append({'date': iso, 'count': by_day.get(iso, 0),
                         'dow': cursor.strftime('%a')})
            cursor += timedelta(days=1)
        return {
            'total': len(rows), 'kinds': kinds, 'employees': len(employees),
            'date_from': monday.isoformat(), 'date_to': today.isoformat(),
            'capped': capped, 'by_day': span,
            # capped at the drill page size — the cap is surfaced, never silent
            'kind_employees': {k: sorted(v)[:_DRILL_IDS] for k, v in kind_emp.items()},
            'kind_overflow': {k: max(0, len(v) - _DRILL_IDS)
                              for k, v in kind_emp.items()},
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
                  'leave_id': lv.id,
                  'avatar_url': '/web/image/hr.employee/%s/avatar_128' % lv.employee_id.id}
                 for lv in out_today[:8]]
        # A 14-day out-of-office density strip for the tile's micro-chart.
        horizon = today + timedelta(days=13)
        upcoming = Leave.search(
            co + [('state', '=', 'validate'),
                  ('request_date_from', '<=', horizon),
                  ('request_date_to', '>=', today)], limit=1000)
        density = []
        for offset in range(14):
            day = today + timedelta(days=offset)
            density.append({
                'date': day.isoformat(), 'dow': day.strftime('%a')[0],
                'count': sum(1 for lv in upcoming
                             if lv.request_date_from and lv.request_date_to
                             and lv.request_date_from <= day <= lv.request_date_to),
            })
        return {'out_today': len(out_today), 'pending': pending, 'cards': cards,
                'overflow': max(0, len(out_today) - len(cards)),
                'out_today_ids': out_today[:_DRILL_IDS].ids,
                'density': density}

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
        near_ids = []
        per_emp = OT.read_group(dom, ['approved_hours:sum'], ['employee_id'])
        if 'pb.ot.ceiling' in self.env:
            cap = self.env['pb.ot.ceiling']._for_company(self.env.company).monthly_cap or 0.0
            if cap > 0:
                # Keep the IDS, not just the count: "N employees near the
                # ceiling" is only actionable if you can see which N.
                for g in per_emp:
                    if (g.get('approved_hours') or 0.0) >= cap * 0.9:
                        near += 1
                        emp = g.get('employee_id')
                        if emp and len(near_ids) < _DRILL_IDS:
                            near_ids.append(emp[0] if isinstance(emp, (list, tuple))
                                            else emp)
        return {'total': round(total, 2), 'by_type': by_type[:4],
                'cap': cap, 'near_cap': near, 'near_cap_ids': near_ids,
                'employees': len(per_emp),
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
        # Orphan rows (no payslip_run_id) carry no company signal at all — a
        # same-date_from heuristic showed every legacy orphan to every
        # company's viewers (review M-3). Policy: orphans are visible ONLY to
        # the super-admin/system tier, who own the legacy cleanup.
        orphan_periods = set()
        if (self.env.user.has_group('base.group_system')
                or self.env.user.has_group(
                    'pb_hr_payroll_base.group_payroll_super_admin')):
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
                # The RUN ID, not just its name. Dropping it (pre-Phase-O) is
                # what forced a snapshot card to open the legacy
                # payroll.analytics form — the only registered form view for
                # that model, and a dashboard whose charts were deleted in
                # Phase M. With the id the card can open the run's real,
                # live composition instead.
                'run_id': rec.payslip_run_id.id if rec.payslip_run_id else False,
                'run_name': rec.payslip_run_id.name if rec.payslip_run_id else '',
                'structure': rec.salary_structure_name or '',
            })
            if len(out) >= _SNAPSHOTS:
                break
        return out

    # ------------------------------------------------------------ explorer
    def _explorer(self):
        """Whether the Explorer is installed, and its action.

        Phase O RETIRED the report gallery. Its nine cards were launchers into
        the Explorer, duplicating the Explorer's own lens grid card-for-card —
        so the board carried a second copy of a menu that already exists one
        click away, while every actual NUMBER on the board was unclickable.

        The gallery is replaced by drill-through: the hero tiles, the cost
        columns, the department rows, the statutory arcs and chips, the pulse
        tiles and the snapshot cards each open their own question. The two
        classic Odoo destinations the gallery also carried moved into the
        Explorer's lens grid (``pb_explorer._classic``), so nothing was lost.
        """
        action = self.env.ref('pb_explorer.action_pb_explorer',
                              raise_if_not_found=False)
        return {'available': bool(action),
                'xmlid': 'pb_explorer.action_pb_explorer' if action else ''}

    # ------------------------------------------------------ people ledgers
    #
    # IA Cycle 6. Two of the pulse tiles drill into a POPULATION nothing else in
    # the product shows: the employees behind this week's attendance exceptions,
    # by kind, and the employees at 90% of their monthly overtime ceiling. Every
    # other drill on this board had a destination — the Explorer for the
    # analytics questions, a hub lens for the operational queues — but these two
    # are filtered subsets that no lens carries, so they used to escape into a
    # bare `hr.employee` list with `target: "current"`: the cockpit replaced,
    # nothing to click, and no way back (W5).
    #
    # They become an in-cockpit ledger with a drawer instead — the fourth use of
    # the C3/C4 pattern, and a clone of it rather than an import, for the same
    # reason pb_statutory gave: a Setup-area cockpit's dependencies are not
    # worth acquiring for two hundred lines of grid.
    #
    # READ-ONLY, like everything else on this facade, and the same shape the
    # other three ledgers ship: `columns` / `rows[].cells` / `_f` (facet values)
    # / `_s` (search haystack), with facets built FROM the loaded rows so a chip
    # can never match nothing.

    _LEDGER_KINDS = {
        'att_missing_punch': ('missing_punch', 'Missing punch'),
        'att_missing_checkout': ('missing_checkout', 'Missing check-out'),
        'att_late': ('late', 'Late arrival'),
        'att_early_leave': ('early_leave', 'Early leave'),
        'ot_near_cap': (None, 'Near the overtime ceiling'),
    }

    def _facets(self, rows, spec):
        """Facets built from the LOADED rows, so a chip always matches rows."""
        out = []
        for key, label in spec:
            vals = sorted({(r['_f'].get(key) or '') for r in rows} - {''})
            out.append({'key': key, 'label': label,
                        'kind': 'chips' if len(vals) <= 8 else 'select',
                        'chips': [{'id': v, 'label': v} for v in vals]})
        return out

    @api.model
    def get_people_ledger(self, kind):
        """The employees behind one pulse tile. Read-only."""
        self._require()
        su = self.sudo()
        if kind not in self._LEDGER_KINDS:
            raise UserError(_("Unknown ledger: %s", kind))
        if kind == 'ot_near_cap':
            return su._ledger_near_cap()
        return su._ledger_attendance(kind)

    def _ledger_attendance(self, kind):
        exc_kind, title = self._LEDGER_KINDS[kind]
        pulse = self._safe(self._pulse_attendance, None) or {}
        ids = (pulse.get('kind_employees') or {}).get(exc_kind) or []
        overflow = (pulse.get('kind_overflow') or {}).get(exc_kind) or 0
        employees = self.env['hr.employee'].browse(ids).exists()
        rows = []
        for emp in employees:
            dept = emp.department_id.name or ''
            job = emp.job_id.name or ''
            rows.append({
                'id': emp.id,
                'cells': [emp.name or '', emp.barcode or emp.identification_id or '',
                          dept or '—', job or '—'],
                '_f': {'department': dept, 'job': job},
                '_s': ' '.join(x for x in [emp.name or '', emp.barcode or '',
                                           dept, job] if x),
            })
        return {
            'kind': kind,
            'title': title,
            'subtitle': _("Employees with this exception between %(a)s and %(b)s.",
                          a=pulse.get('date_from') or '', b=pulse.get('date_to') or ''),
            'search_ph': _("Search name, code or department…"),
            'empty': _("No employee carries this exception in the current week."),
            'columns': [{'label': _("Employee"), 'wide': True},
                        {'label': _("Code")}, {'label': _("Department")},
                        {'label': _("Position")}],
            'facets': self._facets(rows, [('department', _("Department")),
                                          ('job', _("Position"))]),
            'rows': rows, 'total': len(rows) + overflow, 'shown': len(rows),
            # W45: the true total travels beside the capped list, never instead
            # of it — a shrinking backlog on a growing problem is the failure
            # mode a silent cap produces.
            'overflow': overflow,
        }

    def _ledger_near_cap(self):
        pulse = self._safe(self._pulse_ot, None) or {}
        ids = pulse.get('near_cap_ids') or []
        cap = pulse.get('cap') or 0.0
        employees = self.env['hr.employee'].browse(ids).exists()
        hours = {}
        if employees and 'hr.overtime.request' in self.env:
            dom = [('date', '>=', pulse.get('date_from')),
                   ('date', '<=', pulse.get('date_to')),
                   ('state', '=', 'approved'),
                   ('employee_id', 'in', employees.ids)]
            for g in self.env['hr.overtime.request'].read_group(
                    dom, ['approved_hours:sum'], ['employee_id']):
                emp = g.get('employee_id')
                if emp:
                    hours[emp[0] if isinstance(emp, (list, tuple)) else emp] = \
                        round(g.get('approved_hours') or 0.0, 2)
        rows = []
        for emp in employees:
            used = hours.get(emp.id, 0.0)
            pct = round(used / cap * 100.0) if cap else 0
            dept = emp.department_id.name or ''
            band = _("Over the cap") if cap and used >= cap else _("Near the cap")
            rows.append({
                'id': emp.id,
                'cells': [emp.name or '', dept or '—',
                          '%s h' % used, '%s%%' % pct],
                'badge': {'label': band,
                          'tone': 'warn' if (cap and used >= cap) else 'muted'},
                '_f': {'department': dept, 'band': band},
                '_s': ' '.join(x for x in [emp.name or '', dept] if x),
            })
        rows.sort(key=lambda r: -hours.get(r['id'], 0.0))
        return {
            'kind': 'ot_near_cap',
            'title': _("Near the overtime ceiling"),
            'subtitle': _("Approved overtime %(a)s to %(b)s against a monthly "
                          "ceiling of %(cap)s hours.",
                          a=pulse.get('date_from') or '',
                          b=pulse.get('date_to') or '', cap=cap or 0),
            'search_ph': _("Search name or department…"),
            'empty': _("Nobody is near the monthly overtime ceiling."),
            'columns': [{'label': _("Employee"), 'wide': True},
                        {'label': _("Department")}, {'label': _("Approved")},
                        {'label': _("Of ceiling")}],
            'facets': self._facets(rows, [('department', _("Department")),
                                          ('band', _("Band"))]),
            'rows': rows, 'total': len(rows), 'shown': len(rows), 'overflow': 0,
        }

    @api.model
    def get_people_detail(self, kind, employee_id):
        """One employee's drawer. Read-only, and the access check is the REAL
        one: the ledger runs sudo (this whole facade does, behind `_require`),
        so the drawer asks the ORM whether this reader may read this employee
        rather than assuming the tile already answered it."""
        self._require()
        if kind not in self._LEDGER_KINDS:
            raise UserError(_("Unknown ledger: %s", kind))
        emp = self.env['hr.employee'].browse(int(employee_id or 0)).exists()
        if not emp:
            raise UserError(_("That employee no longer exists."))
        emp.check_access('read')
        su = emp.sudo()
        facts = [
            {'label': _("Employee code"),
             'value': su.barcode or su.identification_id or '—'},
            {'label': _("Department"), 'value': su.department_id.name or '—'},
            {'label': _("Position"), 'value': su.job_id.name or '—'},
            {'label': _("Manager"), 'value': su.parent_id.name or '—'},
            {'label': _("Company"), 'value': su.company_id.name or '—'},
        ]
        if kind == 'ot_near_cap':
            pulse = self.sudo()._safe(self._pulse_ot, None) or {}
            facts.append({'label': _("Monthly ceiling"),
                          'value': '%s h' % (pulse.get('cap') or 0)})
        return {
            'id': su.id,
            'title': su.name or '',
            'subtitle': su.job_id.name or su.department_id.name or '',
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % su.id,
            'facts': facts,
        }

    # ----------------------------------------------------- back-compat RPC
    @api.model
    def get_insights_data(self):
        """Pre-Phase-M entry point, kept so a stale browser bundle still
        renders instead of erroring. Returns the new payload."""
        return self.get_insights()
