# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

# kanban lane ladder (Refused/Cancelled collapse into a footer filter)
_LANES = [
    ('draft', 'Draft'),
    ('submitted', 'Manager'),
    ('manager_approved', 'Finance'),
    ('finance_approved', 'HR'),
    ('approved', 'Authorized'),
]
_PENDING = ('submitted', 'manager_approved', 'finance_approved')
#: "Open trips": everything not yet authorized, refused or cancelled.
_OPEN = ('draft',) + _PENDING
#: Off the board: the footer list ("Refused or cancelled").
_CLOSED = ('refused', 'cancelled')

#: Cards per page of the filtered board (all lanes together).
PAGE_SIZE = 120


class PbTrips(models.AbstractModel):
    """RPC facade for the Business Trips cockpit (client action ``pb_trips``).

    FILTER wave 7 (2026-10-31). The board used to read EVERY trip of the
    companies in one unbounded search and narrow it in the browser (a step, or
    "waiting on me"). It now sits on the shared filter panel: the panel counts
    on the server, the five lanes are its "Where the trip is" section (lane
    counts are the panel's counts, so they follow every other filter), the
    cards arrive one page at a time, and the refused / cancelled footer is the
    view "Refused or cancelled". `get_pipeline_data` stays as it was for any
    other reader (ruling R4).
    """
    _name = 'pb.trips'
    _inherit = ['pb.filter.mixin']
    _description = 'Business Trips Cockpit API'

    @api.model
    def get_pipeline_data(self):
        Trip = self.env['pb.business.trip']
        co_ids = self.env.companies.ids or [self.env.company.id]
        trips = Trip.search([('company_id', 'in', co_ids)])
        today = date.today()
        month_start = date(today.year, today.month, 1)
        cur = self.env.company.currency_id

        lanes = {key: {'key': key, 'label': label, 'cards': [],
                       'count': 0, 'advance': 0.0} for key, label in _LANES}
        closed = []
        awaiting_me = 0
        days_mtd = 0
        advance_outstanding = 0.0

        for t in trips:
            can_act = t.state in _PENDING and t._can_current_user_act()
            if can_act:
                awaiting_me += 1
            # days travelled this month (approved only)
            if t.state == 'approved' and t.date_from and t.date_to:
                s = max(t.date_from, month_start)
                e = min(t.date_to, today)
                if e >= s:
                    days_mtd += (e - s).days + 1
            if t.state in _PENDING or t.state == 'approved':
                advance_outstanding += t.advance_amount or 0.0

            waiting = (today - (t.write_date.date() if t.write_date else today)).days
            card = {
                'id': t.id,
                'name': t.name,
                'destination': (t.destination_city or '').title() or _('Trip'),
                'country': t.destination_country_id.code or '',
                'employee': t.employee_id.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % t.employee_id.id,
                'date_from': fields.Date.to_string(t.date_from),
                'date_to': fields.Date.to_string(t.date_to),
                'days': t.duration_days,
                'per_diem_total': t.per_diem_total,
                'advance': t.advance_amount,
                'estimated_total': t.estimated_total,
                'state': t.state,
                'waiting_days': max(0, waiting),
                'can_act': can_act,
            }
            if t.state in lanes:
                lanes[t.state]['cards'].append(card)
                lanes[t.state]['count'] += 1
                lanes[t.state]['advance'] += t.advance_amount or 0.0
            else:
                closed.append(card)

        open_count = sum(lanes[k]['count'] for k in
                         ('draft', 'submitted', 'manager_approved', 'finance_approved'))
        return {
            'lanes': [lanes[k] for k, _l in _LANES],
            'closed': closed,
            'currency': cur.symbol or '',
            'currency_position': cur.position or 'after',
            'kpis': {
                'open': open_count,
                'awaiting_me': awaiting_me,
                'days_mtd': days_mtd,
                'advance_outstanding': round(advance_outstanding, 2),
            },
        }

    # ================================================== the shared filter panel
    @api.model
    def _co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    def _pbf_model(self):
        return 'pb.business.trip'

    def _pbf_screen(self):
        return 'trips'

    def _pbf_base_domain(self):
        # the board's own scope, unchanged: the trips of the companies being
        # looked at, as the reader may see them (record rules do the rest)
        return [('company_id', 'in', self._co_ids())]

    def _pbf_search_fields(self):
        return ['name', 'destination_city', 'destination_country_id.name',
                'employee_id.name', 'department_id.name', 'purpose']

    def _pbf_sorts(self):
        return [
            {'key': 'latest', 'label': _('Latest start first'),
             'order': 'date_from desc, id desc'},
            {'key': 'soonest', 'label': _('Earliest start first'),
             'order': 'date_from asc, id asc'},
            {'key': 'waiting', 'label': _('Waiting longest first'),
             'order': 'write_date asc, id asc'},
            {'key': 'advance', 'label': _('Biggest cash advance first'),
             'order': 'advance_amount desc, id desc'},
            {'key': 'cost', 'label': _('Most expensive first'),
             'order': 'estimated_total desc, id desc'},
            {'key': 'newest', 'label': _('Newest request first'),
             'order': 'id desc'},
        ]

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    # ---- "Waiting on me": a Python fact (the route's seats, the tier groups,
    # the specific line manager). ONE search of the trips still at a step,
    # then the same per-trip check the card's Approve button uses, memoised
    # for the request (ledger F18/F25: pbf_counts asks for it many times).
    @api.model
    def _mine_ids(self):
        key = ('pb_trips.mine', self.env.uid, tuple(self._co_ids()))
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        pending = self.env['pb.business.trip'].search([
            ('company_id', 'in', self._co_ids()), ('state', 'in', _PENDING)])
        ids = [t.id for t in pending if t._can_current_user_act()]
        cache[key] = ids
        return ids

    @api.model
    def _pbf_mine(self):
        return [('id', 'in', self._mine_ids())]

    @api.model
    def _pbf_not_mine(self):
        return [('state', 'in', _PENDING), ('id', 'not in', self._mine_ids())]

    @api.model
    def _step_options(self):
        """The lanes in the board's own words (the step strip's titles), then
        the two states the footer holds."""
        words = [
            ('draft', _('Draft'), 'slate'),
            ('submitted', _('With the manager'), 'amber'),
            ('manager_approved', _('With finance'), 'amber'),
            ('finance_approved', _('With HR'), 'amber'),
            ('approved', _('Authorized'), 'green'),
            ('refused', _('Refused'), 'rose'),
            ('cancelled', _('Cancelled'), 'slate'),
        ]
        return [{'value': k, 'label': label, 'tone': tone,
                 'domain': [('state', '=', k)]} for k, label, tone in words]

    def _pbf_spec(self):
        return [
            # ---- pinned: where it is, who, which team
            {'key': 'step', 'label': _('Where the trip is'), 'icon': 'listChecks',
             'group': 'other', 'type': 'choice', 'pinned': True,
             'options': self._step_options()},
            {'key': 'employee', 'label': _('Who is travelling'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id',
             'pinned': True, 'label_sudo': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id',
             'pinned': True, 'label_sudo': True, 'none_label': _('No department')},
            # ---- more filters
            {'key': 'mine', 'label': _('Who it waits on'), 'icon': 'userCheck',
             'group': 'people', 'type': 'choice',
             'help': _('Trips at a step you can approve now.'),
             'options': [
                 {'value': 'yes', 'label': _('Me'), 'tone': 'amber',
                  'domain_method': '_pbf_mine'},
                 {'value': 'no', 'label': _('Somebody else'), 'tone': 'slate',
                  'domain_method': '_pbf_not_mine'},
             ]},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'work', 'type': 'many2one', 'path': 'destination_country_id',
             'none_label': _('No country given')},
            {'key': 'starts', 'label': _('Leaves on'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'date_from',
             'presets': ['this_week', 'this_month', 'next_7', 'next_30', 'next_90',
                         'later', 'last_month', 'last_90', 'this_year', 'passed']},
            {'key': 'ends', 'label': _('Back on'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'date_to',
             'presets': ['today', 'this_week', 'this_month', 'next_7', 'next_30',
                         'last_month', 'last_90', 'passed']},
            {'key': 'policy', 'label': _('Per-diem policy'), 'icon': 'scrollText',
             'group': 'pay', 'type': 'many2one', 'path': 'policy_id',
             'none_label': _('No policy')},
            {'key': 'advance', 'label': _('Cash advance'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'advance_amount', 'unit': 'money'},
            {'key': 'cost', 'label': _('Expected cost'), 'icon': 'coins',
             'group': 'pay', 'type': 'number', 'path': 'estimated_total', 'unit': 'money'},
            {'key': 'manager', 'label': _('Their manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'manager_id',
             'label_sudo': True, 'none_label': _('No manager')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ]

    @api.model
    def _month_range(self):
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        last = first + relativedelta(months=1) - timedelta(days=1)
        return first, last

    def _pbf_builtin_views(self):
        first, last = self._month_range()
        return [
            {'key': 'open', 'label': _('Open trips'), 'icon': 'plane',
             'filters': {'step': list(_OPEN)}},
            # on the road at some point this month: leaves before the month
            # ends and is back after it began
            {'key': 'travelling', 'label': _('Travelling this month'), 'icon': 'mapPin',
             'filters': {'step': ['approved'],
                         'starts': {'to': fields.Date.to_string(last)},
                         'ends': {'from': fields.Date.to_string(first)}}},
            {'key': 'authorise', 'label': _('Awaiting authorisation'), 'icon': 'stamp',
             'filters': {'step': ['finance_approved']}},
            # the numbers line's "Advance outstanding", as a list
            {'key': 'advance', 'label': _('With a cash advance'), 'icon': 'banknote',
             'filters': {'step': list(_PENDING) + ['approved'], 'advance': {'min': 1}}},
            {'key': 'closed', 'label': _('Refused or cancelled'), 'icon': 'ban',
             'filters': {'step': list(_CLOSED)}},
        ]

    # ------------------------------------------------------------ the reads
    @api.model
    def get_trips_head(self):
        """The numbers line and the strip's notes, counted over every trip of
        the companies being looked at (whatever is filtered) — the same
        figures `get_pipeline_data` gave, without building every card."""
        Trip = self.env['pb.business.trip']
        co = [('company_id', 'in', self._co_ids())]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        cur = self.env.company.currency_id
        mine = self._mine_ids()
        mine_by_state = dict.fromkeys(_PENDING, 0)
        for t in Trip.browse(mine):
            if t.state in mine_by_state:
                mine_by_state[t.state] += 1
        days_mtd = 0
        for t in Trip.search(co + [('state', '=', 'approved'),
                                   ('date_from', '<=', today),
                                   ('date_to', '>=', month_start)]):
            s = max(t.date_from, month_start)
            e = min(t.date_to, today)
            if e >= s:
                days_mtd += (e - s).days + 1
        adv = Trip._read_group(co + [('state', 'in', list(_PENDING) + ['approved'])],
                               [], ['advance_amount:sum'])
        return {
            'currency': cur.symbol or '',
            'currency_position': cur.position or 'after',
            'kpis': {
                'open': Trip.search_count(co + [('state', 'in', list(_OPEN))]),
                'awaiting_me': len(mine),
                'days_mtd': days_mtd,
                'advance_outstanding': round((adv[0][0] if adv else 0.0) or 0.0, 2),
            },
            'mine_by_state': mine_by_state,
        }

    @api.model
    def _trip_card(self, t, today, mine):
        waiting = (today - (t.write_date.date() if t.write_date else today)).days
        return {
            'id': t.id,
            'name': t.name,
            'destination': (t.destination_city or '').title() or _('Trip'),
            'country': t.destination_country_id.code or '',
            'employee': t.employee_id.name or '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % t.employee_id.id,
            'date_from': fields.Date.to_string(t.date_from),
            'date_to': fields.Date.to_string(t.date_to),
            'days': t.duration_days,
            'per_diem_total': t.per_diem_total,
            'advance': t.advance_amount,
            'estimated_total': t.estimated_total,
            'state': t.state,
            'waiting_days': max(0, waiting),
            'can_act': t.id in mine,
        }

    @api.model
    def get_trip_page(self, filters=None, search=None, sort=None, offset=0,
                      limit=PAGE_SIZE):
        """One page of cards for the panel's state (every lane together, in
        the chosen order). The first page also carries each lane's cash
        advance, said about the same filters as the lane counts."""
        Trip = self.env['pb.business.trip']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 300))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        trips = Trip.search(domain, order=self.pbf_order(sort) or 'date_from desc, id desc',
                            offset=offset, limit=limit)
        today = fields.Date.context_today(self)
        mine = set(self._mine_ids())
        out = {
            'cards': [self._trip_card(t, today, mine) for t in trips],
            'total': Trip.search_count(domain),
            'offset': offset,
        }
        if not offset:
            advance = {}
            try:
                for state, total in Trip._read_group(
                        self.pbf_domain(filters, search, skip='step'),
                        ['state'], ['advance_amount:sum']):
                    advance[state] = total or 0.0
            except Exception:  # noqa: BLE001 — the lane note goes, the board stays
                advance = {}
            out['lane_advance'] = advance
        return out
