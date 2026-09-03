# -*- coding: utf-8 -*-
"""FLEET P2B — the rollout, driven end to end with the live box taken out.

T7 and T8. Everything that touches another database is replaced here by
something that answers instantly, which leaves the orchestration itself exposed:
the refusals, the list of tasks a Start writes down, the worker walking a whole
rollout from the practice run to "finished", a failure stopping it with a
sentence, a retry putting it back, and calling the whole thing off.

`_run_unit` is the seam the spec asks for: the one method that reaches P1's
"bring one database in step". Replace it and the entire machine runs in a
transaction.
"""
import inspect
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models import rollout_service

FAKE_RESULT = {
    'installed': [{'module': 'pb_tenancy', 'label': 'Platform Link'}],
    'updated': [], 'skipped_count': 0, 'skipped': [],
    'release_state': 'on', 'installed_after': 224, 'log': [],
    'message': '1 added, 0 brought up to date. Nothing was skipped.',
}


@tagged('post_install', '-at_install')
class TestRollout(TransactionCase):

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        self.cls = type(self.svc)
        self.rel = self.env['pb.release'].sudo().create({
            'name': 'TEST.2026.09.03', 'captured_at': fields.Datetime.now(),
            'notes': 'Payobook now tells you before an update.',
            'snapshot': '{"web": "19.0.1.0"}', 'module_count': 1,
        })
        self.rel.make_current()
        self.canary = self.env['pb.tenant'].sudo().create({
            'name': 'Canary Co', 'slug': 'canaryco2026', 'state': 'live',
            'ring': 'canary'})
        self.rest = self.env['pb.tenant'].sudo().create({
            'name': 'Rest Co', 'slug': 'restco2026', 'state': 'live',
            'ring': 'everyone'})
        # Every window wide open, so the state machine is exercised rather than
        # the clock. The windows themselves are argued with in T2/T3.
        self.env['pb.tenant'].sudo().search([]).write(
            {'maintenance_start': 0, 'maintenance_hours': 24})

    # ----------------------------------------------------------- the harness
    def _patches(self, unit=None, health=None):
        """Everything that would need another database, answered instantly."""
        unit = unit or (lambda self_, target: dict(FAKE_RESULT))
        health = health or (lambda self_, db, since, skipped, host=None:
                            {'ok': True, 'reason': '', 'probe_code': 200,
                             'skipped': 0, 'errors': [], 'error_count': 0})
        return [
            patch.object(self.cls, '_run_unit', unit),
            patch.object(self.cls, '_health_gate', health),
            patch.object(self.cls, 'restore_staging',
                         lambda self_, tid, bid=None: {'from_backup': 'x.zip'}),
            patch.object(self.cls, 'drop_staging', lambda self_, tid: {}),
            patch.object(self.cls, 'notice_send',
                         lambda self_, *a, **kw: {'sent': ['x'], 'skipped': [],
                                                  'message': ''}),
            patch.object(self.cls, 'notice_clear',
                         lambda self_, t: {'cleared': ['x'], 'skipped': []}),
            patch.object(self.cls, '_template_cron_state', lambda self_: (0, 52)),
            patch.object(self.cls, '_push_release_stamp',
                         lambda self_, *a, **kw: None),
            patch.object(self.cls, '_tenancy_installed', lambda self_, db: True),
            patch.object(self.cls, '_master_behind_files',
                         lambda self_, master=None: []),
            patch.object(self.cls, '_tenant_tz', lambda self_, t: 'UTC'),
            patch.object(self.cls, '_rehearsal_source',
                         lambda self_: {'id': self.canary.id,
                                        'name': self.canary.name,
                                        'slug': self.canary.slug}),
            patch.object(self.cls, '_probe', lambda self_, host: (200, 12)),
        ]

    def _run(self, fn, unit=None, health=None):
        ps = self._patches(unit, health)
        for p in ps:
            p.start()
        try:
            return fn()
        finally:
            for p in reversed(ps):
                p.stop()

    def _rollout(self):
        return self.env['pb.rollout'].sudo().search(
            [('release_id', '=', self.rel.id)], limit=1)

    # ================================================================== T7
    def test_t7_01_a_release_with_no_notes_is_refused(self):
        self.rel.notes = ''
        with self.assertRaises(UserError) as e:
            self._run(lambda: self.svc.rollout_start(self.rel.id))
        self.assertIn('what changed', str(e.exception))

    def test_t7_02_a_master_behind_its_own_files_is_refused(self):
        def go():
            with patch.object(self.cls, '_master_behind_files',
                              lambda self_, master=None: ['pb_settings']):
                self.svc.rollout_start(self.rel.id)
        with self.assertRaises(UserError) as e:
            self._run(go)
        self.assertIn('its own files', str(e.exception))

    def test_t7_03_a_customer_with_no_platform_link_is_named(self):
        def go():
            with patch.object(self.cls, '_tenancy_installed',
                              lambda self_, db: db != 'canaryco2026'):
                self.svc.rollout_start(self.rel.id)
        with self.assertRaises(UserError) as e:
            self._run(go)
        self.assertIn('Canary Co', str(e.exception))

    def test_t7_04_a_second_rollout_is_refused_while_one_is_going(self):
        self.env['pb.rollout'].sudo().create({
            'release_id': self.rel.id, 'state': 'waiting'})
        with self.assertRaises(UserError) as e:
            self._run(lambda: self.svc.rollout_start(self.rel.id))
        self.assertIn('already going out', str(e.exception))

    def test_t7_05_start_writes_down_every_task_in_order(self):
        def go():
            # The unit refuses to actually do anything: we only want the list.
            with patch.object(self.cls, '_rollout_tick',
                              lambda self_, r: {'ok': True}):
                self.svc.rollout_start(self.rel.id)
        self._run(go)
        r = self._rollout()
        self.assertTrue(r)
        rings = [t.ring for t in r.task_ids]
        self.assertEqual(rings[:2], ['rehearsal', 'template'])
        self.assertIn('canary', rings)
        self.assertIn('everyone', rings)
        rehearsal = r.task_ids[0]
        self.assertEqual(rehearsal.target_db, 'canaryco2026-staging')
        self.assertFalse(rehearsal.tenant_id)
        self.assertEqual(rehearsal.source_tenant_id, self.canary)
        self.assertEqual(r.state, 'running')
        self.assertEqual(r.started_by, self.env.user)

    def test_t7_06_the_worker_walks_a_whole_rollout_to_finished(self):
        """No watch period, so one Start drives it all the way through."""
        self._run(lambda: self.svc.rollout_start(self.rel.id, 0, 0))
        r = self._rollout()
        self.assertEqual(r.state, 'done', r.reason or '')
        self.assertTrue(r.finished_at)
        self.assertEqual(r.failed_count, 0)
        self.assertEqual(r.done_count, r.task_count)
        self.assertEqual(r.customer_done, 2)
        for t in r.task_ids:
            self.assertEqual(t.state, 'done')
            self.assertEqual(t.attempts, 1)
            self.assertTrue(t.result)
            self.assertGreaterEqual(t.duration_s, 0)

    def test_t7_07_the_watch_period_holds_it_at_the_canary(self):
        self._run(lambda: self.svc.rollout_start(self.rel.id, 24, 48))
        r = self._rollout()
        self.assertEqual(r.state, 'waiting')
        self.assertEqual(r.current_ring, 'canary')
        self.assertTrue(r.ring_done_at)
        rest = r.task_ids.filtered(lambda t: t.ring == 'everyone')
        self.assertEqual(rest.state, 'queued')

    def test_t7_08_continue_now_ends_the_watch_and_finishes_it(self):
        self._run(lambda: self.svc.rollout_start(self.rel.id, 24, 48))
        r = self._rollout()
        self.assertEqual(r.state, 'waiting')
        self._run(lambda: self.svc.rollout_continue_now(r.id))
        self.assertEqual(r.state, 'done', r.reason or '')
        self.assertTrue(any('watch period' in row['line']
                            for row in r.log_rows()))

    def test_t7_09_a_failure_stops_it_with_a_sentence_a_person_can_read(self):
        bad = (lambda self_, db, since, skipped, host=None:
               {'ok': False, 'reason': 'The site did not answer after the update.',
                'probe_code': 0, 'skipped': 0, 'errors': [], 'error_count': 0})
        self._run(lambda: self.svc.rollout_start(self.rel.id, 0, 0), health=bad)
        r = self._rollout()
        self.assertEqual(r.state, 'paused')
        self.assertIn('did not answer', r.reason)
        first = r.task_ids[0]
        self.assertEqual(first.state, 'failed')
        # Nothing after the failure was touched.
        self.assertTrue(all(t.state == 'queued' for t in r.task_ids[1:]))
        self.assertNotIn('Odoo', r.reason)

    def test_t7_10_an_exception_is_a_failure_not_a_crash(self):
        def boom(self_, target):
            raise UserError("The database canaryco2026-staging does not exist.")
        self._run(lambda: self.svc.rollout_start(self.rel.id, 0, 0), unit=boom)
        r = self._rollout()
        self.assertEqual(r.state, 'paused')
        self.assertEqual(r.task_ids[0].state, 'failed')
        self.assertIn('does not exist', r.task_ids[0].error)

    def test_t7_11_retry_puts_a_failed_task_back_and_carries_on(self):
        calls = {'n': 0}

        def flaky(self_, db, since, skipped, host=None):
            calls['n'] += 1
            ok = calls['n'] > 1
            return {'ok': ok, 'reason': '' if ok else 'The site did not answer.',
                    'probe_code': 200 if ok else 0, 'skipped': 0,
                    'errors': [], 'error_count': 0}
        self._run(lambda: self.svc.rollout_start(self.rel.id, 0, 0), health=flaky)
        r = self._rollout()
        self.assertEqual(r.state, 'paused')
        failed = r.task_ids.filtered(lambda t: t.state == 'failed')
        self.assertEqual(len(failed), 1)
        self._run(lambda: self.svc.task_retry(failed.id), health=flaky)
        self.assertEqual(r.state, 'done', r.reason or '')
        self.assertEqual(failed.attempts, 2)

    def test_t7_12_resume_refuses_to_walk_around_a_failure(self):
        bad = (lambda self_, db, since, skipped, host=None:
               {'ok': False, 'reason': 'The site did not answer.',
                'probe_code': 0, 'skipped': 0, 'errors': [], 'error_count': 0})
        self._run(lambda: self.svc.rollout_start(self.rel.id, 0, 0), health=bad)
        r = self._rollout()
        with self.assertRaises(UserError) as e:
            self._run(lambda: self.svc.rollout_resume(r.id))
        self.assertIn('still marked failed', str(e.exception))

    def test_t7_13_skipping_a_customer_needs_their_name_typed(self):
        self._run(lambda: self.svc.rollout_start(self.rel.id, 24, 48))
        r = self._rollout()
        rest = r.task_ids.filtered(lambda t: t.ring == 'everyone')
        with self.assertRaises(UserError) as e:
            self._run(lambda: self.svc.task_skip(rest.id, ''))
        self.assertIn('restco2026', str(e.exception))
        self._run(lambda: self.svc.task_skip(rest.id, 'restco2026'))
        self.assertEqual(rest.state, 'skipped')

    def test_t7_14_calling_it_off_needs_the_release_typed_and_skips_the_rest(self):
        self._run(lambda: self.svc.rollout_start(self.rel.id, 24, 48))
        r = self._rollout()
        with self.assertRaises(UserError):
            self._run(lambda: self.svc.rollout_abort(r.id, 'yes'))
        self._run(lambda: self.svc.rollout_abort(r.id, self.rel.name))
        self.assertEqual(r.state, 'aborted')
        self.assertFalse(r.task_ids.filtered(lambda t: t.state == 'queued'))

    def test_t7_15_run_now_is_recorded_against_the_person_who_asked(self):
        self._run(lambda: self.svc.rollout_start(self.rel.id, 24, 48))
        r = self._rollout()
        rest = r.task_ids.filtered(lambda t: t.ring == 'everyone')
        self.assertEqual(rest.state, 'queued')
        self._run(lambda: self.svc.task_run_now(rest.id))
        self.assertTrue(rest.run_now)
        self.assertEqual(rest.run_now_by, self.env.user)
        # It jumped the watch period because somebody asked it to.
        self.assertEqual(rest.state, 'done')

    def test_t7_16_the_plan_is_a_dry_run_and_writes_nothing(self):
        before = self.env['pb.rollout'].sudo().search_count([])
        plan = self._run(lambda: self.svc.rollout_plan(self.rel.id))
        self.assertEqual(self.env['pb.rollout'].sudo().search_count([]), before)
        self.assertTrue(plan['tasks'])
        self.assertEqual(plan['blockers'], [])
        self.assertTrue(all(t['when'] for t in plan['tasks']))

    def test_t7_17_the_worker_cron_does_nothing_when_nobody_started_anything(self):
        self.env['pb.rollout'].sudo().search([]).write({'state': 'done'})
        self.assertFalse(self.svc._cron_rollout_worker())

    def test_t7_18_the_pre_notice_only_reaches_a_queued_task_and_only_once(self):
        self._run(lambda: self.svc.rollout_start(self.rel.id, 24, 48))
        r = self._rollout()
        rest = r.task_ids.filtered(lambda t: t.ring == 'everyone')
        told = []

        def fake_send(self_, target, kind, title, text, starts, ends):
            told.append((target, title))
            return {'sent': ['x'], 'skipped': [], 'message': ''}
        ps = self._patches()
        for p in ps:
            p.start()
        try:
            with patch.object(self.cls, 'notice_send', fake_send), \
                 patch.object(self.cls, '_log_line', lambda *a, **kw: ''):
                self.assertEqual(self.svc._cron_rollout_notices(), 1)
                self.assertEqual(self.svc._cron_rollout_notices(), 0)
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual([t[0] for t in told], [self.rest.id])
        self.assertTrue(rest.notified_at)

    def test_t7_19_the_customer_gets_told_and_untold_around_their_update(self):
        seen = []

        def fake_send(self_, target, kind, title, text, starts, ends):
            seen.append(('up', target, title))
            return {'sent': ['x'], 'skipped': [], 'message': ''}

        def fake_clear(self_, target):
            seen.append(('down', target, ''))
            return {'cleared': ['x'], 'skipped': []}
        ps = self._patches()
        for p in ps:
            p.start()
        try:
            with patch.object(self.cls, 'notice_send', fake_send), \
                 patch.object(self.cls, 'notice_clear', fake_clear):
                self.svc.rollout_start(self.rel.id, 0, 0)
        finally:
            for p in reversed(ps):
                p.stop()
        for tid in (self.canary.id, self.rest.id):
            self.assertIn(('up', tid, 'Payobook is being updated right now'),
                          [(a, b, c) for a, b, c in seen])
            self.assertIn(('down', tid, ''), seen)
        # The bar goes up before the work and comes down after it.
        self.assertLess(seen.index(('up', self.canary.id,
                                    'Payobook is being updated right now')),
                        seen.index(('down', self.canary.id, '')))

    def test_t7_20_the_release_stamp_waits_for_the_health_check(self):
        """A customer is never told "you are on the new release" too early."""
        stamped = []
        bad = (lambda self_, db, since, skipped, host=None:
               {'ok': False, 'reason': 'The site did not answer.',
                'probe_code': 0, 'skipped': 0, 'errors': [], 'error_count': 0})
        ps = self._patches(health=bad)
        for p in ps:
            p.start()
        try:
            with patch.object(self.cls, '_push_release_stamp',
                              lambda self_, *a, **kw: stamped.append(a[0])):
                self.svc.rollout_start(self.rel.id, 0, 0)
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(stamped, [],
                         "Nothing that failed its checks may announce a release.")

    def test_t7_21_the_practice_copy_is_deleted_even_when_the_run_fails(self):
        dropped = []

        def boom(self_, target):
            raise UserError("It fell over.")
        ps = self._patches(unit=boom)
        for p in ps:
            p.start()
        try:
            with patch.object(self.cls, 'drop_staging',
                              lambda self_, tid: dropped.append(tid) or {}):
                self.svc.rollout_start(self.rel.id, 0, 0)
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(dropped, [self.canary.id],
                         "Rail R4: the copy goes, whatever happened.")

    def test_t7_22_a_template_with_live_jobs_fails_the_check(self):
        ps = self._patches()
        for p in ps:
            p.start()
        try:
            with patch.object(self.cls, '_template_cron_state',
                              lambda self_: (9, 52)), \
                 patch.object(self.cls, '_health_gate',
                              lambda self_, db, since, skipped, host=None:
                              {'ok': True, 'reason': '', 'probe_code': None,
                               'skipped': 0, 'errors': [], 'error_count': 0}):
                self.svc.rollout_start(self.rel.id, 0, 0)
        finally:
            for p in reversed(ps):
                p.stop()
        r = self._rollout()
        self.assertEqual(r.state, 'paused')
        self.assertIn('scheduled job', r.reason)

    def test_t7_23_the_customers_window_is_settable_and_bounded(self):
        self.svc.tenant_set_window(self.canary.id, 'early', 23, 4)
        self.assertEqual(self.canary.ring, 'early')
        self.assertEqual(self.canary.maintenance_start, 23)
        self.assertEqual(self.canary.maintenance_hours, 4)
        for bad in ((24, 3), (-1, 3)):
            with self.assertRaises(UserError):
                self.svc.tenant_set_window(self.canary.id, None, bad[0], bad[1])
        with self.assertRaises(UserError):
            self.svc.tenant_set_window(self.canary.id, None, 22, 40)
        with self.assertRaises(UserError):
            self.svc.tenant_set_window(self.canary.id, 'platinum')

    def test_t7_24_every_customer_starts_in_the_last_wave(self):
        t = self.env['pb.tenant'].sudo().create(
            {'name': 'New Co', 'slug': 'newco2026'})
        self.assertEqual(t.ring, 'everyone',
                         "A customer becomes a canary because somebody chose "
                         "it, never because it was created first.")

    # ================================================================== T8
    def test_t8_01_the_lock_is_a_real_skip_locked_row_lock(self):
        """The guard is the database's, not a flag we could forget to clear.

        Asserted on the source because two threads cannot be arranged inside
        one test transaction: a transaction can always re-take its own row
        lock, so a second `_rollout_tick` here would (correctly) succeed. The
        behaviour of the losing side is asserted below.
        """
        src = inspect.getsource(rollout_service.PbTenantsRollout._lock_rollout)
        self.assertIn('FOR UPDATE SKIP LOCKED', src)
        self.assertIn('pb_rollout', src)

    def test_t8_02_the_loser_walks_away_and_touches_nothing(self):
        def go():
            with patch.object(self.cls, '_rollout_tick',
                              lambda self_, r: {'ok': True}):
                self.svc.rollout_start(self.rel.id, 0, 0)
        self._run(go)
        r = self._rollout()
        self.assertEqual(r.task_ids[0].state, 'queued')
        ran = []
        ps = self._patches()
        for p in ps:
            p.start()
        try:
            with patch.object(self.cls, '_lock_rollout', lambda self_, r: False), \
                 patch.object(self.cls, '_run_task',
                              lambda self_, t: ran.append(t.id)):
                res = self.svc._rollout_tick(r)
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(res, {'ok': False, 'reason': 'busy'})
        self.assertEqual(ran, [], "The losing side must do nothing at all.")
        self.assertEqual(r.task_ids[0].state, 'queued')
