# -*- coding: utf-8 -*-
"""pb.fact.builder — the ONLY writer of the payroll fact tables (Phase N).

Design contract
---------------
1. **One aggregate, two consumers.** ``_aggregate_sql()`` is the single source of
   truth for how payslip truth becomes a fact row. The BUILDER runs it to
   populate the tables; the LIVE FALLBACK runs the identical statement when a
   run has not been built yet. ``test_01_aggregate_parity`` asserts both paths
   return the same numbers, so the fast path can never quietly diverge from the
   honest one.

2. **Freshness is checked, not assumed.** Every read calls ``ensure_fresh()``,
   which compares a cheap source fingerprint against the stored token
   UNCONDITIONALLY (never "only if we think something changed") and rebuilds on
   any mismatch. The token is computed for ALL candidate runs in ONE query, so
   the check costs the same whether the board shows 6 runs or 60.

3. **Empty is a valid state.** A run with no payslips still gets a header row
   with a token, so it is not rebuilt on every single read forever (the
   thrash-rebuild bug this guards against is silent and expensive).

4. **History does not move.** Dimensions are resolved AS OF the period end, not
   as of today — ``hr_employee.current_version_id`` means "right now" (C18.80),
   so a transfer would otherwise silently rewrite last quarter's departments on
   the next rebuild. Where an employee has no version dated on or before the
   period end (63% of slips on the live demo world, whose versions are stamped
   at creation while its payroll history runs Apr–Jun), the EARLIEST version is
   used and the row is COUNTED in ``asof_fallback_count`` rather than dropped.
"""

import logging
import time

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# A rebuild deletes and re-inserts a run's facts inside one transaction. Chunk
# the run list so a "rebuild everything" never holds one giant statement.
_BUILD_CHUNK = 12

# Most runs rebuilt inside ONE interactive read. A full 41-run build measured
# ~35 s on the live demo world — far past any sane RPC budget — so a read builds
# what it can and REPORTS the rest as pending rather than blocking or lying.
_ENSURE_CAP = 8

# Runs in these states are excluded entirely (no facts, no header).
_DEAD_STATES = ('cancel',)

# ---------------------------------------------------------------------------
# Shared SQL fragments
# ---------------------------------------------------------------------------
# Resolve the employee's org placement AS OF the period end (see contract 4).
# Prefers the newest version at/before date_end; falls back to the earliest
# version otherwise, and reports which happened via ``asof_ok``.
_ASOF_JOIN = """
    LEFT JOIN LATERAL (
        SELECT hv.department_id, hv.job_id,
               (hv.date_version <= r.date_end) AS asof_ok
          FROM hr_version hv
         WHERE hv.employee_id = p.employee_id
         ORDER BY (hv.date_version <= r.date_end) DESC,
                  CASE WHEN hv.date_version <= r.date_end
                       THEN hv.date_version END DESC NULLS LAST,
                  hv.date_version ASC
         LIMIT 1
    ) v ON TRUE
"""

# hr_payslip_line.name / hr_salary_rule.name / hr_department.name are ALL jsonb
# in Odoo 19 (verified on live) — there is no MIN() for jsonb, and any logic that
# matched on the displayed name would break the moment the UI is Vietnamese.
# The snapshot below is a last-resort label only: the real display name is read
# through the ORM from rule_id, properly translated.
_COMPONENT_LABEL = "MIN(COALESCE(pl.name->>'en_US', pl.code))"


