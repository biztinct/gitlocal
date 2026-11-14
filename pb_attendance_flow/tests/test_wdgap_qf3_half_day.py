# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP QF3 (handover case 13) — a half day off is not a day off.

A validated WHOLE-day leave still hides the day's missing punch, exactly as
before. A half-day (or hours) leave does not: the person works the other half,
so no punch at all on that day is still a missing punch. Lateness that the
leave explains (morning off, in at 13:00) is not raised.
"""

from datetime import date, datetime, time, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_qf3')
class TestWdgapQf3HalfDay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Engine = cls.env['pb.attendance.exception.engine']
        cls.tmpl = cls.env['hr.shift.template'].create({
            'name': 'QF3 Day', 'code': 'QF3D', 'start_hour': 8.0,
            'end_hour': 17.0, 'is_overnight': False, 'shift_type': 'morning',
            'company_id': cls.company.id})
        Type = cls.env['hr.leave.type']
        cls.t_day = Type.create({
            'name': 'QF3 ATF Day', 'requires_allocation': False,
            'leave_validation_type': 'no_validation', 'request_unit': 'day'})
        cls.t_half = Type.create({
            'name': 'QF3 ATF Half', 'requires_allocation': False,
            'leave_validation_type': 'no_validation',
            'request_unit': 'half_day'})
        cls.t_hour = Type.create({
            'name': 'QF3 ATF Hours', 'requires_allocation': False,
            'leave_validation_type': 'no_validation', 'request_unit': 'hour'})
        d = date.today() - timedelta(days=7)
        cls.day = d - timedelta(days=d.weekday())       # a past Monday

    def _emp(self, name):
        return self.env['hr.employee'].create({
            'name': name, 'company_id': self.company.id, 'tz': 'UTC'})

    def _shift(self, emp, actual_in=None, actual_out=None):
        d = self.day
        return self.env['hr.shift.planning'].create({
            'employee_id': emp.id, 'shift_template_id': self.tmpl.id,
            'date': d, 'state': 'published',
            'start_datetime': datetime.combine(d, time(8, 0)),
            'end_datetime': datetime.combine(d, time(17, 0)),
            'actual_check_in': actual_in, 'actual_check_out': actual_out})

    def _leave(self, emp, lt, **extra):
        vals = {'name': 'off', 'employee_id': emp.id,
                'holiday_status_id': lt.id, 'request_date_from': self.day,
                'request_date_to': self.day}
        vals.update(extra)
        leave = self.env['hr.leave'].sudo().create(vals)   # HR enters the past
        if leave.state != 'validate':
            leave.sudo().action_approve()
        self.assertEqual(leave.state, 'validate')
        return leave

    def _kinds(self, emp):
        rows = self.Engine._get_exceptions(
            emp, self.day - timedelta(days=1), self.day + timedelta(days=1))
        return [r['kind'] for r in rows if r['date'] == self.day.isoformat()]

    def test_13a_a_whole_day_leave_still_hides_the_missing_punch(self):
        emp = self._emp('QF3 Whole')
        self._shift(emp)
        self.assertIn('missing_punch', self._kinds(emp), 'fixture: no punch')
        self._leave(emp, self.t_day)
        self.assertNotIn('missing_punch', self._kinds(emp))
        # a half-day KIND taken as a full day is a whole day off too
        emp2 = self._emp('QF3 Half as full')
        self._shift(emp2)
        self._leave(emp2, self.t_half, request_date_from_period='am',
                    request_date_to_period='pm')
        self.assertNotIn('missing_punch', self._kinds(emp2))

    def test_13b_a_half_day_does_not_hide_the_missing_punch(self):
        emp = self._emp('QF3 Half')
        self._shift(emp)
        leave = self._leave(emp, self.t_half, request_date_from_period='am',
                            request_date_to_period='am')
        self.assertEqual(leave.number_of_days, 0.5)
        self.assertIn('missing_punch', self._kinds(emp))
        # nor do a few hours
        emp2 = self._emp('QF3 Hours')
        self._shift(emp2)
        self._leave(emp2, self.t_hour, request_hour_from=9.0,
                    request_hour_to=11.0)
        self.assertIn('missing_punch', self._kinds(emp2))

    def test_13c_lateness_the_morning_off_explains_is_not_raised(self):
        d = self.day
        emp = self._emp('QF3 Late after a morning off')
        shift = self._shift(emp, actual_in=datetime.combine(d, time(13, 0)),
                            actual_out=datetime.combine(d, time(17, 0)))
        if shift.compliance_status != 'late':
            self.skipTest('this database does not rate that shift as late')
        self.assertIn('late', self._kinds(emp), 'fixture: late without leave')
        self._leave(emp, self.t_half, request_date_from_period='am',
                    request_date_to_period='am')
        self.assertNotIn('late', self._kinds(emp))
