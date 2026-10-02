# -*- coding: utf-8 -*-
"""`pb.training` — the Training lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing number answers zero instead of taking the screen down, a row cap that
is a PARAMETER (right for a screen, wrong for a job — R76), and no sudo in a
read except where a field's own `groups=` forces it.

THE QUESTION THIS BOARD ANSWERS is "who still has to do what". So the order is
PROBLEM FIRST (R113): the courses with somebody on them who has not started,
then the ones where the test is failing, then the rest by name. A board sorted
by date is a board that hides the course fourteen people signed up for and
nobody opened.

WHY THE COURSES ARE NOT COMPANY-SCOPED. `slide.channel` has no `company_id` on
this build — a course is a piece of content, not a transaction, and the
content engine deliberately does not put one on it. So the BOARD is the whole
library and the PEOPLE PICKER is scoped to `self.env.companies`, which is where
the boundary actually matters: enrolling somebody is a statement about a
person, and a person belongs to a company. Said out loud here because a reader
who expects the usual `company_id in company_ids` clause and does not find one
should know it is absent on purpose.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from .training_common import (
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, P_COMPLETION_MAIL, P_COURSE_LIMIT,
    P_PEOPLE_LIMIT, as_id, counted, duration_words, flag, fold, minutes,
    number,
)

_logger = logging.getLogger(__name__)


class PbTraining(models.AbstractModel):
    _name = 'pb.training'
    _description = 'Payobook Training cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception:               # noqa: BLE001
            # WARNING with the traceback, never DEBUG: a swallowed exception
            # logged at debug level is invisible on a live server and the
            # caller gets a cheerful zero either way (R92).
            _logger.warning('pb_training: a board read failed', exc_info=True)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN))

    @api.model
    def _can_write(self):
        """Putting somebody on a course is the training team's own work.

        Not the manager tier: enrolling people IS the job the Trainer group
        exists for, and gating it a tier up meant the person doing the work
        could not press a single button on their own board (R-A1's
        `_can_recruit`, reached from the same direction).
        """
        return self._can_read()

    @api.model
    def _can_admin(self):
        return self.env.user.has_group(GROUP_ADMIN)

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_(
                "Training is looked after by the training team. Ask your HR "
                "administrator to add you to it."))

    @api.model
    def _require_write(self):
        self._require_read()

    # ==================================================================
    #  the board
    # ==================================================================
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'courses': [], 'kpis': {}}
        cap = number(self.env, P_COURSE_LIMIT)
        courses = self._safe(lambda: self._courses(cap), default=[])
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_admin': self._can_admin(),
            'courses': courses,
            'kpis': self._safe(lambda: self._kpis(courses), default={}),
            'completion_mail': flag(self.env, P_COMPLETION_MAIL),
        }

    def _courses(self, cap):
        channels = self.env['slide.channel'].search(
            [('active', '=', True)], limit=cap)
        rows = []
        for channel in channels:
            rows.append(self._course_row(channel))
        # PROBLEM FIRST. A course nobody has opened is the one somebody has to
        # do something about; a course everybody has finished is the one that
        # needs nothing. Within a band, by name, because that is how a person
        # looks a course up.
        return sorted(rows, key=lambda r: (r['rank'], r['name'].lower()))

    def _course_row(self, channel):
        sudo = channel.sudo()
        lessons = sudo._pb_lessons()
        test_slide = sudo._pb_test_slide()
        members = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', channel.id),
            ('member_status', '!=', 'invited'),
        ])
        not_started = len(members.filtered(lambda m: not m.completion))
        finished = len(members.filtered(
            lambda m: m.member_status == 'completed'))
        avg = int(round(sum(members.mapped('completion')) / len(members))) \
            if members else 0

        passed = failed = 0
        if test_slide:
            inputs = self.env['survey.user_input'].sudo().search([
                ('survey_id', '=', test_slide.survey_id.id),
                ('state', '=', 'done'),
                ('test_entry', '=', False),
                ('partner_id', 'in', members.mapped('partner_id').ids),
            ])
            winners = inputs.filtered('scoring_success').mapped('partner_id')
            passed = len(winners)
            failed = len(inputs.mapped('partner_id') - winners)

        if members and not_started == len(members):
            rank = 0                        # nobody has opened it
        elif test_slide and failed > passed:
            rank = 1                        # the test is beating people
        elif not lessons:
            rank = 2                        # a course with nothing in it
        elif not members:
            rank = 3                        # nobody is on it
        else:
            rank = 4

        return {
            'id': channel.id,
            'name': channel.name,
            'published': bool(channel.is_published),
            'lessons': len(lessons),
            'members': len(members),
            'not_started': not_started,
            'finished': finished,
            'average': avg,
            'has_test': bool(test_slide),
            'test_name': (test_slide.survey_id.title
                          if test_slide else ''),
            'test_id': test_slide.survey_id.id if test_slide else 0,
            'pass_mark': int(round(test_slide.survey_id.scoring_success_min))
            if test_slide else 0,
            'passed': passed,
            'failed': failed,
            'duration': duration_words(minutes(channel.total_time)),
            'rank': rank,
        }

    def _kpis(self, courses):
        members = sum(c['members'] for c in courses)
        taken = sum(c['passed'] + c['failed'] for c in courses)
        return {
            'courses': len(courses),
            'members': members,
            'finished': sum(c['finished'] for c in courses),
            'not_started': sum(c['not_started'] for c in courses),
            'passed': sum(c['passed'] for c in courses),
            'taken': taken,
            'pass_rate': int(round(
                100.0 * sum(c['passed'] for c in courses) / taken))
            if taken else None,
        }

    # ==================================================================
    #  one course, opened
    # ==================================================================
    @api.model
    def get_course(self, channel_id):
        self._require_read()
        channel = self.env['slide.channel'].browse(as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        sudo = channel.sudo()
        Slide = self.env['slide.slide']
        lessons = [{
            'id': s.id,
            'name': s.name,
            'kind_word': Slide._pb_kind_word(s.slide_category),
            'icon': Slide._pb_kind_icon(s.slide_category),
            'duration': duration_words(minutes(s.completion_time)),
            'quiz': bool(s.question_ids),
            'section': s.category_id.name if s.category_id else '',
        } for s in sudo._pb_lessons()]

        test_slide = sudo._pb_test_slide()
        test = None
        if test_slide:
            survey = test_slide.survey_id.sudo()
            test = {
                'id': survey.id,
                'name': survey.title,
                'pass_mark': int(round(survey.scoring_success_min or 0)),
                'attempts': int(survey.attempts_limit or 0)
                if survey.is_attempts_limited else 0,
                'time_limit': int(round(survey.time_limit or 0))
                if survey.is_time_limited else 0,
                # `question_count` and never `len(question_ids)`:
                # `question_ids` is a NON-STORED COMPUTE over
                # `question_and_page_ids`, and the engine keeps the count
                # beside it for exactly this reason.
                'questions': survey.question_count,
                'certificate': bool(survey.certification),
            }

        people = self._safe(lambda: self._members(sudo, test_slide),
                            default=[])
        return {
            'id': channel.id,
            'name': channel.name,
            'published': bool(channel.is_published),
            'lessons': lessons,
            'test': test,
            'people': people,
            'can_write': self._can_write(),
        }

    def _members(self, channel, test_slide):
        rows = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', channel.id),
            ('member_status', '!=', 'invited'),
        ])
        results = {}
        if test_slide:
            for attempt in self.env['survey.user_input'].sudo().search([
                    ('survey_id', '=', test_slide.survey_id.id),
                    ('state', '=', 'done'),
                    ('test_entry', '=', False),
                    ('partner_id', 'in', rows.mapped('partner_id').ids)],
                    order='create_date asc'):
                # The BEST result stands, never the latest: somebody who
                # passed and then opened the test again out of curiosity has
                # still passed it.
                key = attempt.partner_id.id
                if results.get(key) != 'passed':
                    results[key] = 'passed' if attempt.scoring_success \
                        else 'failed'
        out = []
        for row in rows:
            out.append({
                'id': row.id,
                'partner_id': row.partner_id.id,
                'name': row.partner_id.name,
                'percent': int(row.completion or 0),
                'done': int(row.completed_slides_count or 0),
                'status': row.member_status,
                'test': results.get(row.partner_id.id, ''),
            })
        return sorted(out, key=lambda r: (r['percent'], r['name'].lower()))

    # ==================================================================
    #  putting people on a course
    # ==================================================================
    @api.model
    def search_people(self, term, channel_id=0):
        """The people picker. Accent-blind, company-scoped, capped.

        Folded in PYTHON and never with an `ilike` domain: Postgres on this
        box has no `unaccent` extension, so `ilike '%bui%'` does not find
        "Bùi" and about four and a half thousand of the five thousand people
        here have an accent in their name (R78). And `search_read` of two
        columns rather than `search` of records, because reading one field of
        an `hr.employee` reads forty and about forty of them sit behind
        payroll groups (R56).
        """
        self._require_read()
        needle = fold(term or '')
        rows = self.env['hr.employee'].sudo().search_read(
            [('company_id', 'in', self.env.companies.ids),
             ('active', '=', True)],
            ['name', 'work_email', 'user_id', 'company_id'])
        already = set()
        if channel_id:
            channel = self.env['slide.channel'].sudo().browse(
                as_id(channel_id)).exists()
            if channel:
                already = set(self.env['slide.channel.partner'].sudo().search([
                    ('channel_id', '=', channel.id)]).mapped('partner_id').ids)
        cap = number(self.env, P_PEOPLE_LIMIT)
        out = []
        for row in rows:
            if needle and needle not in fold(row['name']):
                continue
            partner = self._partner_of(row)
            if not partner:
                continue
            out.append({
                'id': row['id'],
                'name': row['name'],
                'partner_id': partner,
                'email': row.get('work_email') or '',
                'on_it': partner in already,
            })
            if len(out) >= cap:
                break
        return sorted(out, key=lambda r: fold(r['name']))

    def _partner_of(self, row):
        """The partner a membership hangs off, for one employee row.

        THE LOGIN'S PARTNER AND NOT THE EMPLOYEE'S WORK CONTACT. The content
        engine keys membership on a partner and every learner page resolves
        "me" as `env.user.partner_id`, so enrolling the work contact of
        somebody whose login has a different partner puts a course on a page
        they will never see. Somebody with no login gets no partner and is
        therefore not offered — said plainly on the screen rather than
        silently enrolled into nothing.
        """
        user_id = row.get('user_id')
        if not user_id:
            return 0
        uid = user_id[0] if isinstance(user_id, (list, tuple)) else user_id
        user = self.env['res.users'].sudo().browse(int(uid)).exists()
        return user.partner_id.id if user and user.partner_id else 0

    @api.model
    def enrol(self, channel_id, employee_ids):
        """Put people on a course. Idempotent, and it says what it did."""
        self._require_write()
        channel = self.env['slide.channel'].browse(as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        ids = [as_id(e) for e in (employee_ids or []) if as_id(e)]
        if not ids:
            raise UserError(_("Pick at least one person."))
        rows = self.env['hr.employee'].sudo().search_read(
            [('id', 'in', ids),
             ('company_id', 'in', self.env.companies.ids)],
            ['name', 'user_id'])
        partner_ids, without_login = [], []
        for row in rows:
            partner = self._partner_of(row)
            if partner:
                partner_ids.append(partner)
            else:
                without_login.append(row['name'])
        if not partner_ids:
            raise UserError(_(
                "None of those people has a login yet, so there is nowhere to "
                "put the course. Ask for their Payobook accounts first."))
        partners = self.env['res.partner'].sudo().browse(partner_ids)
        before = set(self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', channel.id),
            ('partner_id', 'in', partner_ids)]).mapped('partner_id').ids)
        channel.sudo()._action_add_members(partners)
        added = len([p for p in partner_ids if p not in before])
        message = _("%(n)s %(word)s now on this course.",
                    n=added, word=counted(added, _('person is'),
                                          _('people are')))
        if not added:
            message = _("Everybody you picked was already on it.")
        if without_login:
            message = '%s %s' % (message, _(
                "%s has no login yet and was left out.",
                ', '.join(without_login[:5])))
        return {'added': added, 'skipped': without_login, 'message': message}

    @api.model
    def unenrol(self, channel_id, partner_ids):
        """Take somebody off a course. Their progress is kept, not deleted."""
        self._require_write()
        channel = self.env['slide.channel'].browse(as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        ids = [as_id(p) for p in (partner_ids or []) if as_id(p)]
        if not ids:
            raise UserError(_("Pick at least one person."))
        channel.sudo()._remove_membership(ids)
        return {'removed': len(ids), 'message': _(
            "Taken off the course. What they had already done is kept, so "
            "putting them back on picks up where they left off.")}

    # ==================================================================
    #  the doors
    # ==================================================================
    @api.model
    def open_course(self, channel_id):
        """The course, on its own form. R125: a hand-built act_window dict
        MUST carry `views`, or the client throws before the screen opens."""
        self._require_read()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Course"),
            'res_model': 'slide.channel',
            'res_id': as_id(channel_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    @api.model
    def open_test(self, survey_id):
        self._require_read()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Test"),
            'res_model': 'survey.survey',
            'res_id': as_id(survey_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    @api.model
    def new_course(self):
        """A blank course, with the two things this product insists on.

        `visibility = 'members'` and `enroll = 'invite'` because a course made
        here is for the people the training team puts on it, and the engine's
        own default is a PUBLIC course on a public web site. And
        `completed_template_id` is emptied while the completion-mail switch is
        off, so nothing leaves the building from a template nobody has
        written (R54: a switch that is off and does not say so is reported as
        broken — the board says so).
        """
        self._require_write()
        context = {
            'default_channel_type': 'training',
            'default_visibility': 'members',
            'default_enroll': 'invite',
        }
        if not flag(self.env, P_COMPLETION_MAIL):
            context['default_completed_template_id'] = False
        return {
            'type': 'ir.actions.act_window',
            'name': _("New course"),
            'res_model': 'slide.channel',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
            'context': context,
        }

    @api.model
    def new_test(self):
        """A blank test, already a scored certification.

        A certification with no scoring type is refused by the engine's own
        constraint, so defaulting one is the difference between a form that
        saves and a form that argues.
        """
        self._require_write()
        return {
            'type': 'ir.actions.act_window',
            'name': _("New test"),
            'res_model': 'survey.survey',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
            'context': {
                # `survey_type` is survey / live_session / assessment /
                # custom on this build — a test is an ASSESSMENT that also
                # carries the `certification` flag. There is no
                # "certification" survey type, and writing one is a hard
                # ValueError on create rather than a quiet fallback.
                'default_survey_type': 'assessment',
                'default_certification': True,
                'default_scoring_type': 'scoring_with_answers',
                'default_scoring_success_min': 70,
                'default_users_login_required': True,
                'default_access_mode': 'token',
                'default_is_attempts_limited': True,
                'default_attempts_limit': 3,
            },
        }

    @api.model
    def open_courses(self):
        self._require_read()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Courses"),
            'res_model': 'slide.channel',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
        }

    @api.model
    def open_questions(self):
        """The question bank — every question in the library, reusable."""
        self._require_read()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Questions"),
            'res_model': 'survey.question',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
        }

    # ==================================================================
    #  the one verb the board calls
    # ==================================================================
    #: Everything the cockpit may ask for, by name. A public dispatcher that
    #: forwarded any attribute would be a remote-execution hole with a
    #: friendly name on it.
    _VERBS = ('enrol', 'unenrol', 'open_course', 'open_test', 'new_course',
              'new_test', 'open_courses', 'open_questions')

    @api.model
    def act(self, verb, payload=None):
        if verb not in self._VERBS:
            raise UserError(_("%s is not something this screen can do.", verb))
        payload = payload or {}
        if verb == 'enrol':
            return self.enrol(payload.get('channel_id'),
                              payload.get('employee_ids'))
        if verb == 'unenrol':
            return self.unenrol(payload.get('channel_id'),
                                payload.get('partner_ids'))
        if verb == 'open_course':
            return self.open_course(payload.get('channel_id'))
        if verb == 'open_test':
            return self.open_test(payload.get('survey_id'))
        return getattr(self, verb)()
