# -*- coding: utf-8 -*-
"""`pb.journeys` — the Journeys cockpit's only server surface.

An AbstractModel facade in the shape `pb_people` established: `@api.model`
reads, every independent probe inside its own `_safe()` so one failing metric
answers zero instead of taking the screen down, `self.env.companies` scoping on
every search, a row cap, and no sudo anywhere in a read.

Gating is SERVER-SIDE and it is the boundary. The lens gate in the hub config is
a visibility hint; this is what actually refuses. A reader with no lifecycle
group gets an EMPTY BOARD with `allowed: false` rather than an access dialog —
the screen then says, in words, what they are looking at and who to ask.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import AccessError, UserError

from .checkin import CHECKIN_KIND_LABEL
from .lifecycle_common import (
    ASSIGNEE_RULE_LABEL, CASE_STATE_LABEL, CASE_TYPES, CASE_TYPE_LABEL,
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, STEP_KINDS, STEP_KIND_LABEL,
    TASK_STATE_LABEL,
)

_logger = logging.getLogger(__name__)

#: One page of the board (the filter panel pages it; "Show N more" appends).
PAGE_SIZE = 60
TASK_LIMIT = 300
#: A step that still has to be done.
OPEN_TASK_STATES = ('pending', 'in_progress', 'blocked')
LIVE_STATES = ('draft', 'active', 'on_hold')


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?')
            + (parts[-1][0] if len(parts) > 1 else '')).upper()


class PbJourneys(models.AbstractModel):
    _name = 'pb.journeys'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Journeys cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('Journeys cockpit metric failed: %s', e)
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
                "You can look at journeys, but changing one is for the "
                "lifecycle team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        """The head of the board: who may do what, the numbers line, and the
        types/checklists the start dialog offers. The cards themselves are
        paged by the filter panel through `get_journeys_page` (FILTER W1)."""
        if not self._can_read():
            return {
                'allowed': False, 'can_write': False, 'can_admin': False,
                'kpis': {}, 'rows': [], 'types': self._type_options(),
                'templates': [], 'states': [],
            }
        Case = self.env['pb.journey.case']
        Task = self.env['pb.journey.task']
        co_ids = self.env.companies.ids or [self.env.company.id]
        CO = [('company_id', 'in', co_ids)]
        today = date.today()
        month_start = today.replace(day=1)

        live = CO + [('state', 'in', LIVE_STATES)]
        kpis = {
            'active': self._safe(
                lambda: Case.search_count(CO + [('state', '=', 'active')])),
            'overdue': self._safe(lambda: Task.search_count(CO + [
                ('state', 'in', ('pending', 'in_progress', 'blocked')),
                ('due_date', '<', today),
                ('case_id.state', '=', 'active')])),
            'due_week': self._safe(lambda: Task.search_count(CO + [
                ('state', 'in', ('pending', 'in_progress', 'blocked')),
                ('due_date', '>=', today),
                ('due_date', '<=', today + timedelta(days=7)),
                ('case_id.state', '=', 'active')])),
            'red_flags': self._safe(
                lambda: self.env['pb.employee.checkin'].search_count(CO + [
                    ('red_flag', '=', True),
                    ('state', '!=', 'cancelled')])),
            'letters_month': self._safe(
                lambda: self.env['pb.hr.letter'].search_count(CO + [
                    ('generated_at', '>=', month_start.strftime(
                        '%Y-%m-%d 00:00:00'))])),
        }

        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_admin': self.env.user.has_group(GROUP_ADMIN)
            or self.env.user._is_admin(),
            'kpis': kpis,
            # every live journey, whatever is filtered (the "no journeys
            # yet" state reads it)
            'total': self._safe(lambda: Case.search_count(live)),
            'types': self._type_options(),
            'states': [{'id': k, 'label': v}
                       for k, v in CASE_STATE_LABEL.items()
                       if k in ('draft', 'active', 'on_hold')],
            'templates': self._safe(lambda: [
                {'id': t.id, 'name': t.name, 'case_type': t.case_type,
                 'steps': t.step_count}
                for t in self.env['pb.journey.template'].search(
                    [('company_id', 'in', co_ids + [False])],
                    order='sequence, id')], default=[]),
        }

    @api.model
    def _type_options(self):
        return [{'id': k, 'label': v} for k, v in CASE_TYPES]

    @api.model
    def _case_row(self, case, today=None):
        today = today or date.today()
        emp = case.employee_id
        return {
            'id': case.id,
            'employee_id': emp.id,
            'employee': emp.name or '—',
            'initials': _initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id
            if emp else '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': emp.department_id.name if emp.department_id else '',
            'type': case.case_type,
            'type_label': CASE_TYPE_LABEL.get(case.case_type,
                                              case.case_type or ''),
            'state': case.state,
            'state_label': CASE_STATE_LABEL.get(case.state, case.state or ''),
            'progress': case.progress,
            'task_count': case.task_count,
            'open_tasks': case.open_task_count,
            'overdue': case.overdue_task_count,
            'red_flags': case.red_flag_count,
            'next_due': str(case.next_due_date) if case.next_due_date else '',
            'anchor_date': str(case.anchor_date) if case.anchor_date else '',
            'late': bool(case.next_due_date and case.next_due_date < today),
        }

    # ============================================================ filter panel
    # FILTER W1 (2026-10-31): the board used to load the newest 400 journeys
    # and filter them in the browser. Everything is now counted and paged on
    # the server for the panel's state (pb_filter_kit). The gate is the same
    # one `get_board` applies: a reader without lifecycle access gets the
    # screen's own explanation and the panel stays out of the way.

    def _pbf_model(self):
        return 'pb.journey.case'

    def _pbf_screen(self):
        return 'journeys'

    def _pbf_base_domain(self):
        co_ids = self.env.companies.ids or [self.env.company.id]
        return [('company_id', 'in', co_ids), ('state', 'in', LIVE_STATES)]

    def _pbf_search_fields(self):
        return ['employee_id.name', 'employee_id.job_title', 'employee_id.job_id.name',
                'employee_id.department_id.name', 'template_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'key_date', 'label': _('Latest key date first'),
             'order': 'anchor_date desc nulls last, id desc'},
            {'key': 'key_date_asc', 'label': _('Earliest key date first'),
             'order': 'anchor_date asc nulls last, id desc'},
            {'key': 'opened', 'label': _('Opened most recently'),
             'order': 'date_opened desc nulls last, id desc'},
            {'key': 'progress', 'label': _('Least done first'), 'order': 'progress asc, id desc'},
            {'key': 'person', 'label': _('Person, A to Z'), 'order': 'employee_id, id desc'},
        ]

    @api.model
    def _late_domain(self):
        return [('task_ids', 'any', [('state', 'in', OPEN_TASK_STATES),
                                     ('due_date', '<', fields.Date.context_today(self))])]

    @api.model
    def _step_domains(self):
        """Where a journey is. Not started (draft) → under way (running or on
        hold with steps still open) → nothing left to do (running, every step
        settled). Every live journey is at exactly one."""
        has_open = ('task_ids', 'any', [('state', 'in', OPEN_TASK_STATES)])
        return {
            'start': [('state', '=', 'draft')],
            'running': ['|', ('state', '=', 'on_hold'), '&', ('state', '=', 'active'), has_open],
            'wrap': [('state', '=', 'active'), '!', has_open],
        }

    def _pbf_spec(self):
        steps = self._step_domains()
        return [
            # ---- pinned: what kind, how far, whose team
            {'key': 'type', 'label': _('Journey type'), 'icon': 'route',
             'group': 'other', 'type': 'selection', 'path': 'case_type', 'pinned': True},
            {'key': 'status', 'label': _('Status'), 'icon': 'activity',
             'group': 'other', 'type': 'selection', 'path': 'state', 'pinned': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'pinned': True, 'none_label': _('No department')},
            # ---- more filters
            {'key': 'step', 'label': _('Where it is'), 'icon': 'workflow',
             'group': 'other', 'type': 'choice',
             'help': _('The steps above the board.'),
             'options': [
                 {'value': 'start', 'label': _('Not started'), 'tone': 'slate',
                  'domain': steps['start']},
                 {'value': 'running', 'label': _('Under way'), 'tone': 'blue',
                  'domain': steps['running']},
                 {'value': 'wrap', 'label': _('Nothing left to do'), 'tone': 'green',
                  'domain': steps['wrap']},
             ]},
            {'key': 'late', 'label': _('Running late'), 'icon': 'clock',
             'group': 'other', 'type': 'choice',
             'help': _('A journey is late when one of its open steps is past its due date.'),
             'options': [
                 {'value': 'yes', 'label': _('Steps overdue'), 'tone': 'rose',
                  'domain': self._late_domain()},
                 {'value': 'no', 'label': _('On time'), 'tone': 'green',
                  'domain': ['!'] + self._late_domain()},
             ]},
            {'key': 'key_date', 'label': _('Key date'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'anchor_date', 'presets': 'past',
             'help': _('The joining date, the last working day or the probation end.'),
             'none_label': _('No key date')},
            {'key': 'checklist', 'label': _('Checklist used'), 'icon': 'listChecks',
             'group': 'other', 'type': 'many2one', 'path': 'template_id',
             'none_label': _('No checklist')},
            {'key': 'source', 'label': _('Started by'), 'icon': 'plug',
             'group': 'other', 'type': 'selection', 'path': 'source'},
            {'key': 'progress', 'label': _('Done (%)'), 'icon': 'gauge',
             'group': 'other', 'type': 'number', 'path': 'progress'},
            {'key': 'opened', 'label': _('Opened on'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'date_opened', 'presets': 'past',
             'none_label': _('Not recorded')},
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'work', 'type': 'many2one', 'path': 'employee_id.job_id',
             'none_label': _('No job position')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All journeys'), 'icon': 'route', 'filters': {}},
            {'key': 'running', 'label': _('Running now'), 'filters': {'status': ['active']}},
            {'key': 'late', 'label': _('Steps overdue'), 'filters': {'late': ['yes']}},
            {'key': 'start', 'label': _('Not started'), 'filters': {'status': ['draft']}},
            {'key': 'wrap', 'label': _('Nothing left to do'), 'filters': {'step': ['wrap']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': _("Journeys are looked after by the HR team.")}
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
        late = Domain(self._late_domain())
        out = {}
        for o in s['options']:
            d = Domain.AND([base, Domain(o['domain'])])
            out[o['value']] = {'n': Case.search_count(d),
                               'late': Case.search_count(Domain.AND([d, late]))}
        return out

    @api.model
    def get_journeys_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of the board for the filter panel's current state, with the
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
                rows.append(self._case_row(case, today))
            except Exception:  # noqa: BLE001 — one bad card never blanks the board
                _logger.exception('Journeys board row for case %s', case.id)
        out = {'rows': rows, 'total': Case.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search), default={})
        return out

    # -------------------------------------------------------------- one case
    @api.model
    def get_case(self, case_id):
        if not self._can_read():
            raise AccessError(_(
                "Journeys are for the lifecycle team. Ask them for access."))
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That journey is no longer there."))
        today = date.today()
        can_write = self._can_write()
        tasks = []
        for task in case.task_ids.sorted(
                key=lambda t: (t.due_date or date.max, t.sequence, t.id))[
                :TASK_LIMIT]:
            link = ''
            if can_write:
                link = self._safe(lambda t=task: t._token_url(), default='')
            tasks.append({
                'id': task.id,
                'name': task.name,
                'description': task.description or '',
                'kind': task.step_kind or 'task',
                'kind_label': STEP_KIND_LABEL.get(task.step_kind, ''),
                'rule': task.assignee_rule or '',
                'rule_label': ASSIGNEE_RULE_LABEL.get(task.assignee_rule, ''),
                'assignee': task.assignee_user_id.name or '',
                'assignee_id': task.assignee_user_id.id or 0,
                'due': str(task.due_date) if task.due_date else '',
                'overdue': bool(task.due_date and task.due_date < today
                                and task.state in ('pending', 'in_progress',
                                                   'blocked')),
                'state': task.state,
                'state_label': TASK_STATE_LABEL.get(task.state, task.state),
                'blocking': task.blocking_ff,
                'escalated': task.escalated,
                'link': link,
                'note': task.note or '',
                'done_by': task.done_by.name or '',
                'done_at': str(task.done_at)[:16] if task.done_at else '',
            })
        checkins = [{
            'id': c.id,
            'kind': c.kind,
            'kind_label': CHECKIN_KIND_LABEL.get(c.kind, c.kind or ''),
            'owner': c.owner_user_id.name or '',
            'date': str(c.scheduled_date) if c.scheduled_date else '',
            'state': c.state,
            'red_flag': c.red_flag,
            'red_flag_note': c.red_flag_note or '',
            'notes': c.notes or '',
        } for c in case.checkin_ids.sorted(
            key=lambda c: (c.scheduled_date or date.min))]
        letters = [{
            'id': lt.id,
            'name': lt.subject or lt.name,
            'state': lt.state,
            'attachment_id': lt.attachment_id.id or 0,
        } for lt in case.letter_ids]
        return {
            'case': self._case_row(case, today),
            'note': case.note or '',
            'template': case.template_id.name or '',
            'source': case.source,
            'opened': str(case.date_opened) if case.date_opened else '',
            'closed': str(case.date_closed) if case.date_closed else '',
            'tasks': tasks,
            'checkins': checkins,
            'letters': letters,
            'can_write': can_write,
        }

    # --------------------------------------------------------------- actions
    @api.model
    def open_case(self, employee_id, case_type, template_id=None,
                  anchor_date=None):
        self._require_write()
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("Pick a person first."))
        if case_type not in dict(CASE_TYPES):
            raise UserError(_("That is not a journey type we know."))
        Template = self.env['pb.journey.template']
        template = (Template.browse(int(template_id)).exists()
                    if template_id else Template.browse())
        if not template:
            template = Template.pick_for(
                case_type,
                country_id=self.env['pb.journey.case']._employee_country(emp),
                company_id=(emp.company_id or self.env.company).id)
        case = self.env['pb.journey.case'].create({
            'employee_id': emp.id,
            'case_type': case_type,
            'template_id': template.id or False,
            'anchor_date': anchor_date or False,
            'company_id': (emp.company_id or self.env.company).id,
            'source': 'manual',
        })
        case.action_open()
        return {'case_id': case.id, 'steps': len(case.task_ids),
                'template': template.name or ''}

    @api.model
    def task_done(self, task_id):
        self._require_write()
        self._task(task_id).action_done()
        return True

    @api.model
    def task_skip(self, task_id, reason=None):
        self._require_write()
        self._task(task_id).action_skip(reason)
        return True

    @api.model
    def task_reassign(self, task_id, user_id):
        self._require_write()
        self._task(task_id).action_reassign(user_id)
        return True

    @api.model
    def task_reopen(self, task_id):
        self._require_write()
        task = self._task(task_id)
        task.write({'state': 'pending', 'done_at': False, 'done_by': False})
        return True

    @api.model
    def _task(self, task_id):
        task = self.env['pb.journey.task'].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("That step is no longer there."))
        return task

    @api.model
    def add_task(self, case_id, vals):
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That journey is no longer there."))
        vals = vals or {}
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the step a name."))
        kind = vals.get('step_kind')
        self.env['pb.journey.task'].create({
            'case_id': case.id,
            'name': name,
            'description': vals.get('description') or False,
            'due_date': vals.get('due_date') or False,
            'assignee_user_id': int(vals['assignee_user_id'])
            if vals.get('assignee_user_id') else False,
            'step_kind': kind if kind in dict(STEP_KINDS) else 'task',
            'blocking_ff': bool(vals.get('blocking_ff')),
            'sequence': 900,
            'company_id': case.company_id.id or self.env.company.id,
        })
        return True

    @api.model
    def case_action(self, case_id, verb):
        self._require_write()
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That journey is no longer there."))
        verbs = {'done': case.action_done, 'cancel': case.action_cancel,
                 'hold': case.action_hold, 'resume': case.action_resume}
        if verb not in verbs:
            raise UserError(_("That is not something a journey can do."))
        verbs[verb]()
        return True

    # ------------------------------------------------------------- lookups
    @api.model
    def search_employees(self, term, limit=12):
        if not self._can_read():
            return []
        Emp = self.env['hr.employee']
        co_ids = self.env.companies.ids or [self.env.company.id]
        domain = [('company_id', 'in', co_ids), ('active', '=', True)]
        found = self._safe(
            lambda: Emp.search(
                domain + ([('name', 'ilike', term)] if term else []),
                order='name', limit=int(limit)),
            default=Emp.browse())
        return [{'id': e.id, 'name': e.name or '—',
                 'job': e.job_title or (e.job_id.name if e.job_id else '')
                 or '',
                 'dept': e.department_id.name if e.department_id else '',
                 'initials': _initials(e.name)} for e in found]

    @api.model
    def search_users(self, term, limit=12):
        if not self._can_read():
            return []
        Users = self.env['res.users']
        found = self._safe(
            lambda: Users.search(
                [('share', '=', False)]
                + ([('name', 'ilike', term)] if term else []),
                order='name', limit=int(limit)),
            default=Users.browse())
        return [{'id': u.id, 'name': u.name} for u in found]
