# -*- coding: utf-8 -*-
"""`pb.my.training` — everything the employee's own training pages read and
write, in ONE place.

WHY ONE PLACE. The portal controller renders six pages and the test suite
exercises the same six journeys; written in the controller, half of it would
be unreachable from a test and the other half would be duplicated in it. So
the controller does exactly two things — it proves who is asking, and it
renders — and every fact on every page comes from here.

WHO "ME" IS, AND WHY IT IS NEVER A PARAMETER. The content engine's membership
key is a PARTNER (`slide.channel.partner`), not an employee, so "me" is
`self.env.user.partner_id` and it is resolved fresh on every call. No method
here takes a partner or an employee id, which means there is no URL anybody
can craft that puts them on somebody else's course or marks somebody else's
lesson done. The employee record is read for the name and nothing else.

WHY EVERYTHING IS SUDO AFTER THAT. A portal user cannot read
`slide.channel.partner`, `slide.slide.partner` or `survey.user_input` in their
own right and should not be given the ability — the ACL that let them read
their own row would let them read the row beside it. The doctrine
`pb_me_portal` set is: the ROUTE is the gate, ownership is proved from the
session, and everything past that point is sudo over records already narrowed
to the caller. Every search below carries `partner_id = <me>` in its domain,
written out, so the narrowing is visible rather than assumed.

THE ONE THING THAT IS NOT SUDO is the two writes the content engine has to
make as the learner: `_action_mark_completed` reads `self.env.user.partner_id`
itself and `_action_set_quiz_done` refuses outright for a non-member, so both
run `with_user(self.env.user)` over a slide the caller has already been proved
to be enrolled on. Running those under sudo would mark the SUPERUSER's lesson
done — silently, and on the wrong row.
"""

import logging
import re

from markupsafe import Markup

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from .training_common import (
    TEST_FAILED, TEST_LOCKED, TEST_NONE, TEST_PASSED, TEST_READY,
    as_id, counted, duration_words, minutes,
)

_logger = logging.getLogger(__name__)


