# -*- coding: utf-8 -*-
"""SC-2 — each connection fetches on ITS OWN schedule, on the company's clock.

RD49 gave everybody one cadence: the 5th, 02:00 UTC — which is 09:00 in
Vietnam, mid-morning, and not something any owner chose. The cron is now an
hourly dispatcher; the cadence (daily / weekly on a day / monthly on a day /
last day of the month, at a time of day) lives on the connector, is written
on the COMPANY's clock, and is converted to UTC only at the edge.

The window rule is the owner's: monthly keeps RD49's previous-month window;
daily and weekly fetch the current month, plus the month just closed during
the first seven days of a new month, so late corrections still arrive before
that month's pay run closes.
"""
from datetime import date, datetime

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSc2SyncSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        # A known clock for every assertion in this file.
        cls.env.company.partner_id.tz = 'Asia/Ho_Chi_Minh'

    def _connector(self, name='SC2', **vals):
        return self.Connector.create(dict(
            {'name': name, 'connector_type': 'demo'}, **vals))

    # =====================================================================
    # the next occurrence, on the company's clock
    # =====================================================================
    def test_01_daily_six_am_vietnam_is_2300_utc_the_night_before(self):
        conn = self._connector(sync_frequency='daily', sync_time=6.0)
        # 2026-09-02 10:00 UTC = 17:00 in Vietnam → next 06:00 is tomorrow,
        # which in UTC is 23:00 TODAY.
        self.assertEqual(
            conn._sync_next_occurrence(datetime(2026, 9, 2, 10, 0)),
            datetime(2026, 9, 2, 23, 0),
            "the schedule is written on the company's clock, not the "
            "server's — this is the whole point of SC-2")

    def test_02_weekly_lands_on_the_chosen_weekday(self):
        conn = self._connector(sync_frequency='weekly', sync_weekday='0',
                               sync_time=6.0)
        # 2026-09-02 (Wednesday) 10:00 UTC → next Monday is 7 Sep, 06:00 VN
        # = 6 Sep 23:00 UTC.
        nxt = conn._sync_next_occurrence(datetime(2026, 9, 2, 10, 0))
        self.assertEqual(nxt, datetime(2026, 9, 6, 23, 0))

    def test_03_monthly_rolls_to_next_month_once_the_day_has_passed(self):
        conn = self._connector(sync_frequency='monthly_day',
                               sync_day_of_month=5, sync_time=6.0)
        self.assertEqual(
            conn._sync_next_occurrence(datetime(2026, 9, 10, 10, 0)),
            datetime(2026, 10, 4, 23, 0),
            "the 5th at 06:00 VN, one month on")
        self.assertEqual(
            conn._sync_next_occurrence(datetime(2026, 12, 10, 10, 0)),
            datetime(2027, 1, 4, 23, 0),
            "December rolls the year")

    def test_04_last_day_of_month_knows_short_months(self):
        conn = self._connector(sync_frequency='monthly_last', sync_time=6.0)
        self.assertEqual(
            conn._sync_next_occurrence(datetime(2026, 2, 10, 10, 0)),
            datetime(2026, 2, 27, 23, 0),
            "28 Feb 06:00 VN = 27 Feb 23:00 UTC")
        # Already past this month's last day → next month's last day.
        self.assertEqual(
            conn._sync_next_occurrence(datetime(2026, 2, 28, 10, 0)),
            datetime(2026, 3, 30, 23, 0))

    # =====================================================================
    # the window rule
    # =====================================================================
    def test_05_monthly_keeps_the_previous_month_window(self):
        conn = self._connector(sync_frequency='monthly_day')
        self.assertEqual(conn._sync_window_pulls(date(2026, 9, 5)),
                         [(date(2026, 8, 1), date(2026, 8, 31))])

    def test_06_daily_fetches_this_month_plus_grace(self):
        conn = self._connector(sync_frequency='daily')
        self.assertEqual(
            conn._sync_window_pulls(date(2026, 9, 3)),
            [(date(2026, 8, 1), date(2026, 8, 31)),
             (date(2026, 9, 1), date(2026, 9, 30))],
            "during the first week the month just closed comes too, so a "
            "late correction still lands before that pay run closes")
        self.assertEqual(
            conn._sync_window_pulls(date(2026, 9, 15)),
            [(date(2026, 9, 1), date(2026, 9, 30))],
            "after the grace week, this month only")

    # =====================================================================
    # the dispatcher
    # =====================================================================
    def test_07_only_due_connectors_run_and_get_restamped(self):
        ran = []

        def record(this, data_types=None, **kwargs):
            ran.append(this.name)
            return True

        due = self._connector('SC2 due', cron_pull_enabled=True)
        due.with_context(sc2_stamping=True).sync_next_run = \
            datetime(2020, 1, 1)
        later = self._connector('SC2 later', cron_pull_enabled=True)
        later.with_context(sc2_stamping=True).sync_next_run = \
            datetime(2099, 1, 1)
        for c in (due, later):
            ep = self.env['hr.integration.endpoint'].create({
                'connector_id': c.id, 'name': 'salary feed',
                'data_type': 'salary', 'code': 'sc2_%s' % c.id})
            cfg = self.env['hr.formula.config'].create({
                'name': 'SC2 cfg %s' % c.id, 'code': 'SC2C%s' % c.id,
                'country_code': 'VN'})
            rule = self.env['hr.formula.rule'].create({
                'config_id': cfg.id, 'name': 'Pay %s' % c.id,
                'code': 'SC2PAY%s' % c.id, 'column_type': 'input'})
            self.env['hr.integration.field.mapping'].create({
                'connector_id': c.id, 'endpoint_id': ep.id,
                'target_rule_id': rule.id, 'source_field': 'Base_Salary',
                'active_state': 'active'})

        self.patch(type(self.Connector), 'action_pull_data', record)
        self.Connector.cron_pull_previous_month()

        self.assertIn('SC2 due', ran)
        self.assertNotIn('SC2 later', ran,
                         "a connector whose time has not come is left alone")
        self.assertGreater(due.sync_next_run, datetime(2026, 1, 1),
                           "after running, the next occurrence is stamped")
        self.assertEqual(later.sync_next_run, datetime(2099, 1, 1))

    def test_08_changing_the_schedule_restamps_the_next_run(self):
        conn = self._connector('SC2 restamp')
        self.assertFalse(conn.sync_next_run)
        conn.write({'cron_pull_enabled': True, 'sync_frequency': 'daily',
                    'sync_time': 6.0})
        self.assertTrue(conn.sync_next_run,
                        "switching the schedule on stamps the first "
                        "occurrence — otherwise the next hourly tick would "
                        "fire it at whatever hour that happens to be")
        first = conn.sync_next_run
        conn.write({'sync_time': 20.0})
        self.assertNotEqual(conn.sync_next_run, first)

    def test_09_the_sentence_speaks_the_company_clock(self):
        conn = self._connector('SC2 words', sync_frequency='weekly',
                               sync_weekday='0', sync_time=6.0,
                               cron_pull_enabled=True)
        sentence = conn._sync_schedule_sentence()
        self.assertIn('Monday', sentence)
        self.assertIn('06:00', sentence)
        self.assertIn('Ho Chi Minh', sentence)
        self.assertNotIn('23:00', sentence,
                         "the UTC value must never be said out loud")

    def test_10_bad_schedule_values_are_refused(self):
        from odoo.exceptions import ValidationError
        conn = self._connector('SC2 bad')
        with self.assertRaises(ValidationError):
            conn.sync_day_of_month = 31
        with self.assertRaises(ValidationError):
            conn.sync_time = 25.0
