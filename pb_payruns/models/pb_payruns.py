# -*- coding: utf-8 -*-
import logging
import re
import unicodedata
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools import format_date, format_datetime

_logger = logging.getLogger(__name__)

# The stages the board draws and the words for them — imported rather than
# re-typed, so the board can never offer a stage the model does not have.
from .hr_payslip_run import (PB_BOARD_STATES, PB_STAGE_NAME,
                             _PB_GROUPS_MEMO_KEY, ReviewGroupsMemo)

STAGE_ORDER = list(PB_BOARD_STATES)
STAGE_LABEL = dict(PB_STAGE_NAME)
BOARD_LIMIT = 60
#: FILTER wave 5 — runs per lane per page, and per page of the list view.
LANE_PAGE = 30
LIST_PAGE = 60
#: The lanes the board loads: the three steps and the Rejected drawer.
LANE_KEYS = ('draft', 'approval_pending', 'done', 'cancel')

# The month journey the hero draws (PAYRUN BOARD redesign, 2026-10-11). The
# numbers are the Pay Run hub's own tracker stages (`pb.pay.hub`, _STAGE_DOC),
# so the chip in the hub's command bar and the hero below it can never
# disagree. Stage 5 is NOT a run state: "delivered" means a completed payslip
# delivery batch hangs off the run.
MONTH_STAGES = 5
_RUN_STAGE = {'draft': 2, 'approval_pending': 3, 'done': 4}

# NAV P3b — the readiness checklist on every open card. The attendance-close
# line is ADVICE: it never blocks Submit (pb_close's cardinal rule, restated).
# One line per open week, at most this many, then "+N more weeks".
CLOSE_LINES_MAX = 2
# Who may open Workforce › Close (pb_mission LENSES `close`.groups). The door
# is offered only to them; anyone else still reads the line and its owner.
_CLOSE_LENS_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)
_OPEN_STATES = ('draft', 'approval_pending')

# PRS P1 — the pay run screen.
#: People rows the screen payload carries at most; the counts cover everyone.
SCREEN_ROW_CAP = 2000
#: A take-home move this large against the previous run flags the person.
SCREEN_CHANGE_SHARE = 0.10
#: Month names a run's NAME may carry, English (full and short). Vietnamese
#: names are matched by `_VI_MONTH_RE` ("Tháng 10/2026", "tháng 10 năm 2026").
_EN_MONTHS = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sept': 9, 'sep': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12,
    'dec': 12,
}
_EN_MONTH_RE = re.compile(
    r'\b(' + '|'.join(sorted(_EN_MONTHS, key=len, reverse=True))
    + r')\.?[\s,/-]*(\d{4})\b', re.IGNORECASE)
_VI_MONTH_RE = re.compile(
    r'th[aá]ng\s*(\d{1,2})\s*(?:/|-|\.|\s+n[aă]m\s+|\s+)\s*(\d{4})\b',
    re.IGNORECASE)
#: The Approvals inbox and set-up screens (pb_approval_config, read softly).
_INBOX_ACTION = 'pb_approval_config.action_pb_approval_inbox'
_MATRIX_ACTION = 'pb_approval_config.action_pb_approval_matrix'
_MAKE_ACTION = 'om_hr_payroll.action_hr_payslip_by_employees'


