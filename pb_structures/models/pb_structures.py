# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

STATE_LABEL = {'draft': 'Draft', 'active': 'Active', 'deprecated': 'Deprecated', 'archived': 'Archived'}
STATE_CLS = {'active': 'ok', 'draft': 'info', 'deprecated': 'warn', 'archived': 'muted'}
CAT_LABEL = {
    'basic': 'Basic Salary', 'allowance': 'Allowances', 'deduction': 'Deductions',
    'tax': 'Taxes', 'social_security': 'Social Security', 'net': 'Net Salary',
    'employer_cost': 'Employer Costs',
}
CAT_ORDER = ['basic', 'allowance', 'deduction', 'tax', 'social_security', 'employer_cost', 'net']
AMOUNT_LABEL = {'fix': 'Fixed', 'percentage': 'Percentage', 'code': 'Python'}
SCHEDULE_LABEL = {
    'monthly': 'Monthly', 'quarterly': 'Quarterly', 'semi-annually': 'Semi-annual',
    'annually': 'Annual', 'weekly': 'Weekly', 'bi-weekly': 'Bi-weekly', 'bi-monthly': 'Bi-monthly',
}
ROSTER_LIMIT = 240


def _country(s):
    return (getattr(s, 'payroll_country_code', False) or
            (s.country_id.code if s.country_id else '') or '—')


def _state(s):
    return getattr(s, 'structure_state', False) or ('active' if s.active else 'archived')


class PbStructures(models.AbstractModel):
    _name = 'pb.structures'
    _description = 'Payobook salary structures cockpit'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Structures metric failed: %s", e)
            return default

    @api.model
    def get_board(self):
        S = self.env['hr.payroll.structure']
        Rule = self.env['hr.salary.rule']
        Cat = self.env['hr.salary.rule.category']
        # Structures are payroll CONFIG (frequently shared across companies), so
        # we list them all rather than filtering by the active company.
        DOM = []

        total_rules = self._safe(lambda: Rule.search_count([]))
        total_cats = self._safe(lambda: Cat.search_count([]))

        structures = []
        countries = {}
        emp_total = 0
        recs = self._safe(lambda: S.search(DOM, order='name', limit=ROSTER_LIMIT), default=S.browse())
        for s in recs:
            try:
                cc = _country(s)
                st = _state(s)
                emp = getattr(s, 'employee_count', 0) or 0
                emp_total += emp
                countries[cc] = countries.get(cc, 0) + 1
                structures.append({
                    'id': s.id, 'name': s.name or '—', 'code': s.code or '',
                    'country': cc,
                    'schedule': SCHEDULE_LABEL.get(getattr(s, 'schedule_pay', ''), getattr(s, 'schedule_pay', '') or '—'),
                    'rules': len(s.rule_ids), 'employees': emp,
                    'is_base': bool(getattr(s, 'is_base_structure', False)),
                    'state': st, 'state_label': STATE_LABEL.get(st, st),
                    'updated': str(s.write_date or '')[:10],
                })
            except Exception as ex:
                _logger.debug("Structure row failed: %s", ex)
                continue

        country_chips = [{'name': k, 'count': v} for k, v in
                         sorted(countries.items(), key=lambda x: -x[1])]

        return {
            'kpis': {
                'structures': len(structures), 'rules': total_rules,
                'categories': total_cats, 'employees': emp_total,
                'countries': len([c for c in countries if c != '—']),
            },
            'countries': country_chips,
            'structures': structures,
            'total': self._safe(lambda: S.search_count(DOM)),
            'shown': len(structures),
        }

    # ------------------------------------------------------------------ detail
    @api.model
    def get_structure_detail(self, structure_id):
        s = self.env['hr.payroll.structure'].browse(int(structure_id))
        if not s.exists():
            return {'error': 'Structure not found'}
        st = _state(s)

        # group rules by category_type
        groups = {}
        for r in s.rule_ids.sorted(lambda x: (x.sequence, x.id)):
            ctype = getattr(r.category_id, 'category_type', False) or 'allowance'
            val = ''
            if r.amount_select == 'fix':
                val = '%s' % (r.amount_fix or 0)
            elif r.amount_select == 'percentage':
                val = '%s%%' % (r.amount_percentage or 0)
            elif r.amount_select == 'code':
                val = 'Python'
            er = getattr(r, 'employer_rate', 0) or 0
            ee = getattr(r, 'employee_rate', 0) or 0
            groups.setdefault(ctype, []).append({
                'id': r.id, 'name': r.name or '—', 'code': r.code or '',
                'amount_select': r.amount_select,
                'amount_label': AMOUNT_LABEL.get(r.amount_select, r.amount_select),
                'value': val, 'employer_rate': er, 'employee_rate': ee,
                'appears': bool(r.appears_on_payslip),
            })
        rule_groups = [{'key': k, 'label': CAT_LABEL.get(k, k), 'rules': groups[k]}
                       for k in CAT_ORDER if k in groups]
        # any leftover category types not in CAT_ORDER
        for k in groups:
            if k not in CAT_ORDER:
                rule_groups.append({'key': k, 'label': CAT_LABEL.get(k, k), 'rules': groups[k]})

        return {
            'id': s.id, 'name': s.name or '—', 'code': s.code or '',
            'country': _country(s),
            'schedule': SCHEDULE_LABEL.get(getattr(s, 'schedule_pay', ''), getattr(s, 'schedule_pay', '') or '—'),
            'state': st, 'state_label': STATE_LABEL.get(st, st), 'state_cls': STATE_CLS.get(st, 'muted'),
            'is_base': bool(getattr(s, 'is_base_structure', False)),
            'counts': {
                'rules': len(s.rule_ids), 'employees': getattr(s, 'employee_count', 0) or 0,
                'categories': len(rule_groups),
            },
            'rule_groups': rule_groups,
            'error': None,
        }


