# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RIZE W2 D1 — T6: the carry-forward watch.

Every assertion here is scoped to the fixture's OWN rows (R221): this suite
runs against a live demo database and "the job wrote nothing" asserted over a
whole table only passes on an empty one.
"""

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCarryWatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Watch = cls.env['pb.timeoff.carry.watch']
        cls.Log = cls.env['pb.timeoff.carry.log']
        cls.param = cls.env['ir.config_parameter'].sudo()
        cls.company = cls.env['res.company'].create({'name': 'D1 Carry Co'})
        cls.calendar = cls.company.resource_calendar_id
        cls.today = cls.env['pb.holidays']._today()

        cls.capped = cls.env['hr.leave.type'].create({
            'name': 'D1 Carry annual', 'requires_allocation': True,
            'leave_validation_type': 'hr', 'allocation_validation_type': 'hr',
            'company_id': cls.company.id, 'pb_carry_cap_days': 12.0})

        cls.boss_user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Carry Manager', 'login': 'demo.carry.boss.d1',
                'email': 'demo.carry.boss@example.com',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.boss = cls.env['hr.employee'].create({
            'name': 'DEMO Carry Manager', 'company_id': cls.company.id,
            'user_id': cls.boss_user.id})

        cls.rich = cls._person('DEMO Carry Rich', 14.0)
        cls.poor = cls._person('DEMO Carry Poor', 8.0)

        # THE CUT-OFF IS INSIDE THE WARNING WINDOW, worked out from the
        # SERVER's clock rather than written down (R36) — a fixed date stops
        # being in the future the year it arrives.
        cutoff = cls.today + relativedelta(months=3)
        cls.param.set_param('pb_timeoff.carry_cutoff',
                            cutoff.strftime('%m-%d'))
        cls.param.set_param('pb_timeoff.carry_warn_months', '6')
        cls.param.set_param('pb_timeoff.carry_watch', '1')

    @classmethod
    def _person(cls, name, days):
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id,
            'parent_id': cls.boss.id,
            'work_email': '%s@example.com' % name.lower().replace(' ', '.'),
            'resource_calendar_id': cls.calendar.id if cls.calendar else False})
        allocation = cls.env['hr.leave.allocation'].create({
            'name': 'DEMO carry allocation',
            'employee_id': employee.id,
            'holiday_status_id': cls.capped.id,
            'number_of_days': days,
            'date_from': cls.today - timedelta(days=30),
        })
        allocation.action_approve()
        return employee

    def _mine(self):
        return self.Log.search([('employee_id', 'in',
                                 [self.rich.id, self.poor.id])])

    def test_only_the_person_over_the_cap_is_warned_and_only_once(self):
        first = self.Watch.cron_carry_watch()
        self.assertTrue(first['window_open'])
        rows = self._mine()
        self.assertEqual(rows.mapped('employee_id'), self.rich,
                         'eight days is under a cap of twelve')
        # RUNNING IT TWICE DOES NOTHING THE SECOND TIME (R214/R184): the
        # question is which rows existed BEFORE this pass, asked once.
        self.Watch.cron_carry_watch()
        self.assertEqual(len(self._mine()), 1)

    def test_the_row_says_what_it_warned_about(self):
        self.Watch.cron_carry_watch()
        row = self._mine()
        self.assertEqual(row.leave_type_id, self.capped)
        self.assertEqual(row.cap_days, 12.0)
        self.assertGreaterEqual(row.days_left, 12.0)
        self.assertTrue(row.told_manager, 'the manager gets a note too')

    def test_both_the_person_and_their_manager_are_emailed(self):
        Mail = self.env['mail.mail']
        before = Mail.search_count([])
        self.Watch.cron_carry_watch()
        self.env.flush_all()
        self.assertGreaterEqual(Mail.search_count([]) - before, 2)

    def test_a_kind_with_no_cap_is_not_watched_at_all(self):
        """R76 — a cap is a PARAMETER and it ships at zero. What "too many
        days" is, is a business fact this code has no way to guess."""
        self.capped.pb_carry_cap_days = 0.0
        self.Watch.cron_carry_watch()
        self.assertFalse(self._mine())

    def test_switched_off_it_counts_and_writes_nothing(self):
        """R54 — a switch that is off and does not SAY so is reported as
        broken. Off, the job answers with the number it WOULD have acted on."""
        self.param.set_param('pb_timeoff.carry_watch', '0')
        try:
            result = self.Watch.cron_carry_watch()
        finally:
            self.param.set_param('pb_timeoff.carry_watch', '1')
        self.assertEqual(result['warned'], 0)
        self.assertGreaterEqual(result['would_have'], 1)
        self.assertFalse(self._mine())

    def test_outside_the_window_nothing_is_due(self):
        far = self.today + relativedelta(months=11)
        self.param.set_param('pb_timeoff.carry_cutoff', far.strftime('%m-%d'))
        self.param.set_param('pb_timeoff.carry_warn_months', '1')
        try:
            result = self.Watch.cron_carry_watch()
        finally:
            self.param.set_param('pb_timeoff.carry_warn_months', '6')
            self.param.set_param(
                'pb_timeoff.carry_cutoff',
                (self.today + relativedelta(months=3)).strftime('%m-%d'))
        self.assertFalse(result['window_open'])
        self.assertFalse(self._mine())

    def test_a_cut_off_nobody_can_read_falls_back_to_the_year_end(self):
        self.param.set_param('pb_timeoff.carry_cutoff', 'the last Friday')
        try:
            cutoff = self.Watch._cutoff_for(self.today)
        finally:
            self.param.set_param(
                'pb_timeoff.carry_cutoff',
                (self.today + relativedelta(months=3)).strftime('%m-%d'))
        self.assertEqual((cutoff.month, cutoff.day), (12, 31))

    def test_a_cut_off_already_gone_this_year_means_next_year(self):
        self.param.set_param('pb_timeoff.carry_cutoff', '01-01')
        try:
            cutoff = self.Watch._cutoff_for(self.today)
        finally:
            self.param.set_param(
                'pb_timeoff.carry_cutoff',
                (self.today + relativedelta(months=3)).strftime('%m-%d'))
        self.assertGreaterEqual(cutoff, self.today)

    def test_one_warning_per_person_per_kind_per_cut_off_is_enforced_in_sql(self):
        """`_sql_constraints` as a LIST is silently ignored on Odoo 19, so the
        idempotency claim would be a comment rather than a rule."""
        self.Watch.cron_carry_watch()
        row = self._mine()
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Log.create({
                    'employee_id': row.employee_id.id,
                    'leave_type_id': row.leave_type_id.id,
                    'cutoff_year': row.cutoff_year,
                })
