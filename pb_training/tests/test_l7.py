# -*- coding: utf-8 -*-
"""LEARNING L7 — the learner's phone. Handover tests T1–T6, T9, T10 (T7/T8
are `pb_training_payai`'s, T11 is the Chrome walk).

The rails: a phone press that the server answers with a page instead of
words (so it cannot be queued or replayed), a quiz answer key on the wire, a
"three minutes" card that promises three minutes for a long lesson, a hero
whose rules run in the wrong order, a streak that forgives a late finish, a
second language drawn twice when nobody translated the lesson, a manifest
with the wrong start page, a service worker, and a word of English or a
vendor name on a Vietnamese screen.

Fixtures are "DEMO" and roll back. Facade classes pin `lang='en_US'` (LN14)
and none of them depends on a job's switch, on seeded rows or on HTTP
reaching the database (LN64): the two HTTP classes probe first and skip,
with the reason, when the server's database filter logs the test session
out (LN63).
"""

import json
import os
import re
import shutil
import subprocess
from datetime import timedelta

from odoo import fields, http
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, tagged

from .test_assignments import AssignmentCase
from .test_training import TrainingCase, _src

NEW_FILES = (
    ('models', 'learner_l7.py'),
    ('views', 'portal_l7.xml'),
    ('static', 'src', 'js', 'portal_lesson.js'),
    ('static', 'src', 'scss', 'portal_l7.scss'),
)
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]')


def _vi_active(env):
    return bool(env['res.lang'].sudo().search_count(
        [('code', '=', 'vi_VN'), ('active', '=', True)]))


# =========================================================================
#  T1 — the JSON branches of /done and /quiz (the HTML branch unchanged)
# =========================================================================
@tagged('post_install', '-at_install')
class TestT1PhoneRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.learner = Users.create({
            'name': 'DEMO L7 phone learner', 'login': 'demo.l7.phone',
            'password': 'demo.l7.phone', 'email': 'demo.l7.phone@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.course = cls.env['slide.channel'].create({
            'name': 'DEMO L7 Phone course', 'channel_type': 'training',
            'visibility': 'members', 'enroll': 'invite',
            'completed_template_id': False, 'is_published': True})
        Slide = cls.env['slide.slide']
        cls.read1 = Slide.create({
            'name': 'DEMO L7 Read one', 'channel_id': cls.course.id,
            'slide_category': 'article', 'html_content': '<p>One.</p>',
            'is_published': True, 'sequence': 1})
        cls.read2 = Slide.create({
            'name': 'DEMO L7 Read two', 'channel_id': cls.course.id,
            'slide_category': 'article', 'html_content': '<p>Two.</p>',
            'is_published': True, 'sequence': 2})
        cls.quiz = Slide.create({
            'name': 'DEMO L7 Quick check', 'channel_id': cls.course.id,
            'slide_category': 'quiz', 'is_published': True, 'sequence': 3})
        cls.q1 = cls.env['slide.question'].create({
            'slide_id': cls.quiz.id, 'sequence': 1, 'question': 'DEMO Left?',
            'answer_ids': [(0, 0, {'text_value': 'Yes', 'is_correct': True}),
                           (0, 0, {'text_value': 'No', 'is_correct': False})]})
        cls.course._action_add_members(cls.learner.partner_id)

    def _login(self):
        self.authenticate('demo.l7.phone', 'demo.l7.phone')
        probe = self.url_open('/my/training/%s' % self.course.id)
        if probe.status_code == 404:
            self.skipTest("this server's database filter logs the test "
                          "session out; the page cannot be reached here")

    def _post(self, path, data, phone=True):
        data = dict(data, csrf_token=http.Request.csrf_token(self))
        headers = {'X-Requested-With': 'XMLHttpRequest'} if phone else {}
        return self.url_open(path, data=data, headers=headers)

    def test_t1_done_answers_json_with_the_next_page(self):
        self._login()
        res = self._post('/my/training/%s/%s/done' % (self.course.id,
                                                      self.read1.id),
                         {'next_id': self.read2.id})
        self.assertEqual(res.status_code, 200)
        self.assertIn('json', res.headers.get('Content-Type', ''))
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['next_url'], '/my/training/%s/%s'
                         % (self.course.id, self.read2.id))
        self.assertEqual(body['lesson_name'], 'DEMO L7 Read one')
        done = self.course._pb_done_ids(self.learner.partner_id)
        self.assertIn(self.read1.id, done)

    def test_t1_quiz_answers_json_marks_only(self):
        self._login()
        wrong = self.q1.answer_ids.filtered(lambda a: not a.is_correct)
        res = self._post('/my/training/%s/%s/quiz' % (self.course.id,
                                                      self.quiz.id),
                         {'q%s' % self.q1.id: wrong.id})
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertFalse(body['passed'])
        self.assertEqual(body['result']['wrong'], [self.q1.id])
        self.assertEqual(body['next_url'], '')
        # Never the answer key: the marks per question and the sentence only.
        self.assertEqual(set(body['result']), {'passed', 'wrong', 'unanswered',
                                               'right', 'message'})
        self.assertNotIn('is_correct', json.dumps(body))
        right = self.q1.answer_ids.filtered('is_correct')
        body = self._post('/my/training/%s/%s/quiz' % (self.course.id,
                                                       self.quiz.id),
                          {'q%s' % self.q1.id: right.id}).json()
        self.assertTrue(body['passed'])
        self.assertIn('/my/training/%s' % self.course.id, body['next_url'])

    def test_t1_a_refusal_is_words_never_a_queued_press(self):
        self._login()
        body = self._post('/my/training/%s/%s/done' % (self.course.id,
                                                       self.quiz.id),
                          {}).json()
        self.assertFalse(body['ok'])
        self.assertEqual(body['problem'], 'quiz')
        self.assertTrue(body['message'])

    def test_t1_the_plain_form_still_redirects(self):
        self._login()
        res = self._post('/my/training/%s/%s/done' % (self.course.id,
                                                      self.read1.id),
                         {'next_id': self.read2.id}, phone=False)
        self.assertIn('/my/training/%s/%s' % (self.course.id, self.read2.id),
                      res.url)
        self.assertNotIn('json', res.headers.get('Content-Type', ''))


