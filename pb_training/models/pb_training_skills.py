# -*- coding: utf-8 -*-
"""Learning › SKILLS, and the learner's side of LEARNING L5 (My learning and
`/my/training/requests`).

SKILLS (rail seq 75): each person against the skills their JOB requires
(`hr.job.current_job_skill_ids`), the gap, and the course that closes it (a
course whose skill grant gives that skill at the level or higher). The
training team sees everybody in their companies; a manager sees the people
under them (`parent_id child_of` their own record) and nobody else — the
lens is offered to whoever `can_see_skills()` says yes to. The hero: "On
average a person has 4 of 6 required skills · 38 gaps across 120 people".

The by-skill table reuses the workforce-planning shape (ledger F7):
`{skill, employees, coverage_pct, levels}` — but measured against the jobs
that require the skill, not over everybody.

The learner: `request_options()` / `ask_course()` / `my_requests()` /
`cancel_request()` / `my_skills()` / `my_feedback()` on `pb.my.training` —
"me" is the session user, never a parameter.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .training_common import (
    OUTSIDE_KIND_LABEL, as_id, duration_words, fold, minutes, money_words, tr,
)

_logger = logging.getLogger(__name__)

PEOPLE_CAP = 200


class PbTrainingSkills(models.AbstractModel):
    _inherit = 'pb.training'

    # =====================================================================
    #  who sees what
    # =====================================================================
    @api.model
    def can_see_skills(self):
        """The rail probe: the training team, or anybody who manages
        people."""
        try:
            if self._can_read():
                return True
            return bool(self.env['pb.my.training'].i_manage_people())
        except Exception:               # noqa: BLE001 — a probe never raises
            return False

    @api.model
    def _skills_people(self):
        """(employees, team_mode). Read as the system; the scope IS the
        search."""
        Emp = self.env['hr.employee'].sudo()
        if self._can_read():
            return Emp.search([('company_id', 'in', self.env.companies.ids),
                               ('active', '=', True)]), False
        me = self.env['pb.my.training']._my_employee()
        if not me:
            return Emp.browse(), True
        return Emp.search([('id', 'child_of', me.id), ('id', '!=', me.id),
                           ('active', '=', True)]), True

    @api.model
    def _grant_index(self):
        """{skill_id: [(progress, label, kind, id)]} — every course that gives
        a skill, ours and outside, best level first."""
        index = {}
        for grant in self.env['pb.training.skill.grant'].sudo().search([]):
            if grant.channel_id:
                if not grant.channel_id.active:
                    continue
                item = (grant.skill_level_id.level_progress or 0,
                        grant.channel_id.name or '', 'ours',
                        grant.channel_id.id)
            elif grant.outside_course_id:
                if not grant.outside_course_id.active or \
                        grant.outside_course_id.company_id.id not in \
                        self.env.companies.ids:
                    continue
                item = (grant.skill_level_id.level_progress or 0,
                        grant.outside_course_id.name or '', 'outside',
                        grant.outside_course_id.id)
            else:
                continue
            index.setdefault(grant.skill_id.id, []).append(item)
        for items in index.values():
            items.sort(key=lambda x: (-x[0], x[1]))
        return index

    @api.model
    def _person_skills(self, emp, index):
        """One person's required skills with their state, or None when their
        job requires nothing."""
        job = emp.job_id.sudo()
        required = job.current_job_skill_ids if job else []
        if not required:
            return None
        have = {s.skill_id.id: s for s in emp.current_employee_skill_ids}
        rows, gaps, ok = [], 0, 0
        for need in required:
            got = have.get(need.skill_id.id)
            want = need.skill_level_id.level_progress or 0
            if not got:
                state = 'missing'
            elif (got.level_progress or 0) >= want:
                state = 'ok'
            else:
                state = 'below'
            if state == 'ok':
                ok += 1
            else:
                gaps += 1
            courses = [{'kind': c[2], 'id': c[3], 'name': c[1]}
                       for c in index.get(need.skill_id.id, []) if c[0] >= want]
            rows.append({
                'skill_id': need.skill_id.id,
                'skill': need.skill_id.name or '',
                'level': need.skill_level_id.name or '',
                'have_level': got.skill_level_id.name if got else '',
                'state': state,
                'courses': courses[:3],
            })
        rows.sort(key=lambda r: ({'missing': 0, 'below': 1, 'ok': 2}[r['state']],
                                 fold(r['skill'])))
        return {'required': rows, 'gap_count': gaps, 'ok_count': ok}

    # =====================================================================
    #  the board
    # =====================================================================
    @api.model
    def skills_board(self, filters=None):
        if not self.can_see_skills():
            return {'allowed': False, 'people': [], 'by_skill': []}
        filters = filters or {}
        emps, team = self._skills_people()
        dept = as_id(filters.get('department_id'))
        if dept:
            covered = set(self.env['hr.department'].sudo().search(
                [('id', 'child_of', dept)]).ids)
            emps = emps.filtered(lambda e: e.department_id.id in covered)
        job = as_id(filters.get('job_id'))
        if job:
            emps = emps.filtered(lambda e: e.job_id.id == job)
        needle = fold(filters.get('q') or '')
        if needle:
            emps = emps.filtered(lambda e: needle in fold(e.name))
        skill = as_id(filters.get('skill_id'))
        index = self._grant_index()
        people, by_skill = [], {}
        total_req = total_ok = total_gaps = measured = 0
        for emp in emps.sorted(lambda e: fold(e.name)):
            facts = self._person_skills(emp, index)
            if not facts:
                continue
            if skill and skill not in [r['skill_id'] for r in
                                       facts['required']]:
                continue
            measured += 1
            total_req += len(facts['required'])
            total_ok += facts['ok_count']
            total_gaps += facts['gap_count']
            for row in facts['required']:
                agg = by_skill.setdefault(row['skill_id'], {
                    'skill_id': row['skill_id'], 'skill': row['skill'],
                    'employees': 0, 'ok': 0, 'below': 0, 'missing': 0,
                    'levels': {}, 'courses': row['courses']})
                agg['employees'] += 1
                agg[row['state']] += 1
                if row['have_level']:
                    agg['levels'][row['have_level']] = \
                        agg['levels'].get(row['have_level'], 0) + 1
            if filters.get('only_gaps') and not facts['gap_count']:
                continue
            people.append({
                'employee_id': emp.id,
                'employee': emp.name or '',
                'job': emp.job_id.name or '',
                'department': emp.department_id.name or '',
                'required': facts['required'],
                'gap_count': facts['gap_count'],
                'ok_count': facts['ok_count'],
            })
        people.sort(key=lambda p: (-p['gap_count'], fold(p['employee'])))
        rows = []
        for agg in by_skill.values():
            agg['coverage_pct'] = int(round(100.0 * agg['ok'] /
                                            agg['employees'])) \
                if agg['employees'] else 0
            agg['levels'] = [{'level': k, 'n': v}
                             for k, v in sorted(agg['levels'].items())]
            rows.append(agg)
        rows.sort(key=lambda r: (r['coverage_pct'], fold(r['skill'])))
        avg_req = (total_req / float(measured)) if measured else 0
        avg_ok = (total_ok / float(measured)) if measured else 0
        return {
            'allowed': True,
            'team': team,
            'can_close': self._can_write(),
            'people': people[:PEOPLE_CAP],
            'shown': min(len(people), PEOPLE_CAP),
            'matching': len(people),
            'by_skill': rows,
            'kpis': {'people': measured, 'gaps': total_gaps,
                     'avg_required': round(avg_req, 1),
                     'avg_ok': round(avg_ok, 1),
                     'missing': sum(r['missing'] for r in rows),
                     'below': sum(r['below'] for r in rows)},
            'headline': self._skills_headline(measured, avg_ok,
                                              avg_req, total_gaps),
            'lists': self._skills_lists(emps),
        }

    @api.model
    def _skills_headline(self, people, avg_ok, avg_req, gaps):
        if not people:
            return _("Nobody's job lists the skills it needs yet.")
        first = _("On average a person has %(have)s of %(need)s required "
                  "skills", have=int(round(avg_ok)), need=int(round(avg_req)))
        if not gaps:
            return _("%s · no gaps across %s people", first, people) \
                if people != 1 else _("%s · no gaps", first)
        gap_words = _("1 gap") if gaps == 1 else _("%s gaps", gaps)
        who = _("1 person") if people == 1 else _("%s people", people)
        return _("%(first)s · %(gaps)s across %(who)s", first=first,
                 gaps=gap_words, who=who)

    @api.model
    def _skills_lists(self, emps):
        jobs = emps.mapped('job_id').filtered(
            lambda j: j.current_job_skill_ids)
        depts = emps.mapped('department_id')
        skills = jobs.mapped('current_job_skill_ids.skill_id')
        return {
            'jobs': [{'id': j.id, 'name': j.name} for j in
                     jobs.sorted(lambda j: fold(j.name))],
            'departments': [{'id': d.id, 'name': d.name} for d in
                            depts.sorted(lambda d: fold(d.name))],
            'skills': [{'id': s.id, 'name': s.name} for s in
                       skills.sorted(lambda s: fold(s.name))],
        }

    @api.model
    def _skills_summary(self):
        """Numbers' Skills section: the by-skill table, worst first."""
        if not self._can_read():
            return {'rows': []}
        data = self.skills_board({})
        return {'rows': data.get('by_skill', [])[:15],
                'headline': data.get('headline', ''),
                'kpis': data.get('kpis', {})}

    # =====================================================================
    #  "Close it"
    # =====================================================================
    @api.model
    def close_gap(self, payload=None):
        """Our course → put it on the person (reason One-off); an outside
        course → an agreed request on their behalf. Training team only."""
        self._require_write()
        payload = payload or {}
        emp = self.env['hr.employee'].sudo().browse(
            as_id(payload.get('employee_id'))).exists()
        if not emp or emp.company_id.id not in self.env.companies.ids:
            raise UserError(_("Pick the person."))
        if payload.get('kind') == 'outside':
            return self.put_on_course({
                'employee_ids': [emp.id], 'kind': 'outside',
                'outside_course_id': as_id(payload.get('id')),
                'why': _("Closes a skills gap: %s",
                         payload.get('skill') or '')})
        res = self.env['pb.training.assignment'].assign_many(
            as_id(payload.get('id')), [emp.id], reason='adhoc')
        return {'message': res.get('message') or ''}

    @api.model
    def act(self, verb, payload=None):
        if verb == 'close_gap':
            return self.close_gap(payload or {})
        return super().act(verb, payload)


