# -*- coding: utf-8 -*-
"""FLEET P1 — the drift decisions, tested where they can be reached.

Everything the sync feature DOES happens on another database of the cluster and
cannot be exercised from a suite (rail R6). So every judgement it makes is a
pure function in `models/sync_rules.py`, and this file is a real test of each.

The bug this whole phase exists for is T1's subject: versions were never
compared at all, so a customer two versions behind on something it already had
was reported "in step", in green, on the screen whose only job is to say
otherwise.
"""
from datetime import date

from odoo.tests.common import TransactionCase, tagged

from ..models.sync_rules import (master_behind_files, norm_version,
                                 release_name, release_state, sync_diff,
                                 sync_split, template_cron_plan)


@tagged('post_install', '-at_install')
class TestNormVersion(TransactionCase):
    """T1 — one version string, two databases, one comparable answer."""

    def test_t1_01_the_series_prefix_is_stripped_and_the_rest_is_not(self):
        self.assertEqual(norm_version('19.0.1.7.0'), norm_version('1.7.0'))
        self.assertEqual(norm_version('19.0.1.7.0'), (1, 7, 0))

    def test_t1_02_a_short_version_keeps_all_of_its_parts(self):
        """Four parts or fewer is nobody's series prefix."""
        self.assertEqual(norm_version('1.7.0'), (1, 7, 0))
        self.assertEqual(norm_version('1.2.3.4'), (1, 2, 3, 4))

    def test_t1_03_ten_is_bigger_than_nine(self):
        """The failure text comparison makes, silently."""
        self.assertGreater(norm_version('1.10.0'), norm_version('1.9.0'))
        self.assertGreater(norm_version('19.0.1.10.0'), norm_version('19.0.1.9.0'))
        self.assertGreater(norm_version('19.0.1.10.0'), norm_version('1.9.0'))

    def test_t1_04_a_release_candidate_is_answered_not_crashed(self):
        self.assertEqual(norm_version('19.0.1.7.0-rc1'), (1, 7, 0))
        self.assertEqual(norm_version('1.7.x'), (1, 7, 0))

    def test_t1_05_nothing_at_all_is_the_oldest_thing_there_is(self):
        for empty in (None, '', '   ', False):
            self.assertEqual(norm_version(empty), (0,))
        self.assertLess(norm_version(''), norm_version('0.0.1'))


