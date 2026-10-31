# -*- coding: utf-8 -*-
"""FILTER wave 3 — the four Hiring lists on the shared filter panel.

Roles, Interviews, the Applicants register and the Offers register used to
read a capped window (300 / 300 / 600 / 200 rows) and filter it in the
browser, so a select said "any recruiter" over the newest 300 and every chip
count was a count of what happened to be loaded. They now sit on
`pb_filter_kit`: the panel's sections, counts and views are worked out here,
over EVERY record the reader may see, and each list is served a page at a
time for the panel's state.

ONE FACADE, FOUR RECORD TYPES. `pb.hiring` gets the mixin once; the browser's
kit carries `context.pbf_ctx = {'kind': ...}` on every call and every hook
below reads it (`_pbf_kind`) to pick the model, the sections, the views and
the saved-views key (`hiring:<kind>`, so a view saved on Offers never shows
on Roles).

WHO SEES WHAT IS UNCHANGED, and that is the rule this file is built around
("counts never wider than the screen today"):

  * Roles are searched as the reader (record rules). A stand-in covering a
    recruiter reads as the system with the recruiter clause written into the
    base domain — `pb_hiring_a3.get_board`'s own doctrine.
  * Interviews: as the reader; a stand-in as the system, limited to the roles
    of the recruiters they cover (narrower than the old board, never wider).
  * Applicants: read as the system (as `get_applicants` always did), the
    base being the jobs of the roles the reader may see. Sections and search
    paths that would reveal what the privacy mask blanks on a card (email,
    source, first look, flags…) are offered to the hiring team only.
  * Offers: as the reader. Papers, the background check and money are the
    hiring team's only, as on the rows.

The old reads (`get_board`, `get_applicants`, `get_offers`) stay as they were
for every other caller (ruling R4); the Overview's offer figures now count
through the same domains as the Offers views (`_pbf_offer_kpi_counts`), so a
figure and the view it opens can never disagree.
"""

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.fields import Domain

from .registers_p9 import FAMILY_DOMAINS, OFFER_STEPS

_logger = logging.getLogger(__name__)

KINDS = ('roles', 'interviews', 'applicants', 'offers')
MODELS = {
    'roles': 'pb.hiring.requisition',
    'interviews': 'pb.hiring.interview',
    'applicants': 'hr.applicant',
    'offers': 'pb.hiring.offer',
}
#: Rows per page. A board of cards takes a bigger page than a list.
PAGE = {'roles': 60, 'interviews': 60, 'applicants': 120, 'offers': 60}
PAGE_MAX = 240
#: The Interviews list keeps the board's window: six weeks back, plus any
#: round whose opinions are still being waited for.
IV_WINDOW_DAYS = 42
#: "Joining soon" — the register's own window.
JOINING_DAYS = 30


