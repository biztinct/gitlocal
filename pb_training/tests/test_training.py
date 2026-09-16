# -*- coding: utf-8 -*-
"""RIZE W2 E1 — the rails that must not quietly stop working.

The live Chrome run is what proves the pages render; these are the floor.
Every one of them is written against a failure this module could have and that
nothing at runtime would report:

  * a test that unlocks one lesson early is a certificate somebody did not
    earn, and the screen would look perfectly normal while handing it over;
  * a quiz graded in the browser is a quiz whose answers a learner can read;
  * a membership check that trusts the id in the URL is somebody else's
    training on your screen, and nothing anywhere would say so;
  * a gate on the public course site that also gates the PDF route takes the
    learner's own lesson page down and leaves a blank grey box behind;
  * two adjacent string literals in a JS file blank the entire backend asset
    bundle for every user, with a clean server log.

WHY THE FIXTURES ARE NAMED "DEMO". Everything this suite creates is rolled
back with the transaction, but the names are the live convention anyway
(ledger rule 9): a fixture copied into a live script keeps the name it was
written with, and a fixture called "RIZE test" is how the customer's name ends
up on a screen somebody is shown.
"""

import base64
import re

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")

#: A one-page PDF, small enough to live in a source file.
_PDF = base64.b64encode(
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n")


def _src(*parts):
    path = get_module_path('pb_training')
    with open(path + '/' + '/'.join(parts), encoding='utf-8') as fh:
        return fh.read()


class TrainingCase(TransactionCase):
    """One course, four lessons, a test, and one learner on it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Channel = cls.env['slide.channel']
        cls.Slide = cls.env['slide.slide']
        cls.My = cls.env['pb.my.training']
        cls.Board = cls.env['pb.training']

        # NO SIGNUP EMAIL. `res.users.create` sends one by default, and on
        # this box a queued mail goes out within the second (R47) — the
        # addresses are @example.com, but a test that posts mail is a test
        # that will one day post it somewhere real.
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.learner = Users.create({
            'name': 'DEMO Learner One',
            'login': 'demo.learner.one@example.com',
            'email': 'demo.learner.one@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.other = Users.create({
            'name': 'DEMO Learner Two',
            'login': 'demo.learner.two@example.com',
            'email': 'demo.learner.two@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

        cls.course = cls.Channel.create({
            'name': 'DEMO Agronomist basics',
            'channel_type': 'training',
            'visibility': 'members',
            'enroll': 'invite',
            # The stock per-course "you finished" mail is a template nobody
            # here has written; the switch that would turn it on ships off.
            'completed_template_id': False,
            'is_published': True,
        })
        cls.video = cls.Slide.create({
            'name': 'DEMO Soil, in four minutes',
            'channel_id': cls.course.id,
            'slide_category': 'video',
            'source_type': 'external',
            'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'is_published': True,
            'sequence': 1,
        })
        cls.doc = cls.Slide.create({
            'name': 'DEMO The field handbook',
            'channel_id': cls.course.id,
            'slide_category': 'document',
            'source_type': 'local_file',
            'binary_content': _PDF,
            'is_published': True,
            'sequence': 2,
        })
        cls.article = cls.Slide.create({
            'name': 'DEMO What good looks like',
            'channel_id': cls.course.id,
            'slide_category': 'article',
            'html_content': '<p>Walk the rows before you walk the office.</p>',
            'is_published': True,
            'sequence': 3,
        })
        cls.quiz = cls.Slide.create({
            'name': 'DEMO Two quick questions',
            'channel_id': cls.course.id,
            'slide_category': 'quiz',
            'is_published': True,
            'sequence': 4,
        })
        cls.q1 = cls.env['slide.question'].create({
            'slide_id': cls.quiz.id, 'sequence': 1,
            'question': 'When do you walk the rows?',
            'answer_ids': [
                (0, 0, {'text_value': 'Before the office', 'is_correct': True}),
                (0, 0, {'text_value': 'Never', 'is_correct': False}),
            ],
        })
        cls.q2 = cls.env['slide.question'].create({
            'slide_id': cls.quiz.id, 'sequence': 2,
            'question': 'What is the handbook for?',
            'answer_ids': [
                (0, 0, {'text_value': 'The field', 'is_correct': True}),
                (0, 0, {'text_value': 'The shelf', 'is_correct': False}),
            ],
        })

        cls.survey = cls.env['survey.survey'].create({
            'title': 'DEMO Agronomist basics — test',
            'survey_type': 'assessment',
            'certification': True,
            'scoring_type': 'scoring_with_answers',
            'scoring_success_min': 70,
            'users_login_required': True,
            'access_mode': 'token',
            'is_attempts_limited': True,
            'attempts_limit': 3,
            'question_ids': [
                (0, 0, {
                    'title': 'DEMO Q1', 'question_type': 'simple_choice',
                    'sequence': 1,
                    'suggested_answer_ids': [
                        (0, 0, {'value': 'Right', 'is_correct': True,
                                'answer_score': 1}),
                        (0, 0, {'value': 'Wrong', 'answer_score': 0}),
                    ]}),
                (0, 0, {
                    'title': 'DEMO Q2', 'question_type': 'simple_choice',
                    'sequence': 2,
                    'suggested_answer_ids': [
                        (0, 0, {'value': 'Right', 'is_correct': True,
                                'answer_score': 1}),
                        (0, 0, {'value': 'Wrong', 'answer_score': 0}),
                    ]}),
            ],
        })
        cls.test_slide = cls.Slide.create({
            'name': 'DEMO Agronomist basics — test',
            'channel_id': cls.course.id,
            'slide_category': 'certification',
            'survey_id': cls.survey.id,
            'is_published': True,
            'sequence': 9,
        })

        cls.course._action_add_members(cls.learner.partner_id)

    # ------------------------------------------------------------- helpers
    def _as(self, user):
        return self.env['pb.my.training'].with_user(user)

    def _finish_every_lesson(self, user):
        me = self._as(user)
        for slide in (self.video, self.doc, self.article):
            me.mark_done(self.course.id, slide.id)
        me.answer_quiz(self.course.id, self.quiz.id, [
            self.q1.answer_ids.filtered('is_correct').id,
            self.q2.answer_ids.filtered('is_correct').id,
        ])


# =========================================================================
#  T3/T4 — what a course IS, and what a learner sees of it
# =========================================================================
@tagged('post_install', '-at_install')
class TestWhatALessonIs(TrainingCase):

    def test_the_certification_slide_is_not_a_lesson(self):
        """THE RULE EVERYTHING ELSE HANGS OFF. Counted among the lessons, the
        test would unlock only once the test had been passed."""
        lessons = self.course._pb_lessons()
        self.assertEqual(len(lessons), 4)
        self.assertNotIn(self.test_slide, lessons)
        self.assertEqual(self.course._pb_test_slide(), self.test_slide)

    def test_an_unpublished_lesson_is_not_counted(self):
        self.article.is_published = False
        self.assertEqual(len(self.course._pb_lessons()), 3)

    def test_the_front_page_counts_a_new_learner_at_zero(self):
        home = self._as(self.learner).home()
        self.assertEqual(home['total'], 1)
        self.assertEqual(home['in_progress'], 1)
        self.assertEqual(home['finished'], 0)
        tile = home['courses'][0]
        self.assertEqual((tile['done'], tile['total']), (0, 4))
        self.assertEqual(tile['test'], 'locked')

    def test_the_home_card_counter_is_the_same_number(self):
        self.assertEqual(self._as(self.learner).home_count(), 1)
        self.assertEqual(self._as(self.other).home_count(), 0)


# =========================================================================
#  T5/T6 — the two writes
# =========================================================================
@tagged('post_install', '-at_install')
class TestFinishingALesson(TrainingCase):

    def test_marking_one_done_moves_the_progress(self):
        me = self._as(self.learner)
        me.mark_done(self.course.id, self.video.id)
        row = self.course._pb_membership(self.learner.partner_id)
        self.assertEqual(row.completed_slides_count, 1)
        self.assertTrue(row.completion > 0)
        course = me.course(self.course.id)
        self.assertEqual(course['done'], 1)
        self.assertEqual(course['left'], 3)

    def test_it_is_written_against_the_LEARNER_and_not_the_superuser(self):
        """`_action_mark_completed` reads `self.env.user.partner_id` itself, so
        a call made under sudo marks the SUPERUSER's lesson done — silently,
        on the wrong row, with the learner's screen unchanged."""
        self._as(self.learner).mark_done(self.course.id, self.video.id)
        rows = self.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', self.video.id), ('completed', '=', True)])
        self.assertEqual(rows.mapped('partner_id'), self.learner.partner_id)

    def test_a_lesson_with_questions_refuses_the_button(self):
        with self.assertRaises(UserError):
            self._as(self.learner).mark_done(self.course.id, self.quiz.id)

    def test_a_wrong_quiz_answer_names_the_question_and_leaves_it_open(self):
        answer = self._as(self.learner).answer_quiz(
            self.course.id, self.quiz.id,
            [self.q1.answer_ids.filtered('is_correct').id,
             self.q2.answer_ids.filtered(lambda a: not a.is_correct).id])
        self.assertFalse(answer['passed'])
        self.assertEqual(answer['wrong'], [self.q2.id])
        self.assertEqual(answer['right'], [self.q1.id])
        row = self.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', self.quiz.id),
            ('partner_id', '=', self.learner.partner_id.id)])
        self.assertFalse(row.completed)

    def test_an_unanswered_question_is_not_a_wrong_answer(self):
        answer = self._as(self.learner).answer_quiz(
            self.course.id, self.quiz.id,
            [self.q1.answer_ids.filtered('is_correct').id])
        self.assertFalse(answer['passed'])
        self.assertEqual(answer['unanswered'], [self.q2.id])
        self.assertEqual(answer['wrong'], [])

    def test_all_correct_marks_the_lesson_done(self):
        answer = self._as(self.learner).answer_quiz(
            self.course.id, self.quiz.id,
            [self.q1.answer_ids.filtered('is_correct').id,
             self.q2.answer_ids.filtered('is_correct').id])
        self.assertTrue(answer['passed'])
        row = self.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', self.quiz.id),
            ('partner_id', '=', self.learner.partner_id.id)])
        self.assertTrue(row.completed)

    def test_the_answer_key_never_leaves_the_server(self):
        """A page that knew which answer was right would be a page a learner
        could read the answers off."""
        lesson = self._as(self.learner).lesson(self.course.id, self.quiz.id)
        blob = str(lesson)
        for question in lesson['questions']:
            for ans in question['answers']:
                self.assertEqual(set(ans.keys()), {'id', 'text'})
        self.assertNotIn('is_correct', blob)


