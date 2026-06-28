# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Contribution rule codes grouped by insurance type and leg.
CONTRIB_MAP = {
    'SI_EMP': ('SI', 'emp'), 'SI_COMP': ('SI', 'comp'),
    'HI_EMP': ('HI', 'emp'), 'HI_COMP': ('HI', 'comp'),
    'UI_EMP': ('UI', 'emp'), 'UI_COMP': ('UI', 'comp'),
    # Payobook demo formula-config codes (underscore-free per converter contract).
    'SIEMP': ('SI', 'emp'), 'SICOMP': ('SI', 'comp'),
    'HIEMP': ('HI', 'emp'), 'HICOMP': ('HI', 'comp'),
    'UIEMP': ('UI', 'emp'), 'UICOMP': ('UI', 'comp'),
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
        # hr.payslip.run has no company_id column in this build — only scope by it
        # when the field actually exists (else the latest run overall).
        run_dom = [('company_id', 'in', co_ids)] if 'company_id' in Run._fields else []
        latest = self._safe(
            lambda: Run.search(run_dom, order='date_end desc, id desc', limit=1),
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

        # ---------- policies + tax tables rosters (config — list all) ----------
        policies = []
        if 'vietnam.insurance.policy' in self.env:
            for p in self._safe(lambda: self.env['vietnam.insurance.policy'].search(
                    [], order='effective_date desc, id desc', limit=120), default=[]):
                policies.append({
                    'id': p.id, 'name': p.name or '—', 'code': p.code or '',
                    'effective': str(p.effective_date or ''), 'end': str(p.end_date or ''),
                    'total_employer': round(getattr(p, 'total_employer_rate', 0) or 0, 2),
                    'total_employee': round(getattr(p, 'total_employee_rate', 0) or 0, 2),
                    'active': bool(p.active),
                })
        tax_tables = []
        if 'vietnam.tax.table' in self.env:
            for t in self._safe(lambda: self.env['vietnam.tax.table'].search(
                    [], order='tax_year desc, id desc', limit=120), default=[]):
                tax_tables.append({
                    'id': t.id, 'name': t.name or '—', 'code': t.code or '',
                    'year': t.tax_year, 'slabs': getattr(t, 'slab_count', 0) or len(t.slab_ids),
                    'personal': t.personal_deduction, 'dependent': t.dependent_deduction,
                    'active': bool(t.active),
                })
        dependents = self._safe(
            lambda: self.env['vietnam.employee.dependent'].search_count([])
            if 'vietnam.employee.dependent' in self.env else 0)

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
            'kpis': {
                'contributions': (actuals or {}).get('grand_total', 0),
                'emp_leg': (actuals or {}).get('emp_total', 0),
                'comp_leg': (actuals or {}).get('comp_total', 0),
                'policies': len(policies), 'tax_tables': len(tax_tables),
                'dependents': dependents,
            },
            'policy': policy,
            'tax': tax,
            'actuals': actuals,
            'policies': policies,
            'tax_tables': tax_tables,
            'launches': launches,
        }

    # ------------------------------------------------------------------ details
    @api.model
    def get_policy_detail(self, policy_id):
        p = self.env['vietnam.insurance.policy'].browse(int(policy_id))
        if not p.exists():
            return {'error': 'Policy not found'}
        rows = [
            {'key': 'SI', 'label': INS_LABEL['SI'], 'employee': p.si_employee_rate,
             'employer': p.si_employer_rate, 'ceiling': p.si_max_salary_ceiling},
            {'key': 'HI', 'label': INS_LABEL['HI'], 'employee': p.hi_employee_rate,
             'employer': p.hi_employer_rate, 'ceiling': p.hi_max_salary_ceiling},
            {'key': 'UI', 'label': INS_LABEL['UI'], 'employee': p.ui_employee_rate,
             'employer': p.ui_employer_rate, 'ceiling': p.ui_max_salary_ceiling},
        ]
        waivers = []
        for f, lbl in [('waive_ui_foreign', 'Waive UI for foreign staff'),
                       ('waive_hi_foreign', 'Waive HI for foreign staff'),
                       ('waive_ui_no_fund_areas', 'Waive UI in no-fund areas'),
                       ('oa_waiver_enabled', 'Occupational-accident waiver')]:
            if getattr(p, f, False):
                waivers.append(lbl)
        return {
            'id': p.id, 'name': p.name or '—', 'code': p.code or '',
            'effective': str(p.effective_date or ''), 'end': str(p.end_date or ''),
            'active': bool(p.active),
            'currency': self.env.company.currency_id.symbol or '',
            'rows': rows,
            'total_employee': round(getattr(p, 'total_employee_rate', 0) or 0, 2),
            'total_employer': round(getattr(p, 'total_employer_rate', 0) or 0, 2),
            'waivers': waivers,
            'error': None,
        }

    @api.model
    def get_tax_detail(self, tax_id):
        t = self.env['vietnam.tax.table'].browse(int(tax_id))
        if not t.exists():
            return {'error': 'Tax table not found'}
        slabs = []
        for s in t.slab_ids.sorted(lambda x: (x.sequence, x.income_from)):
            slabs.append({'from': s.income_from, 'to': s.income_to,
                          'rate': s.tax_rate, 'fixed': s.fixed_amount})
        return {
            'id': t.id, 'name': t.name or '—', 'code': t.code or '', 'year': t.tax_year,
            'active': bool(t.active),
            'currency': self.env.company.currency_id.symbol or '',
            'personal': t.personal_deduction, 'dependent': t.dependent_deduction,
            'slabs': slabs, 'slab_count': len(slabs),
            'error': None,
        }


class PbStatutoryWizard(models.AbstractModel):
    _name = 'pb.statutory.wizard'
    _description = 'Payobook statutory config wizards'

    @api.model
    def get_defaults(self):
        from datetime import date
        return {
            'today': date.today().isoformat(),
            'year': date.today().year,
            'currency': self.env.company.currency_id.symbol or '',
            # Vietnam 2024 defaults
            'policy': {'si_employer': 17.5, 'si_employee': 8.0, 'si_ceiling': 46800000,
                       'hi_employer': 3.0, 'hi_employee': 1.5, 'hi_ceiling': 46800000,
                       'ui_employer': 1.0, 'ui_employee': 1.0, 'ui_ceiling': 93600000},
            'tax': {'personal': 11000000, 'dependent': 4400000},
        }

    @api.model
    def create_policy(self, vals):
        if 'vietnam.insurance.policy' not in self.env:
            return {'error': 'Insurance policy model not installed.'}
        if not (vals.get('name') or '').strip() or not (vals.get('code') or '').strip():
            return {'error': 'Name and code are required.'}
        cvals = {'name': vals['name'].strip(), 'code': vals['code'].strip()}
        if vals.get('effective_date'):
            cvals['effective_date'] = vals['effective_date']
        for k in ('si_employer_rate', 'si_employee_rate', 'si_max_salary_ceiling',
                  'hi_employer_rate', 'hi_employee_rate', 'hi_max_salary_ceiling',
                  'ui_employer_rate', 'ui_employee_rate', 'ui_max_salary_ceiling'):
            if vals.get(k) not in (None, ''):
                cvals[k] = float(vals[k])
        try:
            p = self.env['vietnam.insurance.policy'].create(cvals)
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create policy.'}
        return {'policy_id': p.id, 'name': p.name, 'error': None}

    @api.model
    def create_tax_table(self, vals):
        if 'vietnam.tax.table' not in self.env:
            return {'error': 'Tax table model not installed.'}
        if not (vals.get('name') or '').strip() or not (vals.get('code') or '').strip():
            return {'error': 'Name and code are required.'}
        cvals = {'name': vals['name'].strip(), 'code': vals['code'].strip(),
                 'tax_year': int(vals.get('tax_year') or 0)}
        if vals.get('personal_deduction') not in (None, ''):
            cvals['personal_deduction'] = float(vals['personal_deduction'])
        if vals.get('dependent_deduction') not in (None, ''):
            cvals['dependent_deduction'] = float(vals['dependent_deduction'])
        try:
            t = self.env['vietnam.tax.table'].create(cvals)
            if vals.get('gen_slabs') and hasattr(t, 'action_create_default_slabs'):
                t.action_create_default_slabs()
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create tax table.'}
        return {'tax_id': t.id, 'name': t.name, 'slabs': len(t.slab_ids), 'error': None}
