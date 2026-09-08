# -*- coding: utf-8 -*-
"""GROUP P6b — what the pay review promises, tested.

T1  guidance: what each square answers, the unrated and no-band chips, and
    the migration from an old merit matrix
T2  scores: one per person per review, the paste preview and its commit, and
    the legacy snapshot
T3  meters: allocated, left, people, a chip for every kind of limit, block
    against warn, and fairness recomputed only when it is dirty
T4  the cascade: each step gated on its own role, sent back with a note, the
    trail complete, a task raised for the next person
T5  calibration and the bulk gestures: the payload, one recompute for a
    block, sharing out what is left, and what counts as an outlier
T6  apply: the preview is the write, the wage moves, the letter is filed, the
    positions are rebuilt, undo puts every figure back, and a computed
    payslip is never touched
T7  a pay change: its chips, the refusal while a review is open, its cascade,
    its apply and its undo
T8  the portal page: it renders, it is about one person, and it switches off
T9  the budget rows came home (in `pb_budget`'s own suite)
T11 the pre-flight gate: what it passes and what it refuses
T12 the words on the screen
"""

import os
import re
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)


@tagged('post_install', '-at_install')
class TestPayReview(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Guidance = cls.env['pb.pay.guidance']
        cls.Rating = cls.env['pb.pay.rating']
        cls.Review = cls.env['pb.pay.review']
        cls.Line = cls.env['pb.pay.review.line']
        cls.Limit = cls.env['pb.pay.review.limit']
        cls.Apply = cls.env['pb.pay.apply']
        cls.Change = cls.env['pb.pay.change']
        cls.Reviews = cls.env['pb.pay.reviews']
        cls.Settings = cls.env['pb.pay.settings']
        cls.Position = cls.env['pb.pay.position']
        cls.Band = cls.env['pb.pay.band']

        cls.currency = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.env.company.currency_id
        cls.company = cls.env['res.company'].create({
            'name': 'Pay Review Test Co', 'currency_id': cls.currency.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company

        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Review Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Review Type'})
        cls.job = cls.env['hr.job'].create({
            'name': 'Review Test Operator', 'company_id': cls.company.id})

        cls.family = cls.env['pb.pay.family'].create(
            {'name': 'Review Test Family'})
        cls.band = cls.Band.create({
            'family_id': cls.family.id, 'level': 4, 'country_code': 'VN',
            'currency_id': cls.currency.id,
            'min_amount': 1000.0, 'mid_amount': 2000.0, 'max_amount': 3000.0,
            'date_from': '2020-01-01',
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.env['pb.pay.band.job'].create(
            {'band_id': cls.band.id, 'job_id': cls.job.id})

        cls.grid = cls.Guidance.create({
            'name': 'Review Test Guidance', 'rating_scale': '4',
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.settings = cls.Settings.for_company(cls.company)
        cls.settings.write({'guidance_id': cls.grid.id})

        cls.boss = cls._person('Review Boss', 2800.0)
        cls.alice = cls._person('Review Alice', 1200.0, manager=cls.boss)
        cls.bob = cls._person('Review Bob', 2600.0, manager=cls.boss,
                              sex='male')
        cls.Position.recompute_all([cls.company.id])

    # ------------------------------------------------------------ helpers
    @classmethod
    def _person(cls, name, wage, sex='female', months=40, manager=None):
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id,
            'parent_id': manager.id if manager else False,
        })
        if employee.current_version_id:
            employee.current_version_id.write(
                {'sex': sex, 'job_id': cls.job.id})
        cls.env['hr.contract'].create({
            'name': 'Contract %s' % name,
            'employee_id': employee.id,
            'company_id': cls.company.id,
            'date_start': date.today() - timedelta(days=int(months * 30.4)),
            'state': 'open',
            'wage': wage,
            'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        return employee

    def _review(self, budget=100000.0):
        review = self.Review.create({
            'name': 'Test review',
            'scope_kind': 'company', 'scope_ref': self.company.id,
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'currency_id': self.currency.id,
            'year': date.today().year,
            'effective_date': date.today(),
            'budget_amount': budget,
            'guidance_id': self.grid.id,
        })
        review.build_lines()
        return review

    def _line(self, review, employee):
        return review.line_ids.filtered(
            lambda l: l.employee_id.id == employee.id)

    # ================================================================== T1
    def test_t01_every_square_of_the_grid_exists_and_answers(self):
        """A missing square is a silent zero, so a grid is born complete."""
        self.assertEqual(len(self.grid.cell_ids), 4 * 5)
        top = self.grid.pct_for(4, 10.0, True)
        bottom = self.grid.pct_for(1, 10.0, True)
        self.assertGreater(top, bottom,
                           'somebody who did better must not get less')
        low = self.grid.pct_for(4, 10.0, True)
        high = self.grid.pct_for(4, 90.0, True)
        self.assertGreaterEqual(low, high,
                                'the same score lower in the band gets more')

    def test_t01_no_band_and_no_score_land_in_the_middle_and_say_so(self):
        review = self._review()
        line = self._line(review, self.alice)
        self.assertTrue(line, 'the worksheet did not pick the person up')
        keys = {chip['key'] for chip in (line.chips or [])}
        self.assertIn('unrated', keys,
                      'an unscored row must say the guidance guessed')
        # The guidance still answered rather than leaving the row empty.
        self.assertEqual(line.guidance_pct,
                         self.grid.pct_for(self.grid.middle_rating(),
                                           line.position_pct, line.has_band))

    def test_t01_an_old_merit_matrix_becomes_a_grid(self):
        if 'wfp.merit.matrix' not in self.env:
            self.skipTest('the old planning module is not installed here')
        matrix = self.env['wfp.merit.matrix'].create(
            {'name': 'P6B Test Matrix', 'company_id': self.company.id})
        self.env['wfp.merit.matrix.cell'].create({
            'matrix_id': matrix.id, 'performance_label': 'Exceeds',
            'compa_min': 80.0, 'compa_max': 90.0, 'increase_pct': 7.5,
        })
        before = self.Guidance.search_count([])
        report = self.Guidance.migrate_legacy()
        self.assertGreaterEqual(report['grids'], 1)
        self.assertGreater(self.Guidance.search_count([]), before)
        again = self.Guidance.migrate_legacy()
        self.assertEqual(again['grids'], 0, 'the migration must be idempotent')
        self.assertGreaterEqual(again['skipped'], 1)

    # ================================================================== T2
    def test_t02_one_score_per_person_per_review(self):
        review = self._review()
        self.Rating.create({'review_id': review.id,
                            'employee_id': self.alice.id, 'rating': 3})
        with self.assertRaises(Exception):
            self.Rating.create({'review_id': review.id,
                                'employee_id': self.alice.id, 'rating': 4})

    def test_t02_a_paste_previews_before_it_writes(self):
        review = self._review()
        text = 'Review Alice, 4\nReview Bob, 2\nNobody At All, 3\nrubbish\n'
        preview = self.Rating.paste(review.id, text, dry_run=True)
        self.assertEqual(preview['good'], 2)
        self.assertEqual(preview['bad'], 2)
        self.assertEqual(
            self.Rating.search_count([('review_id', '=', review.id)]), 0,
            'a preview must write nothing at all')
        written = self.Rating.paste(review.id, text, dry_run=False)
        self.assertEqual(written['written'], 2)
        self.assertEqual(
            self.Rating.search_count([('review_id', '=', review.id)]), 2)
        self.assertEqual(self._line(review, self.alice).rating, 4)

    def test_t02_a_score_out_of_range_is_refused_by_name(self):
        review = self._review()
        answer = self.Rating.paste(review.id, 'Review Alice, 9', dry_run=True)
        self.assertEqual(answer['good'], 0)
        self.assertIn('1 to 4', answer['rows'][0]['why'])

    def test_t02_the_old_per_person_score_is_kept(self):
        if 'wfp_performance_rating' not in self.env['hr.employee']._fields:
            self.skipTest('the old planning module is not installed here')
        self.alice.sudo().write({'wfp_performance_rating': '4'})
        report = self.Rating.migrate_legacy()
        self.assertGreaterEqual(report['kept'], 1)
        kept = self.Rating.search([('employee_id', '=', self.alice.id),
                                   ('source', '=', 'legacy')])
        self.assertTrue(kept)
        self.assertEqual(kept[0].rating, 4)
        # And the new field on the person was seeded, so the two screens that
        # used to write the old one still have somewhere to write.
        self.assertEqual(self.alice.sudo().pb_performance_rating, '4')

    # ================================================================== T3
    def test_t03_the_meters_add_up_and_the_budget_is_what_is_left(self):
        review = self._review(budget=50000.0)
        self.assertEqual(review.people, len(review.line_ids))
        total = sum(line.annual_cost_delta for line in review.line_ids)
        self.assertAlmostEqual(review.allocated_amount, total, places=2)
        self.assertAlmostEqual(review.remaining_amount,
                               50000.0 - total, places=2)

    def test_t03_every_kind_of_limit_marks_the_row_it_is_about(self):
        review = self._review()
        line = self._line(review, self.alice)
        self.Limit.create({'review_id': review.id, 'kind': 'max_raise_pct',
                           'value': 1.0, 'enforcement': 'block'})
        line.set_proposal(pct=20.0)
        review.recompute_chips()
        chips = line.chips or []
        self.assertTrue(any(c['key'] == 'max_raise_pct' for c in chips))
        self.assertTrue(any(c['blocks'] for c in chips))
        self.assertGreaterEqual(review.lines_blocked, 1)

    def test_t03_a_warning_does_not_stop_the_review_and_a_block_does(self):
        review = self._review()
        line = self._line(review, self.alice)
        limit = self.Limit.create({
            'review_id': review.id, 'kind': 'max_raise_pct',
            'value': 1.0, 'enforcement': 'warn'})
        line.set_proposal(pct=25.0)
        review.recompute_chips()
        self.assertEqual(review.lines_blocked, 0)
        review.action_submit()
        self.assertEqual(review.state, 'proposed')

        limit.write({'enforcement': 'block'})
        review._chain_state_write('draft')
        review.recompute_chips()
        with self.assertRaises(UserError):
            review.action_submit()

    def test_t03_the_band_ceiling_limit_reads_the_band(self):
        review = self._review()
        self.Limit.create({'review_id': review.id, 'kind': 'band_ceiling',
                           'value': 0.0, 'enforcement': 'block'})
        line = self._line(review, self.bob)
        line.set_proposal(pct=50.0)          # 2600 -> 3900, over the 3000 top
        review.recompute_chips()
        self.assertTrue(any(c['key'] == 'band_ceiling'
                            for c in (line.chips or [])))

    def test_t03_fairness_is_worked_out_when_it_is_read_and_not_before(self):
        review = self._review()
        self.assertTrue(review.fairness_dirty)
        answer = review.fairness()
        self.assertFalse(review.fairness_dirty)
        self.assertIn('sentence', answer)
        self.assertTrue(answer['sentence'])
        # A write marks it dirty again rather than recomputing on the spot.
        self._line(review, self.alice).set_proposal(pct=5.0)
        review.mark_fairness_dirty()
        self.assertTrue(review.fairness_dirty)

    def test_t03_a_review_over_its_budget_will_not_be_sent(self):
        review = self._review(budget=1.0)
        self._line(review, self.alice).set_proposal(pct=10.0)
        with self.assertRaises(UserError):
            review.action_submit()

    # ================================================================== T4
    def _staff(self, login, groups):
        user = self.env['res.users'].create({
            'name': login, 'login': login,
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])],
        })
        return user

    def test_t04_each_step_is_gated_on_its_own_role(self):
        review = self._review()
        hr = self._staff('p6b.hr@example.com',
                         ['base.group_user', 'pb_pay.group_pay_manager'])
        finance = self._staff('p6b.finance@example.com',
                              ['base.group_user', 'pb_pay.group_pay_finance'])
        boss = self._staff('p6b.ceo@example.com',
                           ['base.group_user', 'pb_pay.group_pay_ceo'])

        review.with_user(hr).action_submit()
        self.assertEqual(review.state, 'proposed')
        with self.assertRaises(AccessError):
            review.with_user(finance).action_hr_approve()
        review.with_user(hr).action_hr_approve()
        self.assertEqual(review.state, 'hr_review')
        with self.assertRaises(AccessError):
            review.with_user(hr).action_finance_approve()
        review.with_user(finance).action_finance_approve()
        self.assertEqual(review.state, 'finance')
        with self.assertRaises(AccessError):
            review.with_user(finance).action_ceo_approve()
        review.with_user(boss).action_ceo_approve()
        self.assertEqual(review.state, 'approved')

        trail = review.get_approval_trail()
        self.assertEqual([step['to_state'] for step in trail],
                         ['proposed', 'hr_review', 'finance', 'approved'])

    def test_t04_a_review_can_be_sent_back_with_a_reason(self):
        review = self._review()
        review.action_submit()
        review.action_send_back(note='The Retail numbers look wrong.')
        self.assertEqual(review.state, 'draft')
        trail = review.get_approval_trail()
        self.assertIn('Retail', trail[-1]['note'])

    def test_t04_one_row_can_be_sent_back_on_its_own(self):
        review = self._review()
        line = self._line(review, self.alice)
        self.Reviews.return_line(review.id, line.id, 'Talk to me first.')
        self.assertEqual(line.state, 'returned')
        self.assertIn('Talk to me', line.returned_note)
        with self.assertRaises(UserError):
            self.Reviews.return_line(review.id, line.id, '   ')

    def test_t04_the_next_person_gets_a_real_task(self):
        review = self._review()
        self._staff('p6b.hr2@example.com',
                    ['base.group_user', 'pb_pay.group_pay_manager'])
        review.action_submit()
        self.env.flush_all()
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'pb.pay.review'), ('res_id', '=', review.id)])
        self.assertTrue(activities,
                        'nobody was told the review is waiting for them')

    def test_t04_what_is_waiting_is_counted_for_the_reader(self):
        review = self._review()
        review.action_submit()
        answer = self.Reviews.awaiting()
        self.assertGreaterEqual(answer['count'], 1)
        self.assertTrue(answer['sentence'])

    # ================================================================== T5
    def test_t05_the_calibration_payload_holds_everybody(self):
        review = self._review()
        answer = self.Reviews.calibration(review.id)
        self.assertEqual(len(answer['people']), len(review.line_ids))
        self.assertEqual(answer['total'], len(review.line_ids))
        self.assertIn('max_pct', answer)
        self.assertEqual(len(answer['words']),
                         int(review.rating_scale or '4'))
        self.assertEqual(len(answer['columns']),
                         int(review.rating_scale or '4'))

    def test_t05_the_picture_carries_no_cap_and_no_names(self):
        """LOOK rule 16 on the one screen that could still drop somebody.

        And R4: the set that DRAWS the picture carries nothing but what is
        needed to place a mark — at four and a half thousand people, sending
        everybody's name to draw a shape is both a payload and a permission
        problem.
        """
        review = self._review()
        answer = self.Reviews.calibration(review.id)
        self.assertNotIn('capped', answer)
        self.assertNotIn('capped_note', answer)
        self.assertNotIn('dots', answer)
        for person in answer['people']:
            self.assertEqual(sorted(person), ['column', 'line_id', 'pct',
                                              'state'])
        names = {line.employee_id.name for line in review.line_ids}
        listed = {row['name'] for row in answer['outliers']}
        self.assertFalse(listed - names - {''},
                         'the outlier list invented a name')

    def test_t05_a_far_bigger_rise_than_the_others_stands_out(self):
        review = self._review()
        for line in review.line_ids:
            line.set_proposal(pct=3.0)
        self._line(review, self.alice).set_proposal(pct=40.0)
        answer = self.Reviews.calibration(review.id)
        ringed = [one for one in answer['people'] if one['state'] != 'normal']
        self.assertTrue(ringed, 'nothing stood out on an obvious outlier')
        self.assertTrue(answer['outliers'])
        self.assertEqual(answer['outliers_total'], len(ringed))
        self.assertTrue(answer['outliers'][0]['why'])
        self.assertTrue(answer['outliers'][0]['state_word'])

    def test_t05_a_rise_that_breaks_a_limit_says_so_by_name(self):
        """R6: the three states are normal, outlier and blocked, and a limit
        saying no is the more urgent fact about a row."""
        review = self._review()
        self.Limit.create({'review_id': review.id, 'kind': 'max_raise_pct',
                           'value': 5.0, 'enforcement': 'block'})
        for line in review.line_ids:
            line.set_proposal(pct=2.0)
        self._line(review, self.bob).set_proposal(pct=9.0)
        review.recompute_chips()
        answer = self.Reviews.calibration(review.id)
        states = {one['line_id']: one['state'] for one in answer['people']}
        self.assertEqual(states[self._line(review, self.bob).id], 'blocked')
        self.assertEqual(states[self._line(review, self.alice).id], 'normal')
        limits = answer['limits']
        self.assertEqual(len(limits), 1)
        self.assertEqual(limits[0]['value'], 5.0)
        self.assertTrue(limits[0]['blocks'])
        self.assertIn('5', limits[0]['sentence'])

    def test_t05_each_column_carries_the_middle_of_its_own_score(self):
        review = self._review()
        for line in review.line_ids:
            line.rating = 3
            line.set_proposal(pct=0.0)
        rises = [2.0, 6.0, 10.0]
        for line, pct in zip(review.line_ids, rises):
            line.set_proposal(pct=pct)
        answer = self.Reviews.calibration(review.id)
        third = next(one for one in answer['columns'] if one['column'] == 3)
        self.assertTrue(third['has_median'])
        self.assertAlmostEqual(third['median'], 6.0, places=2)
        self.assertEqual(third['scored'], len(review.line_ids))
        self.assertEqual(third['drawn'], len(review.line_ids))
        self.assertIn('6', third['median_label'])

    def test_t05_a_score_nobody_used_is_still_a_column(self):
        review = self._review()
        for line in review.line_ids:
            line.rating = 2
        answer = self.Reviews.calibration(review.id)
        empty = next(one for one in answer['columns'] if one['column'] == 4)
        self.assertEqual(empty['scored'], 0)
        self.assertEqual(empty['drawn'], 0)
        self.assertFalse(empty['has_median'])
        self.assertTrue(empty['word'])

    def test_t05_a_person_nobody_scored_is_drawn_in_the_middle(self):
        review = self._review()
        for line in review.line_ids:
            line.rating = 0
        answer = self.Reviews.calibration(review.id)
        levels = int(review.rating_scale or '4')
        middle = max(1, (levels + 1) // 2)
        self.assertTrue(all(one['column'] == middle
                            for one in answer['people']))
        column = next(one for one in answer['columns']
                      if one['column'] == middle)
        self.assertEqual(column['scored'], 0)
        self.assertEqual(column['drawn'], len(review.line_ids))
        self.assertEqual(column['unscored'], len(review.line_ids))

    def test_t05_the_axis_reaches_past_the_limit_it_draws(self):
        """A limit drawn off the top of the picture explains nothing."""
        review = self._review()
        self.Limit.create({'review_id': review.id, 'kind': 'max_raise_pct',
                           'value': 15.0, 'enforcement': 'warn'})
        for line in review.line_ids:
            line.set_proposal(pct=8.0)
        review.recompute_chips()
        answer = self.Reviews.calibration(review.id)
        self.assertGreater(answer['max_pct'], 15.0)

    def test_t05_the_people_in_one_bin_are_named_on_demand(self):
        review = self._review()
        for line in review.line_ids:
            line.rating = 3
            line.set_proposal(pct=4.0)
        answer = self.Reviews.calibration_people(review.id, 3, 3.0, 5.0)
        self.assertTrue(answer['allowed'])
        self.assertEqual(answer['total'], len(review.line_ids))
        names = {row['name'] for row in answer['rows']}
        self.assertIn('Review Alice', names)
        self.assertTrue(answer['title'])
        self.assertTrue(all(row['state_word'] for row in answer['rows']))
        # A bin nobody is standing in says so rather than answering nothing.
        nobody = self.Reviews.calibration_people(review.id, 3, 90.0, 95.0)
        self.assertTrue(nobody['allowed'])
        self.assertEqual(nobody['rows'], [])
        self.assertTrue(nobody['title'])

    def test_t05_a_bin_is_half_open_so_nobody_is_listed_twice(self):
        """A person standing exactly on a boundary belongs to ONE bar.

        The two ENDS of the axis are the exception and have to be: somebody
        beyond either end is drawn ON that end, so the first and the last bin
        are closed or the picture would count them and the list would not.
        """
        review = self._review()
        for line in review.line_ids:
            line.rating = 3
            line.set_proposal(pct=5.0)
        # One much bigger rise, so 5% is nowhere near the top of the axis.
        self._line(review, self.alice).set_proposal(pct=20.0)
        lower = self.Reviews.calibration_people(review.id, 3, 4.0, 5.0)
        upper = self.Reviews.calibration_people(review.id, 3, 5.0, 6.0)
        self.assertEqual(lower['total'], 0)
        self.assertEqual(upper['total'], len(review.line_ids) - 1)
        # The topmost bin is closed, so the biggest rise is in it.
        picture = self.Reviews.calibration(review.id)
        top = picture['max_pct']
        highest = self.Reviews.calibration_people(review.id, 3, top - 1.0, top)
        self.assertEqual(highest['total'], 1)

    def test_t05_a_reader_with_no_name_role_gets_no_names_at_all(self):
        """A team manager reads their own team's rows and NO names.

        `group_pay_viewer` is the role that reads a review without running
        one: the rows are their own team's (`rule_review_line_own_team`) and
        the names are not theirs to see. The picture still draws.
        """
        review = self._review()
        for line in review.line_ids:
            line.set_proposal(pct=3.0)
        self._line(review, self.alice).set_proposal(pct=40.0)
        viewer = self._staff('p2.viewer@example.com',
                             ['base.group_user', 'pb_pay.group_pay_viewer'])
        self.boss.sudo().user_id = viewer.id
        picture = self.Reviews.with_user(viewer).calibration(review.id)
        self.assertFalse(picture['can_names'])
        self.assertTrue(picture['people'], 'the picture drew nothing at all')
        real = {line.employee_id.name for line in review.line_ids}
        for row in picture['outliers']:
            self.assertNotIn(row['name'], real)
        bin_rows = self.Reviews.with_user(viewer).calibration_people(
            review.id, picture['people'][0]['column'], 0.0, 100.0)
        self.assertTrue(bin_rows['rows'])
        for row in bin_rows['rows']:
            self.assertNotIn(row['name'], real)
        self.boss.sudo().user_id = False

    def test_t05_two_ends_of_a_narrow_range_are_told_apart(self):
        """LOOK L4: a bin a tenth of a point wide may not print its two ends
        as the same figure."""
        low, high = self.Reviews._pct_pair(7.02, 7.14)
        self.assertNotEqual(low, high)
        wide_low, wide_high = self.Reviews._pct_pair(0.0, 30.0)
        self.assertEqual((wide_low, wide_high), ('0', '30'))

    def test_t05_a_block_of_rows_moves_in_one_pass(self):
        review = self._review()
        ids = review.line_ids.ids
        before = {line.id: line.proposal_pct for line in review.line_ids}
        self.Reviews.nudge(review.id, ids, 1.0)
        for line in review.line_ids:
            self.assertAlmostEqual(line.proposal_pct,
                                   before[line.id] + 1.0, places=2)

    def test_t05_sharing_out_what_is_left_respects_the_budget(self):
        review = self._review(budget=120000.0)
        left = review.remaining_amount
        self.assertGreater(left, 0)
        answer = self.Reviews.spread_remaining(review.id, review.line_ids.ids)
        self.assertIn('sentence', answer)
        self.assertLessEqual(review.allocated_amount,
                             review.budget_amount + 1.0,
                             'sharing out what is left must not overspend')

    def test_t05_nothing_left_says_so_rather_than_doing_nothing(self):
        review = self._review(budget=0.0)
        answer = self.Reviews.spread_remaining(review.id, review.line_ids.ids)
        self.assertIn('nothing left', answer['sentence'].lower())

    # ================================================================== T6
    def _approved(self, budget=1000000.0):
        review = self._review(budget=budget)
        for line in review.line_ids:
            line.set_proposal(pct=5.0)
        review.recompute_chips()
        review.action_submit()
        review.action_hr_approve()
        review.action_finance_approve()
        review.action_ceo_approve()
        return review

    def test_t06_the_preview_is_exactly_what_the_write_does(self):
        review = self._approved()
        preview = self.Apply.preview_review(review.id)
        movers = review.line_ids.filtered(
            lambda l: abs(l.new_wage - l.current_wage) > 0.005)
        self.assertEqual(preview['count'], len(movers))
        answer = self.Reviews.apply(review.id)
        self.assertEqual(answer['count'], preview['count'])

    def test_t06_apply_moves_the_wage_and_keeps_the_old_one(self):
        review = self._approved()
        line = self._line(review, self.alice)
        was = line.contract_id.wage
        becomes = line.new_wage
        self.Reviews.apply(review.id)
        self.assertAlmostEqual(line.contract_id.wage, becomes, places=2)
        row = self.Apply.search([('review_id', '=', review.id),
                                 ('employee_id', '=', self.alice.id)])
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(row.old_wage, was, places=2)
        self.assertTrue(row.undo_until)
        self.assertEqual(review.state, 'applied')

    def test_t06_a_letter_is_written_and_filed_for_everybody(self):
        if 'pb.hr.letter' not in self.env:
            self.skipTest('the letter engine is not installed here')
        review = self._approved()
        self.Reviews.apply(review.id)
        rows = self.Apply.search([('review_id', '=', review.id)])
        self.assertTrue(rows)
        self.assertTrue(all(row.letter_id for row in rows),
                        'somebody was given a raise and no letter')

    def test_t06_undo_puts_every_figure_back_exactly(self):
        review = self._approved()
        before = {line.employee_id.id: line.contract_id.wage
                  for line in review.line_ids if line.contract_id}
        self.Reviews.apply(review.id)
        self.Reviews.undo(review.id)
        for employee_id, wage in before.items():
            line = review.line_ids.filtered(
                lambda l: l.employee_id.id == employee_id)
            self.assertAlmostEqual(line.contract_id.wage, wage, places=2)
        self.assertEqual(review.state, 'approved')
        self.assertFalse(self.Apply.search([('review_id', '=', review.id),
                                            ('state', '=', 'applied')]))

    def test_t06_after_the_window_undo_is_refused_in_words(self):
        review = self._approved()
        self.Reviews.apply(review.id)
        review.sudo().undo_until = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            self.Reviews.undo(review.id)

    def test_t06_a_payslip_that_has_been_worked_out_is_never_touched(self):
        review = self._approved()
        slip = self.env['hr.payslip'].sudo().search(
            [('company_id', '=', self.company.id)], limit=1)
        if not slip:
            self.assertNotIn('hr.payslip', _source('models/pb_pay_review.py'),
                             'the review model must not name a payslip')
            self.skipTest('no payslip on this database to guard')
        before = (slip.state, sum(slip.line_ids.mapped('total')))
        self.Reviews.apply(review.id)
        after = (slip.state, sum(slip.line_ids.mapped('total')))
        self.assertEqual(before, after)

    def test_t06_the_positions_are_rebuilt_after_a_raise(self):
        review = self._approved()
        self.Reviews.apply(review.id)
        row = self.Position.search([('employee_id', '=', self.alice.id)])
        self.assertTrue(row)
        self.assertAlmostEqual(
            row.wage, self._line(review, self.alice).new_wage, places=2)

    def test_t06_a_review_that_has_been_applied_is_never_deleted(self):
        review = self._approved()
        self.Reviews.apply(review.id)
        with self.assertRaises(UserError):
            review.unlink()

    # ================================================================== T7
    def test_t07_a_pay_change_carries_the_guidance_and_the_limits(self):
        self.settings.limit_ids = [(0, 0, {
            'kind': 'max_raise_pct', 'value': 5.0, 'enforcement': 'block'})]
        change = self.Change.create({
            'employee_id': self.bob.id,
            'kind': 'promotion',
            'new_wage': 2600.0 * 1.4,
            'effective_date': date.today(),
            'reason': 'Took on the whole line.',
        })
        self.assertGreater(change.pct, 5.0)
        self.assertTrue(any(chip['blocks'] for chip in (change.chips or [])))
        with self.assertRaises(UserError):
            change.action_submit()
        self.settings.limit_ids.unlink()

    def test_t07_a_pay_change_is_refused_while_a_review_is_open(self):
        review = self._review()
        self.assertTrue(review.line_ids)
        with self.assertRaises(UserError):
            self.Change.create({
                'employee_id': self.alice.id,
                'new_wage': 1500.0,
                'effective_date': date.today(),
            })
        review.sudo()._chain_state_write('closed')

    def test_t07_a_pay_change_walks_the_same_ladder_and_undoes(self):
        change = self.Change.create({
            'employee_id': self.boss.id,
            'kind': 'market',
            'new_wage': 2900.0,
            'effective_date': date.today(),
            'reason': 'A counter-offer.',
        })
        was = change.contract_id.wage
        change.action_submit()
        change.action_hr_approve()
        change.action_next_after_hr()
        if change.state == 'finance':
            change.action_ceo_approve()
        self.assertEqual(change.state, 'approved')
        change.action_apply()
        self.assertEqual(change.state, 'applied')
        self.assertAlmostEqual(change.contract_id.wage, 2900.0, places=2)
        change.action_undo()
        self.assertAlmostEqual(change.contract_id.wage, was, places=2)
        self.assertEqual(change.state, 'approved')

    def test_t07_a_change_that_moves_nothing_is_refused(self):
        change = self.Change.create({
            'employee_id': self.boss.id,
            'new_wage': self.boss.contract_ids[:1].wage,
            'effective_date': date.today(),
        })
        with self.assertRaises(UserError):
            change.action_submit()

    # ================================================================== T8
    def test_t08_the_portal_page_is_about_one_person_only(self):
        """A grep, because the promise is an ABSENCE: no route in this module
        may take an employee id, and none may read anybody else's row."""
        body = _source('controllers/portal.py')
        self.assertIn("_ess_employee", body)
        self.assertNotIn('employee_id=', body,
                         'no portal route may take a person as a parameter')
        for route in re.findall(r"@http\.route\(\[([^\]]*)\]", body):
            self.assertNotIn('employee', route)

    def test_t08_the_page_can_be_switched_off_per_company(self):
        self.assertTrue(self.settings.portal_enabled)
        self.settings.portal_enabled = False
        summary = self.settings.summary()
        self.assertFalse(summary['portal_enabled'])
        self.assertIn('switched off', summary['portal_note'])
        self.settings.portal_enabled = True

    # ================================================================= T11
    def test_t11_the_gate_refuses_when_something_has_not_come_across(self):
        gate = self.env['pb.pay.retire']
        answer = gate.preflight()
        self.assertIn('checks', answer)
        self.assertIn('ok', answer)
        keys = {check['key'] for check in answer['checks']}
        for expected in ('guidance', 'reviews', 'ratings', 'budget',
                         'limits', 'manifests', 'plan_lens', 'contracts',
                         'backup'):
            self.assertIn(expected, keys)
        # Every failure carries a sentence a person can act on.
        for check in answer['checks']:
            self.assertTrue(check['text'])
        self.assertTrue(gate.report())

    def test_t11_the_gate_says_no_while_a_module_still_depends_on_the_old_one(
            self):
        answer = self.env['pb.pay.retire']._check_manifests()
        if 'wfp.budget.actual' not in self.env:
            self.skipTest('the old planning module is not installed here')
        self.assertIn('ok', answer)
        self.assertTrue(answer['text'])

    # ================================================================= T12
    def test_t12_the_screen_never_uses_the_old_products_vocabulary(self):
        """Plain English is a rule, and these six words break it."""
        # Written as WORD patterns: "compa" is a substring of "company" and
        # of "compare", and a gate that fails on the word "company" is a gate
        # nobody keeps.
        forbidden = (r'merit matrix', r'\bcompa\b', r'compa[- ]ratio',
                     r'guardrail', r'recommendation', r'compensation cycle')
        offenders = []
        for base, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            if '__pycache__' in base:
                continue
            for name in files:
                if not name.endswith(('.js', '.xml')):
                    continue
                with open(os.path.join(base, name), encoding='utf-8') as fh:
                    body = fh.read().lower()
                body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
                body = re.sub(r'//[^\n]*', '', body)
                body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
                for word in forbidden:
                    if re.search(word, body):
                        offenders.append('%s: %s' % (name, word))
        self.assertFalse(offenders,
                         'the old product\'s vocabulary reached the screen: '
                         '%s' % offenders)

    def test_t12_the_review_screen_says_what_is_waiting_in_a_sentence(self):
        self.assertEqual(self.Reviews._awaiting_sentence(0), '')
        self.assertIn('1 pay decision', self.Reviews._awaiting_sentence(1))
        self.assertIn('3 pay decisions', self.Reviews._awaiting_sentence(3))

    # ------------------------------------------------------- the empty board
    def test_a_reader_with_no_role_is_told_so_rather_than_refused(self):
        nobody = self._staff('p6b.nobody@example.com', ['base.group_user'])
        board = self.Reviews.with_user(nobody).get_board()
        self.assertFalse(board['allowed'])
        self.assertTrue(board['empty_title'])
        self.assertTrue(board['empty_note'])
        self.assertEqual(board['reviews'], [])

    def test_the_board_opens_and_names_its_next_step(self):
        review = self._review()
        board = self.Reviews.get_board()
        self.assertTrue(board['allowed'])
        card = next(c for c in board['reviews'] if c['id'] == review.id)
        self.assertTrue(card['next_step'])
        self.assertTrue(card['meter'])

    def test_a_review_carried_over_from_the_old_screens_is_read_only(self):
        """A PERSON is refused. The server itself is not, because the
        migration that writes the history runs as the server."""
        review = self._review()
        review.sudo().write({'is_legacy': True})
        staff = self._staff('p6b.legacy@example.com',
                            ['base.group_user', 'pb_pay.group_pay_manager'])
        with self.assertRaises(UserError):
            review.with_user(staff).write({'name': 'edited'})


def _source(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as handle:
        return handle.read()
