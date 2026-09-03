# -*- coding: utf-8 -*-
"""FLEET P2B — the decisions a rollout makes, with no database in sight.

T1–T6. Everything a rollout DOES is a live-box act; everything it DECIDES is in
`rollout_rules.py`, and this is where the decisions are argued with. The two
that matter most are `next_window` (a wall clock in somebody else's country, in
a band that runs past midnight, on the two days a year the clocks move) and
`advance` (the whole state machine, every branch).
"""
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.rollout_rules import (
    CUSTOMER_RINGS, DEFAULT_LOG_IGNORE, RING_ORDER, advance, eligible,
    filter_errors, health_verdict, next_window, notice_for, parse_ignore,
    plan_tasks, watch_hours_for, window_bounds, window_open,
)

VN = 'Asia/Ho_Chi_Minh'          # UTC+7 all year, no daylight saving
NY = 'America/New_York'          # UTC-5 / UTC-4
LON = 'Europe/London'            # UTC+0 / UTC+1
SYD = 'Australia/Sydney'         # UTC+11 / UTC+10, southern hemisphere


def rel():
    return {'id': 1, 'name': '2026.09.03'}


def tenant(tid, name, slug, ring='everyone', state='live'):
    return {'id': tid, 'name': name, 'slug': slug, 'ring': ring, 'state': state}