# =========================================================================
#  T7/T8 — the test at the end
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheTest(TrainingCase):

    def test_it_is_locked_until_every_lesson_is_done(self):
        answer = self._as(self.learner).start_test(self.course.id)
        self.assertEqual(answer.get('code'), 'locked')
        self.assertEqual(answer.get('left'), 4)

    def test_three_of_four_is_still_locked(self):
        me = self._as(self.learner)
        for slide in (self.video, self.doc, self.article):
            me.mark_done(self.course.id, slide.id)
        answer = me.start_test(self.course.id)
        self.assertEqual(answer.get('code'), 'locked')
        self.assertEqual(answer.get('left'), 1)

    def test_four_of_four_opens_an_attempt_linked_to_the_slide(self):
        self._finish_every_lesson(self.learner)
        answer = self._as(self.learner).start_test(self.course.id)
        self.assertTrue(answer.get('url'), answer)
        self.assertIn('/survey/start/', answer['url'])
        self.assertIn('answer_token=', answer['url'])
        attempt = self.env['survey.user_input'].sudo().search([
            ('survey_id', '=', self.survey.id),
            ('partner_id', '=', self.learner.partner_id.id)])
        self.assertEqual(len(attempt), 1)
        self.assertEqual(attempt.slide_id, self.test_slide)
        self.assertTrue(attempt.slide_partner_id)

    def test_pressing_it_twice_does_not_open_two_attempts(self):
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        first = me.start_test(self.course.id)
        second = me.start_test(self.course.id)
        self.assertEqual(first['url'], second['url'])

    def test_a_retry_rides_the_same_attempt_pool(self):
        """The engine counts attempts within an `invite_token`. A fresh token
        per go would make "3 attempts" mean "as many as you like"."""
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        me.start_test(self.course.id)
        first = self.env['survey.user_input'].sudo().search(
            [('survey_id', '=', self.survey.id)], limit=1)
        first.write({'state': 'done', 'scoring_percentage': 0,
                     'scoring_success': False})
        me.start_test(self.course.id)
        attempts = self.env['survey.user_input'].sudo().search(
            [('survey_id', '=', self.survey.id),
             ('partner_id', '=', self.learner.partner_id.id)])
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(set(attempts.mapped('invite_token'))), 1)

    def _use_every_go(self, me):
        for _i in range(3):
            me.start_test(self.course.id)
            live = self.env['survey.user_input'].sudo().search(
                [('survey_id', '=', self.survey.id),
                 ('partner_id', '=', self.learner.partner_id.id),
                 ('state', '!=', 'done')])
            live.write({'state': 'done', 'scoring_percentage': 10,
                        'scoring_success': False})

    def test_the_fourth_go_is_refused_in_words(self):
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        self._use_every_go(me)
        answer = me.start_test(self.course.id)
        self.assertEqual(answer.get('code'), 'no_attempts')

    def test_failing_the_last_go_does_not_take_them_off_the_course(self):
        """The engine's own join REMOVES a member who fails their last
        attempt and emails them the stock "enrol again" template. Right for
        somebody selling certifications, wrong for an employer: the course
        vanishes off the employee's page taking the lessons they DID finish
        with it, and nothing on any screen says where it went."""
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        self._use_every_go(me)
        self.assertEqual(me.home()['total'], 1,
                         'the course disappeared off their own page')
        course = me.course(self.course.id)
        self.assertEqual(course['test']['state'], 'failed')
        self.assertEqual(course['test']['attempts_left'], 0)
        self.assertEqual(course['done'], 4, 'their finished lessons went too')

    def test_the_switch_puts_the_engines_own_behaviour_back(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.unenrol_on_failed_test', '1')
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        self._use_every_go(me)
        self.assertEqual(me.home()['total'], 0)

    def test_a_pass_shows_the_score_and_offers_the_certificate(self):
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        me.start_test(self.course.id)
        attempt = self.env['survey.user_input'].sudo().search(
            [('survey_id', '=', self.survey.id)], limit=1)
        attempt.write({'state': 'done', 'scoring_percentage': 100,
                       'scoring_success': True})
        course = me.course(self.course.id)
        self.assertEqual(course['test']['state'], 'passed')
        self.assertEqual(course['test']['score'], 100)
        self.assertTrue(course['test']['certificate'])
        self.assertEqual(
            me.certificate_url(self.course.id),
            {'url': '/survey/%s/get_certification' % self.survey.id})

    def test_a_certificate_is_refused_before_a_pass(self):
        self._finish_every_lesson(self.learner)
        answer = self._as(self.learner).certificate_url(self.course.id)
        self.assertEqual(answer.get('code'), 'not_passed_yet')

    def test_passing_marks_the_course_finished(self):
        """The engine's own join: a successful attempt completes the
        certification slide, which completes the membership."""
        self._finish_every_lesson(self.learner)
        me = self._as(self.learner)
        me.start_test(self.course.id)
        attempt = self.env['survey.user_input'].sudo().search(
            [('survey_id', '=', self.survey.id)], limit=1)
        attempt.write({'state': 'done', 'scoring_percentage': 100,
                       'scoring_success': True})
        # R139's shape: the stored compute that marks the certification slide
        # complete is still in the recompute queue, and `_recompute_completion`
        # counts rows in the DATABASE. Without the flush the count is one
        # short and the membership reads "ongoing" over a passed test.
        self.env.flush_all()
        row = self.course._pb_membership(self.learner.partner_id)
        row._recompute_completion()
        self.assertEqual(row.member_status, 'completed')
        self.assertTrue(me.home()['courses'][0]['finished'])

    def test_a_course_with_no_test_says_so_rather_than_looking_broken(self):
        self.test_slide.unlink()
        self.assertEqual(
            self._as(self.learner).start_test(self.course.id).get('code'),
            'no_test')
        course = self._as(self.learner).course(self.course.id)
        self.assertIsNone(course['test'])


# =========================================================================
#  T10 — somebody else's training
# =========================================================================
@tagged('post_install', '-at_install')
class TestItIsOnlyEverYourOwn(TrainingCase):

    def test_a_learner_who_is_not_a_member_gets_nothing(self):
        self.assertIsNone(self._as(self.other).course(self.course.id))
        self.assertIsNone(
            self._as(self.other).lesson(self.course.id, self.video.id))

    def test_a_forged_slide_id_from_another_course_is_refused(self):
        elsewhere = self.Channel.create({
            'name': 'DEMO Somewhere else', 'is_published': True})
        stray = self.Slide.create({
            'name': 'DEMO Not yours', 'channel_id': elsewhere.id,
            'slide_category': 'article', 'html_content': '<p>x</p>',
            'is_published': True})
        self.assertIsNone(
            self._as(self.learner).lesson(self.course.id, stray.id))
        with self.assertRaises(AccessError):
            self._as(self.learner).mark_done(self.course.id, stray.id)

    def test_an_invitation_is_not_a_course_somebody_is_on(self):
        self.course._action_add_members(self.other.partner_id,
                                        member_status='invited')
        self.assertEqual(self._as(self.other).home()['total'], 0)
        self.assertIsNone(self._as(self.other).course(self.course.id))

    def test_an_unpublished_course_falls_off_the_page(self):
        self.course.is_published = False
        self.assertEqual(self._as(self.learner).home()['total'], 0)
        self.assertIsNone(self._as(self.learner).course(self.course.id))


# =========================================================================
#  T3 — the training team's side
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheBoard(TrainingCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.trainer = cls.env['res.users'].with_context(
            no_reset_password=True).create({
            'name': 'DEMO Trainer',
            'login': 'demo.trainer@example.com',
            'email': 'demo.trainer@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('pb_training.group_training_user').id])],
        })

    def test_a_plain_user_is_told_who_looks_after_training(self):
        board = self.Board.with_user(self.other).get_board()
        self.assertFalse(board['allowed'])
        self.assertEqual(board['courses'], [])

    def test_the_trainer_sees_the_course_and_its_numbers(self):
        board = self.Board.with_user(self.trainer).get_board()
        self.assertTrue(board['allowed'])
        row = next(c for c in board['courses'] if c['id'] == self.course.id)
        self.assertEqual(row['lessons'], 4)
        # TWO, not one: `slide.channel.create` enrols whoever made the course
        # (slide_channel.py:491) so the author can find it again. The number
        # is honest — they really are a member — but a reader expecting "the
        # people I put on it" has to know.
        self.assertEqual(row['members'], 2)
        self.assertEqual(row['not_started'], 2)
        self.assertTrue(row['has_test'])
        self.assertEqual(row['pass_mark'], 70)

    def test_the_board_puts_the_problem_first(self):
        """A course fourteen people were put on and nobody opened comes above
        a course everybody finished in March (R113)."""
        quiet = self.Channel.create({
            'name': 'DEMO Nobody is on this one', 'is_published': True})
        board = self.Board.with_user(self.trainer).get_board()
        order = [c['id'] for c in board['courses']]
        self.assertLess(order.index(self.course.id), order.index(quiet.id))

    def test_the_people_picker_folds_accents(self):
        emp = self.env['hr.employee'].create({
            'name': 'DEMO Bùi Hữu Dũng',
            'user_id': self.learner.id,
            'company_id': self.env.company.id,
        })
        rows = self.Board.with_user(self.trainer).search_people('bui hu')
        self.assertIn(emp.id, [r['id'] for r in rows])

    def test_somebody_with_no_login_is_not_offered(self):
        """A membership hangs off a partner and every learner page resolves
        "me" as the SESSION user's partner, so enrolling a work contact whose
        person cannot sign in puts a course on a page nobody will see."""
        self.env['hr.employee'].create({
            'name': 'DEMO No Login', 'company_id': self.env.company.id})
        rows = self.Board.with_user(self.trainer).search_people('DEMO No Login')
        self.assertEqual(rows, [])

    def test_enrolling_is_idempotent_and_says_what_it_did(self):
        emp = self.env['hr.employee'].create({
            'name': 'DEMO Enrol Me', 'user_id': self.other.id,
            'company_id': self.env.company.id})
        board = self.Board.with_user(self.trainer)
        first = board.enrol(self.course.id, [emp.id])
        self.assertEqual(first['added'], 1)
        second = board.enrol(self.course.id, [emp.id])
        self.assertEqual(second['added'], 0)
        self.assertEqual(self._as(self.other).home()['total'], 1)

    def test_taking_somebody_off_keeps_what_they_did(self):
        self._as(self.learner).mark_done(self.course.id, self.video.id)
        self.Board.with_user(self.trainer).unenrol(
            self.course.id, [self.learner.partner_id.id])
        self.assertEqual(self._as(self.learner).home()['total'], 0)
        row = self.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', self.video.id),
            ('partner_id', '=', self.learner.partner_id.id)])
        self.assertTrue(row.completed)

    def test_an_unknown_verb_is_refused_by_name(self):
        with self.assertRaises(UserError):
            self.Board.with_user(self.trainer).act('drop_everything', {})

    def test_a_private_helper_is_not_reachable_as_a_verb(self):
        with self.assertRaises(UserError):
            self.Board.with_user(self.trainer).act('_require_write', {})

    def test_a_new_course_is_never_a_public_one(self):
        door = self.Board.with_user(self.trainer).new_course()
        self.assertEqual(door['context']['default_visibility'], 'members')
        self.assertEqual(door['context']['default_enroll'], 'invite')
        self.assertIn('views', door)

    def test_a_new_test_is_already_a_scored_certification(self):
        """A certification with no scoring type is refused by the engine's own
        constraint, so defaulting one is the difference between a form that
        saves and a form that argues."""
        ctx = self.Board.with_user(self.trainer).new_test()['context']
        self.assertTrue(ctx['default_certification'])
        # There is no "certification" survey TYPE on this build; a test is an
        # assessment that carries the certification flag. Writing the wrong
        # one is a hard ValueError on create.
        self.assertIn(ctx['default_survey_type'],
                      dict(self.env['survey.survey']._fields['survey_type']
                           .selection))
        self.assertEqual(ctx['default_scoring_type'], 'scoring_with_answers')
        self.assertEqual(ctx['default_scoring_success_min'], 70)


