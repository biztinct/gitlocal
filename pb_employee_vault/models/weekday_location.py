"""Opt-in weekday location defaults; never a payroll working-time calendar."""
from odoo import api, fields, models

WEEKDAYS = tuple(day + '_location_id' for day in
                 ('monday', 'tuesday', 'wednesday', 'thursday', 'friday'))


class Company(models.Model):
    _inherit = 'res.company'

    pb_weekday_location_defaults = fields.Boolean(
        'Default Monday–Friday to work location',
        help='For new employees, fill unspecified weekdays from their Work Location. '
             'Existing explicit choices and weekends are preserved.')
    pb_weekday_fallback_location_id = fields.Many2one(
        'hr.work.location', string='Fallback weekday location',
        domain="[('company_id', '=', id)]",
        help='Used only when the employee has no Work Location.')

    @api.constrains('pb_weekday_fallback_location_id')
    def _check_weekday_location_company(self):
        from odoo.exceptions import ValidationError
        for company in self:
            if company.pb_weekday_fallback_location_id and company.pb_weekday_fallback_location_id.company_id != company:
                raise ValidationError('The fallback work location must belong to this company.')


class Employee(models.Model):
    _inherit = 'hr.employee'

    def _pb_weekday_defaults(self, explicit=()):
        """Only missing values, only when opted in, and only with homeworking installed."""
        self.ensure_one()
        company = self.company_id
        if not company.pb_weekday_location_defaults:
            return {}
        location = self.work_location_id or company.pb_weekday_fallback_location_id
        if not location or not location.active or location.company_id != company:
            return {}
        return {day: location.id for day in WEEKDAYS
                if day in self._fields and day not in explicit and not self[day]}

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        for employee, vals in zip(employees, vals_list):
            defaults = employee._pb_weekday_defaults(explicit=vals)
            if defaults:
                employee.write(defaults)
        return employees

    @api.onchange('work_location_id', 'company_id')
    def _onchange_pb_weekday_location(self):
        for employee in self:
            employee.update(employee._pb_weekday_defaults())
