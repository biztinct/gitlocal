# -*- coding: utf-8 -*-
"""Demo analytics cockpit data — the dashboards the base app didn't ship.

Computes division comparison, salary distribution, gender & age, cost-centre,
overtime, bonuses, employer-vs-employee cost, statutory, and a Jan–Jul trend,
straight from the generated demo payslips. Read-only AbstractModel; all queries
are company-scoped and wrapped so a missing slice degrades to an empty card.
"""
import logging
from datetime import date

from odoo import api, models

from . import demo_catalog as cat

_logger = logging.getLogger(__name__)
_DIVNAME = {k: dv['name_en'] for k, dv in cat.DIVISIONS.items()}


class PbDemoAnalytics(models.AbstractModel):
    _name = 'pb.demo.analytics'
    _description = 'Payobook Demo Analytics'

    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception as e:  # pragma: no cover
            _logger.debug('pb_demo analytics slice failed: %s', e)
            return default if default is not None else []

    @api.model
    def get_analytics_data(self):
        companies = tuple(self.env.companies.ids) or (self.env.company.id,)
        cr = self.env.cr
        # Reference month = latest demo run month present (fallback June 2026).
        cr.execute("""
            SELECT max(p.date_from) FROM hr_payslip p
            JOIN hr_employee e ON e.id = p.employee_id
            WHERE e.is_demo = true AND p.company_id IN %s
        """, (companies,))
        ref = (cr.fetchone() or [None])[0] or date(2026, 6, 1)

        return {
            'period': ref.strftime('%B %Y'),
            'kpis': self._safe(lambda: self._kpis(companies, ref), {}),
            'by_division': self._safe(lambda: self._by_division(companies, ref)),
            'salary_dist': self._safe(lambda: self._salary_dist(companies)),
            'gender': self._safe(lambda: self._gender(companies)),
            'age': self._safe(lambda: self._age(companies)),
            'cost_centre': self._safe(lambda: self._cost_centre(companies, ref)),
            'employer_employee': self._safe(lambda: self._employer_employee(companies, ref), {}),
            'trend': self._safe(lambda: self._trend(companies)),
        }

    # ----- KPI band -----
    def _kpis(self, companies, ref):
        cr = self.env.cr
        cr.execute("""
            SELECT
              count(distinct e.id) AS headcount,
              coalesce(sum(case when pl.code='GROSS' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) AS gross,
              coalesce(sum(case when pl.code='NET' then pl.total else 0 end),0) AS net,
              coalesce(sum(case when c.code in ('INSCO','COMP') and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) AS employer
            FROM hr_payslip p
            JOIN hr_employee e ON e.id=p.employee_id AND e.is_demo=true
            JOIN hr_payslip_line pl ON pl.slip_id=p.id
            JOIN hr_salary_rule_category c ON c.id=pl.category_id
            LEFT JOIN hr_formula_config fc ON fc.id=p.formula_config_id
            WHERE p.company_id IN %s AND p.date_from=%s
        """, (companies, ref))
        r = cr.fetchone() or (0, 0, 0, 0)
        hc = r[0] or 0
        return {'headcount': hc, 'gross': r[1] or 0, 'net': r[2] or 0,
                'employer_cost': r[3] or 0,
                'avg_cost': round((r[1] or 0) / hc) if hc else 0}

    # ----- by division -----
    def _by_division(self, companies, ref):
        cr = self.env.cr
        cr.execute("""
            SELECT e.division,
              count(distinct e.id) AS headcount,
              coalesce(sum(case when pl.code='GROSS' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) AS gross,
              coalesce(sum(case when pl.code='NET' then pl.total else 0 end),0) AS net,
              coalesce(sum(case when cat.code='OT' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) AS ot,
              coalesce(sum(case when cat.code='BON' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) AS bonus
            FROM hr_payslip p
            JOIN hr_employee e ON e.id=p.employee_id AND e.is_demo=true
            JOIN hr_payslip_line pl ON pl.slip_id=p.id
            JOIN hr_salary_rule_category cat ON cat.id=pl.category_id
            LEFT JOIN hr_formula_config fc ON fc.id=p.formula_config_id
            WHERE p.company_id IN %s AND p.date_from=%s AND e.division IS NOT NULL
            GROUP BY e.division ORDER BY gross DESC
        """, (companies, ref))
        return [{'label': _DIVNAME.get(d, d) or '—', 'headcount': h, 'gross': g, 'net': n, 'ot': ot, 'bonus': b}
                for d, h, g, n, ot, b in cr.fetchall()]

    # ----- salary distribution (basic wage buckets) -----
    def _salary_dist(self, companies):
        cr = self.env.cr
        cr.execute("""
            SELECT width_bucket(c.wage, 0, 100000000, 10) AS b, count(*)
            FROM hr_contract c JOIN hr_employee e ON e.id=c.employee_id
            WHERE e.is_demo=true AND c.company_id IN %s AND c.state='open'
            GROUP BY b ORDER BY b
        """, (companies,))
        rows = dict(cr.fetchall())
        out = []
        for i in range(1, 11):
            lo = (i - 1) * 10
            out.append({'label': '%d–%dM' % (lo, lo + 10), 'count': rows.get(i, 0)})
        return out

    # ----- gender -----
    def _gender(self, companies):
        cr = self.env.cr
        cr.execute("""
            SELECT coalesce(e.sex,'other'), count(*)
            FROM hr_employee e WHERE e.is_demo=true AND e.company_id IN %s
            GROUP BY e.sex
        """, (companies,))
        labels = {'male': 'Male', 'female': 'Female', 'other': 'Other'}
        return [{'label': labels.get(s, s or 'Other'), 'count': n} for s, n in cr.fetchall()]

    # ----- age bands -----
    def _age(self, companies):
        cr = self.env.cr
        cr.execute("""
            SELECT band, count(*) FROM (
              SELECT CASE
                WHEN extract(year from age(e.birthday)) < 25 THEN '<25'
                WHEN extract(year from age(e.birthday)) < 35 THEN '25–34'
                WHEN extract(year from age(e.birthday)) < 45 THEN '35–44'
                WHEN extract(year from age(e.birthday)) < 55 THEN '45–54'
                ELSE '55+' END AS band
              FROM hr_employee e
              WHERE e.is_demo=true AND e.company_id IN %s AND e.birthday IS NOT NULL
            ) t GROUP BY band
        """, (companies,))
        order = {'<25': 0, '25–34': 1, '35–44': 2, '45–54': 3, '55+': 4}
        rows = [{'label': b, 'count': n} for b, n in cr.fetchall()]
        return sorted(rows, key=lambda r: order.get(r['label'], 9))

    # ----- cost centre -----
    def _cost_centre(self, companies, ref):
        cr = self.env.cr
        cr.execute("""
            SELECT coalesce(pl.costcenter,'—') cc,
              coalesce(sum(case when pl.code='GROSS' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) gross
            FROM hr_payslip p
            JOIN hr_employee e ON e.id=p.employee_id AND e.is_demo=true
            JOIN hr_payslip_line pl ON pl.slip_id=p.id
            LEFT JOIN hr_formula_config fc ON fc.id=p.formula_config_id
            WHERE p.company_id IN %s AND p.date_from=%s
            GROUP BY pl.costcenter ORDER BY gross DESC LIMIT 12
        """, (companies, ref))
        return [{'label': cc, 'gross': g} for cc, g in cr.fetchall()]

    # ----- employer vs employee cost -----
    def _employer_employee(self, companies, ref):
        cr = self.env.cr
        cr.execute("""
            SELECT
              coalesce(sum(case when cat.code='NET' then pl.total else 0 end),0) net,
              coalesce(sum(case when cat.code='INS' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then -pl.total else 0 end),0) emp_ins,
              coalesce(sum(case when cat.code='TAX' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then -pl.total else 0 end),0) tax,
              coalesce(sum(case when cat.code in ('INSCO','COMP') and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) employer
            FROM hr_payslip p
            JOIN hr_employee e ON e.id=p.employee_id AND e.is_demo=true
            JOIN hr_payslip_line pl ON pl.slip_id=p.id
            JOIN hr_salary_rule_category cat ON cat.id=pl.category_id
            LEFT JOIN hr_formula_config fc ON fc.id=p.formula_config_id
            WHERE p.company_id IN %s AND p.date_from=%s
        """, (companies, ref))
        r = cr.fetchone() or (0, 0, 0, 0)
        return {'net': r[0] or 0, 'employee_insurance': r[1] or 0,
                'tax': r[2] or 0, 'employer_contributions': r[3] or 0}

    # ----- Jan–Jul trend -----
    def _trend(self, companies):
        cr = self.env.cr
        cr.execute("""
            SELECT p.date_from,
              coalesce(sum(case when pl.code='GROSS' and coalesce(fc.cycle_type,'end_cycle')='end_cycle' then pl.total else 0 end),0) gross,
              coalesce(sum(case when pl.code='NET' then pl.total else 0 end),0) net,
              count(distinct e.id) headcount
            FROM hr_payslip p
            JOIN hr_employee e ON e.id=p.employee_id AND e.is_demo=true
            JOIN hr_payslip_line pl ON pl.slip_id=p.id
            LEFT JOIN hr_formula_config fc ON fc.id=p.formula_config_id
            WHERE p.company_id IN %s
            GROUP BY p.date_from ORDER BY p.date_from
        """, (companies,))
        return [{'label': d.strftime('%b'), 'gross': g, 'net': n, 'headcount': h}
                for d, g, n, h in cr.fetchall()]
