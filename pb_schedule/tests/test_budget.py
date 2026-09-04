# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — T2: the labour budget and the cost strip.

Three things are being pinned:

  * the ARITHMETIC — Σ(planned_hours × rate) per day, actual cost only on days
    that have already happened, and a rateless employee counted rather than
    quietly averaged away;
  * the UNIQUENESS RULE, including the case a plain SQL UNIQUE cannot see
    (W30: PostgreSQL treats NULLs as distinct, so two company-wide rows for the
    same week would slip straight through the constraint);
  * the GATES — officer reads, manager writes, and the facade cannot be used to
    walk around the model's own check.
"""

from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestScheduleBudget(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Grid = cls.env['hr.shift.planning.grid']
        cls.Budget = cls.env['pb.schedule.budget']
        cls.company = cls.env.company
        cls.dept = cls.env['hr.department'].create({
            'name': 'P2 Budget Dept', 'company_id': cls.company.id})
        cls.week = date(2026, 3, 2)          # a Monday

    # --------------------------------------------------------------- CRUD
    def test_a_budget_snaps_to_the_monday_of_its_week(self):
        """A row created off-Monday would never match the strip's lookup."""
        b = self.Budget.create({
            'company_id': self.company.id,
            'department_id': self.dept.id,
            'week_start': self.week + timedelta(days=3),   # a Thursday
            'amount': 1000.0,
        })
        self.assertEqual(b.week_start, self.week)

    def test_the_same_scope_and_week_cannot_be_budgeted_twice(self):
        self.Budget.create({
            'company_id': self.company.id,
            'department_id': self.dept.id,
            'week_start': self.week, 'amount': 1000.0})
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Budget.create({
                    'company_id': self.company.id,
                    'department_id': self.dept.id,
                    'week_start': self.week, 'amount': 2000.0})

    def test_the_unique_constraint_really_exists_in_postgres(self):
        """W33 — Odoo 19 IGNORES `_sql_constraints = [...]` (one WARNING among
        hundreds, then nothing), so a model-level assertion proves nothing about
        the database. Read the catalogue."""
        self.env.cr.execute("""
            SELECT conname FROM pg_constraint
             WHERE conrelid = 'pb_schedule_budget'::regclass
               AND contype = 'u'
        """)
        names = {r[0] for r in self.env.cr.fetchall()}
        self.assertTrue(
            any('scope_week_uniq' in n for n in names),
            'the uniqueness constraint is missing from PostgreSQL; found %s'
            % (sorted(names) or 'none'))

    def test_two_company_wide_rows_are_refused_too(self):
        """W30 — the case the SQL constraint structurally cannot catch."""
        self.Budget.create({
            'company_id': self.company.id, 'department_id': False,
            'week_start': self.week, 'amount': 1000.0})
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.Budget.create({
                    'company_id': self.company.id, 'department_id': False,
                    'week_start': self.week, 'amount': 2000.0})

    def test_a_department_row_and_a_company_row_can_coexist(self):
        self.Budget.create({
            'company_id': self.company.id, 'department_id': False,
            'week_start': self.week, 'amount': 9000.0})
        rec = self.Budget.create({
            'company_id': self.company.id, 'department_id': self.dept.id,
            'week_start': self.week, 'amount': 1000.0})
        self.assertTrue(rec.id)

    def test_a_negative_budget_is_refused(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.Budget.create({
                    'company_id': self.company.id,
                    'department_id': self.dept.id,
                    'week_start': self.week, 'amount': -5.0})

    # ------------------------------------------------------- facade CRUD
    def test_set_budget_creates_then_updates_the_same_row(self):
        first = self.Grid.set_budget(self.week.isoformat(), self.dept.id, 1500)
        again = self.Grid.set_budget(self.week.isoformat(), self.dept.id, 2500)
        self.assertEqual(first, again, 'set_budget must UPDATE, not duplicate')
        self.assertAlmostEqual(self.Budget.browse(first).amount, 2500.0, places=2)

    def test_clear_budget_removes_exactly_that_scope(self):
        self.Grid.set_budget(self.week.isoformat(), self.dept.id, 1500)
        self.Grid.set_budget(self.week.isoformat(), False, 9000)
        gone = self.Grid.clear_budget(self.week.isoformat(), self.dept.id)
        self.assertEqual(gone, 1)
        self.assertTrue(self.Budget.search([
            ('week_start', '=', self.week), ('department_id', '=', False)]))

    # -------------------------------------------------------------- gates
    def test_an_officer_may_read_but_not_write(self):
        officer = self._officer_user()
        Budget = self.Budget.with_user(officer)
        self.assertFalse(Budget._pb_can_edit(),
                         'an attendance officer is not a budget manager')
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                Budget.create({
                    'company_id': self.company.id,
                    'department_id': self.dept.id,
                    'week_start': self.week, 'amount': 1.0})

    def test_the_facade_cannot_be_used_to_walk_round_the_gate(self):
        """The manager check lives on the MODEL. A helper on the officer-gated
        facade must not become a second, softer door to the same table."""
        officer = self._officer_user()
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                self.Grid.with_user(officer).set_budget(
                    self.week.isoformat(), self.dept.id, 1000)

    def test_an_attendance_manager_may_write(self):
        mgr = self._manager_user()
        rec_id = self.Grid.with_user(mgr).set_budget(
            self.week.isoformat(), self.dept.id, 4200)
        self.assertAlmostEqual(self.Budget.browse(rec_id).amount, 4200.0, places=2)

    # ---------------------------------------------------------- the strip
    def test_the_strip_costs_what_the_roster_costs(self):
        emp, rate = self._employee_with_rate(wage=17600.0)
        tmpl = self.env['hr.shift.template'].create({
            'name': 'P2 Cost', 'code': 'P2COST', 'shift_type': 'morning',
            'start_hour': 8.0, 'end_hour': 17.0, 'break_duration': 1.0,
            'company_id': self.company.id})
        day = self.week + timedelta(days=1)
        start, end = self.Grid._pb_shift_window(tmpl, day)
        self.env['hr.shift.planning'].create({
            'employee_id': emp.id, 'shift_template_id': tmpl.id, 'date': day,
            'start_datetime': start, 'end_datetime': end})

        stats = self.Grid.get_schedule_data(
            self.week.isoformat(), self.dept.id, 7, '')['stats']
        by_day = {d['date']: d for d in stats['days']}
        cell = by_day[day.isoformat()]
        self.assertAlmostEqual(cell['hours'], 8.0, places=1)
        self.assertAlmostEqual(cell['cost'], 8.0 * rate, places=2)
        self.assertAlmostEqual(stats['total_cost'], 8.0 * rate, places=2)
        self.assertEqual(stats['no_rate'], 0)

    def test_a_future_day_reports_no_actual_cost_rather_than_zero(self):
        """Printing 0 next to a scheduled figure reads as "we spent nothing",
        not "this has not happened yet"."""
        future = date.today() + timedelta(days=30)
        monday = future - timedelta(days=future.weekday())
        stats = self.Grid.get_schedule_data(
            monday.isoformat(), self.dept.id, 7, '')['stats']
        self.assertTrue(all(d['actual_cost'] is None for d in stats['days']),
                        'a future day must carry no actual figure at all')

    def test_a_rateless_employee_is_counted_not_averaged(self):
        emp = self.env['hr.employee'].create({
            'name': 'P2 No Contract', 'department_id': self.dept.id,
            'company_id': self.company.id})
        tmpl = self.env['hr.shift.template'].create({
            'name': 'P2 NoRate', 'code': 'P2NR', 'shift_type': 'morning',
            'start_hour': 9.0, 'end_hour': 17.0, 'break_duration': 0.0,
            'company_id': self.company.id})
        day = self.week + timedelta(days=2)
        start, end = self.Grid._pb_shift_window(tmpl, day)
        self.env['hr.shift.planning'].create({
            'employee_id': emp.id, 'shift_template_id': tmpl.id, 'date': day,
            'start_datetime': start, 'end_datetime': end})
        stats = self.Grid.get_schedule_data(
            self.week.isoformat(), self.dept.id, 7, '')['stats']
        self.assertEqual(stats['no_rate'], 1)
        self.assertAlmostEqual(stats['total_cost'], 0.0, places=2)
        self.assertGreater(stats['total_hours'], 0.0,
                           'the HOURS are still real even with no rate')

    def test_cost_covers_the_whole_scope_not_just_the_visible_page(self):
        """The rate cohort is every employee WITH A SHIFT, not the capped page
        of rows. Keying rates off the visible list would silently zero the
        hours of everyone past row 200 and count them as "no rate" — a cost
        total that quietly shrinks as a department grows."""
        import inspect

        from odoo.addons.pb_schedule.models import schedule_grid
        src = inspect.getsource(schedule_grid.ShiftPlanningGrid._pb_stats)
        self.assertIn('assigned.employee_id.ids', src,
                      'rates must be keyed off the shifts, not the page')
        self.assertNotIn('_pb_rates(employees', src)

    def test_no_budget_row_means_no_budget_block(self):
        stats = self.Grid.get_schedule_data(
            self.week.isoformat(), self.dept.id, 7, '')['stats']
        self.assertIsNone(stats['budget'],
                          'an absent budget must not become a zero budget')

    def test_a_fortnight_reports_how_many_weeks_were_budgeted(self):
        self.Grid.set_budget(self.week.isoformat(), self.dept.id, 1000)
        stats = self.Grid.get_schedule_data(
            self.week.isoformat(), self.dept.id, 14, '')['stats']
        self.assertEqual(stats['budget']['weeks_in_span'], 2)
        self.assertEqual(stats['budget']['weeks_budgeted'], 1)

        self.Grid.set_budget((self.week + timedelta(days=7)).isoformat(),
                             self.dept.id, 1200)
        stats = self.Grid.get_schedule_data(
            self.week.isoformat(), self.dept.id, 14, '')['stats']
        self.assertEqual(stats['budget']['weeks_budgeted'], 2)
        self.assertAlmostEqual(stats['budget']['amount'], 2200.0, places=2)

    def test_the_strip_never_publishes_a_per_person_rate(self):
        """W12: the cost instrument exports AGGREGATES. An attendance officer
        must not learn a colleague's wage from a roster."""
        emp, _rate = self._employee_with_rate(wage=17600.0)
        data = self.Grid.get_schedule_data(
            self.week.isoformat(), self.dept.id, 7, '')
        blob = repr(data)
        self.assertNotIn('rate', data['stats'])
        for row in data['employees']:
            self.assertNotIn('rate', row)
            self.assertNotIn('wage', row)
            self.assertNotIn('cost', row)
        self.assertNotIn("'wage'", blob)

    # ------------------------------------------------------------ helpers
    def _officer_user(self):
        return self.env['res.users'].create({
            'name': 'P2 Officer', 'login': 'p2_officer_probe',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
            ])],
        })

    def _manager_user(self):
        return self.env['res.users'].create({
            'name': 'P2 Manager', 'login': 'p2_manager_probe',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
                self.env.ref('hr_attendance.group_hr_attendance_manager').id,
            ])],
        })

    def _employee_with_rate(self, wage):
        cal = self.env['resource.calendar'].create({
            'name': 'P2 Budget Calendar', 'company_id': self.company.id})
        cal.write({'hours_per_week': 40.0})
        emp = self.env['hr.employee'].create({
            'name': 'P2 Costed', 'department_id': self.dept.id,
            'company_id': self.company.id, 'resource_calendar_id': cal.id})
        contract = self.env['hr.contract'].create({
            'name': 'P2 budget contract', 'employee_id': emp.id,
            'date_start': '2026-01-01', 'wage': wage, 'state': 'open',
            'company_id': self.company.id, 'resource_calendar_id': cal.id,
        })
        return emp, contract._pb_hourly_rate()
