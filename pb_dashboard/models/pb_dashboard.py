# -*- coding: utf-8 -*-
"""The home dashboard's one data call.

TWO RULES GOVERN THIS FILE, and both of them are about honesty.

1. NO FABRICATED NUMBER, EVER. A brand-new tenant sees zeros and a helpful
   empty state; it never sees a company that does not exist. The legacy
   analytics fallback that used to fill these in was a hard-coded sample dict
   and it reached a real customer's screen.

2. NO HARD DEPENDENCY ON ANOTHER COCKPIT. The manifest declares `web`,
   `om_hr_payroll` and `pb_hr_payroll_base` and nothing else. The activation
   checklist below asks questions of the learning module and of the import
   module, and both of those questions are asked through `optional()`, which
   answers "not on this database" instead of raising. There is no python
   import of either module anywhere in here, and there must never be one:
   this dashboard is the first screen of every tenant, including the lean
   ones.
"""
from odoo import api, models

# The two scenarios the activation checklist watches, under the namespace
# `learn.progress` stores them in (pb_learn/models/learn_progress.py
# SCENARIO_PREFIX). Strings, not imports — see rule 2 above.
SCENARIO_PREFIX = 'scenario:'
SC_WELCOME = 'sc_welcome'
SC_PAYRUN = 'sc_payrun'


