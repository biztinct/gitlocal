# -*- coding: utf-8 -*-
"""pb.explorer — the read-only Analytics Explorer facade (Sudima Phase N).

One workbench replacing thirteen dead report cards: pick a MEASURE, group it BY
a dimension, spread it OVER a time grain, narrow it WHERE you like, and drill
any cell to the people behind it.

Doctrine
--------
* **Read-only** — this module contains no ``create``/``write``/``unlink``. The
  fact tables are maintained by ``pb.fact.builder``, a separate model; calling
  its ``ensure_fresh()`` is how a read guarantees correctness without this file
  ever becoming a writer. Asserted by ``test_08``.
* **Gate first, then sudo the reads** (C18.17/65/73) — the gate group set is a
  superset of the underlying models' ACLs, exactly as in ``pb.insights``.
* **Company scoping survives sudo** (C18.11/18) — every statement carries an
  explicit ``company_id IN %s`` built from ``env.companies``.
* **Never silently wrong.** Unbuilt periods are REPORTED as pending and left
  out of the numbers; row caps are reported; the as-of fallback count and the
  untyped-category count ride on every payload.
* **Drill on IDs, never names.** ``hr_department.name`` is jsonb (translatable)
  — any drill that round-tripped the displayed label returns nothing the moment
  the UI is Vietnamese. Every series carries its raw key.
"""

import logging
import time
from datetime import date

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- access
_GATE_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_analytics_user',
    'pb_hr_payroll_base.group_payroll_super_admin',
)

# ---------------------------------------------------------------- bounds
_RUN_SCAN = 200        # newest runs considered before company scoping
_MAX_SERIES = 24       # dimension members charted; the overflow is SURFACED
_MAX_BUCKETS = 36      # time buckets on the x axis
_DRILL_PAGE = 100      # employees per drill page
_EXPORT_CAP = 20000    # CSV rows; the cap is reported, never silent
_UNCAPPED = 5000       # derived measures collect both sides whole, then rank

# --------------------------------------------------------------- registry
# Measures are defined by CATEGORY TYPE, never by a code list (C18.81): the
# same definition works for Vietnam, Malaysia or anywhere else.
#   types  - category_types summed for this measure (None = every type)
#   sign   - deductions are stored negative on some structures; 'abs' presents
#            them as a positive magnitude so a bar chart reads correctly.
#   table  - 'emp' forces the employee-grain table (headcount distincts).
_MEASURES = {
    'net':           {'label': 'Net pay',        'types': ('net',),               'kind': 'money'},
    'gross':         {'label': 'Gross pay',      'types': ('basic', 'allowance'), 'kind': 'money'},
    'basic':         {'label': 'Basic salary',   'types': ('basic',),             'kind': 'money'},
    'allowances':    {'label': 'Allowances',     'types': ('allowance',),         'kind': 'money'},
    'deductions':    {'label': 'Deductions',     'types': ('deduction', 'tax', 'social_security'),
                      'kind': 'money', 'abs': True},
    'tax':           {'label': 'Tax withheld',   'types': ('tax',),               'kind': 'money', 'abs': True},
    'social':        {'label': 'Social security','types': ('social_security',),   'kind': 'money', 'abs': True},
    'employer_cost': {'label': 'Employer cost',  'types': ('employer_cost',),     'kind': 'money', 'abs': True},
    # Employee contributions and tax are stored NEGATIVE (they are deductions)
    # while employer cost is positive. Summing them signed gives a number that
    # means nothing and stacks half the chart below the axis; the statutory
    # LOAD is the sum of magnitudes.
    'statutory':     {'label': 'Statutory load', 'types': ('social_security', 'tax', 'employer_cost'),
                      'kind': 'money', 'abs': True},
    'total_cost':    {'label': 'Total cost',     'types': ('basic', 'allowance', 'employer_cost'),
                      'kind': 'money'},
    'component':     {'label': 'Component value','types': None,                   'kind': 'money'},
    'headcount':     {'label': 'Headcount',      'types': None, 'table': 'emp',
                      'kind': 'count', 'agg': 'distinct_employee'},
    'cost_per_head': {'label': 'Cost per head',  'kind': 'money',
                      'derived': ('total_cost', 'headcount')},
}

# Dimensions. ``model`` means the key is a database id whose label is read
# through the ORM (translated correctly); ``char`` keys are their own label.
_T1_ONLY = ('code',)
_T2_ONLY = ('job_id', 'employee_id')
_DIMENSIONS = {
    'department_id': {'label': 'Department',  'model': 'hr.department'},
    'division':      {'label': 'Division',    'kind': 'char'},
    'category_type': {'label': 'Component type', 'kind': 'char'},
    'code':          {'label': 'Component',   'kind': 'char'},
    'cycle':         {'label': 'Cycle',       'kind': 'char'},
    'job_id':        {'label': 'Job position','model': 'hr.job'},
    'company_id':    {'label': 'Company',     'model': 'res.company'},
    'run_id':        {'label': 'Pay run',     'model': 'hr.payslip.run'},
    'none':          {'label': 'Total',       'kind': 'none'},
}

_GRAINS = {
    'month':   {'label': 'Month',   'col': 'month'},
    'quarter': {'label': 'Quarter', 'col': 'quarter'},
    'year':    {'label': 'Year',    'col': 'year'},
    'run':     {'label': 'Pay run', 'col': 'run_id'},
    'none':    {'label': 'No split','col': None},
}

_CHARTS = ('column', 'stacked', 'line', 'donut', 'heatmap', 'table')

# Filter fields that may appear in a spec, mapped to their fact column.
_FILTERS = {
    'department_id': ('department_id', 'int'),
    'division':      ('division', 'char'),
    'category_type': ('category_type', 'char'),
    'code':          ('code', 'char'),
    'cycle':         ('cycle', 'char'),
    'company_id':    ('company_id', 'int'),
    'run_id':        ('run_id', 'int'),
    'job_id':        ('job_id', 'int'),
    'employee_id':   ('employee_id', 'int'),
    'basis':         ('basis', 'char'),
}

_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

# --------------------------------------------------------------- lenses
# The nine shipped lenses. Each is a saved spec — the SAME object the chip rail
# produces — so every one of them is fully editable the moment it opens. This
# replaces the thirteen-card gallery whose destinations were hardcoded KPIs,
# permanently blank charts and totals that could not be non-zero.
# Labels are translated at read time (module constant: _() here would freeze
# the language at import).
# Real Odoo views worth keeping a route to. `pb_hr_flow`'s payslip-line pivot is
# the richest one in the codebase and had ZERO entry points before Phase N.
_CLASSIC_REPORTS = [
    ('pb_hr_flow.action_hr_payslip_line_analytics', 'Payslip Line Pivot',
     'The raw pivot — every payslip line, by component'),
    ('payroll_analytics_approval.action_payroll_analytics_comparison',
     'Period Comparison', 'Month-over-month component comparison'),
]

