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

import calendar
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
    # GROUP P3 — "Headcount" was a word from the code. A person is a PERSON,
    # counted once across the whole group, and the measure says so.
    'headcount':     {'label': 'People',         'types': None, 'table': 'emp',
                      'kind': 'count', 'agg': 'distinct_person'},
    'fte':           {'label': 'Full-time equivalents', 'types': None,
                      'table': 'emp', 'kind': 'count', 'agg': 'fte'},
    'cost_per_head': {'label': 'Cost per person', 'kind': 'money',
                      'derived': ('total_cost', 'headcount')},
}

# The four kinds of pay run, in the words a person uses. The keys are
# `hr.formula.config.cycle_type`; nothing on screen ever says "cycle_type".
_KIND_LABELS = {
    'regular': 'Regular',
    'mid_cycle': 'Mid-month advance',
    'end_cycle': 'End of month',
    'full_final': 'Final settlement',
    '': 'Not from a scheme',
}

# Dimensions. ``model`` means the key is a database id whose label is read
# through the ORM (translated correctly); ``char`` keys are their own label.
_T1_ONLY = ('code',)
_T2_ONLY = ('job_id', 'employee_id')
_DIMENSIONS = {
    'department_id': {'label': 'Department',  'model': 'hr.department'},
    # Two ways to say "division": the group-level record (P1) and the key the
    # scheme carried before groups existed. `get_schema` offers exactly ONE of
    # them — whichever the facts actually have — under the plain word
    # "Division", so nobody ever chooses between two identical menu entries.
    'division_id':   {'label': 'Division',    'model': 'pb.division'},
    'division':      {'label': 'Division',    'kind': 'char'},
    'category_type': {'label': 'Component type', 'kind': 'char'},
    'code':          {'label': 'Component',   'kind': 'char'},
    'kind':          {'label': 'Kind of run', 'kind': 'char', 'col': 'cycle',
                      'labels': _KIND_LABELS},
    'scheme':        {'label': 'Payroll scheme', 'model': 'hr.formula.config',
                      'col': 'config_id'},
    'job_id':        {'label': 'Job position','model': 'hr.job'},
    'company_id':    {'label': 'Company',     'model': 'res.company'},
    # Derived from the company: a fact row carries no country of its own, and
    # inventing a column for something that is one join away would be a second
    # place for the answer to be wrong.
    'country':       {'label': 'Country',     'model': 'res.country',
                      'col': 'company_id', 'derive': 'country'},
    'group':         {'label': 'Group',       'model': 'pb.group',
                      'col': 'company_id', 'derive': 'group'},
    'run_id':        {'label': 'Pay run',     'model': 'hr.payslip.run'},
    'none':          {'label': 'Total',       'kind': 'none'},
}

# The walk down the group. Each level filters on the key of the one above it,
# and the chart always shows the level BELOW where you are standing.
_BREADCRUMB = ('group', 'country', 'company_id', 'division_id',
               'department_id', 'job_id')

_GRAINS = {
    'month':   {'label': 'Month',   'col': 'month'},
    'quarter': {'label': 'Quarter', 'col': 'quarter'},
    'year':    {'label': 'Year',    'col': 'year'},
    'run':     {'label': 'Pay run', 'col': 'run_id'},
    'none':    {'label': 'No split','col': None},
}

_CHARTS = ('column', 'stacked', 'line', 'donut', 'heatmap', 'table', 'compare')

# Filter fields that may appear in a spec, mapped to their fact column.
# `country` and `group` carry no column of their own — they are expanded into
# a list of company ids in ``_where``.
_FILTERS = {
    'department_id': ('department_id', 'int'),
    'division_id':   ('division_id', 'int'),
    'division':      ('division', 'char'),
    'category_type': ('category_type', 'char'),
    'code':          ('code', 'char'),
    'kind':          ('cycle', 'char'),
    'cycle':         ('cycle', 'char'),
    'scheme':        ('config_id', 'int'),
    'company_id':    ('company_id', 'int'),
    'country':       ('company_id', 'int'),
    'group':         ('company_id', 'int'),
    'run_id':        ('run_id', 'int'),
    'job_id':        ('job_id', 'int'),
    'employee_id':   ('employee_id', 'int'),
    'basis':         ('basis', 'char'),
}

# Money shown in the group's currency, or each company's own.
_CURRENCY_MODES = ('group', 'own')
# Advance (mid-month) runs are OUT unless asked for: counting them adds the
# same person and the same month's money twice.
_ADVANCE_MODES = ('main', 'all')

_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

