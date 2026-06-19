# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Contribution rule codes grouped by insurance type and leg.
CONTRIB_MAP = {
    'SI_EMP': ('SI', 'emp'), 'SI_COMP': ('SI', 'comp'),
    'HI_EMP': ('HI', 'emp'), 'HI_COMP': ('HI', 'comp'),
    'UI_EMP': ('UI', 'emp'), 'UI_COMP': ('UI', 'comp'),
}
INS_LABEL = {'SI': 'Social Insurance (BHXH)', 'HI': 'Health Insurance (BHYT)',
             'UI': 'Unemployment (BHTN)'}

LAUNCH_CANDIDATES = [
    ('pb_hr_payroll_vietnam.action_vietnam_insurance_policy',
     'Insurance Policies', 'Rates, ceilings & effective dates', 'shield'),
    ('pb_hr_payroll_vietnam.action_vietnam_tax_table',
     'Tax Tables', 'Progressive brackets & deductions', 'percent'),
    ('pb_hr_payroll_vietnam.action_vietnam_insurance_analytics',
     'Insurance Analytics', 'Contribution trends & breakdowns', 'bar-chart'),
    ('pb_hr_payroll_vietnam.action_vietnam_insurance_adjustment',
     'Insurance Adjustments', 'Mid-period corrections', 'sliders'),
    ('pb_hr_payroll_vietnam.action_vietnam_employee_dependent',
     'Dependents', 'Personal relief registration', 'users'),
]


class PbStatutory(models.AbstractModel):
    _name = 'pb.statutory'
    _description = 'Payobook Statutory cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Statutory metric failed: %s", e)
            return default

    @api.model
    def get_statutory_data(self):
        company = self.env.company
        cur = company.currency_id
        co_ids = self.env.companies.ids or [company.id]

        # ---------- insurance policy ----------
        policy = None
        if 'vietnam.insurance.policy' in self.env:
            Pol = self.env['vietnam.insurance.policy']
            rec = self._safe(
                lambda: Pol.search([('company_id', 'in', co_ids), ('active', '=', True)],
                                   order='effective_date desc', limit=1),
                default=Pol.browse())
            if rec:
                policy = {
                    'name': rec.name, 'code': rec.code or '',
                    'effective': str(rec.effective_date or ''),
                    'rows': [
                        {'key': 'SI', 'label': INS_LABEL['SI'],
                         'employee': rec.si_employee_rate, 'employer': rec.si_employer_rate,
                         'ceiling': rec.si_max_salary_ceiling},
                        {'key': 'HI', 'label': INS_LABEL['HI'],
                         'employee': rec.hi_employee_rate, 'employer': rec.hi_employer_rate,
                         'ceiling': rec.hi_max_salary_ceiling},
                        {'key': 'UI', 'label': INS_LABEL['UI'],
                         'employee': rec.ui_employee_rate, 'employer': rec.ui_employer_rate,
                         'ceiling': rec.ui_max_salary_ceiling},
                    ],
                }
                te = sum(r['employee'] for r in policy['rows'])
                tr = sum(r['employer'] for r in policy['rows'])
                policy['total_employee'] = round(te, 2)
                policy['total_employer'] = round(tr, 2)
                policy['total_combined'] = round(te + tr, 2)

        # ---------- tax table ----------
        tax = None
        if 'vietnam.tax.table' in self.env:
            Tax = self.env['vietnam.tax.table']
            rec = self._safe(
                lambda: Tax.search([('company_id', 'in', co_ids), ('active', '=', True)],
                                   order='tax_year desc', limit=1),
                default=Tax.browse())
            if rec:
                slabs = []
                try:
                    for s in rec.slab_ids.sorted(lambda x: (x.sequence, x.income_from)):
                        slabs.append({
                            'from': s.income_from, 'to': s.income_to,
                            'rate': s.tax_rate, 'fixed': s.fixed_amount,
                        })
                except Exception:
                    slabs = []
                tax = {
                    'name': rec.name, 'year': rec.tax_year,
                    'personal_deduction': rec.personal_deduction,
                    'dependent_deduction': rec.dependent_deduction,
                    'slabs': slabs,
                }

        # ---------- contribution actuals (latest run) ----------
        actuals = None
        Run = self.env['hr.payslip.run']
        latest = self._safe(
            lambda: Run.search([('company_id', 'in', co_ids)],
                               order='date_end desc, id desc', limit=1),
            default=Run.browse())
        if latest:
            buckets = {k: {'emp': 0.0, 'comp': 0.0} for k in ('SI', 'HI', 'UI')}
            try:
                g = self.env['hr.payslip.line'].read_group(
                    [('slip_id.payslip_run_id', '=', latest.id),
                     ('code', 'in', list(CONTRIB_MAP.keys()))],
                    ['total:sum'], ['code'])
                for row in g:
                    code = row.get('code')
                    amt = abs(row.get('total') or 0.0)
                    if code in CONTRIB_MAP:
                        ins, leg = CONTRIB_MAP[code]
                        buckets[ins][leg] += amt
            except Exception:
                pass
            emp_total = sum(b['emp'] for b in buckets.values())
            comp_total = sum(b['comp'] for b in buckets.values())
            covered = self._safe(
                lambda: self.env['hr.payslip'].search_count(
                    [('payslip_run_id', '=', latest.id)]))
            actuals = {
                'run_name': latest.name or '',
                'rows': [{'key': k, 'label': INS_LABEL[k],
                          'emp': buckets[k]['emp'], 'comp': buckets[k]['comp'],
                          'total': buckets[k]['emp'] + buckets[k]['comp']}
                         for k in ('SI', 'HI', 'UI')],
                'emp_total': emp_total, 'comp_total': comp_total,
                'grand_total': emp_total + comp_total, 'covered': covered,
            }

        # ---------- launch buttons ----------
        launches = []
        for xmlid, label, desc, icon in LAUNCH_CANDIDATES:
            try:
                if self.env.ref(xmlid, raise_if_not_found=False):
                    launches.append({'xmlid': xmlid, 'label': label,
                                     'desc': desc, 'icon': icon})
            except Exception:
                continue

        return {
            'currency': cur.symbol or '',
            'company': company.name,
            'policy': policy,
            'tax': tax,
            'actuals': actuals,
            'launches': launches,
        }
