# -*- coding: utf-8 -*-
"""LEARNING L5 — outside courses, course requests, versions, test results,
feedback, follow-ups, skills. Handover tests T1–T15 (T16 is the Chrome walk).

The rails: a request that writes money, a request agreed twice that puts the
course on twice, pre-booked money counted twice (or not at all) when the
claim comes in, a version that resets somebody who never finished or deletes
a certificate, a hardest-question figure that punishes a question for the
attempts that never drew it, a test results page any colleague can open,
feedback asked twice, a follow-up sent to nobody, a skill edited in place or
lowered, a manager reading somebody else's team, and an Inbox that drops the
receipt row.

Fixtures are "DEMO" and roll back. The classes run in a company of their own
(ledger LN32) and pin `lang='en_US'` (LN14).
"""

import base64
import json
import types
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .test_assignments import AssignmentCase
from .test_training import _PDF, _src

NEW_FILES = (
    ('models', 'outside_course.py'),
    ('models', 'request.py'),
    ('models', 'request_approval.py'),
    ('models', 'course_version.py'),
    ('models', 'test_results.py'),
    ('models', 'feedback.py'),
    ('models', 'skill_grant.py'),
    ('models', 'pb_training_catalogue.py'),
    ('models', 'pb_training_skills.py'),
    ('data', 'mail_template_l5.xml'),
    ('views', 'l5_views.xml'),
    ('views', 'portal_l5.xml'),
)


