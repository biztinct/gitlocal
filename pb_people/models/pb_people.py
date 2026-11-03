# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

STATE_LABEL = {
    'draft': 'New', 'open': 'Running', 'close': 'Expired',
    'cancel': 'Cancelled', 'none': 'No contract',
}
ROSTER_LIMIT = 240
#: Rows per page on the filtered roster ("Show more" loads the next page).
PAGE_SIZE = 60


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
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook People cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("People cockpit metric failed: %s", e)
            return default

    @api.model
    def _pay_symbol(self, e, cache=None):
        """The money sign for this person's wage: their pay scheme's currency.

        A Singapore-paid person's wage is in S$, not the company's dong. The
        scheme comes from the stored "Paid by" (`pb_paid_by_id`, GROUP P2);
        a database without it, or a person nobody pays yet, gets the
        company's money as before. `cache` (scheme id -> sign) keeps a roster
        page to one lookup per scheme.
        """
        company_sign = (e.company_id or self.env.company).currency_id.symbol or ''
        scheme = e.pb_paid_by_id if 'pb_paid_by_id' in e._fields else False
        if not scheme or not hasattr(scheme, 'scheme_currency'):
            return company_sign
        if cache is not None and scheme.id in cache:
            return cache[scheme.id]
        sign = self._safe(
            lambda: scheme.sudo().scheme_currency().get('symbol') or '',
            default='') or company_sign
        if cache is not None:
            cache[scheme.id] = sign
        return sign

    @api.model
    def _roster_kpis(self):
        """The quiet numbers + department list, over every active employee."""
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

        # The quiet numbers and what pressing one lists are both read over
        # EVERY active employee (the roster below is capped), so a figure
        # never says 4,510 while the list behind it holds 240.
        today = date.today()
        month_start = today.replace(day=1)
        soon = today + timedelta(days=30)
        status_dom = {
            'running': [('contract_id.state', '=', 'open')],
            'expiring': [('contract_id.state', '=', 'open'),
                         ('contract_id.date_end', '>=', str(today)),
                         ('contract_id.date_end', '<=', str(soon))],
            'notready': ['|', '|', ('contract_id', '=', False),
                         ('contract_id.state', '!=', 'open'),
                         ('account_number', '=', False)],
        }
        if 'first_contract_date' in Emp._fields:
            status_dom['new'] = [('first_contract_date', '>=', str(month_start))]
        expiring_soon = self._safe(lambda: Emp.search_count(EMP_DOM + status_dom['expiring']))
        not_ready = self._safe(lambda: Emp.search_count(EMP_DOM + status_dom['notready']))
        new_hires = (self._safe(lambda: Emp.search_count(EMP_DOM + status_dom['new']))
                     if 'new' in status_dom else None)
        # department breakdown (bulk "Move to department")
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
        return {
            'currency': cur.symbol or '',
            'kpis': {
                'headcount': headcount, 'running': running, 'expiring': expiring,
                'total_wage': total_wage, 'with_bank': with_bank,
                'new_hires': new_hires, 'expiring_soon': expiring_soon,
                'not_ready': not_ready,
                'ready_pct': round(100 * with_bank / headcount) if headcount else 0,
            },
            'departments': departments,
            'status_dom': status_dom,
            'emp_dom': EMP_DOM,
            'con_dom': CON_DOM,
        }

    @api.model
    def get_roster_data(self, status=None):
        """The pre-filter-panel call (numbers + the first 240 people + 240
        contracts). Kept for anything still calling it; Employees now uses
        get_roster_head + get_roster_page."""
        Emp = self.env['hr.employee']
        Contract = self.env['hr.contract']
        head = self._roster_kpis()
        status_dom, EMP_DOM, CON_DOM = head['status_dom'], head['emp_dom'], head['con_dom']
        kpis = head['kpis']
        headcount = kpis['headcount']
        new_hires = kpis['new_hires']
        today = date.today()
        month_start = today.replace(day=1)
        LIST_DOM = EMP_DOM + status_dom.get(status or '', [])

        # ---- roster page ----
        count_new = new_hires is None
        new_hires = new_hires or 0
        people = []
        pay_signs = {}
        emps = self._safe(lambda: Emp.search(LIST_DOM, order='name', limit=ROSTER_LIMIT),
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
                # no stored hire date on this build: count what is listed
                if count_new and jd and jd >= month_start:
                    new_hires += 1
                people.append({
                    'id': e.id,
                    'currency': self._pay_symbol(e, pay_signs),
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

        kpis = dict(kpis, new_hires=new_hires)
        return {
            'currency': head['currency'],
            'kpis': kpis,
            'departments': head['departments'],
            'people': people,
            # how many match what is being listed (everyone, or the figure pressed)
            'people_total': (self._safe(lambda: Emp.search_count(LIST_DOM))
                             if status in status_dom else headcount),
            'contracts': contracts,
            'contracts_total': self._safe(lambda: Contract.search_count(CON_DOM)),
            'shown': len(people),
        }

    # ============================================================ filter panel
    # The Employees list is the first screen on the shared filter panel
    # (pb_filter_kit, FILTER program 2026-10-30). Everything is counted on the
    # server over every active employee: the roster used to load 240 people
    # and filter those in the browser, so a department chip said 208 while
    # the list behind it could hold 11.

    def _pbf_model(self):
        return 'hr.employee'

    def _pbf_screen(self):
        return 'employees'

    def _pbf_base_domain(self):
        company = self.env.company
        co_ids = self.env.companies.ids or [company.id]
        return [('company_id', 'in', co_ids), ('active', '=', True)]

    def _pbf_search_fields(self):
        return ['name', 'job_title', 'department_id.name', 'work_email',
                'barcode', 'vietnam_employee_id']

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_sorts(self):
        sorts = [
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
            {'key': 'name_desc', 'label': _('Name, Z to A'), 'order': 'name desc, id desc'},
        ]
        if 'first_contract_date' in self.env['hr.employee']._fields:
            sorts += [
                {'key': 'newest', 'label': _('Newest joiners first'),
                 'order': 'first_contract_date desc nulls last, name asc'},
                {'key': 'longest', 'label': _('Longest serving first'),
                 'order': 'first_contract_date asc nulls last, name asc'},
            ]
        return sorts

    def _pbf_spec(self):
        not_ready = ['|', '|', ('contract_id', '=', False),
                     ('contract_id.state', '!=', 'open'), ('account_number', '=', False)]
        return [
            # ---- pinned: the three questions asked before every pay run
            {'key': 'status', 'label': _('Contract status'), 'icon': 'fileText',
             'group': 'contract', 'type': 'choice', 'pinned': True,
             'requires': ['contract_id.state'],
             'options': [
                 {'value': 'open', 'label': _('Running'), 'tone': 'green',
                  'domain': [('contract_id.state', '=', 'open')]},
                 {'value': 'draft', 'label': _('Not started yet'), 'tone': 'blue',
                  'domain': [('contract_id.state', '=', 'draft')]},
                 {'value': 'close', 'label': _('Ended'), 'tone': 'slate',
                  'domain': [('contract_id.state', '=', 'close')]},
                 {'value': 'cancel', 'label': _('Cancelled'), 'tone': 'rose',
                  'domain': [('contract_id.state', '=', 'cancel')]},
                 {'value': 'none', 'label': _('No contract'), 'tone': 'amber',
                  'domain': [('contract_id', '=', False)]},
             ]},
            {'key': 'ready', 'label': _('Payroll-ready'), 'icon': 'shieldCheck',
             'group': 'pay', 'type': 'choice', 'pinned': True,
             'requires': ['contract_id.state', 'account_number'],
             'help': _('Ready means a running contract and bank details on file.'),
             'options': [
                 {'value': 'yes', 'label': _('Ready to be paid'), 'tone': 'green',
                  'domain': [('contract_id.state', '=', 'open'), ('account_number', '!=', False)]},
                 {'value': 'no', 'label': _('Missing something'), 'tone': 'amber',
                  'domain': not_ready},
             ]},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id', 'pinned': True,
             'none_label': _('No department')},
            # ---- more filters, grouped people > work > contract > pay > dates
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'people', 'type': 'many2one', 'path': 'job_id',
             'none_label': _('No job position')},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'parent_id',
             'none_label': _('No manager')},
            {'key': 'nationality', 'label': _('Nationality'), 'icon': 'globe',
             'group': 'people', 'type': 'many2one', 'path': 'country_id',
             'none_label': _('Not recorded')},
            {'key': 'gender', 'label': _('Gender'), 'icon': 'users',
             'group': 'people', 'type': 'selection', 'path': 'sex',
             'none_label': _('Not recorded')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
            {'key': 'work_country', 'label': _('Work country'), 'icon': 'mapPin',
             'group': 'work', 'type': 'many2one', 'path': 'company_id.partner_id.country_id',
             'none_label': _('Not recorded')},
            {'key': 'location', 'label': _('Work location'), 'icon': 'mapPin',
             'group': 'work', 'type': 'many2one', 'path': 'work_location_id',
             'none_label': _('No work location')},
            {'key': 'division', 'label': _('Division'), 'icon': 'layers',
             'group': 'work', 'type': 'char', 'path': 'division',
             'none_label': _('No division')},
            {'key': 'type', 'label': _('Employee type'), 'icon': 'idCard',
             'group': 'work', 'type': 'selection', 'path': 'employee_type'},
            {'key': 'contract_type', 'label': _('Contract type'), 'icon': 'file',
             'group': 'contract', 'type': 'many2one', 'path': 'contract_id.contract_type_id',
             'none_label': _('Not set')},
            {'key': 'probation', 'label': _('Trial period'), 'icon': 'hourglass',
             'group': 'contract', 'type': 'selection', 'path': 'pb_probation_state',
             'none_label': _('Not recorded')},
            {'key': 'ends', 'label': _('Contract ends'), 'icon': 'calendarClock',
             'group': 'contract', 'type': 'date', 'path': 'contract_id.date_end',
             'presets': 'future', 'none_label': _('No end date')},
            {'key': 'structure', 'label': _('Pay structure'), 'icon': 'sigma',
             'group': 'pay', 'type': 'many2one', 'path': 'contract_id.struct_id',
             'none_label': _('No pay structure')},
            {'key': 'grade', 'label': _('Grade'), 'icon': 'award',
             'group': 'pay', 'type': 'char', 'path': 'pb_grade',
             'none_label': _('No grade')},
            {'key': 'bank', 'label': _('Bank details'), 'icon': 'creditCard',
             'group': 'pay', 'type': 'choice', 'requires': ['account_number'],
             'options': [
                 {'value': 'yes', 'label': _('On file'), 'tone': 'green',
                  'domain': [('account_number', '!=', False)]},
                 {'value': 'no', 'label': _('Missing'), 'tone': 'amber',
                  'domain': [('account_number', '=', False)]},
             ]},
            {'key': 'wage', 'label': _('Monthly wage'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'contract_id.wage', 'unit': 'money'},
            {'key': 'joined', 'label': _('Joined'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'first_contract_date',
             'presets': 'past', 'none_label': _('No start date')},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All employees'), 'icon': 'users', 'filters': {}},
            {'key': 'notready', 'label': _('Not payroll-ready'), 'filters': {'ready': ['no']}},
            {'key': 'ending', 'label': _('Ending within 30 days'),
             'filters': {'status': ['open'], 'ends': {'preset': 'next_30'}}},
            {'key': 'joined', 'label': _('Joined this month'),
             'filters': {'joined': {'preset': 'this_month'}}},
            {'key': 'trial', 'label': _('On trial period'),
             'filters': {'probation': ['extended', 'in_probation']}},
        ]

    @api.model
    def _roster_row(self, e, today, month_start, pay_signs=None):
        """One card on the roster (shared by the paged list and the old call)."""
        c = e.contract_id
        state = c.state if c else 'none'
        bank = bool(getattr(e, 'account_number', False))
        jd = _join_date(e)
        dte = None
        if c and c.state == 'open' and c.date_end:
            dte = (c.date_end - today).days
        return {
            'id': e.id,
            'currency': self._pay_symbol(e, pay_signs),
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
        }

    @api.model
    def get_roster_head(self):
        """The numbers line and the department list (bulk "Move to"), without
        the roster: the filter panel loads the list itself."""
        d = self._roster_kpis()
        kpis = dict(d['kpis'], new_hires=d['kpis']['new_hires'] or 0)
        return {'currency': d['currency'], 'kpis': kpis, 'departments': d['departments']}

    @api.model
    def get_roster_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of the roster for the filter panel's current state."""
        Emp = self.env['hr.employee']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        domain = self.pbf_domain(filters or {}, search)
        order = self.pbf_order(sort) or 'name'
        emps = Emp.search(domain, order=order, offset=offset, limit=limit)
        today = date.today()
        month_start = today.replace(day=1)
        rows = []
        pay_signs = {}
        for e in emps:
            try:
                rows.append(self._roster_row(e, today, month_start, pay_signs))
            except Exception as ex:  # noqa: BLE001 — one bad card never blanks the list
                _logger.debug("People roster row failed: %s", ex)
        return {'rows': rows, 'total': Emp.search_count(domain), 'offset': offset}

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
            'currency': self._pay_symbol(e),
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
