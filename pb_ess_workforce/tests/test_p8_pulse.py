# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T4 — the pulse: anonymous by construction, once a day, and floored.

The first three tests are the privacy contract, and they are written as
STRUCTURAL assertions rather than behavioural ones on purpose. "This payload did
not happen to contain an employee id" is a fact about one call; "this table has
no column that can hold one" is a fact about the design, and it is the one that
survives the next contributor.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import EssWorkforceCase
from ..models.shift_pulse import PULSE_FLOOR, PULSE_WINDOW_DAYS


@tagged('post_install', '-at_install')
class TestP8Pulse(EssWorkforceCase):

    def _pulse(self, user=None):
        return self.env['pb.shift.pulse'].with_user(user or self.user_a)

    def _rater_today(self, user=None):
        """The day the RATER is in, not the day the test runner is in.

        `fields.Date.context_today` resolves against the CALLING user's tz, and
        this suite's employees are deliberately UTC+7 while the test runner is
        not (W55/W63). At 21:07 UTC it is already tomorrow in Ho Chi Minh City,
        so a fixture that asks the runner for "today" and then compares it with
        what the employee's own submission stored is wrong for seven hours out
        of every twenty-four — green all morning, red all evening, and blamed on
        the code. Three P8 tests failed on exactly that.
        """
        return fields.Date.context_today(
            self.env['pb.shift.pulse'].with_user(user or self.user_a))

    _seed_n = 0

    def _seed(self, n, rating=4, department=None, days_ago=0):
        """Rows straight through the ORM — the only way to build a population
        without inventing n employees, and legitimate because the model's own
        submission path is tested separately."""
        Pulse = self.env['pb.shift.pulse'].sudo()
        day = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=days_ago)
        made = self.env['pb.shift.pulse']
        for i in range(n):
            made |= Pulse.create({
                'company_id': self.company.id,
                'department_id': department.id if department else False,
                'date': day,
                'rating': rating,
                # A MONOTONIC counter, not (day, index): two `_seed` calls in
                # one test with the same day and the same range of indices
                # produce the same digests, and the unique constraint is doing
                # its job when it refuses them.
                'uniq_hash': 'seed-%s-%s' % (id(self), self._next_seed()),
            })
        return made

    def _next_seed(self):
        type(self)._seed_n += 1
        return type(self)._seed_n

    # ======================================================= the contract
    def test_the_table_cannot_hold_an_employee(self):
        """The privacy contract, asserted on the SCHEMA. A relation to an
        employee, a user or a partner would each defeat the whole feature, and
        the point of this test is that it fails the moment somebody adds one
        "just for reporting"."""
        fields_ = self.env['pb.shift.pulse']._fields
        # `create_uid` / `write_uid` are the ORM's own audit columns: every
        # model has them and they cannot be removed. They are excluded HERE and
        # pinned to the superuser by
        # `test_the_row_is_written_by_the_superuser_not_the_rater` instead —
        # which is the assertion that actually protects them, and the one that
        # caught the `sudo()` hole.
        _ORM_AUDIT = ('create_uid', 'write_uid')
        forbidden = [n for n, f in fields_.items()
                     if n not in _ORM_AUDIT
                     and getattr(f, 'comodel_name', None) in (
                         'hr.employee', 'res.users', 'res.partner')]
        self.assertEqual(forbidden, [],
                         'pb.shift.pulse grew a link to a person: %s' % forbidden)
        for name in ('employee_id', 'user_id', 'partner_id', 'create_uid_ref'):
            self.assertNotIn(name, fields_)

    def test_the_row_is_written_by_the_superuser_not_the_rater(self):
        """`create_uid` and `write_uid` are identity columns the ORM fills in
        unconditionally, and they are the reason `submit_pulse` uses
        `with_user(SUPERUSER_ID)` rather than `sudo()`.

        This test found a real hole on its first live run: `sudo()` raises the
        `su` flag and leaves `env.uid` alone, so every pulse row was stamped
        with its rater's id in a table whose whole purpose is that no row is
        about a person. Both columns are asserted, because a future refactor
        that fixes one and forgets the other leaks just as completely.
        """
        before = self.env['pb.shift.pulse'].sudo().search([], order='id desc', limit=1)
        self._pulse().submit_pulse(4)
        row = self.env['pb.shift.pulse'].sudo().search([], order='id desc', limit=1)
        self.assertNotEqual(row, before, 'no pulse row was created')
        root = self.env.ref('base.user_root').id
        self.assertEqual(row.create_uid.id, root)
        self.assertEqual(row.write_uid.id, root)
        self.assertNotEqual(row.create_uid, self.user_a)

    def test_a_forged_identity_in_the_payload_is_ignored(self):
        """T2 for this endpoint. `submit_pulse` has no employee parameter and
        `**kw` swallows the attempt, so the row is about the CALLER's
        department whatever the caller claims."""
        self.emp_a.department_id = self.env['hr.department'].create(
            {'name': 'P8 Alpha Dept', 'company_id': self.company.id})
        self.emp_b.department_id = self.env['hr.department'].create(
            {'name': 'P8 Beta Dept', 'company_id': self.company.id})
        self._pulse(self.user_a).submit_pulse(
            5, 'nice', employee_id=self.emp_b.id, department_id=self.emp_b.department_id.id,
            company_id=999, date='1999-01-01', uniq_hash='chosen-by-me')
        row = self.env['pb.shift.pulse'].sudo().search([], order='id desc', limit=1)
        self.assertEqual(row.department_id, self.emp_a.department_id)
        self.assertEqual(row.company_id, self.company)
        self.assertEqual(row.date, self._rater_today())
        self.assertNotEqual(row.uniq_hash, 'chosen-by-me')

    def test_the_hash_field_is_system_restricted(self):
        field = self.env['pb.shift.pulse']._fields['uniq_hash']
        self.assertEqual(field.groups, 'base.group_system')

    def test_a_plain_employee_cannot_read_the_pulse_table(self):
        """An employee may CONTRIBUTE and may never READ. Otherwise a
        five-person department reads its own ratings and the anonymity is a
        story rather than a property."""
        self._pulse().submit_pulse(3)
        with self.assertRaises(Exception):
            self.env['pb.shift.pulse'].with_user(self.user_a).search([])

    # ========================================================= submission
    def test_a_rating_outside_one_to_five_is_refused(self):
        for bad in (0, 6, -1, 'x', None, ''):
            with self.assertRaises(UserError):
                self._pulse().submit_pulse(bad)
        self.assertEqual(self.env['pb.shift.pulse'].sudo().search_count([]), 0)

    def test_one_rating_per_person_per_day(self):
        self._pulse().submit_pulse(4)
        with self.assertRaises(UserError):
            self._pulse().submit_pulse(2)
        self.assertEqual(self.env['pb.shift.pulse'].sudo().search_count([]), 1)

    def test_two_people_may_rate_the_same_day(self):
        self._pulse(self.user_a).submit_pulse(4)
        self._pulse(self.user_b).submit_pulse(2)
        self.assertEqual(self.env['pb.shift.pulse'].sudo().search_count([]), 2)

    def test_the_same_person_may_rate_again_the_next_day(self):
        """Proven on the hash rather than by travelling in time: the digest is
        what the uniqueness rests on, so if today's and tomorrow's differ, the
        constraint cannot bind them together."""
        Pulse = self.env['pb.shift.pulse'].sudo()
        today = self._rater_today()          # the day submit_pulse will use
        h_today = Pulse._pulse_hash(self.company.id, self.emp_a.id, today)
        h_tmrw = Pulse._pulse_hash(self.company.id, self.emp_a.id,
                                   today + timedelta(days=1))
        self.assertNotEqual(h_today, h_tmrw)
        self._pulse().submit_pulse(4)
        Pulse.create({'company_id': self.company.id, 'date': today + timedelta(days=1),
                      'rating': 5, 'uniq_hash': h_tmrw})
        self.assertEqual(Pulse.search_count([]), 2)

    def test_the_database_and_not_a_python_check_is_the_guard(self):
        """W33.1 — `_sql_constraints` is silently ignored on Odoo 19 and the
        index simply would not exist. A Python check loses a race by
        construction, so the guard has to be a real unique index."""
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
             WHERE tablename = 'pb_shift_pulse' AND indexdef ILIKE '%unique%'
        """)
        defs = ' '.join(r[0] for r in self.env.cr.fetchall()).lower()
        self.assertIn('uniq_hash', defs,
                      'the double-submit guard is not a database constraint')

    def test_a_comment_is_optional_and_bounded(self):
        self._pulse().submit_pulse(5, 'x' * 900)
        row = self.env['pb.shift.pulse'].sudo().search([], order='id desc', limit=1)
        self.assertEqual(len(row.comment), 500)

    def test_a_user_without_an_employee_cannot_rate(self):
        with self.assertRaises(UserError):
            self._pulse(self.user_none).submit_pulse(4)

    # ============================================================= prompt
    def test_the_prompt_is_silent_when_no_shift_has_ended_today(self):
        self.assertFalse(self._pulse().get_my_prompt()['show'])

    def test_the_prompt_appears_after_a_shift_ended_today(self):
        today = self._rater_today()
        shift = self._shift(self.emp_a, today, start=0, end=1, state='published')
        # end it in the past whatever hour the suite runs at
        shift.sudo().write({
            'start_datetime': fields.Datetime.now() - timedelta(hours=9),
            'end_datetime': fields.Datetime.now() - timedelta(minutes=5)})
        prompt = self._pulse().get_my_prompt()
        self.assertTrue(prompt['show'])
        self.assertIn('–', prompt['shift'])

    def test_the_prompt_stops_once_the_person_has_answered(self):
        today = self._rater_today()
        shift = self._shift(self.emp_a, today, start=0, end=1, state='published')
        shift.sudo().write({
            'start_datetime': fields.Datetime.now() - timedelta(hours=9),
            'end_datetime': fields.Datetime.now() - timedelta(minutes=5)})
        self.assertTrue(self._pulse().get_my_prompt()['show'])
        self._pulse().submit_pulse(4)
        self.assertFalse(self._pulse().get_my_prompt()['show'],
                         'the prompt came back after it was answered')

    # ======================================================== aggregation
    def test_below_the_floor_the_server_returns_no_figures_at_all(self):
        """The floor is the feature. A client cannot be trusted to hide a
        number it has been handed, and a number that arrives is a number that
        leaks — so `avg` and `count` are ABSENT, not zeroed."""
        self._seed(PULSE_FLOOR - 1)
        tile = self.env['pb.shift.pulse'].get_pulse_tile()
        self.assertFalse(tile['shown'])
        self.assertNotIn('avg', tile)
        self.assertNotIn('count', tile)

    def test_at_the_floor_the_tile_appears(self):
        self._seed(PULSE_FLOOR, rating=4)
        tile = self.env['pb.shift.pulse'].get_pulse_tile()
        self.assertTrue(tile['shown'])
        self.assertEqual(tile['count'], PULSE_FLOOR)
        self.assertEqual(tile['avg'], 4.0)

    def test_the_average_is_the_average(self):
        self._seed(3, rating=5)
        self._seed(3, rating=1)
        tile = self.env['pb.shift.pulse'].get_pulse_tile()
        self.assertEqual(tile['count'], 6)
        self.assertEqual(tile['avg'], 3.0)

    def test_ratings_outside_the_window_are_not_counted(self):
        self._seed(PULSE_FLOOR + 3, days_ago=PULSE_WINDOW_DAYS + 2)
        self.assertFalse(
            self.env['pb.shift.pulse'].get_pulse_tile()['shown'],
            'a rating from a fortnight ago is still in the week window')

    def test_a_department_scope_uses_that_departments_ratings_only(self):
        dept = self.env['hr.department'].create(
            {'name': 'P8 Stores', 'company_id': self.company.id})
        other = self.env['hr.department'].create(
            {'name': 'P8 Depot', 'company_id': self.company.id})
        self._seed(PULSE_FLOOR, rating=5, department=dept)
        self._seed(PULSE_FLOOR, rating=1, department=other)
        self.assertEqual(
            self.env['pb.shift.pulse'].get_pulse_tile(dept.id)['avg'], 5.0)
        self.assertEqual(
            self.env['pb.shift.pulse'].get_pulse_tile(other.id)['avg'], 1.0)
        # and unscoped is everybody
        self.assertEqual(
            self.env['pb.shift.pulse'].get_pulse_tile()['count'], PULSE_FLOOR * 2)

    def test_a_department_below_the_floor_gets_nothing_even_when_the_company_clears_it(self):
        """The scope the officer is LOOKING at is the scope that must clear the
        floor. Falling back to the company-wide figure would silently answer a
        different question than the one on screen."""
        dept = self.env['hr.department'].create(
            {'name': 'P8 Tiny', 'company_id': self.company.id})
        self._seed(2, department=dept)
        self._seed(PULSE_FLOOR + 5)
        self.assertTrue(self.env['pb.shift.pulse'].get_pulse_tile()['shown'])
        self.assertFalse(self.env['pb.shift.pulse'].get_pulse_tile(dept.id)['shown'])

    # ========================================================= Today tile
    def test_the_today_board_carries_the_tile_and_stays_read_only(self):
        self._seed(PULSE_FLOOR, rating=4)
        admin = self.env.ref('base.user_admin')
        data = self.env['pb.today'].with_user(admin).get_today_data()
        self.assertIn('pulse', data)
        self.assertTrue(data['pulse']['shown'])
        self.assertEqual(data['pulse']['avg'], 4.0)
        # W25: the board must still have no write path anywhere in it
        for key in ('tiles', 'rows', 'day', 'truncated', 'updated_at',
                    'has_shifts'):
            self.assertIn(key, data, 'the pulse override lost %s' % key)

    def test_a_pulse_failure_never_costs_the_board(self):
        Pulse = type(self.env['pb.shift.pulse'])
        original = Pulse.get_pulse_tile

        def boom(self, department_id=False):
            raise RuntimeError('aggregation exploded')

        Pulse.get_pulse_tile = boom
        try:
            data = self.env['pb.today'].with_user(
                self.env.ref('base.user_admin')).get_today_data()
        finally:
            Pulse.get_pulse_tile = original
        self.assertEqual(data['pulse'], {'shown': False})
        self.assertIn('rows', data)
