from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from ..models.weekday_location import WEEKDAYS


@tagged('post_install', '-at_install')
class TestWeekdayLocation(TransactionCase):
    def test_location_defaults_preserve_choices_and_weekends(self):
        if 'monday_location_id' not in self.env['hr.employee']._fields:
            self.skipTest('Optional hr_homeworking is not installed')
        company = self.env.company
        office = self.env['hr.work.location'].create({'name':'Default office test', 'company_id':company.id, 'address_id':company.partner_id.id})
        home = self.env['hr.work.location'].create({'name':'Home test', 'company_id':company.id, 'address_id':company.partner_id.id, 'location_type':'home'})
        company.write({'pb_weekday_location_defaults':True, 'pb_weekday_fallback_location_id':office.id})
        employee = self.env['hr.employee'].create({'name':'Weekday test', 'work_location_id':home.id, 'monday_location_id':office.id, 'friday_location_id':False})
        self.assertEqual(employee.monday_location_id, office)
        self.assertEqual(employee.tuesday_location_id, home)
        self.assertFalse(employee.friday_location_id)
        self.assertFalse(employee.saturday_location_id)
        self.assertFalse(employee.sunday_location_id)
        employee.write({'tuesday_location_id':office.id})
        employee._onchange_pb_weekday_location()
        self.assertEqual(employee.tuesday_location_id, office)
        fallback = self.env['hr.employee'].create({'name':'Fallback test'})
        for day in WEEKDAYS:
            self.assertEqual(fallback[day],office)
        company.pb_weekday_location_defaults = False
        unconfigured = self.env['hr.employee'].create({'name':'No default test'})
        self.assertFalse(unconfigured.monday_location_id)

    def test_cannot_use_another_company_location(self):
        other = self.env['res.company'].create({'name':'Weekday other company'})
        loc = self.env['hr.work.location'].create({'name':'Other office', 'company_id':other.id,'address_id':other.partner_id.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env.company.pb_weekday_fallback_location_id = loc
