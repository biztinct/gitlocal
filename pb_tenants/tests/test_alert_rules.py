# -*- coding: utf-8 -*-
"""FLEET P3 — T1 to T6: every judgement the alerting makes, with no box under it.

These run against `alert_rules.py`, which imports nothing from the framework, so
what is argued with here is the RULE and not the plumbing. The model-level test
next door (`test_alerts.py`) then drives the same rules through a real sweep.

The one to read first is `test_t6_status_page_never_names_a_customer`. Everything
else on this cockpit is written for one reader who already knows every customer's
name; the status page is written for everybody else, and the difference between
those two audiences is one function.
"""
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.alert_rules import (
    DEFAULT_THRESHOLDS, capacity_verdict, digest_lines, readings_to_alerts,
    reconcile, render_status_page, should_notify, status_state,
)

NOW = datetime(2026, 9, 3, 12, 0, 0)


def _readings(**over):
    """A fleet in perfect health. Each test spoils exactly one thing."""
    base = {
        'now': NOW,
        'tenants': [{
            'id': 2, 'name': 'AB Mauri', 'slug': 'abm', 'state': 'live',
            'health': 'ok', 'ping_ms': 40,
            'last_backup_at': NOW - timedelta(hours=3),
            'last_backup_failed': False,
            'cert_days_left': 60, 'cert_own': True,
            'error_lines': 0, 'release_state': 'on',
            'behind_count': 0, 'stale_count': 0, 'release_age_days': 1,
        }],
        'wildcard_cert_days': 70,
        'disk': {'free_pct': 50, 'free_gb': 29.0},
        'memory': {'total_mb': 1907, 'available_mb': 900, 'rss_mb': 565},
        'mail': {'default_from': True, 'failed_recent': 0},
        'rollout': {},
        'master_behind_files': [],
        'template_hot_crons': 0,
        'status_page': {'writable': True, 'age_min': 2},
    }
    tenant_over = over.pop('tenant', None)
    if tenant_over:
        base['tenants'][0].update(tenant_over)
    base.update(over)
    return base


def _keys(alerts):
    return sorted(a['key'] for a in alerts)


