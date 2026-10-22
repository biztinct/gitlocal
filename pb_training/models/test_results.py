# -*- coding: utf-8 -*-
"""LEARNING L5 — Learning › TESTS: the list, the results drawer, the New test
drawer and "ask N of M" random question pools.

Reads, behind the board's gate (`{'allowed': False}` without a training
group):

  * `tests_board()`        every test (a certification survey): course, pass
                           mark, goes allowed, how questions are drawn,
                           people, pass rate;
  * `test_results(id)`     the hero: pass rate, a score histogram (ten
                           buckets that add up to the attempts), the hardest
                           questions — wrong ÷ ASKED, where asked means the
                           question was drawn for that attempt
                           (`predefined_question_ids`), so a question in a
                           pool of 30 is not punished for the 20 attempts
                           that never saw it — and the retake and pool words.

Writes (through `act`): `create_test` (the drawer — a test with one section
drawing N questions when asked), `set_pool` ("Questions drawn per attempt").

The stock results page `/survey/results/<id>` is gated in
`controllers/slides_gate.py` for tests (certifications and course tests).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .training_common import as_id, fold

_logger = logging.getLogger(__name__)

HARDEST = 10


class PbTrainingTests(models.AbstractModel):
    _inherit = 'pb.training'

    # =====================================================================
    #  helpers
    # =====================================================================
    @api.model
    def _test_surveys(self):
        return self.env['survey.survey'].sudo().search(
            [('certification', '=', True)], order='title, id')

    @api.model
    def _test_courses(self, surveys):
        """{survey_id: (channel_id, channel_name)} — the course a test ends."""
        out = {}
        slides = self.env['slide.slide'].sudo().search([
            ('survey_id', 'in', surveys.ids),
            ('slide_category', '=', 'certification')])
        for slide in slides:
            if slide.survey_id.id not in out and slide.channel_id:
                out[slide.survey_id.id] = (slide.channel_id.id,
                                           slide.channel_id.name or '')
        return out

    @api.model
    def _attempts_of(self, survey):
        return self.env['survey.user_input'].sudo().search([
            ('survey_id', '=', survey.id), ('state', '=', 'done'),
            ('test_entry', '=', False)])

    @api.model
    def _pool(self, survey):
        """(drawn, total) — (0, total) when every question is asked."""
        total = survey.question_count or 0
        if survey.questions_selection != 'random':
            return 0, total
        drawn = 0
        loose = len(survey.question_ids.filtered(lambda q: not q.page_id))
        for page in survey.page_ids:
            count = len(page.question_ids)
            n = page.random_questions_count
            drawn += n if 0 < n < count else count
        return drawn + loose, total

    @api.model
    def _pool_words(self, survey):
        drawn, total = self._pool(survey)
        if not drawn or drawn >= total:
            if total == 1:
                return _("Asks its 1 question")
            return _("Asks all %s questions", total)
        return _("Each attempt draws %(n)s of %(m)s questions", n=drawn,
                 m=total)

    @api.model
    def _retake_words(self, survey):
        if not survey.is_attempts_limited:
            return _("As many goes as they like")
        n = survey.attempts_limit or 0
        return _("1 go") if n == 1 else _("%s goes", n)

    # =====================================================================
    #  the list
    # =====================================================================
    @api.model
    def tests_board(self, term=''):
        if not self._can_read():
            return {'allowed': False, 'tests': []}
        surveys = self._test_surveys()
        courses = self._test_courses(surveys)
        needle = fold(term or '')
        rows = []
        for survey in surveys:
            if needle and needle not in fold(survey.title) and needle not in \
                    fold(courses.get(survey.id, (0, ''))[1]):
                continue
            attempts = self._attempts_of(survey)
            people = attempts.mapped('partner_id')
            passers = attempts.filtered('scoring_success').mapped('partner_id')
            rows.append({
                'id': survey.id,
                'name': survey.title or '',
                'course': courses.get(survey.id, (0, ''))[1],
                'course_id': courses.get(survey.id, (0, ''))[0],
                'pass_mark': int(round(survey.scoring_success_min or 0)),
                'retake_words': self._retake_words(survey),
                'pool_words': self._pool_words(survey),
                'random': survey.questions_selection == 'random',
                'questions': survey.question_count or 0,
                'attempts': len(attempts),
                'people': len(people),
                'pass_rate': int(round(100.0 * len(passers) / len(people)))
                if people else None,
                'active': bool(survey.active),
            })
        with_people = [r for r in rows if r['people']]
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'tests': rows,
            'headline': self._tests_headline(len(rows), with_people),
        }

    @api.model
    def _tests_headline(self, count, with_people):
        if not count:
            return _("No tests yet.")
        first = _("1 test") if count == 1 else _("%s tests", count)
        if not with_people:
            return _("%s · nobody has taken one yet", first)
        people = sum(r['people'] for r in with_people)
        passed = sum(round(r['people'] * (r['pass_rate'] or 0) / 100.0)
                     for r in with_people)
        rate = int(round(100.0 * passed / people)) if people else 0
        return _("%(tests)s · %(people)s people took one · %(rate)s%% passed",
                 tests=first, people=people, rate=rate)

    # =====================================================================
    #  the results drawer
    # =====================================================================
    @api.model
    def test_results(self, survey_id):
        self._require_read()
        survey = self.env['survey.survey'].sudo().browse(
            as_id(survey_id)).exists()
        if not survey:
            raise UserError(_("That test is not here any more."))
        attempts = self._attempts_of(survey)
        people = attempts.mapped('partner_id')
        passers = attempts.filtered('scoring_success').mapped('partner_id')
        # Ten buckets, 0–9 … 90–100; every attempt in exactly one.
        buckets = [{'bucket': '%s-%s' % (i * 10, i * 10 + 9 if i < 9 else 100),
                    'n': 0} for i in range(10)]
        for att in attempts:
            pct = max(0.0, min(100.0, att.scoring_percentage or 0.0))
            buckets[min(int(pct // 10), 9)]['n'] += 1
        hardest = self._hardest(survey, attempts)
        drawn, total = self._pool(survey)
        courses = self._test_courses(survey)
        return {
            'id': survey.id,
            'name': survey.title or '',
            'course': courses.get(survey.id, (0, ''))[1],
            'pass_mark': int(round(survey.scoring_success_min or 0)),
            'attempts': len(attempts),
            'people': len(people),
            'passed': len(passers),
            'pass_rate': int(round(100.0 * len(passers) / len(people)))
            if people else None,
            'avg': int(round(sum(attempts.mapped('scoring_percentage'))
                             / len(attempts))) if attempts else None,
            'histogram': buckets,
            'hardest': hardest,
            'retake_words': self._retake_words(survey),
            'pool_words': self._pool_words(survey),
            'drawn': drawn,
            'questions': total,
            'random': survey.questions_selection == 'random',
            'sections': len(survey.page_ids),
            'can_write': self._can_write(),
        }

    @api.model
    def _hardest(self, survey, attempts):
        """Wrong ÷ asked, per question. A multi-choice question has one line
        per ticked answer: it is counted ONCE per attempt — wrong when any
        ticked answer is wrong or the question was skipped."""
        if not attempts:
            return []
        asked, wrong = {}, {}
        lines = self.env['survey.user_input.line'].sudo().search([
            ('user_input_id', 'in', attempts.ids)])
        by_attempt = {}
        for line in lines:
            if not line.question_id or line.question_id.is_page:
                continue
            by_attempt.setdefault(line.user_input_id.id, {}).setdefault(
                line.question_id.id, []).append(line)
        scored = survey.question_ids.filtered(
            lambda q: q.question_type in ('simple_choice', 'multiple_choice')
            and q.suggested_answer_ids.filtered('is_correct'))
        scored_ids = set(scored.ids)
        for att in attempts:
            drawn = set(att.predefined_question_ids.ids) & scored_ids \
                if att.predefined_question_ids else (
                    set(by_attempt.get(att.id, {}).keys()) & scored_ids)
            answered = by_attempt.get(att.id, {})
            for qid in drawn:
                asked[qid] = asked.get(qid, 0) + 1
                rows = answered.get(qid) or []
                ok = bool(rows) and not any(r.skipped for r in rows) and all(
                    r.answer_is_correct for r in rows)
                if not ok:
                    wrong[qid] = wrong.get(qid, 0) + 1
        out = []
        for question in scored:
            n = asked.get(question.id, 0)
            if not n:
                continue
            w = wrong.get(question.id, 0)
            out.append({'question': question.title or '',
                        'question_id': question.id,
                        'asked': n, 'wrong': w,
                        'pct': int(round(100.0 * w / n))})
        out.sort(key=lambda r: (-r['pct'], -r['asked'], r['question']))
        return out[:HARDEST]

    # =====================================================================
    #  the New test drawer and the pool
    # =====================================================================
    @api.model
    def create_test(self, payload=None):
        """A scored certification with the product's defaults; when "draw
        N per attempt" is asked, ONE section drawing N
        (`random_questions_count`) and `questions_selection='random'`."""
        self._require_write()
        payload = payload or {}
        name = (payload.get('name') or '').strip()[:200]
        if not name:
            raise UserError(_("Give the test a name."))
        try:
            mark = int(payload.get('pass_mark') or 70)
            goes = int(payload.get('attempts') or 0)
            draw = int(payload.get('draw') or 0)
        except (TypeError, ValueError):
            raise UserError(_("The pass mark, the goes and the questions "
                              "drawn are numbers."))
        if not 1 <= mark <= 100:
            raise UserError(_("The pass mark is between 1 and 100."))
        if goes < 0 or draw < 0:
            raise UserError(_("Goes and questions drawn cannot be below "
                              "zero."))
        vals = {
            'title': name,
            'survey_type': 'assessment',
            'certification': True,
            'scoring_type': 'scoring_with_answers',
            'scoring_success_min': mark,
            'users_login_required': True,
            'access_mode': 'token',
            'is_attempts_limited': bool(goes),
            'attempts_limit': goes or 1,
            'questions_layout': 'page_per_question',
            'questions_selection': 'random' if draw else 'all',
        }
        survey = self.env['survey.survey'].create(vals)
        if draw:
            self.env['survey.question'].create({
                'survey_id': survey.id,
                'title': _("Questions"),
                'is_page': True,
                'sequence': 1,
                'random_questions_count': draw,
            })
        return {
            'id': survey.id,
            'message': _("%(name)s is made. Add the questions in the test "
                         "editor%(pool)s.", name=name,
                         pool=(_(" — put them under the section, and each "
                                 "attempt draws %s of them", draw)
                               if draw else '')),
            'action': self.open_test(survey.id),
        }

    @api.model
    def set_pool(self, survey_id, draw):
        """"Questions drawn per attempt": 0 = every question."""
        self._require_write()
        survey = self.env['survey.survey'].browse(as_id(survey_id)).exists()
        if not survey:
            raise UserError(_("That test is not here any more."))
        try:
            draw = int(draw or 0)
        except (TypeError, ValueError):
            raise UserError(_("Say how many questions, as a number."))
        if draw < 0:
            raise UserError(_("That cannot be below zero."))
        if not draw:
            survey.write({'questions_selection': 'all'})
            return {'message': _("Every attempt now asks every question.")}
        if len(survey.page_ids) > 1:
            raise UserError(_(
                "This test has more than one section. Set how many questions "
                "each section draws in the test editor."))
        page = survey.page_ids[:1]
        if not page:
            first = min(survey.question_and_page_ids.mapped('sequence') or [10])
            page = self.env['survey.question'].create({
                'survey_id': survey.id, 'title': _("Questions"),
                'is_page': True, 'sequence': first - 1})
        total = len(page.question_ids) or survey.question_count
        if total and draw >= total:
            raise UserError(_(
                "The test has %(m)s questions, so drawing %(n)s is every "
                "question. Pick a smaller number, or 0 for all.", m=total,
                n=draw))
        page.write({'random_questions_count': draw})
        survey.write({'questions_selection': 'random'})
        return {'message': _("Each attempt now draws %(n)s of %(m)s "
                             "questions.", n=draw, m=total or draw)}

    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'create_test':
            return self.create_test(payload)
        if verb == 'set_pool':
            return self.set_pool(payload.get('survey_id'), payload.get('draw'))
        return super().act(verb, payload)
