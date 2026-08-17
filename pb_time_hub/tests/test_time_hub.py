# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1a — server tests for the Time hub facade (handover §5 T2).

The person drawer is the phase's headline feature, so its arithmetic is pinned
here: planned vs entered vs worked_hours, an empty day, an unplanned day, and
the two access rails (non-officer, cross-company).
"""

from datetime import date, datetime, time, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTimeHubFacade(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Hub = cls.env['pb.time.hub']
        cls.Att = cls.env['hr.attendance']
        cls.company = cls.env.company

        # A fixed, safely-past week: Monday..Sunday two weeks back, so nothing
        # here can collide with "today" logic or with live demo data.
        today = date.today()
        cls.week = today - timedelta(days=today.weekday() + 14)
        cls.dept = cls.env['hr.department'].create({
            'name': 'P1a Time Hub', 'company_id': cls.company.id})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Tess Timecard', 'company_id': cls.company.id, 'tz': 'UTC',
            'barcode': 'P1A0001', 'department_id': cls.dept.id,
            'job_title': 'Line lead'})
        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'P1a Day', 'code': 'P1AD', 'start_hour': 8.0, 'end_hour': 16.0,
            'is_overnight': False, 'shift_type': 'morning',
            'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    def _day(self, i):
        return self.week + timedelta(days=i)

    def _shift(self, d, state='published'):
        return self.env['hr.shift.planning'].create({
            'employee_id': self.emp.id,
            'shift_template_id': self.tmpl.id,
            'date': d,
            'start_datetime': datetime.combine(d, time(8, 0)),
            'end_datetime': datetime.combine(d, time(16, 0)),
            'state': state,
        })

    def _att(self, d, start_h=8, hours=8):
        ci = datetime.combine(d, time(start_h, 0))
        return self.Att.create({
            'employee_id': self.emp.id,
            'check_in': ci,
            'check_out': ci + timedelta(hours=hours),
            'pb_entry_source': 'grid',
        })

    def _week(self):
        return self.Hub.get_person_week(self.emp.id, self.week.isoformat())

    # =================================================================== T2.1
    def test_person_week_math(self):
        """sched / entered / actual / delta, with an empty and an unplanned day.

        `entered` is the WEEK-GRID number (the wall-clock span) and `actual` is
        Odoo's `worked_hours`; the drawer shows both precisely because they can
        legitimately differ (the lunch-break deduction, C18 / Sudima E). The
        test asserts each against its own source rather than against each other.
        """
        mon, tue, wed = self._day(0), self._day(1), self._day(2)
        self._shift(mon)
        self._shift(tue)
        self._shift(wed)                 # planned but NEVER punched -> empty day
        a_mon = self._att(mon, hours=8)
        a_tue = self._att(tue, hours=9.5)
        # Thursday: no shift at all, but a punch happened anyway -> unplanned
        thu = self._day(3)
        a_thu = self._att(thu, hours=4)

        data = self._week()
        self.assertTrue(data, "the drawer payload must not be empty")
        by_date = {d['date']: d for d in data['days']}
        self.assertEqual(len(data['days']), 7, "a week is always seven days")

        d_mon = by_date[mon.isoformat()]
        self.assertTrue(d_mon['planned'])
        self.assertAlmostEqual(d_mon['sched'], self.tmpl.duration, places=2)
        self.assertAlmostEqual(d_mon['entered'], 8.0, places=2)
        self.assertAlmostEqual(d_mon['actual'], a_mon.worked_hours, places=2)
        self.assertAlmostEqual(d_mon['delta'], round(8.0 - d_mon['sched'], 2), places=2)

        d_tue = by_date[tue.isoformat()]
        self.assertAlmostEqual(d_tue['entered'], 9.5, places=2,
                               msg="entered is the SPAN, not worked_hours")
        self.assertAlmostEqual(d_tue['actual'], a_tue.worked_hours, places=2)
        self.assertIn('over', d_tue['flags'])

        # the empty day: planned, no punches at all
        d_wed = by_date[wed.isoformat()]
        self.assertTrue(d_wed['planned'])
        self.assertEqual(d_wed['entered'], 0.0)
        self.assertEqual(d_wed['actual'], 0.0)
        self.assertIn('missing', d_wed['flags'])
        self.assertAlmostEqual(d_wed['delta'], -d_wed['sched'], places=2)

        # the unplanned day: hours exist, but there is no schedule to compare to
        d_thu = by_date[thu.isoformat()]
        self.assertFalse(d_thu['planned'],
                         "no shift record => `planned` false, so the UI shows '—'")
        self.assertEqual(d_thu['sched'], 0.0)
        self.assertAlmostEqual(d_thu['entered'], 4.0, places=2)
        self.assertAlmostEqual(d_thu['actual'], a_thu.worked_hours, places=2)

        # totals are the column sums, and delta is entered - sched
        t = data['totals']
        self.assertAlmostEqual(
            t['entered'], sum(d['entered'] for d in data['days']), places=2)
        self.assertAlmostEqual(
            t['actual'], sum(d['actual'] for d in data['days']), places=2)
        self.assertAlmostEqual(
            t['sched'], sum(d['sched'] for d in data['days']), places=2)
        self.assertAlmostEqual(t['delta'], round(t['entered'] - t['sched'], 2), places=2)

        # the employee card the drawer header renders
        card = data['employee']
        self.assertEqual(card['id'], self.emp.id)
        self.assertEqual(card['name'], self.emp.name)
        self.assertEqual(card['badge'], 'P1A0001')
        self.assertEqual(card['dept'], self.dept.name)

    def test_person_week_matches_the_week_grid_cell(self):
        """`entered` must be the SAME number the Week-Grid lens edits."""
        mon = self._day(0)
        self._shift(mon)
        self._att(mon, hours=7.5)

        drawer = self._week()
        grid = self.env['hr.attendance.weekentry'].get_week_entries(
            self.week.isoformat(), False, self.emp.name)
        row = next((r for r in grid['rows'] if r['id'] == self.emp.id), None)
        self.assertTrue(row, "the seeded employee must appear in the grid")
        cell = row['cells'][mon.isoformat()]['measures']['reg']['value']
        d_mon = next(d for d in drawer['days'] if d['date'] == mon.isoformat())
        self.assertAlmostEqual(
            d_mon['entered'], cell, places=2,
            msg="the drawer and the grid must never disagree about entered hours")

    def test_draft_shifts_are_not_scheduled_hours(self):
        """A draft (unpublished) shift is a plan nobody committed to."""
        mon = self._day(0)
        self._shift(mon, state='draft')
        d = next(x for x in self._week()['days'] if x['date'] == mon.isoformat())
        self.assertFalse(d['planned'])
        self.assertEqual(d['sched'], 0.0)

    # =================================================================== T2.2
    def test_summary_counts_equal_the_engine_output(self):
        """The ribbon count IS the Exceptions lens count — same cohort, same
        window, same engine call. If these ever diverge the hub is lying."""
        # a published shift in the past with no punch => one missing_punch
        self._shift(self._day(0))
        self._shift(self._day(1))
        self._att(self._day(1))            # this one is fine

        summary = self.Hub.get_hub_summary(False, self.week.isoformat())
        board = self.env['pb.attendance.flow'].get_control_data(
            self.week.isoformat(), (self.week + timedelta(days=6)).isoformat(), False)

        self.assertEqual(summary['open_exceptions'], len(board['exceptions']))
        self.assertEqual(summary['open_exceptions'], board['kpis']['open_exceptions'])
        self.assertEqual(summary['lens_counts']['exceptions'], summary['open_exceptions'])
        self.assertEqual(summary['week_start'], self.week.isoformat())
        self.assertEqual(summary['week_end'], (self.week + timedelta(days=6)).isoformat())
        self.assertGreaterEqual(summary['open_exceptions'], 1)
        self.assertEqual(summary['ribbon']['tone'], 'amber')
        self.assertIn('need', summary['ribbon']['text'].lower())

    def test_summary_department_scope_and_clear_week(self):
        """A department with nothing in it yields the green 'all clear' ribbon."""
        empty = self.env['hr.department'].create({
            'name': 'P1a Empty', 'company_id': self.company.id})
        self._shift(self._day(0))          # belongs to self.dept, not `empty`
        s = self.Hub.get_hub_summary(empty.id, self.week.isoformat())
        self.assertEqual(s['open_exceptions'], 0)
        self.assertEqual(s['ribbon']['tone'], 'green')
        self.assertEqual(s['lens_counts']['exceptions'], 0)

    def test_summary_normalizes_a_mid_week_date(self):
        """Any day of the week resolves to the same Monday-based window."""
        a = self.Hub.get_hub_summary(False, self.week.isoformat())
        b = self.Hub.get_hub_summary(False, (self.week + timedelta(days=4)).isoformat())
        self.assertEqual(a['week_start'], b['week_start'])

    # =================================================================== T2.3
    def test_non_officer_rpc_is_refused(self):
        """Every hub entry point is officer-gated (deliberate narrowing: the
        Timecards surface this replaces was ungated)."""
        user = self.env['res.users'].create({
            'name': 'Plain Percy', 'login': 'p1a_plain_percy',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        hub = self.Hub.with_user(user)
        with self.assertRaises(AccessError):
            hub.get_hub_summary(False, self.week.isoformat())
        with self.assertRaises(AccessError):
            hub.get_person_week(self.emp.id, self.week.isoformat())

    def test_officer_is_allowed(self):
        """...and an attendance officer is not locked out of their own hub."""
        user = self.env['res.users'].create({
            'name': 'Olive Officer', 'login': 'p1a_olive_officer',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
            ])],
        })
        res = self.Hub.with_user(user).get_hub_summary(False, self.week.isoformat())
        self.assertIn('open_exceptions', res)

    # =================================================================== T2.4
    def test_cross_company_employee_is_not_readable(self):
        """A person outside env.companies must not leak a name or an hours
        total through the drawer — it is reachable from a free typeahead."""
        other = self.env['res.company'].create({'name': 'P1a Other Co'})
        stranger = self.env['hr.employee'].create({
            'name': 'Stranger Sam', 'company_id': other.id, 'tz': 'UTC'})
        self.assertEqual(
            self.Hub.get_person_week(stranger.id, self.week.isoformat()), {},
            "a cross-company employee must yield an empty payload")

        # ...and is readable again once that company is actually active
        allowed = self.Hub.with_company(other).with_context(
            allowed_company_ids=[self.company.id, other.id])
        self.assertTrue(allowed.get_person_week(stranger.id, self.week.isoformat()))

    def test_unknown_employee_yields_empty(self):
        self.assertEqual(self.Hub.get_person_week(0, self.week.isoformat()), {})
        self.assertEqual(self.Hub.get_person_week('nope', self.week.isoformat()), {})
        self.assertEqual(
            self.Hub.get_person_week(2 ** 31 - 1, self.week.isoformat()), {})

    # =============================================== T2 (WP-4) Timeline lens
    def test_timeline_is_gated_scoped_and_pbim_toned(self):
        """The Timeline read-model is officer-gated, company-scoped, and hands
        the lens pbim TONES rather than the legacy facade's 2013 hexes."""
        mon = self._day(0)
        self._att(mon, hours=8)

        data = self.Hub.get_timeline(False, self.week.isoformat(), False)
        self.assertEqual(data['week_start'], self.week.isoformat())
        self.assertEqual(len(data['days']), 7)
        row = next((r for r in data['employees'] if r['id'] == self.emp.id), None)
        self.assertTrue(row, "the seeded employee must appear on the timeline")
        bars = row['days'][mon.isoformat()]['entries']
        self.assertTrue(bars, "a punched day must produce at least one bar")
        for b in bars:
            self.assertIn('tone', b, "every bar carries a pbim tone")
            self.assertIn(b['tone'], ('indigo', 'amber', 'rose', 'cyan', 'trip'))
            # geometry survives; it is maths, not chrome
            self.assertIn('bar_left', b)
            self.assertIn('bar_width', b)
        for l in data['legend']:
            self.assertIn('tone', l)
            self.assertNotIn('color', l,
                             "the legacy hex palette must not reach the client")

        # gate
        user = self.env['res.users'].create({
            'name': 'Plain Pat', 'login': 'p1a_plain_pat',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.Hub.with_user(user).get_timeline(False, self.week.isoformat(), False)

    def test_timeline_company_and_department_scope(self):
        other = self.env['res.company'].create({'name': 'P1a Timeline Co'})
        stranger = self.env['hr.employee'].create({
            'name': 'Aaa Stranger', 'company_id': other.id, 'tz': 'UTC'})
        data = self.Hub.get_timeline(False, self.week.isoformat(), False)
        ids = {r['id'] for r in data['employees']}
        self.assertIn(self.emp.id, ids)
        self.assertNotIn(stranger.id, ids,
                         "sudo reads must still be scoped to env.companies")

        only_dept = self.Hub.get_timeline(self.dept.id, self.week.isoformat(), False)
        self.assertTrue(all(
            self.env['hr.employee'].browse(r['id']).department_id == self.dept
            for r in only_dept['employees']))

        by_name = self.Hub.get_timeline(False, self.week.isoformat(), 'Tess Time')
        self.assertEqual({r['id'] for r in by_name['employees']}, {self.emp.id})

    def test_timeline_empty_cohort_does_not_fall_back_to_everyone(self):
        """An empty filter result must return an empty timeline — never the
        legacy facade's 'no employee_id => search everybody' branch."""
        data = self.Hub.get_timeline(False, self.week.isoformat(), 'zzz-nobody-zzz')
        self.assertEqual(data['employees'], [])
        self.assertEqual(data['legend'], [])
