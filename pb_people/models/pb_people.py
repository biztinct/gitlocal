# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import api, models

_logger = logging.getLogger(__name__)

STATE_LABEL = {
    'draft': 'New', 'open': 'Running', 'close': 'Expired',
    'cancel': 'Cancelled', 'none': 'No contract',
}
ROSTER_LIMIT = 240


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


def _join_date(e):
    """Best-available hire date for an employee."""
    d = getattr(e, 'first_contract_date', False)
    if not d and e.contract_ids:
        starts = [c.date_start for c in e.contract_ids if c.date_start]
        d = min(starts) if starts else False
    if not d:
        cd = getattr(e, 'create_date', False)
        d = cd.date() if cd else False
    return d


class PbPeople(models.AbstractModel):
    _name = 'pb.people'
    _description = 'Payobook People cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("People cockpit metric failed: %s", e)
            return default

    @api.model
    def get_roster_data(self):
        Emp = self.env['hr.employee']
        Contract = self.env['hr.contract']
        company = self.env.company
        cur = company.currency_id
        co_ids = self.env.companies.ids or [company.id]
        EMP_DOM = [('company_id', 'in', co_ids), ('active', '=', True)]
        CON_DOM = [('company_id', 'in', co_ids)]

        # ---- KPIs over the whole active population (aggregates, not per-row) ----
        headcount = self._safe(lambda: Emp.search_count(EMP_DOM))
        running = self._safe(lambda: Contract.search_count(CON_DOM + [('state', '=', 'open')]))
        expiring = self._safe(lambda: Contract.search_count(CON_DOM + [('state', '=', 'close')]))
        with_bank = self._safe(lambda: Emp.search_count(EMP_DOM + [('account_number', '!=', False)]))
        total_wage = 0.0
        try:
            groups = Contract.read_group(CON_DOM + [('state', '=', 'open')], ['wage:sum'], [])
            total_wage = (groups and groups[0].get('wage')) or 0.0
        except Exception:
            total_wage = 0.0

        # department breakdown (for filter chips)
        departments = []
        try:
            dg = Emp.read_group(EMP_DOM, ['department_id'], ['department_id'])
            for g in dg:
                dep = g.get('department_id')
                departments.append({
                    'id': dep[0] if dep else False,
                    'name': dep[1] if dep else 'Unassigned',
                    'count': g.get('department_id_count') or g.get('__count') or 0,
                })
            departments.sort(key=lambda x: -x['count'])
        except Exception:
            departments = []

        # ---- roster page ----
        today = date.today()
        month_start = today.replace(day=1)
        new_hires = 0
        expiring_soon = 0
        people = []
        emps = self._safe(lambda: Emp.search(EMP_DOM, order='name', limit=ROSTER_LIMIT),
                          default=Emp.browse())
        for e in emps:
            try:
                c = e.contract_id
                state = c.state if c else 'none'
                bank = bool(getattr(e, 'account_number', False))
                jd = _join_date(e)
                # days until the running contract ends (None = no end / not running)
                dte = None
                if c and c.state == 'open' and c.date_end:
                    dte = (c.date_end - today).days
                if dte is not None and 0 <= dte <= 30:
                    expiring_soon += 1
                if jd and jd >= month_start:
                    new_hires += 1
                people.append({
                    'id': e.id,
                    'name': e.name or '—',
                    'initials': _initials(e.name),
                    'avatar': '/web/image/hr.employee/%s/avatar_128' % e.id,
                    'job': (e.job_title or (e.job_id.name if e.job_id else '') or '—'),
                    'dept': (e.department_id.name if e.department_id else 'Unassigned'),
                    'manager': e.parent_id.name if e.parent_id else '',
                    'email': e.work_email or '',
                    'state': state,
                    'state_label': STATE_LABEL.get(state, state),
                    'wage': c.wage if c else 0.0,
                    'date_start': str(c.date_start) if (c and c.date_start) else '',
                    'date_end': str(c.date_end) if (c and c.date_end) else '',
                    'join_date': str(jd) if jd else '',
                    'days_to_expiry': dte,
                    'bank': bank,
                    'ready': bool(c and state == 'open' and bank),
                    'contract_id': c.id if c else False,
                })
            except Exception as ex:
                _logger.debug("People roster row failed: %s", ex)
                continue

        # ---- contracts page (for the Contracts toggle) ----
        contracts = []
        try:
            cs = Contract.search(CON_DOM, order='date_start desc, id desc', limit=ROSTER_LIMIT)
            for c in cs:
                contracts.append({
                    'id': c.id,
                    'name': c.name or '—',
                    'employee': c.employee_id.name if c.employee_id else '—',
                    'employee_id': c.employee_id.id if c.employee_id else False,
                    'state': c.state,
                    'state_label': STATE_LABEL.get(c.state, c.state),
                    'wage': c.wage or 0.0,
                    'date_start': str(c.date_start) if c.date_start else '',
                    'date_end': str(c.date_end) if c.date_end else '',
                    'structure': (c.struct_id.name if getattr(c, 'struct_id', False) else
                                  (c.structure_type_id.name if c.structure_type_id else '')),
                })
        except Exception:
            contracts = []

        return {
            'currency': cur.symbol or '',
            'kpis': {
                'headcount': headcount, 'running': running, 'expiring': expiring,
                'total_wage': total_wage, 'with_bank': with_bank,
                'new_hires': new_hires, 'expiring_soon': expiring_soon,
                'ready_pct': round(100 * with_bank / headcount) if headcount else 0,
            },
            'departments': departments,
            'people': people,
            'people_total': headcount,
            'contracts': contracts,
            'contracts_total': self._safe(lambda: Contract.search_count(CON_DOM)),
            'shown': len(people),
        }

    # ------------------------------------------------------------------ bulk
    @api.model
    def bulk_apply(self, emp_ids, op, value=None):
        emps = self.env['hr.employee'].browse([int(i) for i in (emp_ids or [])])
        if not emps:
            return {'error': 'No employees selected.'}
        try:
            if op == 'set_department' and value:
                emps.write({'department_id': int(value)})
            else:
                return {'error': 'Unknown bulk action.'}
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Bulk action failed.'}
        return {'ok': True, 'count': len(emps)}

    # ------------------------------------------------------------------ detail
    @api.model
    def get_employee_detail(self, emp_id):
        e = self.env['hr.employee'].browse(int(emp_id))
        if not e.exists():
            return {'error': 'Employee not found'}
        cur = (e.company_id or self.env.company).currency_id
        c = e.contract_id
        today = date.today()
        jd = _join_date(e)

        # tenure
        tenure_label = '—'
        if jd:
            months = (today.year - jd.year) * 12 + (today.month - jd.month)
            if today.day < jd.day:
                months -= 1
            months = max(months, 0)
            y, m = divmod(months, 12)
            tenure_label = (('%dy ' % y) if y else '') + ('%dm' % m) if (y or m) else '<1m'

        state = c.state if c else 'none'
        dte = None
        if c and c.state == 'open' and c.date_end:
            dte = (c.date_end - today).days

        # contract lifecycle rail (draft -> running -> expired)
        rail_state = {'draft': 'draft', 'open': 'running', 'close': 'expired',
                      'cancel': 'expired'}.get(state, 'draft')
        order = ['draft', 'running', 'expired']
        ci = order.index(rail_state) if rail_state in order else 0
        pipeline = [{'key': s, 'label': s.capitalize(),
                     'done': i < ci, 'current': i == ci} for i, s in enumerate(order)]

        payslips = self._safe(
            lambda: self.env['hr.payslip'].search_count([('employee_id', '=', e.id)]), 0)

        return {
            'id': e.id, 'name': e.name or '—', 'initials': _initials(e.name),
            'avatar': '/web/image/hr.employee/%s/avatar_256' % e.id,
            'job': (e.job_title or (e.job_id.name if e.job_id else '') or '—'),
            'dept': (e.department_id.name if e.department_id else 'Unassigned'),
            'manager': e.parent_id.name if e.parent_id else '',
            'email': e.work_email or '', 'phone': e.work_phone or e.mobile_phone or '',
            'country': e.country_id.name if e.country_id else '',
            'join_date': str(jd) if jd else '', 'tenure_label': tenure_label,
            'currency': cur.symbol or '',
            'contract': {
                'id': c.id if c else False,
                'state': state, 'state_label': STATE_LABEL.get(state, state),
                'wage': c.wage if c else 0.0,
                'date_start': str(c.date_start) if (c and c.date_start) else '',
                'date_end': str(c.date_end) if (c and c.date_end) else '',
                'days_to_expiry': dte,
                'structure': (c.struct_id.name if (c and getattr(c, 'struct_id', False)) else
                              (c.structure_type_id.name if (c and c.structure_type_id) else '')),
            },
            'pipeline': pipeline,
            'statutory': {
                'bank': bool(getattr(e, 'account_number', False)),
                'bank_name': getattr(e, 'bank_name', '') or '',
                'tax': bool(getattr(e, 'subject_to_pit', False)),
                'insurance': bool(getattr(e, 'tham_gia_bhxh', False)),
            },
            'counts': {'contracts': len(e.contract_ids), 'payslips': payslips},
            'error': None,
        }