class L5Case(AssignmentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO L5 Co'})
        cls.env = cls.env(context=dict(
            cls.env.context, lang='en_US', tz='UTC',
            allowed_company_ids=[cls.company.id]))
        (cls.boss | cls.e_one | cls.e_two | cls.e_three).write(
            {'company_id': cls.company.id})
        for user in (cls.boss_user, cls.u_one, cls.u_two, cls.u_three):
            user.write({'company_ids': [(4, cls.company.id)],
                        'company_id': cls.company.id, 'tz': 'UTC'})
        cls.Request = cls.env['pb.training.request']
        cls.Outside = cls.env['pb.training.outside.course']
        cls.Claim = cls.env['pb.training.claim']
        cls.Board = cls.env['pb.training']
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def user(login, group):
            return Users.create({
                'name': login, 'login': login, 'email': login, 'tz': 'UTC',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref(group).id])]})
        cls.trainer = user('demo.l5.trainer@example.com',
                           'pb_training.group_training_user')
        cls.tmanager = user('demo.l5.tmanager@example.com',
                            'pb_training.group_training_manager')
        cls.plain = user('demo.l5.plain@example.com', 'base.group_user')
        cls.year = fields.Date.today().year
        cls.env['pb.training.allowance'].create({
            'company_id': cls.company.id, 'year': cls.year,
            'amount': 10000000.0,
            'currency_id': cls.company.currency_id.id})
        cls.job = cls.env['hr.job'].create({'name': 'DEMO L5 Agronomist',
                                            'company_id': cls.company.id})
        cls.ext = cls.Outside.create({
            'name': 'DEMO Pesticide licence', 'provider': 'DEMO Ag College',
            'url': 'https://example.com/licence', 'cost': 3000000.0,
            'currency_id': cls.company.currency_id.id, 'hours': 8.0,
            'kind': 'exam', 'company_id': cls.company.id,
            'job_ids': [(6, 0, [cls.job.id])]})
        cls.free = cls.Outside.create({
            'name': 'DEMO Soil webinar', 'provider': 'DEMO Online',
            'cost': 0.0, 'kind': 'online', 'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    def _dormant(self, keys=('training_request', 'training_claim')):
        if 'biz.approval.binding' not in self.env:
            return
        for key in keys:
            process = self.env['biz.approval.process'].sudo().search(
                [('key', '=', key)], limit=1)
            if process:
                self.env['biz.approval.binding'].sudo().search(
                    [('process_id', '=', process.id)]).write(
                        {'active': False})

    def _ask(self, user, **values):
        values.setdefault('why', 'DEMO it helps me do the job')
        return self.env['pb.my.training'].with_user(user).ask_course(values)

    def _approve(self, rec):
        rec = rec.sudo()
        rec._advance_state('approved')
        return rec

    def _mail_count(self):
        return self.env['mail.mail'].sudo().search_count([])


# =========================================================================
#  T1 — the outside catalogue
# =========================================================================
@tagged('post_install', '-at_install')
class TestT1Outside(L5Case):

    def test_t1_shape_and_cost_words(self):
        self.assertEqual(self.ext.kind, 'exam')
        self.assertIn('3,000,000', self.ext.cost_words())
        self.assertEqual(self.free.cost_words(), 'Free')
        self.assertEqual(self.ext.hours_words(), '8 hours')
        with self.assertRaises(ValidationError):
            self.Outside.create({'name': 'DEMO bad', 'cost': -1,
                                 'company_id': self.company.id})

    def test_t1_catalogue_filters(self):
        board = self.Board.with_user(self.trainer)
        data = board.outside_board({})
        self.assertTrue(data['allowed'])
        names = [r['name'] for r in data['rows']]
        self.assertIn('DEMO Pesticide licence', names)
        self.assertIn('DEMO Soil webinar', names)
        exams = board.outside_board({'kind': 'exam'})['rows']
        self.assertEqual([r['name'] for r in exams],
                         ['DEMO Pesticide licence'])
        by_job = board.outside_board({'job_id': self.job.id})['rows']
        self.assertEqual([r['name'] for r in by_job],
                         ['DEMO Pesticide licence'])
        found = board.outside_board({'q': 'soil'})['rows']
        self.assertEqual([r['name'] for r in found], ['DEMO Soil webinar'])
        self.assertEqual(self.Board.with_user(self.plain).outside_board({}),
                         {'allowed': False, 'rows': [], 'kpis': {}})

    def test_t1_save_checks_and_archive(self):
        board = self.Board.with_user(self.trainer)
        with self.assertRaises(UserError):
            board.save_outside({'name': ''})
        res = board.save_outside({'name': 'DEMO First aid', 'cost': 500000,
                                  'url': 'example.com/fa', 'hours': 4})
        rec = self.Outside.browse(res['id'])
        self.assertEqual(rec.url, 'https://example.com/fa')
        board.archive_outside(rec.id, False)
        self.assertFalse(rec.active)
        self.assertNotIn('DEMO First aid', [
            r['name'] for r in board.outside_board({})['rows']])


# =========================================================================
#  T2 — the route, the catalogue row, the seed, the detail rows
# =========================================================================
@tagged('post_install', '-at_install')
class TestT2Route(L5Case):

    def test_t2_route_branches_on_money(self):
        from odoo.addons.biz_approval_workflow.models import definition as D
        from odoo.addons.pb_training.models.request_approval import \
            request_route
        steps = request_route()['steps']
        self.assertEqual([s['who']['mode'] for s in steps],
                         ['manager', 'role'])
        self.assertFalse(steps[0].get('condition'))
        cond = steps[1]['condition']
        self.assertEqual(steps[1]['who']['role'], 'hr_lead')
        self._dormant()
        ours = self.Request.sudo().create({
            'employee_id': self.e_one.id, 'kind': 'ours',
            'channel_id': self.simple.id, 'course_name': self.simple.name,
            'why': 'DEMO'})
        outside = self.Request.sudo().create({
            'employee_id': self.e_one.id, 'kind': 'outside',
            'outside_course_id': self.ext.id, 'course_name': self.ext.name,
            'amount': 3000000.0, 'why': 'DEMO'})
        self.assertFalse(D.condition_holds(cond, ours._chain_facts()),
                         'one of ours goes to the manager only')
        self.assertTrue(D.condition_holds(cond, outside._chain_facts()),
                        'an outside course that costs money also goes to '
                        'the HR lead')
        specs = self.Request._chain_fact_specs()
        self.assertEqual(specs['amount']['type'], 'decimal')
        check = D.validate(request_route(),
                           capabilities={'facts': specs}, env=self.env)
        self.assertFalse(check.get('errors'), check.get('errors'))

    def test_t2_catalogue_row_and_seed(self):
        process = self.env['biz.approval.process'].sudo().search(
            [('key', '=', 'training_request')])
        self.assertEqual(len(process), 1)
        self.assertEqual(process.model_name, 'pb.training.request')
        from odoo.addons.pb_training.models.request_approval import seed_all
        seed_all(self.env)
        Binding = self.env['biz.approval.binding'].sudo()
        first = Binding.search_count([('process_id', '=', process.id)])
        seed_all(self.env)
        self.assertEqual(Binding.search_count(
            [('process_id', '=', process.id)]), first,
            'a second seed lays nothing')
        self.assertTrue(Binding.search_count([
            ('process_id', '=', process.id),
            ('company_id', '=', self.company.id)]),
            'the new company has its route too')

    def test_t2_detail_rows_are_dicts(self):
        self._dormant()
        req = self.Request.sudo().create({
            'employee_id': self.e_one.id, 'kind': 'outside',
            'outside_course_id': self.ext.id, 'course_name': self.ext.name,
            'amount': 3000000.0, 'url': self.ext.url, 'why': 'DEMO'})
        detail = req._approval_detail(None)
        self.assertTrue(detail['rows'])
        for row in detail['rows']:
            self.assertIsInstance(row, dict)
            self.assertEqual(set(row), {'head', 'sub', 'cells', 'tone'})


# =========================================================================
#  T3 — pre-booked money
# =========================================================================
@tagged('post_install', '-at_install')
class TestT3Committed(L5Case):

    def test_t3_agreed_request_is_set_aside_then_claimed(self):
        self._dormant()
        res = self._ask(self.u_one, kind='outside',
                        outside_course_id=self.ext.id)
        req = self.Request.browse(res['id']).sudo()
        self.assertEqual(req.state, 'submitted')
        facts = self.Claim._facts_for(self.e_one, self.year)
        self.assertEqual(facts['committed'], 0.0,
                         'a request waiting for a decision books nothing')
        self._approve(req)
        facts = self.Claim._facts_for(self.e_one, self.year)
        self.assertEqual(facts['committed'], 3000000.0)
        self.assertEqual(facts['left'], 7000000.0)
        # The claim from the request: pre-filled, not counted against itself.
        claim_res = self.env['pb.my.training'].with_user(self.u_one) \
            .raise_claim({'request_id': req.id, 'paid_on':
                          fields.Date.today(), 'course_name': '',
                          'amount': 0},
                         invoice=('r.pdf', base64.b64decode(_PDF)),
                         certificate=('c.pdf', base64.b64decode(_PDF)))
        claim = self.Claim.browse(claim_res['id']).sudo()
        self.assertEqual(claim.course_name, 'DEMO Pesticide licence')
        self.assertEqual(claim.amount, 3000000.0)
        self.assertEqual(claim.request_id, req)
        self.assertEqual(req.claim_id, claim)
        claim._advance_state('approved')
        self.assertEqual(req.state, 'claimed')
        facts = self.Claim._facts_for(self.e_one, self.year)
        self.assertEqual(facts['committed'], 0.0)
        self.assertEqual(facts['agreed'], 3000000.0)
        self.assertEqual(facts['left'], 7000000.0,
                         'the money moved from set aside to agreed — never '
                         'counted twice, never dropped')

    def test_t3_over_allowance_sentence_and_switch(self):
        self._dormant()
        big = self.Outside.create({
            'name': 'DEMO MBA module', 'cost': 8000000.0,
            'company_id': self.company.id})
        first = self._ask(self.u_one, kind='outside',
                          outside_course_id=self.ext.id)
        self._approve(self.Request.browse(first['id']))
        with self.assertRaises(UserError) as caught:
            self._ask(self.u_one, kind='outside', outside_course_id=big.id)
        self.assertIn('set aside', str(caught.exception))
        self.assertIn('7,000,000', str(caught.exception))
        self.assertFalse(self.Request.sudo().search(
            [('outside_course_id', '=', big.id)]),
            'a refusal leaves nothing behind')
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.claim_over_allowance', '1')
        res = self._ask(self.u_one, kind='outside', outside_course_id=big.id)
        self.assertEqual(self.Request.browse(res['id']).sudo().state,
                         'submitted')

    def test_t3_a_request_never_writes_money(self):
        self._dormant()
        before = self.env['pb.incentive'].sudo().search_count([])
        res = self._ask(self.u_one, kind='outside',
                        outside_course_id=self.ext.id)
        self._approve(self.Request.browse(res['id']))
        self.assertEqual(self.env['pb.incentive'].sudo().search_count([]),
                         before)


# =========================================================================
#  T4 — what an agreement / refusal / cancel does
# =========================================================================
@tagged('post_install', '-at_install')
class TestT4Decisions(L5Case):

    def test_t4_ours_assigns_once(self):
        self._dormant()
        res = self._ask(self.u_one, kind='ours', channel_id=self.simple.id)
        req = self._approve(self.Request.browse(res['id']))
        self.assertTrue(req.assignment_id)
        self.assertEqual(req.assignment_id.request_id, req)
        self.assertEqual(req.assignment_id.reason, 'adhoc')
        req._on_approved()
        self.assertEqual(self.env['pb.training.assignment'].sudo()
                         .search_count([('employee_id', '=', self.e_one.id),
                                        ('channel_id', '=', self.simple.id)]),
                         1, 'agreed twice is still one course')
        # Finishing it makes the request "Taken".
        self._finish(self.u_one, self.simple, self.simple_lesson)
        req.assignment_id._refresh()
        self.assertEqual(req.state, 'taken')

    def test_t4_refusal_mails_the_reason(self):
        self._dormant()
        res = self._ask(self.u_one, kind='outside',
                        outside_course_id=self.ext.id)
        req = self.Request.browse(res['id']).sudo()
        req.write({'refuse_note': 'DEMO not this quarter'})
        before = self._mail_count()
        req.action_refuse_chain('DEMO not this quarter')
        self.assertEqual(req.state, 'refused')
        mails = self.env['mail.mail'].sudo().search([], order='id desc',
                                                    limit=self._mail_count()
                                                    - before)
        self.assertTrue(any('DEMO not this quarter' in (m.body_html or '')
                            for m in mails))

    def test_t4_cancel_while_submitted(self):
        self._dormant()
        res = self._ask(self.u_one, kind='outside',
                        outside_course_id=self.ext.id)
        self.env['pb.my.training'].with_user(self.u_one).cancel_request(
            res['id'])
        self.assertEqual(self.Request.browse(res['id']).sudo().state,
                         'cancelled')
        with self.assertRaises(AccessError):
            self.env['pb.my.training'].with_user(self.u_two).cancel_request(
                res['id'])

    def test_t4_put_on_by_the_training_team(self):
        res = self.Board.with_user(self.trainer).put_on_outside({
            'outside_course_id': self.ext.id,
            'employee_ids': [self.e_two.id], 'why': 'DEMO licence due'})
        self.assertEqual(res['made'], 1)
        req = self.Request.sudo().search([('employee_id', '=', self.e_two.id)])
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.put_on_by_id, self.trainer)
        with self.assertRaises(AccessError):
            self.Board.with_user(self.plain).put_on_outside({
                'outside_course_id': self.ext.id,
                'employee_ids': [self.e_three.id]})


# =========================================================================
#  T5 — the learner's page
# =========================================================================
@tagged('post_install', '-at_install')
class TestT5Learner(L5Case):

    def test_t5_options_ownership_duplicates(self):
        self._dormant()
        me = self.env['pb.my.training'].with_user(self.u_one)
        opts = me.request_options()
        self.assertTrue(opts['has_employee'])
        self.assertIn(self.ext.id, [o['id'] for o in opts['outside']])
        self._ask(self.u_one, kind='outside', outside_course_id=self.ext.id)
        self.assertNotIn(self.ext.id,
                         [o['id'] for o in me.request_options()['outside']])
        with self.assertRaises(ValidationError):
            self._ask(self.u_one, kind='outside',
                      outside_course_id=self.ext.id)
        with self.assertRaises(UserError):
            self._ask(self.u_one, kind='outside',
                      outside_course_id=self.ext.id, why='  ')
        rows = me.my_requests()['rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['state_word'], 'Waiting for a decision')
        self.assertFalse(self.env['pb.my.training'].with_user(self.u_two)
                         .my_requests()['rows'])

    def test_t5_status_words_in_vietnamese(self):
        self._dormant()
        res = self._ask(self.u_one, kind='outside',
                        outside_course_id=self.ext.id)
        req = self.Request.browse(res['id']).sudo()
        en = req._payload()['state_word']
        vi = req.with_context(lang='vi_VN')._payload()['state_word']
        if self.env['res.lang']._lang_get('vi_VN'):
            self.assertNotEqual(en, vi)

    def test_t5_portal_page_routes_exist(self):
        src = _src('controllers', 'portal.py')
        for route in ('/my/training/requests', '/my/training/requests/new',
                      '/my/training/feedback/<string:token>'):
            self.assertIn(route, src)


# =========================================================================
#  T6 — publishing a new version
# =========================================================================
@tagged('post_install', '-at_install')
class TestT6Versions(L5Case):

    def _finished(self, user, emp):
        row = self.env['pb.training.assignment'].sudo().create({
            'channel_id': self.simple.id, 'employee_id': emp.id})
        self._finish(user, self.simple, [self.simple_lesson])
        row._refresh()
        self.assertEqual(row.state, 'done')
        return row

    def test_t6_resets_finishers_only_and_rereads_once(self):
        self._finished(self.u_one, self.e_one)
        docs = self.env['pb.employee.document'].sudo().search_count([])
        before = self._mail_count()
        res = self.Board.with_user(self.tmanager).publish_version(
            self.simple.id, 'DEMO step 3 changed')
        self.assertEqual(res['version'], 2)
        self.assertEqual(res['people'], 1)
        done = self.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', self.simple_lesson.id),
            ('partner_id', '=', self.u_one.partner_id.id)])
        self.assertFalse(done.completed, 'their progress was reset')
        rereads = self.env['pb.training.assignment'].sudo().search([
            ('channel_id', '=', self.simple.id), ('reason', '=', 'reread')])
        self.assertEqual(rereads.mapped('employee_id'), self.e_one)
        self.assertEqual(rereads.course_version, 2)
        self.assertFalse(rereads.counts_for_probation)
        self.assertEqual(self.env['pb.employee.document'].sudo()
                         .search_count([]), docs, 'certificates untouched')
        self.assertTrue(self.env['mail.mail'].sudo().search(
            [('id', '>', 0)], order='id desc', limit=self._mail_count()
            - before).filtered(lambda m: 'has changed' in (m.subject or '')))
        self.simple._pb_reread_batch()
        self.assertEqual(self.env['pb.training.assignment'].sudo()
                         .search_count([('channel_id', '=', self.simple.id),
                                        ('reason', '=', 'reread')]), 1)

    def test_t6_cap_and_the_morning_remainder(self):
        self._finished(self.u_one, self.e_one)
        self._finished(self.u_two, self.e_two)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.reread_cap', '1')
        res = self.Board.with_user(self.tmanager).publish_version(
            self.simple.id, 'DEMO new rule')
        self.assertEqual((res['people'], res['done'], res['left']), (2, 1, 1))
        self.assertTrue(self.simple.pb_version_pending)
        self.env['pb.training.automation']._rereads()
        self.assertEqual(self.env['pb.training.assignment'].sudo()
                         .search_count([('channel_id', '=', self.simple.id),
                                        ('reason', '=', 'reread')]), 2)
        self.assertFalse(self.simple.pb_version_pending)

    def test_t6_trainer_cannot_publish(self):
        with self.assertRaises(AccessError):
            self.Board.with_user(self.trainer).publish_version(
                self.simple.id, 'DEMO')
        with self.assertRaises(UserError):
            self.Board.with_user(self.tmanager).publish_version(
                self.simple.id, '  ')