# =========================================================================
#  T2 — the replay queue, in node (the repo's JS runner, as pb_learn's)
# =========================================================================
@tagged('post_install', '-at_install')
class TestT2ReplayQueue(TrainingCase):

    def test_t2_node_suite(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed on this server; run '
                          'pb_training/tests/js/portal_lesson.test.mjs by hand')
        path = os.path.join(get_module_path('pb_training'), 'tests', 'js',
                            'portal_lesson.test.mjs')
        out = subprocess.run([node, path], capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn('0 failed', out.stdout)

    def test_t2_the_script_is_plain_and_registers_no_worker(self):
        js = _src('static', 'src', 'js', 'portal_lesson.js')
        self.assertTrue(js.startswith('/** @odoo-module ignore **/'))
        self.assertNotIn('serviceWorker.register', js)
        self.assertIn('"pbtr.queue"', js)
        self.assertIn('CAP = 50', js)
        self.assertIn("'X-Requested-With'", js.replace('"', "'"))
        # every storage call is wrapped
        self.assertEqual(js.count('localStorage'), 1)
        self.assertIn('try { return root.localStorage', js)


# =========================================================================
#  T3 — three minutes today
# =========================================================================
@tagged('post_install', '-at_install')
class TestT3ThreeMinutes(TrainingCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))
        cls.short = cls.Channel.create({
            'name': 'DEMO L7 Short course', 'channel_type': 'training',
            'visibility': 'members', 'enroll': 'invite',
            'completed_template_id': False, 'is_published': True})
        cls.s_long = cls.Slide.create({
            'name': 'DEMO L7 Long read', 'channel_id': cls.short.id,
            'slide_category': 'article', 'html_content': '<p>Long.</p>',
            'completion_time': 0.5, 'is_published': True, 'sequence': 1})
        cls.s_three = cls.Slide.create({
            'name': 'DEMO L7 Three minutes', 'channel_id': cls.short.id,
            'slide_category': 'article', 'html_content': '<p>Short.</p>',
            'completion_time': 0.05, 'is_published': True, 'sequence': 2})
        cls.short._action_add_members(cls.learner.partner_id)
        # The fixture course's lessons are untimed or long.
        (cls.video | cls.doc | cls.article | cls.quiz).write(
            {'completion_time': 0.0})

    def test_t3_five_minutes_or_less_first(self):
        got = self._as(self.learner).three_minutes()
        self.assertEqual(got['lesson_id'], self.s_three.id)
        self.assertEqual(got['url'], '/my/training/%s/%s'
                         % (self.short.id, self.s_three.id))
        self.assertEqual(got['duration'], '3 min')

    def test_t3_none_when_nothing_is_short(self):
        self.s_three.completion_time = 0.75
        self.assertIsNone(self._as(self.learner).three_minutes())

    def test_t3_a_short_lessons_course_offers_its_shortest(self):
        self.s_three.completion_time = 0.75
        self.short.pb_short = True
        got = self._as(self.learner).three_minutes()
        self.assertEqual(got['lesson_id'], self.s_long.id)

    def test_t3_a_finished_lesson_is_not_offered(self):
        self._as(self.learner).mark_done(self.short.id, self.s_three.id)
        self.assertIsNone(self._as(self.learner).three_minutes())

    def test_t3_home_carries_it(self):
        home = self._as(self.learner).home()
        self.assertEqual(home['three']['lesson_id'], self.s_three.id)

    def test_t3_short_lessons_is_a_trainer_switch(self):
        trainer = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO L7 trainer', 'login': 'demo.l7.trainer@example.com', 'lang': 'en_US',
                'group_ids': [(6, 0, [self.env.ref(
                    'pb_training.group_training_user').id])]})
        res = self.Board.with_user(trainer).act(
            'set_short', {'channel_id': self.short.id, 'on': True})
        self.assertTrue(self.short.pb_short)
        self.assertIn('short', res['message'].lower())
        data = self.Board.with_user(trainer).get_course(self.short.id)
        self.assertTrue(data['short'])