# =========================================================================
#  T9 — the door on the public course site
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheStockPageGate(TransactionCase):

    def test_every_switch_has_a_row_an_administrator_can_find(self):
        """`post_init_hook` fires on INSTALL ONLY, so a switch ADDED after a
        database already has the module never gets a row — and a switch
        nobody can find is a switch nobody can turn. The migration beside the
        hook is what closes that, and this is what notices when the pair
        falls out of step."""
        from odoo.addons.pb_training.models.training_common import DEFAULTS
        icp = self.env['ir.config_parameter'].sudo()
        missing = [k for k in DEFAULTS if not icp.get_param(k)]
        self.assertFalse(
            missing,
            'these switches have no row: %s — add a migration beside the '
            'post_init_hook' % missing)

    def test_the_switch_ships_on(self):
        from odoo.addons.pb_training.models.training_common import (
            P_STOCK_PAGES, flag)
        self.assertTrue(flag(self.env, P_STOCK_PAGES))

    def test_every_page_it_claims_to_gate_is_a_real_method(self):
        """A misspelt override is a method nobody calls: the route carries on
        working exactly as it did and nothing anywhere says the gate is not
        there."""
        from odoo.addons.pb_training.controllers import slides_gate
        from odoo.addons.website_slides.controllers.main import WebsiteSlides
        from odoo.addons.website_slides.controllers.legacy import (
            WebsiteSlidesLegacy)
        for name in ('slides_channel', 'channel', 'slide_view',
                     'view_user_profile', 'view_all_users_page',
                     'view_ranks_badges'):
            self.assertTrue(
                hasattr(WebsiteSlides, name),
                'pb_training gates %s, which is not on the controller it '
                'inherits' % name)
            self.assertTrue(
                hasattr(slides_gate.PbTrainingSlidesGate, name))
        self.assertTrue(hasattr(WebsiteSlidesLegacy, 'slides_channel_all'))

    def test_no_content_route_is_gated(self):
        """`/my/training` renders a lesson by pointing an iframe at these.
        Gating one takes the learner's own page down and leaves a grey box."""
        from odoo.addons.pb_training.controllers import slides_gate
        # THE CLASS'S OWN `__dict__`, never `dir()`: `dir()` walks the whole
        # inheritance chain, so it lists every route on the controller being
        # extended and a gate written against it passes over a module that
        # gates nothing and fails over one that gates correctly.
        gated = {n for n in vars(slides_gate.PbTrainingSlidesGate)
                 if not n.startswith('_')}
        for never in ('slide_get_pdf_content', 'slide_get_image',
                      'get_html_content', 'slide_quiz_get',
                      'slide_quiz_submit', 'slide_embed'):
            self.assertNotIn(never, gated,
                             '%s must stay open — the learner pages use it'
                             % never)

    def test_the_gate_overrides_nothing_in_the_test_engine(self):
        """The test runs on the survey routes. A gate there would refuse the
        learner the very page the course sends them to."""
        from odoo.addons.pb_training.controllers import slides_gate
        for name in vars(slides_gate.PbTrainingSlidesGate):
            self.assertFalse(name.startswith('survey_'),
                             'the gate overrides %s, a test-engine route'
                             % name)