@tagged('post_install', '-at_install')
class TestRolloutRules(TransactionCase):

    # ================================================================== T1
    def test_t1_01_the_practice_run_is_first_and_the_template_second(self):
        plan = plan_tasks(rel(), [tenant(2, 'AB Mauri', 'abm', 'canary')],
                          {'id': 2, 'name': 'AB Mauri', 'slug': 'abm'},
                          'payobook_template')
        rings = [t['ring'] for t in plan['tasks']]
        self.assertEqual(rings, ['rehearsal', 'template', 'canary'])
        self.assertEqual(plan['tasks'][0]['target_db'], 'abm-staging')
        self.assertEqual(plan['tasks'][1]['target_db'], 'payobook_template')
        self.assertEqual(plan['tasks'][2]['target_db'], 'abm')
        # The practice run is about a customer's DATA, not an update that
        # customer received: it must never land on their own timeline.
        self.assertIsNone(plan['tasks'][0]['tenant_id'])
        self.assertEqual(plan['tasks'][0]['source_tenant_id'], 2)

    def test_t1_02_customers_come_in_wave_order_then_by_name(self):
        plan = plan_tasks(rel(), [
            tenant(5, 'Zeta', 'zeta', 'everyone'),
            tenant(6, 'Alpha', 'alpha', 'everyone'),
            tenant(7, 'Canary Co', 'canaryco', 'canary'),
            tenant(8, 'Early Bird', 'early', 'early'),
        ], {'id': 7, 'name': 'Canary Co', 'slug': 'canaryco'})
        after = [t['label'] for t in plan['tasks'] if t['ring'] in CUSTOMER_RINGS]
        self.assertEqual(after, ['Canary Co', 'Early Bird', 'Alpha', 'Zeta'])

    def test_t1_03_a_closed_or_half_built_customer_is_left_out_with_a_reason(self):
        plan = plan_tasks(rel(), [
            tenant(1, 'Gone Ltd', 'gone', 'everyone', 'decommissioned'),
            tenant(2, 'Half Built', 'half', 'everyone', 'provisioning'),
            tenant(3, 'Draft Co', 'draft', 'everyone', 'draft'),
            tenant(4, 'Sick Co', 'sick', 'everyone', 'error'),
            tenant(9, 'Good Co', 'good', 'everyone', 'live'),
        ], None)
        touched = [t['tenant_id'] for t in plan['tasks'] if t['tenant_id']]
        self.assertEqual(touched, [9])
        self.assertEqual(len(plan['excluded']), 4)
        for row in plan['excluded']:
            self.assertTrue(row['reason'], "every exclusion says why")
        self.assertNotIn('Odoo', ' '.join(r['reason'] for r in plan['excluded']))

    def test_t1_04_no_customers_still_rehearses_and_does_the_template(self):
        plan = plan_tasks(rel(), [], None)
        self.assertEqual([t['ring'] for t in plan['tasks']], ['template'])
        self.assertTrue(any('practise' in w for w in plan['warnings']))

    def test_t1_05_no_canary_is_a_warning_not_a_refusal(self):
        plan = plan_tasks(rel(), [tenant(2, 'Only Co', 'only', 'everyone')],
                          {'id': 2, 'name': 'Only Co', 'slug': 'only'})
        self.assertTrue(any('canary' in w for w in plan['warnings']))
        self.assertEqual(len([t for t in plan['tasks'] if t['ring'] == 'everyone']), 1)

    def test_t1_06_an_unknown_wave_falls_into_everyone(self):
        plan = plan_tasks(rel(), [tenant(2, 'Odd Co', 'odd', 'platinum')], None)
        self.assertEqual([t['ring'] for t in plan['tasks'] if t['tenant_id']],
                         ['everyone'])

    # ================================================================== T2
    def test_t2_01_a_window_that_runs_past_midnight_wraps(self):
        # 22:00 Vietnam for three hours = 15:00–18:00 UTC.
        self.assertTrue(window_open(datetime(2026, 9, 3, 15, 30), VN, 22, 3))
        self.assertTrue(window_open(datetime(2026, 9, 3, 17, 59), VN, 22, 3))
        self.assertFalse(window_open(datetime(2026, 9, 3, 18, 1), VN, 22, 3))
        self.assertFalse(window_open(datetime(2026, 9, 3, 14, 59), VN, 22, 3))

    def test_t2_02_a_window_inside_one_day_does_not_wrap(self):
        self.assertTrue(window_open(datetime(2026, 9, 3, 3, 0), VN, 9, 4))   # 10:00 local
        self.assertFalse(window_open(datetime(2026, 9, 3, 7, 0), VN, 9, 4))  # 14:00 local

    def test_t2_03_next_window_is_now_when_it_is_already_open(self):
        now = datetime(2026, 9, 3, 16, 0)
        self.assertEqual(next_window(now, VN, 22, 3), now)

    def test_t2_04_next_window_is_tonight_or_tomorrow(self):
        # 08:00 UTC = 15:00 in Vietnam: tonight's 22:00 is still ahead.
        self.assertEqual(next_window(datetime(2026, 9, 3, 8, 0), VN, 22, 3),
                         datetime(2026, 9, 3, 15, 0))
        # 19:00 UTC = 02:00 the next day locally: the window has closed, so the
        # next one is that evening — NOT the day after.
        self.assertEqual(next_window(datetime(2026, 9, 3, 19, 0), VN, 22, 3),
                         datetime(2026, 9, 4, 15, 0))

    def test_t2_05_dst_spring_forward_new_york(self):
        """8 March 2026, 02:00 → 03:00 in New York.

        22:00 local is 03:00 UTC the next day in winter (UTC-5) and 02:00 UTC
        in summer (UTC-4). Asked on the evening the clocks go forward, the
        window must still open at 22:00 on the customer's own clock.
        """
        # Saturday 7 March, 18:00 UTC = 13:00 EST. Tonight's 22:00 EST = 03:00
        # UTC on the 8th, before the change at 07:00 UTC.
        self.assertEqual(next_window(datetime(2026, 3, 7, 18, 0), NY, 22, 3),
                         datetime(2026, 3, 8, 3, 0))
        # Sunday 8 March, 18:00 UTC = 14:00 EDT (clocks already forward).
        # Tonight's 22:00 EDT = 02:00 UTC on the 9th.
        self.assertEqual(next_window(datetime(2026, 3, 8, 18, 0), NY, 22, 3),
                         datetime(2026, 3, 9, 2, 0))

    def test_t2_06_dst_fall_back_london(self):
        """25 October 2026, 02:00 → 01:00 in London.

        22:00 BST is 21:00 UTC; 22:00 GMT is 22:00 UTC. The hour the clocks go
        back is the hour a naive "add a day" gets wrong, which is the case
        `next_window` re-states the wall clock for.
        """
        self.assertEqual(next_window(datetime(2026, 10, 24, 12, 0), LON, 22, 3),
                         datetime(2026, 10, 24, 21, 0))
        self.assertEqual(next_window(datetime(2026, 10, 25, 12, 0), LON, 22, 3),
                         datetime(2026, 10, 25, 22, 0))

    def test_t2_07_dst_southern_hemisphere_sydney(self):
        """Sydney goes the other way: forward in October, back in April."""
        # 3 April 2026 is still AEDT (UTC+11): 22:00 local = 11:00 UTC.
        self.assertEqual(next_window(datetime(2026, 4, 3, 6, 0), SYD, 22, 3),
                         datetime(2026, 4, 3, 11, 0))
        # 6 April 2026 is AEST (UTC+10): 22:00 local = 12:00 UTC.
        self.assertEqual(next_window(datetime(2026, 4, 6, 6, 0), SYD, 22, 3),
                         datetime(2026, 4, 6, 12, 0))

    def test_t2_08_an_unknown_zone_is_utc_rather_than_a_crash(self):
        self.assertEqual(next_window(datetime(2026, 9, 3, 8, 0),
                                     'Mars/Olympus_Mons', 22, 3),
                         datetime(2026, 9, 3, 22, 0))

    def test_t2_09_window_bounds_spans_the_whole_window(self):
        opens, closes = window_bounds(datetime(2026, 9, 3, 8, 0), VN, 22, 3)
        self.assertEqual(opens, datetime(2026, 9, 3, 15, 0))
        self.assertEqual(closes, datetime(2026, 9, 3, 18, 0))

    def test_t2_10_a_silly_window_is_clamped_not_obeyed(self):
        # 0 hours would be a window that never opens; 99 would be no window at
        # all. Both are clamped rather than left to stop the rollout.
        self.assertTrue(window_open(datetime(2026, 9, 3, 15, 30), VN, 22, 0))
        self.assertTrue(window_open(datetime(2026, 9, 3, 5, 0), VN, 22, 99))

    # ================================================================== T3
    def test_t3_01_run_now_beats_the_window(self):
        task = {'ring': 'everyone', 'run_now': True, 'tz': VN,
                'maintenance_start': 22, 'maintenance_hours': 3}
        self.assertTrue(eligible(task, datetime(2026, 9, 3, 8, 0)))

    def test_t3_02_the_practice_run_and_the_template_have_no_window(self):
        for ring in ('rehearsal', 'template'):
            self.assertTrue(eligible({'ring': ring, 'tz': VN}, datetime(2026, 9, 3, 8, 0)))

    def test_t3_03_a_customer_waits_for_their_own_night(self):
        task = {'ring': 'canary', 'run_now': False, 'tz': VN,
                'maintenance_start': 22, 'maintenance_hours': 3}
        self.assertFalse(eligible(task, datetime(2026, 9, 3, 8, 0)))
        self.assertTrue(eligible(task, datetime(2026, 9, 3, 16, 0)))

    # ================================================================== T4
    def test_t4_01_a_site_that_does_not_answer(self):
        ok, why = health_verdict(0, 0, [])
        self.assertFalse(ok)
        self.assertIn('did not answer', why)

    def test_t4_02_parts_that_did_not_load(self):
        ok, why = health_verdict(200, 2, [])
        self.assertFalse(ok)
        self.assertIn('2 parts', why)

    def test_t4_03_errors_in_the_log(self):
        ok, why = health_verdict(200, 0, ['a', 'b', 'c'])
        self.assertFalse(ok)
        self.assertIn('3 errors', why)

    def test_t4_04_one_of_each_reads_as_one(self):
        self.assertIn('1 part', health_verdict(200, 1, [])[1])
        self.assertIn('1 error', health_verdict(200, 0, ['a'])[1])

    def test_t4_05_healthy_says_nothing(self):
        ok, why = health_verdict(200, 0, [])
        self.assertTrue(ok)
        self.assertEqual(why, '')

    def test_t4_06_no_probe_is_not_a_failure(self):
        """The template has no address. That is not a customer being down."""
        ok, _why = health_verdict(None, 0, [])
        self.assertTrue(ok)

    def test_t4_07_could_not_tell_is_honest_and_still_passes(self):
        ok, why = health_verdict(200, -1, [])
        self.assertTrue(ok)
        self.assertIn('Could not tell', why)

    def test_t4_08_a_server_error_page_is_a_failure(self):
        ok, why = health_verdict(500, 0, [])
        self.assertFalse(ok)
        self.assertIn('500', why)

    def test_t4_10_a_line_that_always_fires_does_not_stop_a_rollout(self):
        """Found on the very first live rehearsal.

        A vendor module on this build writes one ERROR every time ANY database
        loads its registry, about a licence file that has never existed. It
        stopped a rollout whose copy was in perfect health. The lines are set
        aside, not deleted — they stay on the record where somebody can read
        them.
        """
        lines = [
            '2026-09-03 10:39:33 ERROR ...license_state: License check FAILED: missing',
            '2026-09-03 10:39:40 ERROR ...payslip: could not compute',
        ]
        kept, ignored = filter_errors(lines, DEFAULT_LOG_IGNORE)
        self.assertEqual(len(kept), 1)
        self.assertIn('payslip', kept[0])
        self.assertEqual(len(ignored), 1)
        # And with only the noise present, the verdict is healthy.
        self.assertTrue(health_verdict(200, 0, filter_errors(
            [lines[0]], DEFAULT_LOG_IGNORE)[0])[0])

    def test_t4_11_an_empty_ignore_list_ignores_nothing(self):
        lines = ['ERROR License check FAILED: missing']
        self.assertEqual(filter_errors(lines, [])[0], lines)
        self.assertEqual(filter_errors(lines, None)[0], lines)

    def test_t4_12_the_ignore_list_is_read_as_one_substring_per_line(self):
        self.assertEqual(parse_ignore("  one \n\n two  \n"), ['one', 'two'])
        self.assertEqual(parse_ignore(''), [])
        self.assertEqual(parse_ignore(None), list(DEFAULT_LOG_IGNORE))

    def test_t4_09_no_reason_mentions_the_framework(self):
        for args in ((0, 0, []), (200, 2, []), (200, 0, ['x']), (500, 0, [])):
            self.assertNotIn('Odoo', health_verdict(*args)[1])

    # ================================================================== T5
    def _snap(self, **kw):
        base = {
            'state': 'running', 'current_ring': 'rehearsal',
            'ring_done_at': None, 'watch_skipped': False,
            'watch_hours': {'canary': 24, 'early': 48},
            'watch_health': [],
            'tasks': [],
        }
        base.update(kw)
        return base

    def _task(self, ring, state='queued', **kw):
        t = {'id': kw.pop('id', 1), 'ring': ring, 'state': state,
             'run_now': False, 'label': kw.pop('label', ring.title()),
             'tz': VN, 'maintenance_start': 22, 'maintenance_hours': 3,
             'started_at': None, 'error': ''}
        t.update(kw)
        return t

    def test_t5_01_run_the_first_thing_that_may_run(self):
        snap = self._snap(tasks=[self._task('rehearsal', id=1),
                                 self._task('template', id=2)])
        kind, task = advance(snap, datetime(2026, 9, 3, 8, 0))
        self.assertEqual(kind, 'run')
        self.assertEqual(task['id'], 1)

    def test_t5_02_wait_until_the_customers_window_opens(self):
        snap = self._snap(current_ring='canary',
                          tasks=[self._task('canary', id=3)])
        kind, until = advance(snap, datetime(2026, 9, 3, 8, 0))
        self.assertEqual(kind, 'wait')
        self.assertEqual(until, datetime(2026, 9, 3, 15, 0))

    def test_t5_03_a_finished_wave_is_stamped_then_advanced(self):
        snap = self._snap(current_ring='rehearsal',
                          tasks=[self._task('rehearsal', 'done', id=1),
                                 self._task('template', id=2)])
        self.assertEqual(advance(snap, datetime(2026, 9, 3, 8, 0)),
                         ('ring_done', 'rehearsal'))
        snap['ring_done_at'] = datetime(2026, 9, 3, 8, 0)
        self.assertEqual(advance(snap, datetime(2026, 9, 3, 8, 1)),
                         ('advance_ring', 'template'))

    def test_t5_04_the_watch_period_holds_the_next_wave_back(self):
        done = datetime(2026, 9, 3, 8, 0)
        snap = self._snap(current_ring='canary', ring_done_at=done,
                          tasks=[self._task('canary', 'done', id=3),
                                 self._task('everyone', id=4)])
        kind, until = advance(snap, done + timedelta(hours=7))
        self.assertEqual(kind, 'wait')
        self.assertEqual(until, done + timedelta(hours=24))
        self.assertEqual(advance(snap, done + timedelta(hours=25)),
                         ('advance_ring', 'everyone'))

    def test_t5_05_continue_now_ends_the_watch_period(self):
        done = datetime(2026, 9, 3, 8, 0)
        snap = self._snap(current_ring='canary', ring_done_at=done,
                          watch_skipped=True,
                          tasks=[self._task('canary', 'done', id=3),
                                 self._task('everyone', id=4)])
        self.assertEqual(advance(snap, done + timedelta(minutes=1)),
                         ('advance_ring', 'everyone'))

    def test_t5_06_a_failed_task_stops_everything(self):
        snap = self._snap(current_ring='canary',
                          tasks=[self._task('canary', 'failed', id=3,
                                            error='The site did not answer.'),
                                 self._task('everyone', id=4)])
        kind, why = advance(snap, datetime(2026, 9, 3, 16, 0))
        self.assertEqual(kind, 'pause')
        self.assertIn('did not answer', why)

    def test_t5_07_a_customer_that_goes_quiet_during_the_watch_stops_it(self):
        done = datetime(2026, 9, 3, 8, 0)
        snap = self._snap(current_ring='canary', ring_done_at=done,
                          watch_health=[{'name': 'AB Mauri', 'ok': False,
                                         'reason': 'The site did not answer.'}],
                          tasks=[self._task('canary', 'done', id=3),
                                 self._task('everyone', id=4)])
        kind, why = advance(snap, done + timedelta(hours=2))
        self.assertEqual(kind, 'pause')
        self.assertIn('AB Mauri', why)

    def test_t5_08_everything_done_is_done(self):
        snap = self._snap(current_ring='everyone', ring_done_at=datetime(2026, 9, 3, 8, 0),
                          tasks=[self._task('rehearsal', 'done', id=1),
                                 self._task('template', 'done', id=2),
                                 self._task('everyone', 'done', id=4)])
        self.assertEqual(advance(snap, datetime(2026, 9, 3, 9, 0)), ('done',))

    def test_t5_09_a_skipped_customer_does_not_hold_the_wave_up(self):
        snap = self._snap(current_ring='canary',
                          tasks=[self._task('canary', 'skipped', id=3),
                                 self._task('everyone', id=4)])
        self.assertEqual(advance(snap, datetime(2026, 9, 3, 8, 0))[0], 'ring_done')

    def test_t5_10_a_task_left_running_for_ever_stops_the_rollout(self):
        started = datetime(2026, 9, 3, 8, 0)
        snap = self._snap(current_ring='canary',
                          tasks=[self._task('canary', 'running', id=3,
                                            started_at=started,
                                            label='AB Mauri')])
        kind, until = advance(snap, started + timedelta(minutes=10))
        self.assertEqual(kind, 'wait')
        self.assertLessEqual(until, started + timedelta(minutes=15))
        kind, why = advance(snap, started + timedelta(hours=3))
        self.assertEqual(kind, 'pause')
        self.assertIn('AB Mauri', why)

    def test_t5_11_an_empty_wave_is_stepped_over(self):
        snap = self._snap(current_ring='canary',
                          tasks=[self._task('everyone', id=4)])
        self.assertEqual(advance(snap, datetime(2026, 9, 3, 8, 0)),
                         ('advance_ring', 'everyone'))

    def test_t5_12_a_rollout_with_no_tasks_is_finished(self):
        self.assertEqual(advance(self._snap(), datetime(2026, 9, 3, 8, 0)),
                         ('done',))

    def test_t5_13_run_now_pulls_a_customer_out_of_their_window(self):
        snap = self._snap(current_ring='canary',
                          tasks=[self._task('canary', id=3, run_now=True)])
        kind, task = advance(snap, datetime(2026, 9, 3, 8, 0))
        self.assertEqual(kind, 'run')
        self.assertEqual(task['id'], 3)

    def test_t5_14_the_practice_run_and_template_never_wait(self):
        self.assertEqual(watch_hours_for('rehearsal'), 0)
        self.assertEqual(watch_hours_for('template'), 0)
        self.assertEqual(watch_hours_for('canary', {'canary': 6}), 6)
        self.assertEqual(watch_hours_for('early'), 48)

    def test_t5_15_the_waves_are_in_the_order_that_makes_them_safe(self):
        self.assertEqual(RING_ORDER,
                         ('rehearsal', 'template', 'canary', 'early', 'everyone'))

    # ================================================================== T6
    def test_t6_01_the_warning_names_the_window(self):
        n = notice_for('pre', '2026-09-03 15:00:00', '2026-09-03 18:00:00', 'x1')
        self.assertEqual(n['kind'], 'maintenance')
        self.assertEqual(n['id'], 'x1')
        self.assertIn('Payobook', n['title'])
        self.assertEqual(n['starts_at'], '2026-09-03 15:00:00')
        self.assertEqual(n['ends_at'], '2026-09-03 18:00:00')

    def test_t6_02_the_in_progress_message_has_no_window(self):
        n = notice_for('now', notice_id='x2')
        self.assertIn('right now', n['title'])
        self.assertEqual(n['starts_at'], '')
        self.assertEqual(n['ends_at'], '')

    def test_t6_05_only_the_in_progress_message_cannot_be_hidden(self):
        """The bar a reader may not close is the one explaining a pause."""
        self.assertTrue(notice_for('now', notice_id='a').get('live'))
        self.assertFalse(notice_for('pre', '2026-09-03 15:00:00',
                                    '2026-09-03 18:00:00', 'b').get('live'))

    def test_t6_03_neither_message_says_odoo_or_talks_like_a_computer(self):
        for n in (notice_for('pre', '2026-09-03 15:00:00', '2026-09-03 18:00:00', 'a'),
                  notice_for('now', notice_id='b')):
            blob = n['title'] + ' ' + n['text']
            self.assertNotIn('Odoo', blob)
            for word in ('database', 'module', 'registry', 'parameter'):
                self.assertNotIn(word, blob.lower())

    def test_t6_04_there_are_only_two_kinds(self):
        with self.assertRaises(ValueError):
            notice_for('something-else')
