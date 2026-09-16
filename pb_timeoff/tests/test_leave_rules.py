# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RIZE W2 D1 — T4 and T5: time off in the past, and time off that has begun.

Both rules are written as REFUSALS, so both are tested from the side that is
refused AND from the side that is not. A guard that refuses everybody is not a
guard, it is an outage — and the two sides of each of these are exactly one
group apart.
"""

from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLeaveRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Leave = cls.env['hr.leave']
        # A DEDICATED company (R221), with the Standard 40h calendar the
        # company creates for itself — a bare calendar has no working hours,
        # every leave computes zero days and the core refuses to validate.
        cls.company = cls.env['res.company'].create({'name': 'D1 Rules Co'})
        cls.calendar = cls.company.resource_calendar_id

        cls.plain_type = cls.env['hr.leave.type'].create({
            'name': 'D1 Paid days', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'company_id': cls.company.id})
        cls.sick_type = cls.env['hr.leave.type'].create({
            'name': 'D1 Sick days', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'company_id': cls.company.id,
            'pb_backdate_ok': True, 'pb_backdate_alert': True})

        cls.officer = cls.env.ref('base.user_admin')
        cls.officer.write({'company_ids': [(4, cls.company.id)]})

        cls.staff = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Rules Asker', 'login': 'demo.rules.asker.d1',
                'email': 'demo.rules.asker@example.com',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'DEMO Rules Asker', 'company_id': cls.company.id,
            'user_id': cls.staff.id,
            'resource_calendar_id': cls.calendar.id if cls.calendar else False})

        # THE SERVER'S today (R36) — a test that writes the laptop's date into
        # a record a guard reads with the server's is a test that fails for a
        # reason that has nothing to do with the rule it guards.
        cls.today = cls.env['pb.holidays']._today()
        cls.last_week = cls.today - timedelta(days=7)

    def _as_staff(self):
        return self.Leave.with_user(self.staff).with_company(self.company)

    def _as_officer(self):
        return self.Leave.with_user(self.officer).with_company(self.company)

    def _vals(self, leave_type, start, days=0):
        return {
            'employee_id': self.employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': start,
            'request_date_to': start + timedelta(days=days),
            'name': 'DEMO rules fixture',
        }

    # ------------------------------------------------------------------ T4
    def test_an_ordinary_kind_cannot_be_asked_for_in_the_past(self):
        with self.assertRaises(UserError) as caught:
            self._as_staff().create(self._vals(self.plain_type, self.last_week))
        message = str(caught.exception)
        self.assertIn('HR', message, 'the refusal must say who can do it')
        self.assertIn('Sick', message,
                      'and it must name the way out, or it is a dead end')

    def test_sick_leave_can_be_and_says_so_on_the_record(self):
        leave = self._as_staff().create(
            self._vals(self.sick_type, self.last_week))
        self.assertTrue(leave.pb_backdated)

    def test_an_officer_may_enter_a_past_day_of_any_kind(self):
        leave = self._as_officer().create(
            self._vals(self.plain_type, self.last_week))
        self.assertTrue(leave.exists())
        self.assertTrue(leave.pb_backdated,
                        'the FACT is true whoever wrote it')

    def test_a_request_for_a_future_day_is_not_backdated(self):
        leave = self._as_staff().create(
            self._vals(self.plain_type, self.today + timedelta(days=5)))
        self.assertFalse(leave.pb_backdated)

    def test_the_board_shows_the_backdated_chip(self):
        self._as_staff().create(self._vals(self.sick_type, self.last_week))
        board = self.env['pb.timeoff'].with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id]).with_company(
                self.company).get_board()
        mine = [card for card in board['queue']
                if card['employee']['id'] == self.employee.id]
        self.assertTrue(mine, 'the request must be on the queue')
        self.assertTrue(any(card['backdated'] for card in mine))

    def test_the_hr_lead_is_told_once_and_the_to_do_does_not_mail_twice(self):
        """R183 — `mail.activity.create` emails the assignee itself unless
        `mail_activity_quick_update` is in the context, so a courtesy to-do
        beside our own email is two messages in the same second."""
        Mail = self.env['mail.mail']
        before = Mail.search_count([])
        leave = self._as_staff().create(
            self._vals(self.sick_type, self.last_week))
        self.env.flush_all()
        after = Mail.search_count([])
        self.assertLessEqual(
            after - before, 1,
            'one message about one thing, never the activity mail as well')
        todo = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.leave'), ('res_id', '=', leave.id)])
        self.assertTrue(todo, 'HR needs the request on their own list')

    def test_a_kind_that_says_do_not_tell_us_does_not(self):
        quiet = self.env['hr.leave.type'].create({
            'name': 'D1 Quiet sick days', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'company_id': self.company.id,
            'pb_backdate_ok': True, 'pb_backdate_alert': False})
        leave = self._as_staff().create(self._vals(quiet, self.last_week))
        todo = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.leave'), ('res_id', '=', leave.id)])
        self.assertFalse(todo)

    # ------------------------------------------------------------------ T5
    def _started_leave(self):
        """A leave that began yesterday, made as the system so the creation
        itself is not the thing under test.

        RE-BROWSED THROUGH A CLEAN RECORDSET, and that is not tidiness: the
        fixture is made with `leave_fast_create=True` and `with_user()` KEEPS
        the context, so every guard below would have been handed the very flag
        that switches it off. The first run of this file passed four tests for
        that reason and told nobody.
        """
        made = self.Leave.with_company(self.company).with_context(
            leave_fast_create=True).create(
                self._vals(self.sick_type, self.today - timedelta(days=1),
                           days=2))
        return self.Leave.browse(made.id)

    def test_the_person_who_asked_cannot_move_a_leave_that_has_begun(self):
        leave = self._started_leave()
        with self.assertRaises(UserError) as caught:
            leave.with_user(self.staff).write(
                {'request_date_to': self.today + timedelta(days=4)})
        self.assertIn('already started', str(caught.exception))

    def test_nor_delete_one(self):
        leave = self._started_leave()
        with self.assertRaises(UserError):
            leave.with_user(self.staff).unlink()
        self.assertTrue(leave.exists())

    def test_an_officer_still_can(self):
        """`hr.leave.name` is a COMPUTE over `private_name` and is dropped for
        a writer without the responsible group, so the substance write these
        cases are about is a DATE — a plain stored column that can be read
        back and believed."""
        leave = self._started_leave()
        wanted = self.today + timedelta(days=4)
        leave.with_user(self.officer).write({'request_date_to': wanted})
        self.assertEqual(leave.request_date_to, wanted)

    def test_the_lock_does_not_fire_on_a_write_that_is_not_the_leave(self):
        """THE WHOLE REASON THE LOCK IS ON THE SUBSTANCE AND NOT ON THE
        RECORD. The approval route writes a seat onto a leave as the person
        deciding it, who is by design somebody with no HR group; a lock that
        fired on every write would strand a backdated sick note half-approved
        — R132's exact failure, reached from a new direction."""
        leave = self._started_leave()
        leave.with_user(self.staff).write(
            {'seat_user_ids': [(4, self.staff.id)]})
        self.assertIn(self.staff, leave.seat_user_ids)

    def test_turning_the_switch_off_puts_the_stock_behaviour_back(self):
        """R54's other half: a switch nobody can see the effect of is a
        switch nobody trusts."""
        leave = self._started_leave()
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_timeoff.lock_past', '0')
        wanted = self.today + timedelta(days=5)
        try:
            leave.with_user(self.staff).write({'request_date_to': wanted})
            self.assertEqual(leave.request_date_to, wanted)
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_timeoff.lock_past', '1')

    def test_a_leave_that_has_not_started_is_still_the_persons_own(self):
        made = self.Leave.with_company(self.company).with_context(
            leave_fast_create=True).create(
                self._vals(self.plain_type, self.today + timedelta(days=3)))
        leave = self.Leave.browse(made.id)
        wanted = self.today + timedelta(days=6)
        leave.with_user(self.staff).write({'request_date_to': wanted})
        self.assertEqual(leave.request_date_to, wanted)


