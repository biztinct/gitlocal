# -*- coding: utf-8 -*-
"""`pb.probation` — the Probation lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down,
`self.env.companies` scoping on every search, a row cap, and no sudo in a READ.

It reuses P0's tiers, the same call P3 and P4 made for the same reason: a trial
period is not a separate permission from the rest of the lifecycle, and a sixth
ladder would be a group nobody knew to grant.

THE QUESTION THIS BOARD ANSWERS is the one an HR coordinator asks on the first
Monday of a month: WHOSE TRIAL PERIOD ENDS SOON, and is anything in the way of
deciding. So a row is a PERSON, the number beside their name is the days left,
and the four things after it are the four things that hold a decision up — the
colleagues nobody has chosen, the answers nobody has given, the course nobody
has finished, and the flag somebody raised at the sixty-day conversation.
"""

import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .probation_common import (
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, MAX_NOMINEES, MIN_NOMINEES,
    P_AUTO_TRIGGER, PROBATION_LIVE, PROBATION_STATE_LABEL, REVIEW_OPEN,
    REVIEW_STATE_LABEL, VERDICT_LABEL, flag, initials,
)

_logger = logging.getLogger(__name__)

#: The old `get_board` payload's cap. The board itself now pages (FILTER W2).
BOARD_LIMIT = 300

#: Cards per page on the filtered board ("Show N more" loads the next page).
PAGE_SIZE = 60

#: How red the days-left number goes.
URGENT_DAYS = 7


