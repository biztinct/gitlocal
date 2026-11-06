# -*- coding: utf-8 -*-
"""`pb.onboarding` — the New joiners lens's only server surface.

The shape `pb_people` established and every cockpit since has kept: an
`AbstractModel` facade, `@api.model` reads, every independent probe inside its
own `_safe()` so one failing metric answers zero instead of taking the screen
down, `self.env.companies` scoping on every search, a row cap, and no sudo in a
read.

The gate is SERVER-SIDE and it is the boundary — the lens gate in the hub config
is a visibility hint. A reader with no lifecycle group gets an EMPTY BOARD with
`allowed: false` rather than an access dialog, so the screen can say in words
what it is and who to ask.

It reuses P0's tiers deliberately. Onboarding is not a separate permission from
the rest of the lifecycle: the board answers "how is this joiner doing", which
is the same question the Journeys board answers about the same cases, and a
fourth ladder would be a group nobody knew to grant.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .newhire_pulse import SCORE_WORD
from .onboarding_common import (
    DAY_MARK_LABEL, GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, initials,
)

_logger = logging.getLogger(__name__)

#: One page of the board (the filter panel pages it; "Show N more" appends).
PAGE_SIZE = 60
#: A step that still has to be done.
OPEN_TASK_STATES = ('pending', 'in_progress', 'blocked')

#: A joiner is "new" for this long after their first day. Past it the journey
#: may still be running (a stray step nobody ticked) but the person is a
#: colleague, not a new joiner, and a board that says otherwise is wrong.
NEW_FOR_DAYS = 120


class PbOnboarding(models.AbstractModel):
    _name = 'pb.onboarding'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook New Joiners cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('New joiners metric failed: %s', e)
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
                "You can look at the new joiners, but changing one is for the "
                "HR team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def _scope(self):
        """Every live joining checklist in the reader's companies whose first
        day is at most NEW_FOR_DAYS behind us (or not set yet)."""
        co_ids = self.env.companies.ids or [self.env.company.id]
        floor = date.today() - timedelta(days=NEW_FOR_DAYS)
        return [
            ('company_id', 'in', co_ids),
            ('case_type', '=', 'onboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
            '|', ('anchor_date', '=', False), ('anchor_date', '>=', floor),
        ]

    @api.model
    def get_board(self):
        """The head of the board: access and the numbers line, counted over
        every joiner on the board (no longer over the 300 rows it held). The
        cards are paged by the filter panel through `get_joiners_page`
        (FILTER W1)."""
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'countries': [], 'departments': [],
                    'months': []}
        Case = self.env['pb.journey.case']
        scope = self._scope()
        today = date.today()
        week_end = today + timedelta(days=7)

        def count(extra):
            return self._safe(lambda: Case.search_count(scope + extra))

        kpis = {
            'joining': count([('anchor_date', '>=', today), ('anchor_date', '<=', week_end)]),
            'started': count([('anchor_date', '<=', today)]),
            'no_buddy': count([('employee_id.buddy_id', '=', False)]),
            # steps, not people: how many checklist steps are late
            'overdue': self._safe(lambda: self.env['pb.journey.task'].search_count([
                ('case_id', 'in', Case.search(scope).ids),
                ('state', 'in', OPEN_TASK_STATES), ('due_date', '<', today)])),
            'red': count(self._pbf_red_yes()),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'kpis': kpis,
            'total': self._safe(lambda: Case.search_count(scope)),
        }

    # ============================================================ filter panel
    # FILTER W1 (2026-10-31): the board used to hold 300 joiners and filter
    # them in the browser (search, month / department / country chips,
    # "Needs something"). Everything is now counted and paged on the server
    # for the panel's state (pb_filter_kit). The gate is the board's own: a
    # reader without lifecycle access gets the screen's explanation and the
    # panel stays out of the way.

    def _pbf_model(self):
        return 'pb.journey.case'

    def _pbf_screen(self):
        return 'joiners'

    def _pbf_base_domain(self):
        return self._scope()

    def _pbf_search_fields(self):
        return ['employee_id.name', 'employee_id.job_title', 'employee_id.job_id.name',
                'employee_id.department_id.name', 'employee_id.buddy_id.name',
                'employee_id.hrbp_user_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'first_day', 'label': _('Latest first day first'),
             'order': 'anchor_date desc nulls first, id desc'},
            {'key': 'first_day_asc', 'label': _('Earliest first day first'),
             'order': 'anchor_date asc nulls last, id desc'},
            {'key': 'progress', 'label': _('Least done first'), 'order': 'progress asc, id desc'},
            {'key': 'person', 'label': _('Person, A to Z'), 'order': 'employee_id, id desc'},
        ]

    @api.model
    def _overdue_domain(self):
        return [('task_ids', 'any', [('state', 'in', OPEN_TASK_STATES),
                                     ('due_date', '<', fields.Date.context_today(self))])]

    @api.model
    def _red_case_ids(self):
        """Joiners who said they are struggling on a check-in — a fact on
        `pb.newhire.pulse`, which has no link back from the case, so the panel
        reaches it through `domain_method` (ledger §3a)."""
        try:
            return self.env['pb.newhire.pulse'].search(
                [('red_flag', '=', True), ('case_id', '!=', False)]).mapped('case_id').ids
        except Exception as e:  # noqa: BLE001
            _logger.info('New joiners pulse probe failed: %s', e)
            return []

    def _pbf_red_yes(self):
        return [('id', 'in', self._red_case_ids())]

    def _pbf_red_no(self):
        return [('id', 'not in', self._red_case_ids())]

    @api.model
    def _step_domains(self):
        """Before the first day (or no first day yet) → settling in (started,
        checklist still open) → checklist done. Every joiner is at one."""
        today = fields.Date.context_today(self)
        return {
            'ready': ['|', ('anchor_date', '=', False), ('anchor_date', '>', today)],
            'settling': [('anchor_date', '<=', today), ('progress', '<', 100)],
            'done': [('anchor_date', '<=', today), ('progress', '>=', 100)],
        }

    def _pbf_spec(self):
        steps = self._step_domains()
        return [
            # ---- pinned: when, how far along, which team
            {'key': 'first_day', 'label': _('First day'), 'icon': 'calendar',
             # first days still to come matter as much as the ones behind
             # us: an explicit preset list (kit 1.2.0)
             'group': 'dates', 'type': 'date', 'path': 'anchor_date',
             'presets': ['next_7', 'next_30', 'this_week', 'this_month', 'last_month',
                         'last_90', 'none'],
             'pinned': True, 'none_label': _('No first day yet')},
            {'key': 'step', 'label': _('Where they are'), 'icon': 'route',
             'group': 'other', 'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'ready', 'label': _('Getting ready'), 'tone': 'blue',
                  'domain': steps['ready']},
                 {'value': 'settling', 'label': _('Settling in'), 'tone': 'amber',
                  'domain': steps['settling']},
                 {'value': 'done', 'label': _('Checklist done'), 'tone': 'green',
                  'domain': steps['done']},
             ]},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'pinned': True, 'none_label': _('No department')},
            # ---- more filters
            {'key': 'buddy', 'label': _('Buddy'), 'icon': 'smilePlus',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.buddy_id',
             'none_label': _('No buddy yet'),
             'help': _('The main buddy only: somebody standing in for a buddy '
                       'who is away is not counted here.')},
            {'key': 'hrbp', 'label': _('HR partner'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.hrbp_user_id',
             'none_label': _('Nobody yet')},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.country_id',
             'none_label': _('Not recorded')},
            {'key': 'checklist', 'label': _('Checklist used'), 'icon': 'listChecks',
             'group': 'other', 'type': 'many2one', 'path': 'template_id',
             'none_label': _('No checklist')},
            {'key': 'status', 'label': _('Status'), 'icon': 'activity',
             'group': 'other', 'type': 'selection', 'path': 'state'},
            {'key': 'source', 'label': _('Started by'), 'icon': 'plug',
             'group': 'other', 'type': 'selection', 'path': 'source'},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.parent_id',
             'none_label': _('No manager')},
            {'key': 'overdue', 'label': _('Running late'), 'icon': 'clock',
             'group': 'other', 'type': 'choice',
             'help': _('A joiner is late when one of their open checklist steps is '
                       'past its due date.'),
             'options': [
                 {'value': 'yes', 'label': _('Steps overdue'), 'tone': 'rose',
                  'domain': self._overdue_domain()},
                 {'value': 'no', 'label': _('On time'), 'tone': 'green',
                  'domain': ['!'] + self._overdue_domain()},
             ]},
            {'key': 'pulse', 'label': _('How they say it is going'), 'icon': 'messageSquare',
             'group': 'people', 'type': 'choice',
             'options': [
                 {'value': 'red', 'label': _('Said they are struggling'), 'tone': 'rose',
                  'domain_method': '_pbf_red_yes'},
                 {'value': 'fine', 'label': _('No warning sign'), 'tone': 'green',
                  'domain_method': '_pbf_red_no'},
             ]},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All new joiners'), 'icon': 'userPlus', 'filters': {}},
            {'key': 'week', 'label': _('Joining this week'),
             'filters': {'first_day': {'preset': 'next_7'}}},
            {'key': 'nobuddy', 'label': _('Still without a buddy'), 'filters': {'buddy': [False]}},
            {'key': 'late', 'label': _('Steps overdue'), 'filters': {'overdue': ['yes']}},
            {'key': 'settling', 'label': _('Started, checklist open'),
             'filters': {'step': ['settling']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': _("New joiners are looked after by the HR team.")}
        return super().pbf_layout()

    @api.model
    def _pbf_step_counts(self, filters, search):
        """The strip's counts for the panel's state — each step counted against
        every OTHER filter (the kit's rule) — and, per step, how many of those
        have a step overdue (the strip's rose flag)."""
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'step'), None)
        if not s:
            return {}
        Case = self.env['pb.journey.case']
        base = self.pbf_domain(filters or {}, search, skip='step', spec=spec)
        late = Domain(self._overdue_domain())
        out = {}
        for o in s['options']:
            d = Domain.AND([base, Domain(o['domain'])])
            out[o['value']] = {'n': Case.search_count(d),
                               'late': Case.search_count(Domain.AND([d, late]))}
        return out

    @api.model
    def get_joiners_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of joiners for the filter panel's current state, with the
        step strip's counts for the same state."""
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        Case = self.env['pb.journey.case']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'anchor_date desc, id desc'
        today = date.today()
        rows = []
        for case in Case.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(case, today))
            except Exception:  # noqa: BLE001 — one bad card never blanks the board
                _logger.exception('New joiners row for case %s', case.id)
        out = {'rows': rows, 'total': Case.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search), default={})
        return out

    @api.model
    def _row(self, case, today=None):
        today = today or date.today()
        emp = case.employee_id
        doj = case.anchor_date or self._safe(lambda: case._joining_date(),
                                             default=False)
        days = (doj - today).days if doj else None
        pulses = self._safe(lambda: self.env['pb.newhire.pulse'].search(
            [('case_id', '=', case.id)], order='due_date'),
            default=self.env['pb.newhire.pulse'].browse())
        answered = [p for p in pulses if p.state == 'answered']
        last = answered[-1] if answered else None
        batch = self._safe(
            lambda: self.env['pb.orientation.batch'].search(
                [('attendee_ids', 'in', emp.id),
                 ('state', '!=', 'cancelled')],
                order='batch_date', limit=1),
            default=self.env['pb.orientation.batch'].browse())
        buddy = emp._pb_buddy_now() if emp else None
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
            'doj': str(doj) if doj else '',
            'month': str(doj)[:7] if doj else '',
            'days': days,
            'when': _when(days),
            'progress': case.progress,
            'open_tasks': case.open_task_count,
            'overdue': case.overdue_task_count,
            'buddy': (buddy.name if buddy else ''),
            'buddy_id': buddy.id if buddy else 0,
            'buddy_temp': bool(emp.buddy_temp_id and buddy
                               and buddy.id == emp.buddy_temp_id.id),
            'hrbp': emp.hrbp_user_id.name if emp.hrbp_user_id else '',
            'hrbp_id': emp.hrbp_user_id.id if emp.hrbp_user_id else 0,
            'orientation': str(batch.batch_date) if batch else '',
            'complete': self._safe(lambda: emp.profile_complete_pct,
                                   default=0),
            'missing': self._safe(lambda: emp.profile_missing, default='')
            or '',
            'pulses': [{'mark': p.day_mark,
                        'mark_label': DAY_MARK_LABEL.get(p.day_mark, ''),
                        'state': p.state,
                        'score': p.score or '',
                        'word': SCORE_WORD.get(p.score or '', ''),
                        'red': p.red_flag} for p in pulses],
            'pulse_last': (SCORE_WORD.get(last.score or '', '')
                           if last else ''),
            'pulse_score': (last.score or '') if last else '',
            'pulse_red': bool([p for p in pulses if p.red_flag]),
        }

    # ------------------------------------------------------------- one joiner
    @api.model
    def get_joiner(self, case_id):
        """The whole of one joiner — the P0 case detail, plus our own columns.

        The steps, check-ins and letters are read through `pb.journeys` rather
        than re-derived: two implementations of "what is on this checklist"
        would drift the first week one of them grew a column.
        """
        if not self._can_read():
            raise AccessError(_(
                "New joiners are looked after by the HR team."))
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That joining checklist is no longer there."))
        detail = self.env['pb.journeys'].get_case(case.id)
        emp = case.employee_id
        detail['joiner'] = self._row(case)
        detail['buddy_card'] = emp._pb_buddy_now()._pb_card() \
            if (emp and emp._pb_buddy_now()) else None
        detail['hrbp_card'] = {
            'name': emp.hrbp_user_id.name,
            'email': emp.hrbp_user_id.email or '',
            'initials': initials(emp.hrbp_user_id.name),
        } if (emp and emp.hrbp_user_id) else None
        return detail

    # --------------------------------------------------------------- buddies
    @api.model
    def buddy_candidates(self, employee_id, term=None):
        if not self._can_read():
            return []
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            return []
        return self.env['pb.buddy.nomination'].suggest_candidates(
            emp, term=term)

    @api.model
    def buddy_choose(self, employee_id, candidate_id, case_id=None):
        self._require_write()
        nomination = self.env['pb.buddy.nomination'].open_for(
            employee_id, case_id)
        return nomination.choose(candidate_id)

    @api.model
    def buddy_temp(self, employee_id, temp_id, date_from=None, date_to=None):
        self._require_write()
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("That person could not be found."))
        return emp.set_temp_buddy(temp_id, date_from, date_to)

    # ------------------------------------------------------------- the doing
    @api.model
    def run_step_now(self, task_id):
        """Run an automatic step today instead of waiting for its date."""
        self._require_write()
        task = self.env['pb.journey.task'].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("That step is no longer there."))
        if not task.is_automatic:
            raise UserError(_(
                "This step is for a person to do — there is nothing to run."))
        if not task.action_auto(force=True):
            raise UserError(_(
                "Nothing was sent. %s",
                task.auto_error or _(
                    "There may be nobody to write to, or the step may be "
                    "switched off in the settings.")))
        return True

    @api.model
    def backfill_hrbp(self):
        self._require_write()
        return {'touched': self.env['pb.hrbp.rule'].backfill()}

    @api.model
    def run_automation(self):
        """The daily job, on demand. Managers only — it sends email."""
        self._require_write()
        return self.env['pb.journey.case'].run_onboarding_automation()

    # ------------------------------------------------------------ the pieces
    @api.model
    def get_settings(self):
        """What the cog shows: the sessions and the HR partner rules."""
        if not self._can_read():
            return {'allowed': False, 'batches': [], 'rules': []}
        co_ids = self.env.companies.ids or [self.env.company.id]
        Batch = self.env['pb.orientation.batch']
        Rule = self.env['pb.hrbp.rule']
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'batches': self._safe(lambda: [
                {'id': b.id, 'date': str(b.batch_date),
                 'state': b.state, 'people': b.attendee_count,
                 'location': b.location or ''}
                for b in Batch.search(
                    [('company_id', 'in', co_ids)],
                    order='batch_date desc', limit=24)], default=[]),
            'rules': self._safe(lambda: [
                {'id': r.id, 'name': r.name,
                 'country': r.country_id.name or '',
                 'dept': r.department_id.name or '',
                 'who': r.hrbp_user_id.name or ''}
                for r in Rule.search(
                    ['|', ('company_id', '=', False),
                     ('company_id', 'in', co_ids)],
                    order='sequence, id')], default=[]),
        }


def _when(days):
    """"in 3 days" / "today" / "12 days in" — words, not arithmetic."""
    if days is None:
        return ''
    if days == 0:
        return _('starts today')
    if days == 1:
        return _('starts tomorrow')
    if days > 0:
        return _('starts in %s days', days)
    if days == -1:
        return _('1 day in')
    return _('%s days in', -days)
