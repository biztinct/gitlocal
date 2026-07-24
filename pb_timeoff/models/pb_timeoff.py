# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.timeoff — RPC facade for the Leave Command Center cockpit (Phase K §3b).

An AbstractModel (no table) exposing an org-wide HR leave board: who's out, the
approval queue, a department×day month heatmap, and a paged balance board — plus
apply-on-behalf. Facade doctrine (C18.17/C18.55a): this surface NEVER writes a
state field and NEVER sudo's a MUTATION. Every change (act / apply_on_behalf)
rides core hr.leave's OWN gated actions AS THE REAL USER; the model's own errors
surface verbatim. The READ board is a consolidation surface — like the audit
console (C18.65) it collects sudo BEHIND the ``_require_officer`` gate, so an
officer-set member who lacks a specific leave-model ACL (e.g. a payroll manager
without the hr_holidays group) still sees the org-wide board; company scoping
(C18.11/18) is preserved because ``env.companies`` is unchanged under sudo. The
one-permission-world split: reads sudo, mutations real-user.
"""

from datetime import date, timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

# Officer set (verified against the installed repo hr_holidays — the officer
# xmlid is hr_holidays.group_hr_holidays_user; reported in the handover §8).
_OFFICER_GROUPS = (
    'hr_holidays.group_hr_holidays_user',
    'hr.group_hr_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)
# Odoo palette index → hex, for the leave-type chip (hr.leave.type.color is an
# Integer palette index, not a hex string).
_COLOR_HEX = {
    0: '#6B7280', 1: '#EF4444', 2: '#F59E0B', 3: '#EAB308', 4: '#06B6D4',
    5: '#8B5CF6', 6: '#D6A77A', 7: '#14B8A6', 8: '#3B82F6', 9: '#EC4899',
    10: '#22C55E', 11: '#A855F7',
}
_QUEUE_STATES = ('confirm', 'validate1')
_LIVE_STATES = ('confirm', 'validate1', 'validate')   # heatmap = pending + approved
_HEATMAP_SCAN = 3000     # bounded leave scan for the heatmap (surfaced)
_BALANCE_PAGE = 30       # employees per balance page (4.5k world — never unbounded)
_TODAY_CARDS = 16        # on-leave-today card cap


class PbTimeoff(models.AbstractModel):
    _name = 'pb.timeoff'
    _description = 'Leave Command Center'

    # ------------------------------------------------------------- access
    @api.model
    def _require_officer(self):
        u = self.env.user
        if u.has_group('base.group_system'):
            return
        for g in _OFFICER_GROUPS:
            try:
                if u.has_group(g):
                    return
            except (ValueError, KeyError):
                continue
        raise AccessError(_("The Leave Command Center is restricted to HR officers."))

    # ------------------------------------------------------------- helpers
    def _co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    def _month_bounds(self, month):
        if month:
            try:
                y, m = [int(x) for x in str(month).split('-')[:2]]
                first = date(y, m, 1)
            except (ValueError, IndexError):
                first = date.today().replace(day=1)
        else:
            first = date.today().replace(day=1)
        if first.month == 12:
            last = date(first.year, 12, 31)
        else:
            last = date(first.year, first.month + 1, 1) - timedelta(days=1)
        return first, last

    def _type_chip(self, lt):
        return {
            'id': lt.id,
            'name': lt.name,
            'code': lt.code or '',
            'color': _COLOR_HEX.get(int(lt.color or 0), _COLOR_HEX[0]),
        }

    def _emp_card(self, emp):
        return {
            'id': emp.id,
            'name': emp.name,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'department': emp.department_id.name if emp.department_id else '',
        }

    def _leave_dates(self, leave):
        df = leave.request_date_from or (leave.date_from.date() if leave.date_from else None)
        dt = leave.request_date_to or (leave.date_to.date() if leave.date_to else df)
        return df, dt

    # ------------------------------------------------------------- board
    @api.model
    def get_board(self, month=False, balance_page=0):
        self._require_officer()          # real-user gate…
        su = self.sudo()                 # …then collect the board sudo (C18.65)
        first, last = su._month_bounds(month)
        return {
            'month': first.strftime('%Y-%m'),
            'month_label': first.strftime('%B %Y'),
            'kpis': su._kpis(),
            'queue': su._queue(),
            'heatmap': su._heatmap(first, last),
            'balances': su._balances(int(balance_page or 0)),
            'leave_types': su._apply_types(),
        }

    def _kpis(self):
        Leave = self.env['hr.leave']
        co_ids = self._co_ids()
        today = date.today()
        # on leave today (approved) — company-scoped (C18.11/18)
        out_today = Leave.search([
            ('state', '=', 'validate'),
            ('employee_id.company_id', 'in', co_ids),
            ('request_date_from', '<=', today),
            ('request_date_to', '>=', today),
        ], order='request_date_to')
        cards = []
        for lv in out_today[:_TODAY_CARDS]:
            _df, dt = self._leave_dates(lv)
            cards.append({
                **self._emp_card(lv.employee_id),
                'type': self._type_chip(lv.holiday_status_id),
                # NOT 'return' — a JS reserved word breaks the OWL expression
                # compiler when accessed as p['return'] in the template.
                'return_date': (dt + timedelta(days=1)).isoformat() if dt else '',
            })
        pending = Leave.search_count([
            ('state', 'in', _QUEUE_STATES),
            ('employee_id.company_id', 'in', co_ids)])

        # this week out-by-day (approved)
        monday = today - timedelta(days=today.weekday())
        week = []
        wk_leaves = Leave.search([
            ('state', '=', 'validate'),
            ('employee_id.company_id', 'in', co_ids),
            ('request_date_from', '<=', monday + timedelta(days=6)),
            ('request_date_to', '>=', monday),
        ])
        for i in range(7):
            d = monday + timedelta(days=i)
            n = sum(1 for lv in wk_leaves
                    if self._covers(lv, d))
            week.append({'iso': d.isoformat(), 'label': d.strftime('%a'),
                         'is_today': d == today, 'count': n})

        return {
            'out_today': cards,
            'out_today_count': len(out_today),
            'pending': pending,
            'week': week,
        }

    def _covers(self, leave, d):
        df, dt = self._leave_dates(leave)
        return bool(df and dt and df <= d <= dt)

    def _queue(self):
        Leave = self.env['hr.leave']
        co_ids = self._co_ids()
        leaves = Leave.search([
            ('state', 'in', _QUEUE_STATES),
            ('employee_id.company_id', 'in', co_ids),
        ], order='date_from')
        return [self._leave_card(lv) for lv in leaves]

    def _leave_card(self, lv):
        df, dt = self._leave_dates(lv)
        state_label = {'confirm': _('To approve'),
                       'validate1': _('2nd approval')}.get(lv.state, lv.state)
        return {
            'id': lv.id,
            'employee': self._emp_card(lv.employee_id),
            'type': self._type_chip(lv.holiday_status_id),
            'date_from': df.isoformat() if df else '',
            'date_to': dt.isoformat() if dt else '',
            'duration': round(lv.number_of_days or 0.0, 2),
            'state': lv.state,
            'state_label': state_label,
            'note': lv.name or '',
            'can_approve': bool(lv.can_approve),
            'can_refuse': bool(getattr(lv, 'can_refuse', True)),
        }

    def _heatmap(self, first, last):
        """Department × day counts for the month, from ONE bounded leave scan.
        (read_group cannot EXPAND a multi-day span into per-day buckets, so the
        counts are folded in Python — a deliberate deviation from a plain
        read_group, C18-noted.)"""
        Leave = self.env['hr.leave']
        co_ids = self._co_ids()
        leaves = Leave.search([
            ('state', 'in', _LIVE_STATES),
            ('employee_id.company_id', 'in', co_ids),
            ('request_date_from', '<=', last),
            ('request_date_to', '>=', first),
        ], order='request_date_from', limit=_HEATMAP_SCAN + 1)
        truncated = len(leaves) > _HEATMAP_SCAN
        if truncated:
            leaves = leaves[:_HEATMAP_SCAN]

        n_days = (last - first).days + 1
        day_cols = [{'iso': (first + timedelta(days=i)).isoformat(),
                     'day': (first + timedelta(days=i)).day,
                     'is_weekend': (first + timedelta(days=i)).weekday() >= 5,
                     'is_today': (first + timedelta(days=i)) == date.today()}
                    for i in range(n_days)]

        rows = {}   # dept_name -> [counts per day]
        for lv in leaves:
            dep = lv.employee_id.department_id.name or _('No department')
            df, dt = self._leave_dates(lv)
            if not (df and dt):
                continue
            row = rows.setdefault(dep, [0] * n_days)
            span_start = max(df, first)
            span_end = min(dt, last)
            d = span_start
            while d <= span_end:
                row[(d - first).days] += 1
                d += timedelta(days=1)

        max_count = max((max(r) for r in rows.values()), default=0)
        heat_rows = [{'department': k, 'counts': v}
                     for k, v in sorted(rows.items())]
        return {
            'days': day_cols,
            'rows': heat_rows,
            'max': max_count,
            'truncated': truncated,
        }

    def _balances(self, page):
        """Employee × allocation-based leave type: validated allocations −
        validated taken. Server-paged (never unbounded — the 4.5k demo world)."""
        Emp = self.env['hr.employee']
        co_ids = self._co_ids()
        domain = [('active', '=', True), ('company_id', 'in', co_ids)]
        total = Emp.search_count(domain)
        emps = Emp.search(domain, order='name',
                          offset=page * _BALANCE_PAGE, limit=_BALANCE_PAGE)
        # allocation-based types only (requires_allocation Boolean, C18.22)
        types = self.env['hr.leave.type'].search(
            [('requires_allocation', '=', True)])
        type_by_id = {t.id: t for t in types}
        if not emps or not types:
            return {'page': page, 'page_size': _BALANCE_PAGE, 'total': total,
                    'has_more': (page + 1) * _BALANCE_PAGE < total,
                    'types': [self._type_chip(t) for t in types], 'rows': []}

        # validated allocations + taken, grouped once each (bounded to the page)
        Alloc = self.env['hr.leave.allocation']
        alloc_g = Alloc.read_group(
            [('employee_id', 'in', emps.ids), ('state', '=', 'validate'),
             ('holiday_status_id', 'in', types.ids)],
            ['number_of_days:sum'], ['employee_id', 'holiday_status_id'],
            lazy=False)
        taken_g = self.env['hr.leave'].read_group(
            [('employee_id', 'in', emps.ids), ('state', '=', 'validate'),
             ('holiday_status_id', 'in', types.ids)],
            ['number_of_days:sum'], ['employee_id', 'holiday_status_id'],
            lazy=False)
        alloc = self._fold_group(alloc_g)
        taken = self._fold_group(taken_g)

        rows = []
        for e in emps:
            cells = {}
            for t in types:
                a = alloc.get((e.id, t.id), 0.0)
                k = taken.get((e.id, t.id), 0.0)
                bal = round(a - k, 2)
                cells[t.id] = {'allocated': round(a, 2), 'taken': round(k, 2),
                               'balance': bal, 'low': bal <= 2.0 and a > 0}
            rows.append({**self._emp_card(e), 'cells': cells})
        return {
            'page': page, 'page_size': _BALANCE_PAGE, 'total': total,
            'has_more': (page + 1) * _BALANCE_PAGE < total,
            'types': [self._type_chip(t) for t in types],
            'rows': rows,
        }

    def _fold_group(self, groups):
        out = {}
        for g in groups:
            emp = g.get('employee_id')
            typ = g.get('holiday_status_id')
            if not (emp and typ):
                continue
            out[(emp[0], typ[0])] = g.get('number_of_days') or 0.0
        return out

    def _apply_types(self):
        """Leave types offered in apply-on-behalf, company-scoped."""
        co_ids = self._co_ids()
        types = self.env['hr.leave.type'].search(
            ['|', ('company_id', '=', False), ('company_id', 'in', co_ids)],
            order='name')
        return [self._type_chip(t) for t in types]

    # ------------------------------------------------------------- act
    @api.model
    def act(self, leave_id, action, note=False):
        """Drive a leave via core hr.leave's OWN action AS THE REAL USER (C18.17).
        Whitelist only — the installed hr_holidays folds 1st/2nd approval into
        action_approve (there is no public action_validate here), so a single
        'approve' advances one tier and the model decides the resulting state."""
        self._require_officer()
        whitelist = {'approve': 'action_approve', 'refuse': 'action_refuse'}
        if action not in whitelist:
            raise AccessError(_("Unknown action."))
        leave = self.env['hr.leave'].browse(int(leave_id)).exists()
        if not leave:
            raise UserError(_("This leave request no longer exists."))
        if action == 'refuse' and not (note and note.strip()):
            raise UserError(_("A reason is required to refuse a leave request."))
        getattr(leave, whitelist[action])()   # the model's own error surfaces verbatim
        # persist the refusal reason as an internal log note (existing core API,
        # no new mail code; mt_note does not email non-followers, and demo
        # employees are email-free — mail-safe, C18.47/48)
        if action == 'refuse' and note:
            try:
                leave.message_post(body=note, subtype_xmlid='mail.mt_note')
            except Exception:
                pass
        return {'ok': True, 'id': leave.id, 'state': leave.state}

    @api.model
    def apply_on_behalf(self, employee_id, type_id, date_from, date_to, note=False):
        """Create a leave for an employee AS THE REAL USER (no sudo). Core
        validation (overlap, balance, calendar) surfaces verbatim; the created
        leave defaults to 'confirm' (To Approve) — the installed hr_holidays has
        no separate action_confirm."""
        self._require_officer()
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("Select an employee."))
        if not type_id:
            raise UserError(_("Select a leave type."))
        if not (date_from and date_to):
            raise UserError(_("Pick a start and end date."))
        leave = self.env['hr.leave'].create({
            'employee_id': emp.id,
            'holiday_status_id': int(type_id),
            'request_date_from': date_from,
            'request_date_to': date_to,
            'name': note or _('Filed by HR'),
        })
        # belt-and-braces: the installed core creates at 'confirm', but honour an
        # action_confirm if a future core adds one.
        if hasattr(leave, 'action_confirm'):
            leave.action_confirm()
        return {'ok': True, 'id': leave.id, 'state': leave.state}

    @api.model
    def get_balances_page(self, page):
        self._require_officer()
        return self.sudo()._balances(int(page or 0))

    @api.model
    def search_employees(self, query, limit=8):
        """Typeahead for apply-on-behalf, company-scoped (read → sudo)."""
        self._require_officer()
        query = (query or '').strip()
        if not query:
            return []
        emps = self.sudo().env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', 'in', self._co_ids()),
            ('name', 'ilike', query),
        ], order='name', limit=int(limit))
        return [self._emp_card(e) for e in emps]