# =========================================================================
#  T7 / T8 — test results and pools
# =========================================================================
@tagged('post_install', '-at_install')
class TestT7Results(L5Case):

    def _pool_survey(self):
        survey = self.env['survey.survey'].create({
            'title': 'DEMO L5 pool test', 'survey_type': 'assessment',
            'certification': True, 'scoring_type': 'scoring_with_answers',
            'scoring_success_min': 50, 'questions_selection': 'random'})
        page = self.env['survey.question'].create({
            'survey_id': survey.id, 'title': 'DEMO section', 'is_page': True,
            'sequence': 1, 'random_questions_count': 2})
        qs = []
        for i in range(3):
            qs.append(self.env['survey.question'].create({
                'survey_id': survey.id, 'title': 'DEMO Q%s' % (i + 1),
                'sequence': 2 + i, 'question_type': 'simple_choice',
                'suggested_answer_ids': [
                    (0, 0, {'value': 'Right', 'is_correct': True,
                            'answer_score': 1}),
                    (0, 0, {'value': 'Wrong', 'answer_score': 0})]}))
        multi = self.env['survey.question'].create({
            'survey_id': survey.id, 'title': 'DEMO Multi', 'sequence': 9,
            'question_type': 'multiple_choice',
            'suggested_answer_ids': [
                (0, 0, {'value': 'A', 'is_correct': True, 'answer_score': 1}),
                (0, 0, {'value': 'B', 'is_correct': True, 'answer_score': 1}),
                (0, 0, {'value': 'C', 'answer_score': -1})]})
        return survey, page, qs, multi

    def _attempt(self, survey, partner, drawn, answers, pct, success):
        att = self.env['survey.user_input'].create({
            'survey_id': survey.id, 'partner_id': partner.id,
            'predefined_question_ids': [(6, 0, [q.id for q in drawn])]})
        for question, picks in answers:
            for pick in picks:
                self.env['survey.user_input.line'].create({
                    'user_input_id': att.id, 'question_id': question.id,
                    'answer_type': 'suggestion',
                    'suggested_answer_id': pick.id})
        att.write({'state': 'done', 'scoring_percentage': pct,
                   'scoring_success': success})
        return att

    def test_t7_pass_rate_histogram_and_hardest(self):
        survey, page, qs, multi = self._pool_survey()
        right = lambda q: q.suggested_answer_ids.filtered('is_correct')[:1]
        wrong = lambda q: q.suggested_answer_ids.filtered(
            lambda a: not a.is_correct)[:1]
        p1, p2, p3 = (self.u_one.partner_id, self.u_two.partner_id,
                      self.u_three.partner_id)
        # Q1 drawn 3 times, wrong once; Q3 drawn once, wrong once.
        self._attempt(survey, p1, [qs[0], qs[1], multi],
                      [(qs[0], [right(qs[0])]), (qs[1], [right(qs[1])]),
                       (multi, multi.suggested_answer_ids.filtered(
                           'is_correct'))], 100, True)
        self._attempt(survey, p2, [qs[0], qs[2], multi],
                      [(qs[0], [wrong(qs[0])]), (qs[2], [wrong(qs[2])]),
                       (multi, multi.suggested_answer_ids)], 15, False)
        self._attempt(survey, p3, [qs[0], qs[1], multi],
                      [(qs[0], [right(qs[0])]), (qs[1], [right(qs[1])]),
                       (multi, multi.suggested_answer_ids.filtered(
                           'is_correct'))], 100, True)
        data = self.Board.with_user(self.trainer).test_results(survey.id)
        self.assertEqual(data['attempts'], 3)
        self.assertEqual(data['pass_rate'], 67)
        self.assertEqual(sum(b['n'] for b in data['histogram']), 3)
        self.assertEqual(data['histogram'][9]['n'], 2)
        self.assertEqual(data['histogram'][1]['n'], 1)
        hard = {h['question']: h for h in data['hardest']}
        self.assertEqual((hard['DEMO Q3']['asked'], hard['DEMO Q3']['wrong'],
                          hard['DEMO Q3']['pct']), (1, 1, 100),
                         'asked = drawn for the attempt, not every attempt')
        self.assertEqual((hard['DEMO Q1']['asked'], hard['DEMO Q1']['wrong']),
                         (3, 1))
        self.assertEqual((hard['DEMO Multi']['asked'],
                          hard['DEMO Multi']['wrong']), (3, 1),
                         'a multi-choice question counts once per attempt')
        self.assertEqual(data['hardest'][0]['question'], 'DEMO Q3')
        self.assertIn('2 of', data['pool_words'])

    def test_t8_new_test_with_a_pool(self):
        res = self.Board.with_user(self.trainer).create_test(
            {'name': 'DEMO L5 drawn test', 'pass_mark': 80, 'attempts': 2,
             'draw': 3})
        survey = self.env['survey.survey'].browse(res['id'])
        self.assertEqual(survey.questions_selection, 'random')
        self.assertTrue(survey.certification)
        self.assertEqual(survey.scoring_success_min, 80)
        self.assertEqual(len(survey.page_ids), 1)
        self.assertEqual(survey.page_ids.random_questions_count, 3)
        self.assertEqual(res['action']['res_model'], 'survey.survey')
        plain = self.Board.with_user(self.trainer).create_test(
            {'name': 'DEMO L5 all questions'})
        self.assertEqual(self.env['survey.survey'].browse(plain['id'])
                         .questions_selection, 'all')
        self.Board.with_user(self.trainer).set_pool(plain['id'], 0)
        with self.assertRaises(AccessError):
            self.Board.with_user(self.plain).create_test({'name': 'DEMO x'})


