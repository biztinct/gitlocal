# -*- coding: utf-8 -*-
"""WDGAP QF4 — "Read scores from Goals" on the pay review (pb_pay side).

Numbered as in `docs/handovers/wdgap/WDGAP_QF4_HANDOVER.md` §5:

  2. the dry run writes nothing and counts; "Use these scores" writes
     `source='goals'` rows and re-applies the guidance;
  3. pay-review write rights are enough (no Goals rights needed), only the
     review's own people are read, no write rights → refused, a decided
     review → refused;
  4. the default year is the latest closed one ending on or before the
     review's effective date; an open year can be chosen and is flagged;
  5. (second half) a review made after the year closed opens filled in.

Every test skips where Goals is not installed: pb_pay does not depend on it.
The pay world is P6b's (`TestPayReview.setUpClass`), reused by subclassing —
the loader runs only the tests a class defines itself (UPDATES ledger G98).
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_pay_review import TestPayReview


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4GoalScores(TestPayReview):

    def setUp(self):
        super().setUp()
        if 'pb.goal.set' not in self.env:
            self.skipTest('Goals is not installed here')
        self.Cycle = self.env['pb.goal.cycle']
        self.Set = self.env['pb.goal.set']
        self.today = fields.Date.context_today(self.env.user)

    # ------------------------------------------------------------ helpers
    def _year(self, name, start, end, state='closed'):
        cycle = self.Cycle.create({
            'name': name, 'company_id': self.company.id,
            'date_start': start, 'date_end': end})
        if state != 'draft':
            cycle.sudo().write({'state': state})
        return cycle

    def _sheet(self, cycle, employee, mark):
        sheet = self.Set.create({
            'employee_id': employee.id, 'cycle_id': cycle.id,
            'company_id': self.company.id, 'deadline': cycle.date_end})
        goal = self.env['pb.goal'].create({
            'set_id': sheet.id, 'title': 'DEMO QF4 goal',
            'description': 'DEMO what good looks like.',
            'date_start': cycle.date_start, 'date_end': cycle.date_end,
            'weight': 100.0})
        kr = self.env['pb.goal.kr'].create({
            'goal_id': goal.id, 'title': 'DEMO QF4 result',
            'measure': 'things', 'target': 10.0})
        if mark is not None:
            kr.sudo().write({'score': mark})
        sheet.invalidate_recordset()
        return sheet

    def _closed_year_with_scores(self):
        cycle = self._year('DEMO QF4 last year',
                           self.today - timedelta(days=400),
                           self.today - timedelta(days=30))
        alice = self._sheet(cycle, self.alice, '4')    # 4.0 → 3 of 4
        bob = self._sheet(cycle, self.bob, None)        # unscored → skipped
        return cycle, alice, bob

    def _rows(self, review):
        return self.Rating.search([('review_id', '=', review.id)])

    # ================================================================ T2
    def test_02_dry_run_writes_nothing_then_use_writes_goals_rows(self):
        cycle, _alice, _bob = self._closed_year_with_scores()
        review = self._review()
        self._rows(review).unlink()
        review.apply_guidance_to()
        people = len(review.line_ids)
        preview = self.Reviews.goal_scores(review.id, cycle.id, True)
        self.assertEqual(preview['read'], 1)
        self.assertEqual(preview['changed'], 1)
        self.assertEqual(preview['missing'], people - 1)
        self.assertEqual(preview['cycle_id'], cycle.id)
        self.assertTrue(preview['cycle_closed'])
        self.assertEqual(len(preview['mapping']), 4)
        self.assertFalse(self._rows(review), 'a preview must write nothing')

        answer = self.Reviews.goal_scores(review.id, cycle.id, False)
        self.assertEqual(answer['written'], 1)
        rows = self._rows(review)
        self.assertEqual(rows.mapped('source'), ['goals'])
        self.assertEqual(rows.employee_id, self.alice)
        line = self._line(review, self.alice)
        self.assertEqual(line.rating, 3)
        self.assertEqual(
            line.guidance_pct,
            self.grid.pct_for(3, line.position_pct, line.has_band),
            'the guidance must be re-applied, as after a paste')
        # Unchanged a second time: everything reads, nothing changes.
        again = self.Reviews.goal_scores(review.id, cycle.id, True)
        self.assertEqual(again['changed'], 0)

    def test_02_the_source_is_named_in_plain_words(self):
        labels = dict(self.Rating._fields['source'].selection)
        self.assertEqual(labels.get('goals'), 'Read from Goals')

    # ================================================================ T3
    def test_03_pay_rights_are_enough_and_only_review_people_are_read(self):
        cycle, _alice, _bob = self._closed_year_with_scores()
        review = self._review()
        late = self._person('Review Latecomer', 1500.0)
        self._sheet(cycle, late, '5')
        self.assertNotIn(late, review.line_ids.employee_id)
        user = self.preparer
        self.assertFalse(user.has_group('pb_goals.group_goals_user')
                         if self.env.ref('pb_goals.group_goals_user',
                                         raise_if_not_found=False) else False)
        preview = self.Reviews.with_user(user).goal_scores(
            review.id, cycle.id, True)
        self.assertEqual(preview['read'], 1,
                         'somebody not on the review was read')
        names = [row['text'] for row in preview['rows']]
        self.assertNotIn('Review Latecomer', names)
        self.Reviews.with_user(user).goal_scores(review.id, cycle.id, False)
        self.assertEqual(self._line(review, self.alice).rating, 3)

    def test_03_no_write_rights_is_refused(self):
        cycle, _a, _b = self._closed_year_with_scores()
        review = self._review()
        viewer = self._staff_user(
            'qf4.viewer@example.com',
            ['base.group_user', 'pb_pay.group_pay_viewer'])
        with self.assertRaises(AccessError):
            self.Reviews.with_user(viewer).goal_scores(
                review.id, cycle.id, True)

    def test_03_a_decided_review_is_refused(self):
        cycle, _a, _b = self._closed_year_with_scores()
        review = self._review()
        review.sudo().write({'state': 'approved'})
        with self.assertRaises(UserError):
            self.Reviews.goal_scores(review.id, cycle.id, True)

    def test_03_a_year_of_another_company_is_refused(self):
        other = self.env['res.company'].create({'name': 'QF4 Other Co'})
        foreign = self.Cycle.create({
            'name': 'DEMO QF4 foreign', 'company_id': other.id,
            'date_start': self.today - timedelta(days=400),
            'date_end': self.today - timedelta(days=30)})
        foreign.sudo().write({'state': 'closed'})
        review = self._review()
        with self.assertRaises(UserError):
            self.Reviews.goal_scores(review.id, foreign.id, True)

    # ================================================================ T4
    def test_04_default_year_and_an_open_year_is_flagged(self):
        before = self._year('DEMO QF4 ended before',
                            self.today - timedelta(days=400),
                            self.today - timedelta(days=30))
        self._year('DEMO QF4 older',
                   self.today - timedelta(days=800),
                   self.today - timedelta(days=401))
        self._year('DEMO QF4 ends after',
                   self.today - timedelta(days=29),
                   self.today + timedelta(days=200))
        running = self._year('DEMO QF4 running',
                             self.today + timedelta(days=201),
                             self.today + timedelta(days=560), state='open')
        review = self._review()
        preview = self.Reviews.goal_scores(review.id, False, True)
        self.assertEqual(preview['cycle_id'], before.id)
        offered = {y['id']: y for y in preview['years']}
        self.assertIn(running.id, offered)
        self.assertFalse(offered[running.id]['closed'])
        self.assertIn('not closed yet', offered[running.id]['label'])
        chosen = self.Reviews.goal_scores(review.id, running.id, True)
        self.assertEqual(chosen['cycle_id'], running.id)
        self.assertFalse(chosen['cycle_closed'])

    def test_04_the_review_payload_says_goals_is_here(self):
        review = self._review()
        head = self.Reviews.open_review(review.id, 0, {}, with_rows=False)
        self.assertTrue(head['has_goals'])

    # ================================================================ T5
    def test_05_a_review_made_after_the_close_opens_filled_in(self):
        if 'pb_performance_rating' not in self.env['hr.employee']._fields:
            self.skipTest('no performance rating field on this build')
        cycle = self._year('DEMO QF4 to close',
                           self.today - timedelta(days=400),
                           self.today - timedelta(days=30), state='open')
        self._sheet(cycle, self.alice, '5')      # 5.0 → 5 on the record
        self._sheet(cycle, self.bob, None)
        self.alice.sudo().pb_performance_rating = False
        self.bob.sudo().pb_performance_rating = False
        self.Cycle.close_cycle(cycle.id, with_gaps=True)
        self.alice.invalidate_recordset()
        self.assertEqual(self.alice.sudo().pb_performance_rating, '5')
        self.assertFalse(self.bob.sudo().pb_performance_rating)
        review = self._review()
        seeded = self._rows(review).filtered(
            lambda r: r.employee_id == self.alice)
        self.assertEqual(seeded.rating, 5)
        self.assertEqual(seeded.source, 'synced')
        self.assertFalse(self._rows(review).filtered(
            lambda r: r.employee_id == self.bob))