_LENSES = [
    {'id': 'cost', 'name': 'Cost Explorer', 'icon': 'wallet',
     'desc': 'Total cost of employment by department, month by month',
     'spec': {'measure': 'total_cost', 'dimension': 'department_id',
              'grain': 'month', 'chart': 'column', 'filters': {}}},
    {'id': 'statutory', 'name': 'Statutory Ledger', 'icon': 'layers',
     'desc': 'Employee contributions, employer contributions and tax withheld',
     'spec': {'measure': 'statutory', 'dimension': 'category_type',
              'grain': 'month', 'chart': 'stacked', 'filters': {}}},
    {'id': 'movement', 'name': 'Workforce Movement', 'icon': 'users',
     'desc': 'Headcount on a payroll basis — who was actually paid, by period',
     'spec': {'measure': 'headcount', 'dimension': 'department_id',
              'grain': 'month', 'chart': 'line', 'filters': {}}},
    {'id': 'benefits', 'name': 'Benefits & Allowances', 'icon': 'sparkles',
     'desc': 'What the allowance budget is actually spent on',
     'spec': {'measure': 'allowances', 'dimension': 'code',
              'grain': 'none', 'chart': 'donut', 'filters': {}}},
    {'id': 'perhead', 'name': 'Cost per Head', 'icon': 'ruler',
     'desc': 'Cost per employee by department — the fairest cross-team compare',
     'spec': {'measure': 'cost_per_head', 'dimension': 'department_id',
              'grain': 'month', 'chart': 'heatmap', 'filters': {}}},
    {'id': 'yoy', 'name': 'Year on Year', 'icon': 'trending',
     'desc': 'Total cost of employment across years, by division',
     'spec': {'measure': 'total_cost', 'dimension': 'division',
              'grain': 'year', 'chart': 'column', 'filters': {}}},
    {'id': 'mix', 'name': 'Structure Mix', 'icon': 'pie',
     'desc': 'How gross pay is composed — basic versus everything else',
     'spec': {'measure': 'gross', 'dimension': 'code',
              'grain': 'none', 'chart': 'donut', 'filters': {}}},
    {'id': 'tax', 'name': 'Tax & Deductions', 'icon': 'filter',
     'desc': 'What is withheld, by department and period',
     'spec': {'measure': 'deductions', 'dimension': 'department_id',
              'grain': 'month', 'chart': 'stacked', 'filters': {}}},
    {'id': 'components', 'name': 'Component Explorer', 'icon': 'grid',
     'desc': 'Every pay component, ranked — the payslip-line pivot, live',
     'spec': {'measure': 'component', 'dimension': 'code',
              'grain': 'month', 'chart': 'table', 'filters': {}}},
]


