# -*- coding: utf-8 -*-
"""WDGAP S9-A — review forms. Numbered as in WDGAP_S9A_REPORT.md §2.

The goals world is pb_goals' own (`YearCase`: one company, a goal year, a
boss with a member of staff and a stranger). Imported as a base CLASS with no
tests of its own, so the loader runs only the tests written here.
"""

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_goals.models.goals_common import RATINGS
from odoo.addons.pb_goals.models.pay_score import PbGoalSetPayScore
from odoo.addons.pb_goals.models.pb_goals_year import PbGoalsYear
from odoo.addons.pb_goals.models.pb_my_goals_year import PbMyGoalsYear
from odoo.addons.pb_goals.tests.test_goals_year import YearCase

BASE_PAY_SCORE = PbGoalSetPayScore._pay_score

#: Throwaway sign-in words for the test logins, made fresh on every run.
_PW = uuid.uuid4().hex


class RFCase(YearCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.hr_user = Users.create({
            'name': 'DEMO HR Lead', 'login': 'demo.rf.hr@example.com',
            'email': 'demo.rf.hr@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('pb_goals.group_goals_manager').id])],
        })
        cls.goals_admin = Users.create({
            'name': 'DEMO Goals Admin', 'login': 'demo.rf.gadmin@example.com',
            'email': 'demo.rf.gadmin@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('pb_goals.group_goals_user').id])],
        })
        cls.portal_user = Users.create({
            'name': 'DEMO Portal Worker', 'login': 'demo.rf.portal@example.com',
            'email': 'demo.rf.portal@example.com', 'password': _PW,
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.worker = cls.env['hr.employee'].create({
            'name': 'DEMO Portal Worker', 'company_id': cls.company.id,
            'user_id': cls.portal_user.id, 'parent_id': cls.boss.id,
            'work_email': 'demo.rf.portal@example.com'})
        cls.F = cls.env['pb.review.forms']
        cls.Form = cls.env['pb.review.form']
        cls.Entry = cls.env['pb.review.entry']

    # ------------------------------------------------------------- helpers
    def _form(self, publish=True, reveal='manager_done', reveal_date=False,
              questions=None, skills=('DEMO Ownership', 'DEMO Teamwork'),
              shares=(70, 30, 0)):
        F = self.F.with_user(self.hr_user)
        F.studio_save(self.cycle.id, {
            'name': 'DEMO End-of-year review',
            'share_goals': shares[0], 'share_skills': shares[1],
            'share_questions': shares[2],
            'reveal': reveal, 'reveal_date': reveal_date,
            'skills': [{'name': name, 'description': 'DEMO'} for name in skills],
            'questions': questions if questions is not None else [
                {'name': 'DEMO What went well?', 'qtype': 'text', 'who': 'both',
                 'required': True}],
        })
        if publish:
            F.studio_publish(self.cycle.id)
        return self.Form.search([('cycle_id', '=', self.cycle.id)])

    def _review(self, employee=None, mark='4'):
        sheet = self._agreed(employee or self.staff)
        if mark:
            self._score_all(sheet, mark)
        review = sheet._ensure_review('year_end', self.cycle.date_end)
        return sheet, review

    def _lines(self, form):
        skills = form._skills()
        questions = form._questions()
        return skills, questions

    def _self_answers(self, form, rating='4'):
        skills, questions = self._lines(form)
        out = {line.id: rating for line in skills}
        for line in questions:
            if line._asks('employee'):
                out[line.id] = 'DEMO my answer' if line.qtype == 'text' else rating
        return out

    def _mgr_answers(self, form, ratings=('3', '4')):
        skills, questions = self._lines(form)
        out = {line.id: ratings[i % len(ratings)] for i, line in enumerate(skills)}
        for line in questions:
            if line._asks('manager'):
                out[line.id] = ('DEMO manager answer' if line.qtype == 'text'
                                else '4')
        return out

    def _send_self(self, review, form, user=None):
        return self.F.with_user(user or self.staff_user).my_save(
            review.id, self._self_answers(form), send=True)

    def _finish(self, review, form, without_self=False):
        return self.F.with_user(self.boss_user).drawer_save(
            review.id, self._mgr_answers(form), 'DEMO a strong year overall.',
            True, without_self)

    def _entry(self, review):
        return self.Entry.sudo().search([('review_id', '=', review.id)])


# =========================================================================
#  T1 one form per goal year; a draft changes nothing
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestForms(RFCase):

    def test_01_one_form_per_goal_year(self):
        self._form(publish=False)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Form.create({'cycle_id': self.cycle.id})

    def test_01_a_draft_form_is_not_used(self):
        self._form(publish=False)
        sheet, review = self._review()
        self.assertFalse(review._rf_applies())
        self.assertEqual(sheet._pay_score(), BASE_PAY_SCORE(sheet))

    # ---------------------------------------------------------------- T2
    def test_02_five_point_scale_is_the_goals_scale(self):
        form = self._form()
        self.assertEqual(
            [r['key'] for r in self.F.studio_load(self.cycle.id)['ratings']],
            [key for key, _l in RATINGS])
        self.assertEqual(dict(RATINGS)['1'], 'Well below')
        self.assertEqual(dict(RATINGS)['5'], 'Well above')
        _sheet, review = self._review()
        skill = form._skills()[0]
        with self.assertRaises(UserError):
            self.F.with_user(self.staff_user).my_save(review.id, {skill.id: '7'})

    # ---------------------------------------------------------------- T3
    def test_03_at_most_eight_questions_and_skills(self):
        F = self.F.with_user(self.hr_user)
        nine = [{'name': 'DEMO q%s' % i, 'qtype': 'text'} for i in range(9)]
        with self.assertRaises(UserError):
            F.studio_save(self.cycle.id, {'questions': nine})
        with self.assertRaises(UserError):
            F.studio_save(self.cycle.id, {
                'skills': [{'name': 'DEMO s%s' % i} for i in range(9)]})
        payload = F.studio_save(self.cycle.id, {'questions': nine[:8]})
        self.assertEqual(len(payload['questions']), 8)

    def test_03_publish_refuses_a_form_with_problems(self):
        F = self.F.with_user(self.hr_user)
        F.studio_save(self.cycle.id, {
            'share_goals': 60, 'share_skills': 30, 'share_questions': 0,
            'skills': [{'name': 'DEMO s'}],
            'questions': [{'name': 'DEMO pick', 'qtype': 'choice',
                           'choices': 'only one'}],
            'reveal': 'date', 'reveal_date': False})
        form = self.Form.search([('cycle_id', '=', self.cycle.id)])
        problems = ' '.join(form._problems())
        self.assertIn('add up to 90', problems)
        self.assertIn('at least two answers', problems)
        self.assertIn('date', problems)
        with self.assertRaises(UserError):
            F.studio_publish(self.cycle.id)
        with self.assertRaises(ValidationError):
            form.sudo().write({'share_goals': 120})

    def test_03_only_the_hr_lead_writes_a_form(self):
        with self.assertRaises(AccessError):
            self.F.with_user(self.goals_admin).studio_save(self.cycle.id, {})
        with self.assertRaises(AccessError):
            self.F.with_user(self.boss_user).studio_save(self.cycle.id, {})
        self.assertFalse(self.F.with_user(self.boss_user).studio_load()['ok'])
        self.assertTrue(self.F.with_user(self.goals_admin).studio_load()['ok'])


# =========================================================================
#  T4 employee first, then the manager, then the overall comment
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestFlow(RFCase):

    def test_04_employee_send_needs_every_answer(self):
        form = self._form()
        _sheet, review = self._review()
        skill = form._skills()[0]
        F = self.F.with_user(self.staff_user)
        F.my_save(review.id, {skill.id: '4'})          # a draft is fine
        self.assertEqual(self._entry(review).self_state, 'draft')
        with self.assertRaises(UserError):
            F.my_save(review.id, {}, send=True)
        self._send_self(review, form)
        entry = self._entry(review)
        self.assertEqual(entry.self_state, 'sent')
        with self.assertRaises(UserError):
            F.my_save(review.id, {skill.id: '2'})

    def test_04_manager_waits_for_the_employee_or_says_so(self):
        form = self._form()
        _sheet, review = self._review()
        with self.assertRaises(UserError):
            self._finish(review, form)
        self._finish(review, form, without_self=True)
        entry = self._entry(review)
        self.assertEqual(entry.mgr_state, 'done')
        self.assertTrue(entry.mgr_without_self)

    def test_04_the_overall_comment_is_required_and_lands_on_the_review(self):
        form = self._form()
        _sheet, review = self._review()
        self._send_self(review, form)
        Mgr = self.F.with_user(self.boss_user)
        with self.assertRaises(UserError):
            Mgr.drawer_save(review.id, self._mgr_answers(form), '', True)
        with self.assertRaises(UserError):
            Mgr.drawer_save(review.id, {}, 'DEMO comment', True)
        self._finish(review, form)
        self.assertEqual(review.state, 'done')
        self.assertEqual(review.manager_note, 'DEMO a strong year overall.')
        self.assertTrue(review.score_at_review)
        # the manager reads the employee's view only once it was sent
        payload = Mgr.drawer_form(review.id)
        self.assertTrue(all(l['theirs'] for l in payload['skills']))

    def test_04_the_manager_does_not_see_a_draft_own_view(self):
        form = self._form()
        _sheet, review = self._review()
        skill = form._skills()[0]
        self.F.with_user(self.staff_user).my_save(review.id, {skill.id: '5'})
        payload = self.F.with_user(self.boss_user).drawer_form(review.id)
        self.assertFalse(any(l['theirs'] for l in payload['skills']))

    def test_04_the_goals_must_be_scored_first(self):
        form = self._form()
        _sheet, review = self._review(mark=None)
        self._send_self(review, form)
        with self.assertRaises(UserError):
            self._finish(review, form)

    def test_04_the_old_write_up_button_is_not_offered_on_a_form_review(self):
        self._form()
        sheet, review = self._review()
        rows = self.Board.with_user(self.boss_user).get_set(sheet.id)['reviews']
        row = [r for r in rows if r['id'] == review.id][0]
        self.assertIn('form', row)
        self.assertFalse(row['form']['is_self'])


# =========================================================================
#  T5 hide-until; T6 acknowledgement; T7 the PDF
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestShowing(RFCase):

    def _done(self, reveal='date', when=None):
        form = self._form(reveal=reveal, reveal_date=when)
        sheet, review = self._review()
        self._send_self(review, form)
        self._finish(review, form)
        return form, sheet, review

    def test_05_nothing_of_the_managers_part_before_the_date(self):
        later = fields.Date.today() + timedelta(days=20)
        form, sheet, review = self._done(when=later)
        Me = self.F.with_user(self.staff_user)
        payload = Me.my_form(review.id)
        self.assertFalse(payload['shown'])
        self.assertNotIn('result', payload)
        self.assertFalse(any('manager_words' in l for l in payload['skills']))
        self.assertNotIn('DEMO a strong year', json.dumps(payload))
        # the review row holds a neutral sentence until it is shown
        self.assertNotIn('strong year', review.manager_note)
        my = self.My.with_user(self.staff_user)
        rows = my._reviews(sheet, fields.Date.today())
        self.assertEqual([r['manager_note'] for r in rows if r['id'] == review.id], [''])
        self.assertFalse(my._scores(sheet)['shown'])
        drawer = self.Board.with_user(self.staff_user).get_set(sheet.id)
        self.assertFalse(drawer['scores']['scored'])
        self.assertTrue(all(not kr['score'] for g in drawer['scores']['goals']
                            for kr in g['krs']))
        self.assertTrue(self.F.with_user(self.staff_user).drawer_form(
            review.id)['is_self'])
        self.assertFalse(self._entry(review).document_id,
                         'nothing may be filed before it is shown')
        # the manager and HR do see it
        self.assertEqual(self.F.with_user(self.boss_user).drawer_form(
            review.id)['comment'], 'DEMO a strong year overall.')

    def test_05_the_day_comes(self):
        later = fields.Date.today() + timedelta(days=20)
        form, sheet, review = self._done(when=later)
        self.assertEqual(self.Entry._cron_release_due(), 0)
        form.sudo().write({'reveal_date': fields.Date.today()})
        self.assertEqual(self.Entry._cron_release_due(), 1)
        payload = self.F.with_user(self.staff_user).my_form(review.id)
        self.assertTrue(payload['shown'])
        self.assertEqual(payload['result']['comment'], 'DEMO a strong year overall.')
        self.assertEqual(review.manager_note, 'DEMO a strong year overall.')
        self.assertTrue(self.My.with_user(self.staff_user)._scores(sheet)['shown'])

    def test_05_show_now_and_close_both_share(self):
        later = fields.Date.today() + timedelta(days=20)
        _form, _sheet, review = self._done(when=later)
        self.F.with_user(self.hr_user).studio_show_now(self.cycle.id)
        self.assertTrue(self._entry(review).released_at)

    def test_05_closing_the_year_shares_finished_reviews(self):
        later = fields.Date.today() + timedelta(days=20)
        _form, _sheet, review = self._done(when=later)
        self.Cycle.close_cycle(self.cycle.id, with_gaps=True)
        self.assertTrue(self._entry(review).released_at)

    def test_05_straight_away_when_the_form_says_so(self):
        _form, _sheet, review = self._done(reveal='manager_done')
        self.assertTrue(self.F.with_user(self.staff_user).my_form(review.id)['shown'])

    def test_05_an_hr_lead_never_sees_their_own_review_early(self):
        later = fields.Date.today() + timedelta(days=20)
        self.staff_user.write({'group_ids': [(4, self.env.ref(
            'pb_goals.group_goals_manager').id)]})
        _form, _sheet, review = self._done(when=later)
        self.assertTrue(self.F.with_user(self.staff_user).drawer_form(
            review.id)['is_self'])
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertFalse(self.Entry.with_user(self.staff_user).search(
            [('review_id', '=', review.id)]))
        self.assertFalse(self.env['pb.review.answer'].with_user(
            self.staff_user).search([('entry_id.review_id', '=', review.id)]))

    # ---------------------------------------------------------------- T6
    def test_06_read_and_talk(self):
        later = fields.Date.today() + timedelta(days=20)
        form, _sheet, review = self._done(when=later)
        Me = self.F.with_user(self.staff_user)
        with self.assertRaises(UserError):
            Me.my_ack(review.id, 'read')
        form.sudo().write({'reveal_date': fields.Date.today()})
        Me.my_form(review.id)
        Me.my_ack(review.id, 'read')
        entry = self._entry(review)
        self.assertEqual(entry.ack_state, 'read')
        self.assertTrue(entry.ack_at)
        answer = Me.my_ack(review.id, 'talk')
        self.assertEqual(entry.ack_state, 'talk')
        if 'pb.ask.hr.ticket' in self.env:
            ticket = self.env['pb.ask.hr.ticket'].sudo().browse(answer['ticket_id'])
            self.assertEqual(ticket.employee_id, self.staff)
            self.assertNotIn('strong year', (ticket.description or '') + ticket.name)
        with self.assertRaises(AccessError):
            self.F.with_user(self.stranger_user).my_ack(review.id, 'read')

    # ---------------------------------------------------------------- T7
    def test_07_the_pdf_is_filed_in_their_documents(self):
        _form, _sheet, review = self._done(reveal='manager_done')
        entry = self._entry(review)
        doc = entry.document_id
        self.assertTrue(doc)
        self.assertEqual(doc.employee_id, self.staff)
        self.assertEqual(doc.category_id, self.env.ref(
            'pb_review_forms.cat_performance_review'))
        self.assertTrue(doc.attachment_id.raw)
        self.assertIn(b'DEMO a strong year', entry.attachment_id.raw)
        self.assertEqual(self.F.with_user(self.staff_user).my_pdf(review.id),
                         entry.attachment_id)
        with self.assertRaises(AccessError):
            self.F.with_user(self.stranger_user).my_pdf(review.id)


# =========================================================================
#  T8 locked after the first review is sent; T9 HR preview
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestLockAndPreview(RFCase):

    def test_08_the_first_sent_review_locks_the_form(self):
        form = self._form()
        _sheet, review = self._review()
        self.assertFalse(form.locked_at)
        self._send_self(review, form)
        self.assertTrue(form.locked_at)
        F = self.F.with_user(self.hr_user)
        with self.assertRaises(UserError):
            form.with_user(self.hr_user)._skills()[0].write({'name': 'DEMO x'})
        with self.assertRaises(UserError):
            form.with_user(self.hr_user).write({'share_goals': 50,
                                                 'share_skills': 50})
        with self.assertRaises(UserError):
            F.studio_unpublish(self.cycle.id)
        # a locked form still takes WHEN it is shown, and nothing else
        payload = F.studio_save(self.cycle.id, {
            'reveal': 'date', 'reveal_date': '2030-01-01',
            'share_goals': 10, 'skills': []})
        self.assertEqual(payload['reveal_date'], '2030-01-01')
        self.assertEqual(payload['share_goals'], 70)
        self.assertEqual(len(payload['skills']), 2)

    def test_08_copy_makes_next_years_version(self):
        form = self._form()
        nxt = self.Cycle.create({
            'name': 'DEMO FY2027', 'company_id': self.company.id,
            'date_start': self.cycle.date_end + timedelta(days=1),
            'date_end': self.cycle.date_end + timedelta(days=366)})
        res = self.F.with_user(self.hr_user).studio_copy(self.cycle.id, nxt.id)
        copy = self.Form.search([('cycle_id', '=', nxt.id)])
        self.assertEqual(res['cycle_id'], nxt.id)
        self.assertEqual(copy.state, 'draft')
        self.assertEqual(len(copy.line_ids), len(form.line_ids))

    def test_09_hr_previews_as_the_employee_and_nothing_is_saved(self):
        form = self._form()
        before = self.Entry.sudo().search_count([])
        payload = self.F.with_user(self.goals_admin).preview(form.id)
        self.assertTrue(payload['preview'])
        self.assertTrue(payload['may_edit'])
        self.assertEqual(len(payload['skills']), 2)
        self.assertEqual(self.Entry.sudo().search_count([]), before)
        with self.assertRaises(AccessError):
            self.F.with_user(self.staff_user).preview(form.id)


# =========================================================================
#  T10 P2 — the overall result into pay; T11 golden: no form, as today
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestPay(RFCase):

    def test_10_the_overall_result_by_the_shares(self):
        form = self._form()                      # 70 goals / 30 skills
        sheet, review = self._review(mark='4')   # goals 4.0
        self.assertIsNone(sheet._pay_score(), 'unfinished: no score, never 1')
        self._send_self(review, form)
        self._finish(review, form)               # skills '3','4' → 3.5
        entry = self._entry(review)
        self.assertAlmostEqual(entry._overall(), round(0.7 * 4 + 0.3 * 3.5, 2))
        self.assertAlmostEqual(sheet._pay_score(), 3.85)
        self.assertEqual(sheet._pay_rating_for(sheet._pay_score(), 4), 3)

    def test_10_rated_questions_count_when_they_have_a_share(self):
        form = self._form(shares=(50, 25, 25), questions=[
            {'name': 'DEMO rate it', 'qtype': 'rating', 'who': 'manager',
             'required': True}])
        sheet, review = self._review(mark='2')
        self._send_self(review, form)
        self._finish(review, form)
        # 0.5*2 + 0.25*3.5 + 0.25*4
        self.assertAlmostEqual(sheet._pay_score(), 2.88)

    def test_10_closing_freezes_the_overall_and_stamps_it(self):
        form = self._form()
        sheet, review = self._review(mark='4')
        self._send_self(review, form)
        self._finish(review, form)
        self.Cycle.close_cycle(self.cycle.id, with_gaps=True)
        frozen = sheet.frozen()
        self.assertEqual(frozen['review_basis'], 'form')
        self.assertAlmostEqual(frozen['review_overall'], 3.85)
        self.assertEqual(frozen['score'], 4.0, 'the goals score is kept as it was')
        self.assertAlmostEqual(sheet._pay_score(), 3.85)
        if 'pb_performance_rating' in self.env['hr.employee']._fields:
            self.staff.invalidate_recordset()
            self.assertEqual(self.staff.sudo().pb_performance_rating, '4')

    def test_10_a_review_written_up_before_the_form_stays_on_goals(self):
        sheet, review = self._review(mark='4')
        review.with_user(self.boss_user).action_review_done('DEMO old way')
        self._form()
        self.assertFalse(review._rf_applies())
        self.assertEqual(sheet._pay_score(), BASE_PAY_SCORE(sheet))

    # ---------------------------------------------------------------- T11
    def test_11_golden_no_form_pay_score(self):
        scored, _r = self._review(mark='3')
        unscored = self._agreed(self.stranger)
        for sheet in (scored, unscored):
            self.assertEqual(sheet._pay_score(), BASE_PAY_SCORE(sheet))
        self.Cycle.close_cycle(self.cycle.id, with_gaps=True)
        for sheet in (scored, unscored):
            self.assertEqual(sheet._pay_score(), BASE_PAY_SCORE(sheet))
        self.assertNotIn('review_basis', scored.frozen())

    def test_11_golden_no_form_screens(self):
        sheet, _review = self._review(mark='4')
        today = fields.Date.today()
        for user in (self.staff_user, self.boss_user):
            My = self.My.with_user(user)
            Board = self.Board.with_user(user)
            self.assertEqual(My._reviews(sheet, today),
                             PbMyGoalsYear._reviews(My, sheet, today))
            self.assertEqual(My._scores(sheet), PbMyGoalsYear._scores(My, sheet))
            self.assertEqual(Board._review_rows(sheet, today),
                             PbGoalsYear._review_rows(Board, sheet, today))
            self.assertEqual(Board._score_rows(sheet),
                             PbGoalsYear._score_rows(Board, sheet))
            self.assertEqual(Board._year_scores(self.cycle.id),
                             PbGoalsYear._year_scores(Board, self.cycle.id))


try:
    from odoo.addons.pb_pay.tests import test_pay_review as pay_base
except ImportError:                     # pb_pay is not a dependency
    pay_base = None


if pay_base is not None:
    @tagged('post_install', '-at_install', 'wdgap_s9a')
    class TestPayReviewGolden(pay_base.TestPayReview):
        """T11 — the pay review's "Read scores from Goals", no form vs today."""

        def _sheet(self, cycle, employee, mark):
            sheet = self.env['pb.goal.set'].create({
                'employee_id': employee.id, 'cycle_id': cycle.id,
                'company_id': self.company.id, 'deadline': cycle.date_end})
            goal = self.env['pb.goal'].create({
                'set_id': sheet.id, 'title': 'DEMO S9A goal',
                'description': 'DEMO', 'date_start': cycle.date_start,
                'date_end': cycle.date_end, 'weight': 100.0})
            kr = self.env['pb.goal.kr'].create({
                'goal_id': goal.id, 'title': 'DEMO result',
                'measure': 'things', 'target': 10.0})
            if mark:
                kr.sudo().write({'score': mark})
            sheet.invalidate_recordset()
            return sheet

        def test_11_golden_pay_review_reading(self):
            today = fields.Date.context_today(self.env.user)
            Cycle = self.env['pb.goal.cycle']
            closed = Cycle.create({'name': 'DEMO S9A closed',
                                   'company_id': self.company.id,
                                   'date_start': today - timedelta(days=400),
                                   'date_end': today - timedelta(days=30)})
            closed.sudo().write({'state': 'closed'})
            opened = Cycle.create({'name': 'DEMO S9A open',
                                   'company_id': self.company.id,
                                   'date_start': today - timedelta(days=100),
                                   'date_end': today + timedelta(days=200)})
            opened.sudo().write({'state': 'open'})
            for cycle in (closed, opened):
                self._sheet(cycle, self.alice, '4')
                self._sheet(cycle, self.bob, None)
            review = self._review()
            Rating = self.env['pb.pay.rating']
            # a draft form changes nothing either
            self.env['pb.review.form'].create({'cycle_id': opened.id})
            for cycle in (closed, opened):
                now = Rating.read_from_goals(review.id, cycle.id, True)
                with patch.object(type(self.env['pb.goal.set']), '_pay_score',
                                  BASE_PAY_SCORE):
                    before = Rating.read_from_goals(review.id, cycle.id, True)
                self.assertEqual(json.dumps(now, sort_keys=True, default=str),
                                 json.dumps(before, sort_keys=True, default=str))
                self.assertEqual(now['read'], 1)


# =========================================================================
#  T12 portal rights, as a real portal login
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestPortal(RFCase, HttpCase):
    """RFCase's world with a browser session (RFCase and its bases define no
    tests, so nothing is run twice)."""

    def _csrf(self, url):
        import re
        page = self.url_open(url)
        found = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        return found.group(1) if found else ''

    def test_12_the_portal_worker_fills_in_their_own_and_nobody_elses(self):
        form = self._form()
        _sheet, review = self._review(employee=self.worker)
        _other_sheet, other = self._review(employee=self.staff)
        self.authenticate('demo.rf.portal@example.com', _PW)
        page = self.url_open('/my/goals/review/%s' % review.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Send to my manager', page.text)
        self.assertIn('DEMO Ownership', page.text)
        # somebody else's review answers as if it did not exist
        stranger = self.url_open('/my/goals/review/%s' % other.id,
                                 allow_redirects=False)
        self.assertIn(stranger.status_code, (301, 302, 303))
        self.assertNotIn('DEMO Ownership', stranger.text)
        # sending through the page itself
        data = {'a_%s' % k: v for k, v in self._self_answers(form).items()}
        data.update({'do': 'send',
                     'csrf_token': self._csrf('/my/goals/review/%s' % review.id)})
        token = data['csrf_token']
        sent = self.url_open('/my/goals/review/%s/save' % review.id, data=data,
                             allow_redirects=False)
        self.assertIn(sent.status_code, (301, 302, 303))
        self.assertIn('ok=sent', sent.headers.get('Location', ''))
        self.env.invalidate_all()
        self.assertEqual(self._entry(review).self_state, 'sent')
        # a crafted post on somebody else's review changes nothing
        data['csrf_token'] = token
        self.url_open('/my/goals/review/%s/save' % other.id, data=data,
                      allow_redirects=False)
        self.env.invalidate_all()
        self.assertFalse(self._entry(other))
        # no right of its own on the answers, through the ORM
        self.env.invalidate_all()
        for model in ('pb.review.entry', 'pb.review.answer', 'pb.review.form'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.portal_user).search([])
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.staff_user).search([])
        # the PDF is not theirs before it is shown, and never somebody else's
        pdf = self.url_open('/my/goals/review/%s/pdf' % other.id,
                            allow_redirects=False)
        self.assertIn(pdf.status_code, (301, 302, 303))

    def test_12_shown_page_and_preview_render(self):
        form = self._form()
        _sheet, review = self._review(employee=self.worker)
        self.F.with_user(self.portal_user).my_save(
            review.id, self._self_answers(form), send=True)
        self._finish(review, form)
        self.authenticate('demo.rf.portal@example.com', _PW)
        page = self.url_open('/my/goals/review/%s' % review.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('I have read this', page.text)
        self.assertIn('DEMO a strong year overall.', page.text)
        goals = self.url_open('/my/goals')
        self.assertEqual(goals.status_code, 200)
        self.assertIn('Your review form', goals.text)
        # the home entry and its stable door
        home = self.url_open('/my')
        self.assertEqual(home.status_code, 200)
        self.assertIn('/my/review', home.text)
        door = self.url_open('/my/review', allow_redirects=False)
        self.assertIn('/my/goals/review/%s' % review.id,
                      door.headers.get('Location', ''))
        # a portal login cannot open HR's preview
        prev = self.url_open('/my/goals/review-form/%s/preview' % form.id,
                             allow_redirects=False)
        self.assertIn(prev.status_code, (301, 302, 303))
        self.hr_user.sudo().write({'password': _PW})
        self.authenticate('demo.rf.hr@example.com', _PW)
        prev = self.url_open('/my/goals/review-form/%s/preview' % form.id)
        self.assertEqual(prev.status_code, 200)
        self.assertIn('Nothing you choose here is saved', prev.text)


# =========================================================================
#  T13 silent install; T14 Needs you; T16 who may open the drawer form
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestQuiet(RFCase):

    def test_13_nothing_happens_without_a_form(self):
        sheet, review = self._review()
        self.assertEqual(self.F.with_user(self.staff_user).my_current_review(), 0)
        self.assertFalse(self.Form.search_count([('cycle_id', '=', self.cycle.id)]))
        self.My.with_user(self.staff_user).home()
        self.Board.with_user(self.boss_user).get_set(sheet.id)
        self.assertFalse(self._entry(review), 'reading pages made a row')
        self.assertEqual(self.Entry._cron_release_due(), 0)
        self.assertEqual(self.F.needs_rows(self.staff), [])
        cron = self.env.ref('pb_review_forms.cron_review_release_due')
        self.assertIn('_cron_release_due', cron.code)

    def test_13_the_job_sends_no_mail(self):
        later = fields.Date.today() + timedelta(days=5)
        form = self._form(reveal='date', reveal_date=later)
        _sheet, review = self._review()
        self.F.with_user(self.staff_user).my_save(
            review.id, self._self_answers(form), send=True)
        self._finish(review, form)
        form.sudo().write({'reveal_date': fields.Date.today()})
        mails = self.env['mail.mail'].sudo().search_count([])
        self.Entry._cron_release_due()
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mails)

    def test_14_needs_you_rows(self):
        form = self._form()
        _sheet, review = self._review()
        rows = self.F.needs_rows(self.staff)
        self.assertEqual([r[0] for r in rows], ['review_self'])
        self._send_self(review, form)
        self.assertEqual(self.F.needs_rows(self.staff), [])
        self._finish(review, form)
        self.assertEqual([r[0] for r in self.F.needs_rows(self.staff)],
                         ['review_read'])
        found = {}
        self.env['pb.me.home'].with_user(self.staff_user)._pbme_needs_extra(
            self.staff, lambda key, n, url, **kw: found.setdefault(key, url))
        self.assertEqual(found.get('review_read'),
                         '/my/goals/review/%s' % review.id)

    def test_16_only_the_manager_or_hr_opens_the_drawer_form(self):
        form = self._form()
        _sheet, review = self._review()
        with self.assertRaises(AccessError):
            self.F.with_user(self.stranger_user).drawer_form(review.id)
        with self.assertRaises(AccessError):
            self.F.with_user(self.stranger_user).drawer_save(review.id, {}, 'x')
        payload = self.F.with_user(self.goals_admin).drawer_form(review.id)
        self.assertFalse(payload['may_edit'])
        with self.assertRaises(AccessError):
            self.F.with_user(self.goals_admin).drawer_save(review.id, {}, 'x')
        self.assertTrue(self.F.with_user(self.hr_user).drawer_form(review.id)['may_edit'])
        with self.assertRaises(AccessError):
            self.F.with_user(self.staff_user).drawer_save(
                review.id, self._mgr_answers(form), 'DEMO', True)


# =========================================================================
#  T21 RV1 — a finished review is for the person, the manager and HR only
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestRV1Privacy(RFCase):
    """Every persona the owner named, read through the ORM as that login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def user(login, groups):
            refs = [cls.env.ref(x, raise_if_not_found=False) for x in groups]
            return Users.create({
                'name': 'DEMO %s' % login, 'login': 'demo.rv1.%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [r.id for r in refs if r])],
            })
        cls.payroll_officer = user('po', ['om_hr_payroll.group_hr_payroll_user'])
        cls.payroll_manager = user('pm', ['om_hr_payroll.group_hr_payroll_manager'])
        cls.hr_officer = user('hro', ['hr.group_hr_user'])
        cls.lifecycle_user = user('lc', ['pb_lifecycle.group_lifecycle_user',
                                         'base.group_user'])
        cls.other_manager = user('om', ['base.group_user'])
        cls.env['hr.employee'].create({
            'name': 'DEMO Other Manager', 'company_id': cls.company.id,
            'user_id': cls.other_manager.id})
        cls.env['hr.employee'].create({
            'name': 'DEMO Other Report', 'company_id': cls.company.id,
            'parent_id': cls.env['hr.employee'].search(
                [('user_id', '=', cls.other_manager.id)], limit=1).id})
        # HR who run reviews AND hold the HR officer right the documents need.
        cls.hr_user.write({'group_ids': [(4, cls.env.ref('hr.group_hr_user').id)]})

    def _finished(self):
        form = self._form()
        sheet, review = self._review()
        self._send_self(review, form)
        self._finish(review, form)
        entry = self._entry(review)
        self.assertTrue(entry.document_id, 'the review was not filed')
        self.assertTrue(entry.document_id.pb_rf_private)
        return sheet, review, entry

    def _reads(self, user, record, fname):
        self.env.flush_all()
        self.env.invalidate_all()
        try:
            with self.env.cr.savepoint():
                rec = record.with_user(user).with_context(
                    allowed_company_ids=[self.company.id])
                rec.check_access('read')
                rec.read([fname])
            return True
        except AccessError:
            return False

    def test_21_who_reads_a_finished_review(self):
        sheet, review, entry = self._finished()
        doc = entry.document_id
        doc_file = doc.attachment_id
        entry_file = entry.attachment_id
        answer = entry.answer_ids[:1]
        nobody = {
            'payroll officer': self.payroll_officer,
            'payroll manager': self.payroll_manager,
            'HR officer without Goals HR rights': self.hr_officer,
            'general lifecycle user': self.lifecycle_user,
            'another employee': self.stranger_user,
            'an unrelated manager': self.other_manager,
        }
        for word, user in nobody.items():
            self.assertFalse(self._reads(user, doc, 'name'), word + ': document')
            self.assertFalse(self._reads(user, doc_file, 'datas'), word + ': PDF file')
            self.assertFalse(self._reads(user, entry_file, 'datas'),
                             word + ': PDF on the review')
            self.assertFalse(self._reads(user, entry, 'overall_comment'),
                             word + ': review')
            self.assertFalse(self._reads(user, answer, 'text'), word + ': answers')
            self.assertFalse(self._reads(user, review, 'manager_note'),
                             word + ': comment on the review row')
            with self.assertRaises(AccessError):
                self.F.with_user(user).drawer_form(review.id)
            with self.assertRaises(AccessError):
                self.F.with_user(user).my_form(review.id)
        # the person: their own document, file and review row, through the
        # vault and their own page (never the answers model itself)
        self.assertTrue(self._reads(self.staff_user, doc, 'name'))
        self.assertTrue(self._reads(self.staff_user, doc_file, 'datas'))
        self.assertTrue(self._reads(self.staff_user, review, 'manager_note'))
        self.assertFalse(self._reads(self.staff_user, entry, 'overall_comment'))
        self.assertTrue(self.F.with_user(self.staff_user).my_form(review.id)['shown'])
        # the manager: the review row and the drawer form
        self.assertTrue(self._reads(self.boss_user, review, 'manager_note'))
        self.assertEqual(self.F.with_user(self.boss_user).drawer_form(
            review.id)['comment'], 'DEMO a strong year overall.')
        # HR who run reviews: everything
        for record, fname in ((doc, 'name'), (doc_file, 'datas'),
                              (entry, 'overall_comment'), (answer, 'text'),
                              (review, 'manager_note')):
            self.assertTrue(self._reads(self.hr_user, record, fname), record._name)

    def test_21_payroll_keeps_the_number(self):
        sheet, _review, _entry = self._finished()
        for user in (self.payroll_officer, self.payroll_manager):
            value = self.env['pb.goal.set'].with_user(user).browse(
                sheet.id)._pay_score()
            self.assertAlmostEqual(value, 3.85)

    def test_21_other_documents_are_untouched(self):
        self._finished()
        Doc = self.env['pb.employee.document']
        att = self.env['ir.attachment'].create({
            'name': 'DEMO contract.pdf', 'raw': b'DEMO'})
        plain = Doc.sudo().create({
            'employee_id': self.staff.id, 'name': 'DEMO contract',
            'category_id': self.env.ref('pb_employee_vault.cat_other').id,
            'attachment_id': att.id, 'company_id': self.company.id})
        att.write({'res_model': 'pb.employee.document', 'res_id': plain.id})
        self.assertTrue(self._reads(self.payroll_officer, plain, 'name'))

    def test_21_nobody_flips_the_flag(self):
        _sheet, _review, entry = self._finished()
        doc = entry.document_id
        with self.assertRaises(AccessError):
            doc.with_user(self.hr_user).write({'pb_rf_private': False})
        att = self.env['ir.attachment'].create({'name': 'DEMO x', 'raw': b'x'})
        other = self.env['pb.employee.document'].with_user(self.payroll_manager).create({
            'employee_id': self.stranger.id, 'name': 'DEMO x',
            'category_id': self.env.ref('pb_employee_vault.cat_other').id,
            'attachment_id': att.id, 'company_id': self.company.id,
            'pb_rf_private': True})
        self.assertFalse(other.sudo().pb_rf_private)


# =========================================================================
#  T17 static gates: translations and white-label
# =========================================================================
@tagged('post_install', '-at_install', 'wdgap_s9a')
class TestStatic(RFCase):

    def _module(self, *parts):
        from odoo.modules.module import get_module_path
        return '/'.join([get_module_path('pb_review_forms')] + list(parts))

    def test_17_every_word_has_vi_and_id(self):
        import re as _re
        from odoo.tools.translate import PoFileReader
        with open(self._module('i18n', 'pb_review_forms.pot'), 'rb') as fh:
            wanted = {row['src'] for row in PoFileReader(fh)}
        self.assertGreater(len(wanted), 150)
        for lang in ('vi_VN', 'id_ID'):
            with open(self._module('i18n', lang + '.po'), 'rb') as fh:
                rows = list(PoFileReader(fh))
            done = {row['src'] for row in rows if row['value']}
            self.assertEqual(wanted - done, set(), lang)
            for row in rows:
                self.assertFalse(_re.search(r'\bodoo\b', row['value'], _re.I),
                                 row['src'])

    def test_17_no_vendor_name_in_what_people_see(self):
        import glob
        import re as _re
        files = (glob.glob(self._module('views', '*.xml'))
                 + glob.glob(self._module('report', '*.xml'))
                 + glob.glob(self._module('static', 'src', 'xml', '*.xml')))
        self.assertTrue(files)
        for path in files:
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            text = _re.sub(r'<!--.*?-->', '', text, flags=_re.S)
            text = text.replace('<odoo>', '').replace('</odoo>', '')
            self.assertFalse(_re.search(r'\bodoo\b', text, _re.I), path)
        with open(self._module('static', 'src', 'js',
                               'review_forms_studio.js'), encoding='utf-8') as fh:
            js = fh.read()
        for found in _re.findall(r'_t\("([^"]*)"', js):
            self.assertNotIn('odoo', found.lower())
