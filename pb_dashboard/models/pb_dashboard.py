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

        employees = safe(lambda: env['hr.employee'].search_count([]))
        contracts = (safe(lambda: env['hr.contract'].search_count([('state', '=', 'open')]))
                     or safe(lambda: env['hr.contract'].search_count([])))

        # ---- Latest pay run ----
        run = safe(lambda: env['hr.payslip.run'].search([], order='id desc', limit=1), None)
        run_data = {'name': '—', 'slips': 0, 'done': 0, 'pending': 0, 'readiness': 0, 'state': ''}
        if run:
            slips = run.slip_ids
            total = len(slips)
            done = len(slips.filtered(lambda s: s.state == 'done'))
            pend = len(slips.filtered(lambda s: s.state in ('level1', 'level2')))
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

        # ---- Company analytics (from analytics dashboard, if present) ----
        adash = safe(lambda: env['hr.analytics.dashboard'].search([], limit=1), None)
        payroll = contributions = avg = 0
        headcount = employees
        if adash:
            payroll = safe(lambda: adash.total_personnel_cost)
            contributions = safe(lambda: adash.total_contributions)
            avg = safe(lambda: adash.average_salary)
            headcount = safe(lambda: adash.total_headcount) or employees

        # ---- Formula engine ----
        cfgs = safe(lambda: env['hr.formula.config'].search([]), None)
        f_count = len(cfgs) if cfgs else 0
        rules = sum(c.rule_count for c in cfgs) if cfgs else 0
        active = len(cfgs.filtered(lambda c: c.state == 'active')) if cfgs else 0
        tests = sum(len(c.test_result_ids) for c in cfgs) if cfgs else 0
        f_health = round(active / f_count * 100) if f_count else 0

        return {
            'user': env.user.name or 'there',
            'company': env.company.name or 'Payobook',
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