class PbFactBuilder(models.AbstractModel):
    _name = 'pb.fact.builder'
    _description = 'Payroll fact builder'

    # ------------------------------------------------------------------ SQL
    @api.model
    def _has_formula(self):
        """The cycle/division dimensions come from the formula engine, which is
        NOT a hard dependency of this module (a structure-based payroll has no
        hr.formula.config at all). Probed, so the aggregate degrades to empty
        strings instead of blowing up on a missing table. The join key is
        probed too: without ``hr_payslip.formula_config_id`` there is nothing
        to join ON."""
        return ('hr.formula.config' in self.env
                and 'formula_config_id' in self.env['hr.payslip']._fields)

    @api.model
    def _has_config_field(self, fname):
        """Model presence is NOT column presence. ``pb_division`` is added to
        hr.formula.config by pb_demo, which is absent from a real customer DB
        (ABM), so probing only ``hr.formula.config in env`` yielded
        ``column fc.pb_division does not exist``. Probe the FIELD, and only
        count stored ones — a non-stored/related field has no column either."""
        if not self._has_formula():
            return False          # no `fc` alias in the FROM clause at all
        f = self.env['hr.formula.config']._fields.get(fname)
        return bool(f is not None and f.store and f.column_type)

    @api.model
    def _from_sql(self):
        formula = ("LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id"
                   if self._has_formula() else "")
        return """
      FROM hr_payslip_line pl
      JOIN hr_payslip p ON p.id = pl.slip_id AND p.state != 'cancel'
      JOIN hr_payslip_run r ON r.id = p.payslip_run_id
      %s
      LEFT JOIN hr_salary_rule_category c ON c.id = pl.category_id
%s""" % (formula, _ASOF_JOIN)

    @api.model
    def _cycle_sql(self):
        return ("COALESCE(fc.cycle_type, '')"
                if self._has_config_field('cycle_type') else "''")

    @api.model
    def _division_sql(self):
        """Division, in order of truth. The config-level key is the finer grain
        (a run *could* mix divisions); where it does not exist, hr_payslip_run
        carries the same key stored+indexed (pb_payruns is a hard dependency of
        this module, so ``r.pb_division`` is always there) — which is exactly
        what the header build already reads through the ORM."""
        if self._has_config_field('pb_division'):
            return "COALESCE(fc.pb_division, '')"
        return "COALESCE(r.pb_division, '')"

    @api.model
    def _aggregate_sql(self, grain):
        """The ONE aggregate. ``grain`` is 'line' (T1) or 'emp' (T2).

        Returns a statement taking a single ``%s`` parameter: a tuple of run ids.
        Shared verbatim by the builder and the live fallback (contract 1).
        """
        cyc, div, frm = self._cycle_sql(), self._division_sql(), self._from_sql()
        if grain == 'line':
            return """
                SELECT r.id                                   AS run_id,
                       MAX(p.company_id)                      AS company_id,
                       {cyc}                                  AS cycle,
                       {div}                                  AS division,
                       v.department_id                        AS department_id,
                       pl.category_id                         AS category_id,
                       COALESCE(c.category_type, 'allowance') AS category_type,
                       pl.code                                AS code,
                       pl.salary_rule_id                      AS rule_id,
                       {label}                                AS component_name,
                       SUM(pl.total)                          AS amount,
                       COUNT(DISTINCT p.employee_id)          AS headcount,
                       COUNT(*)                               AS line_count
                {frm}
                 WHERE r.id IN %s
                 GROUP BY r.id, {cyc}, {div}, v.department_id, pl.category_id,
                          COALESCE(c.category_type, 'allowance'), pl.code,
                          pl.salary_rule_id
            """.format(cyc=cyc, div=div, label=_COMPONENT_LABEL, frm=frm)
        if grain == 'emp':
            return """
                SELECT r.id                                   AS run_id,
                       MAX(p.company_id)                      AS company_id,
                       {cyc}                                  AS cycle,
                       {div}                                  AS division,
                       p.employee_id                          AS employee_id,
                       v.department_id                        AS department_id,
                       v.job_id                               AS job_id,
                       COALESCE(c.category_type, 'allowance') AS category_type,
                       SUM(pl.total)                          AS amount
                {frm}
                 WHERE r.id IN %s
                 GROUP BY r.id, {cyc}, {div}, p.employee_id, v.department_id,
                          v.job_id, COALESCE(c.category_type, 'allowance')
            """.format(cyc=cyc, div=div, frm=frm)
        raise ValueError('unknown grain %r' % (grain,))

    # -------------------------------------------------------------- freshness
    @api.model
    def _token(self, run_ids):
        """{run_id: fingerprint} for every given run, in ONE query.

        Deliberately built from ``hr_payslip`` only (27,989 rows, indexed on
        payslip_run_id) and NOT from ``hr_payslip_line``: fingerprinting 711k
        lines would cost the very 11.3 s full scan this whole module exists to
        avoid. Recomputing a payslip always rewrites the slip itself, so the
        slip fingerprint moves whenever its lines do; the ``dirty`` flag set by
        the run write hook covers the rest.
        """
        out = {}
        if not run_ids:
            return out
        self.env.cr.execute("""
            SELECT r.id, r.state, r.write_date,
                   COUNT(p.id), MAX(p.write_date), COALESCE(SUM(p.id), 0)
              FROM hr_payslip_run r
              LEFT JOIN hr_payslip p
                     ON p.payslip_run_id = r.id AND p.state != 'cancel'
             WHERE r.id IN %s
             GROUP BY r.id, r.state, r.write_date
        """, (tuple(run_ids),))
        for rid, state, rwrite, nslips, maxwrite, idsum in self.env.cr.fetchall():
            # id-sum catches a delete+create of the same COUNT of payslips.
            out[rid] = '%s|%s|%s|%s|%s' % (state or '', rwrite, nslips,
                                           maxwrite, idsum)
        return out

    @api.model
    def ensure_fresh(self, run_ids, cap=_ENSURE_CAP):
        """Rebuild any run whose facts are missing, stale or flagged dirty.

        Returns ``(ready_ids, pending_ids)``.

        The token comparison is UNCONDITIONAL — never "only if we think
        something changed" — which is what makes a fast answer safe.

        At most ``cap`` runs are rebuilt per call so an interactive request can
        never turn into the 35 s full rebuild (41 runs on the live demo world).
        Anything left over is returned as PENDING and is excluded from the
        caller's query: a period that is not ready is reported to the user, not
        silently folded in as a zero. Pass ``cap=None`` to build everything
        (the cron and the explicit Rebuild button do).
        """
        run_ids = [int(r) for r in (run_ids or [])]
        if not run_ids:
            return set(), []
        tokens = self._token(run_ids)
        # A run that vanished between the caller's search and here.
        run_ids = [r for r in run_ids if r in tokens]
        if not run_ids:
            return set(), []

        Fact = self.env['pb.fact.run'].sudo()
        built = {f.run_id.id: f for f in Fact.search([('run_id', 'in', run_ids)])}
        stale = [rid for rid in run_ids
                 if rid not in built
                 or built[rid].dirty
                 or built[rid].token != tokens[rid]]
        pending = []
        if stale:
            if cap is not None and len(stale) > cap:
                stale, pending = stale[:cap], stale[cap:]
            _logger.info('pb_explorer: rebuilding %s run(s) of %s (%s pending)',
                         len(stale), len(run_ids), len(pending))
            self.build_runs(stale, tokens=tokens)
        ready = set(run_ids) - set(pending)
        return ready, pending

    # ---------------------------------------------------------------- build
    @api.model
    def build_runs(self, run_ids, tokens=None):
        """(Re)build the facts for the given runs. The only writer."""
        run_ids = [int(r) for r in (run_ids or [])]
        if not run_ids:
            return 0
        tokens = tokens or self._token(run_ids)
        done = 0
        for i in range(0, len(run_ids), _BUILD_CHUNK):
            chunk = run_ids[i:i + _BUILD_CHUNK]
            done += self._build_chunk(chunk, tokens)
        return done

    def _build_chunk(self, run_ids, tokens):
        t0 = time.time()
        cr = self.env.cr
        Run = self.env['hr.payslip.run'].sudo()
        runs = Run.browse(run_ids).exists()
        if not runs:
            return 0
        live = [r for r in runs if (r.state or '') not in _DEAD_STATES]
        dead_ids = [r.id for r in runs if r.id not in {x.id for x in live}]

        Fact = self.env['pb.fact.run'].sudo()
        # Cancelled runs keep NO facts at all — drop the header and cascade.
        if dead_ids:
            Fact.search([('run_id', 'in', dead_ids)]).unlink()
        if not live:
            return 0

        live_ids = tuple(r.id for r in live)
        # Replace, never merge: the cascade clears T1/T2 with the header's rows.
        Fact.search([('run_id', 'in', list(live_ids))]).unlink()

        # ---- headers ---------------------------------------------------
        coverage = self._coverage(live_ids)
        headers = {}
        for run in live:
            cov = coverage.get(run.id, {})
            start = run.date_start or run.date_end
            month = start.replace(day=1) if start else False
            hdr = Fact.create({
                'run_id': run.id,
                'company_id': cov.get('company_id') or self.env.company.id,
                'name': run.name or '',
                'date_start': run.date_start,
                'date_end': run.date_end,
                'month': month,
                'year': start.year if start else 0,
                'quarter': '%s-Q%s' % (start.year, (start.month - 1) // 3 + 1)
                           if start else '',
                'cycle': cov.get('cycle') or '',
                'division': run.pb_division or cov.get('division') or '',
                'division_label': run.pb_division_label or '',
                'state': run.state or 'draft',
                'basis': 'approved' if (run.state or '') == 'done' else 'provisional',
                'employee_count': run.pb_employee_count or 0,
                'net_total': run.pb_total_net or 0.0,
                'token': tokens.get(run.id) or '',
                'dirty': False,
                'built_on': fields.Datetime.now(),
                'source_slip_count': cov.get('slips', 0),
                'source_line_count': cov.get('lines', 0),
                'asof_fallback_count': cov.get('asof_fallback', 0),
                'untyped_category_count': cov.get('untyped', 0),
            })
            headers[run.id] = hdr

        # ---- T1 + T2 via the shared aggregate --------------------------
        n_line = self._insert_facts('line', live_ids, headers)
        self._insert_facts('emp', live_ids, headers)

        ms = int((time.time() - t0) * 1000)
        for run_id, hdr in headers.items():
            hdr.write({'build_ms': ms, 'fact_line_count': n_line.get(run_id, 0)})
        _logger.info('pb_explorer: built %s run(s) in %s ms', len(headers), ms)
        return len(headers)

    def _insert_facts(self, grain, run_ids, headers):
        """Run the shared aggregate and INSERT the result. Returns {run_id: n}."""
        cr = self.env.cr
        cr.execute(self._aggregate_sql(grain), (run_ids,))
        rows = cr.fetchall()
        if not rows:
            return {}
        uid = self.env.uid
        now = fields.Datetime.now()
        counts = {}
        if grain == 'line':
            table = 'pb_fact_line'
            cols = ('fact_run_id', 'run_id', 'company_id', 'month', 'year',
                    'quarter', 'cycle', 'division', 'basis', 'department_id',
                    'category_id', 'category_type', 'code', 'rule_id',
                    'component_name', 'amount', 'headcount', 'line_count',
                    'create_uid', 'create_date', 'write_uid', 'write_date')
            vals = []
            for (run_id, company_id, cycle, division, dept_id, cat_id,
                 cat_type, code, rule_id, comp_name, amount, heads, nlines) in rows:
                h = headers.get(run_id)
                if not h:
                    continue
                counts[run_id] = counts.get(run_id, 0) + 1
                vals.append((h.id, run_id, company_id or h.company_id.id, h.month,
                             h.year, h.quarter, cycle, division, h.basis, dept_id,
                             cat_id, cat_type, code, rule_id, comp_name,
                             amount or 0.0, heads or 0, nlines or 0,
                             uid, now, uid, now))
        else:
            table = 'pb_fact_emp'
            cols = ('fact_run_id', 'run_id', 'company_id', 'month', 'year',
                    'quarter', 'cycle', 'division', 'basis', 'employee_id',
                    'department_id', 'job_id', 'category_type', 'amount',
                    'create_uid', 'create_date', 'write_uid', 'write_date')
            vals = []
            for (run_id, company_id, cycle, division, emp_id, dept_id, job_id,
                 cat_type, amount) in rows:
                h = headers.get(run_id)
                if not h:
                    continue
                counts[run_id] = counts.get(run_id, 0) + 1
                vals.append((h.id, run_id, company_id or h.company_id.id, h.month,
                             h.year, h.quarter, cycle, division, h.basis, emp_id,
                             dept_id, job_id, cat_type, amount or 0.0,
                             uid, now, uid, now))
        if not vals:
            return counts
        placeholder = '(' + ','.join(['%s'] * len(cols)) + ')'
        args = []
        for v in vals:
            args.extend(v)
        cr.execute(
            'INSERT INTO %s (%s) VALUES %s' % (
                table, ','.join(cols), ','.join([placeholder] * len(vals))),
            args)
        return counts

    # ------------------------------------------------------------- coverage
    def _coverage(self, run_ids):
        """Per-run source counts + the honesty counters, in ONE query."""
        formula = ("LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id"
                   if self._has_formula() else "")
        self.env.cr.execute("""
            SELECT r.id,
                   MAX(p.company_id),
                   COUNT(DISTINCT p.id),
                   COUNT(pl.id),
                   COUNT(DISTINCT p.id) FILTER (WHERE NOT v.asof_ok),
                   COUNT(DISTINCT pl.category_id)
                     FILTER (WHERE c.id IS NOT NULL AND c.category_type IS NULL),
                   MIN({cyc}),
                   MIN({div})
              FROM hr_payslip_run r
              JOIN hr_payslip p
                ON p.payslip_run_id = r.id AND p.state != 'cancel'
              LEFT JOIN hr_payslip_line pl ON pl.slip_id = p.id
              {formula}
              LEFT JOIN hr_salary_rule_category c ON c.id = pl.category_id
              {asof}
             WHERE r.id IN %s
             GROUP BY r.id
        """.format(cyc=self._cycle_sql(), div=self._division_sql(),
                   formula=formula, asof=_ASOF_JOIN), (run_ids,))
        out = {}
        for (rid, company_id, slips, lines, fallback, untyped,
             cycle, division) in self.env.cr.fetchall():
            out[rid] = {
                'company_id': company_id, 'slips': slips or 0,
                'lines': lines or 0, 'asof_fallback': fallback or 0,
                'untyped': untyped or 0, 'cycle': cycle or '',
                'division': division or '',
            }
        return out

    # --------------------------------------------------------------- manual
    @api.model
    def cron_build(self, batch=24):
        """Background top-up so the fact tables self-heal between visits — a
        user who never presses Rebuild still finds the board ready."""
        runs = self.env['hr.payslip.run'].sudo().search(
            [('state', 'not in', list(_DEAD_STATES))], order='date_end desc')
        if not runs:
            return 0
        _ready, pending = self.ensure_fresh(runs.ids, cap=batch)
        if pending:
            _logger.info('pb_explorer cron: %s run(s) still pending', len(pending))
        return len(runs) - len(pending)

    @api.model
    def rebuild_all(self, limit=None):
        """Full rebuild — the maintenance entry point (also used by tests)."""
        runs = self.env['hr.payslip.run'].sudo().search(
            [('state', 'not in', list(_DEAD_STATES))],
            order='date_end desc', limit=limit)
        # Force it: drop the headers so ensure_fresh cannot short-circuit.
        self.env['pb.fact.run'].sudo().search(
            [('run_id', 'in', runs.ids)]).unlink()
        return self.build_runs(runs.ids)
