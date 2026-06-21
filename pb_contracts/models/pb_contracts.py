# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import api, models

_logger = logging.getLogger(__name__)

STATE_LABEL = {'draft': 'Draft', 'open': 'Running', 'close': 'Expired', 'cancel': 'Cancelled'}
ROSTER_LIMIT = 240
# state -> contextual next actions (label, icon, kind)
NEXT = {
    'draft': [('set_running', 'Set running', 'play', 'primary'),
              ('cancel', 'Cancel', 'x', 'danger')],
    'open':  [('renew', 'Renew', 'rotate', 'primary'),
              ('terminate', 'Terminate', 'x', 'danger')],
    'close': [('renew', 'Renew', 'rotate', 'primary')],
    'cancel': [('set_running', 'Re-activate', 'play', 'ghost')],
}
LIFECYCLE = {'set_running', 'terminate', 'cancel'}


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


class PbContracts(models.AbstractModel):
    _name = 'pb.contracts'
    _description = 'Payobook contracts cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Contracts cockpit metric failed: %s", e)
            return default

    @api.model
    def get_board(self):
        C = self.env['hr.contract']
        company = self.env.company
        cur = company.currency_id
        co_ids = self.env.companies.ids or [company.id]
        DOM = [('company_id', 'in', co_ids)]
        today = date.today()

        running = self._safe(lambda: C.search_count(DOM + [('state', '=', 'open')]))
        expired = self._safe(lambda: C.search_count(DOM + [('state', '=', 'close')]))
        draft = self._safe(lambda: C.search_count(DOM + [('state', '=', 'draft')]))
        from datetime import timedelta
        soon = today + timedelta(days=30)
        expiring = self._safe(lambda: C.search_count(
            DOM + [('state', '=', 'open'), ('date_end', '>=', str(today)), ('date_end', '<=', str(soon))]))
        total_wage = 0.0
        try:
            g = C.read_group(DOM + [('state', '=', 'open')], ['wage:sum'], [])
            total_wage = (g and g[0].get('wage')) or 0.0
        except Exception:
            total_wage = 0.0
        avg_wage = round(total_wage / running) if running else 0

        # structure chips — prefer struct_id (populated), fall back to structure_type_id
        structures = []
        gfield = 'struct_id' if 'struct_id' in C._fields else 'structure_type_id'
        try:
            sg = C.read_group(DOM, [gfield], [gfield])
            for g in sg:
                st = g.get(gfield)
                structures.append({'name': st[1] if st else 'Unset',
                                   'count': g.get(gfield + '_count') or g.get('__count') or 0})
            structures.sort(key=lambda x: -x['count'])
        except Exception:
            structures = []

        rows = []
        cs = self._safe(lambda: C.search(DOM, order='date_start desc, id desc', limit=ROSTER_LIMIT),
                        default=C.browse())
        for c in cs:
            try:
                dte = (c.date_end - today).days if c.date_end else None
                rows.append({
                    'id': c.id, 'name': c.name or '—',
                    'employee': c.employee_id.name if c.employee_id else '—',
                    'employee_id': c.employee_id.id if c.employee_id else False,
                    'avatar': ('/web/image/hr.employee/%s/avatar_128' % c.employee_id.id) if c.employee_id else '',
                    'state': c.state, 'state_label': STATE_LABEL.get(c.state, c.state),
                    'kanban_state': c.kanban_state,
                    'wage': c.wage or 0.0,
                    'date_start': str(c.date_start) if c.date_start else '',
                    'date_end': str(c.date_end) if c.date_end else '',
                    'days_to_expiry': dte,
                    'structure': (c.struct_id.name if getattr(c, 'struct_id', False) else
                                  (c.structure_type_id.name if c.structure_type_id else '')),
                })
            except Exception as ex:
                _logger.debug("Contract row failed: %s", ex)
                continue

        return {
            'currency': cur.symbol or '',
            'kpis': {'running': running, 'expiring': expiring, 'expired': expired,
                     'draft': draft, 'total_wage': total_wage, 'avg_wage': avg_wage},
            'structures': structures,
            'contracts': rows,
            'total': self._safe(lambda: C.search_count(DOM)),
            'shown': len(rows),
        }

    # ------------------------------------------------------------------ detail
    @api.model
    def get_contract_detail(self, contract_id):
        c = self.env['hr.contract'].browse(int(contract_id))
        if not c.exists():
            return {'error': 'Contract not found'}
        cur = (c.company_id or self.env.company).currency_id
        today = date.today()
        e = c.employee_id
        dte = (c.date_end - today).days if c.date_end else None

        # tenure since start
        tenure_label = '—'
        if c.date_start:
            months = (today.year - c.date_start.year) * 12 + (today.month - c.date_start.month)
            if today.day < c.date_start.day:
                months -= 1
            months = max(months, 0)
            y, m = divmod(months, 12)
            tenure_label = (('%dy ' % y) if y else '') + ('%dm' % m) if (y or m) else '<1m'

        rail_state = {'draft': 'draft', 'open': 'running', 'close': 'expired',
                      'cancel': 'expired'}.get(c.state, 'draft')
        order = ['draft', 'running', 'expired']
        ci = order.index(rail_state)
        pipeline = [{'key': s, 'label': s.capitalize(), 'done': i < ci, 'current': i == ci}
                    for i, s in enumerate(order)]

        acts = [{'method': m, 'label': l, 'icon': i, 'kind': k} for (m, l, i, k) in NEXT.get(c.state, [])]

        return {
            'id': c.id, 'name': c.name or '—',
            'employee': e.name if e else '—', 'employee_id': e.id if e else False,
            'initials': _initials(e.name if e else ''),
            'avatar': ('/web/image/hr.employee/%s/avatar_256' % e.id) if e else '',
            'job': (e.job_id.name if (e and e.job_id) else ''),
            'dept': (c.department_id.name if c.department_id else ''),
            'structure': (c.struct_id.name if getattr(c, 'struct_id', False) else
                          (c.structure_type_id.name if c.structure_type_id else '')),
            'currency': cur.symbol or '',
            'state': c.state, 'state_label': STATE_LABEL.get(c.state, c.state),
            'kanban_state': c.kanban_state,
            'wage': c.wage or 0.0,
            'date_start': str(c.date_start) if c.date_start else '',
            'date_end': str(c.date_end) if c.date_end else '',
            'trial_end': str(c.trial_date_end) if c.trial_date_end else '',
            'days_to_expiry': dte,
            'tenure_label': tenure_label,
            'pipeline': pipeline,
            'next_actions': acts,
            'error': None,
        }

    @api.model
    def run_contract_action(self, contract_id, method, value=None):
        c = self.env['hr.contract'].browse(int(contract_id))
        err = None
        if method not in LIFECYCLE:
            d = self.get_contract_detail(contract_id)
            d['error'] = 'Action not permitted'
            return d
        try:
            if method == 'set_running':
                c.write({'state': 'open'})
            elif method == 'terminate':
                vals = {'state': 'close'}
                if not c.date_end:
                    vals['date_end'] = value or str(date.today())
                elif value:
                    vals['date_end'] = value
                c.write(vals)
            elif method == 'cancel':
                c.write({'state': 'cancel'})
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Action failed.'
            _logger.warning("Contract action %s failed: %s", method, e)
        detail = self.get_contract_detail(contract_id)
        detail['error'] = err
        return detail
