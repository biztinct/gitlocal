# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared fixture: two employees, two users, one week of shifts.

Two of everything on purpose. Half of this phase's tests are about what the
SECOND employee cannot see, and a fixture with one person in it cannot ask that
question at all.
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import fields
from odoo.tests.common import TransactionCase


class EssWorkforceCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # A non-UTC tenant, deliberately: every stored time in this suite is
        # asserted through a timezone that is not the server's, because a
        # wall-clock bug is invisible in UTC (W55/W63).
        cls.tz = 'Asia/Ho_Chi_Minh'
        cls.tzinfo = pytz.timezone(cls.tz)

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_a = Users.create({
            'name': 'ESS Alpha', 'login': 'p8.alpha@example.invalid',
            'email': 'p8.alpha@example.invalid', 'tz': cls.tz,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.user_b = Users.create({
            'name': 'ESS Beta', 'login': 'p8.beta@example.invalid',
            'email': 'p8.beta@example.invalid', 'tz': cls.tz,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.user_none = Users.create({
            'name': 'ESS Nobody', 'login': 'p8.nobody@example.invalid',
            'email': 'p8.nobody@example.invalid', 'tz': cls.tz,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        Emp = cls.env['hr.employee']
        cls.emp_a = Emp.create({
            'name': 'ESS Alpha', 'user_id': cls.user_a.id,
            'company_id': cls.company.id, 'tz': cls.tz})
        cls.emp_b = Emp.create({
            'name': 'ESS Beta', 'user_id': cls.user_b.id,
            'company_id': cls.company.id, 'tz': cls.tz})

        cls.template = cls.env['hr.shift.template'].create({
            'name': 'P8 Morning', 'code': 'P8AM',
            'start_hour': 8.0, 'end_hour': 17.0,
        })

        today = fields.Date.context_today(cls.env['hr.employee'])
        cls.monday = today - timedelta(days=today.weekday())

    # ------------------------------------------------------------- helpers
    @classmethod
    def _utc(cls, day, hh, mm=0):
        return cls.tzinfo.localize(
            datetime.combine(day, time(hh, mm))).astimezone(
                pytz.UTC).replace(tzinfo=None)

    def _shift(self, employee, day, start=8, end=17, state='draft'):
        shift = self.env['hr.shift.planning'].create({
            'employee_id': employee.id,
            'shift_template_id': self.template.id,
            'date': day,
            'start_datetime': self._utc(day, start),
            'end_datetime': self._utc(day, end),
        })
        if state != 'draft':
            shift.action_publish()
        if state == 'completed':
            shift.action_complete()
        return shift

    def _future_day(self, offset=1):
        """A day whose 08:00 is reliably still in the future.

        The suite runs at an unknown hour, so "tomorrow" is the earliest day a
        shift start can be trusted to be ahead of `now` — a test that publishes
        this morning's shift and then asserts it is acknowledgeable fails
        between 08:01 and midnight and passes the rest of the time, which is
        the worst kind of test there is.
        """
        return fields.Date.context_today(self.env['hr.employee']) + timedelta(
            days=offset)

    def _as(self, user):
        return self.env['pb.ess.workforce'].with_user(user)