def _sel(env, model, field):
    try:
        f = env[model]._fields.get(field)
        return [{'id': k, 'name': v} for k, v in (f.selection or [])]
    except Exception:
        return []


class PbStructureWizard(models.AbstractModel):
    _name = 'pb.structures.wizard'
    _description = 'Payobook structure/rule wizards'

    @api.model
    def get_defaults(self):
        return {
            'countries': _sel(self.env, 'hr.payroll.structure', 'payroll_country_code'),
            'schedules': _sel(self.env, 'hr.payroll.structure', 'schedule_pay'),
        }

    @api.model
    def create_structure(self, vals):
        if not (vals.get('name') or '').strip():
            return {'error': 'A name is required.'}
        if not (vals.get('code') or '').strip():
            return {'error': 'A reference code is required.'}
        cvals = {'name': vals['name'].strip(), 'code': vals['code'].strip()}
        if vals.get('payroll_country_code'):
            cvals['payroll_country_code'] = vals['payroll_country_code']
        if vals.get('schedule_pay'):
            cvals['schedule_pay'] = vals['schedule_pay']
        if vals.get('is_base'):
            cvals['is_base_structure'] = True
        if 'structure_state' in self.env['hr.payroll.structure']._fields:
            cvals['structure_state'] = 'active' if vals.get('activate') else 'draft'
        try:
            s = self.env['hr.payroll.structure'].create(cvals)
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create structure.'}
        return {'structure_id': s.id, 'name': s.name, 'error': None}

    @api.model
    def get_rule_defaults(self, structure_id=False):
        Cat = self.env['hr.salary.rule.category']
        cats = [{'id': c.id, 'name': c.name, 'code': c.code or ''}
                for c in Cat.search([], order='name', limit=200)]
        s = self.env['hr.payroll.structure'].browse(int(structure_id)) if structure_id else None
        return {
            'structure_id': s.id if s else False,
            'structure_name': s.name if s else '',
            'categories': cats,
            'amount_types': [{'id': 'fix', 'name': 'Fixed amount'},
                             {'id': 'percentage', 'name': 'Percentage (%)'}],
        }

    @api.model
    def add_rule(self, vals):
        if not vals.get('structure_id'):
            return {'error': 'No structure selected.'}
        if not (vals.get('name') or '').strip() or not (vals.get('code') or '').strip():
            return {'error': 'Rule name and code are required.'}
        if not vals.get('category_id'):
            return {'error': 'A category is required.'}
        amt = vals.get('amount_select') or 'fix'
        rvals = {
            'name': vals['name'].strip(), 'code': vals['code'].strip(),
            'category_id': int(vals['category_id']),
            'amount_select': amt,
            'appears_on_payslip': bool(vals.get('appears', True)),
            'sequence': int(vals.get('sequence') or 100),
        }
        if amt == 'fix':
            rvals['amount_fix'] = float(vals.get('value') or 0.0)
        elif amt == 'percentage':
            rvals['amount_percentage'] = float(vals.get('value') or 0.0)
        try:
            rule = self.env['hr.salary.rule'].create(rvals)
            self.env['hr.payroll.structure'].browse(int(vals['structure_id'])).write(
                {'rule_ids': [(4, rule.id)]})
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not add rule.'}
        return {'rule_id': rule.id, 'name': rule.name, 'structure_id': int(vals['structure_id']), 'error': None}