@tagged('post_install', '-at_install')
class TestAlertRules(TransactionCase):

    # ------------------------------------------------------------------ T1
    def test_t1_healthy_fleet_says_nothing(self):
        self.assertEqual(readings_to_alerts(_readings()), [],
                         "A healthy platform must raise nothing at all.")

    def test_t1_every_kind_can_be_raised(self):
        r = _readings(
            tenant={'health': 'down', 'last_backup_failed': True,
                    'cert_days_left': 3, 'error_lines': 9,
                    'release_state': 'behind', 'behind_count': 2,
                    'stale_count': 1, 'release_age_days': 30},
            wildcard_cert_days=2,
            disk={'free_pct': 3, 'free_gb': 1.0},
            memory={'total_mb': 1907, 'available_mb': 90, 'rss_mb': 1500},
            mail={'default_from': False, 'failed_recent': 20},
            rollout={'state': 'paused', 'release': '2026.09.03',
                     'reason': 'A customer failed.'},
            master_behind_files=['pb_settings', 'pb_hub'],
            template_hot_crons=9,
            status_page={'writable': False, 'reason': 'The folder is missing.'},
        )
        got = readings_to_alerts(r)
        self.assertEqual(_keys(got), sorted([
            'tenant_down:abm', 'backup_failed:abm', 'cert_expiring:abm',
            'tenant_errors:abm', 'drift:abm', 'cert_expiring:wildcard',
            'disk_low', 'memory_high', 'mail_failing', 'rollout_paused',
            'master_behind_files', 'template_hot_cron',
            'status_page_unwritable']))
        # EVERY ALERT CARRIES ITS NEXT STEP. This is the assertion that keeps
        # the copy honest as kinds are added later.
        for a in got:
            self.assertIn('Next:', a['text'],
                          "%s does not tell anybody what to do." % a['key'])
            self.assertNotIn('odoo', a['text'].lower())
            self.assertNotIn('odoo', a['title'].lower())
        # A failed backup and a stale backup are the same news said twice.
        self.assertNotIn('backup_stale:abm', _keys(got))

    def test_t1_thresholds_at_the_edge(self):
        th = DEFAULT_THRESHOLDS
        # Disk: exactly at the level is fine, one below is not.
        ok = _readings(disk={'free_pct': th['disk_free_pct'], 'free_gb': 20.0})
        self.assertEqual(readings_to_alerts(ok), [])
        bad = _readings(disk={'free_pct': th['disk_free_pct'] - 1, 'free_gb': 20.0})
        self.assertEqual(_keys(readings_to_alerts(bad)), ['disk_low'])
        # Backups: 30 h is the line the nightly job leaves room for.
        edge = _readings(tenant={'last_backup_at':
                                 NOW - timedelta(hours=th['backup_stale_hours'])})
        self.assertEqual(readings_to_alerts(edge), [])
        over = _readings(tenant={'last_backup_at': NOW - timedelta(hours=31)})
        self.assertEqual(_keys(readings_to_alerts(over)), ['backup_stale:abm'])
        # A customer that has never been backed up is the same alarm.
        never = _readings(tenant={'last_backup_at': None})
        self.assertEqual(_keys(readings_to_alerts(never)), ['backup_stale:abm'])
        # Error lines: two is noise on this box, three is a pattern.
        two = _readings(tenant={'error_lines': th['error_lines'] - 1})
        self.assertEqual(readings_to_alerts(two), [])
        three = _readings(tenant={'error_lines': th['error_lines']})
        self.assertEqual(_keys(readings_to_alerts(three)), ['tenant_errors:abm'])
        # And a threshold moved by the owner is obeyed.
        loud = readings_to_alerts(two, {'error_lines': 1})
        self.assertIn('tenant_errors:abm', _keys(loud))

    def test_t1_a_customer_who_is_not_live_is_left_alone(self):
        gone = _readings(tenant={'state': 'decommissioned', 'health': 'down',
                                 'last_backup_at': None})
        self.assertEqual(readings_to_alerts(gone), [],
                         "A closed-down customer must not raise anything.")

    def test_t1_a_reading_nobody_took_raises_nothing(self):
        blind = _readings(disk={}, memory={}, mail={}, status_page={})
        blind['tenants'][0]['cert_days_left'] = None
        blind['wildcard_cert_days'] = None
        self.assertEqual(readings_to_alerts(blind), [],
                         "A missing measurement must never be read as a "
                         "problem — nor as an all-clear.")

    def test_t1_severity_climbs_close_to_the_edge(self):
        soon = _readings(tenant={'cert_days_left': 3})
        self.assertEqual(readings_to_alerts(soon)[0]['severity'], 'critical')
        later = _readings(tenant={'cert_days_left': 10})
        self.assertEqual(readings_to_alerts(later)[0]['severity'], 'warning')

    # ------------------------------------------------------------------ T2
    def test_t2_reconcile_creates_bumps_and_resolves(self):
        fresh = readings_to_alerts(_readings(tenant={'health': 'down'}))
        create, bump, resolve = reconcile([], fresh, NOW)
        self.assertEqual(len(create), 1)
        self.assertEqual(create[0]['count'], 1)
        self.assertEqual(create[0]['first_seen'], NOW)
        self.assertFalse(bump or resolve)

        known = [{'id': 7, 'key': 'tenant_down:abm', 'kind': 'tenant_down',
                  'state': 'open', 'count': 3, 'severity': 'critical'}]
        create, bump, resolve = reconcile(known, fresh, NOW)
        self.assertFalse(create)
        self.assertEqual(bump[0][0], 7)
        self.assertEqual(bump[0][1]['count'], 4)
        self.assertFalse(resolve)

        create, bump, resolve = reconcile(known, [], NOW)
        self.assertEqual(resolve, [7])

    def test_t2_an_acknowledged_problem_is_still_the_same_problem(self):
        known = [{'id': 7, 'key': 'disk_low', 'kind': 'disk_low',
                  'state': 'acknowledged', 'count': 1, 'severity': 'warning'}]
        fresh = readings_to_alerts(_readings(disk={'free_pct': 4, 'free_gb': 1.0}))
        create, bump, _res = reconcile(known, fresh, NOW)
        self.assertFalse(create, "An acknowledged alert must not be duplicated.")
        self.assertEqual(bump[0][1]['severity'], 'critical',
                         "It got worse, and the record has to say so.")

    def test_t2_a_resolved_row_does_not_block_a_new_one(self):
        known = [{'id': 7, 'key': 'disk_low', 'kind': 'disk_low',
                  'state': 'resolved', 'count': 1, 'severity': 'warning'}]
        fresh = readings_to_alerts(_readings(disk={'free_pct': 4, 'free_gb': 1.0}))
        create, _bump, _res = reconcile(known, fresh, NOW)
        self.assertEqual(len(create), 1)

    def test_t2_the_channel_alert_is_never_swept_away(self):
        """The one alert no reading can see must not be resolved by not seeing it."""
        known = [{'id': 9, 'key': 'alert_channel_down',
                  'kind': 'alert_channel_down', 'state': 'open', 'count': 1,
                  'severity': 'critical'}]
        _c, _b, resolve = reconcile(known, [], NOW)
        self.assertEqual(resolve, [])

    # ------------------------------------------------------------------ T3
    def test_t3_should_notify(self):
        never = {'state': 'open', 'severity': 'critical', 'notified_at': None}
        self.assertTrue(should_notify(never, NOW))
        just = {'state': 'open', 'severity': 'critical',
                'notified_at': NOW - timedelta(minutes=30),
                'notified_severity': 'critical'}
        self.assertFalse(should_notify(just, NOW))
        old = dict(just, notified_at=NOW - timedelta(hours=2))
        self.assertTrue(should_notify(old, NOW))
        # A warning waits longer than a critical.
        warn = {'state': 'open', 'severity': 'warning',
                'notified_at': NOW - timedelta(hours=3),
                'notified_severity': 'warning'}
        self.assertFalse(should_notify(warn, NOW))
        self.assertTrue(should_notify(dict(warn, notified_at=NOW - timedelta(hours=7)), NOW))
        # It got worse: say so at once, whatever the interval says.
        worse = {'state': 'open', 'severity': 'critical',
                 'notified_at': NOW - timedelta(minutes=5),
                 'notified_severity': 'warning'}
        self.assertTrue(should_notify(worse, NOW))
        # Acknowledged means "I know". Never again.
        ack = dict(never, state='acknowledged')
        self.assertFalse(should_notify(ack, NOW))
        # Reminders can be switched off entirely.
        self.assertFalse(should_notify(old, NOW, interval_critical=0))

    # ------------------------------------------------------------------ T4
    def test_t4_digest_lines(self):
        rows = [
            {'key': 'disk_low', 'severity': 'warning', 'state': 'open',
             'title': 'The server is running out of disk',
             'first_seen': NOW - timedelta(hours=50), 'count': 200},
            {'key': 'tenant_down:abm', 'severity': 'critical', 'state': 'open',
             'title': 'AB Mauri cannot be reached',
             'first_seen': NOW - timedelta(minutes=20), 'count': 2},
            {'key': 'drift:abm', 'severity': 'warning', 'state': 'acknowledged',
             'title': 'AB Mauri is 30 days behind the release',
             'first_seen': NOW - timedelta(hours=5), 'count': 20},
        ]
        lines = digest_lines(rows, NOW)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith('Needs attention now:'),
                        "The urgent one has to be the first line read.")
        self.assertIn('less than an hour ago', lines[0])
        self.assertIn('2 days', lines[1])
        self.assertIn('acknowledged', lines[2])
        self.assertEqual(digest_lines([], NOW), [])

    # ------------------------------------------------------------------ T5
    def test_t5_capacity_verdict(self):
        ok = capacity_verdict(1907, 900, 565, 3, 1, 60, 400)
        self.assertEqual(ok['level'], 'ok')
        self.assertEqual(ok['headroom'], 8)
        warn = capacity_verdict(1907, 470, 900, 4, 3, 60, 400)
        self.assertEqual(warn['level'], 'warn')
        self.assertEqual(warn['headroom'], 1)
        full = capacity_verdict(1907, 420, 1300, 6, 5, 60, 400)
        self.assertEqual(full['level'], 'full')
        self.assertEqual(full['headroom'], 0)
        # Never below nought on the screen, whatever the arithmetic says.
        over = capacity_verdict(1907, 100, 1500, 8, 9, 60, 400)
        self.assertEqual(over['headroom'], 0)
        self.assertEqual(over['level'], 'full')
        # A cleared setting must not divide by nought.
        safe = capacity_verdict(1907, 900, 565, 3, 1, 0, 400)
        self.assertEqual(safe['level'], 'ok')
        self.assertGreater(safe['headroom'], 0)
        # A machine holding most of itself is not "plenty of room".
        tight = capacity_verdict(1907, 900, 1600, 5, 4, 60, 400)
        self.assertEqual(tight['level'], 'warn')
        for verdict in (ok, warn, full):
            self.assertNotIn('odoo', verdict['reason'].lower())

    # ------------------------------------------------------------------ T6
    def test_t6_status_page_never_names_a_customer(self):
        """THE ASSERTION THIS PHASE IS JUDGED ON.

        Everything on the way in names AB Mauri; nothing on the way out may.
        """
        alerts = readings_to_alerts(_readings(
            tenant={'health': 'down', 'error_lines': 9},
            mail={'default_from': False, 'failed_recent': 9}))
        alerts = [dict(a, id=i + 1, state='open', count=1, first_seen=NOW)
                  for i, a in enumerate(alerts)]
        state = status_state(
            alerts,
            [{'kind': 'maintenance', 'title': 'Planned update tonight',
              'text': 'You may notice a short pause.',
              'range': 'tonight 22:00–01:00'}],
            [{'kind': 'tenant_down', 'minutes': 12, 'ended': '2026-09-01'}],
            NOW)
        page = render_status_page(state, NOW)
        for secret in ('AB Mauri', 'abm', 'tenant_down', 'AB '):
            self.assertNotIn(secret, page,
                             "%r reached the public page." % secret)
        self.assertNotIn('odoo', page.lower())
        # It says the true things.
        self.assertIn('Some systems are degraded', page)
        self.assertIn('Planned update tonight', page)
        self.assertIn('tonight 22:00', page)
        self.assertIn('A customer site was unreachable for 12 minutes', page)
        for name in ('Sign-in &amp; web app', 'Payroll processing',
                     'Email delivery', 'Customer sites'):
            self.assertIn(name, page)
        # It is a whole file, and it checks its own age.
        self.assertTrue(page.startswith('<!doctype html>'))
        self.assertIn('</html>', page)
        self.assertIn('id="stale"', page)
        self.assertIn('setInterval', page)
        self.assertIn('2026-09-03 12:00:00', page)
        # Nothing is fetched from anywhere: the page's whole job is to work on
        # the day the rest of the platform does not.
        self.assertNotIn('http://', page)
        self.assertNotIn('<img', page)
        self.assertNotIn('<link', page)

    def test_t6_a_calm_page_says_so(self):
        state = status_state([], [], [], NOW)
        page = render_status_page(state, NOW)
        self.assertEqual(state['level'], 'ok')
        self.assertIn('All systems operational', page)
        self.assertIn('No incidents in the last seven days.', page)

    def test_t6_planned_work_is_a_different_colour_from_a_fault(self):
        state = status_state([], [], [], NOW, maintenance=True)
        self.assertEqual(state['level'], 'maintenance')
        self.assertIn('Planned maintenance in progress',
                      render_status_page(state, NOW))
        sites = [c for c in state['components'] if c['name'] == 'Customer sites']
        self.assertEqual(sites[0]['level'], 'maintenance')

    def test_t6_only_a_critical_colours_a_component(self):
        warn = [{'id': 1, 'key': 'tenant_errors:abm', 'kind': 'tenant_errors',
                 'severity': 'warning', 'state': 'open'}]
        self.assertEqual(status_state(warn, [], [], NOW)['level'], 'ok')
        crit = [dict(warn[0], severity='critical')]
        self.assertEqual(status_state(crit, [], [], NOW)['level'], 'degraded')

    def test_t6_a_notice_with_a_quote_in_it_cannot_break_the_page(self):
        state = status_state([], [{'kind': 'info',
                                   'title': 'Watch out for <script>x</script>',
                                   'text': '"quoted" & odd', 'range': ''}],
                             [], NOW)
        page = render_status_page(state, NOW)
        self.assertNotIn('<script>x</script>', page)
        self.assertIn('&lt;script&gt;', page)