# =========================================================================
#  T4 — Next for you: the rule order, EN and VI
# =========================================================================
@tagged('post_install', '-at_install')
class TestT4NextBest(TrainingCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US',
                                       tz='UTC'))

    def _tile(self, cid, **kw):
        tile = {'id': cid, 'name': 'DEMO course %s' % cid, 'next_id': cid * 10,
                'next_name': 'DEMO lesson %s' % cid, 'finished': False,
                'percent': 0, 'total': 3, 'test': 'none', 'delivery': 'online',
                'duration': '', 'assignment': None}
        tile.update(kw)
        return tile

    def _world(self):
        """One fact per rule; each test takes facts away from the top."""
        today = fields.Date.today()
        now = fields.Datetime.now()
        return {
            'data': {
                'courses': [
                    self._tile(1, assignment={'state': 'overdue', 'days_over': 4,
                                              'due_words': '4 days overdue',
                                              'due': '2026-01-01'}),
                    self._tile(2),
                    self._tile(3, percent=60),
                    self._tile(4),
                ],
                'paths': [{'state': 'in_progress', 'late': False,
                           'name': 'DEMO path', 'where_words': 'At step 1 of 2',
                           'next': {'channel_id': 2, 'name': 'DEMO course 2'}}],
                'sessions': {'next': {'course': 'DEMO session', 'channel_id': 9,
                                      'start': fields.Datetime.to_string(
                                          now + timedelta(hours=2)),
                                      'when_words': 'today', 'where_words': 'Room'}},
                'feedback': [{'words': 'Rate DEMO', 'course': 'DEMO',
                              'url': '/my/training/feedback/x'}],
            },
            'certs': {'rows': [{'state': 'soon', 'name': 'DEMO licence',
                                'valid_words': 'Expires in 10 days',
                                'expiry': fields.Date.to_string(
                                    today + timedelta(days=10)),
                                'renewal': {'open': True, 'channel_id': 4}}]},
            'required': {'rows': [{'state': 'missing', 'name': 'DEMO rule',
                                   'words': 'Missing', 'channel_id': 4}]},
            'three': {'name': 'DEMO three', 'course': 'DEMO', 'duration': '3 min',
                      'kind_word': 'Reading', 'url': '/my/training/5/50'},
        }

    def _pick(self, w, env=None):
        return (env or self.env)['pb.my.training']._pick_next(
            w['data'], certs=w['certs'], required=w['required'],
            three=w['three'])

    def test_t4_the_rules_in_order(self):
        w = self._world()
        order = []
        steps = [
            ('overdue', lambda: w['data']['courses'][0].update(
                assignment=None)),
            ('path', lambda: w['data'].update(paths=[])),
            ('renewal', lambda: w['certs'].update(rows=[])),
            ('required', lambda: w['required'].update(rows=[])),
            ('continue', lambda: w['data']['courses'][2].update(
                finished=True)),
            ('start', lambda: w['data'].update(courses=[])),
            ('session', lambda: w['data']['sessions'].update(next=None)),
            ('feedback', lambda: w['data'].update(feedback=[])),
            ('three', lambda: w.update(three=None)),
        ]
        for kind, take_away in steps:
            got = self._pick(w)
            order.append(got['kind'])
            self.assertEqual(got['kind'], kind, order)
            self.assertTrue(got['title'] and got['url'] and got['reason'],
                            got)
            take_away()
        last = self._pick(w)
        self.assertEqual(last['kind'], 'none')
        self.assertEqual(last['title'], 'Nothing to do right now.')
        from ..models.learner_l7 import NEXT_RULES
        self.assertEqual(
            [k for k in NEXT_RULES if k != 'signoff'],
            [k for k, _f in steps] + ['none'],
            'the designed order (sign-off waits for LD5)')

    def test_t4_the_hero_goes_into_the_lesson(self):
        w = self._world()
        got = self._pick(w)
        self.assertEqual(got['url'], '/my/training/1/10')
        self.assertEqual(got['button'], 'Continue')
        self.assertIn('4 days overdue', got['line'])

    def test_t4_vietnamese_words(self):
        if not _vi_active(self.env):
            self.skipTest('Vietnamese is not installed on this database')
        vi = self.env(context=dict(self.env.context, lang='vi_VN'))
        got = self._pick(self._world(), vi)
        self.assertEqual(got['kind'], 'overdue', 'the same rules in VI')
        self.assertNotEqual(got['reason'], self._pick(self._world())['reason'])
        self.assertNotEqual(got['button'], 'Continue')
        empty = {'data': {'courses': []}, 'certs': {}, 'required': {},
                 'three': None}
        self.assertNotEqual(self._pick(empty, vi)['title'],
                            'Nothing to do right now.')

    def test_t4_home_carries_a_real_answer(self):
        home = self._as(self.learner).home()
        self.assertIn(home['next']['kind'], ('start', 'continue'))
        self.assertEqual(home['next']['channel_id'], self.course.id)
        self.assertTrue(home['next']['url'].startswith(
            '/my/training/%s' % self.course.id))