# =========================================================================
#  the learner
# =========================================================================
class PbMyTrainingL5(models.AbstractModel):
    _inherit = 'pb.my.training'

    @api.model
    def request_options(self):
        """What "Ask to take a course" offers: our courses open to requests
        that they are not already on or asking for, the outside list, and
        the allowance as they see it."""
        emp = self._my_employee()
        if not emp:
            return {'has_employee': False, 'ours': [], 'outside': []}
        Request = self.env['pb.training.request'].sudo()
        open_reqs = Request.search([('employee_id', '=', emp.id),
                                    ('state', 'in', ('draft', 'submitted',
                                                     'approved'))])
        busy_channels = set(open_reqs.mapped('channel_id').ids)
        busy_channels |= set(self.env['pb.training.assignment'].sudo().search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ('assigned', 'in_progress', 'overdue',
                             'excused'))]).mapped('channel_id').ids)
        partner = emp.user_id.partner_id
        if partner:
            busy_channels |= set(self.env['slide.channel.partner'].sudo()
                                 .search([('partner_id', '=', partner.id),
                                          ('member_status', 'in',
                                           ('joined', 'ongoing'))])
                                 .mapped('channel_id').ids)
        ours = self.env['slide.channel'].sudo().search([
            ('active', '=', True), ('is_published', '=', True),
            ('pb_requestable', '=', True)], order='name', limit=200)
        busy_outside = set(open_reqs.mapped('outside_course_id').ids)
        outside = self.env['pb.training.outside.course'].sudo().search([
            ('active', '=', True),
            ('company_id', 'in', (emp.company_id | self.env.companies).ids)],
            order='name', limit=200)
        facts = self.env['pb.training.claim'].sudo()._facts_for(
            emp, fields.Date.today().year)
        left = money_words(self.env, facts['left'], facts['currency'])
        committed = money_words(self.env, facts.get('committed', 0.0),
                                facts['currency'])
        if not facts['allowance']:
            words = _("No training allowance is set for this year, so only "
                      "free courses and ours can be agreed.")
        elif facts.get('committed'):
            words = _("Your training allowance for %(year)s: %(left)s left, "
                      "after %(set)s set aside for courses already agreed.",
                      year=facts['year'], left=left, set=committed)
        else:
            words = _("Your training allowance for %(year)s: %(left)s left.",
                      year=facts['year'], left=left)
        return {
            'has_employee': True,
            'manager': emp.parent_id.name or '',
            'ours': [{
                'id': c.id, 'name': c.name or '',
                'duration': duration_words(minutes(c._pb_hours()), self.env),
                'blurb': self._plain(c.description_short or '')[:200]
                if hasattr(self, '_plain') else '',
            } for c in ours if c.id not in busy_channels],
            'outside': [{
                'id': o.id, 'name': o.name or '',
                'provider': o.provider or '',
                'cost': o.cost or 0.0,
                'cost_words': o.cost_words(),
                'hours_words': o.hours_words(),
                'kind_word': tr(self.env, OUTSIDE_KIND_LABEL.get(o.kind, '')),
                'url': o.url or '',
                'blurb': o.blurb or '',
            } for o in outside if o.id not in busy_outside],
            'allowance': {
                'words': words,
                'set': bool(facts['allowance']),
                'year': facts['year'],
                'left': facts['left'],
                'left_words': money_words(self.env, facts['left'],
                                          facts['currency']),
                'committed_words': money_words(
                    self.env, facts.get('committed', 0.0), facts['currency'])
                if facts.get('committed') else '',
            },
        }

    @api.model
    def ask_course(self, values):
        return self.env['pb.training.request'].ask(values or {})

    @api.model
    def my_requests(self):
        emp = self._my_employee()
        if not emp:
            return {'has_employee': False, 'rows': []}
        rows = self.env['pb.training.request'].sudo().search(
            [('employee_id', '=', emp.id)], order='id desc', limit=60)
        return {'has_employee': True, 'rows': [r._payload() for r in rows],
                'waiting': len(rows.filtered(
                    lambda r: r.state == 'submitted'))}

    @api.model
    def cancel_request(self, request_id):
        emp = self._my_employee()
        rec = self.env['pb.training.request'].sudo().browse(
            as_id(request_id)).exists()
        if not rec or not emp or rec.employee_id != emp:
            raise AccessError(_("That request is not one of yours."))
        rec.action_cancel()
        return {'message': _("Cancelled. Nobody needs to decide it now.")}

    @api.model
    def claim_prefill(self, request_id):
        """The claim form, filled in from one of MY agreed requests."""
        emp = self._my_employee()
        if not emp:
            return {}
        req = self.env['pb.training.claim']._own_request(emp, request_id)
        if not req:
            return {}
        return {'request_id': req.id, 'course_name': req.course_name or '',
                'provider': req.provider or '',
                'amount': req.amount or 0.0,
                'amount_words': req.amount_words(),
                'words': _("This claim is for a course request that was "
                           "agreed. What it cost when you asked: %s.",
                           req.amount_words())}

    @api.model
    def my_skills(self):
        emp = self._my_employee()
        if not emp:
            return {'has_employee': False, 'skills': [], 'required': []}
        facts = self.env['pb.training']._person_skills(
            emp, self.env['pb.training']._grant_index()) or {}
        return {
            'has_employee': True,
            'job': emp.job_id.name or '',
            'skills': [{'skill': s.skill_id.name or '',
                        'level': s.skill_level_id.name or '',
                        'progress': s.level_progress or 0}
                       for s in emp.current_employee_skill_ids.sudo()
                       if not s.is_certification],
            'required': facts.get('required', []),
            'gap_count': facts.get('gap_count', 0),
        }

    @api.model
    def my_feedback(self):
        """Feedback the reader has been asked for and not given yet."""
        user = self.env.user
        rows = self.env['pb.feedback.request'].sudo().search([
            ('respondent_user_id', '=', user.id),
            ('kind', 'in', ('training', 'training_followup')),
            ('state', 'in', ('sent', 'extended')),
            '|', ('window_end', '=', False),
            ('window_end', '>=', fields.Date.today())],
            order='id desc', limit=10)
        return [{
            'id': r.id,
            'kind': r.kind,
            'words': _("Rate %s", r._pb_course_name())
            if r.kind == 'training' else _(
                "Has %(who)s's work changed since %(course)s?",
                who=r.subject_employee_id.sudo().name or '',
                course=r._pb_course_name()),
            'course': r._pb_course_name(),
            'about': r.subject_employee_id.sudo().name or '',
            'url': '/my/training/feedback/%s' % r.token,
        } for r in rows]

    @api.model
    def home(self):
        data = super().home()
        try:
            data['feedback'] = self.my_feedback()
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: feedback asks could not be read',
                            exc_info=True)
            data['feedback'] = []
        return data
