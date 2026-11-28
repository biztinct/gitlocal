# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — T3: the coverage resolution rules.

Four axes resolve in a fixed order (shift_coverage.py documents them), and each
one is a decision somebody will eventually want to change. So each one is
pinned:

  1. specific scope beats general — a department with its own rule is NOT also
     subject to the company's;
  2. a DATE row beats a weekday row for that day, and does not add to it;
  3. a day-total row is authoritative; without one the per-template rows sum;
  4. supply counts draft + published, never completed.

Plus the property that makes the instrument usable at all: **no rule means no
chip**. A department that has never stated a requirement must not be painted
rose against an implied zero.
"""

from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestShiftCoverage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Grid = cls.env['hr.shift.planning.grid']
        cls.Req = cls.env['hr.shift.coverage.requirement']
        cls.company = cls.env.company
        cls.dept = cls.env['hr.department'].create({
            'name': 'P2 Coverage Dept', 'company_id': cls.company.id})
        cls.week = date(2026, 3, 2)              # Monday
        cls.tuesday = cls.week + timedelta(days=1)
        cls.day_t = cls.env['hr.shift.template'].create({
            'name': 'P2 Cov Day', 'code': 'P2CVD', 'shift_type': 'morning',
            'start_hour': 8.0, 'end_hour': 16.0, 'break_duration': 0.0,
            'company_id': cls.company.id})
        cls.night_t = cls.env['hr.shift.template'].create({
            'name': 'P2 Cov Night', 'code': 'P2CVN', 'shift_type': 'night',
            'start_hour': 22.0, 'end_hour': 6.0, 'break_duration': 0.0,
            'is_overnight': True, 'company_id': cls.company.id})

    # ------------------------------------------------------------ helpers
    def _emp(self, name):
        return self.env['hr.employee'].create({
            'name': name, 'department_id': self.dept.id,
            'company_id': self.company.id})

    def _shift(self, emp, day, tmpl=None, state='published'):
        tmpl = tmpl or self.day_t
        start, end = self.Grid._pb_shift_window(tmpl, day)
        rec = self.env['hr.shift.planning'].create({
            'employee_id': emp.id, 'shift_template_id': tmpl.id, 'date': day,
            'start_datetime': start, 'end_datetime': end})
        if state != 'draft':
            rec.state = state
        return rec

    def _req(self, **vals):
        base = {'company_id': self.company.id, 'required_headcount': 1}
        base.update(vals)
        return self.Req.create(base)

    def _cov(self, department_id=None, num_days=7):
        dept = self.dept.id if department_id is None else department_id
        data = self.Grid.get_schedule_data(
            self.week.isoformat(), dept, num_days, '')
        return data['coverage']

    # ---------------------------------------------------- absent = absent
    def test_no_requirement_means_no_coverage_at_all(self):
        self._shift(self._emp('P2 Cov A'), self.tuesday)
        self.assertIsNone(self._cov(),
                          'an absent rule must not become a requirement of zero')

    # -------------------------------------------------------------- rule 4
    def test_gap_exact_and_surplus(self):
        self._req(department_id=self.dept.id, weekday='1',
                  required_headcount=2)          # Tuesday needs 2
        cov = self._cov()
        cell = cov[self.tuesday.isoformat()]
        self.assertEqual((cell['required'], cell['scheduled'], cell['state']),
                         (2, 0, 'gap'))
        self.assertEqual(cell['gap'], 2)

        self._shift(self._emp('P2 Cov B'), self.tuesday)
        self._shift(self._emp('P2 Cov C'), self.tuesday)
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual((cell['scheduled'], cell['state']), (2, 'exact'))

        self._shift(self._emp('P2 Cov D'), self.tuesday)
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual((cell['scheduled'], cell['state'], cell['surplus']),
                         (3, 'surplus', 1))

    def test_supply_is_draft_plus_published_and_not_completed(self):
        """§3.5 rule 4. pb_demo COMPLETES every past punched shift, so counting
        completed rows would turn coverage into a question the Exceptions queue
        already answers better."""
        self._req(department_id=self.dept.id, weekday='1', required_headcount=3)
        self._shift(self._emp('P2 Cov E'), self.tuesday, state='draft')
        self._shift(self._emp('P2 Cov F'), self.tuesday, state='published')
        self._shift(self._emp('P2 Cov G'), self.tuesday, state='completed')
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual(cell['scheduled'], 2,
                         'a completed shift is history, not coverage')

    # -------------------------------------------------------------- rule 2
    def test_a_date_row_beats_the_weekday_row_and_does_not_add_to_it(self):
        self._req(department_id=self.dept.id, weekday='1', required_headcount=2)
        self._req(department_id=self.dept.id, date=self.tuesday,
                  required_headcount=9)
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual(cell['required'], 9, 'the exception wins outright')

        # and the standing rule still governs the OTHER Tuesday of a fortnight
        cov = self._cov(num_days=14)
        next_tue = self.tuesday + timedelta(days=7)
        self.assertEqual(cov[next_tue.isoformat()]['required'], 2)

    # -------------------------------------------------------------- rule 1
    def test_a_department_rule_replaces_the_company_rule(self):
        self._req(department_id=False, weekday='1', required_headcount=10)
        self._req(department_id=self.dept.id, weekday='1', required_headcount=3)
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual(cell['required'], 3,
                         'specific beats general — it does not add to it')

    def test_the_company_rule_applies_when_the_department_has_none(self):
        self._req(department_id=False, weekday='1', required_headcount=10)
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual(cell['required'], 10)

    # -------------------------------------------------------------- rule 3
    def test_per_template_rows_sum_into_the_day_total(self):
        self._req(department_id=self.dept.id, weekday='1',
                  template_id=self.day_t.id, required_headcount=2)
        self._req(department_id=self.dept.id, weekday='1',
                  template_id=self.night_t.id, required_headcount=1)
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual(cell['required'], 3)
        self.assertEqual(len(cell['per_template']), 2)

    def test_a_day_total_row_is_authoritative_over_the_template_rows(self):
        self._req(department_id=self.dept.id, weekday='1',
                  template_id=self.day_t.id, required_headcount=2)
        self._req(department_id=self.dept.id, weekday='1',
                  template_id=self.night_t.id, required_headcount=1)
        self._req(department_id=self.dept.id, weekday='1',
                  required_headcount=5)          # whole day
        cell = self._cov()[self.tuesday.isoformat()]
        self.assertEqual(cell['required'], 5)
        self.assertEqual(len(cell['per_template']), 2,
                         'the detail is still reported alongside the total')

    def test_a_per_template_gap_is_computed_against_that_template(self):
        self._req(department_id=self.dept.id, weekday='1',
                  template_id=self.night_t.id, required_headcount=2)
        self._shift(self._emp('P2 Cov H'), self.tuesday, tmpl=self.day_t)
        cell = self._cov()[self.tuesday.isoformat()]
        detail = cell['per_template'][0]
        self.assertEqual(detail['template_id'], self.night_t.id)
        self.assertEqual((detail['required'], detail['scheduled'], detail['gap']),
                         (2, 0, 2))

    def test_a_day_with_no_matching_rule_carries_no_cell(self):
        self._req(department_id=self.dept.id, weekday='1', required_headcount=2)
        cov = self._cov()
        self.assertIsNotNone(cov[self.tuesday.isoformat()])
        self.assertIsNone(cov[self.week.isoformat()],
                          'Monday has no rule, so Monday has no chip')

    # ------------------------------------------------------- model rails
    def test_a_rule_needs_exactly_one_of_weekday_or_date(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._req(department_id=self.dept.id)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._req(department_id=self.dept.id, weekday='1',
                          date=self.tuesday)

    def test_the_same_key_cannot_be_stated_twice(self):
        """Two rows for one key would make the answer depend on row order."""
        self._req(department_id=self.dept.id, weekday='1', required_headcount=2)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._req(department_id=self.dept.id, weekday='1',
                          required_headcount=4)

    # -------------------------------------------------------------- gates
    def test_an_officer_may_read_but_not_write(self):
        officer = self.env['res.users'].create({
            'name': 'P2 Cov Officer', 'login': 'p2_cov_officer',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
            ])]})
        self.assertFalse(self.Req.with_user(officer)._pb_can_edit())
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                self.Req.with_user(officer).create({
                    'company_id': self.company.id, 'weekday': '1',
                    'required_headcount': 1})
        # …but the facade's read door still works for them
        payload = self.Grid.with_user(officer).get_coverage_requirements(
            self.dept.id)
        self.assertFalse(payload['can_edit'])
        self.assertIn('rows', payload)

    def test_the_facade_cannot_be_used_to_walk_round_the_gate(self):
        officer = self.env['res.users'].create({
            'name': 'P2 Cov Officer 2', 'login': 'p2_cov_officer2',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
            ])]})
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                self.Grid.with_user(officer).save_coverage_requirement({
                    'department_id': self.dept.id, 'weekday': '1',
                    'required_headcount': 2})

    def test_a_requirement_from_another_company_cannot_be_touched(self):
        """`browse(id)` on an RPC argument is a cross-company door: the manager
        gate asks "may you edit coverage", never "may you edit THIS company's
        coverage", and this model carries no record rule."""
        other = self.env['res.company'].create({'name': 'P2 Other Co'})
        foreign = self._req(company_id=other.id, weekday='3',
                            required_headcount=7)
        # Creating a company as superuser ALSO grants it to the acting user, so
        # the scope has to be pinned explicitly — `_pb_company_ids()` reads
        # `env.companies`, which is `allowed_company_ids` from the context.
        Grid = self.Grid.with_context(allowed_company_ids=[self.company.id])
        self.assertNotIn(other.id, Grid._pb_company_ids(),
                         'the probe company must be outside the active scope')

        self.assertFalse(Grid.delete_coverage_requirement(foreign.id))
        self.assertTrue(foreign.exists(), 'the foreign row must survive')
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                Grid.save_coverage_requirement(
                    {'weekday': '3', 'required_headcount': 99}, foreign.id)
        self.assertEqual(foreign.required_headcount, 7)

    # --------------------------------------------------------- facade CRUD
    def test_save_then_delete_a_requirement_through_the_facade(self):
        rid = self.Grid.save_coverage_requirement({
            'department_id': self.dept.id, 'weekday': '2',
            'required_headcount': 4})
        self.assertTrue(rid)
        rows = self.Grid.get_coverage_requirements(self.dept.id)['rows']
        self.assertIn(rid, [r['id'] for r in rows])
        self.assertTrue(self.Grid.delete_coverage_requirement(rid))
        rows = self.Grid.get_coverage_requirements(self.dept.id)['rows']
        self.assertNotIn(rid, [r['id'] for r in rows])