# =========================================================================
#  The gates — whole classes of defect that are invisible at runtime
# =========================================================================
@tagged('post_install', '-at_install')
class TestSourceGates(TransactionCase):

    _JS = ('training_board.js', 'training_palette.js')

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JS SyntaxError, and the asset pipeline
        concatenates without ever parsing — so one of these blanks
        `web.assets_backend` for every user with a clean server log (R2)."""
        for fname in self._JS:
            src = _src('static', 'src', 'js', fname)
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                '%s has two adjacent string literals across a newline' % fname)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the loop variable into the generated function
        as a bare `<` and the whole template dies, pointing at the template
        and never at the loop (R1)."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        src = re.sub(r'<!--.*?-->', '', _src('static', 'src', 'xml',
                                             'training_board.xml'), flags=re.S)
        for name in re.findall(r't-as="(\w+)"', src):
            self.assertNotIn(name, reserved,
                             'training_board.xml uses the reserved name %s'
                             % name)

    def test_no_doubled_hyphen_inside_an_xml_comment(self):
        """A doubled hyphen inside an XML comment is a parse error that takes
        every template in the file down with it (R35). Section rules use `=`."""
        for parts in (('static', 'src', 'xml', 'training_board.xml'),
                      ('views', 'portal_templates.xml'),
                      ('views', 'training_views.xml'),
                      ('views', 'assignment_views.xml')):
            for body in re.findall(r'<!--(.*?)-->', _src(*parts), flags=re.S):
                self.assertFalse(
                    re.search(r'--', body),
                    '%s has a doubled hyphen inside a comment' % parts[-1])

    def test_every_icon_name_is_in_the_shared_registry(self):
        """`ic()` falls back for an unknown name, so a typo is a blank circle
        rather than an error — and the check is against the INSTALLED copy of
        the registry, not the repo's, because a module that deploys only
        itself can ship against a registry the server has not got (R147)."""
        path = get_module_path('pb_import_kit')
        with open(path + '/static/src/js/import_icons.js',
                  encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('bookOpen', known, 'the icon registry did not parse')
        used = set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                              _src('static', 'src', 'xml',
                                   'training_board.xml')))
        for fname in self._JS:
            src = _src('static', 'src', 'js', fname)
            used |= set(re.findall(r'icon:\s*"([A-Za-z0-9_]+)"', src))
            used |= set(re.findall(r':\s*"([A-Za-z0-9_]+)",\s*//\s*icon', src))
        # R146: the gate must read the object-literal maps too, or it checks
        # half the icons. This module's map is Python-side.
        from odoo.addons.pb_training.models.training_common import LESSON_ICONS
        used |= set(LESSON_ICONS.values())
        for name in used:
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry"
                          % name)

    def test_the_word_odoo_appears_in_no_user_visible_string(self):
        """The white-label rule, and only where it actually binds.

        It covers user-visible STRINGS. Engineering comments MUST be able to
        say the real name — the sentence that stops the next contributor
        reintroducing a bug is worth more than a gate that forbids it (R118) —
        so the comments are stripped and everything that is left is checked.
        """
        for parts in (('static', 'src', 'xml', 'training_board.xml'),
                      ('views', 'training_views.xml'),
                      ('views', 'portal_templates.xml'),
                      ('views', 'assignment_views.xml'),
                      ('data', 'mail_template_assignments.xml'),
                      ('security', 'pb_training_security.xml'),
                      ('security', 'pb_training_rules.xml')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn('Odoo', src,
                             '%s shows the word Odoo to a user' % parts[-1])
            self.assertNotIn('odoo.com', src.lower())
        # The Python strings a person reads, with the docstrings and comments
        # taken out — `_()` is what reaches a screen.
        for parts in (('models', 'pb_training.py'),
                      ('models', 'pb_my_training.py'),
                      ('models', 'assignment.py'),
                      ('models', 'delay.py'),
                      ('models', 'schedule.py'),
                      ('models', 'automation.py'),
                      ('models', 'journey_ext.py'),
                      ('controllers', 'portal.py')):
            for text in re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', _src(*parts)):
                self.assertNotIn('Odoo', text)

    def test_no_bracketed_plurals(self):
        """"1 lesson(s)" is how a screen announces it was written by a
        programme rather than by a person (R46). Log lines are exempt and are
        not in this list."""
        for parts in (('models', 'pb_my_training.py'),
                      ('models', 'pb_training.py'),
                      ('controllers', 'portal.py'),
                      ('models', 'assignment.py'),
                      ('models', 'schedule.py'),
                      ('static', 'src', 'xml', 'training_board.xml'),
                      ('views', 'portal_templates.xml'),
                      ('views', 'assignment_views.xml')):
            src = _src(*parts)
            self.assertFalse(re.search(r'\w\(s\)', src),
                             '%s has a bracketed plural' % parts[-1])

    def test_no_emoji_anywhere_a_user_can_see(self):
        for parts in (('static', 'src', 'xml', 'training_board.xml'),
                      ('views', 'portal_templates.xml'),
                      ('views', 'assignment_views.xml')):
            src = _src(*parts)
            self.assertFalse(
                re.search(r'[\U0001F300-\U0001FAFF✀-➿]', src),
                '%s has an emoji in it' % parts[-1])

    def test_every_hand_built_window_action_carries_views(self):
        """`_preprocessAction` runs `action.views.map(...)` unconditionally,
        and the ORM-computed `views` field exists only on real act_window
        RECORDS — so a dict without it throws in the client and the user sees
        the generic "something went wrong" dialog with nothing useful in the
        console (R125)."""
        import ast
        import os
        path = get_module_path('pb_training')
        offenders = []
        for root, _dirs, files in os.walk(path):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                full = os.path.join(root, fname)
                with open(full, encoding='utf-8') as fh:
                    tree = ast.parse(fh.read(), full)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Dict):
                        continue
                    keys = [k.value for k in node.keys
                            if isinstance(k, ast.Constant)]
                    values = [v.value for v in node.values
                              if isinstance(v, ast.Constant)]
                    if 'ir.actions.act_window' not in values:
                        continue
                    if 'views' not in keys:
                        offenders.append('%s:%s' % (fname, node.lineno))
        self.assertFalse(
            offenders,
            'these act_window dicts carry no `views`: %s' % offenders)

    def test_every_nolabel_field_in_a_group_carries_a_colspan(self):
        """An inner group is a two-column grid and a label-less field takes
        the NARROW cell, so a note box renders about 150px wide with a
        thousand pixels of empty row beside it (R128)."""
        from lxml import etree
        offenders = []
        for parts in (('views', 'training_views.xml'),
                      ('views', 'assignment_views.xml')):
            tree = etree.fromstring(_src(*parts).encode('utf-8'))
            for field in tree.iter('field'):
                if field.get('nolabel') != '1':
                    continue
                parent = field.getparent()
                if parent is None or parent.tag != 'group':
                    continue
                if not field.get('colspan'):
                    offenders.append('%s line %s'
                                     % (parts[-1], field.sourceline))
        self.assertFalse(offenders, 'nolabel without colspan: %s' % offenders)

    def test_no_search_group_carries_a_string_or_expand(self):
        """Odoo 19 search `<group>` takes neither, and either one fails RNG
        validation and ABORTS THE WHOLE MODULE LOAD (R129)."""
        from lxml import etree
        tree = etree.fromstring(
            _src('views', 'training_views.xml').encode('utf-8'))
        for search in tree.iter('search'):
            for group in search.iter('group'):
                self.assertIsNone(group.get('string'))
                self.assertIsNone(group.get('expand'))

    def test_no_portal_page_links_to_the_public_course_site(self):
        """Every learner surface is ours. One `/slides/…` href and the gate
        this module ships would be bouncing people off its own page."""
        src = re.sub(r'<!--.*?-->', '', _src('views', 'portal_templates.xml'),
                     flags=re.S)
        for href in re.findall(r'href="([^"]*)"', src) \
                + re.findall(r't-attf-href="([^"]*)"', src):
            self.assertFalse(href.startswith('/slides'),
                             'a learner page links to %s' % href)

    def test_the_portal_stylesheet_gives_every_colour_a_literal_fallback(self):
        """The portal surface is light-only by design (R39), so "check it in
        both themes" is satisfied by proving every colour RESOLVES."""
        src = _src('static', 'src', 'scss', 'portal_training.scss')
        bare = [m for m in re.findall(r'var\(--[a-z0-9-]+\)', src)]
        self.assertFalse(bare,
                         'these portal colours have no literal fallback: %s'
                         % bare)


