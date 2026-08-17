# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b — T2: `get_control_data(employee_id=…)`.

The Today board's "File correction" door pins a person on the shared context
and hands over to the Time hub's Exceptions lens; the lens passes that pin here.
Three things have to hold or the hand-off is a lie:

  * WITH the argument the queue narrows to that person, and the payload says so
    (`person`), because a filtered queue that does not announce itself reads as
    "this person is clean";
  * WITHOUT it nothing changes at all — the standalone Attendance Control
    cockpit is a live surface and this is a purely additive argument;
  * the filter is a FILTER, not a lookup: a non-officer cannot use it to reach
    a colleague, and the corrections pipeline is deliberately left alone.
"""

from datetime import date, datetime, time, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestControlDataPersonFilter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Flow = cls.env['pb.attendance.flow']
        cls.company = cls.env.company

        # a safely-past Monday so the fixture never depends on the wall clock
        today = date.today()
        cls.day = today - timedelta(days=today.weekday() + 14)
        cls.df = cls.day
        cls.dt = cls.day + timedelta(days=6)

        cls.dept = cls.env['hr.department'].create({
            'name': 'P1b Filter', 'company_id': cls.company.id})
        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'P1b Filter Day', 'code': 'P1BF', 'start_hour': 8.0,
            'end_hour': 16.0, 'is_overnight': False, 'shift_type': 'morning',
            'company_id': cls.company.id})

        Emp = cls.env['hr.employee']
        cls.alice = Emp.create({'name': 'P1b Alice Absent', 'tz': 'UTC',
                                'company_id': cls.company.id,
                                'department_id': cls.dept.id})
        cls.bob = Emp.create({'name': 'P1b Bob Absent', 'tz': 'UTC',
                              'company_id': cls.company.id,
                              'department_id': cls.dept.id})
        # Two published shifts nobody punched against => one missing_punch each.
        for emp in (cls.alice, cls.bob):
            cls.env['hr.shift.planning'].create({
                'employee_id': emp.id,
                'shift_template_id': cls.tmpl.id,
                'date': cls.day,
                'start_datetime': datetime.combine(cls.day, time(8, 0)),
                'end_datetime': datetime.combine(cls.day, time(16, 0)),
                'state': 'published',
            })

    def _board(self, employee_id=False):
        return self.Flow.get_control_data(
            self.df.isoformat(), self.dt.isoformat(), self.dept.id, employee_id)

    # =================================================================== T2.1
    def test_filter_narrows_the_queue_to_one_person(self):
        everyone = self._board()
        ids = {x['employee_id'] for x in everyone['exceptions']}
        self.assertIn(self.alice.id, ids)
        self.assertIn(self.bob.id, ids)
        self.assertFalse(everyone['person'],
                         'no pin => no chip, or the board claims a filter it '
                         'is not applying')

        only_alice = self._board(self.alice.id)
        ids = {x['employee_id'] for x in only_alice['exceptions']}
        self.assertEqual(ids, {self.alice.id})
        self.assertEqual(only_alice['kpis']['open_exceptions'],
                         len(only_alice['exceptions']),
                         'the KPI must count the filtered queue, not the old one')

    def test_the_chip_names_the_person(self):
        board = self._board(self.alice.id)
        self.assertTrue(board['person'])
        self.assertEqual(board['person']['id'], self.alice.id)
        self.assertEqual(board['person']['name'], self.alice.name)

    def test_a_pin_matching_nobody_still_renders_a_clearable_chip(self):
        """"No exceptions for X" and "the queue is empty" are different
        sentences. Without the chip the officer cannot tell them apart — or
        clear the filter that caused it."""
        stranger = self.env['hr.employee'].create({
            'name': 'P1b Unscheduled Ulla', 'tz': 'UTC',
            'company_id': self.company.id})
        board = self._board(stranger.id)
        self.assertEqual(board['exceptions'], [])
        self.assertTrue(board['person'], 'the chip must survive an empty result')
        self.assertEqual(board['person']['id'], stranger.id)
        self.assertEqual(board['person']['name'], stranger.name)

    # =================================================================== T2.2
    def test_without_the_argument_nothing_changed(self):
        """Regression: the standalone cockpit calls this with three arguments
        (and, historically, with none at all)."""
        three = self.Flow.get_control_data(
            self.df.isoformat(), self.dt.isoformat(), self.dept.id)
        four = self._board(False)
        self.assertEqual(
            [x['employee_id'] for x in three['exceptions']],
            [x['employee_id'] for x in four['exceptions']])
        self.assertEqual(three['kpis'], four['kpis'])
        self.assertFalse(three['person'])

        bare = self.Flow.get_control_data()
        self.assertIn('exceptions', bare)
        self.assertIn('window', bare)
        self.assertFalse(bare['person'])

    def test_corrections_pipeline_is_not_filtered(self):
        """Deliberate: an officer triaging one person's exceptions must not
        lose sight of the approval queue they had in flight."""
        corr = self.env['hr.attendance.correction'].create({
            'employee_id': self.bob.id,
            'date': self.day,
            'correction_type': 'create',
            'reason': 'P1b pipeline visibility',
        })
        board = self._board(self.alice.id)
        self.assertIn(corr.id, [c['id'] for c in board['corrections']],
                      "another person's correction must stay in the pipeline")

    # =================================================================== T2.3
    def test_a_non_officer_cannot_pin_a_colleague(self):
        """The filter narrows a cohort the caller can already see; it is never
        a way to reach someone they cannot."""
        user = self.env['res.users'].create({
            'name': 'P1b Nora NonOfficer', 'login': 'p1b_nora_nonofficer',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.env['hr.employee'].create({
            'name': 'P1b Nora', 'tz': 'UTC', 'company_id': self.company.id,
            'user_id': user.id})
        board = self.Flow.with_user(user).get_control_data(
            self.df.isoformat(), self.dt.isoformat(), False, self.alice.id)
        self.assertFalse(board['is_officer'])
        self.assertEqual(
            [x for x in board['exceptions'] if x['employee_id'] == self.alice.id],
            [], "a pinned colleague must not become a way past the own-only rail")
        self.assertFalse(board['person']['name'],
                         'a non-officer must not get a name back from a pin')
