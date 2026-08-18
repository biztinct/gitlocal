# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P7 — the Close board at scale: grouping, paging and the batch.

WHY THIS SUITE EXISTS. On the live demo week the board produced sixty-six flags,
and the only way to clear them was to click "Approve as-is" sixty-six times,
each with its own dialog and its own note. That is not a review, it is a
tolerance test — and the officer's rational response is to stop reading the
rows, which defeats the whole instrument.

The batch is therefore built around ONE property: it may only ever waive a
homogeneous set. "Review all 41 missing punches" is a decision somebody can
defend afterwards ("the gate reader was down on Tuesday"). "Review all 66" is
not a decision at all. Everything below tests some form of that, plus the two
ways a batch silently lies: waiving rows the officer never saw, and reporting a
count that includes rows it could not write.
"""


from odoo.exceptions import AccessError, UserError

from odoo.tests import tagged

from .common import CloseCase


@tagged('post_install', '-at_install')
class TestBulkReview(CloseCase):

    def _week(self):
        return self.week_start.isoformat()

    def _seed_missing_punches(self, n):
        """`n` employees with a published shift and NO punch on the Monday —
        the cleanest `missing_punch` the classifier produces."""
        Emp = self.env['hr.employee']
        made = Emp.browse()
        for i in range(n):
            e = Emp.create({'name': 'P7 Ghost %02d' % i,
                            'company_id': self.company.id, 'tz': 'UTC'})
            self._shift(emp=e, day=self.day)
            made |= e
        return made

    # =================================================== grouping by kind
    def test_the_board_groups_flags_by_kind_with_counts(self):
        """The precondition for the batch: the officer has to be able to SEE a
        homogeneous set before being offered one action over it."""
        self._seed_missing_punches(3)
        # one unscheduled day: a punch with no shift behind it
        self._punch(emp=self.emp2, day=self.day2)
        data = self.env['pb.close'].get_close_data(week_start=self._week())
        kinds = {k['kind']: k for k in data['kinds']}
        self.assertIn('missing_punch', kinds)
        self.assertGreaterEqual(kinds['missing_punch']['open'], 3)
        self.assertIn('unscheduled_day', kinds)
        self.assertEqual(kinds['unscheduled_day']['open'], 1)
        for k in data['kinds']:
            self.assertEqual(k['total'], k['open'] + k['reviewed'])

    def test_the_kind_order_is_stable_rather_than_by_frequency(self):
        """A summary whose rows reorder between two visits is a summary nobody
        can learn. The order is `_KINDS`' own."""
        from odoo.addons.pb_close.models.close import _KINDS
        self._seed_missing_punches(2)
        self._punch(emp=self.emp2, day=self.day2)
        data = self.env['pb.close'].get_close_data(week_start=self._week())
        got = [k['kind'] for k in data['kinds']]
        expected = [k for k in _KINDS if k in got]
        self.assertEqual(got, expected)

    # ========================================================== the batch
    def test_review_all_waives_every_open_flag_of_one_kind(self):
        emps = self._seed_missing_punches(4)
        Close = self.env['pb.close']
        res = Close.review_kind('missing_punch', note='Gate reader was down',
                                week_start=self._week())
        self.assertEqual(res['reviewed'], 4)
        self.assertFalse(res['skipped'])
        reviews = self.env['pb.close.review'].search([
            ('employee_id', 'in', emps.ids), ('kind', '=', 'missing_punch')])
        self.assertEqual(len(reviews), 4)
        self.assertEqual(set(reviews.mapped('note')), {'Gate reader was down'},
                         'one note must reach every row of the batch')

    def test_it_never_touches_another_kind(self):
        """The whole premise. A batch that reached a second kind would be the
        "review all 66" button this design exists to refuse."""
        self._seed_missing_punches(2)
        self._punch(emp=self.emp2, day=self.day2)     # unscheduled_day
        Close = self.env['pb.close']
        Close.review_kind('missing_punch', note='x', week_start=self._week())
        data = Close.get_close_data(week_start=self._week())
        kinds = {k['kind']: k for k in data['kinds']}
        self.assertEqual(kinds['missing_punch']['open'], 0)
        self.assertEqual(kinds['unscheduled_day']['open'], 1,
                         'the batch reached a kind it was not asked about')

    def test_a_second_run_waives_nothing(self):
        """Idempotent for the same reason the single-row path is: the officer's
        second click is the same decision, and the unique constraint on
        (company, employee, day, kind) must not surface as an error."""
        self._seed_missing_punches(3)
        Close = self.env['pb.close']
        self.assertEqual(Close.review_kind('missing_punch', note='a',
                                           week_start=self._week())['reviewed'], 3)
        again = Close.review_kind('missing_punch', note='b',
                                  week_start=self._week())
        self.assertEqual(again['requested'], 0)
        self.assertEqual(again['reviewed'], 0)
        self.assertFalse(again['skipped'])

    def test_the_batch_waives_exactly_the_rows_the_board_showed(self):
        """The bug this shape prevents: a bulk action that rebuilds the set from
        its own domain waives rows the officer never saw, and nothing surfaces
        it. Both sides go through `_rows_for`, so the sets are the same object
        shape — asserted by counting one against the other under the SAME
        department filter."""
        emps = self._seed_missing_punches(3)
        dept = self.env['hr.department'].create({
            'name': 'P7 Scoped', 'company_id': self.company.id})
        emps[0].department_id = dept.id
        Close = self.env['pb.close']
        data = Close.get_close_data(department_id=dept.id, week_start=self._week())
        on_screen = [r for r in data['flagged'] if r['kind'] == 'missing_punch']
        self.assertEqual(len(on_screen), 1)
        res = Close.review_kind('missing_punch', note='scoped',
                                department_id=dept.id, week_start=self._week())
        self.assertEqual(res['reviewed'], 1,
                         'the batch stepped outside the department filter')
        # the other two are untouched
        left = Close.get_close_data(week_start=self._week())
        kinds = {k['kind']: k for k in left['kinds']}
        self.assertEqual(kinds['missing_punch']['open'], 2)

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(UserError):
            self.env['pb.close'].review_kind('not_a_kind', week_start=self._week())

    def test_a_batch_bigger_than_the_cap_is_refused_rather_than_truncated(self):
        """Silently doing 200 of 300 would be the worst outcome: the board would
        look almost clear and nobody would know which hundred were left."""
        from odoo.addons.pb_close.models import close as close_mod
        self._seed_missing_punches(3)
        with self.patch_cap(close_mod, 2):
            with self.assertRaises(UserError):
                self.env['pb.close'].review_kind('missing_punch',
                                                 week_start=self._week())
        # and nothing was written on the way to refusing
        self.assertFalse(self.env['pb.close.review'].search_count(
            [('kind', '=', 'missing_punch'), ('date', '=', self.day)]))

    def patch_cap(self, module, value):
        from unittest.mock import patch
        return patch.object(module, '_MAX_BULK', value)

    # ================================================ the self-review rule
    def test_the_no_self_review_rule_survives_the_batch(self):
        """It is enforced per ROW by the model, so a batch is exactly where it
        would be lost. The manager's own flag must be REFUSED and REPORTED —
        skipping it quietly would let somebody sign off on their own payslip
        inputs by using the bulk button instead of the single one."""
        mgr = self._manager('p7_selfmgr')
        me = self.env['hr.employee'].create({
            'name': 'P7 The Manager', 'company_id': self.company.id,
            'tz': 'UTC', 'user_id': mgr.id})
        self._shift(emp=me, day=self.day)              # my own missing punch
        others = self._seed_missing_punches(2)

        res = self.env['pb.close'].with_user(mgr).review_kind(
            'missing_punch', note='batch', week_start=self._week())
        self.assertEqual(res['reviewed'], 2, 'the two other rows must land')
        self.assertEqual(len(res['skipped']), 1,
                         'my own row must be refused, not waived')
        self.assertEqual(res['skipped'][0]['name'], 'P7 The Manager')
        self.assertIn('own', res['skipped'][0]['reason'].lower(),
                      "the model's own words must survive to the caller")
        self.assertEqual(res['requested'], 3,
                         'the count must include what it could not do')
        # proven in the DATABASE, not from the return value
        self.assertFalse(self.env['pb.close.review'].sudo().search_count(
            [('employee_id', '=', me.id)]))
        self.assertEqual(self.env['pb.close.review'].sudo().search_count(
            [('employee_id', 'in', others.ids)]), 2)

    def test_a_plain_officer_cannot_run_the_batch_at_all(self):
        """Waiving is the manager tier — the batch may not be a softer door
        than the single-row action it replaces (W31)."""
        self._seed_missing_punches(2)
        officer = self._officer('p7_plainofficer')
        with self.assertRaises(AccessError):
            self.env['pb.close'].with_user(officer).review_kind(
                'missing_punch', note='x', week_start=self._week())
        self.assertFalse(self.env['pb.close.review'].sudo().search_count(
            [('date', '=', self.day)]))

    # ============================================================= paging
    def test_the_table_pages_and_reports_true_totals(self):
        """W45. Three numbers, because a paged table can lie in two directions:
        the WEEK's total (what `can_lock` is about), the FILTERED total (what
        the chips select) and what is in this payload."""
        self._seed_missing_punches(30)
        Close = self.env['pb.close']
        p1 = Close.get_close_data(week_start=self._week())
        self.assertEqual(p1['page'], 1)
        self.assertGreaterEqual(p1['pages'], 2)
        self.assertEqual(p1['flagged_shown'], p1['page_size'])
        self.assertGreaterEqual(p1['flagged_total'], 30)
        self.assertEqual(p1['filtered_total'], p1['flagged_total'])

        p2 = Close.get_close_data(week_start=self._week(), page=2)
        self.assertEqual(p2['page'], 2)
        self.assertEqual(p2['flagged_total'], p1['flagged_total'],
                         'the true total must not depend on the page')
        ids1 = {(r['employee_id'], r['date'], r['kind']) for r in p1['flagged']}
        ids2 = {(r['employee_id'], r['date'], r['kind']) for r in p2['flagged']}
        self.assertFalse(ids1 & ids2, 'a row appeared on two pages')

    def test_a_page_past_the_end_lands_on_the_last_one(self):
        """Rather than an empty screen with no explanation."""
        self._seed_missing_punches(3)
        data = self.env['pb.close'].get_close_data(week_start=self._week(),
                                                   page=99)
        self.assertEqual(data['page'], data['pages'])
        self.assertTrue(data['flagged'])

    def test_a_junk_page_is_page_one(self):
        data = self.env['pb.close'].get_close_data(week_start=self._week(),
                                                   page='banana')
        self.assertEqual(data['page'], 1)

    # ============================================================ filters
    def test_the_kind_filter_narrows_the_table_only(self):
        """A filter is a way of LOOKING at a week; it must never change what the
        week is. The classic version of this bug: filter to one kind and watch
        "can lock" turn green."""
        self._seed_missing_punches(3)
        self._punch(emp=self.emp2, day=self.day2)     # unscheduled_day
        Close = self.env['pb.close']
        allrows = Close.get_close_data(week_start=self._week())
        narrowed = Close.get_close_data(week_start=self._week(),
                                        kind='unscheduled_day')
        self.assertEqual(narrowed['filtered_total'], 1)
        self.assertTrue(all(r['kind'] == 'unscheduled_day'
                            for r in narrowed['flagged']))
        self.assertEqual(narrowed['flagged_total'], allrows['flagged_total'],
                         'the WEEK total must not move when the table is filtered')
        self.assertEqual(narrowed['stats']['flagged'],
                         allrows['stats']['flagged'])
        self.assertEqual(narrowed['can_lock'], allrows['can_lock'],
                         'a filter must never unlock a week')
        self.assertEqual(narrowed['checklist'], allrows['checklist'])

    def test_the_reviewed_chip_selects_the_waived_rows(self):
        self._seed_missing_punches(3)
        Close = self.env['pb.close']
        Close.review_kind('missing_punch', note='ok', week_start=self._week())
        done = Close.get_close_data(week_start=self._week(), reviewed='done')
        self.assertEqual(done['filtered_total'], 3)
        self.assertTrue(all(r['reviewed'] for r in done['flagged']))
        openr = Close.get_close_data(week_start=self._week(), reviewed='open')
        self.assertEqual(openr['filtered_total'], 0)

    def test_the_default_payload_is_unchanged_for_a_caller_that_passes_nothing(self):
        """The three new arguments are additive — a client that has not been
        updated must get the board it always got."""
        self._seed_missing_punches(2)
        data = self.env['pb.close'].get_close_data(week_start=self._week())
        for key in ('week_start', 'days', 'stats', 'flagged', 'flagged_total',
                    'flagged_shown', 'handoff', 'checklist', 'can_lock',
                    'can_manage_locks', 'can_review', 'all_locked',
                    'headcount', 'truncated', 'tolerance'):
            self.assertIn(key, data, '%s disappeared from the payload' % key)
        self.assertEqual(data['filter_kind'], False)
        self.assertEqual(data['filter_reviewed'], False)
