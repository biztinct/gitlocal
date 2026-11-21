"""Work timezone defaults. Nationality and the importing user's timezone are not work locations."""
import pytz

from odoo import api, fields, models


COUNTRY_TIMEZONES = {
    'VN': 'Asia/Ho_Chi_Minh', 'IN': 'Asia/Kolkata', 'SG': 'Asia/Singapore',
    'MY': 'Asia/Kuala_Lumpur', 'ID': 'Asia/Jakarta',
}


def country_timezone(code):
    zones = pytz.country_timezones.get(code or '', [])
    return COUNTRY_TIMEZONES.get(code) or (zones[0] if len(zones) == 1 else False)


class WorkLocation(models.Model):
    _inherit = 'hr.work.location'

    pb_work_timezone = fields.Selection(
        selection=lambda self: [(tz, tz) for tz in pytz.all_timezones],
        string='Work timezone',
        help='Timezone at this work location. Set this for countries with several timezones. '
             'Used as a default for new employees; existing employees are not changed by editing this location.')


class WorkCalendar(models.Model):
    _inherit = 'resource.calendar'

    pb_timezone_origin_id = fields.Many2one('resource.calendar', copy=False, ondelete='set null')

    def _pb_in_work_timezone(self, tz, company):
        """Private, scoped copy: never change a calendar shared with another country."""
        self.ensure_one()
        self.check_access('read')
        if self.tz == tz:
            return self
        # Serialize reuse within a company. Only the calendar copy is elevated,
        # so an HR officer can create an employee without calendar-admin rights.
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (company.id, self.id))
        Calendar = self.env['resource.calendar'].sudo()
        existing = Calendar.search([
            ('pb_timezone_origin_id', '=', self.id), ('company_id', '=', company.id),
            ('tz', '=', tz)], limit=1)
        if existing:
            return existing
        original_closures = [(leave.date_from, leave.date_to)
                             for leave in self.global_leave_ids]
        clone = self.sudo().copy({'tz': tz, 'company_id': company.id,
                                 'pb_timezone_origin_id': self.id})
        clone.name = '%s · %s' % (self.name, tz)
        # Calendar closures are local wall times. Employee-specific leave stays
        # on the original records; only global closures are copied by Odoo.
        old_zone, new_zone = pytz.timezone(self.tz), pytz.timezone(tz)
        # hr_holidays can already convert copied dates using the importing
        # user's timezone. Always derive from the original UTC dates instead.
        for leave, dates in zip(clone.global_leave_ids.sorted('id'), original_closures):
            values = {}
            for field, source_date in zip(('date_from', 'date_to'), dates):
                wall = pytz.utc.localize(source_date).astimezone(old_zone).replace(tzinfo=None)
                values[field] = new_zone.localize(wall).astimezone(pytz.utc).replace(tzinfo=None)
            leave.write(values)
        return clone


class Employee(models.Model):
    _inherit = 'hr.employee'

    payroll_country = fields.Selection(selection_add=[('TH', 'Thailand'), ('KH', 'Cambodia'), ('PH', 'Philippines')],
                                      ondelete={'TH': 'set null', 'KH': 'set null', 'PH': 'set null'})

    pb_work_timezone_note = fields.Char(string='Timezone source', compute='_compute_pb_work_timezone_note')

    @api.depends('payroll_country', 'work_location_id', 'work_location_id.pb_work_timezone',
                 'work_location_id.address_id.country_id', 'tz', 'resource_calendar_id.tz')
    def _compute_pb_work_timezone_note(self):
        for employee in self:
            expected = employee._pb_default_work_timezone()
            if not expected:
                employee.pb_work_timezone_note = 'Set Work timezone on the employee’s work location. No country-wide timezone is assumed.'
            elif employee.tz != expected or (employee.resource_calendar_id and employee.resource_calendar_id.tz != expected):
                employee.pb_work_timezone_note = 'Location/country suggests %s. Review the employee timezone and work calendar if this difference is not intentional.' % expected
            else:
                source = 'Work location' if employee.work_location_id.pb_work_timezone else 'Payroll Country' if employee.payroll_country else 'Work address country'
                employee.pb_work_timezone_note = '%s: %s' % (source, expected)

    def _pb_default_work_timezone(self):
        self.ensure_one()
        location = self.work_location_id
        if location.pb_work_timezone:
            return location.pb_work_timezone
        # Work addresses can be shared headquarters (including cross-country
        # payrolls). An explicit location timezone wins; otherwise the payroll
        # country is stronger evidence than an address's inferred timezone.
        code = self.payroll_country or location.address_id.country_id.code
        return country_timezone(code)

    @api.onchange('payroll_country', 'work_location_id')
    def _onchange_pb_work_timezone(self):
        # Changing location proposes a visible default; the user can then
        # override Timezone. Calendar creation is deferred until Save.
        for employee in self:
            tz = employee._pb_default_work_timezone()
            if tz:
                employee.tz = tz

    @api.model_create_multi
    def create(self, vals_list):
        supplied = [dict(vals) for vals in vals_list]
        employees = super().create([dict(vals) for vals in vals_list])
        for employee, vals in zip(employees, supplied):
            if vals.get('resource_id'):
                continue  # Explicit shared resource/copy keeps its own settings.
            calendar = employee.resource_calendar_id
            custom_calendar = vals.get('resource_calendar_id') and calendar != employee.company_id.resource_calendar_id
            tz = vals.get('tz') or (calendar.tz if custom_calendar else employee._pb_default_work_timezone())
            if not tz:
                continue  # Ambiguous multi-zone countries need a work location.
            # Explicit custom schedules remain authoritative. The company
            # default is often sent by the form even when nobody selected it.
            if calendar and (not vals.get('resource_calendar_id') or
                             calendar == employee.company_id.resource_calendar_id):
                calendar = calendar._pb_in_work_timezone(tz, employee.company_id)
                employee.resource_calendar_id = calendar
            employee.tz = tz
        return employees


class Contract(models.Model):
    _inherit = 'hr.contract'

    @api.model_create_multi
    def create(self, vals_list):
        values = [dict(vals) for vals in vals_list]
        for vals in values:
            employee = self.env['hr.employee'].browse(vals.get('employee_id')).exists()
            if employee and not vals.get('resource_calendar_id') and employee.resource_calendar_id:
                vals['resource_calendar_id'] = employee.resource_calendar_id.id
        return super().create(values)
