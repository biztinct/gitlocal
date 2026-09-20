# -*- coding: utf-8 -*-
"""`pb.hiring` — the Hiring lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing number answers zero instead of taking the screen down, `self.env
.companies` scoping on every search, a row cap that is a PARAMETER (right for
a screen, wrong for a job — R76), and no sudo in a read except where a field's
own `groups=` forces it.

THE QUESTION THIS BOARD ANSWERS is "who is waiting on me, and what is stuck".
So the order is PROBLEM FIRST (R113): the requests waiting for a sign-off this
person can give, then the ones that are over budget, then the open roles with
nobody recruiting them, then everything else by age. A board sorted "newest
first" is a board that hides the thing that has been stuck for a fortnight.

THE MONEY IS ON THIS BOARD, unlike the Contracts lens beside it, and for the
opposite reason: the number on a hiring request is a BUDGET, not somebody's
salary. Nobody's pay is disclosed by saying a role is expected to cost
600 million a year, and hiding it would hide the single fact the sign-off
turns on.
"""

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .hiring_common import (
    BUDGET_STATUS, DEBRIEF_DECISIONS, DELAY_KINDS, FINAL_KINDS, GROUP_ADMIN,
    GROUP_MANAGER, GROUP_USER, INTERVIEW_MODES, INTERVIEW_STATES, NO_SHOW_BY,
    RECOMMENDATIONS, REFERRAL_STATES, REQUISITION_STATES, ROLE_TYPES,
    SCREEN_TAGS, STEP_KINDS, as_id, counted, fold,
)

_logger = logging.getLogger(__name__)

#: How many rows the SCREEN reads. A cap that is right for a screen is a bug
#: in a job (R76) — every job in this module passes its own, or none.
BOARD_LIMIT = 300

#: Where a request sits in the order of work. Smaller comes first.
RANK_WAITING_ON_ME = 0
RANK_OVER_BUDGET = 1
RANK_NO_RECRUITER = 2
RANK_OPEN = 3
RANK_IN_FLIGHT = 4
RANK_SETTLED = 5


