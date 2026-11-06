# -*- coding: utf-8 -*-
"""FLEET P2A — composing a notice, and choosing what a customer gets to read.

T4 and T5. Both are pure functions with no database in them at all (rail R6),
which is what lets them be asserted on the shapes that actually go wrong: a
window that ends before it starts, a title long enough to wrap the bar, two
releases cut on the same day.
"""
from datetime import datetime

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.tenancy_rules import (
    MAX_TEXT, MAX_TITLE, default_window, notice_payload, parse_stamp,
    releases_list, render_range,
)


@tagged('post_install', '-at_install')
class TestNoticePayload(TransactionCase):
    """T4 — what may be put on a customer's screen, and what may not."""

    def _ok(self, **kw):
        args = dict(kind='maintenance', title="Update tonight", text="Short pause.",
                    starts_at='2026-09-03 22:00:00', ends_at='2026-09-04 01:00:00',
                    notice_id='abc123')
        args.update(kw)
        return notice_payload(**args)

    def test_t4_01_a_good_message_comes_back_whole(self):
        p = self._ok()
        self.assertEqual(p['kind'], 'maintenance')
        self.assertEqual(p['title'], "Update tonight")
        self.assertEqual(p['starts_at'], '2026-09-03 22:00:00')
        self.assertEqual(p['ends_at'], '2026-09-04 01:00:00')
        self.assertEqual(p['id'], 'abc123')

    def test_t4_02_a_title_is_required(self):
        for bad in ('', '   ', None):
            with self.assertRaises(ValueError):
                self._ok(title=bad)

    def test_t4_03_the_end_must_follow_the_start(self):
        with self.assertRaises(ValueError):
            self._ok(starts_at='2026-09-04 01:00:00', ends_at='2026-09-03 22:00:00')
        with self.assertRaises(ValueError):
            self._ok(starts_at='2026-09-03 22:00:00', ends_at='2026-09-03 22:00:00')

    def test_t4_04_the_kind_is_one_of_two(self):
        for bad in ('', 'urgent', 'MAINTENANCE', None):
            with self.assertRaises(ValueError):
                self._ok(kind=bad)
        self.assertEqual(self._ok(kind='info')['kind'], 'info')

    def test_t4_05_a_message_without_a_window_is_allowed(self):
        p = self._ok(starts_at='', ends_at='')
        self.assertEqual(p['starts_at'], '')
        self.assertEqual(p['ends_at'], '')

    def test_t4_06_the_title_has_to_fit_on_the_bar(self):
        with self.assertRaises(ValueError):
            self._ok(title='x' * (MAX_TITLE + 1))
        with self.assertRaises(ValueError):
            self._ok(text='x' * (MAX_TEXT + 1))

    def test_t4_07_it_needs_an_identity(self):
        with self.assertRaises(ValueError):
            self._ok(notice_id='')

    def test_t4_08_the_browsers_own_date_shape_is_accepted(self):
        p = self._ok(starts_at='2026-09-03T22:00', ends_at='2026-09-04T01:00')
        self.assertEqual(p['starts_at'], '2026-09-03 22:00:00')
        self.assertEqual(p['ends_at'], '2026-09-04 01:00:00')

    def test_t4_09_nonsense_in_a_date_box_is_refused_not_guessed(self):
        with self.assertRaises(ValueError):
            parse_stamp('next tuesday')

    def test_t4_10_the_composer_opens_on_a_sensible_six_hours(self):
        starts, ends = default_window(datetime(2026, 9, 3, 14, 5, 31))
        self.assertEqual(starts, '2026-09-03 14:05:00')
        self.assertEqual(ends, '2026-09-03 20:05:00')


@tagged('post_install', '-at_install')
class TestRenderRange(TransactionCase):
    """T4 — the window as a phrase, which is the only form anybody reads."""

    NOW = datetime(2026, 9, 3, 15, 0, 0)

    def test_t4_11_this_evening_is_tonight(self):
        self.assertEqual(
            render_range('2026-09-03 22:00:00', '2026-09-04 01:00:00', self.NOW),
            "tonight 22:00–01:00")

    def test_t4_12_earlier_the_same_day_is_today(self):
        self.assertEqual(
            render_range('2026-09-03 09:00:00', '2026-09-03 11:00:00', self.NOW),
            "today 09:00–11:00")

    def test_t4_13_the_next_day_is_tomorrow(self):
        self.assertEqual(
            render_range('2026-09-04 22:00:00', '2026-09-05 01:00:00', self.NOW),
            "tomorrow 22:00–01:00")

    def test_t4_14_further_out_names_the_days(self):
        self.assertEqual(
            render_range('2026-09-10 22:00:00', '2026-09-11 01:00:00', self.NOW),
            "Thu 22:00 – Fri 01:00")

    def test_t4_15_no_window_at_all_is_an_empty_string(self):
        self.assertEqual(render_range('', '', self.NOW), '')

    def test_t4_16_an_open_ended_window_still_says_something(self):
        self.assertEqual(render_range('2026-09-03 22:00:00', '', self.NOW),
                         "from 22:00 today")


@tagged('post_install', '-at_install')
class TestReleasesList(TransactionCase):
    """T5 — which ten releases a customer's What's new page carries."""

    @staticmethod
    def _rows(n, notes=''):
        return [{'name': '2026.08.%02d' % (i + 1),
                 'date': '2026-08-%02d' % (i + 1),
                 'notes': notes} for i in range(n)]

    def test_t5_01_ten_at_most_newest_first(self):
        out = releases_list(self._rows(14))
        self.assertEqual(len(out), 10)
        self.assertEqual(out[0]['name'], '2026.08.14')
        self.assertEqual(out[-1]['name'], '2026.08.05')

    def test_t5_02_notes_are_trimmed_and_always_present(self):
        out = releases_list([{'name': '2026.09.03', 'date': '2026-09-03',
                              'notes': '  hello \n'}])
        self.assertEqual(out[0]['notes'], 'hello')
        out = releases_list([{'name': '2026.09.03', 'date': '2026-09-03'}])
        self.assertEqual(out[0]['notes'], '')

    def test_t5_03_two_cut_on_one_day_come_out_in_order(self):
        out = releases_list([
            {'name': '2026.09.03', 'date': '2026-09-03'},
            {'name': '2026.09.03-2', 'date': '2026-09-03'},
        ])
        self.assertEqual([r['name'] for r in out],
                         ['2026.09.03-2', '2026.09.03'])

    def test_t5_04_rubbish_in_the_list_is_dropped_not_crashed_on(self):
        out = releases_list([None, 'x', {}, {'name': ''},
                             {'name': '2026.09.03', 'date': '2026-09-03'}])
        self.assertEqual(len(out), 1)

    def test_t5_05_nothing_at_all_is_an_empty_list(self):
        self.assertEqual(releases_list(None), [])
        self.assertEqual(releases_list([]), [])
