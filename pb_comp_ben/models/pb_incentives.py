# -*- coding: utf-8 -*-
"""`pb.incentives` — the Awards lens's only server surface.

THE QUESTION THIS BOARD ANSWERS: what has somebody promised, and has it been
paid. So the four numbers across the top are the four places an award can be
stuck — waiting for a decision, decided but not in a pay run, in a pay run, and
done — and a row is one award with its state on it.

The preview before "Queue this month" is the hero, and it is the safety rail as
well: nothing is written until somebody has read who gets what, out of which run,
and whether the pay scheme even knows the pay item the money would arrive under.
"""

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.fields import Domain

from .comp_common import (
    FEEDABLE_RUN_STATES, FULFILMENT_LABEL, GROUP_HEAD, GROUP_USER,
    INCENTIVE_KIND_LABEL, INCENTIVE_STATE_LABEL, P_INCENTIVE_CODE,
    P_LETTER_SEND, flag, param,
)

_logger = logging.getLogger(__name__)

#: One page of the table (the filter panel pages it; "Show N more" appends).
PAGE_SIZE = 60

#: Where an award is — the five steps and the one outcome at no step. The
#: strip, the numbers line and the panel's "Where it is" all read these.
WHERE_DOMAINS = {
    'draft': [('state', '=', 'draft')],
    'submitted': [('state', '=', 'submitted')],
    'agreed': [('state', '=', 'approved'), '|', ('fulfilment', '=', False),
               ('fulfilment', 'in', ('pending', 'letter'))],
    'queued': [('state', '=', 'approved'), ('fulfilment', '=', 'queued')],
    'paid': [('state', '=', 'approved'), ('fulfilment', '=', 'paid')],
    'refused': [('state', '=', 'refused')],
}


def _refusal():
    return {
        'allowed': False, 'can_write': False, 'can_approve': False,
        'rows': [], 'kpis': {}, 'runs': [], 'kinds': [], 'states': [],
        'total': 0, 'capped': False, 'code': '', 'letters_on': False,
        'why': _("Awards are looked after by the pay team. This screen is not "
                 "part of the general HR permissions — somebody has to add you "
                 "to it by name."),
    }


