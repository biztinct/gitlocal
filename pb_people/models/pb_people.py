# -*- coding: utf-8 -*-
import logging
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
                    'name': dep[1] if dep else 'Unassigned',
                    'count': g.get('department_id_count') or g.get('__count') or 0,
                })
            departments.sort(key=lambda x: -x['count'])
        except Exception:
            departments = []

        # ---- roster page ----
        people = []
        emps = self._safe(lambda: Emp.search(EMP_DOM, order='name', limit=ROSTER_LIMIT),
                          default=Emp.browse())
        for e in emps:
            try:
                c = e.contract_id
                state = c.state if c else 'none'
                bank = bool(getattr(e, 'account_number', False))
                people.append({
                    'id': e.id,
                    'name': e.name or '—',
                    'initials': _initials(e.name),
                    'job': (e.job_title or (e.job_id.name if e.job_id else '') or '—'),
                    'dept': (e.department_id.name if e.department_id else 'Unassigned'),
                    'email': e.work_email or '',
                    'state': state,
                    'state_label': STATE_LABEL.get(state, state),
                    'wage': c.wage if c else 0.0,
                    'date_start': str(c.date_start) if (c and c.date_start) else '',
                    'date_end': str(c.date_end) if (c and c.date_end) else '',
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
                'ready_pct': round(100 * with_bank / headcount) if headcount else 0,
            },
            'departments': departments,
            'people': people,
            'people_total': headcount,
            'contracts': contracts,
            'contracts_total': self._safe(lambda: Contract.search_count(CON_DOM)),
            'shown': len(people),
        }
