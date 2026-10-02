# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — the `get_schedule_data` read model, and the promise that the
LEGACY payloads are untouched.

§3.2 is binding: `pb_schedule` may only ADD facade methods.

P2 justified that by the retired `shift_planning_grid` screen, which consumed
`get_grid_data`'s exact dict. P7 deleted that screen, and
`test_the_legacy_payload_shape_is_untouched` stays anyway: `get_grid_data` and
its siblings are the published contract of a BASE model that `pb_schedule`
inherits and `pb_close` reads, and a base model's payload does not get to
change shape because one of its consumers went away.

Everything runs inside the TransactionCase rollback: on a live database this
suite creates shifts and leaves and leaves NOTHING behind.
"""

from datetime import date, datetime, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_schedule.models.schedule_grid import WF_ROW_CAP


@tagged('post_install', '-at_install')
class TestScheduleGrid(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Grid = cls.env['hr.shift.planning.grid']
        cls.company = cls.env.company
        cls.dept = cls.env['hr.department'].create({
            'name': 'P2 Schedule Dept', 'company_id': cls.company.id})
        cls.other_dept = cls.env['hr.department'].create({
            'name': 'P2 Other Dept', 'company_id': cls.company.id})
        # An explicit, non-UTC timezone on purpose (P5 WP-0b): a roster time is
        # a WALL CLOCK, and every "08:00" below is only a real assertion if the
        # employee lives somewhere the stored UTC value is NOT 08:00.
        cls.emp = cls.env['hr.employee'].create({
            'name': 'P2 Zoe Scheduler', 'job_title': 'Line lead',
            'tz': 'Asia/Ho_Chi_Minh',
            'department_id': cls.dept.id, 'company_id': cls.company.id})
        cls.emp2 = cls.env['hr.employee'].create({
            'name': 'P2 Yann Elsewhere', 'job_title': 'Packer',
            'tz': 'Asia/Ho_Chi_Minh',
            'department_id': cls.other_dept.id, 'company_id': cls.company.id})
        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'P2 Day', 'code': 'P2DAY', 'shift_type': 'morning',
            'start_hour': 8.0, 'end_hour': 17.0, 'break_duration': 1.0,
            'color': 3, 'company_id': cls.company.id})
        # a Monday, comfortably clear of "today" so no compliance recompute
        # depends on the wall clock
        cls.week = date(2026, 3, 2)

    def _shift(self, employee, day, state='draft', tmpl=None):
        tmpl = tmpl or self.tmpl
        start, end = self.Grid._pb_shift_window(
            tmpl, day, self.Grid._pb_shift_tzname(employee))
        rec = self.env['hr.shift.planning'].create({
            'employee_id': employee.id,
            'shift_template_id': tmpl.id,
            'date': day,
            'start_datetime': start,
            'end_datetime': end,
        })
        if state != 'draft':
            rec.state = state
        return rec

    def _data(self, **kw):
        args = {'week_start_str': self.week.isoformat(),
                'department_id': self.dept.id, 'num_days': 7, 'search': ''}
        args.update(kw)
        return self.Grid.get_schedule_data(**args)

    # ---------------------------------------------------------- the shape
    def test_the_payload_carries_every_documented_key(self):
        data = self._data()
        for key in ('week_start', 'week_end', 'num_days', 'days', 'employees',
                    'open_shifts', 'templates', 'conflicts', 'truncated',
                    'row_cap', 'counts'):
            self.assertIn(key, data, 'get_schedule_data must return %r' % key)
        self.assertEqual(len(data['days']), 7)
        self.assertEqual(data['week_start'], self.week.isoformat())
        self.assertEqual(data['week_end'], (self.week + timedelta(days=6)).isoformat())
        self.assertEqual(data['row_cap'], WF_ROW_CAP)

    def test_a_day_column_knows_what_kind_of_day_it_is(self):
        days = self._data()['days']
        self.assertEqual([d['dow'] for d in days], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual([d['is_weekend'] for d in days],
                         [False] * 5 + [True, True])

    def test_fortnight_widens_the_window_from_the_same_week(self):
        data = self._data(num_days=14)
        self.assertEqual(data['num_days'], 14)
        self.assertEqual(len(data['days']), 14)
        self.assertEqual(data['week_start'], self.week.isoformat())
        self.assertEqual(data['week_end'],
                         (self.week + timedelta(days=13)).isoformat())

    def test_an_unknown_span_falls_back_to_a_week(self):
        """The span is a UI toggle; a hand-crafted RPC must not be able to ask
        for a 400-day roster."""
        self.assertEqual(self._data(num_days=400)['num_days'], 7)

    # ------------------------------------------------------------- shifts
    def test_a_shift_lands_on_its_employee_and_its_day(self):
        day = self.week + timedelta(days=1)
        shift = self._shift(self.emp, day)
        row = self._row(self._data())
        cards = row['shifts'].get(day.isoformat())
        self.assertTrue(cards, 'the shift must be on Tuesday')
        card = cards[0]
        self.assertEqual(card['id'], shift.id)
        self.assertEqual(card['state'], 'draft')
        self.assertEqual(card['template_name'], 'P2 Day')
        self.assertEqual(card['color'], 3)
        # HH:MM, not the legacy "8am" — every P0/P1 surface prints 24h
        self.assertEqual(card['start'], '08:00')
        self.assertEqual(card['end'], '17:00')
        self.assertAlmostEqual(card['planned_hours'], 8.0, places=2)

    def test_cancelled_shifts_are_not_on_the_roster(self):
        day = self.week + timedelta(days=2)
        shift = self._shift(self.emp, day)
        shift.state = 'cancelled'
        row = self._row(self._data())
        self.assertFalse(row['shifts'].get(day.isoformat()))

    def test_counts_add_up(self):
        self._shift(self.emp, self.week)
        self._shift(self.emp, self.week + timedelta(days=1), state='published')
        counts = self._data()['counts']
        self.assertEqual(counts['shifts'], 2)
        self.assertEqual(counts['draft'], 1)
        self.assertEqual(counts['published'], 1)

    def test_overlapping_shifts_are_reported_as_conflicts(self):
        day = self.week + timedelta(days=3)
        a = self._shift(self.emp, day)
        b = self._shift(self.emp, day)
        data = self._data()
        self.assertTrue(data['conflicts'], 'two 08:00-17:00 shifts must conflict')
        self.assertEqual(data['counts']['conflicts'], len(data['conflicts']))
        flagged = {c['id'] for c in self._row(data)['shifts'][day.isoformat()]
                   if c['conflict']}
        self.assertEqual(flagged, {a.id, b.id})

    # ------------------------------------------------------------ filters
    def test_the_department_filter_scopes_the_rows(self):
        names = [r['name'] for r in self._data()['employees']]
        self.assertIn('P2 Zoe Scheduler', names)
        self.assertNotIn('P2 Yann Elsewhere', names)

    def test_search_is_applied_on_the_SERVER(self):
        """A client-side filter over a CAPPED list would search only the rows
        that happened to survive the cap — worse than no search at all."""
        data = self._data(department_id=False, search='P2 Yann Elsewhere')
        names = [r['name'] for r in data['employees']]
        self.assertIn('P2 Yann Elsewhere', names)
        self.assertNotIn('P2 Zoe Scheduler', names)

    def test_the_row_budget_is_respected(self):
        data = self._data(department_id=False)
        self.assertLessEqual(len(data['employees']), WF_ROW_CAP)
        self.assertEqual(data['row_cap'], WF_ROW_CAP)
        self.assertGreaterEqual(data['truncated'], 0)

    def test_people_with_shifts_survive_the_cap(self):
        """The cap must bite where the information is not. Someone scheduled
        this week is never dropped in favour of an alphabetically earlier
        colleague with an empty row."""
        self._shift(self.emp, self.week)
        data = self._data(department_id=False)
        self.assertIn(self.emp.id, [r['id'] for r in data['employees']])

    # -------------------------------------------------------------- leave
    def test_approved_leave_paints_the_square(self):
        day = self.week + timedelta(days=4)
        # A type that needs no allocation — see test_warnings._leave_type for
        # why `search([], limit=1)` is a trap here.
        leave_type = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', False)], limit=1)
        if not leave_type:
            leave_type = self.env['hr.leave.type'].sudo().create({
                'name': 'P2 Grid Probe Leave', 'requires_allocation': False})
        leave = self.env['hr.leave'].sudo().create({
            'name': 'P2 leave probe',
            'employee_id': self.emp.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': day,
            'request_date_to': day,
        })
        leave.sudo().write({'state': 'validate'})
        row = self._row(self._data())
        cell = row['leaves'].get(day.isoformat())
        self.assertTrue(cell, 'an approved leave must overlay its day')
        self.assertTrue(cell['is_approved'])

    # ------------------------------------------------- the legacy promise
    def test_the_legacy_payload_shape_is_untouched(self):
        """§3.2: `pb_schedule` ADDS. The retired grid still consumes this dict
        and a "small improvement" here breaks a surface nobody is watching."""
        legacy = self.Grid.get_grid_data(self.week.isoformat(), self.dept.id)
        for key in ('days', 'employees', 'templates', 'open_shifts',
                    'warnings', 'summary', 'week_start', 'week_end'):
            self.assertIn(key, legacy, 'legacy get_grid_data lost %r' % key)
        for key in ('total_shifts', 'published', 'draft', 'completed',
                    'total_hours', 'open_shifts', 'warnings',
                    'leave_approved', 'leave_pending'):
            self.assertIn(key, legacy['summary'],
                          'the legacy 9-metric summary lost %r' % key)
        if legacy['employees']:
            for key in ('id', 'name', 'job_title', 'avatar_url', 'total_hours',
                        'contracted_hours', 'shifts', 'leaves'):
                self.assertIn(key, legacy['employees'][0])

    # ------------------------------------------------------------ helpers
    def _row(self, data):
        for r in data['employees']:
            if r['id'] == self.emp.id:
                return r
        self.fail('the seeded employee is not on the roster')

    # ------------------------------------------------------- shift window
    def test_the_shift_window_matches_the_create_path_exactly(self):
        """The warning engine predicts a row `quick_create_shift` will write;
        if the two disagree by a minute the warnings are about a shift nobody
        is making.

        P5 WP-0b moved BOTH sides onto UTC, so the identity claim is the same
        claim and the absolute values are the ones the column is supposed to
        hold: 22:00 in Ho Chi Minh City is 15:00 UTC the same evening, and an
        overnight 06:00 end is 23:00 UTC on the DAY OF THE SHIFT — which is
        exactly the midnight crossing that makes storing a wall clock as UTC a
        real defect rather than a cosmetic one.
        """
        night = self.env['hr.shift.template'].create({
            'name': 'P2 Night', 'code': 'P2NIGHT', 'shift_type': 'night',
            'start_hour': 22.0, 'end_hour': 6.0, 'break_duration': 0.5,
            'is_overnight': True, 'company_id': self.company.id})
        day = self.week + timedelta(days=5)
        tzname = self.Grid._pb_shift_tzname(self.emp2)
        self.assertEqual(tzname, 'Asia/Ho_Chi_Minh')
        start, end = self.Grid._pb_shift_window(night, day, tzname)
        self.assertEqual(start, datetime(day.year, day.month, day.day, 15, 0))
        self.assertEqual(end, datetime(day.year, day.month, day.day, 23, 0))

        created = self.env['hr.shift.planning'].browse(
            self.Grid.quick_create_shift(self.emp2.id, day.isoformat(), night.id))
        self.assertEqual(created.start_datetime, start)
        self.assertEqual(created.end_datetime, end)
        # and it reads back as the wall clock the planner typed
        self.assertEqual(self.Grid._pb_hhmm(created.start_datetime, tzname), '22:00')
        self.assertEqual(self.Grid._pb_hhmm(created.end_datetime, tzname), '06:00')

    # ------------------------------------------------- P5 WP-0b: local time
    def test_a_shift_prints_the_employees_wall_clock_not_utc(self):
        """The roster said 01:00 for every 08:00 Vietnamese shift — not a
        rounding error, a different shift. Same family as W51/W55: pb_today,
        pb_time_hub and the exception engine all localize before they say a
        time out loud, and the roster is the surface a planner reads first."""
        day = self.week + timedelta(days=1)
        shift = self._shift(self.emp, day)
        # the STORE is UTC (08:00 ICT = 01:00 UTC) …
        self.assertEqual(shift.start_datetime.hour, 1)
        self.assertEqual(shift.end_datetime.hour, 10)
        # … and the CARD is the employee's morning
        card = self._row(self._data())['shifts'][day.isoformat()][0]
        self.assertEqual(card['start'], '08:00')
        self.assertEqual(card['end'], '17:00')

    def test_the_cost_strip_keys_the_same_local_day_as_the_card(self):
        """A shift whose UTC start lands on the previous calendar day must
        still be counted on the day its card is drawn on — the strip keys the
        roster DAY, and the two may not disagree."""
        day = self.week + timedelta(days=2)
        early = self.env['hr.shift.template'].create({
            'name': 'P2 Early', 'code': 'P2EARLY', 'shift_type': 'morning',
            'start_hour': 6.0, 'end_hour': 14.0, 'break_duration': 0.0,
            'company_id': self.company.id})
        shift = self._shift(self.emp, day, state='published', tmpl=early)
        # 06:00 ICT is 23:00 UTC on the PREVIOUS calendar day
        self.assertEqual(shift.start_datetime.date(), day - timedelta(days=1))
        self.assertEqual(shift.start_datetime.hour, 23)

        data = self._data()
        card = self._row(data)['shifts'][day.isoformat()][0]
        self.assertEqual(card['start'], '06:00')
        by_day = {d['date']: d for d in data['stats']['days']}
        self.assertEqual(by_day[day.isoformat()]['shifts'], 1)
        self.assertEqual(
            by_day[(day - timedelta(days=1)).isoformat()]['shifts'], 0)