class PbPayruns(models.AbstractModel):
    _name = 'pb.payruns'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Pay Runs board data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Pay Runs board metric failed: %s", e)
            return default

    # ============================================================ filter panel
    # FILTER wave 5. The board is on the shared filter panel (pb_filter_kit).
    # It used to load the newest 240 runs, keep 60 and filter those in the
    # browser, so a division chip could hide a run that was simply not loaded.
    # Now every count is the server's, and each lane pages on its own.

    def _pbf_model(self):
        return 'hr.payslip.run'

    def _pbf_screen(self):
        return 'payruns'

    def _pbf_base_domain(self):
        """The board's company rule as a domain.

        A run carries no company of its own (`_run_companies`): its live
        payslips' company decides, and a run with none (rejected, or not
        computed yet) falls back to its scheme's company — and to "this
        company" when it has neither, which the reader is always in.
        """
        co = self.env.companies.ids or [self.env.company.id]
        live = [('state', '!=', 'cancel')]
        if 'pb_formula_config_id' not in self.env['hr.payslip.run']._fields:
            return ['|', ('slip_ids', 'any', live + [('company_id', 'in', co)]),
                    ('slip_ids', 'not any', live)]
        return ['|', ('slip_ids', 'any', live + [('company_id', 'in', co)]),
                '&', ('slip_ids', 'not any', live),
                '|', ('pb_formula_config_id', '=', False),
                '|', ('pb_formula_config_id.company_id', '=', False),
                ('pb_formula_config_id.company_id', 'in', co)]

    def _pbf_search_fields(self):
        return ['name', 'pb_division_label']

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_sorts(self):
        return [
            {'key': 'latest', 'label': _('Latest period first'), 'order': 'date_end desc, id desc'},
            {'key': 'oldest', 'label': _('Oldest period first'), 'order': 'date_end asc, id asc'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
            {'key': 'people', 'label': _('Most people first'),
             'order': 'pb_employee_count desc, date_end desc, id desc'},
            {'key': 'gross', 'label': _('Biggest gross first'),
             'order': 'pb_total_gross desc, date_end desc, id desc'},
            {'key': 'net', 'label': _('Biggest net pay first'),
             'order': 'pb_total_net desc, date_end desc, id desc'},
        ]

    @api.model
    def _pbf_division_options(self):
        """One option per division on this database, named as the board
        names it (the scheme's own name: "Information Technology", not "It"),
        plus "No division" for traditional structure payroll."""
        _chips, names = self._divisions()
        keys = set(names)
        try:
            for value, _n in self.env['hr.payslip.run']._read_group(
                    [('pb_division', '!=', False), ('pb_division', '!=', '')],
                    ['pb_division'], ['__count']):
                if value:
                    keys.add(value)
        except Exception as e:  # noqa: BLE001
            _logger.debug("Pay Runs division keys failed: %s", e)
        opts = [{'value': k, 'label': names.get(k) or self._pbf_pretty(k),
                 'domain': [('pb_division', '=', k)]} for k in keys]
        opts.sort(key=lambda o: (o['label'] or '').lower())
        opts.append({'value': '__none', 'label': _('No division'), 'tone': 'slate',
                     'domain': ['|', ('pb_division', '=', False), ('pb_division', '=', '')]})
        return opts

    def _pbf_spec(self):
        draft = ['|', ('state', '=', 'draft'), ('state', '=', False)]
        spec = [
            # ---- pinned: where is it, which month, which part of the business
            {'key': 'stage', 'label': _('Where it is'), 'icon': 'activity', 'group': 'pay',
             'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'draft', 'label': _('Draft'), 'tone': 'slate', 'domain': draft},
                 {'value': 'approval_pending', 'label': _('Waiting for approval'),
                  'tone': 'amber', 'domain': [('state', '=', 'approval_pending')]},
                 {'value': 'done', 'label': _('Done'), 'tone': 'green',
                  'domain': [('state', '=', 'done')]},
                 {'value': 'cancel', 'label': _('Rejected'), 'tone': 'rose',
                  'domain': [('state', '=', 'cancel')]},
             ]},
            {'key': 'period', 'label': _('Pay period ends'), 'icon': 'calendar', 'group': 'dates',
             'type': 'date', 'path': 'date_end', 'pinned': True,
             'presets': ['this_month', 'last_month', 'this_quarter', 'this_year', 'last_year']},
            {'key': 'division', 'label': _('Division'), 'icon': 'layers', 'group': 'work',
             'type': 'choice', 'pinned': True, 'requires': ['pb_division'],
             'options': self._pbf_division_options()},
            # ---- more filters
            {'key': 'mine', 'label': _('Whose turn'), 'icon': 'userCheck', 'group': 'people',
             'type': 'choice', 'requires': ['pb_awaiting_me'],
             'options': [
                 {'value': 'me', 'label': _('Waiting on me'), 'tone': 'amber',
                  'domain': [('pb_awaiting_me', '=', True)]},
                 {'value': 'others', 'label': _('Waiting on someone else'), 'tone': 'slate',
                  'domain': [('state', '=', 'approval_pending'), ('pb_awaiting_me', '=', False)]},
             ]},
            {'key': 'sentback', 'label': _('Sent back'), 'icon': 'rotate', 'group': 'pay',
             'type': 'choice', 'requires': ['pb_return_note'],
             'options': [
                 {'value': 'yes', 'label': _('Sent back to be fixed'), 'tone': 'amber',
                  'domain': draft + [('pb_return_note', '!=', False)]},
                 {'value': 'no', 'label': _('Not sent back'), 'tone': 'slate',
                  'domain': ['|', ('pb_return_note', '=', False),
                             '&', ('state', '!=', 'draft'), ('state', '!=', False)]},
             ]},
            {'key': 'health', 'label': _('Checks'), 'icon': 'shieldCheck', 'group': 'pay',
             'type': 'choice', 'requires': ['pb_balance_ok', 'pb_unsourced_count'],
             'help': _('A check fails when gross minus deductions is not net pay, or when '
                       'payslips were worked out with no source data.'),
             'options': [
                 {'value': 'fail', 'label': _('Something needs a check'), 'tone': 'rose',
                  'domain': ['|', ('pb_balance_ok', '=', False), ('pb_unsourced_count', '>', 0)]},
                 {'value': 'ok', 'label': _('Every check passes'), 'tone': 'green',
                  'domain': [('pb_balance_ok', '=', True),
                             '|', ('pb_unsourced_count', '=', False), ('pb_unsourced_count', '=', 0)]},
             ]},
            {'key': 'scheme', 'label': _('Payroll scheme'), 'icon': 'sigma', 'group': 'pay',
             'type': 'many2one', 'path': 'pb_formula_config_id', 'label_sudo': True,
             'none_label': _('No scheme')},
            {'key': 'currency', 'label': _('Currency'), 'icon': 'coins', 'group': 'pay',
             'type': 'many2one', 'path': 'pb_currency_id', 'none_label': _('Not set')},
            {'key': 'prepared', 'label': _('Prepared by'), 'icon': 'user', 'group': 'people',
             'type': 'many2one', 'path': 'pb_prepared_uid', 'label_sudo': True,
             'none_label': _('Not recorded')},
            {'key': 'refund', 'label': _('Kind of run'), 'icon': 'undo', 'group': 'pay',
             'type': 'choice', 'requires': ['credit_note'],
             'options': [
                 {'value': 'yes', 'label': _('Refund runs'), 'tone': 'rose',
                  'domain': [('credit_note', '=', True)]},
                 {'value': 'no', 'label': _('Regular runs'), 'tone': 'slate',
                  'domain': [('credit_note', '=', False)]},
             ]},
            {'key': 'people', 'label': _('People paid'), 'icon': 'users', 'group': 'people',
             'type': 'number', 'path': 'pb_employee_count'},
            {'key': 'net', 'label': _('Net pay'), 'icon': 'banknote', 'group': 'pay',
             'type': 'number', 'path': 'pb_total_net', 'unit': 'money',
             'help': _('Each run in its own money: a run paid in another currency is '
                       'compared in that currency.')},
        ]
        # Paid is the bank's answer, stamped on each payslip when its money
        # left (pb_pay_delivery) — a run is paid when every one of its done
        # payslips is. Absent on a database without that module.
        paid = self._paid_domains()
        if paid:
            spec.insert(3, {
                'key': 'paid', 'label': _('Paid'), 'icon': 'wallet', 'group': 'pay',
                'type': 'choice',
                'options': [
                    {'value': 'topay', 'label': _('Approved, not paid yet'), 'tone': 'blue',
                     'domain': paid[0]},
                    {'value': 'paid', 'label': _('Paid'), 'tone': 'green',
                     'domain': paid[1]},
                ]})
        # A run belongs to the company of its payslips; listed only where the
        # reader works in more than one.
        if len(self.env.companies) > 1:
            spec.append({
                'key': 'company', 'label': _('Company'), 'icon': 'landmark', 'group': 'work',
                'type': 'choice',
                'options': [{'value': c.id, 'label': c.name,
                             'domain': [('slip_ids', 'any', [('company_id', '=', c.id),
                                                             ('state', '!=', 'cancel')])]}
                            for c in self.env.companies],
            })
        return spec

    @api.model
    def _paid_domains(self):
        """(approved but not paid, paid) as domains, or None without
        pb_pay_delivery. The run's own `pb_paid` is computed, not stored: a
        done run is paid when it has done payslips and every one carries the
        stamp the payment release writes (`pb_paid_on`)."""
        if 'pb_paid_on' not in self.env['hr.payslip']._fields:
            return None
        done = [('state', '=', 'done')]
        unpaid_slip = [('state', '=', 'done'), ('pb_paid_on', '=', False)]
        topay = done + ['|', ('slip_ids', 'not any', done), ('slip_ids', 'any', unpaid_slip)]
        paid = done + [('slip_ids', 'any', done), ('slip_ids', 'not any', unpaid_slip)]
        return topay, paid

    def _pbf_builtin_views(self):
        this_month = {'preset': 'this_month'}
        return [
            {'key': 'all', 'label': _('All pay runs'), 'icon': 'calendar', 'filters': {}},
            {'key': 'mine', 'label': _('Waiting on me'), 'filters': {'mine': ['me']}},
            {'key': 'month', 'label': _('This month'), 'filters': {'period': this_month}},
            {'key': 'sentback', 'label': _('Sent back'), 'filters': {'sentback': ['yes']}},
            {'key': 'topay', 'label': _('Approved, not paid'), 'filters': {'paid': ['topay']}},
            {'key': 'rejected', 'label': _('Rejected'), 'filters': {'stage': ['cancel']}},
        ]

    # ------------------------------------------------- the board's own calls
    @api.model
    def _month_runs(self):
        """The live runs the hero talks about: those whose period ENDS in the
        calendar month (the date the period filter and the board's month
        groups read), whatever the panel shows."""
        Run = self.env['hr.payslip.run']
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        nxt = first + relativedelta(months=1)
        domain = Domain.AND([
            Domain(self._pbf_base_domain()),
            Domain([('state', '!=', 'cancel'), ('date_end', '>=', first), ('date_end', '<', nxt)]),
        ])
        return Run.search(domain, order='date_end desc, id desc', limit=BOARD_LIMIT)

    @api.model
    def get_board_head(self):
        """Everything above the lanes, un-narrowed by the panel: the month
        the hero speaks about with its own runs, the lane names, who may
        submit. The lanes load through `get_board_page`."""
        company = self.env.company
        cur = company.currency_id
        month = self._safe(self._month_runs, default=self.env['hr.payslip.run'].browse())
        built = self._board_cards(month)
        return {
            'currency': cur.symbol or '',
            'currency_name': cur.name or '',
            'company': company.name,
            'can_submit': built['may_write'],
            'columns': [{'key': s, 'label': STAGE_LABEL[s]} for s in STAGE_ORDER],
            'month_batches': built['batches'],
            'period': self._period_block(built['batches'], company),
        }

    @api.model
    def _lane_domain(self, key):
        if key == 'draft':
            return ['|', ('state', '=', 'draft'), ('state', '=', False)]
        return [('state', '=', key)]

    @api.model
    def get_board_page(self, filters=None, search=None, sort=None, lane=None,
                       offset=0, limit=None):
        """The board for the panel's current state.

        lane=None   every lane (Draft, Waiting for approval, Done, and the
                    Rejected drawer), first page of each, with each lane's
                    total and the counts its header flag says;
        lane=<key>  the next page of that one lane ("Show N more");
        lane='list' one page of the list view, every state, in the sort.
        """
        Run = self.env['hr.payslip.run']
        try:
            offset = max(0, int(offset or 0))
            limit = int(limit) if limit else 0
        except (TypeError, ValueError):
            offset, limit = 0, 0
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'date_end desc, id desc'

        def cards(runs):
            built = self._board_cards(runs)
            return built['batches']

        def currencies_of(batches):
            return sorted({b['currency_name'] for b in batches if b.get('currency_name')})

        if lane == 'list':
            limit = max(1, min(limit or LIST_PAGE, 200))
            runs = Run.search(domain, order=order, offset=offset, limit=limit)
            rows = cards(runs)
            return {'rows': rows, 'total': Run.search_count(domain), 'offset': offset,
                    'currencies': currencies_of(rows)}

        limit = max(1, min(limit or LANE_PAGE, 120))
        keys = [lane] if lane in LANE_KEYS else list(LANE_KEYS)
        picked = {}
        union = Run.browse()
        for key in keys:
            lane_dom = Domain.AND([domain, Domain(self._lane_domain(key))])
            runs = Run.search(lane_dom, order=order, offset=offset if lane else 0, limit=limit)
            picked[key] = (lane_dom, runs)
            union |= runs
        by_id = {b['id']: b for b in cards(union)}
        out = {}
        for key, (lane_dom, runs) in picked.items():
            out[key] = {
                'rows': [by_id[r.id] for r in runs if r.id in by_id],
                'total': Run.search_count(lane_dom),
                'flags': self._safe(lambda d=lane_dom, k=key: self._lane_flags(k, d), default={}),
            }
        return {'lanes': out, 'offset': offset if lane else 0,
                'currencies': currencies_of(list(by_id.values()))}

    @api.model
    def _lane_flags(self, key, lane_dom):
        """The one sentence a lane header says, counted over the WHOLE lane
        as filtered (not the page the lane shows)."""
        Run = self.env['hr.payslip.run']

        def n(extra):
            return Run.search_count(Domain.AND([lane_dom, Domain(extra)]))
        if key == 'draft':
            return {'back': n([('pb_return_note', '!=', False)]),
                    'bad': n(['|', ('pb_balance_ok', '=', False), ('pb_unsourced_count', '>', 0)])}
        if key == 'approval_pending':
            return {'mine': n([('pb_awaiting_me', '=', True)])}
        if key == 'done':
            paid = self._paid_domains()
            return {'topay': n(paid[0]) if paid else 0}
        return {}

    @api.model
    def get_board_data(self):
        """The whole board in one payload, as it was before the filter panel.

        Kept for the readers that are not the board (FILTER ruling R4):
        Learn's "Right now" (pb_payruns_learn), the learn manifests and the
        tests read it. The board itself loads through `get_board_head` and
        the paged `get_board_page` since FILTER wave 5.
        """
        company = self.env.company
        cur = company.currency_id
        Run = self.env['hr.payslip.run']
        runs = self._safe(
            lambda: Run.search([], order='date_end desc, id desc',
                               limit=BOARD_LIMIT * 4),
            default=Run.browse())
        owner = self._run_companies(runs)
        allowed = set(self.env.companies.ids or [company.id])
        runs = runs.filtered(
            lambda r: owner.get(r.id, company.id) in allowed)[:BOARD_LIMIT]
        built = self._board_cards(runs, owner=owner)
        batches = built['batches']
        stage_counts = built['stage_counts']
        may_write = built['may_write']

        drawn = [s for s in STAGE_ORDER]
        columns = [{'key': s, 'label': STAGE_LABEL[s], 'count': stage_counts.get(s, 0)}
                   for s in drawn]
        divisions, _division_name = self._divisions()

        # Demo users get the board pre-filtered to the live demo month (June 2026).
        is_demo_user = self._safe(
            lambda: self.env.user.has_group('pb_demo.group_payobook_demo'),
            default=False)
        demo_period = {'from': '2026-06-01', 'to': '2026-06-30'} if is_demo_user else None

        currencies = sorted({b['currency_name'] for b in batches if
                             b.get('currency_name')})
        return {
            'currency': cur.symbol or '',
            'currency_name': cur.name or '',
            # More than one money on the board is worth SAYING: the stage
            # total below only ever adds up the active company's own runs.
            'many_currencies': len(currencies) > 1,
            'currencies': currencies,
            'company': company.name,
            'divisions': divisions,
            'is_demo_user': is_demo_user,
            'demo_period': demo_period,
            'can_submit': may_write,
            'columns': columns,
            'batches': batches,
            'rejected_count': stage_counts.get('cancel', 0),
            # The month the hero talks about: the calendar month, as the Pay
            # Run hub's own tracker keys it — and, since NAV P3b, its two
            # dates from the Payroll calendar.
            'period': self._period_block(batches, company),
            'kpis': {
                'total': len(batches),
                'done': stage_counts.get('done', 0),
                'in_pipeline': stage_counts.get('draft', 0)
                + stage_counts.get('approval_pending', 0),
                'my_pending': built['my_pending'],
                'period_net': built['period_net'],
            },
        }

    @api.model
    def _board_cards(self, runs, owner=None):
        """Every card the board draws for `runs`, built in a fixed number of
        reads however many runs there are. Shared by `get_board_data` and the
        filter panel's paged `get_board_page`, so a card is one thing.

        Returns {'batches', 'stage_counts', 'my_pending', 'period_net',
        'may_write'}.
        """
        company = self.env.company
        cur = company.currency_id
        Run = self.env['hr.payslip.run']

        # WHO MAY DO WHAT IS NO LONGER A GROUP QUESTION. A pay run is signed
        # off by whoever the published route resolves to, so the board asks the
        # engine which runs are waiting on THIS person rather than deciding it
        # from a role. Submitting and rejecting are ordinary edits of the run,
        # so they follow the run's own write access.
        may_write = self._safe(lambda: Run.has_access('write'), default=False)
        awaiting = self._safe(lambda: Run._pb_runs_awaiting(self.env.uid),
                              default=set())
        if owner is None:
            owner = self._run_companies(runs)
        currency_of = self._currency_by_company()
        scheme_currency_of = self._scheme_currency_by_run(runs)
        # Where each approved run's money and payslips have got to — one query
        # per delivery model, never one per card.
        delivery_of = self._delivery_by_run(runs)
        # Division names, read ONCE off the schemes that carry a division. The
        # stored label title-cases the key ("it" → "It"); the scheme's own name
        # says "Information Technology" and is what the chips already showed.
        divisions, division_name = self._divisions()

        # Batch-compute all run totals in ONE pass (single SQL) instead of letting
        # each per-run field access trigger its own aggregation.
        self._safe(lambda: runs.mapped('pb_total_net'))
        # NAV P3b — everything the open cards' checklists need, read once for
        # the whole board: the Payroll owner per company, the attendance
        # owner per run, and the day locks of every open run's period.
        readiness = self._safe(lambda: self._readiness_context(runs, owner),
                               default=None) or self._empty_readiness()

        batches = []
        stage_counts = {s: 0 for s in STAGE_ORDER}
        stage_counts['cancel'] = 0
        my_pending = 0
        period_net = 0.0

        for run in runs:
            state = run.state or 'draft'
            stage_counts[state] = stage_counts.get(state, 0) + 1
            waiting_on_me = run.id in awaiting
            if state == 'draft':
                next_action, can_act = 'submit', may_write
            elif state == 'approval_pending':
                next_action, can_act = 'decide', waiting_on_me
            else:
                next_action, can_act = '', False
            if waiting_on_me:
                my_pending += 1

            net = self._safe(lambda r=run: r.pb_total_net)
            run_company = owner.get(run.id, company.id)
            # The scheme decides; the company is only the fallback for a run
            # with no scheme at all (traditional structure payroll).
            run_currency = (scheme_currency_of.get(run.id)
                            or currency_of.get(run_company)
                            or {'name': cur.name or '',
                                'symbol': cur.symbol or ''})
            if state == 'done' and run_currency['name'] == (cur.name or ''):
                # Only ever add up money of the SAME kind. A cross-currency
                # total is not a rounding problem, it is a wrong number.
                period_net += net or 0.0

            division = run.pb_division or ''
            delivery = delivery_of.get(run.id) or self._empty_delivery()
            approval = self._approval_chip(run)
            balance_ok = self._safe(lambda r=run: bool(r.pb_balance_ok),
                                    default=True)
            balance_gap = self._safe(lambda r=run: r.pb_balance_gap) or 0.0
            unsourced = self._safe(lambda r=run: r.pb_unsourced_count) or 0
            checks, ready, close_weeks = self._safe(
                lambda r=run: self._run_checks(
                    r, state, next_action, run_company, readiness,
                    unsourced=unsourced, balance_ok=balance_ok,
                    balance_gap=balance_gap,
                    symbol=run_currency['symbol']),
                default=([], False, None))
            batches.append({
                'id': run.id,
                'name': run.name or '—',
                'state': state,
                'stage_label': STAGE_LABEL.get(state, state),
                'date_start': str(run.date_start or ''),
                'date_end': str(run.date_end or ''),
                'period': self._fmt_period(run.date_start, run.date_end),
                # The calendar month the card files under ('YYYY-MM'). A run
                # is keyed by the period it pays for, so the END date names
                # the month: a 25th-to-24th cycle belongs to the month it
                # closes in.
                'month': self._month_key(run.date_end or run.date_start),
                'month_label': self._month_label(run.date_end or run.date_start),
                'employees': self._safe(lambda r=run: r.pb_employee_count),
                'net': net or 0.0,
                'gross': self._safe(lambda r=run: r.pb_total_gross) or 0.0,
                'deductions': self._safe(lambda r=run: r.pb_total_deductions) or 0.0,
                'employer_cost': self._safe(
                    lambda r=run: r.pb_total_employer_cost) or 0.0,
                # The run's own health, already stored beside its totals.
                'balance_ok': balance_ok,
                'balance_gap': balance_gap,
                'unsourced': unsourced,
                # NAV P3b — can this run move, and who must act: one line per
                # open thing, each with its owner, and `ready` when a draft has
                # nothing in its way. The three keys above stay for Learn.
                'checks': checks,
                'ready': ready,
                'close_weeks': close_weeks,
                'credit_note': bool(run.credit_note),
                'next_action': next_action,
                'can_act': can_act,
                'can_reject': may_write and state in ('draft',
                                                      'approval_pending'),
                'awaiting_me': waiting_on_me,
                # The route this run is on, and where it has got to — read off
                # the request rather than off a state name, because "who is it
                # with" is now a person, not a tier.
                'approval': approval,
                # why this run came back, if an approver sent it back
                'return_note': run.pb_return_note or '',
                'return_by': run.pb_return_uid.name or '',
                'return_on': self._fmt_date(run.pb_return_date),
                # why this run was rejected (kept for good once it is)
                'reject_note': run.pb_reject_note or '',
                'reject_by': run.pb_reject_uid.name or '',
                'prepared_by': run.pb_prepared_uid.name or '',
                # Where an approved run's money and payslips have got to.
                'delivery': delivery,
                # What happened to it, in order, in words.
                'history': self._history(run, approval, delivery),
                # The division key the board's chips filter on, and its name.
                'division': division,
                'division_label': division_name.get(division)
                or run.pb_division_label or '',
                # Each run priced in ITS OWN company's money.
                'company_id': run_company,
                'currency': run_currency['symbol'],
                'currency_name': run_currency['name'],
            })
        return {'batches': batches, 'stage_counts': stage_counts,
                'my_pending': my_pending, 'period_net': period_net,
                'may_write': may_write}

    # ============================================================ run screen
    # PRS P1 (docs/handovers/payrunscreen/PRS_P1_HANDOVER.md). Everything the
    # ONE pay run screen shows, in one round trip, already in words.
    #
    # READ-ONLY. Nothing below writes a record. The facts the board already
    # knows come from the board's own card (`_board_cards`), never rebuilt;
    # what only this screen needs is read in a fixed number of queries
    # however many payslips the run has. Every optional piece (route preview,
    # previous run, Source Atlas, statement) sits inside `_safe`, so one
    # failure never blanks the screen.

    @api.model
    def get_run_screen(self, run_id, parts=None):
        """The pay run screen's payload for one run. See the handover for
        the exact keys; a run the reader cannot read raises AccessError.

        `parts` (PRS P2, item 16) lets the screen draw before the slowest
        read — working out who signs a DRAFT off (the approval engine's own
        route preview, ~230 ms of a 520-payslip run's ~630 ms):

        * None / 'all' — everything, in one go (tests, the old callers);
        * 'main'  — everything except that preview: a draft with payslips
          comes back with `route.mode == 'pending'`, a pending route check
          row, and `route_pending: True`;
        * 'route' — ONLY the pieces the route decides: route, checks,
          journey, primary, actions (Split needs the same groups read).

        The screen asks for 'main', then for 'route' whenever
        `route_pending` is set — the same code path for every run.
        """
        parts = parts if parts in ('main', 'route') else 'all'
        _ = self.env._
        Run = self.env['hr.payslip.run']
        try:
            rid = int(run_id or 0)
        except (TypeError, ValueError):
            rid = 0
        run = Run.browse(rid).exists() if rid else Run.browse()
        if not run:
            raise UserError(_("This pay run no longer exists. Go back to Pay "
                              "runs and open it from there."))
        # The gate. Everything after it reads what this person may already
        # read on the board and on the run's own form.
        run.check_access('read')

        built = self._board_cards(run)
        card = built['batches'][0]
        may_write = built['may_write']
        state = card['state']
        sent_back = state == 'draft' and bool(run.pb_return_note)

        currency = run.pb_currency_id or self.env.company.currency_id
        money = lambda amount, short=False: self._screen_money(  # noqa: E731
            amount, currency, short=short)

        # ---- the payslips: as the reader sees them, then their facts in SQL
        slips = run.slip_ids
        facts = self._safe(lambda: self._screen_slip_facts(slips),
                           default={}) or {}
        if slips and not facts:
            # The one query failed: read the same facts the slow way rather
            # than tell the reader a run full of payslips has none.
            facts = {s.id: {'state': s.state or 'draft',
                            'employee_id': s.employee_id.id or False,
                            'name': s.name or '', 'lines': len(s.line_ids),
                            'calculated_at': False, 'unsourced': False}
                     for s in slips}
        totals =self._safe(lambda: Run._pb_slip_totals(run.ids),
                            default={}) or {}
        live_facts = [f for f in facts.values() if f['state'] != 'cancel']
        live_count = len(live_facts)
        uncalculated = sum(1 for f in live_facts if not f['lines'])
        calculated_count = live_count - uncalculated

        # ---- the run before this one, for "compared with last month"
        prev = Run.browse()
        if live_count:
            prev = self._safe(lambda: self._screen_previous_run(run, currency),
                              default=Run.browse()) or Run.browse()
        prev_month = (self._safe(lambda: format_date(
            self.env, prev.date_end or prev.date_start, date_format='MMMM'),
            default='') if prev else '')

        # PRS P2 item 16: only a draft with payslips previews its route, so
        # only that case is ever deferred.
        defer = parts == 'main' and state == 'draft' and bool(live_count)
        # Which (scheme, part of the business, currency) groups the payslips
        # fall in, worked out ONCE: the route preview and the Split offer both
        # need it, and on rize it is the single most expensive read here.
        groups = None
        if state == 'draft' and live_count and not defer:
            run = run.with_context(**{_PB_GROUPS_MEMO_KEY: ReviewGroupsMemo()})
            groups = self._safe(lambda: run._pb_review_groups(), default=None)
        if defer:
            route = self._screen_route_pending(run)
        else:
            route = self._screen_route(run, card, state, live_count,
                                       groups=groups)
        checks = self._screen_checks(run, card, state, live_count,
                                     uncalculated, facts, route,
                                     may_write)
        bad = sum(1 for item in checks['items'] if not item['ok'])
        # "All N checks pass" counts the four real checks, never the board's
        # amber advice lines shown under them.
        n_checks = sum(1 for item in checks['items'] if item['key'] in
                       ('data', 'balance', 'calculated', 'route'))
        notes = sum(1 for item in checks['items'] if item.get('tone') == 'amber')
        journey = self._screen_journey(run, card, state, live_count, bad,
                                       n_checks, sent_back, notes=notes)
        primary = self._screen_primary(run, card, state, live_count, bad,
                                       sent_back, may_write, route)
        split_ok = bool(state == 'draft' and may_write and groups
                        and len(groups) > 1)
        actions = self._screen_actions(run, card, state, may_write,
                                       live_count, calculated_count, prev_month,
                                       split_ok)
        if parts == 'route':
            return {'route': route, 'checks': checks, 'journey': journey,
                    'primary': primary, 'actions': actions,
                    'route_pending': False}

        prev_net_of = {}
        if prev:
            prev_net_of = self._safe(lambda: self._screen_net_by_employee(prev),
                                     default={}) or {}
        people = self._screen_people(facts, totals, state, prev,
                                     prev_net_of, prev_month)

        net = card['net'] or 0.0
        gross = card['gross'] or 0.0
        employer = card['employer_cost'] or 0.0
        n = card['employees'] or 0
        if state == 'cancel':
            sentence = _("This pay run was rejected, so nobody is paid from it.")
        elif not n:
            sentence = _("No payslips yet, so there is no money on this run.")
        elif employer:
            sentence = (_("1 person takes home %(net)s. With the company's own "
                          "contributions, this run costs %(total)s in all.",
                          net=money(net, True),
                          total=money(gross + employer, True)) if n == 1
                        else _("%(n)s people take home %(net)s. With the "
                               "company's own contributions, this run costs "
                               "%(total)s in all.", n=n, net=money(net, True),
                               total=money(gross + employer, True)))
        else:
            sentence = (_("1 person takes home %(net)s, out of %(gross)s gross "
                          "pay.", net=money(net, True),
                          gross=money(gross, True)) if n == 1
                        else _("%(n)s people take home %(net)s, out of "
                               "%(gross)s gross pay.", n=n,
                               net=money(net, True), gross=money(gross, True)))

        compare, compare_none = None, None
        if live_count and prev:
            compare = self._safe(
                lambda: self._screen_compare(prev, net), default=None)
        elif live_count:
            compare_none = self._screen_compare_none(run)

        delivery = dict(card['delivery'])
        delivery.update(self._screen_delivery_steps(run, card, state,
                                                     live_count, net, money))

        Slip = self.env['hr.payslip']
        return {
            'run': card,
            'header': {
                'title': run.name or '',
                'work_dates': self._screen_work_dates(run.date_start,
                                                      run.date_end),
                # sudo: a payroll officer who may open the run is not always
                # allowed to open the SCHEME (`_pb_review_groups` says why);
                # its name is a label on the run, not the scheme handed over.
                'scheme': (run.sudo().pb_formula_config_id.name or '')
                if 'pb_formula_config_id' in Run._fields else '',
                'people': n,
                'currency_name': currency.name or '',
                'symbol': currency.symbol or currency.name or '',
                'decimals': currency.decimal_places,
                'status': self._screen_status(state, sent_back),
            },
            'date_mismatch': self._safe(
                lambda: self._screen_date_mismatch(run), default=None),
            'journey': journey,
            'primary': primary,
            'money': {
                'net': net, 'gross': gross,
                'deductions': card['deductions'] or 0.0,
                'employer_cost': employer,
                'total_cost': gross + employer,
                'sentence': sentence,
            },
            'compare': compare,
            'compare_none': compare_none,
            'checks': checks,
            'route': route,
            'delivery': delivery,
            'people': people,
            'settings_editable': state == 'draft' and may_write,
            'actions': actions,
            'bulk': {
                'recalc': (state == 'draft' and may_write and bool(live_count)
                           and hasattr(Slip, 'action_recompute_formula_lines')),
                'pdf': state != 'cancel' and bool(calculated_count),
                'delete': state == 'draft' and may_write and bool(live_count),
            },
            'statement_available': 'pb_statement_json' in Slip._fields,
            'route_pending': defer,
        }

    # ---------------------------------------------------------- run screen: words
    @api.model
    def _screen_money(self, amount, currency, short=False):
        """Money as a reader writes it, in the run's own currency.

        Full form: ₫1,250,000 / $1,250.50 — the currency's own decimals, so
        dong never shows ".00" (PRS C4). Short form for sentences: ₫1.62
        billion, ₫3.5 million — trailing zeros dropped, never "₫2.00 billion".
        """
        _ = self.env._
        symbol = currency.symbol or currency.name or ''
        value = float(amount or 0.0)
        sign = '−' if value < 0 else ''
        value = abs(value)

        def trim(text):
            return text.rstrip('0').rstrip('.') if '.' in text else text

        if short and value >= 1e9:
            return _("%(amount)s billion",
                     amount='%s%s%s' % (sign, symbol, trim('%.2f' % (value / 1e9))))
        if short and value >= 1e6:
            return _("%(amount)s million",
                     amount='%s%s%s' % (sign, symbol, trim('%.1f' % (value / 1e6))))
        decimals = max(int(currency.decimal_places or 0), 0)
        return '%s%s%s' % (sign, symbol, '{:,.{d}f}'.format(value, d=decimals))

    @api.model
    def _screen_pct(self, value):
        """12 → '12', 2.44 → '2.4' (one decimal, trailing zero dropped)."""
        text = '%.1f' % abs(value)
        return text[:-2] if text.endswith('.0') else text

    @api.model
    def _initials(self, name):
        """Two letters for an avatar: first and last word of the name."""
        words = [w for w in (name or '').replace('DEMO ', '', 1).split()
                 if w[:1].isalpha()]
        if not words:
            return ''
        if len(words) == 1:
            return words[0][:1].upper()
        return (words[0][:1] + words[-1][:1]).upper()

    @api.model
    def _screen_status(self, state, sent_back):
        _ = self.env._
        if state == 'draft':
            return ({'key': 'sent_back', 'label': _("Sent back")} if sent_back
                    else {'key': 'draft', 'label': _("Draft")})
        if state == 'approval_pending':
            return {'key': 'pending', 'label': _("Waiting for approval")}
        if state == 'done':
            return {'key': 'done', 'label': _("Approved")}
        return {'key': 'rejected', 'label': _("Rejected")}

    @api.model
    def _screen_work_dates(self, d1, d2):
        """"1 – 30 Sep 2026", "16 Sep – 15 Oct 2026", "16 Dec 2026 – 15 Jan
        2027" — the reader's own language for the month names."""
        if not d1 or not d2:
            return self._fmt_period(d1, d2)

        def fmt(d, pattern):
            return self._safe(lambda: format_date(self.env, d, date_format=pattern),
                              default=str(d))
        if (d1.year, d1.month) == (d2.year, d2.month):
            left = fmt(d1, 'd')
        elif d1.year == d2.year:
            left = fmt(d1, 'd MMM')
        else:
            left = fmt(d1, 'd MMM y')
        return '%s – %s' % (left, fmt(d2, 'd MMM y'))

    @api.model
    def _screen_named_month(self, name):
        """(year, month) a run's NAME speaks of, or None."""
        text = unicodedata.normalize('NFC', name or '')
        found = _EN_MONTH_RE.search(text)
        if found:
            return int(found.group(2)), _EN_MONTHS[found.group(1).lower()]
        found = _VI_MONTH_RE.search(text)
        if found:
            month = int(found.group(1))
            if 1 <= month <= 12:
                return int(found.group(2)), month
        return None

    @api.model
    def _screen_main_month(self, d1, d2):
        """(year, month) holding most of the days d1..d2; a tie goes to the
        later month, the one the board files the run under."""
        best, best_days = None, -1
        start = d1
        while start <= d2:
            month_end = start + relativedelta(day=31)
            end = min(month_end, d2)
            days = (end - start).days + 1
            if days >= best_days:
                best, best_days = (start.year, start.month), days
            start = month_end + timedelta(days=1)
        return best

    @api.model
    def _screen_date_mismatch(self, run):
        """R2 — a plain warning when the name names another month than the
        dates cover (rize 1591: "… October 2026" over 1 – 30 Sep 2026)."""
        if not run.date_start or not run.date_end or run.date_end < run.date_start:
            return None
        named = self._screen_named_month(run.name)
        if not named:
            return None
        main = self._screen_main_month(run.date_start, run.date_end)
        if named == main:
            return None
        _ = self.env._
        named_label = self._safe(lambda: format_date(
            self.env, date(named[0], named[1], 1), date_format='MMMM y'),
            default='%s/%s' % (named[1], named[0]))
        dates = self._screen_work_dates(run.date_start, run.date_end)
        if run.state == 'draft':
            text = _("The name says %(named)s, but the dates are %(dates)s. "
                     "Check the dates before sending it.",
                     named=named_label, dates=dates)
        else:
            text = _("The name says %(named)s, but the dates are %(dates)s.",
                     named=named_label, dates=dates)
        return {'text': text}

    # ---------------------------------------------------------- run screen: reads
    @api.model
    def _screen_slip_facts(self, slips):
        """{slip id: {'state', 'employee_id', 'name', 'lines': n,
        'unsourced': bool, 'calculated_at': dt}} in ONE query, oldest first.

        `slips` is the run's payslips AS THE READER SEES THEM (the one2many
        applies the payslip record rules); only their ids reach the query.
        `unsourced` is the run's own rule (`_compute_pb_totals`) applied per
        payslip. Read in SQL rather than record by record: on a 520-payslip
        run the per-record attribute reads alone cost ~350 ms.
        """
        if not slips:
            return {}
        Slip = self.env['hr.payslip']
        self.env['hr.payslip.line'].flush_model(['slip_id'])
        source_aware = all(f in Slip._fields for f in (
            'pb_sourced_inputs', 'calculation_method', 'formula_input_sources'))
        columns = ['state', 'employee_id', 'name']
        if source_aware:
            columns += ['pb_sourced_inputs', 'calculation_method',
                        'formula_input_sources']
        Slip.flush_model(columns)
        unsourced = ("""(p.state != 'cancel'
                         AND COALESCE(p.pb_sourced_inputs, 0) = 0
                         AND p.calculation_method = 'formula'
                         AND p.formula_input_sources IS NOT NULL
                         AND p.formula_input_sources <> '')"""
                     if source_aware else 'FALSE')
        self.env.cr.execute("""
            SELECT p.id, p.state, p.employee_id, p.name,
                   COUNT(l.id), MAX(l.create_date), """ + unsourced + """
            FROM hr_payslip p
            LEFT JOIN hr_payslip_line l ON l.slip_id = p.id
            WHERE p.id IN %s
            GROUP BY p.id
            ORDER BY p.id
        """, (tuple(slips.ids),))
        return {sid: {'state': st or 'draft', 'employee_id': eid or False,
                      'name': name or '', 'lines': lines or 0,
                      'calculated_at': at, 'unsourced': bool(flag)}
                for sid, st, eid, name, lines, at, flag
                in self.env.cr.fetchall()}

    @api.model
    def _screen_month_before(self, run):
        """(first, last) day of the calendar month just before the month
        this run is filed under — its END date's month, as on the board."""
        anchor = run.date_end or run.date_start
        if not anchor:
            return None
        first = anchor.replace(day=1) - relativedelta(months=1)
        return first, first + relativedelta(day=31)

    @api.model
    def _screen_previous_run(self, run, currency):
        """The run "Compared with" reads (R5, 2026-11-04, narrowing R3).

        ONLY a run of the SAME KIND — the scheme map's kind of run
        (`_pb_kind_key`: regular / mid-month advance / end of month / final
        settlement), the same notion the approval route is chosen by — whose
        end date falls in the CALENDAR MONTH JUST BEFORE this run's month, on
        the same scheme, part of the business and currency, not rejected, and
        with payslips. Nothing else is "last month": a June mid-month advance
        is not the comparison for a July end-of-month run, and neither is May.
        """
        Run = self.env['hr.payslip.run']
        window = self._screen_month_before(run)
        if not window:
            return Run.browse()
        first, last = window
        # R6 (2026-11-04): only an APPROVED run is "last month" — a draft
        # or one still waiting for approval has paid nobody yet.
        domain = [('id', '!=', run.id), ('state', '=', 'done'),
                  ('date_end', '>=', first), ('date_end', '<=', last),
                  ('pb_currency_id', '=', currency.id)]
        if run.date_start:
            domain.append(('date_end', '<', run.date_start))
        if 'pb_formula_config_id' in Run._fields:
            domain.append(('pb_formula_config_id', '=',
                           run.pb_formula_config_id.id or False))
        division = run.pb_division or ''
        kind = run._pb_kind_key()
        for candidate in Run.search(domain, order='date_end desc, id desc',
                                    limit=20):
            if (candidate.pb_division or '') == division \
                    and candidate.pb_employee_count \
                    and candidate._pb_kind_key() == kind:
                return candidate
        return Run.browse()

    @api.model
    def _screen_compare_none(self, run):
        """Why there is no "Compared with" (R5), as one sentence."""
        _ = self.env._
        window = self._screen_month_before(run)
        if not window:
            return _("There is nothing to compare this run with yet.")
        return _("There is no approved run of the same kind for %s on this "
                 "scheme, so there is nothing to compare with yet.",
                 self._month_label(window[0]))

    @api.model
    def _screen_net_by_employee(self, run):
        """{employee id: take-home} on `run` — the same per-payslip money."""
        totals = self.env['hr.payslip.run']._pb_slip_totals(run.ids)
        self.env['hr.payslip'].flush_model(['payslip_run_id', 'employee_id',
                                            'state'])
        self.env.cr.execute(
            "SELECT id, employee_id FROM hr_payslip "
            "WHERE payslip_run_id = %s AND state != 'cancel'", (run.id,))
        out = {}
        for sid, eid in self.env.cr.fetchall():
            out[eid] = out.get(eid, 0.0) + (totals.get(sid) or {}).get('net', 0.0)
        return out

    @api.model
    def _screen_compare(self, prev, net):
        _ = self.env._
        before = float(prev.pb_total_net or 0.0)
        label = self._month_label(prev.date_end or prev.date_start)
        people = prev.pb_employee_count or 0
        pct = None
        if before:
            pct = round((float(net) - before) / abs(before) * 100.0, 1)
        if pct is None:
            change = _("%s paid no take-home, so there is no percentage to "
                       "compare.", label)
        elif pct > 0:
            change = _("%(pct)s%% more take-home than %(label)s.",
                       pct=self._screen_pct(pct), label=label)
        elif pct < 0:
            change = _("%(pct)s%% less take-home than %(label)s.",
                       pct=self._screen_pct(pct), label=label)
        else:
            change = _("The same take-home as %s.", label)
        then = (_("1 person was paid then.") if people == 1
                else _("%s people were paid then.", people))
        return {'run_id': prev.id, 'label': label, 'net': before,
                'people': people, 'change_pct': pct,
                'sentence': '%s %s' % (change, then)}

    @api.model
    def _screen_people(self, facts, totals, state, prev, prev_net_of,
                       prev_month):
        """The people table: one row per payslip, the team list, the counts."""
        _ = self.env._
        employees = self.env['hr.employee'].browse(
            {f['employee_id'] for f in facts.values() if f['employee_id']})
        info = self._safe(lambda: self._screen_employee_info(employees),
                          default={}) or {}
        net_of = {}
        for sid, fact in facts.items():
            if fact['state'] != 'cancel':
                eid = fact['employee_id']
                net_of[eid] = net_of.get(eid, 0.0) + \
                    (totals.get(sid) or {}).get('net', 0.0)

        rows, teams = [], {}
        counts = {'all': 0, 'flagged': 0, 'changed': 0}
        for sid, fact in facts.items():
            eid = fact['employee_id']
            person = info.get(eid) or {}
            money_row = totals.get(sid) or {}
            flag = self._screen_flag(fact, state, eid, net_of,
                                     prev, prev_net_of, prev_month)
            name = person.get('name') or fact['name'] or ''
            row = {
                'slip_id': sid, 'employee_id': eid or False,
                'name': name, 'initials': self._initials(name),
                'job': person.get('job') or '', 'team': person.get('team') or '',
                'gross': money_row.get('gross', 0.0),
                'deductions': money_row.get('deductions', 0.0),
                'net': money_row.get('net', 0.0),
                'employer_cost': money_row.get('employer_cost', 0.0),
                'flag': flag,
            }
            rows.append(row)
            counts['all'] += 1
            if flag['kind'] in ('rose', 'amber'):
                counts['flagged'] += 1
            elif flag['kind'] == 'p':
                counts['changed'] += 1
            if fact['state'] != 'cancel':
                team = row['team'] or _("No team")
                bucket = teams.setdefault(team, {'name': team, 'count': 0,
                                                 'net': 0.0})
                bucket['count'] += 1
                bucket['net'] += row['net']
        rows.sort(key=lambda r: (-(r['net'] or 0.0), r['name'].lower()))
        return {
            'rows': rows[:SCREEN_ROW_CAP],
            'teams': sorted(teams.values(),
                            key=lambda t: (-t['count'], t['name'].lower())),
            'counts': counts,
            'changed_available': bool(prev),
            'capped': len(rows) > SCREEN_ROW_CAP,
            'total': len(rows),
        }

    @api.model
    def _screen_employee_info(self, employees):
        """{employee id: {'name','job','team'}} in a fixed number of reads.

        Read as the reader first. A payroll officer who may open this run
        already sees these names on its payslip list; where the employee
        record itself is closed to them, the name, job title and team are read
        past that — nothing else about the person is.
        """
        if not employees:
            return {}
        try:
            rows = self._screen_employee_rows(employees)
        except AccessError:
            rows = self._screen_employee_rows(employees.sudo())

        def names(model, ids):
            if not ids or model not in self.env:
                return {}
            return {r['id']: r['name'] for r in self.env[model].sudo()
                    .browse(list(ids)).read(['name'], load=None)}
        dept_name = names('hr.department',
                          {r['department_id'] for r in rows if r.get('department_id')})
        job_name = names('hr.job', {r['job_id'] for r in rows
                                    if r.get('job_id') and not r.get('job_title')})
        out = {}
        for r in rows:
            out[r['id']] = {
                'name': r.get('name') or '',
                'job': r.get('job_title') or job_name.get(r.get('job_id')) or '',
                'team': dept_name.get(r.get('department_id')) or ''}
        return out

    @api.model
    def _screen_employee_rows(self, employees):
        """[{'id','name','job_title','job_id','department_id'}], ids only.

        Job and team live on the employee's current VERSION on this build
        (`hr.employee.department_id` is a related field — raw SQL on it
        fails, and reading it through the employee computes the version for
        every person). So the stored `current_version_id` is read, then the
        versions themselves — the same values the employee's related fields
        show. `load=None` keeps every many2one a bare id: the display names a
        classic read adds cost ~250 ms on a 520-person run and the job and
        team names are read once each instead.
        """
        Emp = employees.env['hr.employee']
        Version = employees.env.get('hr.version')
        if Version is None or 'current_version_id' not in Emp._fields:
            wanted = [f for f in ('name', 'job_title', 'job_id', 'department_id')
                      if f in Emp._fields]
            return employees.read(wanted, load=None)
        rows = employees.read(['name', 'current_version_id'], load=None)
        version_ids = [r['current_version_id'] for r in rows
                       if r.get('current_version_id')]
        wanted = [f for f in ('job_title', 'job_id', 'department_id')
                  if f in Version._fields]
        versions = {v['id']: v for v in
                    Version.browse(version_ids).read(wanted, load=None)}
        for r in rows:
            version = versions.get(r.get('current_version_id')) or {}
            for f in wanted:
                r[f] = version.get(f) or False
        return rows

    @api.model
    def _screen_flag(self, fact, state, eid, net_of, prev, prev_net_of,
                     prev_month):
        """One person's status chip. First match wins: cancelled · no data ·
        not calculated · new · take-home moved ≥ 10% · fine."""
        _ = self.env._
        if fact.get('state') == 'cancel':
            return {'kind': 'muted', 'text': _("Cancelled")}
        if fact.get('unsourced'):
            return {'kind': 'rose', 'text': _("No data this period")}
        if not fact.get('lines'):
            return {'kind': 'rose', 'text': _("Not calculated yet")}
        if prev and eid:
            if eid not in prev_net_of:
                return {'kind': 'p', 'text': _("New since %s", prev_month)}
            before = prev_net_of.get(eid) or 0.0
            now = net_of.get(eid) or 0.0
            if before and abs(now - before) >= abs(before) * SCREEN_CHANGE_SHARE:
                pct = (now - before) / abs(before) * 100.0
                pct_text = '%d' % round(abs(pct))
                return {'kind': 'p',
                        'text': (_("+%(pct)s%% vs %(month)s", pct=pct_text,
                                   month=prev_month) if pct > 0
                                 else _("−%(pct)s%% vs %(month)s",
                                        pct=pct_text, month=prev_month))}
        if state == 'done':
            return {'kind': 'ok', 'text': _("Approved")}
        return {'kind': 'ok', 'text': _("Calculated")}

    # --------------------------------------------------------- run screen: route
    @api.model
    def _screen_route(self, run, card, state, live_count, groups=None):
        """Who signs it off. A draft is PREVIEWED (exactly what Submit would
        resolve, minus the writes); a run already sent shows its live seats."""
        _ = self.env._
        out = {'mode': 'none', 'seats': [], 'note': '', 'error': None,
               'fast': False, 'prepared_by': None}
        preparer = run.pb_prepared_uid or run.create_uid
        if preparer:
            out['prepared_by'] = {'name': preparer.name or '',
                                  'initials': self._initials(preparer.name),
                                  'me': preparer.id == self.env.uid}
        approval = card.get('approval') or {}

        if state != 'draft':
            steps = approval.get('steps') or []
            if steps:
                out['mode'] = 'live'
                for index, st in enumerate(steps, start=1):
                    if st['status'] == 'done':
                        names, status = st['decided_by'], 'done'
                        when = (_("Signed off %s", st['decided_on'])
                                if st['decided_on'] else _("Signed off"))
                    elif st['status'] in ('active', 'blocked'):
                        names, status, when = st['with'], 'now', _("Has it now")
                    else:
                        names, status = st['with'], 'later'
                        when = _("Step %s", index)
                    name = ', '.join(names) or _("Nobody yet")
                    out['seats'].append({
                        'name': name, 'initials': self._initials(names[0])
                        if names else '', 'title': st['title'] or '',
                        'status': status, 'when': when, 'issue': ''})
            if approval.get('blocked'):
                out['error'] = approval['blocked']
            if state == 'approval_pending':
                now = [s for s in out['seats'] if s['status'] == 'now']
                out['note'] = (_("It is with %(who)s now, for “%(step)s”.",
                                 who=now[0]['name'], step=now[0]['title'])
                               if now else _("Waiting for the sign-off."))
            elif state == 'done':
                out['note'] = (_("Approved on %s.", approval['closed_on'])
                               if approval.get('closed_on')
                               else _("Approved."))
                if not steps:
                    out['note'] = _("Nobody needed to sign it off. That is "
                                    "recorded.")
            else:
                out['note'] = _("This pay run was rejected, so nobody signs "
                                "it off.")
            return out

        if not live_count:
            out['note'] = _("Who signs it off is worked out from the payslips, "
                            "once they are made.")
            return out
        out['mode'] = 'preview'
        preview = self._safe(lambda: self._screen_route_preview(run, groups),
                             default=None)
        if preview is None:
            out['error'] = _("Who signs this run off could not be worked out "
                             "just now. Reload the run to try again.")
            return out
        if preview['error']:
            out['error'] = preview['error']
            return out
        index = 0
        for step in preview['steps']:
            if step.get('kind') == 'notify' or not step.get('included', True):
                continue
            if step.get('kind') == 'fast':
                out['fast'] = True
                continue
            index += 1
            names = [p['name'] for p in step.get('people') or [] if p.get('name')]
            issue = step.get('issue') or {}
            out['seats'].append({
                'name': ', '.join(names) or _("Nobody yet"),
                'initials': self._initials(names[0]) if names else '',
                'title': step.get('title') or '',
                'status': 'later', 'when': _("Step %s", index),
                'issue': issue.get('msg') or ''})
            if issue.get('level') == 'block' and not out['error']:
                out['error'] = issue.get('msg') or ''
        names = [s['name'] for s in out['seats']]
        if out['fast'] and not names:
            first = _("Nobody checks this pay run before it is approved: it "
                      "is approved the moment it is sent, and that is "
                      "recorded.")
        elif not names:
            first = _("No step of the route applies to this run, so it would "
                      "be approved the moment it is sent.")
        elif len(names) == 1:
            first = _("When you send it, it goes to %s.", names[0])
        elif len(names) == 2:
            first = _("When you send it, it goes to %(first)s first, then to "
                      "%(second)s.", first=names[0], second=names[1])
        else:
            first = _("When you send it, it goes to %(n)s people in turn: "
                      "%(names)s.", n=len(names), names=', '.join(names))
        scope = preview.get('scope') or ''
        out['note'] = (_("%(first)s This route is set for %(scope)s.",
                         first=first, scope=scope) if scope else first)
        return out

    @api.model
    def _screen_route_pending(self, run):
        """The route of a draft with payslips, not worked out yet (P2 item
        16): the screen fills it from a second `parts='route'` call."""
        preparer = run.pb_prepared_uid or run.create_uid
        return {'mode': 'pending', 'seats': [], 'note': '', 'error': None,
                'fast': False,
                'prepared_by': ({'name': preparer.name or '',
                                 'initials': self._initials(preparer.name),
                                 'me': preparer.id == self.env.uid}
                                if preparer else None)}

    @api.model
    def _screen_route_preview(self, run, groups=None):
        """What `biz.approval.engine.submit` would resolve for this draft,
        minus every write (engine.py `submit`, `preview`). The engine's
        preview asks for approval set-up rights, so it runs as superuser —
        AFTER `get_run_screen` has checked the reader may read the run.

        `groups` is the run's `_pb_review_groups()`, already read by the
        caller. Exactly one group on a draft with payslips is everything
        `_approval_validate` checks, so it is only asked — for its exact
        words — when that is not the case."""
        if groups is None or len(groups) != 1:
            try:
                run._approval_validate()
            except UserError as e:
                return {'error': e.args[0] if e.args else '', 'steps': [],
                        'scope': ''}
        ctx = run._approval_context()
        process = run._approval_process()
        company = self.env['res.company'].browse(int(ctx['company_id']))
        engine = self.env['biz.approval.engine'].sudo()
        _binding, version, _trace, error = engine._resolve_binding(
            company, process, ctx.get('scope_keys'), ctx.get('kind_key'))
        if error:
            return {'error': error.get('message') or '', 'steps': [],
                    'scope': ctx.get('scope_label') or ''}
        result = engine.preview(version, ctx)
        return {'error': None, 'steps': result.get('steps') or [],
                'scope': ctx.get('scope_label') or ''}

    # -------------------------------------------------------- run screen: checks
    @api.model
    def _screen_checks(self, run, card, state, live_count, uncalculated,
                       facts, route, may_write):
        """The verdict and the mock-up's four rows, in order: this period's
        data · the figures add up · calculated · who signs it off. The rose
        rows reuse the board's own words (`_run_checks`)."""
        _ = self.env._
        if state == 'cancel' and not live_count:
            return {'verdict': 'bad', 'title': _("This pay run was rejected"),
                    'sub': card.get('reject_note') or '', 'items': []}
        if not live_count:
            return {'verdict': 'wait', 'title': _("Nothing to check yet"),
                    'sub': _("Make the payslips first. The checks run as soon "
                             "as they exist."),
                    'items': []}
        items = []
        unsourced = card.get('unsourced') or 0
        if unsourced:
            items.append({
                'key': 'data', 'ok': False,
                'title': (_("1 payslip has no source data") if unsourced == 1
                          else _("%s payslips have no source data", unsourced)),
                'detail': _("Their figures are scheme defaults, not real pay."),
                'door': {'kind': 'flagged',
                         'label': (_("Show the person") if unsourced == 1
                                   else _("Show the %s people", unsourced))}})
        else:
            items.append({
                'key': 'data', 'ok': True,
                'title': _("Every payslip has this period's data"),
                'detail': _("No payslip was calculated from scheme defaults "
                            "alone."),
                'door': None})

        if card.get('balance_ok') is False:
            gap = self._money_words(card.get('balance_gap'),
                                    run.pb_currency_id.symbol
                                    or card.get('currency'))
            atlas = self._screen_atlas_ok()
            items.append({
                'key': 'balance', 'ok': False,
                'title': _("Figures do not add up (gap %s)", gap),
                'detail': _("%s is unaccounted for between gross, deductions "
                            "and net.", gap),
                'door': ({'kind': 'atlas',
                          'label': _("Where the numbers come from")}
                         if atlas else None)})
        else:
            items.append({
                'key': 'balance', 'ok': True,
                'title': _("The figures add up"),
                'detail': _("Gross pay less deductions equals take-home."),
                'door': None})

        if uncalculated:
            items.append({
                'key': 'calculated', 'ok': False,
                'title': (_("1 payslip is not calculated yet") if uncalculated == 1
                          else _("%s payslips are not calculated yet",
                                 uncalculated)),
                'detail': (_("Recalculate everyone to work them out.")
                           if state == 'draft' and may_write
                           else _("They have no pay lines yet.")),
                'door': {'kind': 'flagged',
                         'label': (_("Show the person") if uncalculated == 1
                                   else _("Show the %s people", uncalculated))}})
        else:
            stamps = [f['calculated_at'] for f in facts.values()
                      if f.get('calculated_at')]
            when = self._safe(lambda: format_datetime(
                self.env, max(stamps), dt_format='d MMM y, HH:mm'),
                default='') if stamps else ''
            items.append({
                'key': 'calculated', 'ok': True,
                'title': (_("The payslip is calculated") if live_count == 1
                          else _("All %s payslips are calculated", live_count)),
                'detail': _("Last calculated on %s.", when) if when else '',
                'door': None})

        if route.get('mode') == 'pending':
            # P2 item 16: the screen asks for the route a moment later and
            # replaces this row. Never counted as a problem.
            items.append({
                'key': 'route', 'ok': True, 'tone': 'pending',
                'title': _("Working out who signs it off"),
                'detail': _("This takes a moment on a big run."),
                'door': None})
        elif route.get('error'):
            setup = self._screen_setup_door()
            items.append({
                'key': 'route', 'ok': False,
                'title': _("Who signs it off is not settled"),
                'detail': route['error'],
                'door': ({'kind': 'approvals_setup',
                          'label': _("Set who signs it off")}
                         if setup else None)})
        else:
            titles = [s['title'] for s in route.get('seats') or [] if s['title']]
            title = _("Approval route is set")
            tone = 'ok'
            if route.get('fast') and not titles:
                # R4 (2026-11-04): a scheme with no sign-off is AMBER — it is
                # allowed, but whoever presses Send should know nobody looks.
                # Amber never makes the run unready and never adds to the
                # primary's warn badge (that counts rose rows only).
                title = _("No sign-off is set for this scheme")
                detail = _("Sending it approves it straight away.")
                tone = 'amber'
            elif not titles and route.get('mode') != 'preview':
                title = _("No sign-off was needed")
                detail = _("Nobody needed to sign it off.")
            elif not titles:
                title = _("No step of the route applies to this run")
                detail = _("Sending it approves it straight away.")
                tone = 'amber'
            elif len(titles) == 1:
                detail = _("1 sign-off: %s.", titles[0])
            else:
                detail = _("%(n)s sign-offs: %(steps)s.", n=len(titles),
                           steps=' → '.join(titles))
            items.append({'key': 'route', 'ok': True, 'tone': tone,
                          'title': title, 'detail': detail, 'door': None})

        # The board's own amber ADVICE (never a block) for an open run —
        # today FILLIN's "answers Payobook filled in that nobody has checked"
        # (12e57634d). Same words as the board card; never counted as a
        # problem (R4's amber rule).
        if state in ('draft', 'approval_pending'):
            for advice in card.get('checks') or []:
                if advice.get('advisory') and advice.get('tone') == 'amber':
                    # The board's own door, when it has one (`next`: key +
                    # label, e.g. 'close' → Workforce › Close); none, no
                    # button — 'fillin' has none today.
                    nxt = advice.get('next') or None
                    door = (dict(nxt, kind='board')
                            if nxt and nxt.get('label') else None)
                    items.append({
                        'key': advice.get('key') or 'advice', 'ok': True,
                        'tone': 'amber', 'title': advice.get('text') or '',
                        'detail': advice.get('detail') or '', 'door': door})

        for item in items:
            item.setdefault('tone', 'ok' if item['ok'] else 'bad')
        amber = any(item['tone'] == 'amber' for item in items
                    if item['key'] == 'route')
        bad = sum(1 for item in items if not item['ok'])
        if state == 'cancel':
            return {'verdict': 'bad', 'title': _("This pay run was rejected"),
                    'sub': card.get('reject_note') or '', 'items': items}
        if state == 'done':
            return {'verdict': 'done', 'title': _("Checked and approved"),
                    'sub': _("The figures are locked."), 'items': items}
        if state == 'approval_pending':
            changed = self._safe(
                lambda: bool(run.pb_source_revision)
                and run._pb_source_revision() != run.pb_source_revision,
                default=None)
            if changed:
                sub = _("The figures have changed since it was sent, so it "
                        "cannot be approved as it is.")
            elif changed is None:
                sub = _("Waiting for the sign-off.")
            else:
                sub = _("Nothing has changed since it was sent.")
            return {'verdict': 'wait', 'title': _("Checked and sent in"),
                    'sub': sub, 'items': items}
        if bad:
            return {
                'verdict': 'bad',
                'title': (_("1 thing to fix before sending") if bad == 1
                          else _("%s things to fix before sending", bad)),
                'sub': (_("It cannot be sent until who signs it off is "
                          "settled.") if route.get('error')
                        else _("You can still send it. The approver will see "
                               "these too.")),
                'items': items}
        # Follow-up 1: amber rows are NOTES — they never make the run unready
        # (R4), but the verdict names them so nobody reads "Everything checks
        # out" as "there is nothing below".
        notes = sum(1 for item in items if item['tone'] == 'amber')
        if run.pb_return_note:
            sub = _("Fix what was sent back, then send it again.")
        elif amber and notes > 1:
            sub = _("Ready to send, with %s notes below. Nobody signs it off, "
                    "so it is approved the moment it is sent.", notes)
        elif amber:
            sub = _("Ready to send. Nobody signs it off, so it is approved "
                    "the moment it is sent.")
        elif notes == 1:
            sub = _("Ready to send for approval, with 1 note below.")
        elif notes:
            sub = _("Ready to send for approval, with %s notes below.", notes)
        else:
            sub = _("Ready to send for approval.")
        return {'verdict': 'ok', 'title': _("Everything checks out"),
                'sub': sub, 'items': items, 'notes': notes}

    @api.model
    def _screen_atlas_ok(self):
        """May this reader open Where the numbers come from?"""
        if not callable(getattr(self.env['hr.payslip.run'],
                                'action_open_source_atlas', None)):
            return False
        Atlas = self.env.get('pb.source.atlas')
        if Atlas is None:
            return False
        return bool(self._safe(lambda: Atlas._atlas_gate(), default=False))

    @api.model
    def _screen_setup_door(self):
        """May this reader open the approval set-up (the Matrix)?"""
        if not self.env.ref(_MATRIX_ACTION, raise_if_not_found=False):
            return False
        return bool(self._safe(
            lambda: self.env['biz.approval.engine']._require_config() or True,
            default=False))

    # ------------------------------------------------- run screen: journey, next
    @api.model
    def _screen_journey(self, run, card, state, live_count, bad, n_checks,
                        sent_back, notes=0):
        """Prepare · Check · Approve · Pay · Send payslips — the mock-up's
        `journey()`, from the run's real state."""
        _ = self.env._

        def step(key, st, label, sub):
            return {'key': key, 'state': st, 'label': label, 'sub': sub}
        labels = {'prepare': _("Prepare"), 'check': _("Check"),
                  'approve': _("Approve"), 'pay': _("Pay"),
                  'deliver': _("Send payslips")}
        if not live_count and state in ('draft', 'approval_pending'):
            return [step('prepare', 'now', labels['prepare'], _("No payslips yet")),
                    step('check', 'later', labels['check'], _("Waits for payslips")),
                    step('approve', 'later', labels['approve'], '—'),
                    step('pay', 'later', labels['pay'], '—'),
                    step('deliver', 'later', labels['deliver'], '—')]
        if state == 'cancel':
            made = _("Payslips cancelled")
        else:
            made = (_("1 payslip made") if live_count == 1
                    else _("%s payslips made", live_count))
        prepare = step('prepare', 'done', labels['prepare'], made)
        all_pass = _("All %s checks pass", n_checks)
        approval = card.get('approval') or {}
        if state == 'draft':
            if bad:
                check = step('check', 'warn', labels['check'],
                             _("1 thing to fix") if bad == 1
                             else _("%s things to fix", bad))
            elif sent_back:
                check = step('check', 'warn', labels['check'],
                             _("Sent back — fix and send again"))
            elif notes:
                # Follow-up 1: never "All 4 checks pass" above amber notes.
                check = step('check', 'done', labels['check'],
                             _("Checks pass · 1 note") if notes == 1
                             else _("Checks pass · %s notes", notes))
            else:
                check = step('check', 'done', labels['check'], all_pass)
            return [prepare, check,
                    step('approve', 'later' if (bad or sent_back) else 'now',
                         labels['approve'], _("Not sent yet")),
                    step('pay', 'later', labels['pay'], _("After approval")),
                    step('deliver', 'later', labels['deliver'],
                         _("After payment"))]
        if state == 'approval_pending':
            if approval.get('blocked'):
                approve = step('approve', 'warn', labels['approve'],
                               _("Stuck: %s", approval['blocked']))
            elif approval.get('with'):
                approve = step('approve', 'now', labels['approve'],
                               _("With %(who)s · step %(i)s of %(n)s",
                                 who=approval['with'],
                                 i=approval.get('step_index') or 1,
                                 n=approval.get('step_total') or 1))
            else:
                approve = step('approve', 'now', labels['approve'],
                               _("Waiting for the sign-off"))
            return [prepare,
                    step('check', 'done', labels['check'], _("Checked and sent in")),
                    approve,
                    step('pay', 'later', labels['pay'], _("After approval")),
                    step('deliver', 'later', labels['deliver'],
                         _("After payment"))]
        if state == 'done':
            delivery = card.get('delivery') or {}
            closed = approval.get('closed_on')
            approve = step('approve', 'done', labels['approve'],
                           _("Approved %s", closed) if closed else _("Approved"))
            if delivery.get('paid'):
                pay = step('pay', 'done', labels['pay'],
                           _("Paid %s", delivery['paid_on'])
                           if delivery.get('paid_on') else _("Paid"))
            elif delivery.get('bank_file'):
                pay = step('pay', 'now', labels['pay'],
                           _("Bank file made, not paid yet"))
            else:
                pay = step('pay', 'now', labels['pay'],
                           _("Bank file not made yet"))
            if delivery.get('delivered'):
                deliver = step('deliver', 'done', labels['deliver'],
                               _("Sent to %s people",
                                 delivery.get('slips_sent') or 0))
            elif delivery.get('paid'):
                deliver = step('deliver', 'now', labels['deliver'],
                               _("Not sent yet"))
            else:
                deliver = step('deliver', 'later', labels['deliver'],
                               _("After payment"))
            return [prepare,
                    step('check', 'done', labels['check'], all_pass),
                    approve, pay, deliver]
        # rejected
        return [prepare,
                step('check', 'done', labels['check'], _("Checked")),
                step('approve', 'warn', labels['approve'], _("Rejected")),
                step('pay', 'later', labels['pay'], _("Will not be paid")),
                step('deliver', 'later', labels['deliver'],
                     _("Will not be sent"))]

    @api.model
    def _screen_primary(self, run, card, state, live_count, bad, sent_back,
                        may_write, route):
        """The ONE next step. Agrees with the board's `next_action` for the
        same run, plus the two cases the board does not need: no payslips
        (make them) and approved but not yet paid and delivered."""
        _ = self.env._
        none = {'kind': 'none', 'label': '', 'method': None, 'action': None,
                'context': None, 'warn': 0, 'confirm': None}
        if state == 'draft' and not live_count:
            if may_write and self.env.ref(_MAKE_ACTION,
                                          raise_if_not_found=False):
                return dict(none, kind='make', label=_("Make payslips"),
                            action=_MAKE_ACTION,
                            context={'active_model': 'hr.payslip.run',
                                     'active_id': run.id,
                                     'active_ids': [run.id]})
            return none
        if state == 'draft':
            if card.get('next_action') != 'submit' or not card.get('can_act'):
                return none
            label = _("Send again") if sent_back else _("Send for approval")
            names = [s['name'] for s in route.get('seats') or []]
            if bad:
                confirm = {
                    'title': (_("Send it with 1 problem?") if bad == 1
                              else _("Send it with %s problems?", bad)),
                    'body': (_("The checks found things to fix, and %s will see "
                               "them too. Most people fix them first.",
                               names[0]) if names
                             else _("The checks found things to fix, and the "
                                    "approver will see them too. Most people "
                                    "fix them first.")),
                    'ok': _("Send anyway"), 'cancel': _("Fix first"),
                    'danger': True}
            else:
                keep = _("You can still see it, but not change it, while it is "
                         "being approved.")
                if len(names) == 1:
                    where = _("It goes to %s.", names[0])
                elif len(names) == 2:
                    where = _("It goes to %(first)s first, then to %(second)s.",
                              first=names[0], second=names[1])
                elif names:
                    where = _("It goes to %(n)s people in turn, starting with "
                              "%(first)s.", n=len(names), first=names[0])
                elif route.get('mode') == 'preview' and not route.get('error'):
                    # R4: fast lane, or no step applies — the same words as
                    # the amber route row, and nothing about "while it is
                    # being approved": it is approved on the spot.
                    where = (_("No sign-off is set for this scheme. Sending it "
                               "approves it straight away.")
                             if route.get('fast')
                             else _("No step of the route applies to this run. "
                                    "Sending it approves it straight away."))
                    keep = ''
                else:
                    where = ''
                confirm = {'title': _("Send for approval?"),
                           'body': ('%s %s' % (where, keep)).strip(),
                           'ok': label, 'cancel': _("Not yet"),
                           'danger': False}
            return dict(none, kind='resubmit' if sent_back else 'submit',
                        label=label, method='action_approval_submit',
                        warn=bad, confirm=confirm)
        inbox = _INBOX_ACTION if self.env.ref(
            _INBOX_ACTION, raise_if_not_found=False) else None
        if state == 'approval_pending':
            if card.get('next_action') == 'decide' and card.get('can_act'):
                return dict(none, kind='decide', label=_("Open the approval"),
                            action=inbox)
            return dict(none, kind='approvals', label=_("Open in Approvals"),
                        action=inbox)
        if state == 'done':
            delivery = card.get('delivery') or {}
            if not (delivery.get('paid') and delivery.get('delivered')) \
                    and callable(getattr(self.env['hr.payslip.run'],
                                         'action_pb_pay_deliver', None)):
                return dict(none, kind='paydeliver', label=_("Pay & deliver"),
                            method='action_pb_pay_deliver')
        return none

    @api.model
    def _screen_delivery_steps(self, run, card, state, live_count, net, money):
        """Approved → bank file → paid → payslips sent → journals, each with
        its state; `now` is the first one not done on an approved run."""
        _ = self.env._
        d = card.get('delivery') or {}
        approval = card.get('approval') or {}
        done = state == 'done'
        last = (approval.get('steps') or [{}])[-1] if approval.get('steps') else {}
        who = ', '.join(last.get('decided_by') or [])
        closed = approval.get('closed_on') or ''
        if closed and who:
            approved_sub = _("On %(when)s, by %(who)s", when=closed, who=who)
        elif closed:
            approved_sub = _("On %s", closed)
        else:
            approved_sub = ''
        people = card.get('employees') or 0
        rows = [
            ('approved', done, _("Approved"), approved_sub),
            ('bank_file', bool(d.get('bank_file')), _("Make the bank file"),
             _("Made") if d.get('bank_file')
             else (_("1 transfer · %s", money(net, True)) if people == 1
                   else _("%(n)s transfers · %(net)s", n=people,
                          net=money(net, True)))),
            ('paid', bool(d.get('paid')), _("Mark as paid"),
             _("Paid on %s", d['paid_on']) if d.get('paid') and d.get('paid_on')
             else _("After the bank confirms")),
            ('sent', bool(d.get('delivered')), _("Send payslips"),
             _("Sent to %s people", d.get('slips_sent') or 0)
             if d.get('delivered')
             else (_("1 person by email") if people == 1
                   else _("%s people by email", people))),
            ('journals', bool(d.get('journals')), _("Post to the books"),
             _("Posted on %s", d['journals_on'])
             if d.get('journals') and d.get('journals_on')
             else _("The salary journal")),
        ]
        steps, now_given = [], False
        for key, is_done, label, sub in rows:
            if done and is_done:
                st = 'done'
            elif done and not now_given:
                st, now_given = 'now', True
            else:
                st = 'later'
            steps.append({'key': key, 'state': st, 'label': label, 'sub': sub})
        return {'steps': steps,
                'left': sum(1 for s in steps if s['state'] != 'done')}

    @api.model
    def _screen_actions(self, run, card, state, may_write, live_count,
                        calculated_count, prev_month, split_ok):
        """Downloads and More: only what applies to this state and what this
        reader may do; a method another module adds is offered only where
        that module is installed."""
        _ = self.env._
        Run = self.env['hr.payslip.run']

        def has(method):
            return callable(getattr(Run, method, None))

        def item(key, label, hint, method=None, action=None, danger=False,
                 confirm=None, context=None):
            return {'key': key, 'label': label, 'hint': hint, 'method': method,
                    'action': action, 'danger': danger, 'confirm': confirm,
                    'context': context}

        def ask(title, body, ok, cancel, danger=False):
            return {'title': title, 'body': body, 'ok': ok, 'cancel': cancel,
                    'danger': danger}

        downloads, more = [], []
        open_run = state != 'cancel'
        if live_count and open_run:
            if has('action_download_payslip_xlsx'):
                downloads.append(item(
                    'xlsx', _("Excel workbook"),
                    _("Every payslip, one row per person"),
                    method='action_download_payslip_xlsx'))
            if has('action_open_payroll_report'):
                downloads.append(item(
                    'report', _("Payroll report"),
                    _("Totals by team and pay item"),
                    method='action_open_payroll_report'))
        if calculated_count and open_run and has('action_pb_print_payslips'):
            downloads.append(item(
                'pdf', _("Payslips as PDF"),
                _("The approved payslips") if state == 'done'
                else _("For checking before approval"),
                method='action_pb_print_payslips'))

        if live_count and self._screen_atlas_ok():
            more.append(item(
                'atlas', _("Where the numbers come from"),
                _("Trace any figure back to its file or record"),
                method='action_open_source_atlas'))
        if live_count and has('action_input_changes'):
            more.append(item(
                'changes',
                _("What changed since %s", prev_month) if prev_month
                else _("What changed"),
                _("Pay data that is new or different this time"),
                method='action_input_changes'))
        if state == 'draft' and may_write and live_count:
            # PRS P2: the old header's Generate Payslips lives on as the
            # primary while a run is empty, and here once it has payslips —
            # a joiner added late still needs a way onto the run.
            if self.env.ref(_MAKE_ACTION, raise_if_not_found=False):
                more.append(item(
                    'remake', _("Add or remake payslips"),
                    _("Pick people and make their payslips for these dates"),
                    action=_MAKE_ACTION,
                    context={'active_model': 'hr.payslip.run',
                             'active_id': run.id, 'active_ids': [run.id]}))
            if has('action_recompute_formula_lines_batch'):
                # R7 (2026-11-04): it changes figures, so it asks first —
                # not a danger style.
                more.append(item(
                    'recalc', _("Recalculate everyone"),
                    _("After you fix a pay item or the pay data"),
                    method='action_recompute_formula_lines_batch',
                    confirm=ask(
                        _("Recalculate the payslip?") if live_count == 1
                        else _("Recalculate %s payslips?", live_count),
                        _("Its figures may change.") if live_count == 1
                        else _("Their figures may change."),
                        _("Recalculate"), _("Not now"))))
            if split_ok:
                more.append(item(
                    'split', _("Split into review groups"),
                    _("One run per scheme and part of the business"),
                    method='action_split_review_groups',
                    confirm=ask(
                        _("Split into review groups?"),
                        _("Makes one pay run per pay scheme and part of the "
                          "business, and moves each payslip into the right "
                          "one. This run is removed once it is empty."),
                        _("Split it"), _("Not now"))))
            more.append(item(
                'cleardraft', _("Delete draft payslips"),
                _("Keeps the run, so you can make them again"),
                method='action_pb_delete_draft_payslips', danger=True,
                confirm=ask(
                    _("Delete the draft payslip?") if live_count == 1
                    else _("Delete all %s draft payslips?", live_count),
                    _("The run stays, so you can make them again. Nothing "
                      "approved is touched."),
                    _("Delete payslips"), _("Keep them"), danger=True)))
        if state in ('draft', 'approval_pending') and card.get('can_reject'):
            more.append(item(
                'reject', _("Reject this run"),
                _("Asks why first. A rejected run cannot come back."),
                method='action_pb_ask_reject', danger=True,
                confirm=ask(
                    _("Reject this run?"),
                    _("You will be asked why. A rejected run cannot be sent "
                      "again; you would start a new one."),
                    _("Reject"), _("Keep it"), danger=True)))
        if state == 'done' and may_write:
            delivery = card.get('delivery') or {}
            if not (delivery.get('paid') or delivery.get('bank_file')
                    or delivery.get('delivered')):
                more.append(item(
                    'redraft', _("Set back to draft"),
                    _("Only before anyone is paid"),
                    method='draft_payslip_run', danger=True,
                    confirm=ask(
                        _("Set this run back to draft?"),
                        _("Its payslips can be changed again, and it must be "
                          "approved again before anyone is paid."),
                        _("Set back to draft"), _("Keep it approved"),
                        danger=True)))
            if has('action_send_email_all') and live_count:
                more.append(item(
                    'email', _("Email payslips"),
                    _("Each person gets their own payslip"),
                    method='action_send_email_all',
                    confirm=ask(
                        _("Email every payslip?"),
                        _("1 person gets their payslip by email.")
                        if live_count == 1
                        else _("Each of the %s people gets their own payslip "
                               "by email.", live_count),
                        _("Send them"), _("Not now"))))
        return {'downloads': downloads, 'more': more}

    # ---------------- helpers ----------------
    @api.model
    def _approval_chip(self, run):
        """Which route this run is on and who it is waiting for, in words.

        Read as superuser. The reader can already see the run; the request's
        own record rules ("mine" for approval users) would refuse anyone who
        is not a seat on it, and that refusal used to escape this card and
        blank the whole board ("You don't have access to this yet"). The chip
        is a summary — route, step, names — so showing it to whoever sees the
        run leaks nothing the run itself does not.
        """
        return self._safe(lambda: self._approval_chip_data(run), default={})

    @api.model
    def _approval_chip_data(self, run):
        request = run.sudo().approval_request_id
        if not request:
            return {}
        step = None
        if request.current_step_key:
            step = request.step_ids.filtered(
                lambda s: s.key == request.current_step_key)[:1]
        # Every step the route includes, in order, with who holds it and
        # whether it has been decided — the quick look draws the whole
        # route, the card draws "Sign-off 2 of 3".
        included = request.step_ids.filtered('included').sorted(
            key=lambda s: (s.sequence, s.id))
        steps = []
        for st in included:
            open_seats = st.seat_ids.filtered(lambda s: s.status == 'open')
            done_seats = st.seat_ids.filtered(lambda s: s.status == 'approved')
            steps.append({
                'key': st.key,
                'title': st.title or '',
                'status': st.status,
                'with': sorted(set(open_seats.mapped('acting_user_id.name'))),
                'decided_by': sorted(set(done_seats.mapped('acting_user_id.name'))),
                'decided_on': self._fmt_date(st.decided_at),
            })
        index = 0
        if step:
            keys = [s['key'] for s in steps]
            index = keys.index(step.key) + 1 if step.key in keys else 0
        return {
            'request_id': request.id,
            'state': request.state,
            'workflow': request.version_id.workflow_id.name or '',
            'step': (step.title if step else ''),
            'with': ', '.join(sorted(set(
                step.seat_ids.filtered(lambda s: s.status == 'open')
                .mapped('acting_user_id.name')))) if step else '',
            'blocked': request.block_reason or '',
            'step_index': index,
            'step_total': len(steps),
            'steps': steps,
            'submitted_on': self._fmt_date(request.submitted_at),
            'closed_on': self._fmt_date(request.closed_at),
        }

    @api.model
    def _paid_by_run(self, run_ids):
        """{run id: (paid, paid_on)} for `run_ids`, in one query; None on a
        database without the payment stamp (pb_pay_delivery absent)."""
        Slip = self.env['hr.payslip']
        if 'pb_paid_on' not in Slip._fields:
            return None
        if not run_ids:
            return {}
        # raw SQL reads the table, not the cache (ledger: ABM June pay run)
        Slip.flush_model(['payslip_run_id', 'state', 'pb_paid_on'])
        self.env.cr.execute(
            "SELECT payslip_run_id, COUNT(*) FILTER (WHERE state = 'done'), "
            "COUNT(*) FILTER (WHERE state = 'done' AND pb_paid_on IS NOT NULL), "
            "MAX(pb_paid_on) FILTER (WHERE state = 'done') "
            "FROM hr_payslip WHERE payslip_run_id IN %s GROUP BY 1",
            (tuple(run_ids),))
        out = {}
        for run_id, done, stamped, last in self.env.cr.fetchall():
            out[run_id] = (bool(done) and done == stamped, last or False)
        return out

    @api.model
    def _empty_delivery(self):
        return {'bank_file': False, 'paid': False, 'paid_on': '',
                'delivered': False, 'slips_sent': 0, 'delivered_on': '',
                'journals': False, 'journals_on': ''}

    @api.model
    def _delivery_by_run(self, runs):
        """{run id: delivery dict} — bank file, payment, payslips, journals.

        Each is a model of ``pb_pay_delivery``, which this module does not
        depend on, so every read is guarded by ``self.env.get`` and the
        answer on a database without it is "nothing delivered" — true, since
        nothing could have been.
        """
        out = {}
        if not runs:
            return out
        ids = runs.ids
        done_runs = runs.filtered(lambda r: r.state == 'done')
        # FILTER wave 5: the board is rebuilt on every filter change now, so
        # "paid" is read for every done run in ONE grouped query — the run's
        # own `pb_paid` compute loads every payslip of every run (3 s for 30
        # runs on the demo copy). Same rule as `hr.payslip.run._compute_pb_paid`
        # (pb_pay_delivery): paid when the run has done payslips and every one
        # carries the payment stamp; paid on = the latest stamp.
        paid_of = self._safe(lambda: self._paid_by_run(done_runs.ids), default=None)
        for run in done_runs:
            out[run.id] = self._empty_delivery()
            if paid_of is not None:
                paid, paid_on = paid_of.get(run.id, (False, False))
            else:
                # pb_paid / pb_paid_on live on the run only with pb_pay_delivery.
                paid_on = self._safe(lambda r=run: getattr(r, 'pb_paid_on', False),
                                     default=False)
                paid = self._safe(lambda r=run: bool(getattr(r, 'pb_paid', False)),
                                  default=False)
            if paid:
                out[run.id]['paid'] = True
                out[run.id]['paid_on'] = self._fmt_date(paid_on)

        BankFile = self.env.get('pb.bank.file')
        if BankFile is not None:
            rows = self._safe(lambda: BankFile.sudo().search_read(
                [('run_id', 'in', ids), ('state', '=', 'approved')],
                ['run_id']), default=[])
            for row in rows:
                rid = row['run_id'][0]
                if rid in out:
                    out[rid]['bank_file'] = True

        Batch = self.env.get('pb.payslip.delivery.batch')
        if Batch is not None:
            rows = self._safe(lambda: Batch.sudo().search_read(
                [('run_id', 'in', ids), ('state', '=', 'done')],
                ['run_id', 'sent_count', 'write_date'], order='id asc'),
                default=[])
            for row in rows:
                rid = row['run_id'][0]
                if rid in out:
                    out[rid]['delivered'] = True
                    out[rid]['slips_sent'] += row.get('sent_count') or 0
                    out[rid]['delivered_on'] = self._fmt_date(row.get('write_date'))

        Journal = self.env.get('pb.payroll.journal')
        if Journal is not None:
            rows = self._safe(lambda: Journal.sudo().search_read(
                [('run_id', 'in', ids), ('state', '=', 'posted')],
                ['run_id', 'posted_on']), default=[])
            for row in rows:
                rid = row['run_id'][0]
                if rid in out:
                    out[rid]['journals'] = True
                    out[rid]['journals_on'] = self._fmt_date(row.get('posted_on'))
        return out

    @api.model
    def _history(self, run, approval, delivery):
        """What happened to this run, oldest first: [[sentence, date], …].

        Plain sentences built server-side so a translator sees whole lines.
        """
        ev = []
        try:
            prepared = run.pb_prepared_uid.name or run.create_uid.name or ''
            ev.append([self.env._("Prepared by %s", prepared) if prepared
                       else self.env._("Prepared"),
                       self._fmt_date(run.create_date)])
            if approval:
                if approval.get('submitted_on'):
                    ev.append([self.env._("Submitted for approval"),
                               approval['submitted_on']])
                for st in approval.get('steps') or []:
                    if st['status'] == 'done' and st['decided_by']:
                        ev.append([self.env._(
                            "%(step)s · signed off by %(who)s",
                            step=st['title'], who=', '.join(st['decided_by'])),
                            st['decided_on']])
                    elif st['status'] == 'active':
                        who = ', '.join(st['with']) or self.env._("nobody yet")
                        ev.append([self.env._(
                            "%(step)s · waiting for %(who)s",
                            step=st['title'], who=who), ''])
            if run.pb_return_note:
                ev.append([self.env._("Sent back by %s to be fixed",
                                      run.pb_return_uid.name or ''),
                           self._fmt_date(run.pb_return_date)])
            if run.state == 'done':
                ev.append([self.env._("Approved"),
                           (approval or {}).get('closed_on', '')])
                if delivery.get('bank_file'):
                    ev.append([self.env._("Bank file made"), ''])
                if delivery.get('paid'):
                    ev.append([self.env._("Paid"), delivery.get('paid_on', '')])
                if delivery.get('delivered'):
                    ev.append([self.env._("Payslips sent to %s people",
                                          delivery.get('slips_sent') or 0),
                               delivery.get('delivered_on', '')])
                if delivery.get('journals'):
                    ev.append([self.env._("Journals posted"),
                               delivery.get('journals_on', '')])
            if run.state == 'cancel' and run.pb_reject_note:
                ev.append([self.env._("Rejected by %s", run.pb_reject_uid.name or ''),
                           ''])
        except Exception as e:  # a card's story must never blank the board
            _logger.debug("Pay Runs board history failed: %s", e)
        return ev

    @api.model
    def _divisions(self):
        """([{key, label}], {key: label}) from the schemes that carry a division."""
        seen = {}
        try:
            for c in self.env['hr.formula.config'].sudo().search([]):
                d = getattr(c, 'pb_division', '')
                if d and d not in seen:
                    nm = (c.name or '').replace('Payobook', '').split('—')[0].strip()
                    seen[d] = nm or d.replace('_', ' ').title()
        except Exception:
            seen = {}
        chips = [{'key': k, 'label': v}
                 for k, v in sorted(seen.items(), key=lambda x: x[1])]
        return chips, seen

    @api.model
    def _period_block(self, batches, company=None):
        """The calendar month the hero speaks about, keyed like the hub chip.

        Stage = the LEAST advanced of the month's live runs (zero runs is
        stage 1), exactly as `pb.pay.hub._stage` does it — restated here
        because this module must not depend on the hub that mounts it.

        NAV P3b: plus the month's two dates from the Payroll calendar —
        when changes close and when people are paid (`_calendar_dates`).
        """
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        last = first + relativedelta(months=1, days=-1)
        key = first.strftime('%Y-%m')
        stages = []
        for b in batches:
            if b['state'] == 'cancel':
                continue
            try:
                ds = date.fromisoformat(b['date_start']) if b['date_start'] else None
                de = date.fromisoformat(b['date_end']) if b['date_end'] else None
            except ValueError:
                continue
            if not (ds and de) or ds > last or de < first:
                continue
            s = _RUN_STAGE.get(b['state'], 2)
            if s == 4 and b['delivery'].get('delivered'):
                s = 5
            stages.append(s)
        block = {
            'key': key,
            'label': self._month_label(first),
            'short': format_date(self.env, first, date_format='MMM y'),
            'range': self._fmt_period(first, last),
            'date_start': first.isoformat(),
            'date_end': last.isoformat(),
            'stage': min(stages) if stages else 1,
            'total': MONTH_STAGES,
            'next_label': self._month_label(first + relativedelta(months=1)),
        }
        block.update(self._calendar_dates(first, today,
                                          company or self.env.company))
        return block

    @api.model
    def _calendar_dates(self, first, today, company):
        """The month's two dates from `pb.payroll.calendar`, as the hero says
        them: ``cutoff`` / ``pay_date`` (ISO or None), ``cutoff_in_days`` /
        ``pay_in_days`` (int or None) and ``cutoff_label`` / ``pay_label``
        (the reader's short date, e.g. "Fri 24 Oct").

        `pb.payroll.calendar` is pb_comp_ben's, which this module does NOT
        depend on — read through ``self.env.get`` and absent without it. The
        company's own row wins over a shared one (company empty), exactly as
        Home reads it (pb_dashboard home_data.py). Read as the system: these
        are two dates the whole payroll team works to, not a record the
        reader has to be in Compensation & Benefits to see.
        """
        out = {'cutoff': None, 'pay_date': None, 'cutoff_in_days': None,
               'pay_in_days': None, 'cutoff_label': '', 'pay_label': ''}
        Cal = self.env.get('pb.payroll.calendar')
        if Cal is None:
            return out
        cid = company.id if company else False
        rows = self._safe(lambda: Cal.sudo().search_read(
            [('month', '=', first), ('company_id', 'in', [cid, False])],
            ['company_id', 'cutoff_date', 'pay_date']), default=[]) or []
        if not rows:
            return out
        rows.sort(key=lambda r: 0 if r['company_id'] else 1)
        row = rows[0]
        for key, field in (('cutoff', 'cutoff_date'), ('pay_date', 'pay_date')):
            d = row.get(field)
            if not d:
                continue
            days_key = 'cutoff_in_days' if key == 'cutoff' else 'pay_in_days'
            label_key = 'cutoff_label' if key == 'cutoff' else 'pay_label'
            out[key] = d.isoformat()
            out[days_key] = (d - today).days
            out[label_key] = self._day_label(d)
        return out

    @api.model
    def _day_label(self, d):
        """A bare date as the reader says it: weekday, day, month ("Fri 24
        Oct" / "Th 6, 24 thg 10"). Formatted here, on the server, from the
        DATE itself — never through a JS Date, which reads a bare date as UTC
        midnight and shows the day before west of UTC (NAV ledger, P3a)."""
        if not d:
            return ''
        return self._safe(
            lambda: format_date(self.env, d, date_format='EEE d MMM'),
            default=d.strftime('%a %d %b'))

    # ---------------- NAV P3b: readiness ----------------
    @api.model
    def _empty_readiness(self):
        return {'payroll': {}, 'attendance': {}, 'close': {},
                'close_door': False}

    @api.model
    def _readiness_context(self, runs, owner):
        """Everything the open cards' checklists need, in a fixed number of
        reads however many cards there are (spec §3.5):

          payroll     {company id: res.users | None} — the company's Payroll
                      manager (responsibility `payroll_mgr`), one resolve per
                      company
          close       {run id: {'open': [Monday, …], 'closed', 'total'}} —
                      ONE `pb.wf.lock` query for every open run's days
          attendance  {run id: res.users} — the attendance manager most of
                      the run's people report to, ONE grouped query
          close_door  may the reader open Workforce › Close at all
        """
        ctx = self._empty_readiness()
        open_runs = runs.filtered(lambda r: (r.state or 'draft') in _OPEN_STATES)
        if not open_runs:
            return ctx
        default_cid = self.env.company.id
        companies = {owner.get(r.id, default_cid) for r in open_runs}
        ctx['payroll'] = self._safe(lambda: self._payroll_owners(companies),
                                    default={}) or {}
        if 'pb.wf.lock' in self.env:
            ctx['close'] = self._safe(
                lambda: self._close_status(open_runs, owner), default={}) or {}
            with_open = [rid for rid, st in ctx['close'].items() if st['open']]
            if with_open:
                ctx['attendance'] = self._safe(
                    lambda: self._attendance_owners(with_open), default={}) or {}
                ctx['close_door'] = self._safe(self._close_door, default=False)
        return ctx

    @api.model
    def _payroll_owners(self, company_ids):
        """{company id: res.users or None} — who holds `payroll_mgr` for the
        whole company today (biz_approval_workflow `resolve`, the very lookup
        a pay run's route seats its Payroll check with)."""
        Role = self.env.get('biz.approval.role')
        Resp = self.env.get('biz.approval.responsibility')
        if Role is None or Resp is None:
            return {}
        role = Role.sudo().search([('key', '=', 'payroll_mgr')], limit=1)
        if not role:
            return {}
        out = {}
        for cid in company_ids:
            company = self.env['res.company'].sudo().browse(cid).exists()
            if not company:
                continue
            row, _via = Resp.sudo().resolve(company, role, [''])
            user = row.user_id if row else None
            if row and not user and row.pool_user_ids:
                user = row.pool_user_ids[:1]
            out[cid] = user or None
        return out

    @api.model
    def _close_weeks(self, ds, de):
        """[(Monday, [days of that week inside [ds, de]])] for every week
        overlapping the period — pb_close's own rule (`_close_weeks_in` +
        `_close_week_status`, payrun_wizard.py): a week straddling the month
        edge counts only its days inside this run's period."""
        if not ds or not de or de < ds:
            return []
        out = []
        cur = ds - timedelta(days=ds.weekday())
        while cur <= de:
            days = [cur + timedelta(days=i) for i in range(7)]
            days = [d for d in days if ds <= d <= de]
            if days:
                out.append((cur, days))
            cur += timedelta(days=7)
        return out

    @api.model
    def _close_status(self, open_runs, owner):
        """{run id: {'open': [Monday, …], 'closed': n, 'total': n}}.

        A week is closed when every one of its days inside the period is
        LOCKED for the run's company (`total == 0 or locked >= total`, the
        wizard's test). One `_locked_pairs` call covers every company and
        every day of every open run on the board.

        Only weeks that have STARTED count (Monday <= today; coordinator
        decision 2026-10-21): a week that is not here yet is not "not
        closed", so a run prepared on the 21st does not list the week of the
        26th, and `closed` / `total` are "of the weeks so far".
        """
        Lock = self.env['pb.wf.lock']
        default_cid = self.env.company.id
        today = fields.Date.context_today(self)
        plan, companies, days = {}, set(), set()
        for run in open_runs:
            weeks = [(monday, ds) for monday, ds
                     in self._close_weeks(run.date_start, run.date_end)
                     if monday <= today]
            if not weeks:
                continue
            cid = owner.get(run.id, default_cid)
            plan[run.id] = (cid, weeks)
            companies.add(cid)
            for _monday, ds in weeks:
                days.update(ds)
        if not plan:
            return {}
        locked = Lock._locked_pairs(list(companies), list(days))
        out = {}
        for rid, (cid, weeks) in plan.items():
            open_weeks = [monday for monday, ds in weeks
                          if not all((cid, d) in locked for d in ds)]
            out[rid] = {'open': open_weeks,
                        'closed': len(weeks) - len(open_weeks),
                        'total': len(weeks)}
        return out

    @api.model
    def _attendance_owners(self, run_ids):
        """{run id: res.users} — the attendance manager most of the run's
        people have (`hr.employee.attendance_manager_id`), ties to the lowest
        id. One grouped query for every run that has an open week."""
        Employee = self.env['hr.employee']
        field = Employee._fields.get('attendance_manager_id')
        if not run_ids or not field or not field.store:
            return {}
        # Raw SQL reads the table, not the cache (ledger: ABM June pay run).
        self.env['hr.payslip'].flush_model(
            ['payslip_run_id', 'employee_id', 'state'])
        Employee.flush_model(['attendance_manager_id'])
        self.env.cr.execute(
            "SELECT p.payslip_run_id, e.attendance_manager_id, COUNT(*) "
            "FROM hr_payslip p JOIN hr_employee e ON e.id = p.employee_id "
            "WHERE p.payslip_run_id IN %s AND p.state != 'cancel' "
            "AND e.attendance_manager_id IS NOT NULL "
            "GROUP BY 1, 2 ORDER BY 1, 3 DESC, 2",
            (tuple(run_ids),))
        best = {}
        for run_id, user_id, _n in self.env.cr.fetchall():
            best.setdefault(run_id, user_id)
        users = self.env['res.users'].sudo().browse(set(best.values())).exists()
        by_id = {u.id: u for u in users}
        return {rid: by_id[uid] for rid, uid in best.items() if uid in by_id}

    @api.model
    def _close_door(self):
        """True when Workforce › Close exists here and the reader may open
        it. A door that lands on a lens the reader cannot see is a dead end."""
        if not self.env.ref('pb_mission.action_pb_workforce',
                            raise_if_not_found=False):
            return False
        user = self.env.user
        for xmlid in _CLOSE_LENS_GROUPS:
            try:
                if user.has_group(xmlid):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _short_name(self, name):
        """What a chip calls a person: the given name (the last word of a
        Vietnamese name), the whole name when it is two words or fewer once a
        DEMO prefix is set aside (pb_hiring facade_p6 `_short_name`)."""
        words = (name or '').replace('DEMO ', '', 1).split()
        return ' '.join(words) if len(words) <= 2 else words[-1]

    @api.model
    def _person(self, user=None, team=''):
        """An owner chip: a person, or the team when nobody is named."""
        if user:
            return {'name': user.name or '', 'short': self._short_name(user.name),
                    'uid': user.id, 'me': user.id == self.env.uid, 'team': False}
        return {'name': team, 'short': team, 'uid': False, 'me': False,
                'team': True}

    @api.model
    def _money_words(self, amount, symbol):
        """A gap as a reader writes it: ₫1,200,000 (whole units)."""
        try:
            return '%s%s' % (symbol or '', '{:,.0f}'.format(abs(amount or 0.0)))
        except (TypeError, ValueError):
            return '%s%s' % (symbol or '', amount)

    @api.model
    def _run_checks(self, run, state, next_action, run_company, readiness,
                    unsourced=0, balance_ok=True, balance_gap=0.0, symbol=''):
        """(checks, ready, close_weeks) for one card.

        checks       [{key, tone, icon, text, detail, owner, next, advisory,
                       more}] in the spec's order — sent back · no source
                     data · does not add up · attendance weeks. Only what is
                     relevant; empty on Done and Rejected runs.
        ready        a draft with nothing in its way: it can be sent in, no
                     rose line and nothing sent back to fix. Advice (the
                     attendance line) does not make a run unready.
        close_weeks  {'closed', 'total'} when the close line is in play, for
                     the quick look's "Weeks closed: 3 of the 4 weeks so
                     far" (started weeks only); else None.
        """
        if state not in _OPEN_STATES:
            return [], False, None
        _ = self.env._
        checks = []
        payroll_user = (readiness.get('payroll') or {}).get(run_company)
        preparer = run.pb_prepared_uid
        if preparer:
            fixer = self._person(preparer)
        elif payroll_user:
            fixer = self._person(payroll_user)
        else:
            fixer = self._person(team=_("Payroll team"))
        run_door = {'key': 'run'}

        if state == 'draft' and run.pb_return_note:
            by = run.pb_return_uid
            note = run.pb_return_note
            text = (_("Sent back by %(who)s: “%(note)s”",
                      who=self._short_name(by.name), note=note) if by
                    else _("Sent back: “%s”", note))
            # the quick look names people in full
            full = (_("Sent back by %(who)s: “%(note)s”",
                      who=by.name, note=note) if by else text)
            when = self._fmt_date(run.pb_return_date)
            detail = (_("Sent back on %s. Fix what it says, then send it in again.",
                        when) if when
                      else _("Fix what it says, then send it in again."))
            checks.append({'key': 'sent_back', 'tone': 'amber', 'icon': 'rotate',
                           'text': text, 'full': full, 'detail': detail,
                           'by': (by.name or '') if by else '',
                           'owner': fixer, 'next': None, 'advisory': False,
                           'more': ''})
        if unsourced:
            checks.append({
                'key': 'unsourced', 'tone': 'rose', 'icon': 'alert',
                'text': (_("1 payslip has no source data") if unsourced == 1
                         else _("%s payslips have no source data", unsourced)),
                'detail': _("Their figures are scheme defaults, not real pay."),
                'owner': fixer,
                'next': dict(run_door, label=_("Open the payslips")),
                'advisory': False, 'more': ''})
        if balance_ok is False:
            gap = self._money_words(balance_gap, symbol)
            checks.append({
                'key': 'balance', 'tone': 'rose', 'icon': 'alert',
                'text': _("Figures do not add up (gap %s)", gap),
                'detail': _("%s is unaccounted for between gross, deductions "
                            "and net.", gap),
                'owner': fixer,
                'next': dict(run_door, label=_("Open the run to see which component")),
                'advisory': False, 'more': ''})

        # FILLIN P2 C1 — people on this run whose draft or running contract
        # still holds an answer Payobook filled in by itself that nobody has
        # checked (FILLIN P1 marks). Advice, never a block. A read.
        fillin = 0
        Line = self.env.get('hr.contract.advantage')
        if Line is not None and 'pb_fill' in Line._fields:
            self.env.cr.execute("""
                SELECT COUNT(DISTINCT p.employee_id)
                  FROM hr_payslip p
                  JOIN hr_contract c ON c.employee_id = p.employee_id
                                   AND c.state IN ('draft', 'open')
                  JOIN hr_contract_advantage a ON a.contract_id = c.id
                 WHERE p.payslip_run_id = %s AND p.state != 'cancel'
                   AND a.pb_fill = 'auto' AND a.pb_checked_at IS NULL""",
                                (run.id,))
            fillin = int(self.env.cr.fetchone()[0] or 0)
        if fillin:
            checks.append({
                'key': 'fillin', 'tone': 'amber', 'icon': 'listChecks',
                'text': (_("1 person has answers Payobook filled in that "
                           "nobody has checked yet.") if fillin == 1
                         else _("%s people have answers Payobook filled in "
                                "that nobody has checked yet.", fillin)),
                'detail': _("BPJS and tax settings were filled in from the "
                            "scheme's usual answers when their contracts "
                            "were created. Check them once under Contracts "
                            "› To check; the run can still go ahead."),
                'owner': self._person(team=_("HR team")),
                # The door: the Contracts roster opened on its "To check"
                # view (contracts.js reads `params.view`). The card's
                # `openCheck` and the run screen's `boardDoor` both open a
                # `next.action` as it is, so no screen change is needed.
                'next': {'key': 'contracts',
                         'label': _("Open Contracts › To check"),
                         'action': {'type': 'ir.actions.client',
                                    'tag': 'pb_contracts',
                                    'name': _("Contracts"),
                                    'params': {'view': 'fillin'}}},
                'advisory': True, 'more': ''})

        close_weeks = None
        status = (readiness.get('close') or {}).get(run.id)
        if status and status['total']:
            close_weeks = {'closed': status['closed'], 'total': status['total']}
        if status and status['open']:
            att = (readiness.get('attendance') or {}).get(run.id)
            att_owner = (self._person(att) if att
                         else self._person(team=_("Attendance team")))
            door = ({'key': 'close', 'label': _("Open Workforce › Close")}
                    if readiness.get('close_door') else None)
            weeks = status['open']
            shown = weeks[:CLOSE_LINES_MAX]
            rest = len(weeks) - len(shown)
            for i, monday in enumerate(shown):
                more = ''
                last = i == len(shown) - 1
                if rest and last:
                    more = (_("+1 more week") if rest == 1
                            else _("+%s more weeks", rest))
                checks.append({
                    'key': 'close_week', 'tone': 'amber', 'icon': 'lock',
                    'text': _("Attendance week of %s not closed",
                              self._safe(lambda m=monday: format_date(
                                  self.env, m, date_format='d MMM'),
                                  default=monday.strftime('%d %b'))),
                    'detail': _("Advice only: the run can still be sent in. "
                                "Closing the week locks the attendance behind "
                                "these payslips."),
                    'week': monday.isoformat(),
                    # one door per card, on the last week line: the same
                    # door under every week was noise (found in the walk)
                    'owner': att_owner, 'next': door if last else None,
                    'advisory': True,
                    'more': more})

        ready = (state == 'draft' and next_action == 'submit'
                 and not any(c['tone'] == 'rose' or c['key'] == 'sent_back'
                             for c in checks))
        return checks, ready, close_weeks

    @api.model
    def _run_companies(self, runs):
        """{run id: company id} — the entity a pay run actually happened in.

        `hr.payslip.run` carries no company of its own on this build. Its
        payslips do, and since GROUP P2 so does the scheme it was run for, so
        the answer is read from those in ONE indexed query rather than guessed
        from whichever company the reader is looking at.
        """
        if not runs:
            return {}
        out = {}
        Run = self.env['hr.payslip.run']
        if 'pb_formula_config_id' in Run._fields:
            for run in runs:
                config = run.pb_formula_config_id
                if config and config.company_id:
                    out[run.id] = config.company_id.id
        self.env.cr.execute(
            "SELECT payslip_run_id, MIN(company_id) FROM hr_payslip "
            "WHERE payslip_run_id IN %s AND state != 'cancel' GROUP BY 1",
            (tuple(runs.ids),))
        for run_id, company_id in self.env.cr.fetchall():
            if company_id:
                out[run_id] = company_id      # payslip truth wins
        return out

    @api.model
    def _scheme_currency_by_run(self, runs):
        """Each run's SCHEME currency, where it has a scheme.

        SCHEMECTX P1 — an India scheme inside a Vietnamese company is an India
        run, so the money on the card is the scheme's, not that of the company
        which happens to own the payslips. Rize runs both its Vietnam and its
        India payroll out of one VND company, so reading the company priced the
        India run's gross and net in dong while the payslips inside it were
        correctly in rupees.

        Same precedent as ``pb_payrun_results`` (SCHEMECTX P1 there too), and
        derived live through ``hr.payslip.run._pb_scheme_currency`` — the very
        method the stored ``pb_currency_id`` is computed from — rather than
        read off that stored field, which on some demo runs was computed under
        a different company context.
        """
        out = {}
        # FILTER wave 5: the same answer as `_pb_scheme_currency`, read for
        # every run at once. That method falls back to
        # `slip_ids.mapped('formula_config_id')[:1]`, which loads every payslip
        # of a run with no scheme of its own (9 s for 48 runs on the demo copy);
        # here the fallback is one query: the scheme of the run's newest
        # payslip that has one (payslips are ordered newest first).
        Run = self.env['hr.payslip.run']
        Slip = self.env['hr.payslip']
        config_of = {}
        if 'pb_formula_config_id' in Run._fields:
            for run in runs:
                if run.pb_formula_config_id:
                    config_of[run.id] = run.pb_formula_config_id
        rest = [rid for rid in runs.ids if rid not in config_of]
        if rest and 'formula_config_id' in Slip._fields:
            def first_configs():
                Slip.flush_model(['payslip_run_id', 'formula_config_id'])
                self.env.cr.execute(
                    "SELECT DISTINCT ON (payslip_run_id) payslip_run_id, formula_config_id "
                    "FROM hr_payslip WHERE payslip_run_id IN %s "
                    "AND formula_config_id IS NOT NULL "
                    "ORDER BY payslip_run_id, id DESC", (tuple(rest),))
                return dict(self.env.cr.fetchall())
            first = self._safe(first_configs, default=None)
            if first is None:
                for run in runs.filtered(lambda r: r.id in rest):
                    currency = self._safe(lambda r=run: r._pb_scheme_currency(), default=None)
                    if currency:
                        out[run.id] = {'name': currency.name,
                                       'symbol': currency.symbol or currency.name}
            else:
                Config = Slip._fields['formula_config_id'].comodel_name
                configs = self.env[Config].browse(set(first.values()))
                for rid, cid in first.items():
                    config_of[rid] = configs.filtered(lambda c, i=cid: c.id == i)[:1]
        for rid, config in config_of.items():
            currency = self._safe(lambda c=config: c.currency_id, default=None)
            if currency:
                out[rid] = {'name': currency.name,
                            'symbol': currency.symbol or currency.name}
        return out

    @api.model
    def _currency_by_company(self):
        rows = self.env['res.company'].sudo().with_context(
            active_test=False).search_read([], ['currency_id'])
        currencies = self.env['res.currency'].sudo().with_context(
            active_test=False).browse(
            [r['currency_id'][0] for r in rows if r['currency_id']]).exists()
        by_id = {c.id: {'name': c.name, 'symbol': c.symbol or c.name}
                 for c in currencies}
        return {r['id']: by_id.get(r['currency_id'][0])
                for r in rows if r['currency_id']}

    @api.model
    def _fmt_period(self, d1, d2):
        if not d1 and not d2:
            return ''
        try:
            a = d1.strftime('%d %b') if d1 else '?'
            b = d2.strftime('%d %b %Y') if d2 else '?'
            return '%s – %s' % (a, b)
        except Exception:
            return '%s – %s' % (d1 or '?', d2 or '?')

    @api.model
    def _fmt_date(self, d):
        """A date or datetime as the reader's short date, or ''."""
        if not d:
            return ''
        try:
            if hasattr(d, 'hour'):
                d = fields.Datetime.context_timestamp(self, d).date()
            return format_date(self.env, d, date_format='d MMM y')
        except Exception:
            return str(d)[:10]

    @api.model
    def _month_key(self, d):
        return d.strftime('%Y-%m') if d else ''

    @api.model
    def _month_label(self, d):
        if not d:
            return ''
        return self._safe(lambda: format_date(self.env, d, date_format='MMMM y'),
                          default=d.strftime('%B %Y'))
