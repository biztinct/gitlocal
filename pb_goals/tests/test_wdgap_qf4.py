# -*- coding: utf-8 -*-
"""WDGAP QF4 — goal scores into the pay review (pb_goals side).

Numbered as in `docs/handovers/wdgap/WDGAP_QF4_HANDOVER.md` §5:

  1. the mapping, (score, levels) → rating, and an unscored sheet skipped;
  5. closing the year stamps the latest performance score on scored sheets
     only; the old cycle-form "Close it" no longer bypasses the real close.
     (The "a review created afterwards seeds it" half lives in pb_pay's
     suite, which has the pay fixtures.)
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.pay_score import pay_rating
from .test_goals_year import YearCase


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4Mapping(TransactionCase):

    def test_01_the_mapping_table(self):
        expected = {
            5: {0.0: 1, 0.4: 1, 2.5: 3, 3.0: 3, 4.49: 4, 4.5: 5, 5.0: 5},
            4: {0.0: 1, 0.4: 1, 2.5: 2, 3.0: 2, 4.49: 4, 4.5: 4, 5.0: 4},
            3: {0.0: 1, 0.4: 1, 2.5: 2, 3.0: 2, 4.49: 3, 4.5: 3, 5.0: 3},
        }
        for levels, rows in expected.items():
            for score, rating in rows.items():
                self.assertEqual(pay_rating(score, levels), rating,
                                 '%s at %s levels' % (score, levels))

    def test_01_unscored_is_skipped_not_one(self):
        self.assertIsNone(pay_rating(None, 4))
        self.assertIsNone(pay_rating(False, 5))
        # 0.0 is a real score ("nothing done") and is the bottom, not a skip.
        self.assertEqual(pay_rating(0.0, 5), 1)

    def test_01_the_table_covers_every_score_once(self):
        Set = self.env['pb.goal.set']
        for levels in (3, 4, 5):
            rows = Set._pay_mapping(levels)
            self.assertEqual([r['rating'] for r in rows],
                             list(range(1, levels + 1)))
            self.assertEqual(rows[0]['from'], 0.0)
            self.assertEqual(rows[-1]['to'], 5.0)
            for low, high in zip(rows, rows[1:]):
                self.assertAlmostEqual(high['from'], low['to'] + 0.01,
                                       places=2)


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4Close(YearCase):

    def _rating(self, employee):
        employee.invalidate_recordset()
        return employee.sudo().pb_performance_rating

    def setUp(self):
        super().setUp()
        if 'pb_performance_rating' not in self.env['hr.employee']._fields:
            self.skipTest('no performance rating field on this build')

    def test_05_close_stamps_scored_sheets_only(self):
        scored = self._agreed(self.staff)
        self._score_all(scored, '4')            # 4.0 of 5 → 4
        unscored = self._agreed(self.stranger)  # no marks at all
        self.staff.sudo().pb_performance_rating = False
        self.stranger.sudo().pb_performance_rating = '2'
        self.Cycle.close_cycle(self.cycle.id, with_gaps=True)
        self.assertEqual(scored.state, 'closed')
        self.assertEqual(unscored.state, 'closed')
        self.assertEqual(self._rating(self.staff), '4')
        self.assertEqual(self._rating(self.stranger), '2',
                         'an unscored sheet must never write a score')
        posted = self.staff.sudo().message_ids.mapped('body')
        self.assertTrue(any('latest performance score' in (b or '')
                            for b in posted))

    def test_05_reopening_does_not_roll_back(self):
        sheet = self._agreed(self.staff)
        self._score_all(sheet, '5')
        self.Cycle.close_cycle(self.cycle.id)
        self.assertEqual(self._rating(self.staff), '5')
        self.cycle.action_reopen_cycle()
        self.assertEqual(self._rating(self.staff), '5')

    def test_05_a_closed_sheet_reads_the_frozen_figure(self):
        sheet = self._agreed(self.staff)
        self._score_all(sheet, '3')
        self.Cycle.close_cycle(self.cycle.id)
        frozen = sheet.frozen()
        self.assertEqual(sheet._pay_score(), frozen['score'])
        # A later edit of the frozen copy is what is read, not the compute.
        frozen['score'] = 1.0
        import json
        sheet.sudo().frozen_json = json.dumps(frozen)
        self.assertEqual(sheet._pay_score(), 1.0)

    def test_05_the_preview_says_what_closing_stamps(self):
        self._agreed(self.staff)
        preview = self.Cycle.preview_close(self.cycle.id)
        self.assertIn('latest performance score', preview['sentence'])
        self.assertIn('does not take that back', preview['sentence'])

    def test_05_old_close_button_goes_through_the_real_close(self):
        sheet = self._agreed(self.staff)
        # Unscored: the real close refuses; the old button used to close it.
        with self.assertRaises(UserError):
            self.cycle.action_close()
        self.assertEqual(self.cycle.state, 'open')
        self._score_all(sheet, '4')
        self.cycle.action_close()
        self.assertEqual(self.cycle.state, 'closed')
        self.assertEqual(sheet.state, 'closed',
                         'the old button skipped the sheets')
        self.assertTrue(sheet.frozen_json, 'the old button skipped the freeze')
        self.assertEqual(self._rating(self.staff), '4')