class PbDashboard(models.AbstractModel):
    _name = 'pb.dashboard'
    _description = 'Payobook Dashboard data provider'

    @api.model
    def get_dashboard_data(self):
        env = self.env

        def safe(fn, default=0):
            try:
                return fn()
            except Exception:
                return default

        def optional(model, fn, default=0):
            """Read a model another module owns, or report `default`.

            THE REGISTRY IS THE PROBE, not the module table: what the caller
            needs is for `env[model]` not to raise, and that is exactly what
            this tests. It needs no rights at all, which an
            `ir.module.module` read under superuser did (pb_learn ledger,
            run D1).

            Everything this dashboard reads from pb_learn or from the import
            module goes through here. That is a structural property rather
            than a promise — `tests/test_activation.py::test_04` walks the
            syntax tree of this file and fails if a single one of those reads
            sits outside an `optional()` call.
            """
            if model not in env:
                return default
            return safe(fn, default)

        cdom = [('company_id', 'in', env.companies.ids)]
        employees = safe(lambda: env['hr.employee'].search_count(cdom))
        contracts = (safe(lambda: env['hr.contract'].search_count(cdom + [('state', '=', 'open')]))
                     or safe(lambda: env['hr.contract'].search_count(cdom)))

        # ---- Latest pay run ----
        # NOT company-scoped, and that is a property of the model rather than
        # an oversight: `hr.payslip.run` carries no `company_id` field in this
        # codebase — om_hr_payroll does not declare one and none of the eight
        # modules that inherit it adds one. A `company_id` domain here would
        # raise on every call, which `safe()` would turn into a silent zero.
        runs = safe(lambda: env['hr.payslip.run'].search_count([]))
        run = safe(lambda: env['hr.payslip.run'].search([], order='id desc', limit=1), None)
        run_data = {'name': '—', 'slips': 0, 'done': 0, 'pending': 0, 'readiness': 0, 'state': ''}
        if run:
            # Indexed count-only queries (payslip_run_id is indexed) — never load
            # the run's payslips into memory.
            P = env['hr.payslip']
            total = safe(lambda: P.search_count([('payslip_run_id', '=', run.id)]))
            done = safe(lambda: P.search_count([('payslip_run_id', '=', run.id), ('state', '=', 'done')]))
            pend = safe(lambda: P.search_count([('payslip_run_id', '=', run.id),
                                                ('state', 'in', ['level1', 'level2'])]))
            run_data = {
                'name': run.name or '—',
                'slips': total,
                'done': done,
                'pending': pend,
                'readiness': round(done / total * 100) if total else 0,
                'state': run.state or '',
            }

        # ---- Pending approvals ----
        pending = safe(lambda: env['payroll.analytics'].search_count([('state', '=', 'ready')]))
        if not pending:
            pending = safe(lambda: env['hr.payslip'].search_count([('state', 'in', ['level1', 'level2'])]))

        # ---- Company KPIs from the latest payroll month (real payslip data) ----
        # Aggregate the most recent month's payslips directly (SQL, company-scoped)
        # rather than trusting the legacy analytics snapshot, which can be stale.
        companies = tuple(env.companies.ids) or (env.company.id,)
        payroll = contributions = avg = 0
        headcount = employees
        cr = env.cr
        try:
            cr.execute("SELECT max(date_from) FROM hr_payslip WHERE company_id IN %s", (companies,))
            ref = (cr.fetchone() or [None])[0]
            if ref:
                # Scope to END-cycle payslips: with a Mid+End cycle both carry the
                # full GROSS, so counting both would double the payroll/headcount.
                cr.execute("""
                    SELECT count(DISTINCT p.employee_id),
                           coalesce(sum(CASE WHEN pl.code='GROSS' THEN pl.total ELSE 0 END), 0),
                           coalesce(sum(CASE WHEN cat.code IN ('INSCO', 'COMP') THEN pl.total ELSE 0 END), 0)
                    FROM hr_payslip p
                    JOIN hr_payslip_line pl ON pl.slip_id = p.id
                    JOIN hr_salary_rule_category cat ON cat.id = pl.category_id
                    LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id
                    WHERE p.company_id IN %s AND p.date_from = %s
                      AND (fc.cycle_type = 'end_cycle' OR fc.id IS NULL)
                """, (companies, ref))
                hc, payroll, contributions = cr.fetchone() or (0, 0.0, 0.0)
                hc = hc or 0
                avg = round(payroll / hc) if hc else 0
        except Exception:
            payroll = contributions = avg = 0
        # NO FALLBACK. A database with no payslips reports zeros. The legacy
        # analytics-dashboard record used to fill these in, and its figures were
        # a hard-coded sample dict, so a brand-new tenant was shown a company
        # that does not exist (LEARNOS ledger rule 1 — honest zeros). This
        # module must not read that model at all; the phase greps for it.

        # ---- Formula engine ----
        cfgs = safe(lambda: env['hr.formula.config'].search([]), None)
        f_count = len(cfgs) if cfgs else 0
        rules = sum(c.rule_count for c in cfgs) if cfgs else 0
        active = len(cfgs.filtered(lambda c: c.state == 'active')) if cfgs else 0
        tests = sum(len(c.test_result_ids) for c in cfgs) if cfgs else 0
        f_health = round(active / f_count * 100) if f_count else 0

        # ---- Presentation context ----
        # The money formatter used to hard-code `₫`. Ship the company's own
        # currency instead; the browser only formats what it is given.
        cur = env.company.currency_id
        currency = {
            'symbol': (cur.symbol if cur else None) or '',
            'position': (cur.position if cur else None) or 'before',
        }
        # ---- Activation checklist (LEARNOS Phase 3) ----
        # FIVE STEPS, FIVE REAL COUNTS. Nothing here is remembered in a flag,
        # inferred from a button press or carried in a browser: every item
        # reports the state of the database, so a step somebody finished in
        # another tab is already ticked when this loads, and a step nobody has
        # done cannot be ticked by pressing its button and coming back.
        #
        # The panel is shown while activation is incomplete and disappears for
        # good once the tenant has a pay run — which is also item 5, so the
        # last tick and the last render are the same event.
        def scenario_done(key):
            """Has THIS learner finished this walkthrough, in any of its three
            modes? One row per learner per key (learn.progress has a unique
            constraint on the pair), so a count is the whole answer."""
            return bool(optional('learn.progress', lambda: env['learn.progress'].search_count([
                ('user_id', '=', env.uid),
                ('key', '=', SCENARIO_PREFIX + key),
                ('state', '=', 'done'),
            ])))

        # Is the learning module on this database at all? The same registry
        # probe `optional()` uses, asked once, because it decides whether the
        # two learning steps are OFFERED rather than only whether they can be
        # read. A step whose predicate can never be satisfied is a step that
        # sits unticked forever, which is worse than a shorter list.
        learn_here = 'learn.progress' in env

        # HEADCOUNT > 1, NOT > 0. The golden template ships the admin's
        # `hr.employee` row (id 1, renamed per tenant), and provisioning does
        # not create it — so a tenant that has never added anybody still
        # reports one employee. Contracts carry the "is this tenant empty"
        # question everywhere else in this file for the same reason.
        batches = optional('hr.payroll.import.batch',
                           lambda: env['hr.payroll.import.batch'].search_count(cdom))
        activation_items = []
        if learn_here:
            activation_items.append({'key': 'meet', 'done': scenario_done(SC_WELCOME)})
        activation_items.append({'key': 'employee', 'done': employees > 1})
        activation_items.append({'key': 'import', 'done': bool(contracts) or bool(batches)})
        if learn_here:
            activation_items.append({'key': 'practice', 'done': scenario_done(SC_PAYRUN)})
        activation_items.append({'key': 'real', 'done': runs > 0})

        return {
            'user': env.user.name or 'there',
            'company': env.company.name or 'Payobook',
            'currency': currency,
            'activation': {'show': not runs, 'items': activation_items},
            'kpis': {
                'headcount': headcount,
                'contracts': contracts,
                'payroll': payroll,
                'contributions': contributions,
                'avg': avg,
                'pending': pending,
            },
            'run': run_data,
            'formula': {'count': f_count, 'rules': rules, 'active': active,
                        'tests': tests, 'health': f_health},
        }