class PbExplorer(models.AbstractModel):
    _name = 'pb.explorer'
    _description = 'Payobook Analytics Explorer — read-only query facade'

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
        raise AccessError(_("The Analytics Explorer is restricted to payroll "
                            "analytics managers."))

    def _co_ids(self):
        """Every SELECTED company (C18.11/18)."""
        return tuple(self.env.companies.ids or [self.env.company.id])

    # -------------------------------------------------------------- entry
    @api.model
    def resolve_spec(self, lens=None, spec=None):
        """Resolve a cockpit ENTRY POINT into a validated spec.

        Two ways in, one exit. A gallery card or sidebar link passes a named
        ``lens``; any element on another board that wants to hand over an exact
        question passes a full ``spec`` (Insights' "every number is a door").

        Both go through ``_clean_spec``, so a spec arriving from a URL or an
        action context is untrusted input that degrades to sane defaults —
        every value must match a registry key or it is replaced, and nothing
        reaches SQL uninterpolated. Resolving server-side keeps the lens
        definitions a single source of truth instead of duplicating them in JS.
        """
        self._require()
        if spec:
            return self._clean_spec(spec)
        if lens:
            for entry in _LENSES:
                if entry['id'] == lens:
                    return self._clean_spec(entry['spec'])
        return self._clean_spec({})

    # -------------------------------------------------------------- specs
    @staticmethod
    def _pick(spec, key, registry, fallback):
        """Choose a registry key from untrusted input.

        The value has to be forced to something HASHABLE before the membership
        test: a spec can arrive from an action context or a URL, and a JSON
        object there made ``value not in registry`` raise
        ``TypeError: unhashable type: 'dict'`` — a crash instead of a
        graceful default. Found by the hostile-spec test, not in review.
        """
        value = spec.get(key)
        if not isinstance(value, str):
            return fallback
        return value if value in registry else fallback

    @api.model
    def _clean_spec(self, spec):
        """Normalise an untrusted client spec. Every value that reaches SQL is
        either a registry key or a bound parameter — never interpolated text."""
        if not isinstance(spec, dict):
            spec = {}
        measure = self._pick(spec, 'measure', _MEASURES, 'net')
        dimension = self._pick(spec, 'dimension', _DIMENSIONS, 'department_id')
        grain = self._pick(spec, 'grain', _GRAINS, 'month')
        chart = self._pick(spec, 'chart', _CHARTS, 'column')

        filters = {}
        raw_filters = spec.get('filters')
        for key, raw in (raw_filters if isinstance(raw_filters, dict) else {}).items():
            if key not in _FILTERS:
                continue
            _col, typ = _FILTERS[key]
            vals = raw if isinstance(raw, (list, tuple)) else [raw]
            # Only scalars survive: a nested list/dict is not a filter value.
            vals = [v for v in vals if isinstance(v, (str, int, float))
                    and not isinstance(v, bool)]
            if typ == 'int':
                vals = [int(v) for v in vals if str(v).lstrip('-').isdigit()]
            else:
                vals = [str(v) for v in vals if v not in (None, '')]
            if vals:
                filters[key] = vals

        try:
            limit = int(spec.get('limit') or _MAX_SERIES)
        except (TypeError, ValueError):
            limit = _MAX_SERIES
        return {
            'measure': measure, 'dimension': dimension, 'grain': grain,
            'chart': chart, 'filters': filters,
            'date_from': self._as_date(spec.get('date_from')),
            'date_to': self._as_date(spec.get('date_to')),
            'limit': min(max(1, limit), _MAX_SERIES),
        }

    @staticmethod
    def _as_date(v):
        if not isinstance(v, str):
            return None
        if not v:
            return None
        try:
            return str(v)[:10] if len(str(v)) >= 10 else None
        except Exception:
            return None

    @api.model
    def _resolve_table(self, spec):
        """Which fact table answers this spec — and refuse, loudly, when the
        combination genuinely has no honest answer.

        The trap this closes: ``pb.fact.line.headcount`` is a distinct count AT
        ITS OWN GRAIN, so summing it across components double-counts people.
        Headcount therefore always comes from T2. Asking for headcount BY
        component is not a rounding problem, it is a category error — one
        employee is in a dozen components — so it is rejected with a real
        explanation rather than answered wrongly.
        """
        m, d = spec['measure'], spec['dimension']
        meas = _MEASURES[m]
        # A derived measure needs BOTH tables (cost per head = money / people),
        # so it inherits the employee-grain restriction of its denominator.
        derived = meas.get('derived') or ()
        needs_emp = (meas.get('table') == 'emp'
                     or any(_MEASURES[k].get('table') == 'emp' for k in derived)
                     or d in _T2_ONLY
                     or 'employee_id' in spec['filters']
                     or 'job_id' in spec['filters'])
        needs_line = (d in _T1_ONLY or m == 'component'
                      or 'code' in spec['filters'])
        if needs_emp and needs_line:
            raise UserError(_(
                "“%(measure)s” cannot be broken down by “%(dim)s”. Headcount "
                "and job-level figures are counted per employee, while "
                "component-level figures are counted per pay component — one "
                "employee appears in many components, so combining them would "
                "count people more than once. Pick a component measure, or "
                "group by department or division instead.",
                measure=_(meas['label']), dim=_(_DIMENSIONS[d]['label'])))
        return 'emp' if needs_emp else 'line'

    # -------------------------------------------------------------- scope
    def _scope_runs(self, spec):
        """Company-scoped, date-scoped run ids, freshened.

        Returns ``(ready_ids, pending)`` where pending carries the runs whose
        facts were not built inside this request's budget.
        """
        Run = self.env['hr.payslip.run'].sudo()
        dom = []
        if spec.get('date_from'):
            dom.append(('date_end', '>=', spec['date_from']))
        if spec.get('date_to'):
            dom.append(('date_start', '<=', spec['date_to']))
        if spec['filters'].get('run_id'):
            dom.append(('id', 'in', spec['filters']['run_id']))
        runs = Run.search(dom + [('state', '!=', 'cancel')],
                          order='date_end desc, id desc', limit=_RUN_SCAN)
        if not runs:
            return [], []
        # hr.payslip.run has NO company_id in this om_hr_payroll (C18.43) —
        # scope through its payslips, one indexed lookup.
        self.env.cr.execute(
            "SELECT DISTINCT payslip_run_id FROM hr_payslip "
            "WHERE payslip_run_id IN %s AND company_id IN %s AND state != 'cancel'",
            (tuple(runs.ids), self._co_ids()))
        allowed = {r[0] for r in self.env.cr.fetchall()}
        scoped = [r.id for r in runs if r.id in allowed]
        if not scoped:
            return [], []
        ready, pending_ids = self.env['pb.fact.builder'].ensure_fresh(scoped)
        pending = []
        if pending_ids:
            pending = [{'id': r.id, 'name': r.name or ''}
                       for r in Run.browse(pending_ids).exists()]
        return [r for r in scoped if r in ready], pending

    # -------------------------------------------------------------- query
    @api.model
    def query(self, spec=None):
        """The workbench aggregate. Returns categories x series, chart-ready."""
        self._require()
        t0 = time.time()
        spec = self._clean_spec(spec)
        table = self._resolve_table(spec)
        run_ids, pending = self._scope_runs(spec)
        if not run_ids:
            return self._empty(spec, pending, t0)

        if _MEASURES[spec['measure']].get('derived'):
            payload = self._query_derived(spec, table, run_ids)
        else:
            payload = self._query_one(spec, table, run_ids, spec['measure'])
        payload.update({
            'ok': True, 'spec': spec, 'pending': pending,
            'coverage': self._coverage(run_ids),
            'ms': int((time.time() - t0) * 1000),
        })
        payload.update(self._labels(spec))
        return payload

    def _empty(self, spec, pending, t0):
        out = {'ok': True, 'spec': spec, 'categories': [], 'series': [],
               'grand_total': 0.0, 'pending': pending, 'truncated': 0,
               'coverage': self._coverage([]),
               'ms': int((time.time() - t0) * 1000)}
        out.update(self._labels(spec))
        return out

    def _labels(self, spec):
        m = _MEASURES[spec['measure']]
        return {
            'measure_label': _(m['label']),
            'measure_kind': m.get('kind', 'money'),
            'dimension_label': _(_DIMENSIONS[spec['dimension']]['label']),
            'grain_label': _(_GRAINS[spec['grain']]['label']),
        }

    def _where(self, spec, table, run_ids):
        """(sql, params) — every value bound, nothing interpolated."""
        clauses = ['run_id IN %s', 'company_id IN %s']
        params = [tuple(run_ids), self._co_ids()]
        meas = _MEASURES[spec['measure']]
        types = meas.get('types')
        if types:
            clauses.append('category_type IN %s')
            params.append(tuple(types))
        for key, vals in spec['filters'].items():
            col, _typ = _FILTERS[key]
            if key == 'run_id':          # already in the run scope
                continue
            if table == 'emp' and key == 'code':
                continue                  # unreachable: _resolve_table refused
            if table == 'line' and key in ('employee_id', 'job_id'):
                continue
            clauses.append('%s IN %%s' % col)
            params.append(tuple(vals))
        return ' AND '.join(clauses), params

    def _dim_expr(self, spec, table):
        d = spec['dimension']
        if d == 'none':
            return 'NULL::int', None
        return d, d

    def _time_expr(self, spec):
        col = _GRAINS[spec['grain']]['col']
        return (col or 'NULL::int')

    def _query_one(self, spec, table, run_ids, measure_key, limit=None):
        sub = dict(spec, measure=measure_key)
        if limit is not None:
            sub['limit'] = limit
        where, params = self._where(sub, table, run_ids)
        dim_col, _d = self._dim_expr(spec, table)
        time_col = self._time_expr(spec)
        meas = _MEASURES[measure_key]
        agg = ('COUNT(DISTINCT employee_id)'
               if meas.get('agg') == 'distinct_employee' else 'SUM(amount)')
        sql = """
            SELECT {dim} AS dkey, {tim} AS tkey, {agg} AS val
              FROM pb_fact_{tbl}
             WHERE {where}
             GROUP BY 1, 2
        """.format(dim=dim_col, tim=time_col, agg=agg,
                   tbl=table, where=where)
        self.env.cr.execute(sql, params)
        return self._shape(self.env.cr.fetchall(), spec, meas, limit=sub['limit'])

    def _query_derived(self, spec, table, run_ids):
        """cost_per_head and friends: two honest aggregates divided CELL BY
        CELL, never a ratio of pre-averaged numbers.

        Both sides are collected UNTRUNCATED and only the combined result is
        ranked and capped. Truncating each side separately would rank the
        numerator by cost and the denominator by headcount — different top-N
        sets — so a department could arrive with cost but no people and read as
        a flat zero.
        """
        num_key, den_key = _MEASURES[spec['measure']]['derived']
        wide = _UNCAPPED
        num = self._query_one(spec, 'line', run_ids, num_key, limit=wide)
        den = self._query_one(spec, 'emp', run_ids, den_key, limit=wide)
        den_map = {(s['key'], c['key']): v
                   for s in den['series']
                   for c, v in zip(den['categories'], s['values'])}
        cats = num['categories']

        rows, tot_num, tot_den = [], 0.0, 0.0
        for s in num['series']:
            vals, s_num, s_den = [], 0.0, 0.0
            for c, v in zip(cats, s['values']):
                heads = den_map.get((s['key'], c['key'])) or 0
                vals.append(round(v / heads, 2) if heads else 0.0)
                s_num += v
                s_den += heads
            # Series total is cost/heads over the whole row — not the mean of
            # the per-cell ratios, which would weight a tiny month equally.
            rows.append(dict(s, values=vals,
                             total=round(s_num / s_den, 2) if s_den else 0.0))
            tot_num += s_num
            tot_den += s_den

        rows.sort(key=lambda r: abs(r['total']), reverse=True)
        truncated = max(0, len(rows) - spec['limit'])
        return {'categories': cats, 'series': rows[:spec['limit']],
                'grand_total': round(tot_num / tot_den, 2) if tot_den else 0.0,
                'truncated': truncated}

    # -------------------------------------------------------------- shape
    def _shape(self, rows, spec, meas, limit=None):
        """Raw (dkey, tkey, val) tuples -> aligned categories x series."""
        limit = spec['limit'] if limit is None else limit
        use_abs = meas.get('abs')
        cat_keys, series_map = [], {}
        seen_cat = set()
        for dkey, tkey, val in rows:
            v = float(val or 0.0)
            if use_abs:
                v = abs(v)
            ck = self._ckey(tkey, spec)
            if ck not in seen_cat:
                seen_cat.add(ck)
                cat_keys.append((ck, tkey))
            series_map.setdefault(dkey, {})
            series_map[dkey][ck] = series_map[dkey].get(ck, 0.0) + v

        # Chronological, not lexical: run ids sort as strings ('10' < '9'), so
        # the run grain is ordered by the run's own period instead.
        cat_keys.sort(key=self._cat_sort_key(spec, cat_keys))
        categories = [{'key': ck, 'label': self._clabel(tkey, spec)}
                      for ck, tkey in cat_keys]
        order = [ck for ck, _t in cat_keys]

        totals = {k: sum(v.values()) for k, v in series_map.items()}
        ranked = sorted(totals, key=lambda k: abs(totals[k]), reverse=True)
        truncated = max(0, len(ranked) - limit)
        ranked = ranked[:limit]

        labels = self._dim_labels(spec['dimension'], ranked)
        series = []
        for k in ranked:
            row = series_map[k]
            series.append({
                'key': '' if k is None else str(k),
                'raw': k,
                'label': labels.get(k) or _('Unassigned'),
                'values': [round(row.get(ck, 0.0), 2) for ck in order],
                'total': round(totals[k], 2),
            })
        return {'categories': categories, 'series': series,
                'grand_total': round(sum(totals[k] for k in ranked), 2),
                'truncated': truncated}

    def _cat_sort_key(self, spec, cat_keys):
        if spec['grain'] != 'run':
            return lambda kt: str(kt[0])
        runs = self.env['hr.payslip.run'].sudo().browse(
            [int(t) for _c, t in cat_keys if t is not None]).exists()
        order = {r.id: (r.date_end or r.date_start or date.min, r.id) for r in runs}
        return lambda kt: order.get(int(kt[1]) if kt[1] is not None else 0,
                                    (date.min, 0))

    @staticmethod
    def _ckey(tkey, spec):
        if tkey is None:
            return '_all'
        if spec['grain'] == 'month':
            return str(tkey)[:10]
        return str(tkey)

    def _clabel(self, tkey, spec):
        g = spec['grain']
        if tkey is None:
            return _('All periods')
        if g == 'month':
            d = tkey if isinstance(tkey, date) else None
            if d:
                return '%s %s' % (_(_MONTHS[d.month - 1]), d.year)
            return str(tkey)[:7]
        if g == 'run':
            run = self.env['hr.payslip.run'].sudo().browse(int(tkey)).exists()
            return (run.name or str(tkey)) if run else str(tkey)
        return str(tkey)

    def _dim_labels(self, dimension, keys):
        """Display labels read through the ORM so translated names are correct."""
        meta = _DIMENSIONS[dimension]
        if dimension == 'none':
            return {k: _('Total') for k in keys}
        model = meta.get('model')
        if not model:
            return {k: (str(k) if k else _('Unassigned')).replace('_', ' ').title()
                    for k in keys}
        ids = [int(k) for k in keys if k]
        recs = self.env[model].sudo().browse(ids).exists()
        out = {r.id: (r.display_name or '') for r in recs}
        return {k: out.get(int(k)) if k else None for k in keys}

    # ------------------------------------------------------------- schema
    @api.model
    def get_schema(self):
        """Everything the chip rail needs to render: the registries plus the
        DISTINCT values actually present in the facts (never a hardcoded list —
        a database with no Vietnam data must not offer Vietnamese filters)."""
        self._require()
        self.env.cr.execute("""
            SELECT DISTINCT division, cycle, category_type, basis
              FROM pb_fact_line WHERE company_id IN %s
        """, (self._co_ids(),))
        divisions, cycles, ctypes, bases = set(), set(), set(), set()
        for div, cyc, ct, basis in self.env.cr.fetchall():
            if div:
                divisions.add(div)
            if cyc:
                cycles.add(cyc)
            if ct:
                ctypes.add(ct)
            if basis:
                bases.add(basis)

        self.env.cr.execute("""
            SELECT code, MIN(component_name), SUM(ABS(amount)) AS w
              FROM pb_fact_line WHERE company_id IN %s AND code IS NOT NULL
             GROUP BY code ORDER BY w DESC LIMIT 200
        """, (self._co_ids(),))
        codes = [{'value': c, 'label': n or c}
                 for c, n, _w in self.env.cr.fetchall()]

        self.env.cr.execute("""
            SELECT DISTINCT department_id FROM pb_fact_line
             WHERE company_id IN %s AND department_id IS NOT NULL
        """, (self._co_ids(),))
        dept_ids = [r[0] for r in self.env.cr.fetchall()]
        depts = [{'value': d.id, 'label': d.display_name}
                 for d in self.env['hr.department'].sudo().browse(dept_ids).exists()]
        depts.sort(key=lambda x: x['label'] or '')

        self.env.cr.execute(
            "SELECT MIN(month), MAX(month) FROM pb_fact_line WHERE company_id IN %s",
            (self._co_ids(),))
        dmin, dmax = self.env.cr.fetchone() or (None, None)

        Fact = self.env['pb.fact.run'].sudo()
        total_runs = self.env['hr.payslip.run'].sudo().search_count(
            [('state', '!=', 'cancel')])
        return {
            'measures': [{'value': k, 'label': _(v['label']),
                          'kind': v.get('kind', 'money')}
                         for k, v in _MEASURES.items()],
            'dimensions': [{'value': k, 'label': _(v['label'])}
                           for k, v in _DIMENSIONS.items()],
            'grains': [{'value': k, 'label': _(v['label'])}
                       for k, v in _GRAINS.items()],
            'charts': list(_CHARTS),
            'options': {
                'division': [{'value': d, 'label': d.replace('_', ' ').title()}
                             for d in sorted(divisions)],
                'cycle': [{'value': c, 'label': c.title()} for c in sorted(cycles)],
                'category_type': [{'value': c,
                                   'label': c.replace('_', ' ').title()}
                                  for c in sorted(ctypes)],
                'basis': [{'value': b, 'label': b.title()} for b in sorted(bases)],
                'department_id': depts,
                'code': codes,
            },
            'bounds': {'date_from': str(dmin) if dmin else None,
                       'date_to': str(dmax) if dmax else None},
            'build': {'built_runs': Fact.search_count([]),
                      'total_runs': total_runs},
            'lenses': self._lenses(),
            'classic': self._classic(),
        }

    def _classic(self):
        """Destinations that are real Odoo views, not lenses.

        These used to hang off the Insights report gallery. That gallery is
        retired (every number on the board is now its own door), so they live
        here — the one place that is *about* choosing an analysis. Only entries
        that RESOLVE on this database are returned.
        """
        out = []
        for xmlid, label, desc in _CLASSIC_REPORTS:
            if self.env.ref(xmlid, raise_if_not_found=False):
                out.append({'xmlid': xmlid, 'label': _(label), 'desc': _(desc)})
            else:
                _logger.info('pb_explorer: classic report %s not installed', xmlid)
        return out

    # -------------------------------------------------------------- drill
    @api.model
    def drill(self, spec=None, series_key=None, category_key=None, page=0):
        """The employees behind one cell — read from PAYSLIP TRUTH, not from
        the facts, so the drill doubles as the audit trail for the number.

        Keyed on the series' RAW id (``series_key``), never on its displayed
        label: department names are jsonb/translatable and a label round-trip
        returns nothing under a Vietnamese UI.
        """
        self._require()
        spec = self._clean_spec(spec)
        run_ids, _pending = self._scope_runs(spec)
        if not run_ids:
            return {'ok': True, 'rows': [], 'total': 0, 'page': 0,
                    'cell': {}, 'has_more': False}

        clauses = ["p.payslip_run_id IN %s", "p.company_id IN %s",
                   "p.state != 'cancel'"]
        params = [tuple(run_ids), self._co_ids()]

        # Narrow to the clicked cell.
        cell = {}
        dim = spec['dimension']
        if series_key not in (None, '', '_all') and dim != 'none':
            cell['dimension'] = dim
            if dim == 'department_id':
                clauses.append('fe.department_id = %s')
                params.append(int(series_key))
            elif dim == 'job_id':
                clauses.append('fe.job_id = %s')
                params.append(int(series_key))
            elif dim == 'code':
                clauses.append('pl.code = %s')
                params.append(str(series_key))
            elif dim == 'category_type':
                clauses.append("COALESCE(c.category_type, 'allowance') = %s")
                params.append(str(series_key))
            elif dim == 'run_id':
                clauses.append('p.payslip_run_id = %s')
                params.append(int(series_key))
            elif dim == 'company_id':
                clauses.append('p.company_id = %s')
                params.append(int(series_key))
            elif dim in ('division', 'cycle'):
                clauses.append('fe.%s = %%s' % dim)
                params.append(str(series_key))
        if category_key not in (None, '', '_all'):
            cell['period'] = category_key
            g = spec['grain']
            if g == 'month':
                clauses.append('fe.month = %s')
                params.append(str(category_key)[:10])
            elif g == 'quarter':
                clauses.append('fe.quarter = %s')
                params.append(str(category_key))
            elif g == 'year':
                clauses.append('fe.year = %s')
                params.append(int(category_key))
            elif g == 'run':
                clauses.append('p.payslip_run_id = %s')
                params.append(int(category_key))

        meas = _MEASURES[spec['measure']]
        types = meas.get('types')
        if types:
            clauses.append("COALESCE(c.category_type, 'allowance') IN %s")
            params.append(tuple(types))
        for key, vals in spec['filters'].items():
            if key in ('run_id',):
                continue
            if key == 'code':
                clauses.append('pl.code IN %s')
            elif key == 'category_type':
                clauses.append("COALESCE(c.category_type, 'allowance') IN %s")
            elif key in ('department_id', 'job_id', 'division', 'cycle', 'basis'):
                clauses.append('fe.%s IN %%s' % key)
            elif key == 'employee_id':
                clauses.append('p.employee_id IN %s')
            elif key == 'company_id':
                clauses.append('p.company_id IN %s')
            else:
                continue
            params.append(tuple(vals))

        where = ' AND '.join(clauses)
        # pb_fact_emp supplies the as-of dimensions (department/job/period) so
        # the drill agrees with the chart it came from, cell for cell.
        base = """
              FROM hr_payslip_line pl
              JOIN hr_payslip p ON p.id = pl.slip_id
              LEFT JOIN hr_salary_rule_category c ON c.id = pl.category_id
              JOIN pb_fact_emp fe
                ON fe.run_id = p.payslip_run_id
               AND fe.employee_id = p.employee_id
               AND fe.category_type = COALESCE(c.category_type, 'allowance')
             WHERE {where}
        """.format(where=where)

        self.env.cr.execute(
            "SELECT COUNT(*) FROM (SELECT p.employee_id %s GROUP BY p.employee_id) t"
            % base, params)
        total = (self.env.cr.fetchone() or [0])[0]

        page = max(0, int(page or 0))
        self.env.cr.execute("""
            SELECT p.employee_id, SUM(pl.total) AS amt, COUNT(*) AS nlines,
                   MAX(fe.department_id)
            %s
             GROUP BY p.employee_id
             ORDER BY ABS(SUM(pl.total)) DESC
             LIMIT %%s OFFSET %%s
        """ % base, params + [_DRILL_PAGE, page * _DRILL_PAGE])
        raw = self.env.cr.fetchall()

        emps = self.env['hr.employee'].sudo().browse(
            [r[0] for r in raw]).exists()
        emap = {e.id: e for e in emps}
        depts = self.env['hr.department'].sudo().browse(
            [r[3] for r in raw if r[3]]).exists()
        dmap = {d.id: d.display_name for d in depts}
        use_abs = meas.get('abs')
        rows = []
        for emp_id, amt, nlines, dept_id in raw:
            e = emap.get(emp_id)
            v = float(amt or 0.0)
            rows.append({
                'employee_id': emp_id,
                'name': e.display_name if e else _('(deleted employee)'),
                'department': dmap.get(dept_id) or _('Unassigned'),
                'amount': round(abs(v) if use_abs else v, 2),
                'lines': nlines,
            })
        return {'ok': True, 'rows': rows, 'total': total, 'page': page,
                'page_size': _DRILL_PAGE, 'cell': cell,
                'has_more': (page + 1) * _DRILL_PAGE < total,
                'measure_label': _(meas['label'])}

    # ------------------------------------------------------------- export
    @api.model
    def export_csv(self, spec=None):
        """The current lens as CSV. Follows the house pattern (OT desk,
        pb_hr_workforce/models/ot_desk.py:393): a base64 payload the cockpit
        downloads through a data-URI anchor, so no ir.attachment is persisted
        and this facade stays a pure reader.

        The row cap is REPORTED in the payload — a truncated export that looks
        complete is the worst possible analytics bug.
        """
        self._require()
        import base64
        import csv
        import io

        payload = self.query(spec)
        buf = io.StringIO()
        w = csv.writer(buf)
        head = [payload['dimension_label']] + [c['label'] for c in
                                               payload['categories']]
        w.writerow(head + [_('Total')])
        written = 0
        for s in payload['series']:
            if written >= _EXPORT_CAP:
                break
            w.writerow([s['label']] + list(s['values']) + [s['total']])
            written += 1
        data = buf.getvalue().encode('utf-8-sig')   # BOM: Excel reads UTF-8
        return {
            'ok': True,
            'csv_b64': base64.b64encode(data).decode('ascii'),
            'filename': 'payobook_%s_by_%s_%s.csv' % (
                payload['spec']['measure'], payload['spec']['dimension'],
                date.today().isoformat()),
            'rows': written,
            'truncated': max(0, len(payload['series']) - written)
                         + payload.get('truncated', 0),
            'cap': _EXPORT_CAP,
        }

    # ==================================================================
    #  Narrative layer — analytics that EXPLAIN instead of just displaying
    # ==================================================================
    @api.model
    def narrate(self, spec=None):
        """The story behind the movement: an exactly-reconciling variance
        waterfall plus an anomaly rail, both scoped by the current lens."""
        self._require()
        t0 = time.time()
        spec = self._clean_spec(spec)
        run_ids, pending = self._scope_runs(spec)
        if len(run_ids) < 2:
            return {'ok': True, 'waterfall': None, 'anomalies': [],
                    'reason': _('Two comparable pay periods are needed to '
                                'explain a movement — only %s is in scope.',
                                len(run_ids)),
                    'pending': pending, 'ms': int((time.time() - t0) * 1000)}

        pair = self._compare_pair(run_ids)
        water = self._waterfall(spec, pair)
        anomalies = self._anomalies(spec, pair)
        return {'ok': True, 'waterfall': water, 'anomalies': anomalies,
                'pending': pending, 'reason': '',
                'ms': int((time.time() - t0) * 1000)}

    def _compare_pair(self, run_ids):
        """The two most recent COMPARABLE runs in scope.

        Comparable means same cycle and same division: comparing a mid-cycle
        advance against an end-cycle payroll produces a spectacular, entirely
        meaningless delta. Falls back to plain recency when no matching pair
        exists, and SAYS which it did.
        """
        Fact = self.env['pb.fact.run'].sudo()
        facts = Fact.search([('run_id', 'in', run_ids)],
                            order='date_end desc, id desc')
        if len(facts) < 2:
            return None
        head = facts[0]
        mate = next((f for f in facts[1:]
                     if f.cycle == head.cycle and f.division == head.division),
                    None)
        return {'b': head, 'a': mate or facts[1], 'like_for_like': bool(mate)}

    def _emp_map(self, fact_run, spec):
        """{employee_id: {category_type: amount}} for one run, lens-filtered."""
        clauses = ['run_id = %s', 'company_id IN %s']
        params = [fact_run.run_id.id, self._co_ids()]
        for key in ('department_id', 'division', 'cycle', 'job_id'):
            if spec['filters'].get(key):
                clauses.append('%s IN %%s' % key)
                params.append(tuple(spec['filters'][key]))
        self.env.cr.execute("""
            SELECT employee_id, category_type, SUM(amount)
              FROM pb_fact_emp WHERE %s GROUP BY 1, 2
        """ % ' AND '.join(clauses), params)
        out = {}
        for emp_id, ctype, amt in self.env.cr.fetchall():
            out.setdefault(emp_id, {})[ctype] = float(amt or 0.0)
        return out

    def _waterfall(self, spec, pair):
        """Decompose the movement so the bars SUM EXACTLY to the delta.

        With A the prior run, B the current one and M = A ∩ B the matched set:

            Total(B) - Total(A) = Σ_M (b - a)          <- matched movement
                                + Σ_(B\\A) b           <- joiners
                                - Σ_(A\\B) a           <- leavers

        The identity is exact, so the waterfall reconciles to the cent (test
        11). Matched movement is then split by component type — which is the
        whole reason the employee-grain table exists.
        """
        if not pair:
            return None
        a_map, b_map = self._emp_map(pair['a'], spec), self._emp_map(pair['b'], spec)

        # The waterfall decomposes an AMOUNT. Headcount and cost-per-head are
        # not amounts, so it explains net pay instead — and says so, rather
        # than silently charting a different number under the wrong label.
        measure_key = spec['measure']
        notes = []
        if measure_key in ('headcount', 'cost_per_head'):
            notes.append(_('“%s” is not a money total, so the movement below '
                           'explains NET PAY.', _(_MEASURES[measure_key]['label'])))
            measure_key = 'net'
        meas = _MEASURES[measure_key]
        types = meas.get('types')

        # pb.fact.emp is grained by component TYPE, not by component code, so a
        # single-component filter cannot be honoured here. Report it.
        if spec['filters'].get('code'):
            notes.append(_('The component filter does not apply to this '
                           'breakdown — it covers all components.'))

        def total(vals):
            if types:
                return sum(v for k, v in vals.items() if k in types)
            return sum(vals.values())

        a_ids, b_ids = set(a_map), set(b_map)
        matched = a_ids & b_ids
        joiners, leavers = b_ids - a_ids, a_ids - b_ids

        start = sum(total(a_map[e]) for e in a_ids)
        end = sum(total(b_map[e]) for e in b_ids)
        joiner_amt = sum(total(b_map[e]) for e in joiners)
        leaver_amt = -sum(total(a_map[e]) for e in leavers)

        # Matched movement, split by component type.
        by_type = {}
        for e in matched:
            av, bv = a_map[e], b_map[e]
            for ctype in set(av) | set(bv):
                if types and ctype not in types:
                    continue
                by_type[ctype] = by_type.get(ctype, 0.0) + \
                    (bv.get(ctype, 0.0) - av.get(ctype, 0.0))

        steps = []
        if leavers:
            steps.append({'key': 'leavers', 'label': _('Leavers (%s)', len(leavers)),
                          'value': round(leaver_amt, 2)})
        if joiners:
            steps.append({'key': 'joiners', 'label': _('Joiners (%s)', len(joiners)),
                          'value': round(joiner_amt, 2)})
        # When the measure covers a single component type, "Net" as a bar label
        # sits confusingly beside "net movement" in the same panel — the bar is
        # really "what the people who stayed were paid differently".
        live_types = [k for k, v in by_type.items() if round(v, 2)]
        single = len(live_types) == 1
        for ctype, val in sorted(by_type.items(), key=lambda kv: -abs(kv[1])):
            if round(val, 2) == 0:
                continue
            steps.append({'key': ctype,
                          'label': (_('Pay changes (%s stayed)', len(matched))
                                    if single
                                    else ctype.replace('_', ' ').title()),
                          'value': round(val, 2)})

        residual = round(end - start - sum(s['value'] for s in steps), 2)
        return {
            'start': round(start, 2), 'end': round(end, 2),
            'delta': round(end - start, 2),
            'steps': steps,
            'residual': residual,          # must be 0.0; surfaced, not hidden
            'from_label': pair['a'].name or '', 'to_label': pair['b'].name or '',
            'from_run': pair['a'].run_id.id, 'to_run': pair['b'].run_id.id,
            'matched': len(matched), 'joiners': len(joiners),
            'leavers': len(leavers),
            'like_for_like': pair['like_for_like'],
            'basis_note': '' if pair['b'].basis == 'approved' else
                          _('The current period is still provisional.'),
            'notes': notes,
            'measure_label': _(meas['label']),
        }

    def _anomalies(self, spec, pair):
        """What changed that a human would want flagged. Each row carries a
        ready-made lens so a finding is one click from its own evidence."""
        if not pair:
            return []
        out = []
        co = self._co_ids()

        # --- components that appeared or vanished -----------------------
        self.env.cr.execute("""
            SELECT code, MIN(component_name),
                   SUM(amount) FILTER (WHERE run_id = %s) AS a_amt,
                   SUM(amount) FILTER (WHERE run_id = %s) AS b_amt
              FROM pb_fact_line
             WHERE run_id IN %s AND company_id IN %s
             GROUP BY code
        """, (pair['a'].run_id.id, pair['b'].run_id.id,
              (pair['a'].run_id.id, pair['b'].run_id.id), co))
        for code, name, a_amt, b_amt in self.env.cr.fetchall():
            a_amt, b_amt = float(a_amt or 0.0), float(b_amt or 0.0)
            if a_amt and not b_amt:
                out.append({
                    'kind': 'vanished', 'severity': 'high',
                    'title': _('“%s” stopped being paid', name or code),
                    'detail': _('Worth %(amt)s last period, absent this one.',
                                amt=self._fmt(a_amt)),
                    'lens': {'measure': 'component', 'dimension': 'code',
                             'grain': 'run', 'chart': 'column',
                             'filters': {'code': [code]}},
                })
            elif b_amt and not a_amt:
                out.append({
                    'kind': 'new', 'severity': 'info',
                    'title': _('“%s” started being paid', name or code),
                    'detail': _('Worth %(amt)s this period, absent last one.',
                                amt=self._fmt(b_amt)),
                    'lens': {'measure': 'component', 'dimension': 'code',
                             'grain': 'run', 'chart': 'column',
                             'filters': {'code': [code]}},
                })

        # --- departments moving against the company trend ---------------
        self.env.cr.execute("""
            SELECT department_id,
                   SUM(amount) FILTER (WHERE run_id = %s) AS a_amt,
                   SUM(amount) FILTER (WHERE run_id = %s) AS b_amt
              FROM pb_fact_line
             WHERE run_id IN %s AND company_id IN %s AND category_type = 'net'
               AND department_id IS NOT NULL
             GROUP BY department_id
        """, (pair['a'].run_id.id, pair['b'].run_id.id,
              (pair['a'].run_id.id, pair['b'].run_id.id), co))
        rows = [(d, float(a or 0.0), float(b or 0.0))
                for d, a, b in self.env.cr.fetchall()]
        tot_a = sum(r[1] for r in rows)
        tot_b = sum(r[2] for r in rows)
        company_dir = (tot_b - tot_a)
        if rows and tot_a:
            names = {d.id: d.display_name for d in
                     self.env['hr.department'].sudo().browse(
                         [r[0] for r in rows]).exists()}
            for dept_id, a_amt, b_amt in rows:
                if not a_amt:
                    continue
                pct = (b_amt - a_amt) / abs(a_amt) * 100.0
                against = (company_dir >= 0 and (b_amt - a_amt) < 0) or \
                          (company_dir < 0 and (b_amt - a_amt) > 0)
                if abs(pct) >= 15.0:
                    out.append({
                        'kind': 'against' if against else 'swing',
                        'severity': 'high' if abs(pct) >= 30 else 'warn',
                        'title': _('%(dept)s net pay %(dir)s %(pct)s%%',
                                   dept=names.get(dept_id) or _('Unassigned'),
                                   dir=_('rose') if pct > 0 else _('fell'),
                                   pct=abs(round(pct, 1))),
                        'detail': (_('Against the company trend.') if against
                                   else _('%(a)s to %(b)s.',
                                          a=self._fmt(a_amt), b=self._fmt(b_amt))),
                        'lens': {'measure': 'net', 'dimension': 'code',
                                 'grain': 'run', 'chart': 'column',
                                 'filters': {'department_id': [dept_id]}},
                    })

        order = {'high': 0, 'warn': 1, 'info': 2}
        out.sort(key=lambda a: order.get(a['severity'], 3))
        return out[:12]

    @staticmethod
    def _fmt(v):
        v = float(v or 0.0)
        for div, suf in ((1e12, 'T'), (1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
            if abs(v) >= div:
                return '%.1f%s' % (v / div, suf)
        return '%.0f' % v

    # ==================================================================
    #  Ask in English
    # ==================================================================
    @api.model
    def ask(self, text):
        """Compile a plain-English question into an Explorer spec.

        The DETERMINISTIC parser runs first and always produces a usable spec
        (C1: no feature may depend on an LLM being reachable). When an AI
        provider is configured, it gets a chance to REFINE that spec — and its
        answer is validated back through ``_clean_spec``, so a hallucinated
        measure degrades to the keyword result instead of an error.

        The chips it chose are returned with the spec so the UI can show its
        working: this is never a black box the user cannot edit.
        """
        self._require()
        text = (text or '').strip()
        if not text:
            return {'ok': False, 'error': _('Ask a question first.')}
        spec, why = self._ask_keywords(text)
        source = 'keywords'
        refined = self._ask_llm(text, spec)
        if refined:
            spec, source = refined, 'ai'
        return {'ok': True, 'spec': self._clean_spec(spec),
                'source': source, 'matched': why}

    def _ask_keywords(self, text):
        """Deterministic intent parse. Longest phrases first so 'cost per head'
        never matches as 'cost'."""
        t = ' %s ' % text.lower().replace(',', ' ')
        why = []
        spec = {'measure': 'net', 'dimension': 'department_id',
                'grain': 'month', 'chart': 'column', 'filters': {}}

        measures = [
            ('cost per head', 'cost_per_head'), ('per head', 'cost_per_head'),
            ('per employee', 'cost_per_head'), ('headcount', 'headcount'),
            ('head count', 'headcount'), ('employees', 'headcount'),
            ('employer cost', 'employer_cost'), ('employer', 'employer_cost'),
            ('total cost', 'total_cost'), ('social security', 'social'),
            ('social', 'social'), ('insurance', 'social'),
            ('tax', 'tax'), ('deduction', 'deductions'),
            ('allowance', 'allowances'), ('basic', 'basic'),
            ('gross', 'gross'), ('net', 'net'),
        ]
        for phrase, key in measures:
            if ' %s' % phrase in t:
                spec['measure'] = key
                why.append({'chip': 'measure', 'token': phrase})
                break

        dims = [
            ('by department', 'department_id'), ('per department', 'department_id'),
            ('by division', 'division'), ('per division', 'division'),
            ('by component', 'code'), ('by pay component', 'code'),
            ('by job', 'job_id'), ('by position', 'job_id'),
            ('by company', 'company_id'), ('by run', 'run_id'),
            ('by cycle', 'cycle'), ('by type', 'category_type'),
            ('by team', 'department_id'),
        ]
        for phrase, key in dims:
            if phrase in t:
                spec['dimension'] = key
                why.append({'chip': 'dimension', 'token': phrase})
                break

        grains = [('by quarter', 'quarter'), ('quarterly', 'quarter'),
                  ('per quarter', 'quarter'), ('by year', 'year'),
                  ('yearly', 'year'), ('annual', 'year'),
                  ('per run', 'run'), ('by run', 'run'),
                  ('monthly', 'month'), ('by month', 'month'),
                  ('in total', 'none'), ('overall', 'none')]
        for phrase, key in grains:
            if phrase in t:
                spec['grain'] = key
                why.append({'chip': 'grain', 'token': phrase})
                break

        charts = [('as a share', 'donut'), ('share', 'donut'), ('pie', 'donut'),
                  ('trend', 'line'), ('over time', 'line'),
                  ('heatmap', 'heatmap'), ('heat map', 'heatmap'),
                  ('table', 'table'), ('stacked', 'stacked')]
        for phrase, key in charts:
            if phrase in t:
                spec['chart'] = key
                why.append({'chip': 'chart', 'token': phrase})
                break

        # Filters resolved against values that actually EXIST in the facts.
        schema_opts = self._filter_vocab()
        for field, options in schema_opts.items():
            for value, label in options:
                needle = ' %s ' % str(label).lower()
                if needle in t and len(str(label)) >= 3:
                    spec['filters'].setdefault(field, []).append(value)
                    why.append({'chip': 'filter', 'token': str(label)})
        if ' mid ' in t or 'mid-cycle' in t or 'mid cycle' in t:
            spec['filters'].setdefault('cycle', []).append('mid')
            why.append({'chip': 'filter', 'token': 'mid cycle'})

        if 'approved' in t:
            spec['filters'].setdefault('basis', []).append('approved')
            why.append({'chip': 'filter', 'token': 'approved'})
        return spec, why

    def _filter_vocab(self):
        """{field: [(value, label)]} of values present in the facts — never a
        hardcoded vocabulary, so the parser can only ever match real data."""
        out = {}
        self.env.cr.execute("""
            SELECT DISTINCT division, cycle FROM pb_fact_line
             WHERE company_id IN %s
        """, (self._co_ids(),))
        divs, cycles = set(), set()
        for div, cyc in self.env.cr.fetchall():
            if div:
                divs.add(div)
            if cyc:
                cycles.add(cyc)
        out['division'] = [(d, d.replace('_', ' ')) for d in divs]
        out['cycle'] = [(c, c) for c in cycles]

        self.env.cr.execute("""
            SELECT DISTINCT department_id FROM pb_fact_line
             WHERE company_id IN %s AND department_id IS NOT NULL
        """, (self._co_ids(),))
        depts = self.env['hr.department'].sudo().browse(
            [r[0] for r in self.env.cr.fetchall()]).exists()
        out['department_id'] = [(d.id, d.display_name) for d in depts]
        return out

    def _ask_llm(self, text, seed):
        """Optional refinement. SOFT dependency: pb_payroll_ai_insights is not
        in this module's manifest, so everything here is probed."""
        if 'payroll.ai.config' not in self.env:
            return None
        try:
            cfg = self.env['payroll.ai.config'].get_config_for_purpose('insights')
            if not cfg or not cfg.api_key:
                return None
            provider = cfg.get_provider()
            if not provider or not provider.is_available():
                return None
            prompt = (
                "Translate the payroll analytics question into JSON.\n"
                "Question: %s\n"
                "Allowed measure: %s\n"
                "Allowed dimension: %s\n"
                "Allowed grain: %s\n"
                "Allowed chart: %s\n"
                "A keyword parser proposed: %s\n"
                "Reply with ONLY a JSON object using those exact keys; keep the "
                "proposed value when the question does not clearly say otherwise."
                % (text, list(_MEASURES), list(_DIMENSIONS), list(_GRAINS),
                   list(_CHARTS), seed)
            )
            raw = provider.generate_structured(
                prompt, schema_hint='{"measure":"","dimension":"","grain":"","chart":""}',
                max_tokens=300, temperature=0.0)
            if not isinstance(raw, dict):
                return None
            out = dict(seed)
            for key, allowed in (('measure', _MEASURES), ('dimension', _DIMENSIONS),
                                 ('grain', _GRAINS)):
                if raw.get(key) in allowed:
                    out[key] = raw[key]
            if raw.get('chart') in _CHARTS:
                out['chart'] = raw['chart']
            return out
        except Exception as e:                      # noqa: BLE001 — never block
            _logger.info('pb_explorer: AI refinement unavailable (%s)', e)
            return None

    # ------------------------------------------------------------- lenses
    def _lenses(self):
        """The shipped lenses — the honest replacement for the dead gallery."""
        return [dict(x, name=_(x['name']), desc=_(x['desc'])) for x in _LENSES]

    # ----------------------------------------------------------- coverage
    def _coverage(self, run_ids):
        """The honesty block that rides on every payload."""
        if not run_ids:
            return {'runs': 0, 'asof_fallback': 0, 'untyped_categories': 0,
                    'provisional_runs': 0, 'built_runs': 0}
        Fact = self.env['pb.fact.run'].sudo()
        facts = Fact.search([('run_id', 'in', run_ids)])
        return {
            'runs': len(run_ids),
            'built_runs': len(facts),
            'provisional_runs': len(facts.filtered(
                lambda f: f.basis == 'provisional')),
            'asof_fallback': sum(facts.mapped('asof_fallback_count')),
            'untyped_categories': sum(facts.mapped('untyped_category_count')),
        }
