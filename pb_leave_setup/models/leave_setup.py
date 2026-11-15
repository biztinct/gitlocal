# -*- coding: utf-8 -*-
"""pb.leave.setup — the Kinds of leave screen's server half (WDGAP S5-A).

WHY IT EXISTS (FACTS finding 1, ledger S5-6): kinds of leave were only
editable in the stock Time Off configuration menu, which no tenant user can
open. This screen is reached from Settings › HR and the command palette.

Cockpit doctrine (memory `payobook-cockpit-pattern`): every method passes its
own gate first — ``_require_read`` (the Time Off team, the same set the Leave
Command Center admits) or ``_require_write`` (a Time Off administrator, an HR
manager or a system administrator) — then reads and writes under sudo, inside
the companies the reader is working in. A JS ``groups`` list is a hint only.
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain

from .earning import month_start
from .starters import COUNTRIES, pick_lang

_logger = logging.getLogger(__name__)

READ_GROUPS = (
    'hr_holidays.group_hr_holidays_user',
    'hr.group_hr_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)
WRITE_GROUPS = (
    'hr_holidays.group_hr_holidays_manager',
    'hr.group_hr_manager',
)
PAGE = 60
OPEN_PAY = ['|', ('pb_pay_treatment', '=', 'unconfigured'), ('pb_pay_funding', '=', 'unconfigured')]
STATE_DOMAINS = {
    'on': [('active', '=', True)],
    'review': [('active', '=', False), ('pb_ls_review', '=', True)],
    'off': [('active', '=', False), ('pb_ls_review', '=', False)],
}


def _num(value):
    return '{:g}'.format(round(value or 0.0, 2))


class PbLeaveSetup(models.AbstractModel):
    _name = 'pb.leave.setup'
    _inherit = ['pb.filter.mixin']
    _description = 'Kinds of leave screen'

    # ================================================================ gates
    @api.model
    def _holds(self, groups):
        user = self.env.user
        for g in groups:
            try:
                if user.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _can_read(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group('base.group_system')
                    or self._holds(READ_GROUPS) or self._holds(WRITE_GROUPS))

    @api.model
    def _can_write(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group('base.group_system')
                    or self._holds(WRITE_GROUPS))

    @api.model
    def _refusal(self):
        return _('Kinds of leave are looked after by the HR team. Ask your administrator '
                 'for Time Off rights to see this screen.')

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(self._refusal())

    @api.model
    def _require_write(self):
        self._require_read()
        if not self._can_write():
            raise AccessError(_('Only an HR manager can change kinds of leave.'))

    @api.model
    def _co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _scope(self):
        return ['|', ('company_id', '=', False), ('company_id', 'in', self._co_ids())]

    @api.model
    def _Kind(self):
        return self.env['hr.leave.type'].sudo().with_context(active_test=False)

    @api.model
    def _kind(self, kind_id):
        self._require_read()
        try:
            kind_id = int(kind_id or 0)
        except (TypeError, ValueError):
            kind_id = 0
        kind = self._Kind().search(Domain.AND([self._scope(), [('id', '=', kind_id)]]), limit=1)
        if not kind:
            raise UserError(_('This kind of leave could not be found.'))
        return kind

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001 — one figure never blanks the board
            _logger.debug('leave set-up figure failed: %s', e)
            return default

    # ================================================================ words
    @api.model
    def _sel(self, field):
        return dict(self.env['hr.leave.type']._fields[field]._description_selection(self.env))

    @api.model
    def _options(self):
        return {
            'units': [{'key': 'day', 'label': _('Whole days')},
                      {'key': 'half_day', 'label': _('Half days')},
                      {'key': 'hour', 'label': _('Hours')}],
            'earning': [{'key': 'none', 'label': _('Given by HR')},
                        {'key': 'yearly', 'label': _('All at once each year')},
                        {'key': 'monthly', 'label': _('A share each month')}],
            'pay': [{'key': 'paid', 'label': _('Paid')},
                    {'key': 'partial', 'label': _('Partly paid')},
                    {'key': 'unpaid', 'label': _('Unpaid')},
                    {'key': 'unconfigured', 'label': _('Not decided yet')}],
            'funding': [{'key': 'employer', 'label': _('The company')},
                        {'key': 'external', 'label': _('An outside fund')},
                        {'key': 'mixed', 'label': _('Both')},
                        {'key': 'none', 'label': _('Nobody (unpaid)')},
                        {'key': 'unconfigured', 'label': _('Not decided yet')}],
            'approval': [{'key': 'hr', 'label': _('The HR team')},
                         {'key': 'manager', 'label': _('Their manager')},
                         {'key': 'both', 'label': _('Their manager, then HR')},
                         {'key': 'no_validation', 'label': _('Nobody (approved at once)')}],
            'countries': self._countries(),
            'companies': [{'id': c.id, 'name': c.name, 'country': c.country_id.code or ''}
                          for c in self.env.companies],
        }

    @api.model
    def _countries(self):
        Country = self.env['res.country'].sudo()
        out = []
        for code in COUNTRIES:
            c = Country.search([('code', '=', code)], limit=1)
            out.append({'code': code, 'label': c.name or code})
        return out

    @api.model
    def _unit_label(self, kind):
        return {'day': _('Whole days'), 'half_day': _('Half days'),
                'hour': _('Hours')}.get(kind.request_unit or 'day', '')

    @api.model
    def _earning_label(self, kind):
        if not kind.requires_allocation:
            return _('Not counted')
        if kind.pb_ls_earning == 'monthly':
            return _('%s a year, built up monthly', _num(kind.pb_ls_days_per_year))
        if kind.pb_ls_earning == 'yearly':
            return _('%s a year, all at once', _num(kind.pb_ls_days_per_year))
        return _('Given by HR')

    @api.model
    def _pay_label(self, kind):
        t = kind.pb_pay_treatment
        if t == 'unconfigured' or kind.pb_pay_funding == 'unconfigured':
            return _('Pay to decide')
        if t == 'unpaid':
            return _('Unpaid')
        who = {'employer': _('by the company'), 'external': _('by an outside fund'),
               'mixed': _('by the company and a fund')}.get(kind.pb_pay_funding, '')
        if t == 'partial':
            return _('Partly paid (%(pct)s%%) %(who)s',
                     pct=_num((kind.pb_paid_fraction or 0.0) * 100), who=who)
        return _('Paid %s', who)

    @api.model
    def _state(self, kind):
        if kind.active:
            return 'on', _('Switched on')
        if kind.pb_ls_review:
            return 'review', _('Waiting for review')
        return 'off', _('Switched off')

    @api.model
    def _policy_bound(self, kind):
        """A kind under a published leave policy (Rize): its pay and how it
        is earned come from the policy, not from this screen (FACTS risk)."""
        if not kind.pb_policy_category:
            return False
        Edition = self.env['pb.leave.policy.edition'].sudo()
        domain = [('state', '=', 'published')]
        if kind.company_id:
            domain.append(('company_id', '=', kind.company_id.id))
        return bool(Edition.search_count(domain))

    @api.model
    def _row(self, kind):
        state, state_label = self._state(kind)
        TO = self.env['pb.timeoff'].sudo()
        return {
            'id': kind.id,
            'name': kind.name or '',
            'country': TO._type_country(kind),
            'company': kind.company_id.name or _('Every company'),
            'unit_label': self._unit_label(kind),
            'counted': bool(kind.requires_allocation),
            'earning': kind.pb_ls_earning or 'none',
            'earning_label': self._earning_label(kind),
            'pay_label': self._pay_label(kind),
            'pay_open': (kind.pb_pay_treatment == 'unconfigured'
                         or kind.pb_pay_funding == 'unconfigured'),
            'hr_only': bool(kind.pb_ls_hr_only),
            'starter': bool(kind.pb_ls_starter_key),
            'policy': bool(kind.pb_policy_category),
            'state': state,
            'state_label': state_label,
        }

    # ================================================================ board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'why': self._refusal()}
        Kind = self._Kind()
        scope = self._scope()

        def count(domain):
            return self._safe(lambda: Kind.search_count(Domain.AND([scope, domain])))

        # kinds under a leave policy take their pay from the policy rule
        pay_open_domain = Domain.AND([scope, [('active', '=', True),
                                              ('pb_policy_category', '=', False)], OPEN_PAY])
        pay_open_count = count(pay_open_domain)
        pay_open_kinds = self._safe(lambda: Kind.search(pay_open_domain, order='name', limit=8),
                                    default=Kind)
        no_start = self._safe(self._no_start_people, default={'count': 0, 'names': []})
        return {
            'allowed': True,
            'why': '',
            'can_write': self._can_write(),
            'total': count([]),
            'kpis': {
                'on': count(STATE_DOMAINS['on']),
                'review': count(STATE_DOMAINS['review']),
                'off': count(STATE_DOMAINS['off']),
                'pay_open': pay_open_count,
                'earning': count([('active', '=', True), ('pb_ls_earning', 'in', ('monthly', 'yearly'))]),
                'no_start': no_start['count'],
            },
            'checks': {
                'pay_open': [{'id': k.id, 'name': k.name} for k in pay_open_kinds],
                'pay_open_more': max(0, pay_open_count - len(pay_open_kinds)),
                'no_start': no_start,
            },
            'options': self._options(),
            'langs': [short for code, short in (('vi_VN', 'vi'), ('id_ID', 'id'))
                      if code in {c for c, _n in self.env['res.lang'].get_installed()}],
            'default_company_id': self.env.company.id,
            'default_country': (self.env.company.country_id.code or '')
            if (self.env.company.country_id.code or '') in COUNTRIES else 'VN',
        }

    @api.model
    def _no_start_people(self):
        """People a building-up kind is for who have no start date: they get
        no extra days for long service, and nothing at all from a kind with a
        waiting period (never guessed from the contract, ledger D27)."""
        kinds = self._Kind().search(Domain.AND([self._scope(), [
            ('active', '=', True), ('pb_ls_earning', 'in', ('monthly', 'yearly'))]]))
        kinds = kinds.filtered(lambda k: k._pb_ls_earns()
                               and (k.pb_ls_step_ids or k.pb_ls_waiting_months))
        if not kinds:
            return {'count': 0, 'names': []}
        Earn = self.env['pb.leave.earning'].sudo()
        seen = self.env['hr.employee'].sudo()
        for kind in kinds:
            emps = Earn._eligible_employees(kind, month_start(fields.Date.context_today(self)))
            seen |= emps.filtered(lambda e: e.active and not Earn._service_start(e))
        seen = seen.filtered(lambda e: e.company_id.id in self._co_ids())
        return {'count': len(seen), 'names': seen.sorted('name')[:8].mapped('name')}

    # ============================================================ filter panel
    def _pbf_model(self):
        return 'hr.leave.type'

    def _pbf_screen(self):
        return 'leavekinds'

    def _pbf_records(self):
        self._require_read()
        return self._Kind()

    def _pbf_base_domain(self):
        return self._scope()

    def _pbf_search_fields(self):
        return ['name']

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Name A–Z'), 'order': 'name asc, id asc'},
            {'key': 'newest', 'label': _('Newest first'), 'order': 'id desc'},
            {'key': 'country', 'label': _('Country'), 'order': 'country_id, name, id'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'state', 'label': _('Switched on or off'), 'icon': 'powerOff',
             'group': 'other', 'type': 'choice', 'pinned': True, 'requires': ['active'],
             'options': [
                 {'value': 'on', 'label': _('Switched on'), 'tone': 'green',
                  'domain': STATE_DOMAINS['on']},
                 {'value': 'review', 'label': _('Waiting for review'), 'tone': 'amber',
                  'domain': STATE_DOMAINS['review']},
                 {'value': 'off', 'label': _('Switched off'), 'tone': 'slate',
                  'domain': STATE_DOMAINS['off']},
             ]},
            {'key': 'earning', 'label': _('How it is earned'), 'icon': 'calendarClock',
             'group': 'other', 'type': 'selection', 'path': 'pb_ls_earning', 'pinned': True},
            {'key': 'pay', 'label': _('Pay'), 'icon': 'banknote', 'group': 'pay',
             'type': 'choice', 'pinned': True, 'requires': ['pb_pay_treatment'],
             'options': [
                 {'value': 'open', 'label': _('Pay to decide'), 'tone': 'amber', 'domain': OPEN_PAY},
                 {'value': 'paid', 'label': _('Paid'), 'tone': 'green',
                  'domain': [('pb_pay_treatment', '=', 'paid'), ('pb_pay_funding', '!=', 'unconfigured')]},
                 {'value': 'partial', 'label': _('Partly paid'), 'tone': 'blue',
                  'domain': [('pb_pay_treatment', '=', 'partial'), ('pb_pay_funding', '!=', 'unconfigured')]},
                 {'value': 'unpaid', 'label': _('Unpaid'), 'tone': 'slate',
                  'domain': [('pb_pay_treatment', '=', 'unpaid')]},
             ]},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe', 'group': 'work',
             'type': 'many2one', 'path': 'country_id', 'label_sudo': True,
             'none_label': _('Every country')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark', 'group': 'work',
             'type': 'many2one', 'path': 'company_id', 'label_sudo': True,
             'none_label': _('Every company')},
            {'key': 'counted', 'label': _('Counted against an allowance'), 'icon': 'hash',
             'group': 'other', 'type': 'choice', 'requires': ['requires_allocation'],
             'options': [
                 {'value': 'yes', 'label': _('Counted'), 'tone': 'blue',
                  'domain': [('requires_allocation', '=', True)]},
                 {'value': 'no', 'label': _('Not counted'), 'tone': 'slate',
                  'domain': [('requires_allocation', '=', False)]},
             ]},
            {'key': 'unit', 'label': _('Taken in'), 'icon': 'clock', 'group': 'other',
             'type': 'selection', 'path': 'request_unit'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('Every kind'), 'icon': 'umbrella', 'filters': {}},
            {'key': 'on', 'label': _('Switched on'), 'icon': 'checkCircle',
             'filters': {'state': ['on']}},
            {'key': 'review', 'label': _('Waiting for review'), 'icon': 'eye',
             'filters': {'state': ['review']}},
            {'key': 'pay', 'label': _('Pay to decide'), 'icon': 'banknote',
             'filters': {'pay': ['open'], 'state': ['on']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': self._refusal()}
        return super().pbf_layout()

    @api.model
    def _pbf_step_counts(self, filters, search):
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'state'), None)
        if not s:
            return {}
        res = self._pbf_count_section(s, filters or {}, search, spec)
        return {r['v']: r['n'] for r in res.get('values') or []}

    @api.model
    def get_kinds_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE):
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        Kind = self._Kind()
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'name asc, id asc'
        rows = []
        for kind in Kind.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(kind))
            except Exception as e:      # noqa: BLE001 — one bad row never blanks the list
                _logger.debug('leave kind row %s failed: %s', kind.id, e)
        out = {'rows': rows, 'total': Kind.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search), default={})
        return out

    # ================================================================ drawer
    @api.model
    def _names(self, kind):
        out = {'en': kind.with_context(lang='en_US').name or ''}
        langs = {c for c, _n in self.env['res.lang'].get_installed()}
        for code, short in (('vi_VN', 'vi'), ('id_ID', 'id')):
            if code in langs:
                out[short] = kind.with_context(lang=code).name or ''
        return out

    @api.model
    def _sources(self, kind):
        lang = self.env.lang
        return {k: pick_lang(v, lang) for k, v in (kind.pb_ls_sources or {}).items()}

    @api.model
    def get_kind(self, kind_id):
        kind = self._kind(kind_id)
        state, state_label = self._state(kind)
        Earn = self.env['pb.leave.earning'].sudo()
        used = bool(self.env['hr.leave'].sudo().search_count([('holiday_status_id', '=', kind.id)], limit=1))
        recent = Earn.search([('leave_type_id', '=', kind.id)], limit=12)
        holders = len(self.env['hr.leave.allocation'].sudo().search(
            [('holiday_status_id', '=', kind.id), ('state', '=', 'validate')]).employee_id)
        TO = self.env['pb.timeoff'].sudo()
        return {
            'id': kind.id,
            'name': kind.name or '',
            'names': self._names(kind),
            'state': state, 'state_label': state_label,
            'review': bool(kind.pb_ls_review),
            'starter': bool(kind.pb_ls_starter_key),
            'sources': self._sources(kind),
            'company_id': kind.company_id.id or 0,
            'company': kind.company_id.name or _('Every company'),
            'country': TO._type_country(kind),
            'unit': kind.request_unit or 'day',
            'counted': bool(kind.requires_allocation),
            'approval': kind.leave_validation_type or 'hr',
            'hr_only': bool(kind.pb_ls_hr_only),
            'backdate_ok': bool(kind.pb_backdate_ok),
            'backdate_alert': bool(kind.pb_backdate_alert),
            'document': bool(kind.support_document),
            'carry_cap': kind.pb_carry_cap_days or 0.0,
            'pay': kind.pb_pay_treatment or 'unconfigured',
            'pay_pct': round((kind.pb_paid_fraction or 0.0) * 100, 2),
            'funding': kind.pb_pay_funding or 'unconfigured',
            'employer_pct': round((kind.pb_employer_paid_fraction or 0.0) * 100, 2),
            'earning': kind.pb_ls_earning or 'none',
            'days_per_year': kind.pb_ls_days_per_year or 0.0,
            'waiting_months': kind.pb_ls_waiting_months or 0,
            'max_balance': kind.pb_ls_max_balance or 0.0,
            'take_ahead': bool(kind.pb_ls_take_ahead),
            'expire_months': kind.pb_ls_expire_months or 0,
            'earn_from': fields.Date.to_string(kind.pb_ls_earn_from) if kind.pb_ls_earn_from else '',
            'steps': [{'years': s.after_years, 'days': s.extra_days} for s in kind.pb_ls_step_ids],
            'locks': {
                'policy': self._policy_bound(kind),
                'used': used,
            },
            'holders': holders,
            'recent': [self._posting_row(p) for p in recent],
            'can_write': self._can_write(),
        }

    @api.model
    def _posting_row(self, p):
        if p.period == 'month':
            when = p.period_start.strftime('%m/%Y')
        else:
            when = str(p.period_start.year)
        why = []
        if p.worked_share and p.worked_share < 0.9999:
            why.append(_('part of the period'))
        if p.extra_days:
            why.append(_('+%(days)s for %(years)s years of service',
                         days=_num(p.extra_days), years=p.service_years))
        if p.capped:
            why.append(_('limited by the most a person can hold'))
        return {
            'id': p.id, 'who': p.employee_id.name or '', 'when': when,
            'days': _num(p.days), 'why': ', '.join(why),
        }

    # ------------------------------------------------------------ saving
    @api.model
    def _clean(self, vals, kind=None):
        """Plain checks, then the values to write. Raises UserError in words."""
        vals = dict(vals or {})
        out = {}
        if 'name' in vals or kind is None:
            name = (vals.get('name') or '').strip()
            if not name:
                raise UserError(_('Give the kind of leave a name.'))
            out['name'] = name
        if 'company_id' in vals:
            cid = int(vals.get('company_id') or 0)
            if cid and cid not in self._co_ids():
                raise UserError(_('Pick one of your own companies.'))
            out['company_id'] = cid or False
        if 'country' in vals:
            code = (vals.get('country') or '').upper()
            country = self.env['res.country'].sudo().search([('code', '=', code)], limit=1) if code else False
            out['pb_policy_country_id'] = country.id if country else False
            if country:
                out['country_id'] = country.id
        used = bool(kind and self.env['hr.leave'].sudo().search_count(
            [('holiday_status_id', '=', kind.id)], limit=1))
        if 'unit' in vals:
            unit = vals.get('unit') or 'day'
            if unit not in ('day', 'half_day', 'hour'):
                raise UserError(_('Choose whole days, half days or hours.'))
            if kind and used and unit != (kind.request_unit or 'day'):
                raise UserError(_('People have already asked for this kind of leave, so how it is '
                                  'counted cannot change. Make a new kind instead.'))
            if not kind or unit != (kind.request_unit or 'day'):
                out['request_unit'] = unit
        if 'counted' in vals:
            counted = bool(vals.get('counted'))
            if kind and used and counted != bool(kind.requires_allocation):
                raise UserError(_('People have already asked for this kind of leave, so whether it '
                                  'is counted against an allowance cannot change. Make a new kind '
                                  'instead.'))
            # written only when it changes: core refuses even an unchanged
            # value once the kind has been used
            if not kind or counted != bool(kind.requires_allocation):
                out['requires_allocation'] = counted
        if 'approval' in vals:
            appr = vals.get('approval') or 'hr'
            if appr not in ('hr', 'manager', 'both', 'no_validation'):
                raise UserError(_('Choose who approves it.'))
            out['leave_validation_type'] = appr
        for src, dst in (('hr_only', 'pb_ls_hr_only'), ('backdate_ok', 'pb_backdate_ok'),
                         ('backdate_alert', 'pb_backdate_alert'), ('document', 'support_document'),
                         ('take_ahead', 'pb_ls_take_ahead')):
            if src in vals:
                out[dst] = bool(vals.get(src))
        for src, dst in (('carry_cap', 'pb_carry_cap_days'), ('days_per_year', 'pb_ls_days_per_year'),
                         ('max_balance', 'pb_ls_max_balance')):
            if src in vals:
                try:
                    out[dst] = max(0.0, float(vals.get(src) or 0.0))
                except (TypeError, ValueError):
                    raise UserError(_('Type a number of days.'))
        for src, dst in (('waiting_months', 'pb_ls_waiting_months'),
                         ('expire_months', 'pb_ls_expire_months')):
            if src in vals:
                try:
                    out[dst] = max(0, int(float(vals.get(src) or 0)))
                except (TypeError, ValueError):
                    raise UserError(_('Type a number of months.'))
        policy = bool(kind and self._policy_bound(kind))
        pay_keys = {'pay', 'pay_pct', 'funding', 'employer_pct'}
        if policy and pay_keys & set(vals):
            same = (vals.get('pay', kind.pb_pay_treatment) == kind.pb_pay_treatment
                    and vals.get('funding', kind.pb_pay_funding) == kind.pb_pay_funding)
            if not same:
                raise UserError(_('How this kind is paid is set by your leave policy.'))
            vals = {k: v for k, v in vals.items() if k not in pay_keys}
        if pay_keys & set(vals):
            treatment = vals.get('pay', kind.pb_pay_treatment if kind else 'unconfigured')
            funding = vals.get('funding', kind.pb_pay_funding if kind else 'unconfigured')
            try:
                pct = float(vals.get('pay_pct', (kind.pb_paid_fraction * 100) if kind else 100) or 0)
                emp_pct = float(vals.get('employer_pct',
                                         (kind.pb_employer_paid_fraction * 100) if kind else 0) or 0)
            except (TypeError, ValueError):
                raise UserError(_('Type a share between 0 and 100.'))
            if treatment not in ('paid', 'partial', 'unpaid', 'unconfigured'):
                raise UserError(_('Choose how it is paid.'))
            if funding not in ('employer', 'external', 'mixed', 'none', 'unconfigured'):
                raise UserError(_('Choose who pays for it.'))
            if treatment == 'unpaid':
                funding = 'none'
            elif funding == 'none' and treatment != 'unconfigured':
                raise UserError(_('Paid leave needs somebody to pay for it.'))
            if not (0 <= pct <= 100 and 0 <= emp_pct <= 100):
                raise UserError(_('Type a share between 0 and 100.'))
            out.update({
                'pb_pay_treatment': treatment, 'pb_pay_funding': funding,
                'pb_paid_fraction': 1.0 if treatment == 'paid' else (0.0 if treatment == 'unpaid'
                                                                    else pct / 100.0),
                'pb_employer_paid_fraction': emp_pct / 100.0 if funding == 'mixed' else 0.0,
            })
            if kind is None:
                # core's own "Is unpaid" flag is set for a NEW kind only: on an
                # existing kind it feeds worked-day lines, and the drawer must
                # never change a pay figure by being saved
                out['unpaid'] = treatment == 'unpaid'
            if funding == 'mixed' and emp_pct / 100.0 > out['pb_paid_fraction']:
                raise UserError(_("The company's share cannot be more than the part that is paid."))
        if 'earning' in vals:
            earning = vals.get('earning') or 'none'
            if earning not in ('none', 'yearly', 'monthly'):
                raise UserError(_('Choose how it is earned.'))
            if policy and earning != 'none':
                raise UserError(_('How this kind is earned is set by your leave policy.'))
            counted = out.get('requires_allocation', kind.requires_allocation if kind else True)
            unit = out.get('request_unit', kind.request_unit if kind else 'day')
            days = out.get('pb_ls_days_per_year', kind.pb_ls_days_per_year if kind else 0.0)
            if earning != 'none':
                if not counted:
                    raise UserError(_('Only a kind counted against an allowance can build up.'))
                if unit == 'hour':
                    raise UserError(_('A kind taken in hours is given by HR. Choose whole or half '
                                      'days to let it build up.'))
                if not days:
                    raise UserError(_('Say how many days a year it gives.'))
            out['pb_ls_earning'] = earning
            was = kind.pb_ls_earning if kind else 'none'
            if earning != 'none' and (was == 'none' or not (kind and kind.pb_ls_earn_from)):
                # from this month on — never the months before, so days HR
                # already gave by hand are not given a second time
                out.setdefault('pb_ls_earn_from', month_start(fields.Date.context_today(self)))
        if vals.get('earn_from'):
            try:
                out['pb_ls_earn_from'] = month_start(fields.Date.to_date(vals['earn_from']))
            except (TypeError, ValueError):
                raise UserError(_('Pick the first month.'))
        if 'steps' in vals:
            steps = []
            for s in vals.get('steps') or []:
                try:
                    years, days = int(float(s.get('years') or 0)), float(s.get('days') or 0)
                except (TypeError, ValueError, AttributeError):
                    raise UserError(_('Each step needs a number of years and a number of days.'))
                if years or days:
                    steps.append((years, days))
            if len({y for y, _d in steps}) != len(steps):
                raise UserError(_('Two steps start after the same number of years.'))
            out['pb_ls_step_ids'] = [(5, 0, 0)] + [
                (0, 0, {'after_years': y, 'extra_days': d}) for y, d in sorted(steps)]
        return out

    @api.model
    def save_kind(self, kind_id, vals, switch_on=False):
        """Create (kind_id 0) or change a kind. A new kind starts switched
        off unless `switch_on` is asked for. Returns the drawer payload."""
        self._require_write()
        kind = self._kind(kind_id) if kind_id else None
        out = self._clean(vals, kind)
        names = (vals or {}).get('names') or {}
        Kind = self._Kind().with_context(lang='en_US')
        try:
            with self.env.cr.savepoint():
                if kind:
                    kind.with_context(lang='en_US').write(out)
                else:
                    out.setdefault('active', False)
                    if 'company_id' not in out:
                        out['company_id'] = self.env.company.id
                    kind = Kind.create(out)
                self._write_names(kind, names)
        except ValidationError as e:
            raise UserError(e.args[0] if e.args else str(e))
        if switch_on:
            self._switch(kind, True)
        return self.get_kind(kind.id)

    @api.model
    def _write_names(self, kind, names):
        langs = {c for c, _n in self.env['res.lang'].get_installed()}
        tr = {}
        for short, code in (('vi', 'vi_VN'), ('id', 'id_ID')):
            text = (names.get(short) or '').strip()
            if code in langs and text:
                tr[code] = text
        if tr:
            kind.update_field_translations('name', tr)

    @api.model
    def _switch(self, kind, on):
        if on:
            if (kind.pb_pay_treatment == 'unconfigured' or kind.pb_pay_funding == 'unconfigured') \
                    and not kind.pb_policy_category:
                raise UserError(_('Choose how this kind is paid before switching it on.'))
            kind.write({'active': True, 'pb_ls_review': False})
        else:
            kind.write({'active': False})

    @api.model
    def set_active(self, kind_id, on):
        self._require_write()
        kind = self._kind(kind_id)
        self._switch(kind, bool(on))
        return self.get_kind(kind.id)

    # ------------------------------------------------------------ preview
    @api.model
    def preview(self, vals):
        """What the rules mean in plain words, and what the employee sees —
        from the drawer's values as typed, before anything is saved."""
        self._require_read()
        vals = dict(vals or {})
        name = (vals.get('name') or '').strip() or _('This kind of leave')
        counted = bool(vals.get('counted'))
        unit = vals.get('unit') or 'day'
        earning = vals.get('earning') or 'none'
        try:
            per_year = max(0.0, float(vals.get('days_per_year') or 0.0))
            waiting = max(0, int(float(vals.get('waiting_months') or 0)))
            cap = max(0.0, float(vals.get('max_balance') or 0.0))
            expire = max(0, int(float(vals.get('expire_months') or 0)))
        except (TypeError, ValueError):
            per_year, waiting, cap, expire = 0.0, 0, 0.0, 0
        steps = []
        for s in vals.get('steps') or []:
            try:
                y, d = int(float(s.get('years') or 0)), float(s.get('days') or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            if y > 0 and d > 0:
                steps.append((y, d))
        steps.sort()

        def extra_for(years):
            best = 0.0
            for y, d in steps:
                if years >= y:
                    best = max(best, d)
            return best

        rules = []
        table = []
        builds = counted and earning in ('monthly', 'yearly') and per_year > 0 and unit != 'hour'
        if not counted:
            rules.append(_('Not counted against an allowance: people ask for it when they need it.'))
        elif not builds:
            rules.append(_('HR gives the days by hand; nothing is added automatically.'))
        else:
            if earning == 'monthly':
                rules.append(_('%(year)s days a year: %(month)s days are added after each month '
                               'worked.', year=_num(per_year), month=_num(per_year / 12.0)))
                rules.append(_('Somebody who joins or leaves part-way through a month gets that '
                               "part of the month's days."))
                if vals.get('take_ahead'):
                    rules.append(_("People can take the whole year's days from the start of the "
                                   'year. Somebody who leaves early may owe the days taken ahead.'))
                else:
                    rules.append(_('People can take only what they have earned so far.'))
            else:
                rules.append(_('%s days a year, added at the start of each year.', _num(per_year)))
                rules.append(_('Somebody who joins during the year gets a share for the rest of '
                               'that year.'))
            if waiting:
                rules.append(_('Nothing is added in the first %s months of service.', waiting))
            if steps:
                rules.append(_('Extra days for long service count from the month the person '
                               'reaches each step, measured from their date of joining.'))
            if cap:
                rules.append(_('Nobody holds more than %s days; nothing more is added until '
                               'they take some.', _num(cap)))
            if expire:
                rules.append(_('Days not taken run out %s months after the year ends.', expire))
            else:
                rules.append(_('Days not taken do not run out.'))
            for years in sorted({0} | {y for y, _d in steps}):
                total = per_year + extra_for(years)
                table.append({
                    'years': years,
                    'label': (_('In the first year') if years == 0 else
                              _('After 1 year') if years == 1 else
                              _('After %s years', years)),
                    'year': _num(total),
                    'month': _num(total / 12.0) if earning == 'monthly' else '',
                })
        shown = not vals.get('hr_only')
        unit_label = {'day': _('Whole days'), 'half_day': _('Half days or whole days'),
                      'hour': _('Hours')}.get(unit, '')
        tile = None
        if counted:
            sample = (per_year / 12.0 * 4) if builds and earning == 'monthly' else per_year
            tile = {
                'name': name,
                'balance_label': _('%(balance)s days left', balance=_num(sample)),
                'used_label': _('%(taken)s of %(allocated)s days used', taken=0,
                                allocated=_num(sample)),
                'earned_label': (_('%(days)s days earned so far this year', days=_num(sample))
                                 if builds and earning == 'monthly' else ''),
                'next_label': (_('Next: %(days)s on %(date)s', days=_num(per_year / 12.0),
                                 date=self.env['pb.ess.workforce']._pb_ls_date(
                                     month_start(fields.Date.context_today(self))
                                     + relativedelta(months=1)))
                               if builds and earning == 'monthly' else ''),
            }
        return {
            'rules': rules, 'table': table, 'tile': tile,
            'option': {'shown': shown, 'name': name, 'unit_label': unit_label,
                       'document': bool(vals.get('document'))},
        }

    # ------------------------------------------------------------ build-up now
    @api.model
    def post_now(self, kind_id):
        """Run the build-up for one kind now (the same job the night runs).
        Never adds a month twice."""
        self._require_write()
        kind = self._kind(kind_id)
        if not kind._pb_ls_earns():
            raise UserError(_('This kind does not build up: switch it on and choose how it is '
                              'earned first.'))
        Earn = self.env['pb.leave.earning'].sudo()
        res = Earn._run_kind(kind, fields.Date.context_today(self))
        posted = res.get('posted', 0)
        bits = []
        if posted:
            bits.append(_('Days added: %s.', posted))
        else:
            bits.append(_('Nothing new to add: every finished month is already in.'))
        if res.get('no_start'):
            bits.append(_('%s people have no date of joining, so nothing was added for them.',
                          res['no_start']))
        if res.get('failed'):
            bits.append(_('%s could not be added; the next run tries again.', res['failed']))
        return {'msg': ' '.join(bits), 'result': dict(res), 'kind': self.get_kind(kind.id)}

    # ------------------------------------------------------------ ready-made
    @api.model
    def starter_list(self, country, company_id=None):
        self._require_read()
        company = self._company(company_id)
        return {'country': (country or '').upper(), 'company_id': company.id,
                'company': company.name,
                'rows': self.env['pb.leave.starters'].sudo()._review_rows(country, company)}

    @api.model
    def starter_apply(self, country, company_id=None, keys=None):
        self._require_write()
        company = self._company(company_id)
        keys = [k for k in (keys or []) if isinstance(k, str)]
        if not keys:
            raise UserError(_('Tick at least one kind to add.'))
        res = self.env['pb.leave.starters'].sudo()._apply(country, company, keys=set(keys))
        n = len(res['created'])
        if n:
            msg = (_('1 kind added, switched off. Review it, then switch it on.') if n == 1 else
                   _('%s kinds added, switched off. Review each one, then switch it on.', n))
        else:
            msg = _('Nothing was added: these kinds are already there.')
        return {'msg': msg, 'created': res['created'], 'skipped': res['skipped']}

    @api.model
    def _company(self, company_id):
        try:
            cid = int(company_id or 0)
        except (TypeError, ValueError):
            cid = 0
        cid = cid or self.env.company.id
        if cid not in self._co_ids():
            raise UserError(_('Pick one of your own companies.'))
        return self.env['res.company'].sudo().browse(cid)