@tagged('post_install', '-at_install')
class TestT9ResultsGate(HttpCase):

    def test_t9_results_page_is_for_the_training_team(self):
        """The stock route already refuses somebody with no survey group
        (403 from the record converter). The gate is for the people who DO
        hold a survey group for something else — HR running a pulse survey —
        and no training group: a test's results are not theirs."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        surveyor = Users.create({
            'name': 'DEMO L5 gate surveyor', 'login': 'demo.l5.gate.surveyor',
            'password': 'demo.l5.gate.surveyor',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('survey.group_survey_user').id])
                          ]})
        trainer = Users.create({
            'name': 'DEMO L5 gate trainer', 'login': 'demo.l5.gate.trainer',
            'password': 'demo.l5.gate.trainer',
            'group_ids': [(6, 0, [self.env.ref(
                'pb_training.group_training_user').id])]})
        test = self.env['survey.survey'].create({
            'title': 'DEMO L5 gated', 'survey_type': 'assessment',
            'certification': True, 'scoring_type': 'scoring_with_answers'})
        pulse = self.env['survey.survey'].create({
            'title': 'DEMO L5 pulse', 'survey_type': 'survey'})
        self.assertTrue(surveyor and trainer)
        self.authenticate('demo.l5.gate.surveyor', 'demo.l5.gate.surveyor')
        res = self.url_open('/survey/results/%s' % test.id,
                            allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('/my/training', res.headers.get('Location', ''))
        res = self.url_open('/survey/results/%s' % pulse.id,
                            allow_redirects=False)
        self.assertEqual(res.status_code, 200,
                         'an ordinary survey is not touched')
        self.authenticate('demo.l5.gate.trainer', 'demo.l5.gate.trainer')
        res = self.url_open('/survey/results/%s' % test.id,
                            allow_redirects=False)
        self.assertEqual(res.status_code, 200)


# =========================================================================
#  T10 / T11 — feedback and the follow-up
# =========================================================================
@tagged('post_install', '-at_install')
class TestT10Feedback(L5Case):

    def _done(self, user, emp):
        row = self.env['pb.training.assignment'].sudo().create({
            'channel_id': self.simple.id, 'employee_id': emp.id})
        self._finish(user, self.simple, [self.simple_lesson])
        row._refresh()
        return row

    def test_t10_asked_once_and_rolled_up(self):
        row = self._done(self.u_one, self.e_one)
        Feedback = self.env['pb.feedback.request'].sudo()
        reqs = Feedback.search([('assignment_id', '=', row.id),
                                ('kind', '=', 'training')])
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs.respondent_user_id, self.u_one)
        self.assertEqual(reqs.channel_id, self.simple)
        row._refresh()
        self.env['pb.training.feedback.maker']._plan(
            self.e_one, channel=self.simple, assignment=row)
        self.assertEqual(Feedback.search_count(
            [('assignment_id', '=', row.id), ('kind', '=', 'training')]), 1)
        reqs.submit_answers({'useful': {'value': '4'},
                             'recommend': {'value': '5'},
                             'change': {'value': 'DEMO more pictures'}})
        self.assertEqual(self.simple.pb_avg_rating, 4.0)
        self.assertEqual(self.simple.pb_ratings_count, 1)
        self.assertEqual(self.simple.pb_recommend_pct, 100)
        extras = self.Board.with_user(self.trainer).course_extras(
            self.simple.id)
        self.assertEqual(extras['rating_words'], '4.0 · 1 rating')
        self.assertEqual(extras['ratings']['comments'][0]['text'],
                         'DEMO more pictures')

    def test_t10_switch_off_asks_nothing(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.feedback_on', '0')
        row = self._done(self.u_one, self.e_one)
        self.assertFalse(self.env['pb.feedback.request'].sudo().search(
            [('assignment_id', '=', row.id), ('kind', '=', 'training')]))

    def test_t10_token_page_words_the_course(self):
        row = self._done(self.u_one, self.e_one)
        req = self.env['pb.feedback.request'].sudo().search(
            [('assignment_id', '=', row.id), ('kind', '=', 'training')])
        self.assertIn('/my/training/feedback/', req._pb_feedback_url())
        self.assertEqual(req._pb_course_name(), self.simple.name)


@tagged('post_install', '-at_install')
class TestT11Followup(L5Case):

    def test_t11_planned_sent_answered(self):
        row = self.env['pb.training.assignment'].sudo().create({
            'channel_id': self.simple.id, 'employee_id': self.e_one.id})
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh()
        fu = self.env['pb.training.followup'].sudo().search(
            [('assignment_id', '=', row.id)])
        self.assertEqual(fu.state, 'planned')
        self.assertEqual(fu.manager_id, self.boss)
        self.assertEqual(fu.due_date, row.completed_on + timedelta(days=30))
        Auto = self.env['pb.training.automation']
        self.assertEqual(Auto._send_followups(fields.Date.today()), 0,
                         'not before its day')
        self.assertEqual(Auto._send_followups(fu.due_date), 1)
        self.assertEqual(fu.state, 'sent')
        req = fu.feedback_request_id
        self.assertEqual(req.kind, 'training_followup')
        self.assertEqual(req.respondent_user_id, self.boss_user)
        self.assertEqual(Auto._send_followups(fu.due_date), 0,
                         'sent once')
        req.submit_answers({'effect': {'value': '4'},
                            'used': {'value': 'Partly'}})
        self.assertEqual(fu.state, 'answered')
        extras = self.Board.with_user(self.trainer).course_extras(
            self.simple.id)
        self.assertEqual(extras['ratings']['effect_avg'], 4.0)
        self.assertEqual(extras['ratings']['used_pct'], 100)

    def test_t11_no_manager_is_skipped(self):
        self.e_two.parent_id = False
        row = self.env['pb.training.assignment'].sudo().create({
            'channel_id': self.simple.id, 'employee_id': self.e_two.id})
        self._finish(self.u_two, self.simple, [self.simple_lesson])
        row._refresh()
        fu = self.env['pb.training.followup'].sudo().search(
            [('assignment_id', '=', row.id)])
        self.assertEqual(fu.state, 'skipped')


# =========================================================================
#  T12 / T13 — skills
# =========================================================================
class SkillCase(L5Case):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stype = cls.env['hr.skill.type'].create({
            'name': 'DEMO L5 Field skills',
            'skill_level_ids': [
                (0, 0, {'name': 'DEMO Basic', 'level_progress': 25}),
                (0, 0, {'name': 'DEMO Good', 'level_progress': 75})],
            'skill_ids': [(0, 0, {'name': 'DEMO Field safety'}),
                          (0, 0, {'name': 'DEMO Spraying'})]})
        cls.basic = cls.stype.skill_level_ids.filtered(
            lambda lv: lv.level_progress == 25)
        cls.good = cls.stype.skill_level_ids.filtered(
            lambda lv: lv.level_progress == 75)
        cls.safety = cls.stype.skill_ids.filtered(
            lambda s: s.name == 'DEMO Field safety')
        cls.spraying = cls.stype.skill_ids - cls.safety
        cls.grant = cls.env['pb.training.skill.grant'].create({
            'channel_id': cls.simple.id, 'skill_id': cls.safety.id,
            'skill_level_id': cls.good.id})

    def _have(self, emp, skill):
        return emp.current_employee_skill_ids.filtered(
            lambda s: s.skill_id == skill)


@tagged('post_install', '-at_install')
class TestT12Grants(SkillCase):

    def test_t12_archive_and_create_no_downgrade(self):
        old = self.env['hr.employee.skill'].create({
            'employee_id': self.e_one.id, 'skill_id': self.safety.id,
            'skill_level_id': self.basic.id, 'skill_type_id': self.stype.id,
            'valid_from': fields.Date.today() - timedelta(days=30)})
        row = self.env['pb.training.assignment'].sudo().create({
            'channel_id': self.simple.id, 'employee_id': self.e_one.id})
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh()
        self.e_one.invalidate_recordset()
        now = self._have(self.e_one, self.safety)
        self.assertEqual(now.skill_level_id, self.good)
        self.assertTrue(old.exists(), 'the old row is kept as history')
        self.assertEqual(old.valid_to, fields.Date.today() - timedelta(days=1),
                         'and closed, never edited to the new level')
        self.assertEqual(old.skill_level_id, self.basic)
        # No downgrade: a Basic grant does nothing to somebody at Good.
        low = self.env['pb.training.skill.grant'].create({
            'channel_id': self.simple.id, 'skill_id': self.safety.id,
            'skill_level_id': self.basic.id})
        self.assertEqual(self.env['pb.training.skill.grant']._grant(
            self.e_one, low), [])

    def test_t12_outside_course_taken_grants(self):
        self.env['pb.training.skill.grant'].create({
            'outside_course_id': self.ext.id, 'skill_id': self.spraying.id,
            'skill_level_id': self.basic.id})
        self.Board.with_user(self.trainer).put_on_outside({
            'outside_course_id': self.ext.id, 'employee_ids': [self.e_two.id]})
        req = self.Request.sudo().search([('employee_id', '=', self.e_two.id)])
        self.Board.with_user(self.trainer).mark_taken(req.id)
        self.assertEqual(req.state, 'taken')
        self.e_two.invalidate_recordset()
        self.assertEqual(self._have(self.e_two, self.spraying).skill_level_id,
                         self.basic)


@tagged('post_install', '-at_install')
class TestT13Board(SkillCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['hr.job.skill'].create([
            {'job_id': cls.job.id, 'skill_id': cls.safety.id,
             'skill_level_id': cls.good.id, 'skill_type_id': cls.stype.id},
            {'job_id': cls.job.id, 'skill_id': cls.spraying.id,
             'skill_level_id': cls.basic.id, 'skill_type_id': cls.stype.id}])
        (cls.e_one | cls.e_two).write({'job_id': cls.job.id})
        cls.env['hr.employee.skill'].create([
            {'employee_id': cls.e_one.id, 'skill_id': cls.safety.id,
             'skill_level_id': cls.good.id, 'skill_type_id': cls.stype.id},
            {'employee_id': cls.e_two.id, 'skill_id': cls.safety.id,
             'skill_level_id': cls.basic.id, 'skill_type_id': cls.stype.id}])
        cls.outsider_user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO L5 outsider', 'login': 'demo.l5.out@example.com',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.outsider = cls.env['hr.employee'].create({
            'name': 'DEMO L5 outsider', 'user_id': cls.outsider_user.id,
            'company_id': cls.company.id, 'job_id': cls.job.id})

    def test_t13_states_course_and_hero(self):
        data = self.Board.with_user(self.trainer).skills_board({})
        self.assertTrue(data['allowed'])
        rows = {p['employee']: p for p in data['people']}
        one = {r['skill']: r for r in rows[self.e_one.name]['required']}
        two = {r['skill']: r for r in rows[self.e_two.name]['required']}
        self.assertEqual(one['DEMO Field safety']['state'], 'ok')
        self.assertEqual(one['DEMO Spraying']['state'], 'missing')
        self.assertEqual(two['DEMO Field safety']['state'], 'below')
        self.assertEqual(two['DEMO Field safety']['courses'][0]['id'],
                         self.simple.id, 'the course that closes it')
        self.assertFalse(one['DEMO Spraying']['courses'])
        self.assertIn('required skills', data['headline'])
        only = self.Board.with_user(self.trainer).skills_board(
            {'only_gaps': True})
        self.assertTrue(all(p['gap_count'] for p in only['people']))

    def test_t13_a_manager_sees_their_team_only(self):
        self.assertTrue(self.Board.with_user(self.boss_user)
                        .can_see_skills())
        data = self.Board.with_user(self.boss_user).skills_board({})
        names = {p['employee'] for p in data['people']}
        self.assertTrue(data['team'])
        self.assertIn(self.e_one.name, names)
        self.assertNotIn(self.outsider.name, names)
        self.assertFalse(data['can_close'])
        self.assertFalse(self.Board.with_user(self.outsider_user)
                         .can_see_skills())
        self.assertEqual(self.Board.with_user(self.outsider_user)
                         .skills_board({})['allowed'], False)

    def test_t13_close_it(self):
        res = self.Board.with_user(self.trainer).close_gap({
            'employee_id': self.e_two.id, 'kind': 'ours',
            'id': self.simple.id, 'skill': 'DEMO Field safety'})
        self.assertIn('DEMO Walking the rows', res['message'])


# =========================================================================
#  T14 — the Inbox shows the claim's files
# =========================================================================
@tagged('post_install', '-at_install')
class TestT14Inbox(L5Case):

    def test_t14_receipt_row_reaches_the_inbox(self):
        if 'pb.approval.inbox' not in self.env:
            self.skipTest('the approvals inbox is not installed')
        self._dormant()
        claim = self.Claim.create({
            'employee_id': self.e_one.id, 'course_name': 'DEMO Excel',
            'amount': 1000000.0, 'paid_on': fields.Date.today(),
            'company_id': self.company.id,
            'currency_id': self.company.currency_id.id})
        claim.write({'invoice_file': _PDF, 'invoice_filename': 'DEMO r.pdf',
                     'certificate_file': _PDF,
                     'certificate_filename': 'DEMO c.pdf'})
        claim._advance_state('submitted')
        fake = types.SimpleNamespace(res_model='pb.training.claim',
                                     res_id=claim.id)
        detail = self.env['pb.approval.inbox']._detail(fake)
        self.assertTrue(detail)
        heads = [r['head'] for r in detail['rows']]
        self.assertIn('Receipt', heads)
        self.assertIn('Certificate', heads)
        self.assertEqual(detail['rows'][0]['cells'], ['DEMO r.pdf'])


# =========================================================================
#  T15 — white label, emoji, Vietnamese, the rail
# =========================================================================
@tagged('post_install', '-at_install')
class TestT15Words(L5Case):

    def test_t15_no_vendor_word_no_emoji(self):
        import re
        emoji = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
        for parts in NEW_FILES:
            text = _src(*parts)
            low = text.lower()
            for line in low.splitlines():
                if 'odoo' in line and not any(
                        ok in line for ok in ('from odoo', 'import odoo',
                                              'odoo.addons', 'odoo.tests',
                                              'odoo.tools', 'odoo.exceptions',
                                              '<odoo', '</odoo')):
                    self.fail('%s: %s' % ('/'.join(parts), line.strip()))
            self.assertFalse(emoji.search(text), '/'.join(parts))

    def test_t15_vietnamese_present(self):
        po = _src('i18n', 'vi_VN.po')
        for word in ('Waiting for a decision', 'Changed course',
                     'Ask to take a course', 'Outside courses',
                     'Course requests waiting'):
            self.assertIn('msgid "%s"' % word, po, word)

    def test_t15_reason_word(self):
        from odoo.addons.pb_training.models.training_common import \
            ASSIGN_REASON_LABEL
        self.assertEqual(ASSIGN_REASON_LABEL['reread'], 'Changed course')

    def test_t15_overview_queue_rows(self):
        data = self.Board.with_user(self.trainer).overview()
        keys = [q['key'] for q in data['queue']]
        self.assertIn('course_requests', keys)
        self.assertIn('followups', keys)

    def test_t15_numbers_sections(self):
        data = self.env['pb.training.analytics'].with_user(
            self.trainer).get_numbers(False, False, {})
        for key in ('ratings', 'did_it_work', 'course_requests', 'skills'):
            self.assertIn(key, data)