@tagged('post_install', '-at_install')
class TestSyncDiff(TransactionCase):
    """T2 — what to add, what to move up, what never goes, what to leave."""

    MASTER = {'pb_assets': '19.0.1.2.0', 'pb_budget': '19.0.2.0.0',
              'hr': '19.0.1.0.0', 'pb_tenants': '19.0.1.4.0',
              'pb_demo': '19.0.1.0.0'}

    def test_t2_01_missing_parts_are_offered(self):
        d = sync_diff(self.MASTER, {'hr': '19.0.1.0.0'})
        self.assertEqual(d['to_install'], ['pb_assets', 'pb_budget'])

    def test_t2_02_an_older_version_of_something_it_has_is_an_update(self):
        d = sync_diff(self.MASTER, {'hr': '19.0.1.0.0',
                                    'pb_assets': '19.0.1.1.0',
                                    'pb_budget': '19.0.2.0.0'})
        self.assertEqual(d['to_install'], [])
        self.assertEqual(d['to_update'], [{'module': 'pb_assets',
                                           'have': '19.0.1.1.0',
                                           'want': '19.0.1.2.0'}])

    def test_t2_03_the_two_sides_may_write_the_version_differently(self):
        """The master says `19.0.1.2.0`, the customer says `1.2.0`. Same thing."""
        d = sync_diff({'pb_assets': '19.0.1.2.0'}, {'pb_assets': '1.2.0'})
        self.assertEqual(d['to_update'], [])
        self.assertEqual(d['ahead'], [])

    def test_t2_04_a_part_it_never_gets_is_held_back_from_both_lists(self):
        """Present on the master, and stale on the customer — still held back."""
        d = sync_diff(self.MASTER, {'pb_tenants': '19.0.1.0.0'})
        self.assertIn('pb_tenants', d['held_back'])
        self.assertIn('pb_demo', d['held_back'])
        self.assertNotIn('pb_tenants', [r['module'] for r in d['to_update']])
        self.assertNotIn('pb_tenants', d['to_install'])

    def test_t2_05_newer_on_the_customer_is_reported_and_left_alone(self):
        d = sync_diff({'pb_assets': '19.0.1.2.0'}, {'pb_assets': '19.0.1.9.0'})
        self.assertEqual(d['to_update'], [])
        self.assertEqual(d['ahead'], [{'module': 'pb_assets',
                                       'have': '19.0.1.9.0',
                                       'want': '19.0.1.2.0'}])

    def test_t2_06_something_only_the_customer_has_is_not_our_business(self):
        d = sync_diff({'hr': '1.0'}, {'hr': '1.0', 'their_own_thing': '1.0'})
        self.assertEqual(d['to_install'], [])
        self.assertEqual(d['to_update'], [])
        self.assertEqual(d['ahead'], [])
        self.assertEqual(d['held_back'], [])

    def test_t2_07_a_future_platform_part_is_refused_by_default(self):
        d = sync_diff({'pb_platform_billing': '1.0', 'pb_pip': '1.0'}, {})
        self.assertEqual(d['to_install'], ['pb_pip'])
        self.assertEqual(d['held_back'], ['pb_platform_billing'])

    def test_t2_08_every_list_comes_back_sorted_and_they_never_overlap(self):
        d = sync_diff(self.MASTER, {'pb_assets': '19.0.1.0.0'})
        self.assertEqual(d['to_install'], sorted(d['to_install']))
        self.assertEqual(d['held_back'], sorted(d['held_back']))
        names = set(d['to_install']) | {r['module'] for r in d['to_update']}
        self.assertFalse(names & set(d['held_back']))

    def test_t2_09_bare_lists_of_names_are_still_answered(self):
        d = sync_diff(['a', 'b'], ['a'])
        self.assertEqual(d['to_install'], ['b'])
        self.assertEqual(d['to_update'], [])

    def test_t2_10_the_old_split_still_answers_exactly_as_it_did(self):
        """T7's other half: `sync_split` is now a wrapper and must not drift."""
        self.assertEqual(sync_split(['pb_tenants', 'pb_assets'], []),
                         (['pb_assets'], ['pb_tenants']))
        self.assertEqual(sync_split(None, None), ([], []))


@tagged('post_install', '-at_install')
class TestReleaseState(TransactionCase):
    """T3 — on the release, behind it, or nowhere near it."""

    SNAP = {'a': '19.0.1.0.0', 'b': '19.0.2.0.0', 'c': '19.0.1.0.0',
            'd': '19.0.1.0.0', 'pb_tenants': '19.0.1.4.0'}

    def test_t3_01_everything_present_at_the_right_version_is_on(self):
        self.assertEqual(release_state(self.SNAP, dict(self.SNAP)), 'on')

    def test_t3_02_one_older_part_is_behind(self):
        have = dict(self.SNAP, b='19.0.1.0.0')
        self.assertEqual(release_state(self.SNAP, have), 'behind')

    def test_t3_03_one_missing_part_is_behind(self):
        have = {k: v for k, v in self.SNAP.items() if k != 'd'}
        self.assertEqual(release_state(self.SNAP, have), 'behind')

    def test_t3_04_a_database_that_has_almost_none_of_it_is_not_on_a_release(self):
        self.assertEqual(release_state(self.SNAP, {'a': '19.0.1.0.0'}), 'none')
        self.assertEqual(release_state(self.SNAP, {}), 'none')

    def test_t3_05_the_parts_a_customer_never_gets_do_not_count(self):
        """The photograph shows the whole master; the measure ignores our own."""
        have = {k: v for k, v in self.SNAP.items() if k != 'pb_tenants'}
        self.assertEqual(release_state(self.SNAP, have), 'on')

    def test_t3_06_newer_than_the_release_is_still_on_it(self):
        have = dict(self.SNAP, b='19.0.9.0.0')
        self.assertEqual(release_state(self.SNAP, have), 'on')

    def test_t3_07_an_empty_photograph_answers_none_rather_than_on(self):
        self.assertEqual(release_state({}, {'a': '1.0'}), 'none')