# =========================================================================
#  T5 — the on-time streak
# =========================================================================
@tagged('post_install', '-at_install')
class TestT5Streak(AssignmentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))

    def _done(self, finished, due, excused=None):
        row = self.env['pb.training.assignment'].sudo().create({
            'channel_id': self.simple.id, 'employee_id': self.e_one.id})
        row.write({'state': 'done', 'completed_on': finished, 'due_date': due,
                   'excused_until': excused})
        return row

    def _streak(self):
        return self.env['pb.my.training'].with_user(self.u_one).streak()

    def test_t5_counts_on_time_finishes_only_and_resets(self):
        today = fields.Date.today()
        d = lambda n: today - timedelta(days=n)            # noqa: E731
        self.assertEqual(self._streak()['count'], 0)
        self.assertEqual(self._streak()['words'], '')
        self._done(d(30), d(28))                            # on time
        self.assertEqual(self._streak()['count'], 1)
        self._done(d(20), d(25))                            # late
        self.assertEqual(self._streak()['count'], 0, 'a late finish resets it')
        self._done(d(10), d(9))                             # on time
        self._done(d(5), d(5))                              # on the day
        got = self._streak()
        self.assertEqual(got['count'], 2)
        self.assertEqual(got['words'], '2 in a row, on time')

    def test_t5_agreed_more_time_counts_and_no_date_is_skipped(self):
        today = fields.Date.today()
        self._done(today - timedelta(days=9), today - timedelta(days=12),
                   excused=today - timedelta(days=8))
        self._done(today - timedelta(days=3), False)
        self.assertEqual(self._streak()['count'], 1)

    def test_t5_never_shown_to_others(self):
        """It is the reader's own: nothing on the team page or a board."""
        for rel in (('models', 'overview_l6.py'), ('models', 'numbers_l6.py'),
                    ('static', 'src', 'xml', 'learning_overview.xml'),
                    ('static', 'src', 'xml', 'training_numbers.xml')):
            self.assertNotIn('streak', _src(*rel))