class PbHiring(models.AbstractModel):
    _name = 'pb.hiring'
    _description = 'Payobook Hiring cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception:               # noqa: BLE001
            # WARNING with the traceback, never DEBUG: a swallowed exception
            # logged at debug level is invisible on a live server and the
            # caller gets a cheerful zero either way (R92).
            _logger.warning('pb_hiring: a board read failed', exc_info=True)
            return default

    # NO `_is_admin()` FALLBACK ANYWHERE IN THIS FACADE, and that is
    # deliberate — the same call `pb.pip` made for the same reason (R56's
    # note). The record rules on these models are granted BY NAME: a system
    # administrator who holds no hiring group has no applicable group rule
    # and therefore sees no rows at all. A facade that answered "allowed"
    # over that would draw "No hiring requests yet" across a database full
    # of them, which is the one thing worse than an explained empty screen.
    # The two built-in administrator accounts are members of
    # `group_hiring_admin` in the security file, so nobody is locked out of
    # a fresh install; everybody else is added by a human, on purpose.
    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN)
                or self.env['pb.hiring.requisition']._can_raise(user))

    @api.model
    def _can_write(self):
        user = self.env.user
        return (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN))

    @api.model
    def _can_admin(self):
        return self.env.user.has_group(GROUP_ADMIN)

    @api.model
    def _can_recruit(self):
        """THE RECRUITER'S OWN WORK IS NOT THE MANAGER'S WORK.

        Writing and publishing an advert, sending it to a job board and
        screening a CV are what a recruiter is FOR — the group's own
        description says so. Agreeing a request, closing a role and marking
        one filled are decisions about head count and money, and those are
        the manager tier. Gating the whole facade on the manager tier meant
        the person doing the job could not press a single button on their
        own board, and the refusal even told them to "ask the hiring team".
        """
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN))

    # A3 — the gate takes the ROLE it is being asked about, because a
    # recruiter's cover is not a promotion: somebody standing in for one
    # colleague for a fortnight may work on that colleague's roles and on
    # nobody else's. `pb_hiring_a3.py` is where that second question is asked;
    # here the argument is simply carried, so every verb names the role it is
    # about rather than leaving the gate to guess.
    @api.model
    def _require_recruit(self, requisition=None):
        if not self._can_recruit():
            raise AccessError(_(
                "Adverts and candidates are the recruiters' side of this "
                "screen. Ask whoever is recruiting this role, or ask the HR "
                "team to add you to the hiring team."))
        return True

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can see the hiring board, but agreeing, closing or "
                "filling a role is for the hiring managers. Ask them and "
                "they will do it in a minute."))
        return True

    # =====================================================================
    #  The board
    # =====================================================================
    @api.model
    def get_board(self, limit=None):
        if not self._can_read():
            return self._empty_board()
        Requisition = self.env['pb.hiring.requisition']
        co_ids = self.env.companies.ids or [self.env.company.id]
        cap = int(limit or BOARD_LIMIT)

        requests = self._safe(
            lambda: Requisition.search([('company_id', 'in', co_ids)],
                                       order='id desc', limit=cap),
            default=Requisition.browse())
        total = self._safe(
            lambda: Requisition.search_count([('company_id', 'in', co_ids)]),
            default=len(requests))

        rows = [self._row(req) for req in requests]
        rows.sort(key=lambda r: (r['rank'], -(r['days_open'] or 0),
                                 -(r['id'] or 0)))
        interviews = self._safe(lambda: self._interview_rows(co_ids),
                                default=[])

        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_recruit': self._can_recruit(),
            'can_admin': self._can_admin(),
            'can_raise': Requisition._can_raise(),
            'kpis': self._kpis(rows, interviews),
            'rows': rows,
            'departments': self._safe(lambda: self._departments(co_ids),
                                      default=[]),
            'countries': sorted({(r['country_id'], r['country'])
                                 for r in rows if r['country_id']},
                                key=lambda t: t[1]),
            'recruiters': sorted({(r['recruiter_id'], r['recruiter'])
                                  for r in rows if r['recruiter_id']},
                                 key=lambda t: t[1]),
            'states': [{'key': k, 'label': v} for k, v in REQUISITION_STATES],
            'role_types': [{'key': k, 'label': v} for k, v in ROLE_TYPES],
            'budget_states': [{'key': k, 'label': v} for k, v in BUDGET_STATUS],
            'screen_tags': [{'key': k, 'label': v} for k, v in SCREEN_TAGS],
            'rule_count': self._safe(
                lambda: self.env['pb.hiring.country.rule'].sudo().search_count(
                    [('company_id', 'in', co_ids)]), default=0),
            'total': total,
            'capped': total > len(rows),
            # A2 — the other half of this board. The words come from the
            # server's own lists so the screen can never hold a second copy
            # that drifts out of step with them.
            'interviews': interviews,
            'interview_states': [{'key': k, 'label': v}
                                 for k, v in INTERVIEW_STATES],
            'modes': [{'key': k, 'label': v} for k, v in INTERVIEW_MODES],
            'step_kinds': [{'key': k, 'label': v} for k, v in STEP_KINDS],
            'no_show_reasons': [{'key': k, 'label': v} for k, v in NO_SHOW_BY],
            'delay_kinds': [{'key': k, 'label': v} for k, v in DELAY_KINDS],
            'decisions': [{'key': k, 'label': v} for k, v in DEBRIEF_DECISIONS],
            'recommendations': [{'key': k, 'label': v}
                                for k, v in RECOMMENDATIONS],
        }

    @api.model
    def _empty_board(self):
        return {'allowed': False, 'can_write': False,
                'can_recruit': False, 'can_admin': False,
                'can_raise': False, 'kpis': {}, 'rows': [], 'departments': [],
                'countries': [], 'recruiters': [], 'states': [],
                'role_types': [], 'budget_states': [], 'screen_tags': [],
                'rule_count': 0, 'total': 0, 'capped': False,
                'interviews': [], 'interview_states': [], 'modes': [],
                'step_kinds': [], 'no_show_reasons': [], 'delay_kinds': [],
                'decisions': [], 'recommendations': []}

    @api.model
    def _departments(self, co_ids):
        """Sorted in PYTHON: `complete_name` is computed and not stored on
        this build, so ORDER BY it dies (R91)."""
        rows = self.env['hr.department'].sudo().search_read(
            [('company_id', 'in', co_ids)], ['id', 'name'], limit=400)
        return sorted([{'id': r['id'], 'name': r['name'] or ''}
                       for r in rows], key=lambda r: fold(r['name']))

    @api.model
    def _row(self, req):
        today = fields.Date.context_today(self)
        waiting_title, waiting_mine = self._waiting(req)
        recruiter = req.recruiter_id
        pipeline = self._safe(lambda: self._pipeline(req), default=[])
        candidates = sum(p['count'] for p in pipeline)
        referrals = len(req.referral_ids)
        age = (today - (req.create_date.date() if req.create_date
                        else today)).days

        if waiting_mine:
            rank = RANK_WAITING_ON_ME
        elif req.state in ('draft', 'submitted', 'manager_ok', 'hr_ok') \
                and req.budget_status == 'over':
            rank = RANK_OVER_BUDGET
        elif req.state == 'open' and not recruiter:
            rank = RANK_NO_RECRUITER
        elif req.state == 'open':
            rank = RANK_OPEN
        elif req.state in ('draft', 'submitted', 'manager_ok', 'hr_ok'):
            rank = RANK_IN_FLIGHT
        else:
            rank = RANK_SETTLED

        return {
            'id': req.id,
            'name': req.name or '',
            'title': req.title or '',
            'role_type': req.role_type or '',
            'role_type_label': dict(ROLE_TYPES).get(req.role_type, ''),
            'department_id': req.department_id.id,
            'department': req.department_id.name or '',
            'country_id': req.country_id.id,
            'country': req.country_id.name or '',
            'location': req.location or '',
            'headcount': req.headcount or 1,
            'state': req.state,
            'state_label': dict(REQUISITION_STATES).get(req.state, ''),
            'waiting': waiting_title,
            'waiting_mine': waiting_mine,
            'budget_status': req.budget_status or 'unknown',
            'budget_label': dict(BUDGET_STATUS).get(req.budget_status, ''),
            'budget_note': req.budget_note or '',
            'budget_cost': req.budget_cost or 0.0,
            'budget_over_by': req.budget_over_by or 0.0,
            'currency': req.currency_id.name or '',
            'recruiter_id': recruiter.id,
            'recruiter': recruiter.name or '',
            # `avatar_128` and never `image_128`: the latter draws a grey
            # camera when the field is unset, which is a 200 that looks
            # broken to a person (R82).
            'recruiter_avatar': ('/web/image/res.users/%s/avatar_128'
                                 % recruiter.id) if recruiter else '',
            'requested_by': self.env['pb.hiring.requisition']._person(
                req.requested_by_id).name or '',
            'jd_state': (req.jd_current_id and 'approved')
            or (req.jd_ids and req.jd_ids[0].state) or 'none',
            'jd_count': len(req.jd_ids),
            'published': bool(req.published),
            'referral_open': bool(req.referral_open),
            'referrals': referrals,
            'candidates': candidates,
            'pipeline': pipeline,
            'days_open': req.days_open or age,
            'target_start_date': (str(req.target_start_date)
                                  if req.target_start_date else ''),
            'rank': rank,
        }

    @api.model
    def _waiting(self, req):
        """Which rung it is on, and whether it is on THIS reader.

        Read from the engine rather than guessed from the status: a route
        with a conditional rung legitimately skips one, and a second opinion
        written here would only ever disagree with the one that counts.
        """
        try:
            request = req._chain_open_request()
            if not request:
                return ('', False)
            step = req._chain_active_step()
            title = (step.title or '') if step else ''
            mine = bool(req._chain_my_seat())
            return (title, mine)
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: could not read the sign-off state of '
                            '%s', req.id, exc_info=True)
            return ('', False)

    @api.model
    def _pipeline(self, req):
        """Candidates per stage, for the little bar on every row."""
        if not req.job_id:
            return []
        Applicant = self.env['hr.applicant'].sudo()
        rows = Applicant.search_read(
            [('job_id', '=', req.job_id.id), ('active', '=', True)],
            ['stage_id'], limit=500)
        by_stage = {}
        for row in rows:
            stage = row.get('stage_id')
            if not stage:
                continue
            by_stage[stage[0]] = by_stage.get(stage[0], 0) + 1
        if not by_stage:
            return []
        stages = self.env['hr.recruitment.stage'].sudo().browse(
            list(by_stage)).sorted('sequence')
        return [{'id': s.id, 'name': s.name or '', 'count': by_stage[s.id]}
                for s in stages]

    # =====================================================================
    #  A2 — the interviews
    # =====================================================================
    @api.model
    def _interview_rows(self, co_ids, limit=None):
        """Everything still live, plus the recent past.

        The window is deliberate: an interview last March is history and
        belongs on the candidate, not on a board whose question is "what is
        happening this week and what is stuck". Six weeks back is enough to
        still see the round whose opinions nobody has written.
        """
        cap = int(limit or BOARD_LIMIT)
        since = fields.Datetime.now() - timedelta(days=42)
        rows = self.env['pb.hiring.interview'].search(
            [('company_id', 'in', co_ids), ('start', '>=', since)],
            order='start', limit=cap)
        return [self._interview_row(rec) for rec in rows]

    @api.model
    def _interview_row(self, rec):
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        start = rec.start
        bucket = 'past'
        if rec.state == 'scheduled' and start:
            if start.date() == today:
                bucket = 'today'
            elif today < start.date() <= today + timedelta(days=7):
                bucket = 'week'
            elif start > now:
                bucket = 'later'
        if rec.state in ('scheduled', 'done') and rec.feedback_late:
            bucket = 'late'
        elif rec.state in ('scheduled', 'done') and rec.stop and rec.stop < now \
                and rec.feedback_in < rec.feedback_total:
            bucket = 'awaiting'
        return {
            'id': rec.id,
            'requisition_id': rec.requisition_id.id,
            'role': rec.requisition_id.title or '',
            'applicant_id': rec.applicant_id.id,
            'candidate': rec.candidate_name or '',
            'round_no': rec.round_no or 1,
            'kind': rec.kind or '',
            'kind_label': dict(STEP_KINDS).get(rec.kind, ''),
            'start': str(rec.start or ''),
            'stop': str(rec.stop or ''),
            'mode': rec.mode or '',
            'mode_label': dict(INTERVIEW_MODES).get(rec.mode, ''),
            'location': rec.location or '',
            'panel': [p.name or '' for p in rec.panel_employee_ids.sudo()],
            'recruiter': rec.recruiter_id.name or '',
            'state': rec.state,
            'state_label': dict(INTERVIEW_STATES).get(rec.state, ''),
            'feedback_in': rec.feedback_in,
            'feedback_total': rec.feedback_total,
            'feedback_late': rec.feedback_late,
            'feedback_due': str(rec.feedback_due_at or ''),
            'recommendation_avg': round(rec.recommendation_avg, 2),
            'late_notice': bool(rec.late_notice),
            'moved_times': len(rec.reschedule_ids),
            'decision': rec.decision or '',
            'decision_label': dict(DEBRIEF_DECISIONS).get(rec.decision, ''),
            'can_debrief': rec.kind in FINAL_KINDS,
            'bucket': bucket,
        }

    @api.model
    def _kpis(self, rows, interviews=None):
        interviews = interviews or []
        month_start = date.today().replace(day=1)
        return {
            'interviews_week': sum(1 for i in interviews
                                   if i['bucket'] in ('today', 'week')),
            'feedback_late': sum(i['feedback_late'] for i in interviews),
            'open': sum(1 for r in rows if r['state'] == 'open'),
            'waiting': sum(1 for r in rows if r['waiting']),
            'waiting_mine': sum(1 for r in rows if r['waiting_mine']),
            'candidates': sum(r['candidates'] for r in rows),
            'referrals': self._safe(
                lambda: self.env['pb.hiring.referral'].search_count([
                    ('company_id', 'in', self.env.companies.ids
                     or [self.env.company.id]),
                    ('submitted_on', '>=', str(month_start))]), default=0),
            # THE SAME DOMAIN AS THE CHIP IT FILTERS (R80). Counting only
            # the ones still going, over a filter that shows every one of
            # them, put "Over budget 0" on a board with an "Over by
            # 300,000,000 ₫" card two inches below it — a number that is
            # wrong about the list beside it, and a filter that opens on
            # rows the tile said were not there.
            'over_budget': sum(1 for r in rows
                               if r['budget_status'] == 'over'),
        }

    # =====================================================================
    #  One request, in full
    # =====================================================================
    @api.model
    def get_requisition(self, requisition_id):
        req = self.env['pb.hiring.requisition'].browse(as_id(requisition_id))
        if not req.exists():
            raise UserError(_("That hiring request is no longer there."))
        row = self._row(req)
        row.update({
            'requirements': req.requirements or '',
            'remarks': req.remarks or '',
            'closing_note': req.closing_note or '',
            'reporting_manager': self.env['pb.hiring.requisition']._person(
                req.reporting_manager_id).name or '',
            'recruiter_manager': req.recruiter_manager_id.name or '',
            'opened_on': str(req.opened_on) if req.opened_on else '',
            'job_id': req.job_id.id,
            'job_name': req.job_id.name or '',
            'steps': [{'id': s.id, 'name': s.name or '',
                       'kind': s.kind or '',
                       'kind_label': dict(s._fields['kind'].selection).get(
                           s.kind, ''),
                       'owner': s.owner_id.name or '',
                       'stage': s.stage_id.name or '',
                       'days': s.days_expected or 0}
                      for s in req.step_ids],
            'selected_applicant_id': req.selected_applicant_id.id,
            'selected_applicant':
                req.selected_applicant_id.sudo().partner_name or '',
            'panel_people': self._safe(lambda: self._panel_people(req),
                                       default=[]),
            'jds': [{'id': j.id, 'version': j.version or 1,
                     'title': j.title or '', 'state': j.state,
                     'state_label': dict(j._fields['state'].selection).get(
                         j.state, ''),
                     'summary': j.summary or '',
                     'is_current': bool(j.is_current),
                     'approved_on': str(j.approved_on) if j.approved_on
                     else ''}
                    for j in req.jd_ids],
            # EVERY LIST IN THIS DRAWER IS ITS OWN PROBE. Found live on
            # 2026-09-15: the person who ASKED for a role holds no hiring
            # group by definition, had no read on the advert pack, and
            # opening their own request answered an AccessError naming a
            # model they have never heard of — over a drawer whose other
            # eight sections they were perfectly entitled to. One failing
            # number must answer empty, never take the screen down (R92).
            'postings': self._safe(lambda: self._postings(req), default=[]),
            'referrals': [{'id': r.id, 'name': r.candidate_name or '',
                           'by': self.env['pb.hiring.requisition']._person(
                               r.employee_id).name or '',
                           'state': r.state or 'received',
                           'state_label': r.state_label or '',
                           'applicant_id': r.applicant_id.id,
                           'on': str(r.submitted_on)[:10]
                           if r.submitted_on else ''}
                          for r in req.referral_ids],
            'candidates_list': self._safe(lambda: self._candidates(req),
                                          default=[]),
            'other_jobs': self._safe(
                lambda: self.env['hr.applicant'].pb_open_jobs(), default=[]),
            'refuse_reasons': self._safe(
                lambda: [{'id': r['id'], 'name': r['name']}
                         for r in self.env[
                             'hr.applicant.refuse.reason'].sudo().search_read(
                                 [], ['name'], limit=30)], default=[]),
        })
        return row

    @api.model
    def _postings(self, req):
        return [{'id': p.id, 'platform': p.platform_id.name or '',
                 'email': p.platform_email or '',
                 'subject': p.subject or '',
                 'state': p.state,
                 'state_label': dict(p._fields['state'].selection).get(
                     p.state, ''),
                 'sent_on': str(p.sent_on) if p.sent_on else ''}
                for p in req.posting_ids]

    @api.model
    def _candidates(self, req):
        if not req.job_id:
            return []
        Applicant = self.env['hr.applicant'].sudo()
        rows = Applicant.with_context(active_test=False).search(
            [('job_id', '=', req.job_id.id)],
            order='stage_id desc, id desc', limit=120)
        # ONE READ FOR EVERY CANDIDATE'S INTERVIEWS, not one per card. A
        # drawer with forty candidates would otherwise be forty searches, and
        # the row cap above is what makes that a slow screen rather than a
        # broken one — which is the worse of the two failures.
        by_applicant = {}
        interviews = self.env['pb.hiring.interview'].search(
            [('applicant_id', 'in', rows.ids)], order='start desc', limit=400)
        for rec in interviews:
            by_applicant.setdefault(rec.applicant_id.id, []).append(
                self._interview_row(rec))
        out = []
        for app in rows:
            mine = by_applicant.get(app.id, [])
            live = [i for i in mine if i['state'] == 'scheduled']
            out.append({
                'id': app.id,
                'name': app.partner_name or app.email_from or _('Candidate'),
                'email': app.email_from or '',
                'stage': app.stage_id.name or '',
                'stage_seq': app.stage_id.sequence or 0,
                'source': app.source_id.name or '',
                'screen': app.pb_screen or '',
                'screen_label': dict(SCREEN_TAGS).get(app.pb_screen, ''),
                'status': app.application_status or '',
                'active': bool(app.active),
                'interviews': mine,
                # The one a person would ask about: the hour that has not
                # happened yet, soonest first.
                'next_interview': sorted(
                    live, key=lambda i: i['start'])[0] if live else None,
                'rounds': len([i for i in mine
                               if i['state'] not in ('cancelled',
                                                     'rescheduled')]),
                'selected': app.id == req.selected_applicant_id.id,
            })
        return out

    @api.model
    def _panel_people(self, req):
        """Who can be put on a panel: this company's people, folded for
        searching.

        `fold` rather than a domain `ilike`, because Postgres on this box has
        no `unaccent` extension and most people on this database have an
        accent in their name (R78) — and `search_read` of two columns rather
        than a `search` of records, because reading one field of an
        `hr.employee` reads forty (R56).
        """
        co_ids = [req.company_id.id] if req.company_id \
            else (self.env.companies.ids or [self.env.company.id])
        rows = self.env['hr.employee'].sudo().search_read(
            [('company_id', 'in', co_ids)], ['id', 'name', 'job_title'],
            limit=600)
        return sorted(
            [{'id': r['id'], 'name': r['name'] or '',
              'role': r.get('job_title') or '',
              'fold': fold(r['name'] or '')} for r in rows],
            key=lambda r: r['fold'])

    # =====================================================================
    #  The verbs
    # =====================================================================
    @api.model
    def act(self, verb, payload=None):
        """One door for every press on the board.

        The board never writes a field: it names an intention and the server
        decides whether it may happen. `payload` is always a plain dictionary
        because a recordset does not survive the wire (R43).
        """
        payload = payload or {}
        handler = getattr(self, '_act_%s' % (verb or ''), None)
        if handler is None or not (verb or '').isidentifier():
            raise UserError(_("That is not something this screen can do."))
        return handler(payload)

    # -------------------------------------------------------- the request
    def _act_create(self, payload):
        Requisition = self.env['pb.hiring.requisition']
        Requisition._require_raise()
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            raise UserError(_(
                "Payobook does not have an employee record for your login "
                "yet, and a hiring request has to say who asked for it. Ask "
                "the HR team to link them."))
        vals = {
            'title': (payload.get('title') or '').strip(),
            'role_type': payload.get('role_type') or 'new_role',
            'department_id': as_id(payload.get('department_id')),
            'headcount': int(payload.get('headcount') or 1),
            'requested_by_id': employee.id,
            'budget_cost': float(payload.get('budget_cost') or 0.0),
            'location': (payload.get('location') or '').strip(),
            'requirements': (payload.get('requirements') or '').strip(),
        }
        if payload.get('country_id'):
            vals['country_id'] = as_id(payload['country_id'])
        if payload.get('target_start_date'):
            vals['target_start_date'] = payload['target_start_date']
        if not vals['title'] or not vals['department_id']:
            raise UserError(_(
                "A hiring request needs a role name and the part of the "
                "business it is for."))
        req = Requisition.create(vals)
        return {'id': req.id, 'name': req.name,
                'note': _("%s is saved as a draft. Add the advert and the "
                          "stages, then send it in.", req.name)}

    def _act_submit(self, payload):
        req = self._get(payload)
        req.action_submit()
        return {'id': req.id, 'state': req.state,
                'note': _("Sent in. You will see it move as each person "
                          "agrees it.")}

    def _act_refresh_budget(self, payload):
        req = self._get(payload)
        req._refresh_budget()
        return {'id': req.id, 'budget_status': req.budget_status,
                'note': req.budget_note or ''}

    def _act_open_role(self, payload):
        """The dormant path's last rung, for a database with no route."""
        req = self._get(payload)
        self._require_write()
        req.action_open_role(note=payload.get('note'))
        return {'id': req.id, 'state': req.state}

    def _act_close(self, payload):
        req = self._get(payload)
        self._require_write()
        req.action_close(note=payload.get('note'))
        return {'id': req.id, 'state': req.state,
                'note': _("Closed. It stays on the board so the history is "
                          "not lost.")}

    def _act_mark_filled(self, payload):
        req = self._get(payload)
        self._require_write()
        req.action_mark_filled()
        return {'id': req.id, 'state': req.state,
                'note': _("Marked filled, and the role is off the careers "
                          "page.")}

    def _act_toggle_referrals(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        wanted = not req.referral_open
        req.sudo().write({'referral_open': wanted})
        return {'id': req.id, 'referral_open': wanted,
                'note': _("Everybody can put somebody forward for this role "
                          "now.") if wanted else
                _("This role is off the referral page.")}

    def _act_publish(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        return req.action_publish()

    def _act_send_posting(self, payload):
        posting = self.env['pb.hiring.posting'].browse(
            as_id(payload.get('posting_id')))
        posting.ensure_one()
        self._require_recruit(posting.requisition_id)
        posting.action_send()
        return {'id': posting.id, 'state': posting.state,
                'note': _("Sent to %s.", posting.platform_id.name or '')}

    # ------------------------------------------------------------ the advert
    def _act_new_jd(self, payload):
        req = self._get(payload)
        jd = self.env['pb.hiring.jd'].create({
            'requisition_id': req.id,
            'title': payload.get('title') or req.title,
            'body': payload.get('body') or '',
            'summary': payload.get('summary') or '',
        })
        return {'id': jd.id, 'version': jd.version,
                'note': _("Version %s started.", jd.version)}

    def _act_submit_jd(self, payload):
        jd = self.env['pb.hiring.jd'].browse(as_id(payload.get('jd_id')))
        jd.ensure_one()
        jd.action_submit()
        return {'id': jd.id, 'state': jd.state,
                'note': _("Sent to be agreed.")}

    def _act_approve_jd(self, payload):
        jd = self.env['pb.hiring.jd'].browse(as_id(payload.get('jd_id')))
        jd.ensure_one()
        jd.action_approve(note=payload.get('note'))
        return {'id': jd.id, 'state': jd.state,
                'note': _("Agreed. It is now the advert this role uses.")}

    # --------------------------------------------------------- the screening
    def _act_screen(self, payload):
        applicant = self.env['hr.applicant'].browse(
            as_id(payload.get('applicant_id')))
        applicant.ensure_one()
        self._require_recruit(applicant.sudo().pb_requisition_id)
        applicant.action_pb_screen(payload.get('tag'),
                                   job_id=payload.get('job_id'),
                                   reason_id=payload.get('reason_id'))
        labels = dict(SCREEN_TAGS)
        return {'id': applicant.id,
                'note': _("%(who)s: %(what)s.",
                          who=applicant.sudo().partner_name or '',
                          what=labels.get(payload.get('tag'), ''))}

    # --------------------------------------------------------------- doors
    def _act_open_requisition(self, payload):
        req = self._get(payload)
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.requisition', 'res_id': req.id,
                'view_mode': 'form', 'views': [[False, 'form']],
                'name': req.display_name}

    def _act_open_jd(self, payload):
        jd = self.env['pb.hiring.jd'].browse(as_id(payload.get('jd_id')))
        jd.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'pb.hiring.jd',
                'res_id': jd.id, 'view_mode': 'form',
                'views': [[False, 'form']], 'name': jd.display_name}

    def _act_open_job(self, payload):
        req = self._get(payload)
        return req.action_open_job()

    def _act_open_applicant(self, payload):
        applicant = self.env['hr.applicant'].browse(
            as_id(payload.get('applicant_id')))
        applicant.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.applicant',
                'res_id': applicant.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': applicant.sudo().partner_name or _('Candidate'),
                'context': {'active_test': False}}

    def _act_open_rules(self, payload):
        action = self.env.ref('pb_hiring.action_pb_hiring_country_rule',
                              raise_if_not_found=False)
        if not action:
            raise UserError(_("The hiring rules screen is not in this build."))
        return action.read()[0]

    def _act_run_automation(self, payload):
        """"Run it now" does exactly what the night does (R53)."""
        self._require_recruit()
        counts = self.env['pb.hiring.automation'].run_now()
        return {'note': self.env['pb.hiring.automation'].describe(counts),
                'counts': counts}

    # =====================================================================
    #  A2 — the interview loop
    # =====================================================================
    def _interview(self, payload, key='interview_id'):
        rec = self.env['pb.hiring.interview'].browse(
            as_id(payload.get(key) or payload.get('id')))
        rec.ensure_one()
        return rec

    def _act_schedule(self, payload):
        self._require_recruit(self.env['pb.hiring.requisition'].browse(
            as_id(payload.get('requisition_id'))))
        interview = self.env['pb.hiring.interview'].schedule(payload)
        return {
            'id': interview.id,
            'note': _("Round %(n)s with %(who)s is arranged, and everybody "
                      "has the invitation.",
                      n=interview.round_no or 1,
                      who=interview.candidate_name or ''),
        }

    def _act_reschedule(self, payload):
        interview = self._interview(payload)
        self._require_recruit(interview.requisition_id)
        fresh = interview.reschedule(payload)
        return {'id': fresh.id,
                'note': _("Moved. The old time is called off and the new one "
                          "has gone out.")}

    def _act_no_show(self, payload):
        interview = self._interview(payload)
        self._require_recruit(interview.requisition_id)
        interview.action_no_show(by=payload.get('by'),
                                 note=payload.get('note'))
        return {'id': interview.id, 'state': interview.state,
                'note': _("Written down. The recruiter has been given "
                          "something to do about it.")}

    def _act_mark_done(self, payload):
        interview = self._interview(payload)
        self._require_recruit(interview.requisition_id)
        interview.action_mark_done()
        return {'id': interview.id, 'state': interview.state,
                'note': _("Done, with every opinion in.")}

    def _act_cancel_interview(self, payload):
        interview = self._interview(payload)
        self._require_recruit(interview.requisition_id)
        interview.action_cancel(note=payload.get('note'))
        return {'id': interview.id, 'state': interview.state,
                'note': _("Called off, and everybody has been told.")}

    def _act_debrief(self, payload):
        interview = self._interview(payload)
        self._require_recruit(interview.requisition_id)
        interview.action_debrief(notes=payload.get('notes'),
                                 decision=payload.get('decision'))
        return {'id': interview.id,
                'note': _("Written down while everybody still remembers it.")}

    def _act_next_round(self, payload):
        applicant = self.env['hr.applicant'].browse(
            as_id(payload.get('applicant_id')))
        applicant.ensure_one()
        self._require_recruit(applicant.sudo().pb_requisition_id)
        applicant.action_pb_next_round(step_id=payload.get('step_id'))
        return {'id': applicant.id,
                'note': _("Through to %s, and they have been told.",
                          applicant.sudo().stage_id.name or '')}

    def _act_reject(self, payload):
        applicant = self.env['hr.applicant'].browse(
            as_id(payload.get('applicant_id')))
        applicant.ensure_one()
        self._require_recruit(applicant.sudo().pb_requisition_id)
        name = applicant.sudo().partner_name or ''
        applicant.action_pb_reject(reason_id=payload.get('reason_id'))
        return {'id': applicant.id,
                'note': _("%s has been told. It is a small thing and almost "
                          "nobody does it.", name)}

    def _act_open_interview(self, payload):
        interview = self._interview(payload)
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.interview', 'res_id': interview.id,
                'view_mode': 'form', 'views': [[False, 'form']],
                'name': interview.display_name}

    def _act_copy_feedback_link(self, payload):
        """A panel member whose mail bounced is a very ordinary problem."""
        row = self.env['pb.hiring.feedback'].browse(
            as_id(payload.get('feedback_id')))
        row.ensure_one()
        self._require_recruit(row.requisition_id)
        return {'id': row.id, 'link': row.sudo()._token_url(),
                'note': _("Their own link is on screen — send it to them "
                          "however you like.")}

    def _act_interview_panel(self, payload):
        """Who is on this interview's panel, and what each of them said."""
        interview = self._interview(payload)
        labels = dict(RECOMMENDATIONS)
        return {
            'id': interview.id,
            'rows': [{
                'id': f.id,
                'who': f.panel_employee_id.sudo().name or '',
                'state': f.state,
                'verdict': labels.get(f.recommendation, ''),
                'score': round(f.score_avg, 1),
                'notes': f.notes or '',
                'due': str(f.due_at or ''),
                'chased': bool(f.urgent_sent_at),
            } for f in interview.feedback_ids.sorted('id')],
        }

    def _act_run_reminders(self, payload):
        """The ten-minute step, run by hand. Stamped, so it is safe."""
        self._require_recruit()
        Auto = self.env['pb.hiring.automation']
        counts = Auto.run_reminders()
        return {'note': Auto.describe_reminders(counts), 'counts': counts}

    # --------------------------------------------------------------- helper
    def _get(self, payload):
        req = self.env['pb.hiring.requisition'].browse(
            as_id(payload.get('requisition_id') or payload.get('id')))
        req.ensure_one()
        return req