class PbIncentives(models.AbstractModel):
    _name = 'pb.incentives'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook awards cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:              # noqa: BLE001
            _logger.debug('awards metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin()
                    or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_HEAD))

    @api.model
    def _can_write(self):
        return self._can_read()

    @api.model
    def _can_approve(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group(GROUP_HEAD))

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_refusal()['why'])
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def _scope(self):
        """Every award this reader's companies hold, and the ones filed under
        no company."""
        return ['|', ('company_id', '=', False),
                ('company_id', 'in', self.env.companies.ids)]

    @api.model
    def get_board(self, month=None):
        """The head of the board: who may do what, the numbers line, the runs
        an award can go into. The table is paged by the filter panel through
        `get_awards_page` (FILTER W1); the numbers are counted over every
        award now, not over the newest 400."""
        if not self._can_read():
            return _refusal()
        Incentive = self.env['pb.incentive']
        scope = self._scope()
        today = date.today()
        this_month = today.replace(day=1)
        in_month = [('period_month', '>=', this_month),
                    ('period_month', '<', this_month + relativedelta(months=1))]

        def count(key, extra=None):
            return self._safe(lambda: Incentive.search_count(
                scope + WHERE_DOMAINS[key] + (extra or [])))

        to_queue_dom = scope + WHERE_DOMAINS['agreed'] + in_month
        amount_to_queue = self._safe(lambda: sum(
            Incentive.search(to_queue_dom).mapped('amount')), default=0.0)
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_approve': self._can_approve(),
            'total': self._safe(lambda: Incentive.search_count(scope)),
            'code': (param(self.env, P_INCENTIVE_CODE) or 'INCENTV').upper(),
            'letters_on': flag(self.env, P_LETTER_SEND),
            'month': this_month.isoformat(),
            'runs': self._open_runs(),
            'kinds': [{'key': k, 'label': v}
                      for k, v in INCENTIVE_KIND_LABEL.items()],
            'states': [{'key': k, 'label': v}
                       for k, v in INCENTIVE_STATE_LABEL.items()],
            'kpis': {
                'waiting': count('submitted'),
                'to_queue': count('agreed', in_month),
                'queued': count('queued'),
                'paid_mtd': count('paid', in_month),
                'refused': count('refused'),
                'amount_to_queue': amount_to_queue,
            },
            'why': '',
        }

    # ============================================================ filter panel
    # FILTER W1 (2026-10-31): the table used to hold the newest 400 awards and
    # filter them in the browser; the numbers line was counted from those 400
    # too. Everything is now counted and paged on the server for the panel's
    # state (pb_filter_kit). The gate is the screen's own: a reader this
    # board refuses gets its explanation, and the panel stays out of the way.

    def _pbf_model(self):
        return 'pb.incentive'

    def _pbf_screen(self):
        return 'awards'

    def _pbf_base_domain(self):
        return self._scope()

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_search_domain(self, search):
        """A person (by name or code) or a reason. The person is found as the
        system, the same way every employee read on this board is (R56): an
        awards holder need not be able to read the employee file."""
        q = (search or '').strip()
        if not q:
            return None
        parts = [Domain('reason', 'ilike', q)]
        try:
            emp_ids = self.env['hr.employee'].sudo().with_context(active_test=False).search(
                ['|', ('name', 'ilike', q), ('barcode', 'ilike', q)]).ids
        except Exception as e:  # noqa: BLE001
            _logger.info('awards search by person failed: %s', e)
            emp_ids = []
        if emp_ids:
            parts.append(Domain('employee_id', 'in', emp_ids))
        return Domain.OR(parts)

    def _pbf_sorts(self):
        return [
            {'key': 'month', 'label': _('Pay month, newest first'),
             'order': 'period_month desc, id desc'},
            {'key': 'month_asc', 'label': _('Pay month, oldest first'),
             'order': 'period_month asc, id asc'},
            {'key': 'amount', 'label': _('Largest amount first'), 'order': 'amount desc, id desc'},
            {'key': 'recent', 'label': _('Raised most recently'), 'order': 'id desc'},
        ]

    def _pbf_spec(self):
        return [
            # ---- pinned: where it is, what kind, which month
            {'key': 'where', 'label': _('Where it is'), 'icon': 'route',
             'group': 'pay', 'type': 'choice', 'pinned': True,
             'requires': ['state', 'fulfilment'],
             'help': _('The steps above the table, plus the awards that were not approved.'),
             'options': [
                 {'value': 'draft', 'label': _('Being prepared'), 'tone': 'slate',
                  'domain': WHERE_DOMAINS['draft']},
                 {'value': 'submitted', 'label': _('Waiting for approval'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['submitted']},
                 {'value': 'agreed', 'label': _('Agreed, not in a run'), 'tone': 'blue',
                  'domain': WHERE_DOMAINS['agreed']},
                 {'value': 'queued', 'label': _('In a pay run'), 'tone': 'blue',
                  'domain': WHERE_DOMAINS['queued']},
                 {'value': 'paid', 'label': _('Paid'), 'tone': 'green',
                  'domain': WHERE_DOMAINS['paid']},
                 {'value': 'refused', 'label': _('Not approved'), 'tone': 'rose',
                  'domain': WHERE_DOMAINS['refused']},
             ]},
            {'key': 'kind', 'label': _('Kind'), 'icon': 'award',
             'group': 'pay', 'type': 'selection', 'path': 'kind', 'pinned': True},
            {'key': 'month', 'label': _('Pay it in'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'period_month', 'presets': 'past',
             'pinned': True, 'help': _('The month the award is paid with the salary.')},
            # ---- more filters
            # names read as the system (kit 1.2.0 `label_sudo`), the same R56
            # reason `_person()` reads the employee that way
            {'key': 'person', 'label': _('Who it is for'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id', 'label_sudo': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'none_label': _('No department'), 'label_sudo': True},
            {'key': 'run', 'label': _('Pay run'), 'icon': 'play',
             'group': 'pay', 'type': 'many2one', 'path': 'run_id',
             'none_label': _('Not in a pay run')},
            {'key': 'amount', 'label': _('Amount'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'amount', 'unit': 'money'},
            {'key': 'approval', 'label': _('Approval'), 'icon': 'stamp',
             'group': 'other', 'type': 'selection', 'path': 'state'},
            {'key': 'fulfilment', 'label': _('Where it has got to'), 'icon': 'send',
             'group': 'other', 'type': 'selection', 'path': 'fulfilment',
             'none_label': _('Not approved yet')},
            {'key': 'source', 'label': _('Where it came from'), 'icon': 'sparkles',
             'group': 'other', 'type': 'selection', 'path': 'source'},
            {'key': 'asked_by', 'label': _('Asked by'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'requested_by_user_id',
             'none_label': _('Not recorded')},
            {'key': 'letter', 'label': _('Letter on file'), 'icon': 'fileText',
             'group': 'other', 'type': 'choice', 'requires': ['letter_id'],
             'options': [
                 {'value': 'yes', 'label': _('Letter prepared'), 'tone': 'green',
                  'domain': [('letter_id', '!=', False)]},
                 {'value': 'no', 'label': _('No letter yet'), 'tone': 'slate',
                  'domain': [('letter_id', '=', False)]},
             ]},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All awards'), 'icon': 'award', 'filters': {}},
            {'key': 'waiting', 'label': _('Waiting for approval'),
             'filters': {'where': ['submitted']}},
            {'key': 'agreed', 'label': _('Agreed, not in a run'), 'filters': {'where': ['agreed']}},
            {'key': 'queued', 'label': _('In a pay run'), 'filters': {'where': ['queued']}},
            {'key': 'paid', 'label': _('Paid this month'),
             'filters': {'where': ['paid'], 'month': {'preset': 'this_month'}}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': _refusal()['why']}
        return super().pbf_layout()

    @api.model
    def _pbf_step_counts(self, filters, search):
        """The strip's counts for the panel's state: each step counted against
        every OTHER filter (the kit's rule), so the strip and the panel's
        "Where it is" section always say the same numbers."""
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'where'), None)
        if not s:
            return {}
        res = self._pbf_count_section(s, filters or {}, search, spec)
        return {r['v']: r['n'] for r in res.get('values') or []}

    @api.model
    def get_awards_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of the table for the filter panel's current state, with
        the step strip's counts for the same state."""
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        Incentive = self.env['pb.incentive']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'period_month desc, id desc'
        rows = []
        for rec in Incentive.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(rec))
            except Exception as e:  # noqa: BLE001 — one bad row never blanks the table
                _logger.debug('awards row %s failed: %s', rec.id, e)
        out = {'rows': rows, 'total': Incentive.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search), default={})
        return out

    @api.model
    def _row(self, rec):
        emp = rec._person()
        return {
            'id': rec.id,
            'employee': emp.name or '',
            'employee_id': emp.id,
            'initials': _initials(emp.name or ''),
            'kind': rec.kind or '',
            'kind_label': INCENTIVE_KIND_LABEL.get(rec.kind, ''),
            'amount': rec.amount or 0.0,
            'currency': rec.currency_id.symbol or '',
            'month': (rec.period_month.isoformat() if rec.period_month else ''),
            'month_label': (rec.period_month.strftime('%b %Y')
                            if rec.period_month else ''),
            'state': rec.state or 'draft',
            'state_label': INCENTIVE_STATE_LABEL.get(rec.state, ''),
            'fulfilment': rec.fulfilment or '',
            'fulfilment_label': FULFILMENT_LABEL.get(rec.fulfilment, ''),
            'has_letter': bool(rec.letter_id and rec.letter_id.attachment_id),
            'letter_id': rec.letter_id.id if rec.letter_id else 0,
            'run': rec.run_id.name if rec.run_id else '',
            'run_id': rec.run_id.id if rec.run_id else 0,
            'reason': rec.reason or '',
            'source': rec.source or 'manual',
        }

    @api.model
    def _open_runs(self):
        """Pay runs an award can still be put into — and NOTHING else.

        A closed list is the safety rail expressed as a control: the dialog
        cannot offer a run that has been sent in for approval, so nobody has to
        be told no.
        """
        runs = self.env['hr.payslip.run'].sudo().search(
            [('state', 'in', list(FEEDABLE_RUN_STATES))],
            order='date_start desc, id desc', limit=25)
        return [{'id': r.id, 'name': r.name or '',
                 'state': r.state or 'draft',
                 'period': ('%s → %s' % (r.date_start or '', r.date_end or ''))}
                for r in runs]

    # ------------------------------------------------------------ the writes
    @api.model
    def create_award(self, vals):
        self._require_read()
        clean = {
            'employee_id': int((vals or {}).get('employee_id') or 0),
            'kind': (vals or {}).get('kind') or 'bonus',
            'amount': float((vals or {}).get('amount') or 0.0),
            'reason': (vals or {}).get('reason') or '',
        }
        month = (vals or {}).get('period_month')
        if month:
            clean['period_month'] = fields.Date.to_date(month).replace(day=1)
        if not clean['employee_id']:
            raise AccessError(_("Choose who the award is for."))
        rec = self.env['pb.incentive'].create(clean)
        return rec.id

    @api.model
    def submit(self, incentive_id):
        self._require_read()
        return self.env['pb.incentive'].browse(int(incentive_id)).action_submit()

    @api.model
    def approve(self, incentive_id):
        self._require_read()
        return self.env['pb.incentive'].browse(int(incentive_id)).action_approve()

    @api.model
    def refuse(self, incentive_id, note=False):
        self._require_read()
        return self.env['pb.incentive'].browse(
            int(incentive_id)).action_refuse(note=note or False)

    @api.model
    def make_letter(self, incentive_id):
        self._require_read()
        return bool(self.env['pb.incentive'].browse(
            int(incentive_id)).action_make_letter())

    @api.model
    def employee_options(self, term=''):
        """People to pick from. Read as the system for the SAME reason every
        other employee read in this module is (R56) — the search is the gate."""
        self._require_read()
        Emp = self.env['hr.employee'].sudo()
        domain = [('company_id', 'in', self.env.companies.ids)]
        if term:
            domain += ['|', ('name', 'ilike', term), ('barcode', 'ilike', term)]
        rows = Emp.search(domain, order='name', limit=25)
        return [{'id': e.id, 'name': e.name or '',
                 'code': e.barcode or ''} for e in rows]

    # -------------------------------------------------------------- the feed
    @api.model
    def preview_queue(self, run_id, incentive_ids=None):
        self._require_read()
        return self.env['pb.oneoff.feed'].preview_for_run(
            run_id, incentive_ids=incentive_ids or None)

    @api.model
    def confirm_queue(self, run_id, incentive_ids=None):
        self._require_read()
        return self.env['pb.oneoff.feed'].queue_for_run(
            incentive_ids or None, run_id)


def _initials(name):
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return '?'
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()
