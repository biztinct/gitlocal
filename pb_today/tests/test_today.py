# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b — T1: the pb.today facade.

Four things are pinned here, because they are the four ways a triage board can
lie:

  * the TILE MATH — five states, the four buckets summing to the total, and
    `late` behaving as the cross-cut it is rather than a sixth bucket;
  * GRACE PARITY — the same employee flagged late by Today is flagged late by
    the exception engine. Both resolve their tolerance through
    `pb.attendance.rule._grace_for_company`, so this test would fail the moment
    someone reintroduced a hardcoded number (the legacy board's was 10 minutes,
    five off from every other Workforce surface);
  * ACCESS — non-officers are refused, exactly like the Time hub;
  * COMPANY SCOPE — a person outside `env.companies` never reaches the board.

Every assertion is scoped to a private department, so a live demo database's
own attendance story cannot move the numbers under the test.
"""

from datetime import date, datetime, time, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTodayFacade(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Today = cls.env['pb.today']
        cls.Att = cls.env['hr.attendance']
        cls.Shift = cls.env['hr.shift.planning']
        cls.company = cls.env.company

        # A fixed, safely-past Monday (two weeks back) so nothing here depends
        # on the wall clock — except the explicitly live-day test below.
        today = date.today()
        cls.day = today - timedelta(days=today.weekday() + 14)

        cls.dept = cls.env['hr.department'].create({
            'name': 'P1b Today', 'company_id': cls.company.id})
        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'P1b Day', 'code': 'P1BD', 'start_hour': 8.0, 'end_hour': 16.0,
            'is_overnight': False, 'shift_type': 'morning',
            'company_id': cls.company.id})

        def emp(name):
            return cls.env['hr.employee'].create({
                'name': name, 'company_id': cls.company.id, 'tz': 'UTC',
                'department_id': cls.dept.id, 'job_title': 'Operator'})

        cls.e_late = emp('P1b Late Larry')
        cls.e_missing = emp('P1b Missing Mia')
        cls.e_out = emp('P1b Doneby Dora')
        cls.e_in = emp('P1b Onshift Otto')
        cls.e_leave = emp('P1b Onleave Olga')

    # ------------------------------------------------------------- helpers
    @classmethod
    def _shift(cls, employee, d, state='published', actual_in=None):
        s = cls.Shift.create({
            'employee_id': employee.id,
            'shift_template_id': cls.tmpl.id,
            'date': d,
            'start_datetime': datetime.combine(d, time(8, 0)),
            'end_datetime': datetime.combine(d, time(16, 0)),
            'state': state,
        })
        if actual_in:
            s.actual_check_in = actual_in
        return s

    @classmethod
    def _att(cls, employee, d, start=time(8, 0), hours=8):
        ci = datetime.combine(d, start)
        return cls.Att.create({
            'employee_id': employee.id,
            'check_in': ci,
            'check_out': (ci + timedelta(hours=hours)) if hours else False,
        })

    def _board(self, day=None, department=True):
        return self.Today.get_today_data(
            self.dept.id if department else False,
            (day or self.day).isoformat())

    def _row(self, board, employee):
        return next((r for r in board['rows'] if r['id'] == employee.id), None)

    def _seed_a_day(self):
        """One of each state on `self.day`, all inside the private department."""
        d = self.day
        # LATE: shift 08:00, arrived 08:24 — past the 15-minute default grace.
        late_in = datetime.combine(d, time(8, 24))
        self._shift(self.e_late, d, actual_in=late_in)
        self._att(self.e_late, d, start=time(8, 24))
        # NOT STARTED: a published shift nobody punched against.
        self._shift(self.e_missing, d)
        # CHECKED OUT: on time, closed punch.
        self._shift(self.e_out, d, actual_in=datetime.combine(d, time(8, 0)))
        self._att(self.e_out, d)
        # ON SHIFT: an OPEN punch (no check_out).
        self._shift(self.e_in, d, actual_in=datetime.combine(d, time(8, 0)))
        self._att(self.e_in, d, hours=0)
        # ON LEAVE: approved leave covering the day.
        self._leave(self.e_leave, d)

    @classmethod
    def _leave(cls, employee, d):
        lt = cls.env['hr.leave.type'].sudo().with_context(
            active_test=False).search([('name', '=', 'P1b Today Leave')], limit=1)
        if not lt:
            lt = cls.env['hr.leave.type'].sudo().create({
                'name': 'P1b Today Leave',
                'requires_allocation': False,
                'leave_validation_type': 'hr',
                'allocation_validation_type': 'hr',
            })
        lv = cls.env['hr.leave'].sudo().create({
            'employee_id': employee.id,
            'holiday_status_id': lt.id,
            'request_date_from': d,
            'request_date_to': d,
            'name': 'P1b leave',
        })
        # Approve through the model's own action, never a state write.
        for _ in range(2):
            if lv.state == 'validate':
                break
            lv.action_approve()
        return lv

    # =================================================================== T1.1
    def test_tile_math_on_a_seeded_day(self):
        """Five states, and the four buckets add up to the total."""
        self._seed_a_day()
        board = self._board()
        t = board['tiles']

        self.assertEqual(t['total'], 5, 'exactly the five seeded people: %s'
                         % [r['name'] for r in board['rows']])
        self.assertEqual(t['on_shift'], 1)
        # TWO: Dora (on time) and Larry (late). Larry arrived at 08:24 and left
        # at 16:24, so his day is closed — being late does not put a person in a
        # different bucket, it tags the bucket they are already in.
        self.assertEqual(t['checked_out'], 2)
        self.assertEqual(t['not_started'], 1)
        self.assertEqual(t['on_leave'], 1)
        # `late` is a CROSS-CUT of the buckets, never a sixth bucket: Larry is
        # counted once in checked_out AND once in late.
        self.assertEqual(t['late'], 1)
        self.assertEqual(
            t['on_shift'] + t['checked_out'] + t['not_started'] + t['on_leave'],
            t['total'],
            'the four buckets must partition the cohort — late overlaps them')

        self.assertEqual(board['day'], self.day.isoformat())
        self.assertFalse(board['is_today'])
        self.assertEqual(board['truncated'], 0)

    def test_row_shape_and_states(self):
        self._seed_a_day()
        board = self._board()

        larry = self._row(board, self.e_late)
        self.assertTrue(larry['is_late'])
        self.assertEqual(larry['minutes_late'], 24)
        self.assertEqual(larry['check_in'], '08:24')
        self.assertEqual(larry['state'], 'checked_out')
        self.assertTrue(larry['can_correct'], 'a late row must offer the door')
        self.assertIn('08:00', larry['shift_label'])
        self.assertEqual(larry['dept'], self.dept.name)

        mia = self._row(board, self.e_missing)
        self.assertEqual(mia['state'], 'not_started')
        self.assertFalse(mia['is_late'],
                         'a PAST day with no punch is a missing punch, not a '
                         'late arrival — that story belongs to the exception engine')
        self.assertTrue(mia['can_correct'])

        otto = self._row(board, self.e_in)
        self.assertEqual(otto['state'], 'on_shift')
        self.assertEqual(otto['check_out'], '')

        dora = self._row(board, self.e_out)
        self.assertEqual(dora['state'], 'checked_out')
        self.assertFalse(dora['is_late'])
        self.assertEqual(dora['check_out'], '16:00')

        olga = self._row(board, self.e_leave)
        self.assertEqual(olga['state'], 'on_leave')
        self.assertTrue(olga['leave_type'])

    def test_rows_lead_with_the_people_who_need_a_decision(self):
        """The cap is a product decision (WF_ROW_CAP); the ORDER is what makes
        it survivable — a truncated list must never drop the late people."""
        self._seed_a_day()
        rows = self._board()['rows']
        self.assertEqual(rows[0]['id'], self.e_late.id)
        self.assertEqual(rows[1]['id'], self.e_missing.id,
                         'unresolved before resolved')

    # =================================================================== T1.2
    def test_late_agrees_with_the_exception_engine(self):
        """§2.5 — Today and Exceptions share ONE grace source.

        Both read `pb.attendance.rule._grace_for_company`: Today directly, the
        engine through `hr.shift.planning.compliance_status`. The same person
        must therefore be late on both surfaces, and only that person.
        """
        self._seed_a_day()
        board = self._board()
        late_ids = {r['id'] for r in board['rows'] if r['is_late']}

        emps = (self.e_late | self.e_missing | self.e_out
                | self.e_in | self.e_leave)
        rows = self.env['pb.attendance.exception.engine']._get_exceptions(
            emps, self.day, self.day)
        engine_late = {r['employee_id'] for r in rows if r['kind'] == 'late'}

        self.assertEqual(late_ids, {self.e_late.id})
        self.assertEqual(engine_late, late_ids,
                         'the two surfaces disagreed about who is late — the '
                         'grace source has drifted (§2.5)')

    def test_grace_is_configuration_not_a_constant(self):
        """Widen the rule and the same arrival stops being late — proof the
        number comes from pb.attendance.rule and is not hardcoded anywhere."""
        self._seed_a_day()
        self.assertTrue(self._row(self._board(), self.e_late)['is_late'])

        Rule = self.env['pb.attendance.rule'].sudo()
        rule = Rule._for_company(self.company)
        if rule and rule.company_id == self.company:
            rule.grace_in_minutes = 45
        else:
            # the shipped fallback row is GLOBAL; override it per company
            # rather than editing everyone's policy
            Rule.create({'name': 'P1b wide grace', 'company_id': self.company.id,
                         'grace_in_minutes': 45, 'grace_out_minutes': 15})

        self.assertFalse(self._row(self._board(), self.e_late)['is_late'],
                         'a 24-minute arrival must be inside a 45-minute grace')

    def test_a_live_shift_nobody_punched_is_late_only_once_the_clock_passes(self):
        """The live half of the board: the exception engine cannot see this
        case yet (the shift has not ended), which is why Today exists."""
        now = datetime.now()
        today = date.today()
        started = self._shift(
            self.e_missing, today, actual_in=None)
        started.write({
            'start_datetime': now - timedelta(hours=2),
            'end_datetime': now + timedelta(hours=6),
        })
        row = self._row(self._board(day=today), self.e_missing)
        self.assertTrue(row['is_late'])
        self.assertGreaterEqual(row['minutes_late'], 115)

        # ...and a shift that has not started yet is simply not started
        started.write({
            'start_datetime': now + timedelta(hours=2),
            'end_datetime': now + timedelta(hours=10),
        })
        row = self._row(self._board(day=today), self.e_missing)
        self.assertEqual(row['state'], 'not_started')
        self.assertFalse(row['is_late'])

    # =================================================================== T1.3
    def test_non_officer_rpc_is_refused(self):
        """Officer-gated, like the Time hub. Live Attendance was already
        officer-gated; the Workforce Dashboard whose counts this absorbs was
        NOT, so this is a deliberate narrowing (report §7)."""
        user = self.env['res.users'].create({
            'name': 'P1b Plain Pat', 'login': 'p1b_plain_pat',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.Today.with_user(user).get_today_data(False, self.day.isoformat())

    def test_officer_is_allowed(self):
        user = self.env['res.users'].create({
            'name': 'P1b Olive Officer', 'login': 'p1b_olive_officer',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_attendance.group_hr_attendance_officer').id,
            ])],
        })
        res = self.Today.with_user(user).get_today_data(False, self.day.isoformat())
        self.assertIn('tiles', res)

    # =================================================================== T1.4
    def test_cross_company_people_never_reach_the_board(self):
        """The board is scoped to `env.companies`, so the test has to PIN
        env.companies.

        `res.company.create()` adds the new company to the creating user's
        allowed companies, so a naive version of this test creates a second
        company, widens its own scope by doing so, and then reports a "leak"
        that is the facade correctly honouring the scope it was given. The
        context below is what makes the assertion mean what it says.
        """
        other = self.env['res.company'].create({'name': 'P1b Other Co'})
        stranger = self.env['hr.employee'].create({
            'name': 'P1b Stranger', 'company_id': other.id, 'tz': 'UTC'})
        self.Shift.create({
            'employee_id': stranger.id,
            'shift_template_id': self.tmpl.id,
            'date': self.day,
            'start_datetime': datetime.combine(self.day, time(8, 0)),
            'end_datetime': datetime.combine(self.day, time(16, 0)),
            'state': 'published',
            'company_id': other.id,
        })
        self._att(stranger, self.day)

        board = self.Today.with_context(
            allowed_company_ids=[self.company.id]).get_today_data(
                False, self.day.isoformat())
        self.assertNotIn(stranger.id, [r['id'] for r in board['rows']],
                         'an employee outside env.companies leaked onto the board')
        # ...and the same call WITH the other company allowed does see them, so
        # the assertion above is proving a scope, not an empty query.
        wide = self.Today.with_context(
            allowed_company_ids=[self.company.id, other.id]).get_today_data(
                False, self.day.isoformat())
        self.assertIn(stranger.id, [r['id'] for r in wide['rows']])

    # =================================================================== T1.5
    def test_department_filter_and_empty_day(self):
        self._seed_a_day()
        empty = self.env['hr.department'].create({
            'name': 'P1b Empty', 'company_id': self.company.id})
        board = self.Today.get_today_data(empty.id, self.day.isoformat())
        self.assertEqual(board['tiles']['total'], 0)
        self.assertEqual(board['rows'], [])
        self.assertFalse(board['has_shifts'])
        self.assertTrue(board['updated_at'], 'the board always says when it read')

    def test_day_defaults_to_today(self):
        board = self.Today.get_today_data(self.dept.id)
        self.assertEqual(board['day'], date.today().isoformat())
        self.assertTrue(board['is_today'])

    def test_draft_shifts_are_not_on_the_board(self):
        """An unpublished roster is a plan nobody committed to."""
        self._shift(self.e_missing, self.day, state='draft')
        board = self._board()
        self.assertEqual(board['tiles']['total'], 0,
                         'a draft shift must not put anyone on the board')