class PbProbation(models.AbstractModel):
    _name = 'pb.probation'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Probation cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('Probation metric failed: %s', e)
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
                "You can look at who is in their trial period, but running a "
                "review is for the HR team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'countries': [], 'departments': [],
                    'states': [], 'auto_on': False}
        Emp = self.env['hr.employee']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()

        people = self._safe(lambda: Emp.search([
            ('company_id', 'in', co_ids),
            ('active', '=', True),
            ('pb_probation_state', 'in', ['in_probation', 'extended']),
        ], order='id', limit=BOARD_LIMIT), default=Emp.browse())

        rows = []
        for person in people:
            try:
                rows.append(self._row(person, today))
            except Exception:
                _logger.exception('Probation row for employee %s', person.id)
        rows.sort(key=lambda r: (r['days'] if r['days'] is not None else 9999,
                                 r['employee']))

        kpis = {
            'in_probation': len(rows),
            'running': len([r for r in rows if r['review_state']
                            and r['review_state'] != 'closed']),
            'verdicts': len([r for r in rows
                             if r['review_state'] == 'verdict']),
            'overdue_feedback': len([r for r in rows if r['feedback_late']]),
            'urgent': len([r for r in rows if r['days'] is not None
                           and r['days'] <= URGENT_DAYS]),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'auto_on': flag(self.env, P_AUTO_TRIGGER),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'countries': _facet(rows, 'country'),
            'departments': _facet(rows, 'dept'),
            'states': _facet(rows, 'review_label'),
            'min_nominees': MIN_NOMINEES,
            'max_nominees': MAX_NOMINEES,
        }

    @api.model
    def _row(self, emp, today=None):
        today = today or date.today()
        Review = self.env['pb.probation.review']
        # `for_employee` and NOT `order='state, id desc'`. Ordering a board by a
        # Selection column sorts by the STORED STRING, and "closed" is first in
        # the alphabet — so a person whose second round had just been scheduled
        # showed the first round's "Closed" on the board, with the live review
        # invisible. `for_employee` asks the question properly: the open one if
        # there is one, otherwise the most recent.
        review = self._safe(lambda: Review.for_employee(emp),
                            default=Review.browse())
        trial = self._safe(lambda: emp.sudo().trial_date_end, default=False)
        days = (trial - today).days if trial else None
        training = self._safe(
            lambda: self.env['pb.training.status'].summary_for(emp),
            default={'total': 0, 'done': 0, 'pending': [], 'ok': True,
                     'has_track': False})
        flags = self._safe(
            lambda: self.env['pb.employee.checkin'].sudo().search_count([
                ('employee_id', '=', emp.id), ('red_flag', '=', True),
                ('state', '!=', 'cancelled')]), default=0)
        deadline = review.feedback_deadline if review else False
        return {
            'id': emp.id,
            'review_id': review.id if review else 0,
            'employee': emp.name or '—',
            'initials': initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': (emp.department_id.name if emp.department_id else '')
            or _('No team'),
            'country': (emp.country_id.name if emp.country_id else '')
            or (emp.company_id.country_id.name
                if emp.company_id and emp.company_id.country_id else '')
            or _('Not set'),
            'manager': emp.parent_id.name if emp.parent_id else '',
            'doj': str(self._safe(lambda: emp._pb_join_date(), default='')
                       or ''),
            'trial_end': str(trial) if trial else '',
            'days': days,
            'when': _when(days),
            'urgent': bool(days is not None and days <= URGENT_DAYS),
            'state': emp.pb_probation_state or '',
            'state_label': PROBATION_STATE_LABEL.get(
                emp.pb_probation_state or '', ''),
            'round': review.round if review else 0,
            'review_state': review.state if review else '',
            'review_label': REVIEW_STATE_LABEL.get(review.state, '')
            if review else _('Not started'),
            'nominees': review.nominee_count if review else 0,
            'feedback_in': review.feedback_in if review else 0,
            'feedback_total': review.feedback_total if review else 0,
            'deadline': str(deadline) if deadline else '',
            'feedback_late': bool(
                review and review.state == 'feedback' and deadline
                and deadline < today),
            'deadline_extended': bool(review and review.deadline_extended),
            'verdict': review.verdict if review else '',
            'verdict_label': VERDICT_LABEL.get(review.verdict, '')
            if review else '',
            'training_ok': training['ok'],
            'training_done': training['done'],
            'training_total': training['total'],
            'training_pending': training['pending'],
            'red_flags': flags,
            'has_report': bool(review and review.consolidated_html),
        }

    # =====================================================================
    #  THE FILTER PANEL (pb_filter_kit, FILTER wave 2)
    #
    #  The board used to read 300 people, count its chips from them and
    #  filter them in the browser. Now every count is a server count over
    #  everybody in a trial period, and the cards come a page at a time.
    #  `get_board` above still answers the old payload (ruling R4).
    # =====================================================================
    @api.model
    def _pr_may_list(self):
        """The board's own tier AND the trial-period field itself, which is
        behind hr.group_hr_user: a reader who cannot read it has never been
        able to list anybody here, and is now told so instead of being shown
        an empty board."""
        if not self._can_read():
            return False
        Emp = self.env['hr.employee']
        field = Emp._fields.get('pb_probation_state')
        try:
            return bool(field) and Emp._has_field_access(field, 'read')
        except Exception:               # noqa: BLE001
            return False

    def _pbf_model(self):
        return 'hr.employee'

    def _pbf_screen(self):
        return 'probation'

    def _pbf_records(self):
        """SUDO for exactly the readers this board lets in, and nobody else.

        The board has always read the trial end date (behind
        hr.group_hr_manager), the reviews and the check-ins under sudo; its
        counts and its order by end date must see the same. The audience is
        unchanged (`_pr_may_list`) and the company travels in the base domain.
        """
        Emp = self.env['hr.employee']
        return Emp.sudo() if self._pr_may_list() else Emp

    def _pbf_base_domain(self):
        co_ids = self.env.companies.ids or [self.env.company.id]
        return [('company_id', 'in', co_ids), ('active', '=', True),
                ('pb_probation_state', 'in', list(PROBATION_LIVE))]

    def _pbf_search_fields(self):
        return ['name', 'job_title', 'department_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'ends', 'label': _('Trial ends soonest first'),
             'order': 'trial_date_end asc nulls last, name asc, id asc'},
            {'key': 'ends_late', 'label': _('Trial ends latest first'),
             'order': 'trial_date_end desc nulls last, name asc, id asc'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
            {'key': 'newest', 'label': _('Newest joiners first'),
             'order': 'first_contract_date desc nulls last, name asc, id asc'},
        ]

    @api.model
    def _pr_rules(self):
        """Every review fact on a card, as a domain on `hr.employee`.

        A person's review is the LIVE one (at most one: a second trigger adds
        nothing, R30) or, when none is live, the latest — the same rule as
        `pb.probation.review.for_employee`. All literal domains: every count
        stays one SQL query.
        """
        today = self._pbf_today()
        ds = fields.Date.to_string
        live = list(REVIEW_OPEN)

        def rev(dom):
            return Domain('pb_probation_review_ids', 'any', dom)

        none = Domain('pb_probation_review_ids', '=', False)
        no_live = Domain('pb_probation_review_ids', 'not any', [('state', 'in', live)])
        review = {'none': none}
        for st in live:
            review[st] = rev([('state', '=', st)])
        review['closed'] = no_live & rev([('state', '=', 'closed')])
        # the five numbered steps (probation_board.js flowStepOf)
        steps = {
            'peers': none | rev([('state', 'in', ['scheduled', 'nomination']),
                                 ('pb_gate', '!=', 'approved')]),
            'answers': rev([('state', '=', 'feedback'), ('pb_gate', '!=', 'approved')]),
            'talk': (rev([('state', 'in', ['consolidation', 'one_on_one']),
                          ('pb_gate', '!=', 'approved')])
                     | rev([('state', '=', 'verdict'),
                            ('pb_gate', 'not in', ['hr', 'ceo', 'approved'])])),
            'review': rev([('state', '=', 'verdict'), ('pb_gate', 'in', ['hr', 'ceo'])]),
            'outcome': review['closed'] | rev([('state', 'in', live),
                                               ('pb_gate', '=', 'approved')]),
        }
        late = rev([('state', '=', 'feedback'), ('feedback_deadline', '<', ds(today))])
        later = rev([('round', '>=', 2)])
        week = ds(today + timedelta(days=7))
        return {
            'today': today, 'review': review, 'steps': steps, 'late': late,
            'later': later, 'first': Domain('pb_probation_review_ids', '!=', False) & ~later,
            'running': rev([('state', 'in', live)]),
            'week': week,
        }

    @api.model
    def _pr_glance_filters(self, rules=None):
        """What each figure on the numbers line means as a filter — the SAME
        filters as the built-in views, so pressing one lights its tab."""
        rules = rules or self._pr_rules()
        return {
            'running': {'review': list(REVIEW_OPEN)},
            'verdicts': {'review': ['verdict']},
            'late': {'answers_late': ['yes']},
            # "Ending within a week" has always counted a trial that has
            # already run out too: that one cannot wait either.
            'urgent': {'trial_ends': {'to': rules['week']}},
        }

    def _pbf_spec(self):
        rules = self._pr_rules()
        review, steps = rules['review'], rules['steps']
        return [
            # ---- pinned: when it ends, where the review is, which team
            {'key': 'trial_ends', 'label': _('Trial period ends'), 'icon': 'calendarClock',
             'group': 'contract', 'type': 'date', 'path': 'trial_date_end',
             'presets': 'future', 'pinned': True, 'none_label': _('No end date')},
            {'key': 'stage', 'label': _('Review step'), 'icon': 'listChecks',
             'group': 'contract', 'type': 'choice', 'pinned': True,
             'requires': ['pb_probation_review_ids'],
             'help': _('The five steps of a probation review, as on the strip above the cards.'),
             'options': [
                 {'value': 'peers', 'label': _('Choose peers'), 'tone': 'slate',
                  'domain': steps['peers']},
                 {'value': 'answers', 'label': _('Gather perspectives'), 'tone': 'blue',
                  'domain': steps['answers']},
                 {'value': 'talk', 'label': _('Manager conversation'), 'tone': 'blue',
                  'domain': steps['talk']},
                 {'value': 'review', 'label': _('HR & leadership review'), 'tone': 'amber',
                  'domain': steps['review']},
                 {'value': 'outcome', 'label': _('Share the outcome'), 'tone': 'green',
                  'domain': steps['outcome']},
             ]},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id',
             'pinned': True, 'none_label': _('No team')},
            # ---- more filters
            {'key': 'review', 'label': _('Review status'), 'icon': 'fileText',
             'group': 'contract', 'type': 'choice',
             'requires': ['pb_probation_review_ids'],
             'options': [
                 {'value': 'none', 'label': _('Not started'), 'tone': 'slate',
                  'domain': review['none']},
                 {'value': 'scheduled', 'label': _('Scheduled'), 'tone': 'slate',
                  'domain': review['scheduled']},
                 {'value': 'nomination', 'label': _('Peers being chosen'), 'tone': 'blue',
                  'domain': review['nomination']},
                 {'value': 'feedback', 'label': _('Feedback running'), 'tone': 'blue',
                  'domain': review['feedback']},
                 {'value': 'consolidation', 'label': _('Consolidating'), 'tone': 'blue',
                  'domain': review['consolidation']},
                 {'value': 'one_on_one', 'label': _('Manager 1:1'), 'tone': 'blue',
                  'domain': review['one_on_one']},
                 {'value': 'verdict', 'label': _('Awaiting decision'), 'tone': 'amber',
                  'domain': review['verdict']},
                 {'value': 'closed', 'label': _('Closed'), 'tone': 'green',
                  'domain': review['closed']},
             ]},
            {'key': 'answers_late', 'label': _("Colleagues' answers"), 'icon': 'clock',
             'group': 'contract', 'type': 'choice',
             'requires': ['pb_probation_review_ids'],
             'help': _('Colleagues were asked, the answer window has closed and answers are missing.'),
             'options': [
                 {'value': 'yes', 'label': _('Overdue'), 'tone': 'rose',
                  'domain': rules['late']},
                 {'value': 'no', 'label': _('Nothing overdue'), 'tone': 'green',
                  'domain': ~rules['late']},
             ]},
            {'key': 'round', 'label': _('Review round'), 'icon': 'repeat',
             'group': 'contract', 'type': 'choice',
             'requires': ['pb_probation_review_ids'],
             'options': [
                 {'value': 'first', 'label': _('First round'), 'tone': 'slate',
                  'domain': rules['first']},
                 {'value': 'later', 'label': _('Second round or later'), 'tone': 'amber',
                  'domain': rules['later']},
             ]},
            {'key': 'trial', 'label': _('Trial status'), 'icon': 'hourglass',
             'group': 'contract', 'type': 'selection', 'path': 'pb_probation_state'},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'people', 'type': 'many2one', 'path': 'country_id',
             'none_label': _('Not recorded')},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'parent_id',
             'none_label': _('Nobody named')},
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'work', 'type': 'many2one', 'path': 'job_id',
             'none_label': _('No job position')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
            {'key': 'joined', 'label': _('Joined'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'first_contract_date',
             'presets': 'past', 'none_label': _('No start date')},
        ]

    def _pbf_builtin_views(self):
        glance = self._pr_glance_filters()
        return [
            {'key': 'all', 'label': _('All in trial'), 'icon': 'hourglass', 'filters': {}},
            {'key': 'ending', 'label': _('Ending within 7 days'),
             'filters': glance['urgent']},
            {'key': 'verdict', 'label': _('Waiting on a decision'),
             'filters': glance['verdicts']},
            {'key': 'late', 'label': _('Answers overdue'), 'filters': glance['late']},
            {'key': 'extended', 'label': _('Extended'), 'filters': {'trial': ['extended']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._pr_may_list():
            # the board shows its own "looked after by the HR team" panel
            return {'refused': _("Trial periods are looked after by the HR team.")}
        return super().pbf_layout()

    @api.model
    def get_board_head(self):
        """The numbers line, the switch notice and the flags, counted over
        EVERYBODY in a trial period. The cards come from `get_board_page`."""
        if not self._pr_may_list():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'auto_on': False, 'total': 0, 'glance_filters': {},
                    'min_nominees': MIN_NOMINEES, 'max_nominees': MAX_NOMINEES}
        Rec = self._pbf_records()
        rules = self._pr_rules()
        base = Domain(self._pbf_base_domain())

        def count(dom):
            return self._safe(lambda: Rec.search_count(base & Domain(dom)))

        total = self._safe(lambda: Rec.search_count(base))
        kpis = {
            'in_probation': total,
            'running': count(rules['running']),
            'verdicts': count(rules['review']['verdict']),
            'overdue_feedback': count(rules['late']),
            'urgent': count(Domain('trial_date_end', '<=', rules['week'])),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'auto_on': flag(self.env, P_AUTO_TRIGGER),
            'kpis': kpis,
            'total': total,
            'glance_filters': self._pr_glance_filters(rules),
            'min_nominees': MIN_NOMINEES,
            'max_nominees': MAX_NOMINEES,
        }

    @api.model
    def get_board_page(self, filters=None, search=None, sort=None, offset=0,
                       limit=PAGE_SIZE):
        """One page of cards for the panel's filters, plus — on the first
        page — the five step counts for those same filters (ruling R1)."""
        if not self._pr_may_list():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        Rec = self._pbf_records()
        spec = self._pbf_clean_spec()
        domain = self.pbf_domain(filters or {}, search, spec=spec)
        found = Rec.search(domain, order=self.pbf_order(sort) or 'name, id',
                           offset=offset, limit=limit)
        today = date.today()
        rows = []
        # Read as the reader, exactly as the old board read its cards.
        for person in self.env['hr.employee'].browse(found.ids):
            try:
                rows.append(self._row(person, today))
            except Exception:           # noqa: BLE001 — one bad card never blanks the board
                _logger.exception('Probation row for employee %s', person.id)
        out = {'rows': rows, 'total': Rec.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._pr_step_counts(filters or {}, search, spec)
        return out

    @api.model
    def _pr_step_counts(self, filters, search, spec):
        """{step: {n, flag counts}} for the panel's filters minus the step."""
        Rec = self._pbf_records()
        rules = self._pr_rules()
        dom = self.pbf_domain(filters, search, skip='stage', spec=spec)
        out = {}
        for key, step_dom in rules['steps'].items():
            at = dom & step_dom
            out[key] = {
                'n': self._safe(lambda at=at: Rec.search_count(at)),
                # the strip's flag: whose answers are late (only ever at
                # "Gather perspectives"; everybody at the sign-off step is
                # waiting for a sign-off, so that flag is the count itself)
                'late': self._safe(lambda at=at: Rec.search_count(
                    at & rules['late'])) if key == 'answers' else 0,
            }
        return out

    # ------------------------------------------------------------ one person
    @api.model
    def get_person(self, employee_id):
        """One trial period, whole — the drawer behind a row."""
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("That person could not be found."))
        # The live review if there is one (see `_row` on why not an order=).
        review = self.env['pb.probation.review'].for_employee(emp)
        checkins = self._safe(
            lambda: self.env['pb.employee.checkin'].sudo().search(
                [('employee_id', '=', emp.id), ('state', '!=', 'cancelled')],
                order='scheduled_date'),
            default=self.env['pb.employee.checkin'].browse())
        training = self._safe(
            lambda: self.env['pb.training.status'].sudo().search(
                [('employee_id', '=', emp.id)], order='track_id, id'),
            default=self.env['pb.training.status'].browse())
        return {
            'row': self._row(emp),
            'timeline': self._timeline(emp, review, checkins),
            'report': str(review.consolidated_html or '') if review else '',
            'avg_rating': review.avg_rating if review else 0.0,
            'strengths': (review.strengths or '') if review else '',
            'improvements': (review.improvements or '') if review else '',
            'peers': [{
                'name': p.name or '',
                'dept': p.department_id.name if p.department_id else '',
                'answered': self._peer_answered(review, p),
            } for p in (review.nominee_ids if review
                        else self.env['hr.employee'].browse())],
            'training': [{
                'id': t.id,
                'name': t.item_id.name or '',
                'track': t.track_id.name or '',
                'required': t.required,
                'done': t.state == 'done',
                'score': t.score,
            } for t in training],
            'checkins': [{
                'id': c.id,
                'name': c.name or '',
                'date': str(c.scheduled_date) if c.scheduled_date else '',
                'state': c.state,
                'notes': c.notes or '',
                'red': c.red_flag,
                'red_note': c.red_flag_note or '',
            } for c in checkins],
            'one_on_one': {
                'id': review.one_on_one_checkin_id.id,
                'date': str(review.one_on_one_checkin_id.scheduled_date or ''),
                'done': review.one_on_one_checkin_id.state == 'done',
            } if (review and review.one_on_one_checkin_id) else None,
            'letter_id': review.letter_id.id
            if (review and review.letter_id) else 0,
            'exit_case_id': review.exit_case_id.id
            if (review and review.exit_case_id) else 0,
        }

    def _peer_answered(self, review, person):
        if not review:
            return False
        for row in review.feedback_request_ids:
            same_user = (row.respondent_user_id and person.user_id
                         and row.respondent_user_id.id == person.user_id.id)
            same_mail = (row.respondent_email and person.work_email
                         and row.respondent_email.strip().lower()
                         == person.work_email.strip().lower())
            if same_user or same_mail:
                return row.state == 'submitted'
        return False

    def _timeline(self, emp, review, checkins):
        """Joining day, the conversations, the review, the trial end.

        One list, in date order, so the drawer tells a story rather than
        showing four boxes the reader has to reconcile.
        """
        out = []
        joined = self._safe(lambda: emp._pb_join_date(), default=False)
        if joined:
            out.append({'date': str(joined), 'kind': 'start',
                        'title': _('Joined'), 'note': ''})
        for row in checkins:
            out.append({
                'date': str(row.scheduled_date or ''),
                'kind': 'flag' if row.red_flag else 'checkin',
                'title': row.name or '',
                'note': row.red_flag_note or row.notes or '',
                'done': row.state == 'done',
            })
        if review:
            if review.create_date:
                out.append({'date': str(review.create_date.date()),
                            'kind': 'review',
                            'title': _('Review opened'), 'note': ''})
            if review.feedback_deadline:
                out.append({
                    'date': str(review.feedback_deadline), 'kind': 'review',
                    'title': _('Colleagues answer by'),
                    'note': _('%(done)s of %(total)s answered',
                              done=review.feedback_in,
                              total=review.feedback_total)})
            if review.verdict_at:
                out.append({'date': str(review.verdict_at.date()),
                            'kind': 'verdict',
                            'title': VERDICT_LABEL.get(review.verdict, ''),
                            'note': ''})
        trial = self._safe(lambda: emp.sudo().trial_date_end, default=False)
        if trial:
            out.append({'date': str(trial), 'kind': 'end',
                        'title': _('Trial period ends'), 'note': ''})
        out.sort(key=lambda e: e['date'] or '')
        return out

    # =====================================================================
    #  WRITES. Every one of them goes through the model that owns the fact.
    # =====================================================================
    @api.model
    def start_review(self, employee_id):
        self._require_write()
        review = self.env['pb.probation.review'].open_for(int(employee_id))
        review.action_start_nomination()
        return {'review_id': review.id}

    @api.model
    def nominee_options(self, employee_id, term=None):
        if not self._can_read():
            return []
        review = self.env['pb.probation.review'].open_for(int(employee_id))
        return review.suggest_nominees(term=term)

    @api.model
    def confirm_nominees(self, employee_id, nominee_ids):
        self._require_write()
        review = self.env['pb.probation.review'].open_for(int(employee_id))
        return review.action_confirm_nominees(nominee_ids)

    @api.model
    def extend_deadline(self, review_id):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_extend_deadline()

    @api.model
    def consolidate(self, review_id):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        review.action_consolidate()
        return True

    @api.model
    def finish_one_on_one(self, review_id, notes=None):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_one_on_one_done(notes=notes)

    @api.model
    def verdict_preview(self, review_id, verdict, extension_months=None):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.verdict_preview(verdict, extension_months)

    @api.model
    def save_verdict(self, review_id, verdict, strengths=None,
                     improvements=None, extension_months=None):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_verdict(verdict, strengths=strengths,
                                     improvements=improvements,
                                     extension_months=extension_months)

    @api.model
    def start_exit(self, review_id):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_start_exit()

    @api.model
    def settle_training(self, status_id, done=True, score=None):
        self._require_write()
        row = self.env['pb.training.status'].sudo().browse(
            int(status_id)).exists()
        if not row:
            raise UserError(_("That training item could not be found."))
        return row.action_done(score=score) if done else row.action_reopen()

    @api.model
    def run_automation(self):
        self._require_write()
        return self.env['pb.journey.case'].run_probation_automation()

    # ------------------------------------------------------------ the doors
    @api.model
    def open_review_action(self, review_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.probation.review',
            'res_id': int(review_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    @api.model
    def open_letter_action(self, letter_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        letter = self.env['pb.hr.letter'].browse(int(letter_id)).exists()
        if not letter:
            raise UserError(_("That letter could not be found."))
        return letter.action_open_pdf()

    @api.model
    def open_employee_action(self, employee_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': int(employee_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
        }


def _when(days):
    """"in 12 days" / "today" / "6 days ago" — never a bare number."""
    if days is None:
        return _('no date set')
    if days == 0:
        return _('ends today')
    if days == 1:
        return _('ends tomorrow')
    if days > 1:
        return _('in %s days', days)
    if days == -1:
        return _('ended yesterday')
    return _('%s days ago', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