# =========================================================================
#  T6 — both languages, and Missing Vietnamese
# =========================================================================
@tagged('post_install', '-at_install')
class TestT6BothLanguages(TrainingCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _vi_active(cls.env):
            cls.env['res.lang']._activate_lang('vi_VN')
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))
        # Written in English only, whatever the database's own language (a
        # record made in Vietnamese stores both languages at once).
        cls.article = cls.env['slide.slide'].with_context(lang='en_US').create({
            'name': 'DEMO What good looks like', 'channel_id': cls.course.id,
            'slide_category': 'article', 'is_published': True, 'sequence': 5,
            'html_content': '<p>Walk the rows before you walk the office.</p>'})

    def test_t6_only_when_the_translation_differs(self):
        me = self._as(self.learner)
        data = me.lesson(self.course.id, self.article.id)
        self.assertIsNone(data['both'], 'nobody translated it')
        self.article.with_context(lang='vi_VN').write(
            {'name': 'DEMO Thế nào là tốt'})
        self.article.update_field_translations('html_content', {'vi_VN': {
            'Walk the rows before you walk the office.':
                'Đi thăm ruộng trước khi vào văn phòng.'}})
        data = me.lesson(self.course.id, self.article.id)
        self.assertEqual(data['both']['other_code'], 'VI')
        self.assertEqual(data['both']['name'], 'DEMO Thế nào là tốt')
        self.assertIn('văn phòng', str(data['both']['article']))
        vi = me.with_context(lang='vi_VN').lesson(self.course.id,
                                                  self.article.id)
        self.assertEqual(vi['both']['other_code'], 'EN')
        self.assertEqual(vi['both']['name'], 'DEMO What good looks like')
        self.assertIn('walk the office', str(vi['both']['article']))
        self.assertIn('văn phòng', str(vi['article']))

    def test_t6_missing_vietnamese_on_the_drawer(self):
        trainer = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO L7 drawer', 'login': 'demo.l7.drawer@example.com',
                'group_ids': [(6, 0, [self.env.ref(
                    'pb_training.group_training_user').id])]})
        data = self.Board.with_user(trainer).get_course(self.course.id)
        row = next(l for l in data['lessons'] if l['id'] == self.article.id)
        self.assertTrue(row['missing_vi'])
        self.article.with_context(lang='vi_VN').write(
            {'name': 'DEMO Thế nào là tốt'})
        self.article.update_field_translations('html_content', {'vi_VN': {
            'Walk the rows before you walk the office.': 'Tốt.'}})
        data = self.Board.with_user(trainer).get_course(self.course.id)
        row = next(l for l in data['lessons'] if l['id'] == self.article.id)
        self.assertFalse(row['missing_vi'])
        self.assertEqual(data['missing_vi'], len([
            l for l in data['lessons'] if l['missing_vi']]))

    def test_t6_the_toggle_is_remembered_and_works_without_a_script(self):
        js = _src('static', 'src', 'js', 'portal_lesson.js')
        self.assertIn('"pbtr.both"', js)
        ctl = _src('controllers', 'portal.py')
        self.assertIn("'both_on': kw.get('both') == '1'", ctl)
        xml = _src('views', 'portal_templates.xml')
        self.assertIn('?both=1', xml)
        self.assertIn('Show both languages', xml)