# Money, in the words people type. Longest first so "singapore dollars" never
# matches as "dollars". A word only wins when the currency really exists here.
_CURRENCY_WORDS = (
    ('singapore dollars', 'SGD'), ('singapore dollar', 'SGD'),
    ('us dollars', 'USD'), ('us dollar', 'USD'),
    ('dollars', 'USD'), ('dollar', 'USD'),
    ('dong', 'VND'), ('vnd', 'VND'), ('sgd', 'SGD'), ('usd', 'USD'),
    ('euros', 'EUR'), ('euro', 'EUR'), ('eur', 'EUR'),
    ('rupiah', 'IDR'), ('ringgit', 'MYR'), ('baht', 'THB'),
    ('rupees', 'INR'), ('rupee', 'INR'), ('riel', 'KHR'),
)

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
    # GROUP P3 — months across, schemes down, one measure at a time.
    {'id': 'compare', 'name': 'Compare schemes', 'icon': 'gitMerge',
     'desc': 'Every payroll scheme side by side, month by month',
     'spec': {'measure': 'total_cost', 'dimension': 'scheme',
              'grain': 'month', 'chart': 'compare', 'filters': {}}},
    {'id': 'divisions', 'name': 'Across the group', 'icon': 'globe',
     'desc': 'Cost by division, across every company in the group',
     'spec': {'measure': 'total_cost', 'dimension': 'division_id',
              'grain': 'month', 'chart': 'column', 'filters': {}}},
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

        # GROUP P3 -----------------------------------------------------------
        # Three switches that change what a number MEANS, so each is part of
        # the spec, travels in the URL and is shown as a chip.
        advances = self._pick(spec, 'advances', _ADVANCE_MODES, 'main')
        currency = self._pick(spec, 'currency', _CURRENCY_MODES, 'group')
        # "…in dollars" asks for a currency this group may not report in. The
        # id is validated against real currencies, never trusted.
        try:
            target = int(spec.get('target_currency') or 0)
        except (TypeError, ValueError):
            target = 0
        if target and not self.env['res.currency'].sudo().with_context(
                active_test=False).browse(target).exists():
            target = 0
        # The breadcrumb: where the reader is standing. Every step also filters,
        # so the path is normalised here rather than trusted.
        path = []
        for step in (spec.get('path') if isinstance(spec.get('path'), list)
                     else []):
            if not isinstance(step, dict):
                continue
            level = step.get('level')
            if level not in _BREADCRUMB or level in {p['level'] for p in path}:
                continue
            key = step.get('key')
            if isinstance(key, bool) or not isinstance(key, (str, int)):
                continue
            path.append({'level': level, 'key': key,
                         'label': str(step.get('label') or '')[:120]})
        # Standing somewhere IS filtering by it. Doing that here means the
        # breadcrumb, the chips and the export can never disagree about what
        # the number covers.
        for step in list(path):
            key = step['level']
            _col, typ = _FILTERS[key]
            try:
                value = int(step['key']) if typ == 'int' else str(step['key'])
            except (TypeError, ValueError):
                path.remove(step)
                continue
            vals = filters.setdefault(key, [])
            if value not in vals:
                vals.append(value)
        return {
            'measure': measure, 'dimension': dimension, 'grain': grain,
            'chart': chart, 'filters': filters,
            'date_from': self._as_date(spec.get('date_from')),
            'date_to': self._as_date(spec.get('date_to')),
            'limit': min(max(1, limit), _MAX_SERIES),
            'advances': advances,
            'currency': currency,
            'target_currency': target,
            'per_head': bool(spec.get('per_head')),
            'path': path,
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
        # A derived measure needs BOTH tables (cost per person = money /
        # people), so it inherits the employee-grain restriction of its
        # denominator. `per_head` makes any money measure derived.
        derived = meas.get('derived') or ()
        if spec.get('per_head') and not derived and meas.get('kind') == 'money':
            derived = self._derived_pair(spec)
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

        per_head = (spec.get('per_head')
                    and _MEASURES[spec['measure']].get('kind') == 'money')
        if _MEASURES[spec['measure']].get('derived') or per_head:
            payload = self._query_derived(spec, table, run_ids)
        else:
            payload = self._query_one(spec, table, run_ids, spec['measure'])
        payload.update({
            'ok': True, 'spec': spec, 'pending': pending,
            'coverage': self._coverage(run_ids),
            'ms': int((time.time() - t0) * 1000),
        })
        payload.update(self._labels(spec))
        payload['trail'] = self._trail(spec)
        payload['heads'] = self._heads(spec, run_ids)
        return payload

    def _heads(self, spec, run_ids):
        """People and full-time equivalents behind exactly what is on screen.

        Counted ONCE across the whole group: somebody paid by two companies in
        the same month, or paid an advance and then a salary, is one person.
        That sentence is on the screen next to the number, because "headcount"
        is the figure people most often quietly disagree about.
        """
        sub = dict(spec, measure='headcount')
        where, params = self._where(sub, 'emp', run_ids)
        self.env.cr.execute("""
            SELECT COUNT(*), COALESCE(SUM(fte), 0) FROM (
                SELECT COALESCE(NULLIF(person_id, 0), employee_id) AS person,
                       MAX(fte) AS fte
                  FROM pb_fact_emp WHERE {where}
                 GROUP BY 1
            ) t
        """.format(where=where), params)
        people, fte = self.env.cr.fetchone() or (0, 0.0)
        return {'people': int(people or 0), 'fte': round(float(fte or 0.0), 1)}

    def _empty(self, spec, pending, t0):
        out = {'ok': True, 'spec': spec, 'categories': [], 'series': [],
               'grand_total': 0.0, 'pending': pending, 'truncated': 0,
               'coverage': self._coverage([]), 'parts': [], 'mixed': False,
               'money': None, 'converted': False,
               'currency_mode': spec.get('currency', 'group'),
               'currency': self._target_currency(spec),
               'ms': int((time.time() - t0) * 1000)}
        out.update(self._labels(spec))
        out['trail'] = self._trail(spec)
        out['heads'] = {'people': 0, 'fte': 0.0}
        return out

    def _labels(self, spec):
        m = _MEASURES[spec['measure']]
        label = _(m['label'])
        if spec.get('per_head') and m.get('kind') == 'money' \
                and not m.get('derived'):
            label = _('%s per person', label)
        return {
            'measure_label': label,
            'measure_kind': m.get('kind', 'money'),
            'dimension_label': _(_DIMENSIONS[spec['dimension']]['label']),
            'grain_label': _(_GRAINS[spec['grain']]['label']),
        }

    # --------------------------------------------------------- breadcrumb
    def _trail(self, spec):
        """Where the reader is standing, and what one step down would show.

        Group › Country › Company › Division › Department › Job — but only the
        rungs this database actually has. A group of one company in one country
        never shows a country crumb nobody can click, and a database with no
        divisions never shows a division level with one bar reading "Not in a
        division". A level that carries exactly ONE value is a wasted click, so
        it stays in the trail (it is where you are) and is skipped as a
        destination.

        Built on the server so a link pasted to a colleague draws the same
        trail on their screen — with THEIR companies and THEIR permissions.
        """
        scope = self.env.companies.sudo()
        has_group = 'pb_group_id' in self.env['res.company']._fields
        groups = scope.mapped('pb_group_id') if has_group else None
        countries = {c.country_id.id for c in scope if c.country_id}
        self.env.cr.execute("""
            SELECT COUNT(DISTINCT company_id),
                   COUNT(DISTINCT NULLIF(division_id, 0))
              FROM pb_fact_line WHERE company_id IN %s
        """, (self._co_ids(),))
        n_company, n_division = self.env.cr.fetchone() or (0, 0)

        levels = []
        if groups:
            levels.append('group')
        if len(countries) > 1:
            levels.append('country')
        levels.append('company_id')
        if n_division:
            levels.append('division_id')
        levels += ['department_id', 'job_id']

        singular = {
            'group': True,
            'country': len(countries) < 2,
            'company_id': (n_company or len(scope)) < 2,
        }
        walked = {step['level'] for step in spec['path']}
        nxt = ''
        for level in levels:
            if level == levels[0] or level in walked or singular.get(level):
                continue
            nxt = level
            break
        if not nxt:
            nxt = 'job_id' if 'department_id' in walked else 'department_id'
        root_label = (groups[:1].name if groups
                      else (scope[:1].name if scope else '')) or ''
        return {
            'levels': levels,
            'path': spec['path'],
            'root': levels[0],
            'root_label': root_label,
            'next': nxt,
            'next_label': _(_DIMENSIONS[nxt]['label']) if nxt else '',
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
        # VALUEKIND P4 — a money measure counts each dong once.
        #
        # A component whose amount is ALREADY INSIDE another component's total
        # ("SI-HI-IU Total 10.5%" inside "Total Deduction") is kept as a fact
        # row so the component view can show what a total is made of, and is
        # skipped by every measure that sums money. Summing both reported ABM's
        # gross as ~14bn against a true 927,155,630.
        #
        # `component`, which IS the per-component view, opts out by declaring no
        # `types` — it is the one measure whose whole purpose is the detail.
        if types and table == 'line':
            clauses.append('COALESCE(is_rollup, FALSE) = FALSE')
        # GROUP P3 — the default that stops a person, and their pay, being
        # counted twice in one month. Removable, and the chip says why.
        if spec.get('advances', 'main') == 'main':
            clauses.append('COALESCE(is_advance, FALSE) = FALSE')
        for key, vals in spec['filters'].items():
            col, _typ = _FILTERS[key]
            if key == 'run_id':          # already in the run scope
                continue
            if table == 'emp' and key == 'code':
                continue                  # unreachable: _resolve_table refused
            if table == 'line' and key in ('employee_id', 'job_id'):
                continue
            if key in ('country', 'group'):
                # No column of their own: a country and a group are sets of
                # companies, so they become the one predicate the facts carry.
                company_ids = self._companies_for(key, vals)
                if not company_ids:
                    # Nothing matched — say so with an impossible predicate
                    # rather than silently dropping the filter and showing
                    # figures the reader did not ask for.
                    clauses.append('company_id IN %s')
                    params.append((0,))
                    continue
                clauses.append('company_id IN %s')
                params.append(tuple(company_ids))
                continue
            clauses.append('%s IN %%s' % col)
            params.append(tuple(vals))
        return ' AND '.join(clauses), params

    def _companies_for(self, key, vals):
        """The companies a country code or a group id stands for."""
        Company = self.env['res.company'].sudo().with_context(active_test=False)
        scope = list(self._co_ids())
        if key == 'group':
            ids = [int(v) for v in vals if str(v).lstrip('-').isdigit()]
            hit = Company.search([('id', 'in', scope),
                                  ('pb_group_id', 'in', ids)]) \
                if 'pb_group_id' in Company._fields else Company.browse()
            return hit.ids
        codes = [str(v) for v in vals if v]
        ids = [int(v) for v in vals if str(v).lstrip('-').isdigit()]
        domain = ['|', ('country_id', 'in', ids), ('country_id.code', 'in', codes)]
        return Company.search([('id', 'in', scope)] + domain).ids

    def _dim_expr(self, spec, table):
        """The SQL expression the chart's rows are grouped by."""
        d = spec['dimension']
        if d == 'none':
            return 'NULL::int', None
        col = _DIMENSIONS[d].get('col', d)
        return col, col

    def _time_expr(self, spec):
        col = _GRAINS[spec['grain']]['col']
        return (col or 'NULL::int')

    def _raw(self, spec, table, run_ids, measure_key, limit=None):
        """The aggregate itself: rows of ``(dkey, tkey, currency_id, value)``.

        The currency travels with the row from here on. It is the difference
        between "3.2 billion" and "3.2 billion of WHAT", and a group that
        cannot answer the second question has no business adding the first.
        """
        sub = dict(spec, measure=measure_key)
        if limit is not None:
            sub['limit'] = limit
        where, params = self._where(sub, table, run_ids)
        dim_col, _d = self._dim_expr(spec, table)
        time_col = self._time_expr(spec)
        meas = _MEASURES[measure_key]
        money = meas.get('kind', 'money') == 'money'
        cur_col = 'currency_id' if money else 'NULL::int'
        agg_kind = meas.get('agg')
        # A person's full-time equivalent is a property of the PERSON, not of
        # each component row they appear on, so it is deduped per person
        # before it is summed. Summing the column flat would multiply every
        # person by the number of component types on their payslip.
        person = 'COALESCE(NULLIF(person_id, 0), employee_id)'
        if agg_kind == 'fte':
            sql = """
                SELECT dkey, tkey, ckey, SUM(fte) AS val FROM (
                    SELECT {dim} AS dkey, {tim} AS tkey, {cur} AS ckey,
                           {person} AS person, MAX(fte) AS fte
                      FROM pb_fact_{tbl}
                     WHERE {where}
                     GROUP BY 1, 2, 3, 4
                ) t GROUP BY 1, 2, 3
            """.format(dim=dim_col, tim=time_col, cur=cur_col, person=person,
                       tbl=table, where=where)
        else:
            agg = ('COUNT(DISTINCT %s)' % person
                   if agg_kind in ('distinct_person', 'distinct_employee')
                   else 'SUM(amount)')
            sql = """
                SELECT {dim} AS dkey, {tim} AS tkey, {cur} AS ckey, {agg} AS val
                  FROM pb_fact_{tbl}
                 WHERE {where}
                 GROUP BY 1, 2, 3
            """.format(dim=dim_col, tim=time_col, cur=cur_col, agg=agg,
                       tbl=table, where=where)
        self.env.cr.execute(sql, params)
        rows = self.env.cr.fetchall()
        return self._dim_remap(spec, rows), meas, sub['limit']

    # ------------------------------------------------------------- derived
    def _dim_remap(self, spec, rows):
        """Country and group are the company, read one level up.

        No fact column, no join in the hot statement: the company ids the
        aggregate already returned are rewritten to their country or their
        group and re-bucketed here, over at most a few dozen distinct values.
        """
        derive = _DIMENSIONS[spec['dimension']].get('derive')
        if not derive:
            return rows
        ids = {r[0] for r in rows if r[0]}
        companies = self.env['res.company'].sudo().with_context(
            active_test=False).browse([int(i) for i in ids]).exists()
        if derive == 'country':
            up = {c.id: (c.country_id.id or None) for c in companies}
        else:
            has_group = 'pb_group_id' in self.env['res.company']._fields
            up = {c.id: ((c.pb_group_id.id or None) if has_group else None)
                  for c in companies}
        merged = {}
        for dkey, tkey, ckey, val in rows:
            key = up.get(int(dkey)) if dkey else None
            merged[(key, tkey, ckey)] = merged.get((key, tkey, ckey), 0.0) \
                + float(val or 0.0)
        return [(k[0], k[1], k[2], v) for k, v in merged.items()]

    def _query_one(self, spec, table, run_ids, measure_key, limit=None):
        """One measure, shaped — and, when the money is in more than one
        currency, shaped once PER CURRENCY rather than added up."""
        rows, meas, cap = self._raw(spec, table, run_ids, measure_key, limit)
        buckets, money = self._buckets(spec, rows, run_ids, meas)
        parts = []
        for bucket in buckets:
            shaped = self._shape(bucket['rows'], spec, meas, limit=cap)
            shaped['currency'] = bucket['currency']
            shaped['rate'] = bucket.get('rate')
            parts.append(shaped)
        head = parts[0] if parts else self._shape([], spec, meas, limit=cap)
        out = dict(head)
        out['money'] = money
        out['converted'] = bool(money and money.get('converted'))
        out['currency_mode'] = spec.get('currency', 'group')
        if len(parts) > 1:
            out['mixed'] = True
            out['parts'] = parts
        else:
            out['mixed'] = False
            out['parts'] = parts
        return out

    def _period_end(self, spec, run_ids):
        """tkey -> the day a conversion for that bucket is dated on.

        The end of the period, because that is what a month's figures ARE:
        a rate picked on the 3rd would report August at July's money.
        """
        grain = spec['grain']
        runs = {}
        if grain == 'run' or grain == 'none':
            for r in self.env['hr.payslip.run'].sudo().browse(
                    list(run_ids)).exists():
                runs[r.id] = r.date_end or r.date_start
        fallback = max([d for d in runs.values() if d] or [date.today()])

        def when(tkey):
            if tkey is None:
                return fallback
            if grain == 'month':
                day = tkey if isinstance(tkey, date) else None
                if not day:
                    try:
                        day = date.fromisoformat(str(tkey)[:10])
                    except ValueError:
                        return fallback
                last = calendar.monthrange(day.year, day.month)[1]
                return date(day.year, day.month, last)
            if grain == 'quarter':
                try:
                    year, quarter = str(tkey).split('-Q')
                    month = int(quarter) * 3
                    return date(int(year), month,
                                calendar.monthrange(int(year), month)[1])
                except (ValueError, TypeError):
                    return fallback
            if grain == 'year':
                try:
                    return date(int(tkey), 12, 31)
                except (ValueError, TypeError):
                    return fallback
            if grain == 'run':
                return runs.get(int(tkey)) or fallback
            return fallback
        return when

    def _buckets(self, spec, rows, run_ids, meas):
        """Rows grouped into things that may honestly be added together.

        One bucket is one currency. In GROUP mode every bucket that has a rate
        is converted into the group's money and they become one; a bucket with
        no rate is NOT converted, NOT guessed and NOT dropped silently — it is
        reported under "Not converted" with the reason. In OWN mode the
        buckets stay apart and the screen shows a subtotal for each.
        """
        money = meas.get('kind', 'money') == 'money'
        if not money:
            return [{'currency': None,
                     'rows': [(r[0], r[1], r[3]) for r in rows]}], None
        by_currency = {}
        for dkey, tkey, ckey, val in rows:
            by_currency.setdefault(int(ckey or 0), []).append(
                (dkey, tkey, float(val or 0.0)))
        currencies = self._currency_info(list(by_currency))
        mode = spec.get('currency', 'group')
        target = self._target_currency(spec)
        meta = {'mode': mode, 'converted': False, 'target': target,
                'rates': [], 'unconverted': []}

        single = len(by_currency) == 1
        only = next(iter(by_currency)) if single else 0
        # One currency is one currency: nothing to convert, nothing to badge.
        if single and (mode == 'own' or not target or only == target['id']
                       or not only):
            return ([{'currency': currencies.get(only), 'rows': by_currency[only]}],
                    meta)

        if mode == 'own':
            out = []
            for cid, bucket in sorted(
                    by_currency.items(),
                    key=lambda kv: -sum(abs(v) for _d, _t, v in kv[1])):
                out.append({'currency': currencies.get(cid), 'rows': bucket})
            return out, meta

        # ---- group mode: convert at the end of each period ----------------
        if not target or 'pb.fx' not in self.env:
            return ([{'currency': currencies.get(only) if single else None,
                      'rows': [r for b in by_currency.values() for r in b]}],
                    meta)
        when = self._period_end(spec, run_ids)
        fx = self.env['pb.fx']
        pairs = {}
        for cid, bucket in by_currency.items():
            for _dkey, tkey, _val in bucket:
                pairs.setdefault((cid, tkey), when(tkey))
        answers = fx.convert_many(
            [{'amount': 1.0, 'src': cid, 'dst': target['id'], 'when': day}
             for (cid, _t), day in pairs.items()])
        rate_by_pair = {}
        for (key, answer) in zip(pairs.keys(), answers):
            rate_by_pair[key] = answer
        merged, seen_rate, missing = [], {}, {}
        for cid, bucket in by_currency.items():
            for dkey, tkey, val in bucket:
                answer = rate_by_pair.get((cid, tkey))
                if cid == target['id'] or not cid:
                    merged.append((dkey, tkey, val))
                    continue
                if not answer or not answer['known']:
                    note = (answer or {}).get('meta', {}).get('note', '')
                    bag = missing.setdefault(
                        (cid, tkey), {'currency': currencies.get(cid),
                                      'amount': 0.0, 'note': note,
                                      'period': self._clabel(tkey, spec)})
                    bag['amount'] += val
                    continue
                info = answer['meta']
                merged.append((dkey, tkey, val * info['rate']))
                seen_rate[(cid, tkey)] = {
                    'src': info['src'], 'dst': info['dst'],
                    'rate': info['rate'], 'rate_date': info['rate_date'],
                    'policy': info['policy'],
                    'period': self._clabel(tkey, spec),
                }
        meta['converted'] = bool(seen_rate)
        meta['rates'] = list(seen_rate.values())[:24]
        meta['unconverted'] = sorted(missing.values(),
                                     key=lambda m: -abs(m['amount']))[:24]
        return [{'currency': target, 'rows': merged}], meta

    def _target_currency(self, spec=None):
        """The money the group reads in, as a small dict — or None."""
        asked = (spec or {}).get('target_currency')
        if asked:
            currency = self.env['res.currency'].sudo().with_context(
                active_test=False).browse(int(asked)).exists()
            if currency:
                return {'id': currency.id, 'name': currency.name,
                        'symbol': currency.symbol or currency.name,
                        'position': currency.position or 'after'}
        try:
            currency = self.env['pb.fx'].presentation_currency(self.env.company)
        except Exception:                            # noqa: BLE001
            currency = self.env.company.currency_id
        if not currency:
            return None
        return {'id': currency.id, 'name': currency.name,
                'symbol': currency.symbol or currency.name,
                'position': currency.position or 'after'}

    def _currency_info(self, ids):
        recs = self.env['res.currency'].sudo().with_context(
            active_test=False).browse([int(i) for i in ids if i]).exists()
        return {c.id: {'id': c.id, 'name': c.name,
                       'symbol': c.symbol or c.name,
                       'position': c.position or 'after'} for c in recs}

    def _query_derived(self, spec, table, run_ids):
        """cost_per_head and friends: two honest aggregates divided CELL BY
        CELL, never a ratio of pre-averaged numbers.

        Both sides are collected UNTRUNCATED and only the combined result is
        ranked and capped. Truncating each side separately would rank the
        numerator by cost and the denominator by headcount — different top-N
        sets — so a department could arrive with cost but no people and read as
        a flat zero.
        """
        num_key, den_key = self._derived_pair(spec)
        wide = _UNCAPPED
        num = self._query_one(spec, 'line', run_ids, num_key, limit=wide)
        den = self._query_one(spec, 'emp', run_ids, den_key, limit=wide)
        den_map = {(s['key'], c['key']): v
                   for s in den['series']
                   for c, v in zip(den['categories'], s['values'])}

        def divide(part):
            cats = part['categories']
            rows, tot_num, tot_den = [], 0.0, 0.0
            for s in part['series']:
                vals, s_num, s_den = [], 0.0, 0.0
                for c, v in zip(cats, s['values']):
                    heads = den_map.get((s['key'], c['key'])) or 0
                    vals.append(round(v / heads, 2) if heads else 0.0)
                    s_num += v
                    s_den += heads
                # Series total is cost/people over the whole row — not the mean
                # of the per-cell ratios, which would weight a tiny month
                # equally with a full one.
                rows.append(dict(s, values=vals,
                                 total=round(s_num / s_den, 2) if s_den else 0.0))
                tot_num += s_num
                tot_den += s_den
            rows.sort(key=lambda r: abs(r['total']), reverse=True)
            return {'categories': cats, 'series': rows[:spec['limit']],
                    'grand_total': round(tot_num / tot_den, 2) if tot_den else 0.0,
                    'truncated': max(0, len(rows) - spec['limit']),
                    'currency': part.get('currency'),
                    'rate': part.get('rate')}

        parts = [divide(p) for p in (num.get('parts') or [num])]
        out = dict(parts[0] if parts else divide(num))
        out.update({'money': num.get('money'),
                    'converted': num.get('converted'),
                    'currency_mode': num.get('currency_mode'),
                    'mixed': bool(num.get('mixed')), 'parts': parts})
        return out

    def _derived_pair(self, spec):
        """(numerator, denominator) for a per-person figure.

        `cost_per_head` names its own pair. `per_head` — the Compare screen's
        toggle — turns WHATEVER measure is on screen into the same figure, so
        a CEO can compare two schemes whose headcounts differ by a factor of
        ten without doing arithmetic in their head.
        """
        meas = _MEASURES[spec['measure']]
        if meas.get('derived'):
            return meas['derived']
        return spec['measure'], 'headcount'

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
        # A fixed vocabulary that is TRANSLATED, not title-cased: nobody should
        # ever read "Mid Cycle" on a payroll screen.
        fixed = meta.get('labels')
        if fixed:
            return {k: _(fixed.get(str(k or ''), str(k or '')))
                    for k in keys}
        model = meta.get('model')
        if not model:
            return {k: (str(k) if k else _('Unassigned')).replace('_', ' ').title()
                    for k in keys}
        if model not in self.env:
            return {k: str(k or '') for k in keys}
        ids = [int(k) for k in keys if k]
        recs = self.env[model].sudo().browse(ids).exists()
        out = {r.id: (r.display_name or '') for r in recs}
        empty = {
            'division_id': _('Not in a division'),
            'country': _('No country set'),
            'group': _('Not in a group'),
            'scheme': _('No scheme named'),
            'department_id': _('No department'),
        }.get(dimension)
        return {k: (out.get(int(k)) if k else empty) for k in keys}

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

        # ---- GROUP P3: what the facts actually carry --------------------
        self.env.cr.execute("""
            SELECT DISTINCT division_id, config_id, currency_id
              FROM pb_fact_line WHERE company_id IN %s
        """, (self._co_ids(),))
        div_ids, cfg_ids, cur_ids = set(), set(), set()
        for div_id, cfg_id, cur_id in self.env.cr.fetchall():
            if div_id:
                div_ids.add(div_id)
            if cfg_id:
                cfg_ids.add(cfg_id)
            if cur_id:
                cur_ids.add(cur_id)

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

        # ONE word for one idea. The group-level division (P1) is the truth
        # when it exists; the key the scheme carried is the fallback for a
        # database that never set a group up. The reader is never asked to
        # choose between two menu entries called "Division".
        use_division_id = bool(div_ids)
        hidden = {'division_id'} if not use_division_id else {'division'}
        if not cfg_ids:
            hidden.add('scheme')
        if not cycles:
            hidden.add('kind')
        if len(self.env.companies) < 2:
            hidden.update({'country', 'group'})
        elif 'pb_group_id' not in self.env['res.company']._fields \
                or not self.env.companies.sudo().mapped('pb_group_id'):
            hidden.add('group')
        # `cycle` is the old key for `kind` — kept accepted in a saved spec,
        # never offered again.
        hidden.add('cycle')

        schemes = [{'value': c.id, 'label': c.display_name}
                   for c in self.env['hr.formula.config'].sudo()
                   .with_context(active_test=False).browse(sorted(cfg_ids))
                   .exists()] if cfg_ids else []
        schemes.sort(key=lambda x: x['label'] or '')
        division_opts = [{'value': d.id, 'label': d.display_name}
                         for d in self.env['pb.division'].sudo()
                         .with_context(active_test=False).browse(sorted(div_ids))
                         .exists()] if div_ids and 'pb.division' in self.env else []
        countries, group_opts = [], []
        if len(self.env.companies) > 1:
            seen = {}
            for co in self.env.companies.sudo():
                if co.country_id:
                    seen[co.country_id.id] = co.country_id.display_name
            countries = [{'value': k, 'label': v} for k, v in
                         sorted(seen.items(), key=lambda kv: kv[1] or '')]
            if 'pb_group_id' in self.env['res.company']._fields:
                group_opts = [{'value': g.id, 'label': g.display_name}
                              for g in self.env.companies.sudo()
                              .mapped('pb_group_id')]

        return {
            'measures': [{'value': k, 'label': _(v['label']),
                          'kind': v.get('kind', 'money')}
                         for k, v in _MEASURES.items()],
            'dimensions': [{'value': k, 'label': _(v['label'])}
                           for k, v in _DIMENSIONS.items()
                           if k not in hidden],
            'grains': [{'value': k, 'label': _(v['label'])}
                       for k, v in _GRAINS.items()],
            'charts': [c for c in _CHARTS if c != 'compare'],
            'options': {
                'division': [{'value': d, 'label': d.replace('_', ' ').title()}
                             for d in sorted(divisions)],
                'division_id': division_opts,
                'scheme': schemes,
                'kind': [{'value': c, 'label': _(_KIND_LABELS.get(c, c))}
                         for c in sorted(cycles)],
                'country': countries,
                'group': group_opts,
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
            'money': self._money_schema(cur_ids),
            'trail': self._trail(self._clean_spec({})),
            'lenses': self._lenses(),
            'classic': self._classic(),
        }

    def _money_schema(self, currency_ids):
        """What the header chip has to say about money before anything loads."""
        target = self._target_currency()
        info = self._currency_info(list(currency_ids))
        group = self.env['pb.group'].browse() if 'pb.group' in self.env \
            else None
        if group is not None and 'pb_group_id' in self.env['res.company']._fields:
            group = self.env.companies.sudo().mapped('pb_group_id')[:1]
        policy = ''
        if group and 'fx_policy' in group._fields:
            # The group's OWN words for how it picks a rate — read from the
            # field's selection so there is one sentence, not two.
            policy = dict(group._fields['fx_policy'].selection or []).get(
                group.fx_policy, '')
        return {
            'target': target,
            'currencies': sorted(info.values(), key=lambda c: c['name']),
            'many': len(info) > 1,
            'group': group.name if group else '',
            'policy': policy or '',
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
            elif dim in ('country', 'group'):
                ids = self._companies_for(dim, [series_key])
                clauses.append('p.company_id IN %s')
                params.append(tuple(ids) or (0,))
            elif dim in ('scheme', 'division_id'):
                clauses.append('fe.%s = %%s' % _DIMENSIONS[dim].get('col', dim))
                params.append(int(series_key))
            elif dim in ('division', 'cycle', 'kind'):
                clauses.append('fe.%s = %%s' % _DIMENSIONS[dim].get('col', dim))
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
        # The default that keeps a person out of the same month twice.
        if spec.get('advances', 'main') == 'main':
            clauses.append('COALESCE(fe.is_advance, FALSE) = FALSE')
        for key, vals in spec['filters'].items():
            if key in ('run_id',):
                continue
            if key == 'code':
                clauses.append('pl.code IN %s')
            elif key == 'category_type':
                clauses.append("COALESCE(c.category_type, 'allowance') IN %s")
            elif key in ('department_id', 'job_id', 'division', 'cycle',
                         'basis', 'kind', 'scheme', 'division_id'):
                clauses.append('fe.%s IN %%s' % _FILTERS[key][0])
            elif key == 'employee_id':
                clauses.append('p.employee_id IN %s')
            elif key == 'company_id':
                clauses.append('p.company_id IN %s')
            elif key in ('country', 'group'):
                clauses.append('p.company_id IN %s')
                params.append(tuple(self._companies_for(key, vals)) or (0,))
                continue
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
        written = 0
        parts = payload.get('parts') or [payload]
        for part in parts:
            currency = (part.get('currency') or {}).get('name') or ''
            if currency:
                # The money is named on the sheet, once per block. A column of
                # numbers with no currency is the export equivalent of the bug
                # this whole phase is about.
                w.writerow([_('Amounts in %s', currency)])
            head = [payload['dimension_label']] + [c['label'] for c in
                                                   part['categories']]
            w.writerow(head + [_('Total')])
            for s in part['series']:
                if written >= _EXPORT_CAP:
                    break
                w.writerow([s['label']] + list(s['values']) + [s['total']])
                written += 1
            w.writerow([])
        money = payload.get('money') or {}
        if money.get('unconverted'):
            w.writerow([_('Not converted — no exchange rate on file')])
            w.writerow([_('Currency'), _('Period'), _('Amount'), _('Why')])
            for row in money['unconverted']:
                w.writerow([(row.get('currency') or {}).get('name') or '',
                            row.get('period') or '', row.get('amount') or 0.0,
                            row.get('note') or ''])
        data = buf.getvalue().encode('utf-8-sig')   # BOM: Excel reads UTF-8
        return {
            'ok': True,
            'csv_b64': base64.b64encode(data).decode('ascii'),
            'filename': 'payobook_%s_by_%s_%s.csv' % (
                payload['spec']['measure'], payload['spec']['dimension'],
                date.today().isoformat()),
            'rows': written,
            'truncated': max(0, sum(len(p['series']) for p in parts) - written)
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

        pair = self._compare_pair(run_ids, spec)
        water = self._waterfall(spec, pair)
        anomalies = self._anomalies(spec, pair)
        return {'ok': True, 'waterfall': water, 'anomalies': anomalies,
                'pending': pending, 'reason': '',
                'ms': int((time.time() - t0) * 1000)}

    def _compare_pair(self, run_ids, spec=None):
        """The two most recent COMPARABLE runs in scope.

        Comparable means same cycle and same division: comparing a mid-cycle
        advance against an end-cycle payroll produces a spectacular, entirely
        meaningless delta. Falls back to plain recency when no matching pair
        exists, and SAYS which it did.
        """
        Fact = self.env['pb.fact.run'].sudo()
        domain = [('run_id', 'in', run_ids)]
        # A mid-month advance next to an end-of-month payroll is not a
        # movement, it is two different questions — so the default view never
        # compares one against the other.
        if (spec or {}).get('advances', 'main') == 'main':
            domain.append(('is_advance', '=', False))
        facts = Fact.search(domain, order='date_end desc, id desc')
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
        for key in ('department_id', 'division', 'division_id', 'cycle',
                    'kind', 'scheme', 'job_id'):
            if spec['filters'].get(key):
                clauses.append('%s IN %%s' % _FILTERS[key][0])
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

        division_dim = 'division_id' if self._has_group_divisions() else 'division'
        dims = [
            ('by department', 'department_id'), ('per department', 'department_id'),
            ('by payroll scheme', 'scheme'), ('by scheme', 'scheme'),
            ('per scheme', 'scheme'),
            ('by division', division_dim), ('per division', division_dim),
            ('by country', 'country'), ('per country', 'country'),
            ('by group', 'group'),
            ('by component', 'code'), ('by pay component', 'code'),
            ('by job', 'job_id'), ('by position', 'job_id'),
            ('by company', 'company_id'), ('by run', 'run_id'),
            ('by kind of run', 'kind'), ('by cycle', 'kind'),
            ('by type', 'category_type'),
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

        # ---- GROUP P3: the three switches, asked for in words -------------
        if 'including advances' in t or 'with advances' in t \
                or 'include advances' in t:
            spec['advances'] = 'all'
            why.append({'chip': 'runs', 'token': 'including advances'})
        elif 'main runs' in t or 'main run only' in t or 'main runs only' in t:
            spec['advances'] = 'main'
            why.append({'chip': 'runs', 'token': 'main runs'})

        if 'in group currency' in t or 'in the group currency' in t:
            spec['currency'] = 'group'
            why.append({'chip': 'money', 'token': 'in group currency'})
        elif 'in its own money' in t or 'in their own money' in t \
                or 'each in its own' in t or 'own currency' in t:
            spec['currency'] = 'own'
            why.append({'chip': 'money', 'token': 'each in its own money'})

        if 'per person' in t or 'per head' in t:
            spec['per_head'] = True
            why.append({'chip': 'money', 'token': 'per person'})

        for word, code in _CURRENCY_WORDS:
            if ' in %s' % word in t:
                currency = self.env['res.currency'].sudo().with_context(
                    active_test=False).search([('name', '=', code)], limit=1)
                if currency:
                    spec['currency'] = 'group'
                    spec['target_currency'] = currency.id
                    why.append({'chip': 'money', 'token': word})
                break
        return spec, why

    def _has_group_divisions(self):
        """Does this database actually use group-level divisions?"""
        self.env.cr.execute(
            'SELECT 1 FROM pb_fact_line WHERE company_id IN %s '
            'AND division_id IS NOT NULL AND division_id != 0 LIMIT 1',
            (self._co_ids(),))
        return bool(self.env.cr.fetchone())

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

        # GROUP P3 — schemes and group divisions are things people name out
        # loud ("the retail scheme", "logistics"), so they belong in the
        # vocabulary the parser is allowed to match.
        self.env.cr.execute("""
            SELECT DISTINCT config_id, division_id FROM pb_fact_line
             WHERE company_id IN %s
        """, (self._co_ids(),))
        cfg_ids, div_ids = set(), set()
        for cfg_id, div_id in self.env.cr.fetchall():
            if cfg_id:
                cfg_ids.add(cfg_id)
            if div_id:
                div_ids.add(div_id)
        if cfg_ids and 'hr.formula.config' in self.env:
            out['scheme'] = [
                (c.id, c.display_name) for c in
                self.env['hr.formula.config'].sudo().with_context(
                    active_test=False).browse(sorted(cfg_ids)).exists()]
        if div_ids and 'pb.division' in self.env:
            out['division_id'] = [
                (d.id, d.display_name) for d in
                self.env['pb.division'].sudo().with_context(
                    active_test=False).browse(sorted(div_ids)).exists()]
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
                    'provisional_runs': 0, 'built_runs': 0,
                    'division_fallback': 0}
        Fact = self.env['pb.fact.run'].sudo()
        facts = Fact.search([('run_id', 'in', run_ids)])
        return {
            'runs': len(run_ids),
            'built_runs': len(facts),
            'provisional_runs': len(facts.filtered(
                lambda f: f.basis == 'provisional')),
            'asof_fallback': sum(facts.mapped('asof_fallback_count')),
            'untyped_categories': sum(facts.mapped('untyped_category_count')),
            'division_fallback': sum(facts.mapped('division_fallback_count')),
        }