class PbHiringFilters(models.AbstractModel):
    _name = 'pb.hiring'
    _inherit = ['pb.hiring', 'pb.filter.mixin']

    # =====================================================================
    #  Small helpers
    # =====================================================================
    @api.model
    def _pbf_memo(self, key, fn):
        """One answer per request: the kit asks for the base domain once per
        section it counts, and the Applicants base walks every role."""
        store = getattr(self.env.cr, 'cache', None)
        if store is None:
            return fn()
        bucket = store.setdefault('pb_hiring_pbf', {})
        k = (self.env.uid, tuple(self.env.companies.ids), key)
        if k not in bucket:
            bucket[k] = fn()
        return bucket[k]

    @api.model
    def _pbf_kind(self):
        kind = self._pbf_ctx().get('kind')
        return kind if kind in KINDS else 'roles'

    @api.model
    def _pbf_for(self, kind):
        """This facade, pointed at one of the four lists."""
        return self.with_context(pbf_ctx={'kind': kind})

    @api.model
    def _pbf_co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _pbf_covered(self):
        """The recruiters a stand-in covers (empty for the hiring team)."""
        return self._pbf_memo('covered', lambda: list(
            self._safe(lambda: self._cover_scope(), default=[]) or []))

    @api.model
    def _pbf_team(self):
        """Does this reader see what the privacy mask hides from others: the
        hiring team, or a stand-in (whose every role is a covered one)."""
        return self._pbf_memo('team', lambda: bool(
            self._hiring_group() or self._pbf_covered()))

    @api.model
    def _pbf_people_readable(self):
        """hr.employee names (hiring manager, reporting manager) only for a
        reader who may read employees, or one reading as the system."""
        if self._pbf_kind() == 'roles' and self._pbf_covered():
            return True
        try:
            return bool(self.env['hr.employee'].has_access('read'))
        except Exception:  # noqa: BLE001
            return False

    @api.model
    def _pbf_local_midnight(self, day):
        """The reader's midnight on `day`, as the naive UTC the database keeps."""
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:  # noqa: BLE001
            tz = pytz.UTC
        local = tz.localize(datetime.combine(day, time.min))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def _pbf_mine_ids(self, model, states=None):
        """Records of `model` whose open sign-off seat is THIS reader's.

        One query finds every open seat the reader acts on; the handful of
        records behind them are then asked the engine's own question
        (`_chain_my_seat`), so this answer is exactly the row's `waiting_mine`
        and never a second opinion of it."""
        def find():
            Seat = self.env['biz.approval.request.seat'].sudo()
            seats = Seat.search([
                ('status', '=', 'open'),
                ('acting_user_id', '=', self.env.uid),
                ('step_id.status', '=', 'active'),
                ('request_id.state', 'in', ('pending', 'blocked')),
                ('request_id.res_model', '=', model),
            ])
            res_ids = {s.request_id.res_id for s in seats if s.request_id.res_id}
            if not res_ids:
                return []
            recs = self.env[model].sudo().browse(list(res_ids)).exists()
            if states:
                recs = recs.filtered(lambda r: r.state in states)
            return [r.id for r in recs if r._chain_my_seat()]
        return self._pbf_memo(('mine', model), lambda: self._safe(find, default=[]))

    @api.model
    def _pbf_roles_mine(self):
        return [('id', 'in', self._pbf_mine_ids('pb.hiring.requisition'))]

    @api.model
    def _pbf_offers_mine(self):
        return [('id', 'in', self._pbf_mine_ids(
            'pb.hiring.offer', states=('submitted', 'manager_ok')))]

    @api.model
    def _pbf_app_jobs(self):
        """{job id: role id} — the newest role on the reader's board that names
        each job (the register's own `by_job` rule)."""
        def build():
            out = {}
            for req in self._p9_roles():
                if req.job_id and req.job_id.id not in out:
                    out[req.job_id.id] = req.id
            return out
        return self._pbf_memo('app_jobs', build)

    # =====================================================================
    #  The mixin's hooks, switched by kind
    # =====================================================================
    def _pbf_model(self):
        return MODELS[self._pbf_kind()]

    def _pbf_screen(self):
        return 'hiring:%s' % self._pbf_kind()

    def _pbf_records(self):
        kind = self._pbf_kind()
        Rec = self.env[MODELS[kind]]
        if kind == 'applicants':
            return Rec.sudo().with_context(active_test=False)
        if kind in ('roles', 'interviews') and self._pbf_covered():
            return Rec.sudo()
        return Rec

    def _pbf_base_domain(self):
        kind = self._pbf_kind()
        co = self._pbf_co_ids()
        covered = self._pbf_covered()
        if kind == 'roles':
            dom = [('company_id', 'in', co)]
            if covered:
                dom.append(('recruiter_id', 'in', covered))
            return dom
        if kind == 'interviews':
            since = fields.Datetime.now() - timedelta(days=IV_WINDOW_DAYS)
            dom = [('company_id', 'in', co), '|', ('start', '>=', since),
                   '&', ('state', 'in', ('scheduled', 'done')),
                   ('feedback_ids.state', '=', 'pending')]
            if covered:
                dom = ['&', ('requisition_id.recruiter_id', 'in', covered)] + dom
            return dom
        if kind == 'applicants':
            return [('job_id', 'in', list(self._pbf_app_jobs()) or [0])]
        return [('company_id', 'in', co)]

    def _pbf_search_fields(self):
        kind = self._pbf_kind()
        if kind == 'roles':
            return ['title', 'name', 'department_id.name', 'location',
                    'recruiter_id.name', 'requested_by_user_id.name']
        if kind == 'interviews':
            return ['candidate_name', 'requisition_id.title', 'recruiter_id.name']
        if kind == 'applicants':
            paths = ['partner_name', 'pb_requisition_id.title', 'job_id.name']
            if self._pbf_team():
                paths.append('email_from')
            return paths
        return ['candidate_name', 'name', 'job_title', 'requisition_id.title',
                'requisition_id.recruiter_id.name']

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_sorts(self):
        kind = self._pbf_kind()
        if kind == 'roles':
            return [
                # THE ORDER IS THE HERO (hiring_board.js): problem first. Not
                # an SQL order — `get_roles_page` walks the tiers itself.
                {'key': 'attention', 'label': _('What needs you first'), 'order': 'id desc'},
                {'key': 'newest', 'label': _('Newest first'), 'order': 'id desc'},
                {'key': 'longest', 'label': _('Open the longest'),
                 'order': 'opened_on asc nulls last, id asc'},
                {'key': 'wanted', 'label': _('Wanted soonest'),
                 'order': 'target_start_date asc nulls last, id desc'},
                {'key': 'title', 'label': _('Role, A to Z'), 'order': 'title asc, id desc'},
            ]
        if kind == 'interviews':
            return [
                {'key': 'soonest', 'label': _('Earliest first'), 'order': 'start asc, id asc'},
                {'key': 'latest', 'label': _('Latest first'), 'order': 'start desc, id desc'},
                {'key': 'name', 'label': _('Candidate, A to Z'), 'order': 'candidate_name asc, start asc'},
            ]
        if kind == 'applicants':
            return [
                {'key': 'moved', 'label': _('Moved most recently'),
                 'order': 'date_last_stage_update desc, id desc'},
                {'key': 'stuck', 'label': _('Longest in their stage'),
                 'order': 'date_last_stage_update asc, id asc'},
                {'key': 'applied', 'label': _('Applied most recently'),
                 'order': 'create_date desc, id desc'},
                {'key': 'applied_old', 'label': _('Applied longest ago'),
                 'order': 'create_date asc, id asc'},
                {'key': 'name', 'label': _('Name, A to Z'), 'order': 'partner_name asc, id desc'},
                {'key': 'name_desc', 'label': _('Name, Z to A'), 'order': 'partner_name desc, id desc'},
            ]
        return [
            {'key': 'newest', 'label': _('Newest first'), 'order': 'id desc'},
            {'key': 'joining', 'label': _('Joining soonest'),
             'order': 'expected_join_date asc nulls last, start_date asc, id desc'},
            {'key': 'name', 'label': _('Candidate, A to Z'), 'order': 'candidate_name asc, id desc'},
        ]

    def _pbf_spec(self):
        kind = self._pbf_kind()
        return getattr(self, '_pbf_spec_%s' % kind)()

    def _pbf_builtin_views(self):
        kind = self._pbf_kind()
        return getattr(self, '_pbf_views_%s' % kind)()

    # =====================================================================
    #  The gate: the kit's calls answer exactly who the board answers
    # =====================================================================
    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': _("Hiring is looked after by the hiring team.")}
        return super().pbf_layout()

    @api.model
    def pbf_counts(self, filters=None, search=None, keys=None):
        if not self._can_read():
            return {'sections': {}, 'matched': 0}
        return super().pbf_counts(filters=filters, search=search, keys=keys)

    @api.model
    def pbf_find_values(self, key, query, filters=None, search=None):
        if not self._can_read():
            return []
        return super().pbf_find_values(key, query, filters=filters, search=search)

    # =====================================================================
    #  ROLES
    # =====================================================================
    @api.model
    def _pbf_roles_with_people(self):
        """'Has candidates' exactly as the row counts them (`_pipeline`: an
        active applicant in a stage, on the role's job), read as the system —
        a line manager reading their own roles may not read applicants, and a
        domain through `applicant_ids` would then fail for them."""
        def find():
            groups = self.env['hr.applicant'].sudo()._read_group(
                [('job_id', '!=', False), ('active', '=', True), ('stage_id', '!=', False)],
                ['job_id'], ['__count'])
            return [job.id for job, _n in groups if job]
        return Domain('job_id', 'in', self._pbf_memo('jobs_with_people', find) or [0])

    @api.model
    def _pbf_role_steps(self):
        """The four steps of the strip as domains — `stageOf` in
        hiring_board.js, written once for the server. A role is at exactly
        one, so the counts add up."""
        people = self._pbf_roles_with_people()
        reaching = Domain.OR([Domain('published', '=', True),
                              Domain('referral_open', '=', True), people])
        is_open = Domain('state', '=', 'open')
        return [
            ('setup', _('Set up'), 'slate', [('state', '=', 'setup')]),
            ('publish', _('Prepare & publish'), 'blue', Domain.AND([is_open, ~reaching])),
            ('recruit', _('Meet your candidates'), 'amber', Domain.AND([is_open, reaching])),
            ('joined', _('Welcome aboard'), 'green', [('state', '=', 'filled')]),
        ]

    def _pbf_spec_roles(self):
        team = self._pbf_team()
        live = [('state', 'in', ('setup', 'open'))]
        attention = [
            {'value': 'mine', 'label': _('Waiting on you'), 'tone': 'amber',
             'domain_method': '_pbf_roles_mine'},
            {'value': 'signoff', 'label': _('Waiting for a sign-off'), 'tone': 'blue',
             'domain': [('request_state', 'in', ('sent_in', 'hr_ok'))]},
            {'value': 'norecruiter', 'label': _('Nobody recruiting it'), 'tone': 'rose',
             'domain': live + [('recruiter_id', '=', False)]},
        ]
        if team:
            attention.append({'value': 'over', 'label': _('Over budget'), 'tone': 'rose',
                              'domain': live + [('budget_status', '=', 'over'),
                                                ('request_state', '!=', 'agreed')]})
        spec = [
            # ---- pinned: where it is, what state it is in, whose it is
            {'key': 'step', 'label': _('Where it is'), 'icon': 'route', 'group': 'work',
             'type': 'choice', 'pinned': True,
             'help': _('The four steps every role walks, as on the strip above.'),
             'options': [{'value': k, 'label': lbl, 'tone': tone, 'domain': dom}
                         for k, lbl, tone, dom in self._pbf_role_steps()]},
            {'key': 'status', 'label': _('Role status'), 'icon': 'circleDot', 'group': 'work',
             'type': 'selection', 'path': 'state', 'pinned': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building', 'group': 'work',
             'type': 'many2one', 'path': 'department_id', 'pinned': True,
             'none_label': _('No department')},
            # ---- more filters
            {'key': 'attention', 'label': _('Needs attention'), 'icon': 'bell', 'group': 'other',
             'type': 'choice', 'options': attention},
            {'key': 'request', 'label': _('Hiring request'), 'icon': 'fileCheck', 'group': 'other',
             'type': 'selection', 'path': 'request_state'},
            {'key': 'recruiter', 'label': _('Recruiter'), 'icon': 'userCheck', 'group': 'people',
             'type': 'many2one', 'path': 'recruiter_id', 'none_label': _('Nobody yet')},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe', 'group': 'work',
             'type': 'many2one', 'path': 'country_id', 'none_label': _('Not recorded')},
            {'key': 'role_type', 'label': _('Why it is needed'), 'icon': 'helpCircle',
             'group': 'work', 'type': 'selection', 'path': 'role_type'},
            {'key': 'has_candidates', 'label': _('Candidates'), 'icon': 'users', 'group': 'people',
             'type': 'choice', 'options': [
                 {'value': 'yes', 'label': _('Has candidates'), 'tone': 'green',
                  'domain': self._pbf_roles_with_people()},
                 {'value': 'no', 'label': _('Nobody yet'), 'tone': 'slate',
                  'domain': ~self._pbf_roles_with_people()},
             ]},
            {'key': 'headcount', 'label': _('People to find'), 'icon': 'hash', 'group': 'work',
             'type': 'number', 'path': 'headcount'},
            {'key': 'wanted_by', 'label': _('Wanted by'), 'icon': 'calendarClock', 'group': 'dates',
             'type': 'date', 'path': 'target_start_date', 'presets': 'future',
             'none_label': _('No date set')},
            {'key': 'opened', 'label': _('Opened on'), 'icon': 'calendar', 'group': 'dates',
             'type': 'date', 'path': 'opened_on', 'presets': 'past',
             'none_label': _('Not opened yet')},
        ]
        if team:
            spec.insert(5, {'key': 'budget', 'label': _('Budget'), 'icon': 'wallet',
                            'group': 'pay', 'type': 'selection', 'path': 'budget_status'})
        if self._pbf_people_readable():
            spec.insert(7, {'key': 'manager', 'label': _('Who they would report to'),
                            'icon': 'user', 'group': 'people', 'type': 'many2one',
                            'path': 'reporting_manager_id', 'none_label': _('Not named yet')})
        return spec

    def _pbf_views_roles(self):
        views = [
            {'key': 'all', 'label': _('All roles'), 'icon': 'briefcase', 'filters': {}},
            {'key': 'open', 'label': _('Open roles'), 'filters': {'status': ['open', 'setup']}},
        ]
        if self._pbf_team():
            views.append({'key': 'over', 'label': _('Over budget'), 'filters': {'budget': ['over']}})
        views += [
            {'key': 'noask', 'label': _('Nobody asked yet'),
             'filters': {'status': ['open', 'setup'], 'request': ['none']}},
            {'key': 'filled', 'label': _('Filled'), 'filters': {'status': ['filled']}},
            {'key': 'quarter', 'label': _('Opened this quarter'),
             'filters': {'opened': {'preset': 'this_quarter'}}},
        ]
        return views

    @api.model
    def _pbf_roles_tiers(self, domain):
        """The board's order of work as disjoint slices of `domain`: waiting
        on me, over budget, nobody recruiting, open, being set up, the rest
        (`_row`'s rank, read from fields instead of from built rows)."""
        live = [('state', 'in', ('setup', 'open'))]
        conds = [Domain(self._pbf_roles_mine())]
        if self._pbf_team():
            conds.append(Domain(live + [('budget_status', '=', 'over'),
                                        ('request_state', '!=', 'agreed')]))
        conds += [Domain(live + [('recruiter_id', '=', False)]),
                  Domain([('state', '=', 'open')]),
                  Domain([('state', '=', 'setup')]),
                  Domain.TRUE]
        tiers, before = [], []
        for cond in conds:
            tiers.append(Domain.AND([domain, cond] + [~b for b in before]))
            before.append(cond)
        return tiers

    @api.model
    def _pbf_page_args(self, kind, offset, limit):
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE[kind]), PAGE_MAX))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE[kind]
        return offset, limit

    @api.model
    def _pbf_choice_counts(self, me, key, filters, search):
        """Counts per option of one choice section, over every OTHER filter
        that is on (the kit's own rule) — the steps strip reads these."""
        spec = me._pbf_clean_spec()
        sec = next((s for s in spec if s['key'] == key), None)
        if not sec:
            return {}
        Rec = me._pbf_records()
        base = me.pbf_domain(filters, search, skip=key, spec=spec)
        out = {}
        for opt in sec.get('options') or []:
            out[opt['value']] = Rec.search_count(
                Domain.AND([base, Domain(me._pbf_opt_domain(opt))]))
        return out

    @api.model
    def get_roles_page(self, filters=None, search=None, sort=None, offset=0, limit=None):
        """One page of the Roles list for the panel's state, in `_row` form
        (every later phase's additions and the money mask included)."""
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        me = self._pbf_for('roles')
        offset, limit = me._pbf_page_args('roles', offset, limit)
        filters = filters if isinstance(filters, dict) else {}
        Rec = me._pbf_records()
        domain = me.pbf_domain(filters, search)
        total = Rec.search_count(domain)
        known = {s['key'] for s in me._pbf_sorts()}
        if (sort if sort in known else 'attention') == 'attention':
            recs = Rec.browse()
            skip, need = offset, limit
            order = 'opened_on asc nulls last, create_date asc, id desc'
            for tier in me._pbf_roles_tiers(domain):
                n = Rec.search_count(tier)
                if skip >= n:
                    skip -= n
                    continue
                got = Rec.search(tier, order=order, offset=skip, limit=need)
                skip = 0
                recs |= got
                need -= len(got)
                if need <= 0:
                    break
        else:
            recs = Rec.search(domain, order=me.pbf_order(sort) or 'id desc',
                              offset=offset, limit=limit)
        builder = self.sudo() if me._pbf_covered() else self
        rows = []
        for req in recs:
            row = self._safe(lambda req=req: builder._row(req), default=None)
            if row:
                rows.append(row)
        out = {'allowed': True, 'rows': rows, 'total': total, 'offset': offset}
        if not offset:
            out['steps'] = self._safe(
                lambda: self._pbf_choice_counts(me, 'step', filters, search), default={})
        return out

    # =====================================================================
    #  INTERVIEWS
    # =====================================================================
    def _pbf_spec_interviews(self):
        today = fields.Date.context_today(self)
        d0 = self._pbf_local_midnight(today)
        d1 = self._pbf_local_midnight(today + timedelta(days=1))
        d8 = self._pbf_local_midnight(today + timedelta(days=8))
        now = fields.Datetime.now()
        live = [('state', '=', 'scheduled')]
        late = [('state', 'in', ('scheduled', 'done')),
                ('feedback_ids', 'any', [('state', '=', 'pending'), ('due_at', '!=', False),
                                         ('due_at', '<', now)])]
        return [
            {'key': 'when', 'label': _('When it is'), 'icon': 'calendarClock', 'group': 'dates',
             'type': 'choice', 'pinned': True, 'options': [
                 {'value': 'today', 'label': _('Today'), 'tone': 'blue',
                  'domain': live + [('start', '>=', d0), ('start', '<', d1)]},
                 {'value': 'week', 'label': _('In the next 7 days'), 'tone': 'blue',
                  'domain': live + [('start', '>=', d0), ('start', '<', d8)]},
                 {'value': 'later', 'label': _('Later than that'), 'tone': 'slate',
                  'domain': live + [('start', '>=', d8)]},
                 {'value': 'past', 'label': _('Already happened'), 'tone': 'slate',
                  'domain': [('start', '<', now)]},
             ]},
            {'key': 'state', 'label': _('How it went'), 'icon': 'circleDot', 'group': 'work',
             'type': 'selection', 'path': 'state', 'pinned': True},
            {'key': 'role', 'label': _('Role'), 'icon': 'briefcase', 'group': 'work',
             'type': 'many2one', 'path': 'requisition_id', 'pinned': True},
            {'key': 'opinions', 'label': _('Opinions'), 'icon': 'messageSquare', 'group': 'people',
             'type': 'choice', 'options': [
                 {'value': 'late', 'label': _('Late'), 'tone': 'rose', 'domain': late},
                 {'value': 'waiting', 'label': _('Still coming in'), 'tone': 'amber',
                  'domain': [('feedback_ids', 'any', [('state', '=', 'pending')])]},
                 {'value': 'in', 'label': _('All in'), 'tone': 'green',
                  'domain': [('feedback_ids', 'any', [('state', '=', 'submitted')]),
                             ('feedback_ids', 'not any', [('state', '=', 'pending')])]},
             ]},
            {'key': 'kind', 'label': _('Kind of step'), 'icon': 'layers', 'group': 'work',
             'type': 'selection', 'path': 'kind'},
            {'key': 'mode', 'label': _('How it happens'), 'icon': 'video', 'group': 'work',
             'type': 'selection', 'path': 'mode'},
            {'key': 'recruiter', 'label': _('Recruiter'), 'icon': 'userCheck', 'group': 'people',
             'type': 'many2one', 'path': 'recruiter_id', 'none_label': _('Nobody yet')},
            {'key': 'job', 'label': _('Job'), 'icon': 'idCard', 'group': 'work',
             'type': 'many2one', 'path': 'job_id', 'none_label': _('No job yet')},
            {'key': 'round', 'label': _('Round'), 'icon': 'repeat', 'group': 'work',
             'type': 'number', 'path': 'round_no'},
            # kit 1.2.0: an explicit preset list, past and future together
            {'key': 'date', 'label': _('Date'), 'icon': 'calendar', 'group': 'dates',
             'type': 'date', 'path': 'start',
             'presets': ['today', 'this_week', 'next_7', 'next_30', 'passed', 'last_90']},
        ]

    def _pbf_views_interviews(self):
        return [
            {'key': 'all', 'label': _('All interviews'), 'icon': 'calendar', 'filters': {}},
            {'key': 'today', 'label': _('Today'), 'filters': {'when': ['today']}},
            {'key': 'week', 'label': _('This week'), 'filters': {'when': ['week']}},
            {'key': 'late', 'label': _('Opinions late'), 'filters': {'opinions': ['late']}},
            {'key': 'off', 'label': _('Called off recently'), 'filters': {'state': ['cancelled']}},
        ]

    @api.model
    def get_interviews_page(self, filters=None, search=None, sort=None, offset=0, limit=None):
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'total': 0, 'offset': 0}
        me = self._pbf_for('interviews')
        offset, limit = me._pbf_page_args('interviews', offset, limit)
        Rec = me._pbf_records()
        domain = me.pbf_domain(filters if isinstance(filters, dict) else {}, search)
        recs = Rec.search(domain, order=me.pbf_order(sort) or 'start asc, id asc',
                          offset=offset, limit=limit)
        builder = self.sudo() if me._pbf_covered() else self
        team = self._hiring_group()
        rows = []
        for rec in recs:
            row = self._safe(lambda rec=rec: builder._interview_row(rec), default=None)
            if not row:
                continue
            if not team:
                # the transcript is the hiring team's (G-30), as on the board
                row.pop('transcript_url', None)
                row.pop('transcript_file', None)
            rows.append(row)
        return {'allowed': True, 'rows': rows, 'total': Rec.search_count(domain),
                'offset': offset}

    # =====================================================================
    #  APPLICANTS
    # =====================================================================
    @api.model
    def _pbf_app_flags(self):
        """The card flags (`_card` in board_p1.py) as domains on hr.applicant.
        A card's family is its stage's, and an archived person in a working
        stage counts as closed."""
        now = fields.Datetime.now()
        week_end = now + timedelta(days=7)
        open_family = [('active', '=', True), ('stage_id.pb_family', 'in', ('open', False))]
        unlogged_past = [('state', '=', 'scheduled'), ('stop', '!=', False), ('stop', '<=', now)]
        unlogged_live = [('state', '=', 'scheduled'), ('start', '>', now)]
        waiting = Domain.OR([
            Domain(open_family + [('stage_id.pb_key', '=', 'screening'),
                                  ('pb_screen', '=', False)]),
            Domain(open_family + [('pb_interview_ids', 'any', unlogged_past)]),
            Domain.AND([~Domain(open_family), Domain.OR([
                Domain('pb_interview_ids', 'any', unlogged_past),
                Domain('pb_interview_ids', 'any', unlogged_live)])]),
        ])
        late = Domain(open_family + [('pb_interview_ids', 'any', [
            ('state', 'in', ('scheduled', 'done')),
            ('feedback_ids', 'any', [('state', '=', 'pending'), ('due_at', '!=', False),
                                     ('due_at', '<', now)])])])
        iv_week = Domain('pb_interview_ids', 'any', unlogged_live + [('start', '<=', week_end)])
        iv_any = Domain('pb_interview_ids', 'any', unlogged_live)
        duplicate = Domain([('pb_possible_duplicate_id', '!=', False),
                            ('pb_same_person_id', '=', False)])
        return {'waiting': waiting, 'late': late, 'iv_week': iv_week,
                'iv_any': iv_any, 'duplicate': duplicate}

    def _pbf_spec_applicants(self):
        team = self._pbf_team()
        flags = self._pbf_app_flags()
        attention = []
        if team:
            attention += [
                {'value': 'waiting', 'label': _('Waiting on you'), 'tone': 'amber',
                 'domain': flags['waiting']},
                {'value': 'late', 'label': _('Opinions late'), 'tone': 'rose',
                 'domain': flags['late']},
            ]
        attention += [
            {'value': 'iv_week', 'label': _('Interview this week'), 'tone': 'blue',
             'domain': flags['iv_week']},
            {'value': 'iv_any', 'label': _('An interview arranged'), 'tone': 'slate',
             'domain': flags['iv_any']},
        ]
        if team:
            attention.append({'value': 'duplicate', 'label': _('Possibly the same person'),
                              'tone': 'amber', 'domain': flags['duplicate']})
        spec = [
            {'key': 'family', 'label': _('Where they are'), 'icon': 'route', 'group': 'work',
             'type': 'choice', 'pinned': True, 'options': [
                 {'value': 'play', 'label': _('In play'), 'tone': 'blue',
                  'domain': FAMILY_DOMAINS['play']},
                 {'value': 'offer', 'label': _('Offer'), 'tone': 'amber',
                  'domain': FAMILY_DOMAINS['offer']},
                 {'value': 'joined', 'label': _('Joined'), 'tone': 'green',
                  'domain': FAMILY_DOMAINS['joined']},
                 {'value': 'closed', 'label': _('Closed'), 'tone': 'slate',
                  'domain': FAMILY_DOMAINS['closed']},
             ]},
            {'key': 'role', 'label': _('Role'), 'icon': 'briefcase', 'group': 'work',
             'type': 'many2one', 'path': 'pb_requisition_id', 'pinned': True,
             'none_label': _('No role')},
            {'key': 'recruiter', 'label': _('Recruiter'), 'icon': 'userCheck', 'group': 'people',
             'type': 'many2one', 'path': 'pb_requisition_id.recruiter_id', 'pinned': True,
             'none_label': _('Nobody yet')},
            {'key': 'attention', 'label': _('Needs attention'), 'icon': 'bell', 'group': 'other',
             'type': 'choice', 'options': attention},
            {'key': 'stage', 'label': _('Stage'), 'icon': 'columns', 'group': 'work',
             'type': 'many2one', 'path': 'stage_id'},
            {'key': 'moved', 'label': _('Moved to this stage'), 'icon': 'history', 'group': 'dates',
             'type': 'date', 'path': 'date_last_stage_update', 'presets': 'past'},
        ]
        if team:
            spec += [
                {'key': 'screen', 'label': _('First look'), 'icon': 'eye', 'group': 'work',
                 'type': 'selection', 'path': 'pb_screen', 'none_label': _('Not looked at yet')},
                {'key': 'source', 'label': _('Where they came from'), 'icon': 'share2',
                 'group': 'people', 'type': 'many2one', 'path': 'source_id',
                 'none_label': _('Not recorded')},
                {'key': 'authorisation', 'label': _('Allowed to work'), 'icon': 'shieldCheck',
                 'group': 'people', 'type': 'selection', 'path': 'pb_work_authorization',
                 'none_label': _('Not asked')},
                {'key': 'applied', 'label': _('Applied'), 'icon': 'calendar', 'group': 'dates',
                 'type': 'date', 'path': 'create_date', 'presets': 'past'},
                {'key': 'hold', 'label': _('Look at them again'), 'icon': 'hourglass',
                 'group': 'dates', 'type': 'date', 'path': 'pb_hold_until',
                 'presets': 'future', 'none_label': _('No date set')},
            ]
        return spec

    def _pbf_views_applicants(self):
        team = self._pbf_team()
        views = [
            {'key': 'all', 'label': _('Everyone'), 'icon': 'users', 'filters': {}},
            {'key': 'play', 'label': _('In play'), 'filters': {'family': ['play']}},
        ]
        if team:
            views += [
                {'key': 'waiting', 'label': _('Waiting on you'), 'filters': {'attention': ['waiting']}},
                {'key': 'late', 'label': _('Opinions late'), 'filters': {'attention': ['late']}},
            ]
        views.append({'key': 'iv', 'label': _('Interview this week'),
                      'filters': {'attention': ['iv_week']}})
        if team:
            views.append({'key': 'dup', 'label': _('Possible duplicates'),
                          'filters': {'attention': ['duplicate']}})
        return views

    @api.model
    def _pbf_app_glance(self, me):
        """The register's hero line, over everybody on the reader's roles (not
        the filters): the same domains as the views it opens."""
        Rec = me._pbf_records()
        base = Domain(me._pbf_base_domain())
        flags = self._pbf_app_flags()
        play = Domain.AND([base, Domain(FAMILY_DOMAINS['play'])])
        out = {
            'in_play': Rec.search_count(play),
            'roles': len(Rec._read_group(play, ['job_id'], ['__count'])),
            'waiting_mine': 0, 'opinions_late': 0,
            # the two figures below filter only for the hiring team (the
            # privacy mask blanks those facts on everybody else's cards)
            'team': bool(me._pbf_team()),
        }
        if me._pbf_team():
            out['waiting_mine'] = Rec.search_count(Domain.AND([base, flags['waiting']]))
            out['opinions_late'] = Rec.search_count(Domain.AND([base, flags['late']]))
        return out

    @api.model
    def _pbf_app_columns(self, Rec, domain):
        """One column per stage in journey order: every stage a visible role
        shows plus any somebody in this list sits in, each with its count over
        the WHOLE filtered list (not the page)."""
        Stage = self.env['hr.recruitment.stage'].sudo()
        counts = {}
        for stage, n in Rec._read_group(domain, ['stage_id'], ['__count']):
            if stage:
                counts[stage.id] = n
        shown = set()
        for req in self._p9_roles():
            shown |= set(self._safe(lambda req=req: req._pb_board_stages().ids, default=[]))
        out = []
        for s in Stage.search([('pb_key', '!=', False)], order='sequence,id'):
            if s.id not in shown and not counts.get(s.id):
                continue
            out.append({
                'id': s.id, 'key': s.pb_key, 'name': s.name or '', 'label': s.name or '',
                'family': s.pb_family or 'open', 'meaning': s.pb_meaning or '',
                'count': counts.get(s.id, 0), 'visible': True, 'avg_days': None,
            })
        return out

    @api.model
    def get_applicants_page(self, filters=None, search=None, sort=None, offset=0, limit=None):
        """One page of the Applicants register for the panel's state: the very
        cards a role's board builds (`_candidates`, privacy mask included),
        with the role on each, in the panel's order."""
        empty = {'allowed': False, 'cards': [], 'total': 0, 'offset': 0, 'roles': [],
                 'columns': [], 'glance': {}, 'can_move': False}
        if not self._can_read():
            return empty
        me = self._pbf_for('applicants')
        offset, limit = me._pbf_page_args('applicants', offset, limit)
        Rec = me._pbf_records()
        domain = me.pbf_domain(filters if isinstance(filters, dict) else {}, search)
        apps = Rec.search(domain, order=me.pbf_order(sort) or 'date_last_stage_update desc, id desc',
                          offset=offset, limit=limit)
        jobs = me._pbf_app_jobs()
        Requisition = self.env['pb.hiring.requisition'].sudo()
        groups = {}
        for app in apps:
            groups.setdefault(app.job_id.id, []).append(app.id)
        page_roles = Requisition.browse([jobs[j] for j in groups if j in jobs])
        role_rows = self._p9_role_rows(page_roles)
        by_role = {r['id']: r for r in role_rows}
        cards = {}
        for job_id, ids in groups.items():
            req = Requisition.browse(jobs.get(job_id) or [])
            if not req:
                continue
            role = by_role.get(req.id) or {}
            built = self._safe(lambda req=req, ids=ids: self.with_context(
                pb_hiring_app_ids=ids)._candidates(req), default=[])
            for card in built:
                card.update({
                    'role_id': req.id,
                    'role': role.get('name') or req.title or '',
                    'recruiter_id': role.get('recruiter_id') or False,
                    'recruiter': role.get('recruiter') or '',
                    'can_move': bool(role.get('can_move')),
                })
                cards[card['id']] = card
        out = {
            'allowed': True,
            'cards': [cards[i] for i in apps.ids if i in cards],
            'total': Rec.search_count(domain),
            'offset': offset,
            'roles': [r for r in role_rows if r['has_job']],
        }
        if not offset:
            out['columns'] = self._safe(lambda: self._pbf_app_columns(Rec, domain), default=[])
            out['glance'] = self._safe(lambda: self._pbf_app_glance(me), default={})
            # may this reader move anybody at all (the register's selection bar)
            out['can_move'] = bool(self._safe(lambda: any(
                self._can_move(r) for r in self._p9_roles()), default=False))
        return out

    # =====================================================================
    #  OFFERS
    # =====================================================================
    @api.model
    def _pbf_offer_joining(self):
        """(soon, passed) as domains: an accepted or signed offer whose joining
        date — the expected one, or the start date when none is set — falls
        in the next 30 days, or has gone by without them joining."""
        today = fields.Date.context_today(self)
        until = today + timedelta(days=JOINING_DAYS)
        signed = Domain('state', 'in', ('accepted', 'signed'))
        has_exp = Domain('expected_join_date', '!=', False)
        no_exp = Domain('expected_join_date', '=', False)
        soon = Domain.AND([signed, Domain.OR([
            Domain.AND([has_exp, Domain('expected_join_date', '>=', today),
                        Domain('expected_join_date', '<=', until)]),
            Domain.AND([no_exp, Domain('start_date', '>=', today),
                        Domain('start_date', '<=', until)]),
        ])])
        passed = Domain.AND([signed, Domain.OR([
            Domain.AND([has_exp, Domain('expected_join_date', '<', today)]),
            Domain.AND([no_exp, Domain('start_date', '<', today)]),
        ])])
        return soon, passed

    def _pbf_spec_offers(self):
        team = self._hiring_group()
        today = fields.Date.context_today(self)
        soon, passed = self._pbf_offer_joining()
        step_words = {
            'approval': (_('In approval'), 'blue'),
            'candidate': (_('With the candidate'), 'amber'),
            'signing': (_('Accepted and signing'), 'green'),
            'joined': (_('Joined'), 'green'),
            'closed': (_('Did not happen'), 'slate'),
        }
        spec = [
            {'key': 'step', 'label': _('Where it is'), 'icon': 'route', 'group': 'work',
             'type': 'choice', 'pinned': True, 'options': [
                 {'value': key, 'label': step_words[key][0], 'tone': step_words[key][1],
                  'domain': [('state', 'in', list(states))]}
                 for key, states in OFFER_STEPS]},
            {'key': 'state', 'label': _('Offer status'), 'icon': 'circleDot', 'group': 'work',
             'type': 'selection', 'path': 'state', 'pinned': True},
            {'key': 'role', 'label': _('Role'), 'icon': 'briefcase', 'group': 'work',
             'type': 'many2one', 'path': 'requisition_id', 'pinned': True},
            {'key': 'attention', 'label': _('Needs attention'), 'icon': 'bell', 'group': 'other',
             'type': 'choice', 'options': [
                 {'value': 'mine', 'label': _('Waiting on you'), 'tone': 'amber',
                  'domain_method': '_pbf_offers_mine'},
                 {'value': 'joining_soon', 'label': _('Joining in 30 days'), 'tone': 'green',
                  'domain': soon},
                 {'value': 'join_passed', 'label': _('Joining date passed'), 'tone': 'rose',
                  'domain': passed},
             ]},
            {'key': 'recruiter', 'label': _('Recruiter'), 'icon': 'userCheck', 'group': 'people',
             'type': 'many2one', 'path': 'requisition_id.recruiter_id',
             'none_label': _('Nobody yet')},
            {'key': 'decision', 'label': _('Their answer'), 'icon': 'messageSquare',
             'group': 'people', 'type': 'selection', 'path': 'candidate_decision',
             'none_label': _('Not asked yet')},
            {'key': 'start', 'label': _('Starts on'), 'icon': 'calendarClock', 'group': 'dates',
             'type': 'date', 'path': 'start_date', 'presets': 'future'},
            {'key': 'sent', 'label': _('Sent on'), 'icon': 'send', 'group': 'dates',
             'type': 'date', 'path': 'sent_on', 'presets': 'past', 'none_label': _('Not sent yet')},
            {'key': 'joined', 'label': _('Joined on'), 'icon': 'logIn', 'group': 'dates',
             'type': 'date', 'path': 'joined_on', 'presets': 'past',
             'none_label': _('Not joined yet')},
        ]
        if self._pbf_people_readable():
            spec.insert(5, {'key': 'manager', 'label': _('Who they will report to'),
                            'icon': 'user', 'group': 'people', 'type': 'many2one',
                            'path': 'reporting_manager_id', 'none_label': _('Not named yet')})
        if team:
            overdue = Domain.OR([
                Domain('docreq_id.state', '=', 'expired'),
                Domain.AND([Domain('docreq_id.deadline', '!=', False),
                            Domain('docreq_id.deadline', '<', today),
                            Domain('docreq_id.state', '!=', 'complete')]),
            ])
            spec += [
                {'key': 'docs', 'label': _('Documents'), 'icon': 'paperclip', 'group': 'other',
                 'type': 'choice', 'options': [
                     {'value': 'overdue', 'label': _('Past the date'), 'tone': 'rose',
                      'domain': overdue},
                     {'value': 'waiting', 'label': _('Still coming in'), 'tone': 'amber',
                      'domain': Domain.AND([Domain('docreq_id', '!=', False),
                                            Domain('docreq_id.state', 'in', ('sent', 'partial')),
                                            ~overdue])},
                     {'value': 'complete', 'label': _('All in'), 'tone': 'green',
                      'domain': [('docreq_id.state', '=', 'complete')]},
                     {'value': 'none', 'label': _('Not asked yet'), 'tone': 'slate',
                      'domain': [('docreq_id', '=', False)]},
                 ]},
                {'key': 'check', 'label': _('Background check'), 'icon': 'shieldCheck',
                 'group': 'other', 'type': 'selection', 'path': 'bgv_id.state',
                 'none_label': _('No check started')},
                {'key': 'monthly', 'label': _('A month'), 'icon': 'banknote', 'group': 'pay',
                 'type': 'number', 'path': 'monthly_total', 'unit': 'money'},
            ]
        return spec

    def _pbf_views_offers(self):
        views = [
            {'key': 'all', 'label': _('All offers'), 'icon': 'send', 'filters': {}},
            {'key': 'candidate', 'label': _('With the candidate'), 'filters': {'step': ['candidate']}},
            {'key': 'joining', 'label': _('Joining in 30 days'),
             'filters': {'attention': ['joining_soon']}},
        ]
        if self._hiring_group():
            views.append({'key': 'docs', 'label': _('Documents overdue'),
                          'filters': {'docs': ['overdue']}})
        views += [
            {'key': 'joined', 'label': _('Joined this month'),
             'filters': {'state': ['joined'], 'joined': {'preset': 'this_month'}}},
            {'key': 'declined', 'label': _('Turned down'), 'filters': {'state': ['declined']}},
        ]
        return views

    @api.model
    def _pbf_offer_kpi_counts(self):
        """The Overview's offer figures, counted through the Offers views' own
        domains over every offer the reader may see (not the newest 200)."""
        me = self._pbf_for('offers')
        Rec = me._pbf_records()
        spec = me._pbf_clean_spec()

        def n(filters):
            return Rec.search_count(me.pbf_domain(filters, '', spec=spec))
        return {
            'offers_waiting_mine': n({'attention': ['mine']}),
            'joining_soon': n({'attention': ['joining_soon']}),
            'joined_month': n({'state': ['joined'], 'joined': {'preset': 'this_month'}}),
        }

    @api.model
    def get_offers_page(self, filters=None, search=None, sort=None, offset=0, limit=None):
        """One page of the Offers register for the panel's state: `_offer_row`
        (masked as always) plus the register's own facts per row."""
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'total': 0, 'offset': 0,
                    'steps': {}, 'flags': {}, 'show_money': False}
        me = self._pbf_for('offers')
        offset, limit = me._pbf_page_args('offers', offset, limit)
        filters = filters if isinstance(filters, dict) else {}
        Rec = me._pbf_records()
        domain = me.pbf_domain(filters, search)
        offers = Rec.search(domain, order=me.pbf_order(sort) or 'id desc',
                            offset=offset, limit=limit)
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        sudo = offers.sudo()
        bgvs = {}
        for bgv in self.env['pb.hiring.bgv'].sudo().search([
                ('requisition_id', 'in', sudo.mapped('requisition_id').ids),
                ('applicant_id', 'in', sudo.mapped('applicant_id').ids)], order='id desc'):
            bgvs.setdefault((bgv.requisition_id.id, bgv.applicant_id.id), bgv)
        rows = []
        for offer in offers:
            row = self._safe(lambda offer=offer: self._p9_offer_row(
                offer, today, month_start, bgvs), default=None)
            if row:
                rows.append(row)
        out = {'allowed': True, 'rows': rows, 'total': Rec.search_count(domain),
               'offset': offset, 'show_money': bool(self._hiring_group())}
        if not offset:
            out['steps'] = self._safe(
                lambda: self._pbf_choice_counts(me, 'step', filters, search), default={})
            # the two lines the step strip carries ("3 waiting on you",
            # "2 joining in 30 days"), over the list as it is filtered
            out['flags'] = self._safe(
                lambda: self._pbf_choice_counts(me, 'attention', filters, search), default={})
        return out
