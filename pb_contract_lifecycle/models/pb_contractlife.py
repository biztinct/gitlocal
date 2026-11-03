# -*- coding: utf-8 -*-
"""`pb.contractlife` — the Contracts lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down, `self.env
.companies` scoping on every search, a row cap, and no sudo in a READ except
where a field's own `groups=` forces it (R56 — reading one field of an
`hr.employee` prefetches forty, half of them behind payroll groups).

THE QUESTION THIS BOARD ANSWERS is the one nobody asks until it is too late:
WHOSE AGREEMENT RUNS OUT, AND HAS ANYBODY DECIDED. So a row is a CONTRACT, the
number beside the name is the days left, and the chip after it says what kind of
employment this is — because "intern" and "contractor" are the two answers that
change what the decision even means.

THERE IS NO MONEY ON THIS BOARD, ON PURPOSE. A screen that lists what everybody
earns is a screen nobody can leave open on a shared desk, and a contract
decision does not need the number. The wage appears in exactly one place — the
confirm dialog, at the moment somebody is about to agree to it.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .contract_common import (
    DECISION_LABEL, EMPLOYEE_TYPE_LABEL, GROUP_ADMIN, GROUP_MANAGER,
    GROUP_USER, NON_PERMANENT_TYPES, P_AUTO_TRIGGER, P_EXTENSION_MONTHS,
    P_LEAD_DAYS, REVIEW_OPEN, REVIEW_STATE_LABEL, flag, initials, number,
)

_logger = logging.getLogger(__name__)

#: How many rows the SCREEN reads. Right for a screen and wrong for a job —
#: the nightly work passes no cap at all (R76). Only the old `get_board`
#: payload still uses it; the board itself now pages (FILTER W2).
BOARD_LIMIT = 300

#: Cards per page on the filtered board ("Show N more" loads the next page).
PAGE_SIZE = 60

#: How red the days-left number goes: half the lead time, or a fortnight,
#: whichever is smaller.
def _urgent_days(lead):
    return min(30, max(7, int(lead or 60) // 2))


class PbContractLife(models.AbstractModel):
    _name = 'pb.contractlife'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Contracts & interns cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception:               # noqa: BLE001
            # WARNING with the traceback, never DEBUG (R92): a swallowed
            # exception logged at debug level is invisible on a live server,
            # and the caller gets a cheerful zero either way.
            _logger.warning('pb_contract_lifecycle: a board metric failed',
                            exc_info=True)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN) or user._is_admin())

    @api.model
    def _can_write(self):
        user = self.env.user
        return (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)
                or user._is_admin())

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at which contracts are ending, but deciding "
                "what happens to one is for the HR team. Ask them to make the "
                "change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'kinds': [], 'departments': [], 'months': [],
                    'states': [], 'auto_on': False, 'lead_days': 60,
                    'total': 0, 'capped': False, 'would_raise': 0}
        Contract = self.env['hr.contract']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()
        lead = max(1, number(self.env, P_LEAD_DAYS, 60))

        # ---- everybody with an end date, plus every intern and contractor ----
        # TWO SEARCHES AND NOT ONE, because they answer different questions and
        # a person can be either without being both: a fixed-term contract has
        # an end date whoever is on it, and an intern with no end date on their
        # paperwork is exactly the person this board exists to catch.
        rows_by_id = {}
        dated = self._safe(lambda: Contract.search([
            ('company_id', 'in', co_ids),
            ('date_end', '!=', False),
            ('state', 'in', ('draft', 'open')),
        ], order='date_end, id', limit=BOARD_LIMIT),
            default=Contract.browse())
        for contract in dated:
            rows_by_id[contract.id] = contract

        if len(rows_by_id) < BOARD_LIMIT:
            people = self._safe(lambda: self.env['hr.employee'].search([
                ('company_id', 'in', co_ids),
                ('active', '=', True),
                ('employee_type', 'in', list(NON_PERMANENT_TYPES)),
            ], limit=BOARD_LIMIT), default=self.env['hr.employee'].browse())
            extra = self._safe(lambda: Contract.search([
                ('company_id', 'in', co_ids),
                ('employee_id', 'in', people.ids),
                ('state', 'in', ('draft', 'open')),
            ], order='date_start desc, id desc',
                limit=BOARD_LIMIT - len(rows_by_id)),
                default=Contract.browse())
            for contract in extra:
                rows_by_id.setdefault(contract.id, contract)

        rows = []
        for contract in rows_by_id.values():
            try:
                rows.append(self._row(contract, today, lead))
            except Exception:           # noqa: BLE001
                _logger.warning('pb_contract_lifecycle: row for contract %s',
                                contract.id, exc_info=True)
        rows.sort(key=lambda r: (r['days'] if r['days'] is not None else 99999,
                                 r['employee']))

        year_start = date(today.year, 1, 1)
        converted = self._safe(lambda: self.env['pb.contract.review'].search_count([
            ('company_id', 'in', co_ids),
            ('decision', '=', 'convert'),
            ('decided_at', '>=', str(year_start)),
        ]))
        would = self._safe(lambda: len(
            self.env['pb.journey.case']._due_for_decision()))

        kpis = {
            'ending': len([r for r in rows if r['days'] is not None
                           and 0 <= r['days'] <= lead]),
            'undecided': len([r for r in rows if r['needs_decision']]),
            'running': len([r for r in rows
                            if r['review_state'] == 'conversion']),
            'waiting': len([r for r in rows
                            if r['review_state'] == 'extension']),
            'converted': converted,
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'auto_on': flag(self.env, P_AUTO_TRIGGER),
            'would_raise': would,
            'lead_days': lead,
            'default_months': number(self.env, P_EXTENSION_MONTHS, 12),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'kinds': _facet(rows, 'kind_label'),
            'departments': _facet(rows, 'dept'),
            # A MONTH FACET IS READ IN CALENDAR ORDER, not in order of size.
            # Sorted by count, the row read "October 2026, November 2026,
            # August 2026, December 2026…" and a reader looking for next month
            # had to hunt for it.
            'months': _facet(rows, 'end_month', by_key=True),
            'states': _facet(rows, 'review_label'),
        }

    @api.model
    def _row(self, contract, today=None, lead=None):
        today = today or date.today()
        lead = lead or max(1, number(self.env, P_LEAD_DAYS, 60))
        emp = contract.employee_id
        Review = self.env['pb.contract.review']
        review = self._safe(
            lambda: Review.sudo().search(
                [('contract_id', '=', contract.id)],
                order='id desc', limit=1),
            default=Review.browse())
        # The LIVE one if there is one — never `order='state, ...'`, which
        # sorts a Selection by its stored string and would put "conversion"
        # ahead of "decide" for no reason anybody could explain (R50).
        live = self._safe(
            lambda: Review.sudo().search(
                [('contract_id', '=', contract.id),
                 ('state', 'in', ('upcoming', 'decide', 'extension',
                                  'conversion'))],
                order='id desc', limit=1),
            default=Review.browse())
        review = live or review

        kind = self._safe(lambda: emp._pb_employment_type(), default='') \
            if emp else ''
        days = (contract.date_end - today).days if contract.date_end else None
        urgent = _urgent_days(lead)
        needs = bool(
            days is not None and days <= lead
            and (not review or review.state in ('upcoming', 'decide')))
        # CONTRACTLIFE SCOPE: the Python twin of `_cl_open_ended_domain` —
        # no end date and not an active non-permanent person. The type is
        # read under sudo (R56: `employee_type` is HR-gated).
        temp = bool(emp) and self._safe(
            lambda: bool(emp.sudo().active
                         and emp.sudo().employee_type in NON_PERMANENT_TYPES),
            default=False)
        open_ended = not contract.date_end and not temp
        if open_ended:
            # a quiet card: nothing to decide, no decision shown on it
            review = Review.browse()
            needs = False
        return {
            'open_ended': open_ended,
            'id': contract.id,
            'employee_id': emp.id if emp else 0,
            'employee': (emp.name if emp else '') or _('Nobody on it'),
            'initials': initials(emp.name if emp else ''),
            'avatar': ('/web/image/hr.employee/%s/avatar_128' % emp.id)
            if emp else '',
            'job': self._safe(
                lambda: emp.sudo().job_title
                or (emp.sudo().job_id.name if emp.sudo().job_id else ''),
                default='') or '' if emp else '',
            'dept': self._safe(
                lambda: emp.sudo().department_id.name
                if (emp and emp.sudo().department_id) else '',
                default='') or _('No team'),
            'manager': self._safe(
                lambda: emp.sudo().parent_id.name
                if (emp and emp.sudo().parent_id) else '', default='') or '',
            'kind': kind,
            'kind_label': EMPLOYEE_TYPE_LABEL.get(kind, '') or _('Not set'),
            'non_permanent': kind in NON_PERMANENT_TYPES,
            'contract_name': contract.name or '—',
            'contract_type': contract.type_id.name if contract.type_id else '',
            'state': contract.state,
            'date_start': str(contract.date_start) if contract.date_start
            else '',
            'date_end': str(contract.date_end) if contract.date_end else '',
            'end_month': (contract.date_end.strftime('%Y-%m')
                          if contract.date_end else ''),
            'days': days,
            'when': _when(days),
            'urgent': bool(days is not None and days <= urgent),
            'needs_decision': needs,
            'review_id': review.id if review else 0,
            'review_state': review.state if review else '',
            'review_label': (_('Nothing to decide') if open_ended
                             else REVIEW_STATE_LABEL.get(review.state, '')
                             if review else _('Not raised')),
            'decision': review.decision if review else '',
            'decision_label': (DECISION_LABEL.get(review.decision, '')
                               if review else ''),
            'new_contract_id': (review.new_contract_id.id
                                if (review and review.new_contract_id) else 0),
            'evaluation_id': (review.review_id.id
                              if (review and review.review_id) else 0),
        }

    # =====================================================================
    #  THE FILTER PANEL (pb_filter_kit, FILTER wave 2)
    #
    #  The board used to read two searches merged into 300 rows, count its
    #  chips from those rows and filter them in the browser, so a chip could
    #  say 40 while the board behind it held 11 and the 301st contract was
    #  simply not there. Now every count is a server count over every
    #  contract the board is about, and the cards come a page at a time.
    #  `get_board` above still answers the old payload for anything that
    #  reads it (ruling R4).
    # =====================================================================
    @api.model
    def _cl_may_list(self):
        """May this reader see the cards at all? The board's own tier AND
        read access to contracts, because the cards are read as the reader."""
        if not self._can_read():
            return False
        try:
            return bool(self.env['ir.model.access'].check(
                'hr.contract', 'read', raise_exception=False))
        except Exception:               # noqa: BLE001
            return False

    def _pbf_model(self):
        return 'hr.contract'

    def _pbf_screen(self):
        return 'contractends'

    def _pbf_records(self):
        """SUDO for exactly the readers this board lets in, and nobody else.

        The board has always read the employment type and every decision
        under sudo (R56: `employee_type` sits behind hr.group_hr_user and the
        decisions behind their own rules), so its counts must see what its
        cards show. The company restriction travels in the base domain.
        """
        Contract = self.env['hr.contract']
        return Contract.sudo() if self._cl_may_list() else Contract

    def _pbf_base_domain(self):
        """EVERY draft or running contract of the reader's companies.

        CONTRACTLIFE SCOPE (2026-11-04): the board used to hold only the
        decision population (an end date, or an intern/contractor) and said
        "All 40" on a tenant with 210 contracts. The base is now every
        contract; the decision population is the `dated` rule
        (`_cl_dated_domain`), which every decision/step/attention rule and
        the first tab carry, so their counts did not move."""
        co_ids = self.env.companies.ids or [self.env.company.id]
        return ['&',
                ('company_id', 'in', co_ids),
                ('state', 'in', ['draft', 'open'])]

    @api.model
    def _cl_temp_people(self):
        """An active intern / contractor / … on the contract. As `any` on the
        many2one, so its negation (`not any`) also keeps contracts with no
        employee — a `!=` on a dotted path would silently drop those."""
        return [('active', '=', True),
                ('employee_type', 'in', list(NON_PERMANENT_TYPES))]

    @api.model
    def _cl_dated_domain(self):
        """The decision population: an end date, or a non-permanent person."""
        return (Domain('date_end', '!=', False)
                | Domain('employee_id', 'any', self._cl_temp_people()))

    @api.model
    def _cl_open_ended_domain(self):
        """Exactly the complement of `_cl_dated_domain` within the base."""
        return (Domain('date_end', '=', False)
                & Domain('employee_id', 'not any', self._cl_temp_people()))

    def _pbf_search_fields(self):
        return ['employee_id.name', 'employee_id.job_title',
                'employee_id.department_id.name', 'name']

    def _pbf_sorts(self):
        return [
            {'key': 'ends', 'label': _('Ending soonest first'),
             'order': 'date_end asc nulls last, id asc'},
            {'key': 'ends_late', 'label': _('Ending latest first'),
             'order': 'date_end desc nulls last, id desc'},
            {'key': 'name', 'label': _('Name, A to Z'),
             'order': 'employee_id, id'},
            {'key': 'started', 'label': _('Started most recently'),
             'order': 'date_start desc nulls last, id desc'},
        ]

    @api.model
    def _cl_rules(self):
        """Every fact on a card, as a domain on `hr.contract`.

        A contract's decision is its LIVE review (at most one: a second
        trigger adds nothing, R30) or, when none is live, the latest one —
        the same rule `_row` reads. All literal domains: nothing here needs
        Python per row, so every count stays one SQL query.
        """
        today = self._pbf_today()
        lead = max(1, number(self.env, P_LEAD_DAYS, 60))
        urgent = _urgent_days(lead)
        ds = fields.Date.to_string

        # CONTRACTLIFE SCOPE: the base now holds every contract, so every
        # decision fact below carries `dated` — an open-ended contract for a
        # permanent person has nothing to decide and must never count as
        # "Not raised yet", "Running" or "Nothing needed".
        dated = self._cl_dated_domain()
        open_ended = self._cl_open_ended_domain()

        def rev(*states):
            return dated & Domain('pb_review_ids', 'any', [('state', 'in', list(states))])

        no_live = Domain('pb_review_ids', 'not any', [('state', 'in', list(REVIEW_OPEN))])
        review = {
            'none': dated & Domain('pb_review_ids', '=', False),
            'upcoming': rev('upcoming'),
            'decide': rev('decide'),
            'extension': rev('extension'),
            'conversion': rev('conversion'),
            'done': no_live & rev('done'),
            'lapsed': no_live & rev('lapsed') & ~rev('done'),
        }
        # `needs_decision` and `urgent` on a card (`_row`), and "needs
        # somebody" on the old chip row (contractlife_board.js needsAttention)
        needs = (Domain('date_end', '<=', ds(today + timedelta(days=lead)))
                 & (review['none'] | rev('upcoming', 'decide')))
        soon = Domain('date_end', '<=', ds(today + timedelta(days=urgent)))
        # an intern or contractor with no end date (`dated` keeps the old
        # "active person" condition the base used to carry)
        undated = (dated & Domain('date_end', '=', False)
                   & Domain('employee_id.employee_type', 'in', list(NON_PERMANENT_TYPES)))
        attention = needs | soon | review['lapsed'] | undated
        return {
            'today': today, 'lead': lead, 'urgent': urgent,
            'review': review, 'needs': needs, 'soon': soon,
            'undated': undated, 'attention': attention,
            'dated': dated, 'open_ended': open_ended,
            # the four steps; a contract is at exactly one of them
            'steps': {
                'running': review['none'] | review['upcoming'],
                'choose': review['decide'],
                'agree': review['extension'] | review['conversion'],
                'closed': review['done'] | review['lapsed'],
            },
            # "Ending within the lead days": today to today + lead, inclusive
            'window': {'from': ds(today), 'to': ds(today + timedelta(days=lead))},
        }

    @api.model
    def _cl_glance_filters(self, rules=None):
        """What each figure on the numbers line means as a filter — the SAME
        filters as the built-in views, so pressing one lights its tab."""
        rules = rules or self._cl_rules()
        return {
            'ending': {'ends': dict(rules['window'])},
            'undecided': {'attention': ['undecided']},
            'waiting': {'decision': ['extension']},
            'running': {'decision': ['conversion']},
        }

    def _pbf_spec(self):
        rules = self._cl_rules()
        review = rules['review']
        types = [
            ('employee', _('Permanent')), ('worker', _('Worker')),
            ('student', _('Student')), ('trainee', _('Trainee')),
            ('intern', _('Intern')), ('contractor', _('Contractor')),
            ('freelance', _('Freelancer')),
        ]
        return [
            # ---- pinned: when, has anybody decided, which team
            {'key': 'ends', 'label': _('Contract ends'), 'icon': 'calendarClock',
             'group': 'contract', 'type': 'date', 'path': 'date_end',
             'presets': 'future', 'pinned': True,
             'none_label': _('No end date')},
            {'key': 'decision', 'label': _('Decision'), 'icon': 'scale',
             'group': 'contract', 'type': 'choice', 'pinned': True,
             'requires': ['pb_review_ids'],
             'help': _('Where the decision about this contract stands.'),
             'options': [
                 {'value': 'none', 'label': _('Not raised yet'), 'tone': 'slate',
                  'domain': review['none']},
                 {'value': 'upcoming', 'label': _('Opened, nobody asked yet'),
                  'tone': 'blue', 'domain': review['upcoming']},
                 {'value': 'decide', 'label': _('Decision needed'), 'tone': 'rose',
                  'domain': review['decide']},
                 {'value': 'extension', 'label': _('Extension requested'),
                  'tone': 'amber', 'domain': review['extension']},
                 {'value': 'conversion', 'label': _('Evaluation running'),
                  'tone': 'blue', 'domain': review['conversion']},
                 {'value': 'done', 'label': _('Decided'), 'tone': 'green',
                  'domain': review['done']},
                 {'value': 'lapsed', 'label': _('Ended with nothing decided'),
                  'tone': 'rose', 'domain': review['lapsed']},
             ]},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one',
             'path': 'employee_id.department_id', 'pinned': True,
             'none_label': _('No team')},
            # ---- more filters
            {'key': 'attention', 'label': _('Needs somebody'), 'icon': 'alert',
             'group': 'contract', 'type': 'choice',
             'help': _('Contracts somebody has to act on before the date.'),
             'options': [
                 {'value': 'undecided', 'label': _('Nobody has decided'),
                  'tone': 'rose', 'domain': rules['needs']},
                 {'value': 'soon', 'label': _('Ends within %s days', rules['urgent']),
                  'tone': 'amber', 'domain': rules['soon']},
                 {'value': 'lapsed', 'label': _('Ended with nothing decided'),
                  'tone': 'rose', 'domain': review['lapsed']},
                 {'value': 'undated', 'label': _('Intern or contractor with no end date'),
                  'tone': 'amber', 'domain': rules['undated']},
                 {'value': 'fine', 'label': _('Nothing needed'), 'tone': 'green',
                  'domain': rules['dated'] & ~rules['attention']},
             ]},
            # CONTRACTLIFE SCOPE: which contracts the board is about. Hidden
            # from the panel; the "With an end date" and "Open-ended" tabs
            # switch it on (and its chip names it while on).
            {'key': 'scope', 'label': _('Contracts'), 'icon': 'calendarClock',
             'group': 'contract', 'type': 'choice', 'hidden': True,
             'options': [
                 {'value': 'dated', 'label': _('With an end date'),
                  'tone': 'blue', 'domain': rules['dated']},
                 {'value': 'open_ended', 'label': _('Open-ended'),
                  'tone': 'slate', 'domain': rules['open_ended']},
             ]},
            {'key': 'step', 'label': _('Where it stands'), 'icon': 'listChecks',
             'group': 'contract', 'type': 'choice', 'requires': ['pb_review_ids'],
             'options': [
                 {'value': 'running', 'label': _('Running'), 'tone': 'slate',
                  'domain': rules['steps']['running']},
                 {'value': 'choose', 'label': _('Decision needed'), 'tone': 'rose',
                  'domain': rules['steps']['choose']},
                 {'value': 'agree', 'label': _('Being agreed'), 'tone': 'amber',
                  'domain': rules['steps']['agree']},
                 {'value': 'closed', 'label': _('Decided'), 'tone': 'green',
                  'domain': rules['steps']['closed']},
             ]},
            {'key': 'kind', 'label': _('Employment type'), 'icon': 'idCard',
             'group': 'people', 'type': 'choice',
             'requires': ['employee_id.employee_type'],
             'options': [{'value': k, 'label': label,
                          'tone': 'blue' if k in NON_PERMANENT_TYPES else '',
                          'domain': [('employee_id.employee_type', '=', k)]}
                         for k, label in types]},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.parent_id',
             'none_label': _('Nobody named')},
            {'key': 'status', 'label': _('Contract status'), 'icon': 'fileText',
             'group': 'contract', 'type': 'selection', 'path': 'state'},
            {'key': 'category', 'label': _('Contract category'), 'icon': 'file',
             'group': 'contract', 'type': 'many2one', 'path': 'type_id',
             'none_label': _('No category')},
            {'key': 'starts', 'label': _('Started'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'date_start',
             'presets': 'past', 'none_label': _('No start date')},
        ]

    def _pbf_builtin_views(self):
        rules = self._cl_rules()
        glance = self._cl_glance_filters(rules)
        # The FIRST view is the start view (pb_filter_kit) — the decision
        # population, as before; "All contracts" is the base with no filter.
        return [
            {'key': 'dated', 'label': _('With an end date'), 'icon': 'calendarClock',
             'filters': {'scope': ['dated']}},
            {'key': 'ending', 'label': _('Ending within %s days', rules['lead']),
             'filters': glance['ending']},
            {'key': 'undecided', 'label': _('Nobody has decided'),
             'filters': glance['undecided']},
            {'key': 'waiting', 'label': _('Waiting to be agreed'),
             'filters': glance['waiting']},
            {'key': 'temps', 'label': _('Interns and contractors'),
             'filters': {'kind': list(NON_PERMANENT_TYPES), 'scope': ['dated']}},
            {'key': 'open_ended', 'label': _('Open-ended'),
             'filters': {'scope': ['open_ended']}},
            {'key': 'all', 'label': _('All contracts'), 'icon': 'fileText', 'filters': {}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._cl_may_list():
            # the board shows its own "looked after by the HR team" panel
            return {'refused': _("Contracts are looked after by the HR team.")}
        return super().pbf_layout()

    @api.model
    def get_board_head(self):
        """The numbers line, the switch notice and the flags, counted over
        EVERY contract the board is about. The cards come from
        `get_board_page`, a page at a time, for the panel's filters."""
        if not self._cl_may_list():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'auto_on': False, 'would_raise': 0, 'lead_days': 60,
                    'default_months': 12, 'total': 0, 'all_total': 0,
                    'open_ended': 0, 'glance_filters': {}}
        Rec = self._pbf_records()
        rules = self._cl_rules()
        every = Domain(self._pbf_base_domain())
        # the numbers line counts the decision population only (as before)
        base = every & rules['dated']
        co_ids = self.env.companies.ids or [self.env.company.id]

        def count(dom):
            return self._safe(lambda: Rec.search_count(base & Domain(dom)))

        win = rules['window']
        year_start = date(rules['today'].year, 1, 1)
        kpis = {
            'ending': count(Domain('date_end', '>=', win['from'])
                            & Domain('date_end', '<=', win['to'])),
            'undecided': count(rules['needs']),
            'running': count(rules['review']['conversion']),
            'waiting': count(rules['review']['extension']),
            'converted': self._safe(lambda: self.env['pb.contract.review'].search_count([
                ('company_id', 'in', co_ids),
                ('decision', '=', 'convert'),
                ('decided_at', '>=', str(year_start)),
            ])),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'auto_on': flag(self.env, P_AUTO_TRIGGER),
            'would_raise': self._safe(lambda: len(
                self.env['pb.journey.case']._due_for_decision())),
            'lead_days': rules['lead'],
            'default_months': number(self.env, P_EXTENSION_MONTHS, 12),
            'kpis': kpis,
            'total': self._safe(lambda: Rec.search_count(base)),
            # CONTRACTLIFE SCOPE: the line under the four steps, and whether
            # the board has any contract at all to list
            'all_total': self._safe(lambda: Rec.search_count(every)),
            'open_ended': self._safe(lambda: Rec.search_count(
                every & rules['open_ended'])),
            'glance_filters': self._cl_glance_filters(rules),
        }

    @api.model
    def get_board_page(self, filters=None, search=None, sort=None, offset=0,
                       limit=PAGE_SIZE):
        """One page of cards for the panel's filters, plus — on the first
        page — the four step counts for those same filters (ruling R1)."""
        if not self._cl_may_list():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        Rec = self._pbf_records()
        spec = self._pbf_clean_spec()
        domain = self.pbf_domain(filters or {}, search, spec=spec)
        found = Rec.search(domain, order=self.pbf_order(sort) or 'date_end, id',
                           offset=offset, limit=limit)
        today = date.today()
        lead = max(1, number(self.env, P_LEAD_DAYS, 60))
        rows = []
        # Read as the reader, exactly as the old board read its cards; only
        # the search above needed sudo (the employment type is HR-gated).
        for contract in self.env['hr.contract'].browse(found.ids):
            try:
                rows.append(self._row(contract, today, lead))
            except Exception:           # noqa: BLE001 — one bad card never blanks the board
                _logger.warning('pb_contract_lifecycle: row for contract %s',
                                contract.id, exc_info=True)
        out = {'rows': rows, 'total': Rec.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._cl_step_counts(filters or {}, search, spec)
        return out

    @api.model
    def _cl_step_counts(self, filters, search, spec):
        """{step: {n, flag counts}} for the panel's filters minus the step."""
        Rec = self._pbf_records()
        rules = self._cl_rules()
        dom = self.pbf_domain(filters, search, skip='step', spec=spec)
        # every step rule already carries `dated` (_cl_rules), so on the
        # Open-ended tab the four steps read 0: they count decisions only
        out = {}
        for key, step_dom in rules['steps'].items():
            at = dom & step_dom
            row = {'n': self._safe(lambda at=at: Rec.search_count(at))}
            if key == 'agree':
                row['signoff'] = self._safe(lambda at=at: Rec.search_count(
                    at & rules['review']['extension']))
            elif key == 'closed':
                row['lapsed'] = self._safe(lambda at=at: Rec.search_count(
                    at & rules['review']['lapsed']))
            else:
                row['undecided'] = self._safe(lambda at=at: Rec.search_count(
                    at & rules['needs']))
            out[key] = row
        return out

    # ------------------------------------------------------- one contract
    @api.model
    def get_contract(self, contract_id):
        """One contract, whole — the decision drawer behind a row."""
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        contract = self.env['hr.contract'].browse(int(contract_id)).exists()
        if not contract:
            raise UserError(_("That contract could not be found."))
        Review = self.env['pb.contract.review'].sudo()
        history = self._safe(
            lambda: Review.search([('contract_id', '=', contract.id)],
                                  order='id desc'),
            default=Review.browse())
        live = history.filtered(
            lambda r: r.state in ('upcoming', 'decide', 'extension',
                                  'conversion'))[:1]
        review = live or history[:1]
        extension = self.env['pb.contract.extension'].browse()
        if review:
            extension = review.extension_ids.filtered(
                lambda e: e.state in ('draft', 'pending'))[:1]
        return {
            'row': self._row(contract),
            'terms': self._safe(lambda: contract.pb_terms_summary(),
                                default={}),
            'review_id': review.id if review else 0,
            'review_state': review.state if review else '',
            'previews': {kind: self._safe(
                lambda k=kind: review.decision_preview(k), default={})
                for kind in ('terminate', 'extend', 'convert')}
            if review else {},
            'extension': {
                'id': extension.id,
                'reason': extension.reason or '',
                'months': extension.months,
                'approver': (extension.approver_user_id.name
                             if extension.approver_user_id else ''),
                'approve_by': str(extension.approve_by or ''),
                'state': extension.state,
                'state_label': extension.state_label(),
                'overdue': bool(extension.approve_by
                                and extension.approve_by < date.today()),
                'new_start': str(extension.new_date_start or ''),
                'new_end': str(extension.new_date_end or ''),
            } if extension else None,
            'evaluation': self._evaluation(review),
            # WHAT HAS BEEN DECIDED **BEFORE** — so the live one is not in
            # it. The drawer already shows the open decision at the top, with
            # its three choices or the panel for whatever is running; repeating
            # it under a past-tense heading made the screen say "The contract
            # ran to 31 Jan 2027" about a contract that has not started yet.
            'history': [{
                'id': r.id,
                'raised': str(r.create_date.date()) if r.create_date else '',
                'end_date': str(r.end_date or ''),
                'about': _('About the contract ending %s.',
                           r.end_date or _('on no particular date')),
                'state': r.state,
                'state_label': r.state_label(),
                'decision': r.decision or '',
                'decision_label': DECISION_LABEL.get(r.decision, '')
                if r.decision else '',
                'by': r.decided_by.name if r.decided_by else '',
                'on': str(r.decided_at.date()) if r.decided_at else '',
                'note': r.decision_note or '',
                'new_contract_id': (r.new_contract_id.id
                                    if r.new_contract_id else 0),
                'new_contract': (r.new_contract_id.name
                                 if r.new_contract_id else ''),
                'exit_case_id': r.exit_case_id.id if r.exit_case_id else 0,
                'letter_id': r.letter_id.id if r.letter_id else 0,
            } for r in history if not (review and r.id == review.id)],
            'kinds': [{'id': k, 'label': v}
                      for k, v in EMPLOYEE_TYPE_LABEL.items()],
        }

    def _evaluation(self, review):
        """Where a conversion evaluation has got to, in P5's own words."""
        if not review or not review.review_id:
            return None
        evaluation = review.review_id
        return {
            'id': evaluation.id,
            'state': evaluation.state,
            'state_label': self._safe(lambda: evaluation.state_label(),
                                      default=''),
            'verdict': evaluation.verdict or '',
            'nominees': evaluation.nominee_count,
            'answers_in': evaluation.feedback_in,
            'answers_total': evaluation.feedback_total,
            'deadline': str(evaluation.feedback_deadline or ''),
        }

    # =====================================================================
    #  WRITES. Every one of them goes through the model that owns the fact.
    # =====================================================================
    @api.model
    def raise_decision(self, contract_id):
        self._require_write()
        review = self.env['pb.contract.review'].open_for(int(contract_id))
        review.notify_decision_needed()
        return {'review_id': review.id}

    @api.model
    def decision_preview(self, review_id, decision, months=None):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        review = self._review(review_id)
        return review.decision_preview(decision, months=months)

    @api.model
    def decide_terminate(self, review_id, note=None):
        self._require_write()
        return self._review(review_id).action_terminate(note=note)

    @api.model
    def request_extension(self, review_id, reason=None, months=None):
        self._require_write()
        return self._review(review_id).action_request_extension(
            reason=reason, months=months)

    @api.model
    def request_conversion(self, review_id):
        self._require_write()
        return self._review(review_id).action_request_conversion()

    @api.model
    def approve_extension(self, extension_id, note=None):
        """Agree an extension. The APPROVAL is checked by the chain, not here.

        `_require_write` is deliberately NOT called: the person who agrees an
        extension is the employee's own manager, who may hold no HR group at
        all. `biz.approval.chain.mixin._approval_can` — overridden on the
        request to admit exactly that person — is the boundary.
        """
        request = self.env['pb.contract.extension'].browse(
            int(extension_id)).exists()
        if not request:
            raise UserError(_("That extension request could not be found."))
        return request.action_approve(note=note)

    @api.model
    def refuse_extension(self, extension_id, note=None):
        request = self.env['pb.contract.extension'].browse(
            int(extension_id)).exists()
        if not request:
            raise UserError(_("That extension request could not be found."))
        return request.action_refuse(note=note)

    @api.model
    def set_employment_type(self, employee_id, kind):
        """Type somebody by hand — the one write this board makes to a person."""
        self._require_write()
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("That person could not be found."))
        if kind not in EMPLOYEE_TYPE_LABEL:
            raise UserError(_("That is not an employment type this build "
                              "knows."))
        emp.pb_set_employment_type(kind, reason=_(
            "Recorded as %(what)s by %(who)s.",
            what=EMPLOYEE_TYPE_LABEL.get(kind, kind),
            who=self.env.user.name))
        return {'kind': kind,
                'label': EMPLOYEE_TYPE_LABEL.get(kind, kind)}

    @api.model
    def run_automation(self):
        self._require_write()
        return self.env['pb.journey.case'].run_contract_automation()

    def _review(self, review_id):
        review = self.env['pb.contract.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That contract decision could not be found."))
        return review

    # ------------------------------------------------------------ the doors
    @api.model
    def open_contract_action(self, contract_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.contract',
                'res_id': int(contract_id), 'view_mode': 'form',
                'views': [[False, 'form']]}

    @api.model
    def open_employee_action(self, employee_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.employee',
                'res_id': int(employee_id), 'view_mode': 'form',
                'views': [[False, 'form']]}

    @api.model
    def open_review_action(self, review_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.contract.review',
                'res_id': int(review_id), 'view_mode': 'form',
                'views': [[False, 'form']]}

    @api.model
    def open_evaluation_action(self, evaluation_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.probation.review',
                'res_id': int(evaluation_id), 'view_mode': 'form',
                'views': [[False, 'form']]}

    @api.model
    def open_letter_action(self, letter_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        letter = self.env['pb.hr.letter'].browse(int(letter_id)).exists()
        if not letter:
            raise UserError(_("That letter could not be found."))
        return letter.action_open_pdf()

    @api.model
    def open_case_action(self, case_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.journey.case',
                'res_id': int(case_id), 'view_mode': 'form',
                'views': [[False, 'form']]}


def _when(days):
    """"in 12 days" / "ends today" / "6 days ago" — never a bare number."""
    if days is None:
        return _('no end date')
    if days == 0:
        return _('ends today')
    if days == 1:
        return _('ends tomorrow')
    if days > 1:
        return _('in %s days', days)
    if days == -1:
        return _('ended yesterday')
    return _('%s days ago', -days)


def _facet(rows, key, by_key=False):
    """The chips beside a list, counted from THAT LIST'S OWN rows (R80).

    `by_key` sorts alphabetically rather than by size, which for a `YYYY-MM`
    key is calendar order — the only order a month chip can sensibly be read
    in.
    """
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    order = (lambda kv: kv[0]) if by_key else (lambda kv: -kv[1])
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=order)]