@tagged('post_install', '-at_install')
class TestMasterBehindFiles(TransactionCase):
    """T4 — rail R3: has the master applied what is on its own disk?"""

    def test_t4_01_equal_after_normalising_is_empty(self):
        rows = [('pb_assets', '19.0.1.7.0', '1.7.0'),
                ('hr', '19.0.1.0.0', '19.0.1.0.0')]
        self.assertEqual(master_behind_files(rows), [])

    def test_t4_02_a_newer_file_is_named(self):
        rows = [('pb_assets', '19.0.1.6.0', '1.7.0'),
                ('hr', '19.0.1.0.0', '1.0.0')]
        self.assertEqual(master_behind_files(rows), ['pb_assets'])

    def test_t4_03_a_file_that_could_not_be_read_is_not_an_accusation(self):
        self.assertEqual(master_behind_files([('gone', '19.0.1.6.0', '')]), [])

    def test_t4_04_a_master_ahead_of_its_files_is_not_behind_them(self):
        self.assertEqual(master_behind_files([('x', '19.0.2.0.0', '1.0.0')]), [])

    def test_t4_05_nothing_in_nothing_out(self):
        self.assertEqual(master_behind_files([]), [])
        self.assertEqual(master_behind_files(None), [])


@tagged('post_install', '-at_install')
class TestReleaseName(TransactionCase):
    """T5 — dated names, and a suffix when two are cut on one day."""

    def test_t5_01_the_first_one_of_the_day_is_the_bare_date(self):
        self.assertEqual(release_name(date(2026, 9, 3), []), '2026.09.03')

    def test_t5_02_the_second_gets_a_suffix_and_the_third_the_next_one(self):
        self.assertEqual(release_name(date(2026, 9, 3), ['2026.09.03']),
                         '2026.09.03-2')
        self.assertEqual(
            release_name(date(2026, 9, 3), ['2026.09.03', '2026.09.03-2']),
            '2026.09.03-3')

    def test_t5_03_other_days_do_not_get_in_the_way(self):
        self.assertEqual(release_name(date(2026, 9, 3), ['2026.09.02']),
                         '2026.09.03')

    def test_t5_04_single_digit_months_and_days_are_padded(self):
        self.assertEqual(release_name(date(2026, 1, 5), []), '2026.01.05')


@tagged('post_install', '-at_install')
class TestTemplateCronPlan(TransactionCase):
    """T6 — rail R8: the golden template never keeps a running job."""

    def test_t6_01_a_first_pass_records_and_switches_off_everything(self):
        to_disable, param = template_cron_plan([3, 1, 2], '')
        self.assertEqual(to_disable, [3, 1, 2])
        self.assertEqual(param, '3,1,2')

    def test_t6_02_what_is_already_written_down_is_not_written_twice(self):
        to_disable, param = template_cron_plan([2, 5], '1,2')
        self.assertEqual(param, '1,2,5')
        self.assertIn(2, to_disable)   # written down, but running again: off it goes

    def test_t6_03_the_order_of_the_written_list_is_preserved(self):
        _off, param = template_cron_plan([9], '7,3,1')
        self.assertEqual(param, '7,3,1,9')

    def test_t6_04_nothing_active_leaves_the_written_list_untouched(self):
        to_disable, param = template_cron_plan([], '4,6')
        self.assertEqual(to_disable, [])
        self.assertEqual(param, '4,6')

    def test_t6_05_rubbish_in_the_written_list_is_ignored_not_repeated(self):
        _off, param = template_cron_plan([8], ' 4 , , x , 6 ')
        self.assertEqual(param, '4,6,8')

    def test_t6_06_the_same_job_twice_in_one_pass_is_one_entry(self):
        to_disable, param = template_cron_plan([5, 5], '')
        self.assertEqual(to_disable, [5])
        self.assertEqual(param, '5')
