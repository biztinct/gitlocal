# -*- coding: utf-8 -*-
from odoo import api, models


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

        cdom = [('company_id', 'in', env.companies.ids)]
        employees = safe(lambda: env['hr.employee'].search_count(cdom))
        contracts = (safe(lambda: env['hr.contract'].search_count(cdom + [('state', '=', 'open')]))
                     or safe(lambda: env['hr.contract'].search_count(cdom)))

        # ---- Latest pay run ----
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
        # Whether the guided tour exists on THIS database — the setup panel's
        # first row is only offered when there is something behind it.
        has_learn = bool(safe(lambda: env['ir.module.module'].sudo().search_count(
            [('name', '=', 'pb_learn'), ('state', '=', 'installed')])))

        return {
            'user': env.user.name or 'there',
            'company': env.company.name or 'Payobook',
            'currency': currency,
            'has_learn': has_learn,
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
