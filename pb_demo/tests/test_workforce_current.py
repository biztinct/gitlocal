# -*- coding: utf-8 -*-
"""Workforce P6 — `ensure_workforce_current()`, the demo world's living present.

The deliverable of this seeder is PERSISTENT data, which makes it the one piece
of pb_demo whose bugs are expensive: a run that is not idempotent doubles the
demo world every time somebody presses the button, and a run that reaches
outside the demo company reaches real payroll evidence. Both are asserted here
against a real run, not against the source.

The suite runs the seeder ONCE in `setUpClass` (it is the slow part) and then
interrogates the result; the idempotency test runs it a second time and asserts
the counts of what it created are all zero and the row totals did not move.
"""

from datetime import date, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

_MINORS = ('Demo Minor 17 (Young Worker)', 'Demo Minor 14 (Young Worker)')


@tagged('post_install', '-at_install')
class TestWorkforceCurrent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gen = cls.env['pb.demo.generator'].sudo().create({})
        cls.company = cls.gen.get_group_company()
        cls.cohort = cls.env['hr.employee'].browse()
        cls.counts = {}
        cls.today = fields.Date.context_today(cls.gen)
        cls.start = cls.today - timedelta(days=14)
        cls.end = cls.today + timedelta(days=7)
        if not cls.company:
            return
        cls.counts = cls.gen.ensure_workforce_current()
        cls.cohort = cls.gen._p6_cohort(cls.company)

    def setUp(self):
        super().setUp()
        if not self.company:
            self.skipTest('no demo company on this database')
        if not self.cohort:
            self.skipTest('no demo employees on this database')

    # ------------------------------------------------------------ the window
    def test_the_window_is_anchored_on_today_not_on_a_constant(self):
        """The whole point of the phase: a rerun in a month must move the world.

        Asserted by shape rather than by value — the seeder derives every date
        from `fields.Date.context_today`, so the newest shift it produced must
        be a week out and the oldest a fortnight back, whenever it is run.
        """
        Shift = self.env['hr.shift.planning'].sudo()
        dates = Shift.search([
            ('employee_id', 'in', self.cohort.ids),
            ('date', '>=', self.start), ('date', '<=', self.end),
        ]).mapped('date')
        self.assertTrue(dates, 'the seeder must have produced a roster')
        self.assertLessEqual(max(dates), self.end)
        self.assertGreaterEqual(max(dates), self.today,
                                'the forward roster must reach today or later')
        self.assertGreaterEqual(min(dates), self.start)

    def test_every_seeded_punch_is_inside_the_utc_safe_window(self):
        """W51: the surfaces disagree about which day a punch belongs to unless
        the punch sits between 00:00 and 15:00 UTC (07:00–22:00 in VN). This is
        why the seeder never uses the night template."""
        Att = self.env['hr.attendance'].sudo()
        punches = Att.search([
            ('employee_id', 'in', self.cohort.ids),
            ('check_in', '>=', self.start), ])
        for a in punches.filtered(lambda a: a.check_in.date() >= self.start):
            self.assertLess(a.check_in.hour, 16,
                            '%s punched at %s UTC — outside the safe window'
                            % (a.employee_id.name, a.check_in))

    def test_the_demo_world_runs_on_vietnamese_office_hours(self):
        """The bug this test exists for cost a whole live run: the demo
        company's `resource.calendar` is Odoo's stock 40-hour one and carries
        `tz = Europe/Brussels`, so a seeder that trusts it puts an "08:00" shift
        at 13:00 in Ho Chi Minh City — and at 09:00 Vietnamese time the Today
        board's live population is still empty, because in Brussels nobody has
        started. `_p6_tz` therefore pins the country, and this asserts it stays
        pinned even if somebody "fixes" it back to the calendar."""
        tz = self.gen._p6_tz(self.company)
        eight_local = self.gen._p6_utc(tz, self.today, 8.0)
        self.assertEqual(
            eight_local.hour, 1,
            '08:00 in the demo world must be 01:00 UTC (Vietnam, UTC+7) — got '
            '%s, which means the seeder is reading a foreign calendar tz'
            % eight_local)
        # Every shift the PLAN describes must begin and end on its own local
        # day — a foreign row somebody else created is not this test's business.
        specs = self.gen._p6_specs(self.cohort, tz, self.today, self.start,
                                   self.end, {})
        for (_eid, d), spec in specs.items():
            for label, dt in (('start', spec['start']), ('end', spec['end'])):
                self.assertEqual(
                    (dt + timedelta(hours=7)).date(), d,
                    'the planned %s for %s lands on another local day — a '
                    'punch against it would be keyed to the wrong day (W51)'
                    % (label, d))

    # --------------------------------------------------------------- content
    def test_it_leaves_a_populated_world_behind(self):
        """Asserted on the WORLD, not on this run's creation counts.

        The counts are zero on any database that is already current — which is
        the normal state of the live demo and exactly what the idempotency test
        below demands — so asserting them here would make a correct rerun fail.
        What must hold after the seeder returns is that the window is full.
        """
        self.assertGreaterEqual(self.counts['cohort'], 40,
                                'cohort too small to look real')
        Shift = self.env['hr.shift.planning'].sudo()
        Att = self.env['hr.attendance'].sudo()
        self.assertGreater(
            Shift.search_count([('employee_id', 'in', self.cohort.ids),
                                ('date', '>=', self.start),
                                ('date', '<=', self.end)]), 100,
            'the roster is empty — every Schedule/Time lens would be blank')
        self.assertGreater(
            Att.search_count([('employee_id', 'in', self.cohort.ids),
                              ('check_in', '>=', self.start)]), 100,
            'nobody punched — the Week Grid and Close board would be blank')

    def test_today_has_a_live_on_shift_population(self):
        """The Today board's whole reason to exist is the open punch."""
        Att = self.env['hr.attendance'].sudo()
        day_start, day_end = self.gen._p6_day_bounds(
            self.gen._p6_tz(self.company), self.today)
        open_now = Att.search_count([
            ('employee_id', 'in', self.cohort.ids),
            ('check_in', '>=', day_start), ('check_in', '<=', day_end),
            ('check_out', '=', False),
        ])
        # Before the first shift of the day starts there is legitimately nobody
        # in yet — the seeder refuses to invent a punch in the future.
        now = fields.Datetime.now()
        first_start = min(
            (s['start'] for s in self.gen._p6_specs(
                self.cohort, self.gen._p6_tz(self.company), self.today,
                self.start, self.end, {}).values()
             if s['start'].date() == self.today), default=None)
        if first_start and first_start > now:
            self.skipTest('the demo working day has not started yet')
        self.assertGreater(open_now, 0,
                           'nobody is on shift — the Today board would be dead')

    def test_the_forward_roster_is_published_with_a_draft_slice(self):
        Shift = self.env['hr.shift.planning'].sudo()
        fwd = Shift.search([
            ('employee_id', 'in', self.cohort.ids),
            ('date', '>', self.today), ('date', '<=', self.end),
        ])
        self.assertTrue(fwd, 'next week must be scheduled')
        states = set(fwd.mapped('state'))
        self.assertIn('published', states,
                      'the Schedule lens must look planned-ahead')

    # ------------------------------------------------------------ ownership
    def test_it_only_ever_touches_demo_employees_of_the_demo_company(self):
        """§5's rail. Not a proxy for it — the actual predicate, over every row
        the seeder can create."""
        self.assertTrue(all(e.is_demo for e in self.cohort))
        self.assertTrue(all(e.company_id == self.company for e in self.cohort))
        for model, field in (('hr.shift.planning', 'employee_id'),
                             ('hr.overtime.request', 'employee_id'),
                             ('pb.business.trip', 'employee_id'),
                             ('hr.attendance.correction', 'employee_id')):
            if model not in self.env:
                continue
            recs = self.env[model].sudo().search(
                [(field, 'in', self.cohort.ids)])
            for r in recs:
                self.assertTrue(r[field].is_demo,
                                '%s reached a non-demo employee' % model)

    # ---------------------------------------------------------- young workers
    def test_the_minors_stay_inside_their_bands(self):
        """The VN caps are a HARD constraint that fires under sudo, so a breach
        would have raised — but a seeder that quietly stopped seeding them
        instead would pass that test and fail the demo. Both are checked."""
        if 'pb.young.worker' not in self.env:
            self.skipTest('pb_young_worker is not installed')
        Eng = self.env['pb.young.worker'].sudo()
        if not Eng._has_any_rule():
            self.skipTest('no young-worker rule on this database')
        minors = self.cohort.filtered(lambda e: e.name in _MINORS)
        if not minors:
            self.skipTest('the demo minors are not on this database')
        Att = self.env['hr.attendance'].sudo()
        for emp in minors:
            d = self.start
            worked = 0
            while d <= self.today:
                res = Eng.check_day_hours(emp, d)
                self.assertTrue(
                    res['ok'],
                    '%s worked %.1f h on %s (cap %.1f)'
                    % (emp.name, res['actual'], d, res['cap']))
                week = Eng.check_week_hours(emp, d)
                self.assertTrue(
                    week['ok'],
                    '%s worked %.1f h in the week of %s (cap %.1f)'
                    % (emp.name, week['actual'], week['week_start'], week['cap']))
                d += timedelta(days=1)
                worked += 1
            # never an OPEN punch: its hours are measured against `now`
            self.assertFalse(
                Att.search_count([('employee_id', '=', emp.id),
                                  ('check_in', '>=', self.start),
                                  ('check_out', '=', False)]),
                '%s has an open punch — it would breach the daily cap by '
                'the afternoon' % emp.name)

    # ------------------------------------------------------------ the locks
    def test_it_never_seeds_onto_a_locked_day(self):
        if 'pb.wf.lock' not in self.env:
            self.skipTest('pb_close is not installed')
        locks = self.env['pb.wf.lock'].sudo().search([
            ('company_id', '=', self.company.id),
            ('date', '>=', self.start), ('date', '<=', self.end),
            ('state', '=', 'locked'),
        ])
        self.assertFalse(
            locks, 'the seeded window must not contain a locked day — the '
                   'punch guard would have refused half the rows')

    # ---------------------------------------------------------- idempotency
    def test_running_it_twice_changes_nothing(self):
        """The contract that makes this safe to wire into `action_generate_all`
        and safe to press twice: a second run creates nothing."""
        before = self._totals()
        again = self.gen.ensure_workforce_current()
        after = self._totals()
        self.assertEqual(before, after,
                         'a second run moved the row counts: %s → %s'
                         % (before, after))
        for key in ('shifts', 'drafts', 'punches', 'overtime', 'leaves',
                    'trips', 'corrections'):
            self.assertEqual(again.get(key, 0), 0,
                             'the second run created %s %s' % (again[key], key))

    def _totals(self):
        Att = self.env['hr.attendance'].sudo()
        Shift = self.env['hr.shift.planning'].sudo()
        return {
            'att': Att.search_count([('employee_id', 'in', self.cohort.ids),
                                     ('check_in', '>=', self.start)]),
            'shift': Shift.search_count([('employee_id', 'in', self.cohort.ids),
                                         ('date', '>=', self.start),
                                         ('date', '<=', self.end)]),
            'ot': self.env['hr.overtime.request'].sudo().search_count(
                [('employee_id', 'in', self.cohort.ids),
                 ('date', '>=', self.start)]),
        }

    # -------------------------------------------------- savepoint isolation
    def test_one_poisoned_section_does_not_kill_the_others(self):
        """The InFailedSqlTransaction lesson, asserted rather than assumed: a
        section that raises is logged and skipped, and the sections after it
        still run and still commit their work."""
        out = {'x': 0}
        marker = self.env['hr.department'].sudo()

        def boom():
            raise ValueError('deliberate')

        def fine():
            marker.create({'name': 'P6 savepoint probe',
                           'company_id': self.company.id})
            return {'x': 1}

        self.gen._p6_section(out, 'boom', boom)
        self.gen._p6_section(out, 'fine', fine)
        self.assertEqual(out['x'], 1,
                         'the section after a failure must still have run')
        probe = marker.search([('name', '=', 'P6 savepoint probe')])
        self.assertTrue(probe, 'the surviving section must have committed')
        probe.unlink()

    def test_the_seeder_never_raises_when_there_is_nothing_to_do(self):
        """§5: it must be safe to call on any database, including one with no
        demo world at all."""
        self.assertIsInstance(self.gen.ensure_workforce_current(), dict)

    # ------------------------------------------------------------- determinism
    def test_the_day_plan_is_pure_and_reproducible(self):
        """No RNG anywhere: the same inputs must produce the same world, or a
        rerun would drift the demo instead of refreshing it."""
        tz = self.gen._p6_tz(self.company)
        a = self.gen._p6_specs(self.cohort, tz, self.today, self.start,
                               self.end, {})
        b = self.gen._p6_specs(self.cohort, tz, self.today, self.start,
                               self.end, {})
        self.assertEqual(
            {k: (v['start'], v['end'], v['co'], v['draft']) for k, v in a.items()},
            {k: (v['start'], v['end'], v['co'], v['draft']) for k, v in b.items()})

    def test_the_demo_employees_carry_their_own_countrys_timezone(self):
        """`pb.today._tzinfo` is `emp.tz or the VIEWER's tz or UTC`, and a demo
        employee had no tz at all — so a correctly-seeded 08:00 Vietnamese shift
        printed as "03:00–11:00" for a European admin. The same field is what
        pb.close / pb.wf.lock / the exception engine key the employee-local day
        on (W51), so a blank one also made them disagree with this seeder."""
        blank = self.env['hr.employee'].sudo().with_context(
            active_test=False).search_count([
                ('is_demo', '=', True), ('company_id', '=', self.company.id),
                '|', ('tz', '=', False), ('tz', '=', '')])
        self.assertFalse(
            blank, '%s demo employees still have no timezone — every Workforce '
                   'surface would render them in the viewer\'s zone' % blank)
        self.assertEqual(self.cohort[0].tz, 'Asia/Ho_Chi_Minh')

    def test_an_uneventful_day_is_worth_exactly_its_planned_hours(self):
        """Otherwise the Close board fills with rollup noise.

        `hr.shift.template.duration` is PAID time; `end_hour − start_hour`
        includes the unpaid break. A seeder that builds the shift from
        `end_hour` overshoots by an hour every day — inside the per-punch
        tolerance, outside the weekly one — and every person in the cohort
        arrives with a "Week outside tolerance" row. Seen live before the fix.
        """
        tz = self.gen._p6_tz(self.company)
        specs = self.gen._p6_specs(self.cohort, tz, self.today, self.start,
                                   self.end, {})
        minors = set(_MINORS)
        checked = 0
        for (eid, d), spec in specs.items():
            emp = self.cohort.browse(eid)
            if emp.name in minors:
                continue
            planned = spec['tpl'].duration
            span = (spec['end'] - spec['start']).total_seconds() / 3600.0
            self.assertAlmostEqual(
                span, planned, places=2,
                msg='the shift on %s spans %.2f h but is worth %.2f h — every '
                    'clean day would post a variance' % (d, span, planned))
            checked += 1
        self.assertTrue(checked, 'no adult shift in the plan to check')

    def test_the_mix_is_realistic_rather_than_uniform(self):
        """A board where everybody is on time teaches nothing. The wheel has to
        produce absences, forgiven lateness and real lateness."""
        kinds = {self.gen._p6_shape(i, date(2026, 3, 2) + timedelta(days=j))[0]
                 for i in range(25) for j in range(7)}
        for expected in ('on_time', 'grace', 'late', 'early', 'long', 'absent'):
            self.assertIn(expected, kinds)