# =========================================================================
#  the certificate badge (LD8) — part of T5's design, tested beside it
# =========================================================================
@tagged('post_install', '-at_install')
class TestBadge(TrainingCase):

    def test_badge_initials_and_tone(self):
        from ..models.learner_l7 import badge_initials, BADGE_HEX
        self.assertEqual(badge_initials('Fire safety for the warehouse'), 'FS')
        self.assertEqual(badge_initials('An toàn lao động'), 'AT')
        self.assertEqual(badge_initials('DEMO Forklift licence'), 'FL')
        self.assertEqual(badge_initials(''), '·')
        self.assertEqual(BADGE_HEX['brand'], '#5A4BB0')

    def test_badge_is_drawn_on_the_wallet_and_my_learning(self):
        self.assertIn('pb_training.tr_badge', _src('views', 'portal_templates.xml'))
        self.assertIn('pb_training.CertBadge', _src(
            'static', 'src', 'xml', 'my_learning_lens.xml'))
        src = _src('models', 'learner_l7.py')
        self.assertNotIn("gamification.badge.user'].create", src)
        self.assertNotIn("gamification.badge.user'].sudo().create", src)


# =========================================================================
#  T9 — the home-screen manifest, and no service worker
# =========================================================================
@tagged('post_install', '-at_install')
class TestT9Manifest(HttpCase):

    def test_t9_manifest_json(self):
        res = self.url_open('/my/training/manifest.webmanifest')
        if res.status_code == 404:
            self.skipTest("this server's database filter does not let the "
                          "test reach this database")
        self.assertEqual(res.status_code, 200)
        self.assertIn('manifest+json', res.headers.get('Content-Type', ''))
        data = res.json()
        self.assertEqual(data['start_url'], '/my/training')
        self.assertEqual(data['scope'], '/my/training')
        self.assertEqual(data['name'], 'My training')
        self.assertEqual(data['display'], 'standalone')
        self.assertTrue(data['icons'])
        for icon in data['icons']:
            path = os.path.join(get_module_path('pb_training'),
                                icon['src'].split('/pb_training/', 1)[1])
            self.assertTrue(os.path.exists(path), icon['src'])

    def test_t9_no_service_worker_anywhere(self):
        base = os.path.join(get_module_path('pb_training'), 'static')
        for root, _dirs, files in os.walk(base):
            for name in files:
                if name.endswith('.js'):
                    with open(os.path.join(root, name), encoding='utf-8') as fh:
                        self.assertNotIn('serviceWorker.register', fh.read(),
                                         name)
        self.assertNotIn('service-worker', _src('controllers', 'portal.py'))
        self.assertIn('tr_pwa_head', _src('views', 'portal_templates.xml'))


# =========================================================================
#  T10 — white label, no emoji, Vietnamese
# =========================================================================
@tagged('post_install', '-at_install')
class TestT10Words(TrainingCase):

    def test_t10_no_vendor_word_no_emoji(self):
        """The vendor's name never appears in a word a person reads; the
        lower-case technical identifiers (`from odoo`, `<odoo>`) are code."""
        for rel in NEW_FILES + (('static', 'src', 'xml', 'my_learning_lens.xml'),
                                ('static', 'src', 'xml', 'training_board.xml'),
                                ('tests', 'js', 'portal_lesson.test.mjs')):
            text = _src(*rel)
            self.assertNotIn('Odoo', text, rel)
            self.assertNotIn('ODOO', text, rel)
            self.assertFalse(EMOJI.search(text), rel)

    def test_t10_vietnamese_for_the_new_words(self):
        po = _src('i18n', 'vi_VN.po')
        for msgid in ('Next for you', 'Three minutes today',
                      'Show both languages', 'Show one language',
                      'Saved on your phone. It will send when you are back online.',
                      'Sent while you were offline:', '<span>Open the file</span>',
                      '%s in a row, on time', 'Missing Vietnamese',
                      'Nothing to do right now.', 'Required for your job.'):
            m = re.search(r'msgid "%s"\nmsgstr "([^"]+)"' % re.escape(msgid), po)
            self.assertTrue(m and m.group(1), 'no Vietnamese for %r' % msgid)

    def test_t10_translatable_text_on_one_line(self):
        """LN13: an OWL / QWeb text node wrapped over lines gets a msgid with
        the newline in it, which no translation matches."""
        for rel in (('views', 'portal_l7.xml'),):
            text = _src(*rel)
            for m in re.finditer(r'<div data-w="\w+">([^<]*)</div>', text):
                self.assertNotIn('\n', m.group(1))
