# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Statutory contribution rule codes (employee + employer legs)
CONTRIB_CODES = ['SI_EMP', 'SI_COMP', 'HI_EMP', 'HI_COMP', 'UI_EMP', 'UI_COMP']

# Quick-launch destinations — only those that resolve at runtime are surfaced.
REPORT_CANDIDATES = [
    ('pb_hr_payroll_analytics.action_open_hr_analytics_dashboard',
     'Analytics Dashboard', 'Headcount, cost & trend analytics', 'bar-chart-2'),
    ('payroll_analytics_approval.action_payroll_analytics_reports',
     'Payroll Reports', 'Analytics, bank export & comparison reports', 'file-text'),
    ('payroll_analytics_approval.action_payroll_analytics',
     'Analytics Records', 'Period-by-period payroll analytics dataset', 'database'),
]


class PbInsights(models.AbstractModel):
    _name = 'pb.insights'
    _description = 'Payobook Insights cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Insights metric failed: %s", e)
            return default

    @api.model
    def _net_for_run(self, run_id):
        """Sum of NET payslip lines for one payslip run."""
        try:
            g = self.env['hr.payslip.line'].read_group(
                [('slip_id.payslip_run_id', '=', run_id), ('code', '=', 'NET')],
                ['total:sum'], [])
            return (g and g[0].get('total')) or 0.0
        except Exception:
            return 0.0

    @api.model
    def get_insights_data(self):
        company = self.env.company
        cur = company.currency_id
        co_ids = self.env.companies.ids or [company.id]
        Emp = self.env['hr.employee']
        Contract = self.env['hr.contract']
        Payslip = self.env['hr.payslip']
        PSLine = self.env['hr.payslip.line']
        Run = self.env['hr.payslip.run']
        EMP_DOM = [('company_id', 'in', co_ids), ('active', '=', True)]
        CON_OPEN = [('company_id', 'in', co_ids), ('state', '=', 'open')]

        headcount = self._safe(lambda: Emp.search_count(EMP_DOM))
        active_contracts = self._safe(lambda: Contract.search_count(CON_OPEN))
        total_wage = 0.0
        try:
            g = Contract.read_group(CON_OPEN, ['wage:sum'], [])
            total_wage = (g and g[0].get('wage')) or 0.0
        except Exception:
            total_wage = 0.0
        avg_salary = (total_wage / active_contracts) if active_contracts else 0.0

        # ---- latest payslip run (real paid figures) ----
        latest = self._safe(
            lambda: Run.search([('company_id', 'in', co_ids)],
                               order='date_end desc, id desc', limit=1),
            default=Run.browse())
        run_name = ''
        monthly_payroll = 0.0
        employees_paid = 0
        statutory_total = 0.0
        statutory_emp = 0.0
        statutory_comp = 0.0
        if latest:
            run_name = latest.name or ''
            monthly_payroll = self._net_for_run(latest.id)
            employees_paid = self._safe(
                lambda: Payslip.search_count([('payslip_run_id', '=', latest.id)]))
            try:
                g = PSLine.read_group(
                    [('slip_id.payslip_run_id', '=', latest.id),
                     ('code', 'in', CONTRIB_CODES)],
                    ['total:sum'], ['code'])
                for row in g:
                    amt = abs(row.get('total') or 0.0)
                    code = row.get('code')
                    statutory_total += amt
                    if code and code.endswith('_EMP'):
                        statutory_emp += amt
                    else:
                        statutory_comp += amt
            except Exception:
                pass
        if not monthly_payroll:
            monthly_payroll = total_wage  # fallback to contracted base

        # ---- payroll trend: last 6 runs ----
        trend = []
        try:
            runs = Run.search([('company_id', 'in', co_ids)],
                              order='date_end desc, id desc', limit=6)
            for r in runs:
                trend.append({
                    'label': (r.name or '')[:18],
                    'date': str(r.date_end or r.date_start or ''),
                    'net': self._net_for_run(r.id),
                })
            trend.reverse()  # oldest -> newest for the chart
        except Exception:
            trend = []
        trend_max = max([t['net'] for t in trend], default=0.0) or 1.0

        # ---- department cost split (open contracts) ----
        departments = []
        try:
            dg = Contract.read_group(CON_OPEN, ['wage:sum'], ['department_id'])
            for g in dg:
                dep = g.get('department_id')
                departments.append({
                    'name': dep[1] if dep else 'Unassigned',
                    'wage': g.get('wage') or 0.0,
                    'count': g.get('department_id_count') or g.get('__count') or 0,
                })
            departments.sort(key=lambda x: -x['wage'])
            departments = departments[:8]
        except Exception:
            departments = []
        dept_max = max([d['wage'] for d in departments], default=0.0) or 1.0

        # ---- validated quick-launch destinations ----
        reports = []
        for xmlid, label, desc, icon in REPORT_CANDIDATES:
            try:
                if self.env.ref(xmlid, raise_if_not_found=False):
                    reports.append({'xmlid': xmlid, 'label': label,
                                    'desc': desc, 'icon': icon})
            except Exception:
                continue

        return {
            'currency': cur.symbol or '',
            'company': company.name,
            'run_name': run_name,
            'kpis': {
                'monthly_payroll': monthly_payroll,
                'headcount': headcount,
                'employees_paid': employees_paid,
                'avg_salary': avg_salary,
                'statutory_total': statutory_total,
                'statutory_emp': statutory_emp,
                'statutory_comp': statutory_comp,
                'active_contracts': active_contracts,
            },
            'trend': trend,
            'trend_max': trend_max,
            'departments': departments,
            'dept_max': dept_max,
            'reports': reports,
        }