@tagged('post_install', '-at_install')
class TestEscalationSeed(TransactionCase):
    """T3's static half — the route SAYS who to escalate to.

    Whether the engine then does it is `biz_approval_workflow`'s own T31c/d/e
    and a live proof; what belongs here is that this module's seed asks for
    it, because a route that never says `to_role` escalates to whoever
    published it and nothing anywhere reports that.
    """

    def test_the_seeded_route_names_the_hr_lead_as_the_escalation(self):
        company = self.env['res.company'].create({'name': 'D1 Escalation Co'})
        self.env['hr.leave']._approval_seed_default(company)
        process = self.env['biz.approval.process'].sudo().search(
            [('key', '=', 'leave')], limit=1)
        self.assertTrue(process, 'the approval catalogue needs a leave row')
        version = self.env['biz.approval.workflow.version'].sudo().search([
            ('workflow_id.company_id', '=', company.id),
            ('workflow_id.process_id', '=', process.id),
        ], limit=1)
        self.assertTrue(version, 'the company must end up with a route')
        late = (version.definition.get('safeguards') or {}).get('late') or {}
        self.assertEqual(late.get('to_role'), 'hr_lead')
        self.assertEqual(late.get('escalate_days'),
                         self.env['hr.leave']._approval_escalate_days())

    def test_the_number_of_days_is_a_dial_and_not_a_number_in_code(self):
        self.assertEqual(self.env['hr.leave']._approval_escalate_days(), 2)
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('pb_timeoff.escalate_days', '5')
        try:
            self.assertEqual(
                self.env['hr.leave']._approval_escalate_days(), 5)
        finally:
            param.set_param('pb_timeoff.escalate_days', '2')
