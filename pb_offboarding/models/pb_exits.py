# -*- coding: utf-8 -*-
"""`pb.exits` — the Exits lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down, `self.env
.companies` scoping on every search, a row cap, and no sudo in a READ.

The one deliberate exception is the GATE. `pb_ready` is computed from three
sudo reads (P2's register, P4's clearances, P0's blocking steps) because a gate
a reader's own access can soften is not a gate — but it is only ever REPORTED
here. Every write goes through `_require_write()` and then through the model
that owns the fact.

It reuses P0's tiers, the same call P3 made for the same reason: an exit is not
a separate permission from the rest of the lifecycle, and a fifth ladder would
be a group nobody knew to grant.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .offboarding_common import (
    CLEARANCE_DEPT_LABEL, CLEARANCE_ORDER, GROUP_ADMIN, GROUP_MANAGER,
    GROUP_USER, KT_STATE_LABEL, RESIGNATION_STATE_LABEL, initials,
)

_logger = logging.getLogger(__name__)

#: The old `get_board` payload's cap. The board itself now pages (FILTER W2).
BOARD_LIMIT = 300

#: Cards per page on the filtered board ("Show N more" loads the next page).
PAGE_SIZE = 60

#: A checklist that is still going (the board's own states, and the gate's).
CASE_OPEN = ('draft', 'active', 'on_hold')

#: A leaver stays on this board for this long after their last day. Past it the
#: checklist may still have a stray step on it, but the person has gone and a
#: board that still calls them "leaving" is wrong.
LEAVING_FOR_DAYS = 120


class PbExits(models.AbstractModel):
    _name = 'pb.exits'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Exits cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('Exits metric failed: %s', e)
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
                "You can look at who is leaving, but changing an exit is for "
                "the HR team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'countries': [], 'departments': [],
                    'months': [], 'depts': []}
        Case = self.env['pb.journey.case']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()
        floor = today - timedelta(days=LEAVING_FOR_DAYS)

        cases = self._safe(lambda: Case.search([
            ('company_id', 'in', co_ids),
            ('case_type', '=', 'offboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
            '|', ('anchor_date', '=', False), ('anchor_date', '>=', floor),
        ], order='anchor_date, id', limit=BOARD_LIMIT),
            default=Case.browse())

        rows = []
        for case in cases:
            try:
                rows.append(self._row(case, today))
            except Exception:
                _logger.exception('Exits row for case %s', case.id)

        month_end = today + timedelta(days=31)
        kpis = {
            'leaving': len([r for r in rows if r['lwd']
                            and today <= _d(r['lwd']) <= month_end]),
            'gone': len([r for r in rows if r['lwd']
                         and _d(r['lwd']) < today]),
            'blocked': len([r for r in rows
                            if r['ff']['id'] and not r['ff']['ready']
                            and not r['ff']['closed']]),
            'clearances': sum(
                len([c for c in r['clearances'] if c['state'] == 'pending'])
                for r in rows),
            'assets': sum(r['assets'] for r in rows),
            # LEARN REFRESH step 6: worked out, waiting for a person to check
            # it and send it for approval
            'to_check': len([r for r in rows if r['ff'].get('to_check')]),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'countries': _facet(rows, 'country'),
            'departments': _facet(rows, 'dept'),
            'months': _facet(rows, 'month'),
            'depts': [{'id': d, 'label': CLEARANCE_DEPT_LABEL[d]}
                      for d in CLEARANCE_ORDER],
        }

    @api.model
    def _row(self, case, today=None):
        today = today or date.today()
        emp = case.employee_id
        lwd = case.anchor_date
        days = (lwd - today).days if lwd else None
        clearances = self._safe(
            lambda: case.clearance_ids.sorted(key=lambda c: c.sequence),
            default=self.env['pb.exit.clearance'].browse())
        by_dept = {c.dept: c for c in clearances}
        assets = self._safe(
            lambda: self.env['pb.asset'].open_items_for(emp.id),
            default={'tangible': [], 'digital': [], 'total': 0})
        resignation = self._safe(
            lambda: self.env['pb.resignation'].sudo().search(
                [('employee_id', '=', emp.id)],
                order='create_date desc', limit=1),
            default=self.env['pb.resignation'].browse())
        ff = self._safe(
            lambda: self.env['hr.full.final.settlement'].pb_gate_for(emp.id),
            default={'id': 0, 'ready': False, 'closed': False, 'blockers': [],
                     'net': 0.0, 'currency': '', 'date': '',
                     'state': '', 'to_check': False, 'issue': ''})
        kt = self._safe(lambda: case.kt_item_ids,
                        default=self.env['pb.kt.item'].browse())
        farewell = self._safe(
            lambda: case.task_ids.filtered(
                lambda t: t.automation_key == 'farewell')[:1],
            default=self.env['pb.journey.task'].browse())
        feedback = self._safe(
            lambda: self.env['pb.feedback.request'].sudo().search(
                [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1),
            default=self.env['pb.feedback.request'].browse())
        return {
            'id': case.id,
            'employee_id': emp.id,
            'employee': emp.name or '—',
            'initials': initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id
            if emp else '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': (emp.department_id.name if emp.department_id else '')
            or _('No team'),
            'country': (emp.country_id.name if emp.country_id else '')
            or (emp.company_id.country_id.name
                if emp.company_id and emp.company_id.country_id else '')
            or _('Not set'),
            'lwd': str(lwd) if lwd else '',
            'month': str(lwd)[:7] if lwd else '',
            'days': days,
            'when': _when(days),
            'progress': case.progress,
            'open_tasks': case.open_task_count,
            'overdue': case.overdue_task_count,
            'resignation_id': resignation.id if resignation else 0,
            'resignation_state': resignation.state if resignation else '',
            'resignation_label': (
                RESIGNATION_STATE_LABEL.get(resignation.state, '')
                if resignation else _('Not through a resignation')),
            'clearances': [{
                'id': by_dept[d].id if d in by_dept else 0,
                'dept': d,
                'label': CLEARANCE_DEPT_LABEL[d],
                'state': by_dept[d].state if d in by_dept else 'missing',
                'owner': (by_dept[d].owner_user_id.name
                          if d in by_dept and by_dept[d].owner_user_id else ''),
                'note': (by_dept[d].note or '') if d in by_dept else '',
            } for d in CLEARANCE_ORDER],
            'kt_open': len([k for k in kt if k.state != 'done']),
            'kt_total': len(kt),
            'kt_last_ping': str(case.kt_last_ping) if case.kt_last_ping else '',
            'assets': len(assets.get('tangible') or []),
            'assets_digital': len(assets.get('digital') or []),
            'ff': ff,
            'feedback': feedback.state if feedback else '',
            'feedback_done': bool(feedback and feedback.state == 'submitted'),
            'feedback_id': feedback.id if feedback else 0,
            'farewell_task_id': farewell.id if farewell else 0,
            'farewell_state': farewell.state if farewell else '',
        }

    # =====================================================================
    #  THE FILTER PANEL (pb_filter_kit, FILTER wave 2)
    #
    #  The board used to read 300 leavers, count its chips from them and
    #  filter them in the browser. Now every count is a server count over
    #  everybody leaving, and the cards come a page at a time. `get_board`
    #  above still answers the old payload (ruling R4).
    #
    #  Half of what a card says lives on OTHER models and has no path from
    #  the checklist: the settlement (found by employee), what the person is
    #  still holding, the steps and desks that hold the money. Those become
    #  `domain_method`s over ONE batch of facts (`_ex_facts`): five queries
    #  over the whole board, never one per card, cached for the request.
    # =====================================================================
    def _pbf_model(self):
        return 'pb.journey.case'

    def _pbf_screen(self):
        return 'exits'

    def _pbf_base_domain(self):
        co_ids = self.env.companies.ids or [self.env.company.id]
        floor = self._pbf_today() - timedelta(days=LEAVING_FOR_DAYS)
        return [('company_id', 'in', co_ids),
                ('case_type', '=', 'offboarding'),
                ('state', 'in', list(CASE_OPEN)),
                '|', ('anchor_date', '=', False),
                ('anchor_date', '>=', fields.Date.to_string(floor))]

    def _pbf_search_fields(self):
        return ['employee_id.name', 'employee_id.job_title',
                'employee_id.department_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'last_day', 'label': _('Last day, soonest first'),
             'order': 'anchor_date asc nulls last, id asc'},
            {'key': 'last_day_late', 'label': _('Last day, latest first'),
             'order': 'anchor_date desc nulls last, id desc'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'employee_id, id'},
            {'key': 'progress', 'label': _('Least done first'),
             'order': 'progress asc, anchor_date asc nulls last, id asc'},
        ]

    @api.model
    def _ex_facts(self):
        """The settlement and gate facts for EVERY leaver on the board.

        `pb_gate_for` answers them for one person (and the cards still use
        it); this answers them for all of them at once, by employee, with the
        same three gate probes `hr.full.final.settlement._pb_blocker_list`
        makes — blocking steps, open clearances, items not back — read under
        sudo exactly as the gate reads them, because a gate a reader's own
        access can soften is not a gate. Five queries in all, cached on the
        cursor for the rest of this request (every count in one panel load
        asks the same question).
        """
        key = ('pb_exits_facts', self.env.uid, tuple(self.env.companies.ids),
               str(self._pbf_today()))
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        Case = self.env['pb.journey.case']
        cases = Case.search_fetch(self._pbf_base_domain(), ['employee_id'])
        emp_of = {c.id: c.employee_id.id for c in cases}
        emp_ids = sorted({e for e in emp_of.values() if e})
        settle, blocked, items = {}, set(), {}
        if emp_ids:
            FF = self.env['hr.full.final.settlement'].sudo()
            wanted = ['employee_id', 'pb_closed']
            has_check = 'pb_to_check' in FF._fields
            if has_check:
                wanted.append('pb_to_check')
            # the settlement `pb_gate_for` picks: closed first, then newest
            for s in FF.search_fetch([('employee_id', 'in', emp_ids)], wanted,
                                     order='pb_closed desc, settlement_date desc, id desc'):
                settle.setdefault(s.employee_id.id, {
                    'closed': bool(s.pb_closed),
                    'to_check': bool(has_check and s.pb_to_check),
                })
            # 1. steps on any open checklist marked as holding the money
            tasks = self.env['pb.journey.task'].sudo().search_fetch([
                ('case_id.employee_id', 'in', emp_ids),
                ('case_id.state', 'in', list(CASE_OPEN)),
                ('blocking_ff', '=', True),
                ('state', 'not in', ('done', 'skipped')),
            ], ['case_id'])
            blocked |= set(tasks.mapped('case_id.employee_id').ids)
            # 2. clearances still owed
            blocked |= set(self.env['pb.exit.clearance'].sudo().search_fetch([
                ('employee_id', 'in', emp_ids),
                ('case_id.state', 'in', list(CASE_OPEN)),
                ('state', '=', 'pending'),
            ], ['employee_id']).mapped('employee_id').ids)
            # 3. what they still physically hold (the tangible half only:
            #    `open_items_for` puts everything that is not digital there)
            for row in self.env['pb.asset.assignment'].sudo().search_fetch([
                ('employee_id', 'in', emp_ids),
                ('state', '=', 'open'),
                ('asset_id.kind', '!=', 'digital'),
            ], ['employee_id']):
                eid = row.employee_id.id
                items[eid] = items.get(eid, 0) + 1
            blocked |= set(items)
        out = {k: set() for k in ('none', 'closed', 'ready', 'held', 'to_check', 'assets')}
        out['item_count'] = 0
        for case_id, emp in emp_of.items():
            ff = settle.get(emp)
            if items.get(emp):
                out['assets'].add(case_id)
                out['item_count'] += items[emp]
            if not ff:
                out['none'].add(case_id)
                continue
            if ff['to_check']:
                out['to_check'].add(case_id)
            if ff['closed']:
                out['closed'].add(case_id)
            elif emp in blocked:
                out['held'].add(case_id)
            else:
                out['ready'].add(case_id)
        cache[key] = out
        return out

    # ---- the facts as domains (choice options name these by `domain_method`)
    def _ex_ids(self, *keys):
        facts = self._ex_facts()
        ids = set()
        for k in keys:
            ids |= facts[k]
        return [('id', 'in', sorted(ids))]

    def _pbf_dm_ff_ready(self):
        return self._ex_ids('ready')

    def _pbf_dm_ff_held(self):
        return self._ex_ids('held')

    def _pbf_dm_ff_check(self):
        return self._ex_ids('to_check')

    def _pbf_dm_ff_closed(self):
        return self._ex_ids('closed')

    def _pbf_dm_ff_none(self):
        return self._ex_ids('none')

    def _pbf_dm_assets_yes(self):
        return self._ex_ids('assets')

    def _pbf_dm_assets_no(self):
        return [('id', 'not in', self._ex_ids('assets')[0][2])]

    def _ex_gone(self):
        return Domain('anchor_date', '<', fields.Date.to_string(self._pbf_today()))

    def _pbf_dm_step_notice(self):
        """Last day still ahead (or not set), settlement neither ready nor closed."""
        done = self._ex_ids('ready', 'closed')[0][2]
        return Domain('id', 'not in', done) & ~self._ex_gone()

    def _pbf_dm_step_signoff(self):
        """Gone, and the settlement is neither ready nor closed."""
        done = self._ex_ids('ready', 'closed')[0][2]
        return Domain('id', 'not in', done) & self._ex_gone()

    def _ex_literal(self):
        today = fields.Date.to_string(self._pbf_today())
        return {
            'pending': Domain('clearance_ids', 'any', [('state', '=', 'pending')]),
            'kt_open': Domain('kt_item_ids', 'any', [('state', '!=', 'done')]),
            'overdue': Domain('task_ids', 'any', [
                ('state', 'in', ['pending', 'in_progress', 'blocked']),
                ('due_date', '<', today)]),
        }

    def _pbf_dm_held_yes(self):
        """"Something is holding it up" — the old chip (exits_board.js
        isBlocked): items not back, a clearance open, a step overdue or a
        handover item open, and the settlement not closed."""
        lit = self._ex_literal()
        return (Domain(self._ex_ids('assets')) | lit['pending'] | lit['overdue']
                | lit['kt_open']) & ~Domain(self._ex_ids('closed'))

    def _pbf_dm_held_no(self):
        return ~self._pbf_dm_held_yes()

    @api.model
    def _ex_glance_filters(self):
        """What each figure on the numbers line means as a filter — the SAME
        filters as the built-in views, so pressing one lights its tab."""
        today = self._pbf_today()
        return {
            # "Leaving this month" has always meant the next 31 days
            'leaving': {'last_day': {'from': fields.Date.to_string(today),
                                     'to': fields.Date.to_string(today + timedelta(days=31))}},
            'gone': {'last_day': {'preset': 'passed'}},
            'blocked': {'settlement': ['held']},
            'clearances': {'clearances': ['pending']},
            'assets': {'assets': ['yes']},
            'to_check': {'settlement': ['to_check']},
        }

    def _pbf_spec(self):
        lit = self._ex_literal()
        desks = [('it', _('IT')), ('hr', _('HR')), ('finance', _('Finance')),
                 ('admin', _('Admin'))]
        return [
            # ---- pinned: when they go, which team, who still has to sign
            {'key': 'last_day', 'label': _('Last day'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'anchor_date',
             'presets': 'future', 'pinned': True, 'none_label': _('No last day set')},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one',
             'path': 'employee_id.department_id', 'pinned': True,
             'none_label': _('No team')},
            {'key': 'clearances', 'label': _('Clearances'), 'icon': 'shieldCheck',
             'group': 'other', 'type': 'choice', 'pinned': True,
             'requires': ['clearance_ids'],
             'options': [
                 {'value': 'pending', 'label': _('Still open'), 'tone': 'amber',
                  'domain': lit['pending']},
                 {'value': 'clear', 'label': _('Nothing open'), 'tone': 'green',
                  'domain': ~lit['pending']},
             ]},
            # ---- more filters
            {'key': 'step', 'label': _('Where they are'), 'icon': 'listChecks',
             'group': 'other', 'type': 'choice',
             'options': [
                 {'value': 'notice', 'label': _('Working their notice'), 'tone': 'slate',
                  'domain_method': '_pbf_dm_step_notice'},
                 {'value': 'signoff', 'label': _('Signing off'), 'tone': 'amber',
                  'domain_method': '_pbf_dm_step_signoff'},
                 {'value': 'ready', 'label': _('Ready to settle'), 'tone': 'blue',
                  'domain_method': '_pbf_dm_ff_ready'},
                 {'value': 'settled', 'label': _('Settled'), 'tone': 'green',
                  'domain_method': '_pbf_dm_ff_closed'},
             ]},
            {'key': 'settlement', 'label': _('Final settlement'), 'icon': 'wallet',
             'group': 'pay', 'type': 'choice',
             'help': _('The last payment, and whether anything still stands in front of it.'),
             'options': [
                 {'value': 'ready', 'label': _('Ready to settle'), 'tone': 'blue',
                  'domain_method': '_pbf_dm_ff_ready'},
                 {'value': 'held', 'label': _('Held up'), 'tone': 'rose',
                  'domain_method': '_pbf_dm_ff_held'},
                 {'value': 'to_check', 'label': _('Worked out, to check'), 'tone': 'amber',
                  'domain_method': '_pbf_dm_ff_check'},
                 {'value': 'closed', 'label': _('Settled'), 'tone': 'green',
                  'domain_method': '_pbf_dm_ff_closed'},
                 {'value': 'none', 'label': _('No settlement yet'), 'tone': 'slate',
                  'domain_method': '_pbf_dm_ff_none'},
             ]},
            {'key': 'held', 'label': _('Held up'), 'icon': 'alert',
             'group': 'other', 'type': 'choice',
             'help': _('Items not back, a clearance open, a step overdue or a handover item open.'),
             'options': [
                 {'value': 'yes', 'label': _('Something is holding it up'), 'tone': 'rose',
                  'domain_method': '_pbf_dm_held_yes'},
                 {'value': 'no', 'label': _('Nothing in the way'), 'tone': 'green',
                  'domain_method': '_pbf_dm_held_no'},
             ]},
            {'key': 'assets', 'label': _('Items not back'), 'icon': 'package',
             'group': 'other', 'type': 'choice',
             'options': [
                 {'value': 'yes', 'label': _('Still holding something'), 'tone': 'amber',
                  'domain_method': '_pbf_dm_assets_yes'},
                 {'value': 'no', 'label': _('Nothing to hand back'), 'tone': 'green',
                  'domain_method': '_pbf_dm_assets_no'},
             ]},
            {'key': 'desk', 'label': _('Desk still open'), 'icon': 'shieldCheck',
             'group': 'other', 'type': 'choice', 'requires': ['clearance_ids'],
             'options': [{'value': d, 'label': label, 'tone': 'amber',
                          'domain': [('clearance_ids', 'any',
                                      [('dept', '=', d), ('state', '=', 'pending')])]}
                         for d, label in desks]},
            {'key': 'handover', 'label': _('Handover'), 'icon': 'repeat',
             'group': 'other', 'type': 'choice', 'requires': ['kt_item_ids'],
             'options': [
                 {'value': 'open', 'label': _('Items still to hand over'), 'tone': 'amber',
                  'domain': lit['kt_open']},
                 {'value': 'done', 'label': _('All handed over'), 'tone': 'green',
                  'domain': Domain('kt_item_ids', '!=', False) & ~lit['kt_open']},
                 {'value': 'none', 'label': _('No handover items'), 'tone': 'slate',
                  'domain': [('kt_item_ids', '=', False)]},
             ]},
            {'key': 'overdue', 'label': _('Steps overdue'), 'icon': 'clock',
             'group': 'other', 'type': 'choice', 'requires': ['task_ids'],
             'options': [
                 {'value': 'yes', 'label': _('A step is overdue'), 'tone': 'rose',
                  'domain': lit['overdue']},
                 {'value': 'no', 'label': _('Nothing overdue'), 'tone': 'green',
                  'domain': ~lit['overdue']},
             ]},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.country_id',
             'none_label': _('Not recorded')},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.parent_id',
             'none_label': _('Nobody named')},
            {'key': 'status', 'label': _('Checklist status'), 'icon': 'listChecks',
             'group': 'other', 'type': 'selection', 'path': 'state'},
            {'key': 'checklist', 'label': _('Checklist used'), 'icon': 'fileText',
             'group': 'other', 'type': 'many2one', 'path': 'template_id',
             'none_label': _('No checklist')},
            {'key': 'source', 'label': _('Started by'), 'icon': 'route',
             'group': 'other', 'type': 'selection', 'path': 'source'},
        ]

    def _pbf_builtin_views(self):
        glance = self._ex_glance_filters()
        return [
            {'key': 'all', 'label': _('All leaving'), 'icon': 'logOut', 'filters': {}},
            {'key': 'leaving', 'label': _('Leaving this month'), 'filters': glance['leaving']},
            {'key': 'gone', 'label': _('Last day has passed'), 'filters': glance['gone']},
            {'key': 'clearances', 'label': _('Clearances still open'),
             'filters': glance['clearances']},
            {'key': 'ready', 'label': _('Ready to settle'), 'filters': {'settlement': ['ready']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            # the board shows its own "looked after by the HR team" panel
            return {'refused': _("Exits are looked after by the HR team.")}
        return super().pbf_layout()

    @api.model
    def get_board_head(self):
        """The numbers line and the flags, counted over EVERYBODY leaving.
        The cards come from `get_board_page`, a page at a time."""
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'total': 0, 'glance_filters': {}, 'depts': []}
        Case = self.env['pb.journey.case']
        base = Domain(self._pbf_base_domain())
        today = self._pbf_today()
        ds = fields.Date.to_string
        facts = self._safe(lambda: self._ex_facts(), default=None)

        def count(dom):
            return self._safe(lambda: Case.search_count(base & Domain(dom)))

        kpis = {
            'leaving': count(Domain('anchor_date', '>=', ds(today))
                             & Domain('anchor_date', '<=', ds(today + timedelta(days=31)))),
            'gone': count(self._ex_gone()),
            'blocked': len(facts['held']) if facts else 0,
            'clearances': self._safe(lambda: self.env['pb.exit.clearance'].search_count([
                ('case_id', 'any', self._pbf_base_domain()),
                ('state', '=', 'pending')])),
            'assets': facts['item_count'] if facts else 0,
            'to_check': len(facts['to_check']) if facts else 0,
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'kpis': kpis,
            'total': self._safe(lambda: Case.search_count(base)),
            'glance_filters': self._ex_glance_filters(),
            'depts': [{'id': d, 'label': CLEARANCE_DEPT_LABEL[d]}
                      for d in CLEARANCE_ORDER],
        }

    @api.model
    def get_board_page(self, filters=None, search=None, sort=None, offset=0,
                       limit=PAGE_SIZE):
        """One page of cards for the panel's filters, plus — on the first
        page — the four step counts for those same filters (ruling R1)."""
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        Case = self._pbf_records()
        spec = self._pbf_clean_spec()
        domain = self.pbf_domain(filters or {}, search, spec=spec)
        cases = Case.search(domain, order=self.pbf_order(sort) or 'anchor_date, id',
                            offset=offset, limit=limit)
        today = date.today()
        rows = []
        for case in cases:
            try:
                rows.append(self._row(case, today))
            except Exception:           # noqa: BLE001 — one bad card never blanks the board
                _logger.exception('Exits row for case %s', case.id)
        out = {'rows': rows, 'total': Case.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._ex_step_counts(filters or {}, search, spec)
        return out

    @api.model
    def _ex_step_counts(self, filters, search, spec):
        """{step: {n, waiting}} for the panel's filters minus the step."""
        Case = self._pbf_records()
        dom = self.pbf_domain(filters, search, skip='step', spec=spec)
        pending = self._ex_literal()['pending']
        steps = {
            'notice': self._pbf_dm_step_notice(),
            'signoff': self._pbf_dm_step_signoff(),
            'ready': Domain(self._pbf_dm_ff_ready()),
            'settled': Domain(self._pbf_dm_ff_closed()),
        }
        out = {}
        for key, step_dom in steps.items():
            at = dom & step_dom
            out[key] = {
                'n': self._safe(lambda at=at: Case.search_count(at)),
                # the strip's flag: how many there wait for a desk to sign off
                'waiting': self._safe(lambda at=at: Case.search_count(at & pending)),
            }
        return out

    # -------------------------------------------------------------- one exit
    @api.model
    def get_exit(self, case_id):
        """The whole of one leaver — P0's case detail plus this phase's rows.

        The steps, check-ins and letters are read through `pb.journeys` rather
        than re-derived: two implementations of "what is on this checklist"
        would drift the first week one of them grew a column.
        """
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        detail = self.env['pb.journeys'].get_case(case.id)
        detail['leaver'] = self._row(case)
        # P0's task payload does not carry "does this step run itself" — the
        # mechanism is P3's and P0 predates it. Annotate here rather than
        # widening `pb.journeys`: without it the drawer offers "Run it now" on
        # a step a person has to do, and the server refuses it. An offer the
        # server would refuse is worse than no offer (W29).
        auto = {t.id: (t.is_automatic, t.automation_key or '')
                for t in case.task_ids}
        for row in detail.get('tasks') or []:
            is_auto, key = auto.get(row.get('id'), (False, ''))
            row['auto'] = bool(is_auto)
            row['auto_key'] = key
        detail['kt'] = [{
            'id': k.id,
            'topic': k.topic or '',
            'from': k.from_employee_id.name or '',
            'to': k.to_employee_id.name or '',
            'link': k.doc_link or '',
            'notes': k.notes or '',
            'state': k.state,
            'state_label': KT_STATE_LABEL.get(k.state, k.state or ''),
        } for k in case.kt_item_ids.sorted(key=lambda k: (k.sequence, k.id))]
        detail['assets'] = self._safe(
            lambda: self.env['pb.asset'].open_items_for(case.employee_id.id),
            default={'tangible': [], 'digital': [], 'total': 0})
        farewell = case.task_ids.filtered(
            lambda t: t.automation_key == 'farewell')[:1]
        detail['farewell'] = {
            'task_id': farewell.id if farewell else 0,
            'state': farewell.state if farewell else '',
            'due': str(farewell.due_date) if farewell and farewell.due_date
            else '',
            'draft': self._safe(lambda: farewell.farewell_draft(), default='')
            if farewell else '',
        } if farewell else None
        feedback = self.env['pb.feedback.request'].sudo().search(
            [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1)
        detail['feedback'] = {
            'id': feedback.id,
            'state': feedback.state,
            'window_end': str(feedback.window_end) if feedback.window_end
            else '',
            # The link is handed only to somebody who may WRITE — it is a
            # credential, and a credential on a read-only screen is a
            # credential in a screenshot.
            'link': self._safe(lambda: feedback._token_url(), default='')
            if self._can_write() else '',
            'answers': self._safe(lambda: _answers(feedback), default=[]),
        } if feedback else None
        return detail

    # --------------------------------------------------------- the row actions
    @api.model
    def clear_clearance(self, clearance_id, note=None, not_needed=False):
        """Sign one desk off. The MODEL decides who may — not this facade.

        `pb.exit.clearance.action_clear` admits the owner of the desk as well
        as the HR team, which is wider than `_require_write()` and deliberately
        so: an IT manager who is not in the lifecycle team still has to be able
        to say the laptop came back.
        """
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        row = self.env['pb.exit.clearance'].browse(
            int(clearance_id or 0)).exists()
        if not row:
            raise UserError(_("That clearance is no longer there."))
        if not_needed:
            return row.action_not_needed(note=note)
        return row.action_clear(note=note)

    @api.model
    def reopen_clearance(self, clearance_id):
        self._require_write()
        row = self.env['pb.exit.clearance'].browse(
            int(clearance_id or 0)).exists()
        if not row:
            raise UserError(_("That clearance is no longer there."))
        return row.action_reopen()

    @api.model
    def add_kt_item(self, case_id, topic, to_employee_id=None, doc_link=None):
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        topic = (topic or '').strip()
        if not topic:
            raise UserError(_("Say what is being handed over."))
        self.env['pb.kt.item'].create({
            'case_id': case.id,
            'topic': topic[:200],
            'from_employee_id': case.employee_id.id,
            'to_employee_id': int(to_employee_id) if to_employee_id else False,
            'doc_link': (doc_link or '').strip()[:400] or False,
            'company_id': (case.company_id or self.env.company).id,
        })
        return True

    @api.model
    def settle_kt_item(self, kt_id, done=True):
        self._require_write()
        row = self.env['pb.kt.item'].browse(int(kt_id or 0)).exists()
        if not row:
            raise UserError(_("That handover item is no longer there."))
        return row.action_done() if done else row.action_reopen()

    @api.model
    def nudge_kt(self, case_id):
        """Remind the people who owe a handover, now rather than on the 15th."""
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        if not case.kt_item_ids.filtered(lambda k: k.state != 'done'):
            raise UserError(_(
                "Everything on the handover list has been handed over — there "
                "is nobody left to remind."))
        if not case.send_kt_ping():
            raise UserError(_(
                "Nothing was sent. There may be no email address for the HR "
                "contact or for the people picking the work up."))
        return True

    @api.model
    def set_farewell_note(self, task_id, text):
        """HR's own wording for the farewell note, before the day it goes."""
        self._require_write()
        task = self.env['pb.journey.task'].browse(int(task_id or 0)).exists()
        if not task or task.automation_key != 'farewell':
            raise UserError(_("That is not the farewell step."))
        if task.state in ('done', 'skipped'):
            raise UserError(_(
                "The farewell note has already gone out, so the wording "
                "cannot be changed now."))
        task.sudo().write({'note': (text or '').strip()[:4000] or False})
        return True

    @api.model
    def run_step_now(self, task_id):
        """Run an automatic step today instead of waiting for its date."""
        self._require_write()
        task = self.env['pb.journey.task'].browse(int(task_id or 0)).exists()
        if not task:
            raise UserError(_("That step is no longer there."))
        if not task.is_automatic:
            raise UserError(_(
                "This step is for a person to do — there is nothing to run."))
        if not task.action_auto(force=True):
            raise UserError(_(
                "Nothing was sent. %s",
                task.auto_error or _(
                    "It may be waiting for something else — a settlement that "
                    "is not closed yet, a switch that is off in the settings, "
                    "or more people to write to than the cap allows. The log "
                    "says which.")))
        return True

    @api.model
    def send_exit_invite(self, case_id):
        """Send (or re-send) the exit questionnaire link."""
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("That leaving checklist is no longer there."))
        request = self.env['pb.feedback.request'].sudo().search(
            [('case_id', '=', case.id), ('kind', '=', 'exit')], limit=1)
        if not request:
            request = case.ensure_exit_feedback()
        if not request:
            raise UserError(_("The exit questionnaire could not be prepared."))
        if request.state == 'submitted':
            raise UserError(_("They have already answered it."))
        if not request.action_send():
            raise UserError(_(
                "There is no email address on this person's record to send "
                "it to."))
        return True

    @api.model
    def close_settlement(self, settlement_id):
        """The gate, from the board. The model raises the plain-English refusal."""
        self._require_write()
        settlement = self.env['hr.full.final.settlement'].browse(
            int(settlement_id or 0)).exists()
        if not settlement:
            raise UserError(_(
                "There is no final settlement for this person yet. Generate "
                "one first, then close it."))
        return settlement.action_pb_close()

    @api.model
    def send_settlement(self, settlement_id):
        """Send a checked settlement for approval, from the board."""
        self._require_write()
        settlement = self.env['hr.full.final.settlement'].browse(
            int(settlement_id or 0)).exists()
        if not settlement:
            raise UserError(_("There is no final settlement for this person yet."))
        return settlement.action_pb_send_for_approval()

    @api.model
    def run_automation(self):
        """The daily job, on demand. Managers only — it sends email."""
        self._require_write()
        return self.env['pb.journey.case'].run_offboarding_automation()

    # ------------------------------------------------------------- the doors
    @api.model
    def open_case_action(self, case_id):
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leaving checklist'),
            'res_model': 'pb.journey.case',
            'res_id': int(case_id or 0),
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    @api.model
    def open_settlement_action(self, employee_id):
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Final settlement'),
            'res_model': 'hr.full.final.settlement',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('employee_id', '=', int(employee_id or 0))],
            'context': {'search_default_employee_id': int(employee_id or 0)},
        }

    @api.model
    def open_resignation_action(self, resignation_id):
        if not self._can_read():
            raise AccessError(_("Exits are looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resignation'),
            'res_model': 'pb.resignation',
            'res_id': int(resignation_id or 0),
            'view_mode': 'form',
            'views': [[False, 'form']],
        }


def _answers(request):
    """The exit answers, paired with the question they answered.

    Anything unreadable answers with an empty list rather than raising: a
    broken answer set must not turn the board into an error page.
    """
    import json
    if not request or not request.answers_json:
        return []
    try:
        loaded = json.loads(request.answers_json) or {}
    except Exception:                   # noqa: BLE001
        return []
    out = []
    for key, item in loaded.items():
        if str(key).startswith('_'):
            continue
        value = (item or {}).get('value') if isinstance(item, dict) else item
        label = ((item or {}).get('label') if isinstance(item, dict)
                 else '') or key
        if value not in (None, '', False):
            out.append({'label': str(label), 'value': str(value)[:600]})
    return out


def _d(value):
    from datetime import datetime
    return datetime.strptime(value, '%Y-%m-%d').date()


def _when(days):
    """"in 3 days" / "today" / "left 12 days ago" — words, not arithmetic."""
    if days is None:
        return ''
    if days == 0:
        return _('last day is today')
    if days == 1:
        return _('last day is tomorrow')
    if days > 0:
        return _('leaves in %s days', days)
    if days == -1:
        return _('left yesterday')
    return _('left %s days ago', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