class PbMyTraining(models.AbstractModel):
    _name = 'pb.my.training'
    _description = 'Payobook Training — the employee\'s own pages'

    # ==================================================================
    #  who is asking
    # ==================================================================
    @api.model
    def _me(self):
        """The session user's partner. The membership key, and the only one."""
        return self.env.user.partner_id

    @api.model
    def _employee(self):
        """Their employee record, read AS THE SYSTEM and narrowly.

        Reading one field of an `hr.employee` reads forty, and about forty of
        them sit behind payroll groups, so an ordinary employee asking for
        their own name gets an AccessError naming thirty fields nobody asked
        for (R56). Only the name is wanted here, and only for the greeting.
        """
        user = self.env.user
        emp = self.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)], limit=1)
        return emp

    # ==================================================================
    #  the courses this person is on
    # ==================================================================
    @api.model
    def _memberships(self):
        """Their live rows, newest first.

        `invited` is deliberately excluded: an invitation is an offer to join
        a course, not a course somebody is on, and putting one on a page
        headed "Your training" would be the page telling somebody they have
        work they have not got.
        """
        me = self._me()
        if not me:
            return self.env['slide.channel.partner'].sudo().browse()
        rows = self.env['slide.channel.partner'].sudo().search([
            ('partner_id', '=', me.id),
            ('member_status', '!=', 'invited'),
        ])
        return rows.filtered(
            lambda r: r.channel_id.active and r.channel_id.is_published
        ).sorted(lambda r: (r.member_status == 'completed', r.channel_id.name))

    @api.model
    def home(self):
        """Everything `/my/training` puts on the screen, in one read."""
        me = self._me()
        rows = self._memberships()
        courses = [self._tile(row) for row in rows]
        in_progress = len([c for c in courses if not c['finished']])
        finished = len([c for c in courses if c['finished']])
        passed = len([c for c in courses if c['test'] == TEST_PASSED])
        emp = self._employee()
        return {
            'partner_id': me.id if me else 0,
            'name': (emp.name if emp else '') or (me.name if me else ''),
            'courses': courses,
            'in_progress': in_progress,
            'finished': finished,
            'passed': passed,
            'total': len(courses),
        }

    @api.model
    def home_count(self):
        """The number on the portal home card. Cheap, and never raises."""
        try:
            return len(self._memberships())
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the training count could not be '
                            'read', exc_info=True)
            return 0

    def _tile(self, row):
        """One course, as the tile on the front page sees it."""
        channel = row.channel_id.sudo()
        lessons = channel._pb_lessons()
        done_ids = channel._pb_done_ids(row.partner_id)
        done = len([s for s in lessons if s.id in done_ids])
        total = len(lessons)
        test_slide = channel._pb_test_slide()
        state, score = self._test_state(channel, row, test_slide, total - done)
        nxt = row.next_slide_id
        # The NEXT lesson is the engine's own answer (it is a stored compute
        # over "published, active, not a category, not finished"), except that
        # it does not know the certification slide is not a lesson. So a
        # course whose lessons are all done answers the test slide, and
        # "Continue" would send somebody into a test the page has just told
        # them is locked.
        if nxt and test_slide and nxt.id == test_slide.id:
            nxt = self.env['slide.slide'].sudo().browse()
        return {
            'id': channel.id,
            'name': channel.name,
            'blurb': self._plain(channel.description_short
                                 or channel.description),
            'done': done,
            'total': total,
            'left': total - done,
            'percent': int(round(100.0 * done / total)) if total else 0,
            'finished': bool(total) and done >= total
            and state in (TEST_PASSED, TEST_NONE),
            'test': state,
            'score': score,
            'next_id': nxt.id if nxt else 0,
            'next_name': nxt.name if nxt else '',
            'duration': duration_words(minutes(channel.total_time)),
        }

    @api.model
    def _plain(self, html):
        """An Html field, as one line of plain words.

        The course editor is a rich-text box, so `description_short` arrives
        with markup in it. A tile that handed that to `t-esc` would print the
        tags and one that handed it to `t-out` would let a course description
        write into the page (R51 from both sides). Tags out, entities in,
        trimmed.
        """
        raw = html or ''
        if isinstance(raw, Markup):
            raw = str(raw)
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = (text.replace('&nbsp;', ' ').replace('&amp;', '&')
                .replace('&lt;', '<').replace('&gt;', '>')
                .replace('&#39;', "'").replace('&quot;', '"'))
        text = ' '.join(text.split())
        return text[:239] + '…' if len(text) > 240 else text

    # ==================================================================
    #  the test at the end
    # ==================================================================
    def _attempts(self, channel, row, test_slide):
        """Every real attempt this person has made, newest first."""
        if not test_slide or not test_slide.survey_id:
            return self.env['survey.user_input'].sudo().browse()
        return self.env['survey.user_input'].sudo().search([
            ('survey_id', '=', test_slide.survey_id.id),
            ('partner_id', '=', row.partner_id.id),
            ('test_entry', '=', False),
        ], order='create_date desc, id desc')

    def _test_state(self, channel, row, test_slide, left):
        """(state, score) for the chip beside a course.

        PASSED beats everything, including "there are lessons left": somebody
        who has passed the test and then had a lesson added to the course has
        still passed the test, and telling them otherwise would be the screen
        arguing with a certificate they are holding.
        """
        if not test_slide:
            return TEST_NONE, None
        attempts = self._attempts(channel, row, test_slide)
        done = attempts.filtered(lambda a: a.state == 'done')
        winner = done.filtered('scoring_success')
        if winner:
            return TEST_PASSED, int(round(winner[0].scoring_percentage or 0))
        if left > 0:
            return TEST_LOCKED, None
        if done:
            return TEST_FAILED, int(round(done[0].scoring_percentage or 0))
        return TEST_READY, None

    def _attempts_left(self, survey, partner, token):
        """How many goes are left, or None when there is no limit."""
        if not survey.is_attempts_limited:
            return None
        try:
            return max(survey.sudo()._get_number_of_attempts_lefts(
                partner, partner.email, token), 0)
        except Exception:               # noqa: BLE001 — a count is never fatal
            _logger.warning('pb_training: the attempts left could not be '
                            'counted for survey %s', survey.id, exc_info=True)
            return None

    # ==================================================================
    #  one course
    # ==================================================================
    @api.model
    def _mine(self, channel_id):
        """The course and this person's row on it, or (empty, empty).

        THE MEMBERSHIP IS THE PROOF and it is re-asked on every request. A
        course id in the URL buys nothing: an id for a course they are not on,
        an archived course, an unpublished one and an id that is not a course
        at all are all answered the same way, by the caller, with a sentence.
        """
        channel = self.env['slide.channel'].sudo().browse(
            as_id(channel_id)).exists()
        me = self._me()
        if not channel or not me or not channel.active \
                or not channel.is_published:
            return (self.env['slide.channel'].sudo().browse(),
                    self.env['slide.channel.partner'].sudo().browse())
        row = channel._pb_membership(me)
        if not row or row.member_status == 'invited':
            return (self.env['slide.channel'].sudo().browse(),
                    self.env['slide.channel.partner'].sudo().browse())
        return channel, row

    @api.model
    def course(self, channel_id):
        """One course page. `None` when it is not theirs — never a traceback."""
        channel, row = self._mine(channel_id)
        if not channel:
            return None
        lessons = channel._pb_lessons()
        done_ids = channel._pb_done_ids(row.partner_id)
        test_slide = channel._pb_test_slide()
        left = len([s for s in lessons if s.id not in done_ids])
        state, score = self._test_state(channel, row, test_slide, left)

        # The list, grouped under the headings the training team typed. A
        # course with no headings is ONE unnamed group, because a page that
        # draws an empty heading over every lesson looks broken and a page
        # that drops the grouping for one course looks like two products.
        groups, seen = [], {}
        for slide in lessons:
            key = slide.category_id.id or 0
            if key not in seen:
                seen[key] = {
                    'id': key,
                    'name': slide.category_id.name if slide.category_id else '',
                    'lessons': [],
                }
                groups.append(seen[key])
            seen[key]['lessons'].append(self._row(slide, slide.id in done_ids))

        test = None
        if test_slide:
            survey = test_slide.survey_id.sudo()
            attempts = self._attempts(channel, row, test_slide)
            token = attempts[0].invite_token if attempts else False
            test = {
                'slide_id': test_slide.id,
                'name': test_slide.name or survey.title,
                'state': state,
                'score': score,
                'pass_mark': int(round(survey.scoring_success_min or 0)),
                'attempts_left': self._attempts_left(
                    survey, row.partner_id, token),
                'time_limit': int(round(survey.time_limit or 0))
                if survey.is_time_limited else 0,
                # The engine's own count. `question_ids` is a non-stored
                # compute over `question_and_page_ids`, so counting it by
                # hand is both slower and one refactor away from wrong.
                'questions': survey.question_count,
                'certificate': bool(survey.certification)
                and state == TEST_PASSED,
                'left_words': counted(left, _('one lesson'),
                                      _('%s lessons') % left),
            }

        return {
            'id': channel.id,
            'name': channel.name,
            'blurb': self._plain(channel.description_short),
            'description': channel.description_html or channel.description,
            'groups': groups,
            'done': len(lessons) - left,
            'total': len(lessons),
            'left': left,
            'percent': int(round(100.0 * (len(lessons) - left) / len(lessons)))
            if lessons else 0,
            'duration': duration_words(minutes(channel.total_time)),
            'next_id': next((s.id for s in lessons
                             if s.id not in done_ids), 0),
            'test': test,
        }

    def _row(self, slide, done):
        """One lesson, as a line on the course page."""
        Slide = self.env['slide.slide']
        return {
            'id': slide.id,
            'name': slide.name,
            'kind': slide.slide_category,
            'kind_word': Slide._pb_kind_word(slide.slide_category),
            'icon': Slide._pb_kind_icon(slide.slide_category),
            'done': done,
            'duration': duration_words(minutes(slide.completion_time)),
            'quiz': bool(slide.sudo().question_ids),
        }

    # ==================================================================
    #  one lesson
    # ==================================================================
    @api.model
    def lesson(self, channel_id, slide_id):
        """One lesson page. `None` for anything that is not theirs.

        A FORGED SLIDE ID FROM ANOTHER COURSE IS THE SAME REFUSAL as a forged
        course id, and it is caught here rather than by the page: the slide
        has to belong to the course whose membership was just proved.
        """
        channel, row = self._mine(channel_id)
        if not channel:
            return None
        lessons = channel._pb_lessons()
        slide = lessons.filtered(lambda s: s.id == as_id(slide_id))[:1]
        if not slide:
            return None
        slide = slide.sudo()
        done_ids = channel._pb_done_ids(row.partner_id)
        order = list(lessons)
        idx = order.index(slide)
        prev = order[idx - 1] if idx > 0 else None
        nxt = order[idx + 1] if idx + 1 < len(order) else None
        Slide = self.env['slide.slide']

        payload = {
            'channel_id': channel.id,
            'channel_name': channel.name,
            'id': slide.id,
            'name': slide.name,
            'kind': slide.slide_category,
            'kind_word': Slide._pb_kind_word(slide.slide_category),
            'icon': Slide._pb_kind_icon(slide.slide_category),
            'duration': duration_words(minutes(slide.completion_time)),
            'done': slide.id in done_ids,
            'position': idx + 1,
            'total': len(order),
            'prev_id': prev.id if prev else 0,
            'prev_name': prev.name if prev else '',
            'next_id': nxt.id if nxt else 0,
            'next_name': nxt.name if nxt else '',
            'quiz': bool(slide.question_ids),
            'questions': [],
            'embed': '',
            'pdf_url': '',
            'image_url': '',
            'article': '',
            'description': self._plain(slide.description),
        }

        # WHAT IS ACTUALLY ON THE PAGE, by kind. The video and Google-Drive
        # players come from the content engine's own `embed_code`, which is
        # computed Html and already carries the no-cookie YouTube host, the
        # Vimeo player and the Drive preview — three iframe shapes and their
        # id-extraction regexes that would otherwise be re-derived here and
        # then be wrong the day one of them changes.
        if slide.slide_category == 'video':
            payload['embed'] = slide.embed_code or ''
        elif slide.slide_category == 'document':
            if slide.source_type == 'local_file' and slide.binary_content:
                payload['pdf_url'] = '/slides/slide/%s/pdf_content' % slide.id
            else:
                payload['embed'] = slide.embed_code or ''
        elif slide.slide_category == 'infographic':
            payload['image_url'] = '/slides/slide/%s/get_image?field=image_1024' \
                % slide.id
        elif slide.slide_category == 'article':
            payload['article'] = slide.html_content or ''

        if slide.question_ids:
            payload['questions'] = [{
                'id': q.id,
                'text': q.question,
                'answers': [{'id': a.id, 'text': a.text_value}
                            for a in q.answer_ids],
            } for q in slide.question_ids.sorted(
                lambda q: (q.sequence, q.id))]

        return payload

    # ==================================================================
    #  the two writes
    # ==================================================================
    @api.model
    def mark_done(self, channel_id, slide_id):
        """"I have watched/read this." Refused for a lesson with questions.

        The content engine says the same thing through
        `can_self_mark_completed`, and it is right to: a lesson somebody has
        to ANSWER is not finished because they pressed a button.
        """
        channel, row = self._mine(channel_id)
        if not channel:
            raise AccessError(_("That course is not one of yours."))
        slide = channel._pb_lessons().filtered(
            lambda s: s.id == as_id(slide_id))[:1]
        if not slide:
            raise AccessError(_("That lesson is not part of this course."))
        if slide.sudo().question_ids:
            raise UserError(_(
                "This one has questions in it — answer them and it marks "
                "itself done."))
        self._complete(slide, row)
        return True

    def _complete(self, slide, row):
        """Mark one slide finished FOR THE PERSON WHO IS ASKING.

        `_action_mark_completed` takes its partner from `self.env.user` and
        `_action_set_quiz_done` refuses outright for somebody who is not a
        member — so both run as the session user over a slide whose
        membership has already been proved. Under sudo the first would write
        the superuser's row and the second would pass its own check while
        doing it, which is a lesson marked done on the wrong person with
        nothing anywhere to say so.
        """
        me = self.env.user
        slide.sudo()._action_set_viewed(row.partner_id)
        slide.with_user(me)._action_mark_completed()
        # The completion percentage and `member_status` are the membership
        # row's own, and nothing recomputes them on a write to a slide.
        row.sudo()._recompute_completion()
        row.invalidate_recordset()

    @api.model
    def answer_quiz(self, channel_id, slide_id, answer_ids):
        """Grade a quiz lesson HERE, against `slide.answer.is_correct`.

        Never in the browser and never from what the form sent back: an
        answer key that crosses the wire is an answer key, and a quiz whose
        marking a learner can read is not a quiz. The form sends chosen
        answer ids and nothing else.

        A WRONG ANSWER IS NOT A FAILURE. The lesson stays open, the questions
        they got wrong are named, and they try again — which is what a quiz
        inside a lesson is for. Only all-correct marks the lesson done.
        """
        channel, row = self._mine(channel_id)
        if not channel:
            raise AccessError(_("That course is not one of yours."))
        slide = channel._pb_lessons().filtered(
            lambda s: s.id == as_id(slide_id))[:1]
        if not slide:
            raise AccessError(_("That lesson is not part of this course."))
        questions = slide.sudo().question_ids.sorted(
            lambda q: (q.sequence, q.id))
        if not questions:
            raise UserError(_("This lesson has no questions in it."))

        chosen = {as_id(a) for a in (answer_ids or []) if as_id(a)}
        wrong, right, unanswered = [], [], []
        for question in questions:
            picked = question.answer_ids.filtered(lambda a: a.id in chosen)
            if not picked:
                unanswered.append(question.id)
            elif len(picked) == 1 and picked.is_correct:
                right.append(question.id)
            else:
                wrong.append(question.id)

        # The attempt is counted whatever the outcome — that is what the
        # training team's "how many goes did this take" number is made of.
        slide.sudo()._action_set_viewed(row.partner_id, quiz_attempts_inc=True)

        if wrong or unanswered:
            return {
                'passed': False,
                'wrong': wrong,
                'unanswered': unanswered,
                'right': right,
                'message': _("Not quite. Have another look at the ones "
                             "marked below.") if wrong
                else _("Answer every question and try again."),
            }
        self._complete(slide, row)
        return {'passed': True, 'wrong': [], 'unanswered': [],
                'right': right,
                'message': _("All correct — that lesson is done.")}

    # ==================================================================
    #  the test
    # ==================================================================
    @api.model
    def start_test(self, channel_id):
        """Where to send somebody who pressed "Take the test".

        Returns `{'url': …}` or `{'problem': <a sentence>}`. Never raises for
        a refusal a person can do something about: "you have three lessons
        left" is an answer, and a traceback is not.

        THE ATTEMPT POOL IS THE FIRST ATTEMPT'S TOKEN. The engine counts
        attempts within an `invite_token`, and minting a fresh one per go
        would make "3 attempts" mean "as many as you like" — so every retry
        rides the token the first attempt was created with.
        """
        channel, row = self._mine(channel_id)
        if not channel:
            return {'code': 'mine'}
        test_slide = channel._pb_test_slide()
        if not test_slide:
            return {'code': 'no_test'}
        left = channel._pb_lessons_left(row.partner_id)
        if left:
            return {'code': 'locked', 'left': left}

        survey = test_slide.survey_id.sudo()
        # The learner's own row on the certification slide. The engine wants
        # one to hang the attempt off, and it is what makes a pass mark the
        # lesson complete.
        test_slide.sudo()._action_set_viewed(row.partner_id)
        membership = self.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', test_slide.id),
            ('partner_id', '=', row.partner_id.id),
        ], limit=1)

        attempts = self._attempts(channel, row, test_slide)
        live = attempts.filtered(lambda a: a.state != 'done')
        if live:
            return {'url': live[0].get_start_url()}
        if attempts.filtered('scoring_success'):
            return {'code': 'already_passed'}

        token = attempts[0].invite_token if attempts else \
            self.env['survey.user_input']._generate_invite_token()
        if not survey._has_attempts_left(row.partner_id,
                                         row.partner_id.email, token):
            return {'code': 'no_attempts'}
        try:
            answer = survey._create_answer(
                partner=row.partner_id, check_attempts=False,
                invite_token=token, slide_id=test_slide.id,
                slide_partner_id=membership.id if membership else False)
        except Exception:               # noqa: BLE001 — never a traceback here
            _logger.warning('pb_training: an attempt at survey %s could not '
                            'be opened for partner %s', survey.id,
                            row.partner_id.id, exc_info=True)
            return {'code': 'denied'}
        return {'url': answer.get_start_url()}

    @api.model
    def certificate_url(self, channel_id):
        """The certificate, or a sentence.

        `/survey/<id>/get_certification` is `auth='user'` and a portal user is
        a user, so the engine's own route serves the PDF — and it re-asks the
        one question that matters (did THIS person pass) before it does.
        """
        channel, row = self._mine(channel_id)
        if not channel:
            return {'code': 'mine'}
        test_slide = channel._pb_test_slide()
        if not test_slide:
            return {'code': 'no_test'}
        survey = test_slide.survey_id.sudo()
        if not survey.certification:
            return {'code': 'no_certificate'}
        if not self._attempts(channel, row, test_slide).filtered(
                'scoring_success'):
            return {'code': 'not_passed_yet'}
        return {'url': '/survey/%s/get_certification' % survey.id}