# =========================================================================
#  The doors
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheDoors(TransactionCase):

    def test_the_client_action_exists_and_carries_a_name(self):
        act = self.env.ref('pb_training.action_pb_training_board')
        self.assertEqual(act.tag, 'pb_training_board')
        self.assertTrue(act.name)

    def test_the_employee_page_is_reachable_as_an_action(self):
        """The palette knows a tag and an xmlid and nothing else, so a page
        reached by URL needs an `ir.actions.act_url` record."""
        act = self.env.ref('pb_training.action_my_training')
        self.assertEqual(act.url, '/my/training')

    def test_the_palette_names_real_actions(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        for xmlid in set(re.findall(r'xmlid:\s*"([\w.]+)"', src)):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'the palette points at %s, which does not resolve'
                            % xmlid)

    def test_the_palette_takes_the_3900_block(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        seqs = sorted(int(s) for s in
                      re.findall(r'\{\s*sequence:\s*(\d{4})\s*\}', src))
        self.assertTrue(seqs)
        for seq in seqs:
            if seq < 3000:          # the lens sequence, not a palette one
                continue
            self.assertTrue(3900 <= seq <= 3990,
                            '%s is outside E1\'s 3900 block' % seq)

    def test_the_lens_sits_at_sequence_twenty_on_the_learn_hub(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        self.assertIn('registry.category(LEARN_LENSES).add("training"', src)
        self.assertIn('{ sequence: 20 }', src)

    def test_this_module_ships_no_menu_and_no_rail_item(self):
        """Training is a LENS on a mission that already has a rail entry. A
        second door would be a second place to look."""
        for parts in (('views', 'training_views.xml'),):
            self.assertNotIn('<menuitem', _src(*parts))
            self.assertNotIn('pb.sidebar.item', _src(*parts))

    def test_the_three_tiers_exist_and_imply_the_engines(self):
        user = self.env.ref('pb_training.group_training_user')
        manager = self.env.ref('pb_training.group_training_manager')
        admin = self.env.ref('pb_training.group_training_admin')
        implied = user.implied_ids
        self.assertIn(self.env.ref('website_slides.group_website_slides_officer'),
                      implied)
        self.assertIn(self.env.ref('survey.group_survey_user'), implied)
        self.assertIn(user, manager.implied_ids)
        self.assertIn(manager, admin.implied_ids)

    def test_no_privilege_name_carries_an_ampersand(self):
        """Odoo 19 embeds a privilege name into the user form's arch WITHOUT
        escaping, and one ampersand makes opening ANY user crash (R124)."""
        rows = self.env['res.groups.privilege'].search([])
        self.assertFalse([r.name for r in rows if '&' in (r.name or '')])
