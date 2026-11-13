from datetime import datetime

import pytz
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmployeeWorkTimezone(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Timezone test company'})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls.calendar = cls.company.resource_calendar_id
        cls.calendar.tz = 'Australia/Sydney'

    def employee(self, **values):
        return self.env['hr.employee'].create(dict(
            name='Timezone test employee', company_id=self.company.id, **values))

    def test_country_defaults_preserve_shared_schedule(self):
        for code, tz in [('VN', 'Asia/Ho_Chi_Minh'), ('IN', 'Asia/Kolkata'), ('SG', 'Asia/Singapore'), ('ID', 'Asia/Jakarta')]:
            employee = self.employee(payroll_country=code)
            self.assertEqual(employee.tz, tz)
            self.assertEqual(employee.resource_calendar_id.tz, tz)
            self.assertNotEqual(employee.resource_calendar_id, self.calendar)
            self.assertEqual(employee.resource_calendar_id.hours_per_week, self.calendar.hours_per_week)
            contract = self.env['hr.contract'].create({'name': 'Timezone contract',
                'employee_id': employee.id, 'company_id': self.company.id,
                'date_start': '2026-01-01', 'wage': 100})
            self.assertEqual(contract.resource_calendar_id, employee.resource_calendar_id)
        self.assertEqual(self.calendar.tz, 'Australia/Sydney')

    def test_reuses_calendar_and_preserves_explicit_timezone(self):
        first = self.employee(payroll_country='VN')
        second = self.employee(payroll_country='VN')
        self.assertEqual(first.resource_calendar_id, second.resource_calendar_id)
        override = self.employee(payroll_country='VN', tz='Asia/Tokyo')
        self.assertEqual(override.tz, 'Asia/Tokyo')
        self.assertEqual(override.resource_calendar_id.tz, 'Asia/Tokyo')

    def test_work_location_wins_over_payroll_country_and_nationality(self):
        address = self.env['res.partner'].create({'name': 'Bali office',
            'country_id': self.env.ref('base.id').id})
        location = self.env['hr.work.location'].create({'name': 'Bali',
            'company_id': self.company.id, 'address_id': address.id,
            'pb_work_timezone': 'Asia/Makassar'})
        employee = self.employee(payroll_country='SG', work_location_id=location.id,
            country_id=self.env.ref('base.vn').id)
        self.assertEqual(employee.tz, 'Asia/Makassar')
        self.assertEqual(employee.resource_calendar_id.tz, 'Asia/Makassar')
        address.country_id = self.env.ref('base.in')
        location.pb_work_timezone = False
        self.assertEqual(employee._pb_default_work_timezone(), 'Asia/Singapore')
        employee.payroll_country = False
        self.assertEqual(employee._pb_default_work_timezone(), 'Asia/Kolkata')
        # Editing a location is not an instruction to bulk rewrite people.
        self.assertEqual(employee.tz, 'Asia/Makassar')

    def test_custom_calendar_preserved_and_unknown_country_not_guessed(self):
        custom = self.calendar.copy({'tz': 'Asia/Tokyo'})
        employee = self.employee(payroll_country='VN', resource_calendar_id=custom.id)
        self.assertEqual(employee.resource_calendar_id, custom)
        self.assertEqual(employee.tz, 'Asia/Tokyo')
        indonesia = self.employee(payroll_country='ID')
        self.assertEqual(indonesia.tz, 'Asia/Jakarta')
        self.assertIn('Payroll Country: Asia/Jakarta', indonesia.pb_work_timezone_note)
        self.assertEqual(self.employee(country_id=self.env.ref('base.vn').id).resource_calendar_id, self.calendar)
        self.assertFalse(self.employee()._pb_default_work_timezone())

    def test_form_defaults_and_global_closure_local_time(self):
        new = self.env['hr.employee'].new({'name': 'Form default', 'payroll_country': 'VN'})
        new._onchange_pb_work_timezone()
        self.assertEqual(new.tz, 'Asia/Ho_Chi_Minh')
        source = self.env['resource.calendar.leaves'].create({'name': 'Local closure',
            'calendar_id': self.calendar.id,
            'date_from': '2026-08-02 14:00:00', 'date_to': '2026-08-03 14:00:00'})
        employee = self.employee(payroll_country='VN')
        closure = employee.resource_calendar_id.global_leave_ids.filtered(lambda l: l.name == 'Local closure')
        self.assertEqual(len(closure), 1)
        for field in ('date_from', 'date_to'):
            original_local = pytz.utc.localize(source[field]).astimezone(pytz.timezone('Australia/Sydney'))
            copied_local = pytz.utc.localize(closure[field]).astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
            self.assertEqual(original_local.replace(tzinfo=None), copied_local.replace(tzinfo=None))

    def test_full_day_is_two_half_days(self):
        employee = self.employee(payroll_country='VN')
        monday = employee.resource_calendar_id.attendance_ids.filtered(lambda a: a.dayofweek == '0')
        self.assertEqual(sum(monday.mapped('duration_hours')), 8)
        self.assertEqual(sum(monday.mapped('duration_days')), 1)
