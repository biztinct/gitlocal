# -- coding: utf-8 --
###################################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2022-TODAY Cybrosys Technologies (<https://www.cybrosys.com>).
#    Author: Cybrosys (<https://www.cybrosys.com>)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###################################################################################
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _


class HrEmployeeInherited(models.Model):
    _inherit = 'hr.employee'

    resource_calendar_ids = fields.Many2one('resource.calendar', 'Working Hours',)


class HrEmployeeShift(models.Model):
    _inherit = 'resource.calendar'

    def _get_default_attendance_ids(self):
        return [
            (0, 0, {'name': _('Monday Morning'), 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'name': _('Tuesday Morning'), 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'name': _('Wednesday Morning'), 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'name': _('Thursday Morning'), 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'name': _('Friday Morning'), 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
        ]

    color = fields.Integer(string='Color Index', help="Color")
    hr_department = fields.Many2one('hr.department', string="Department", help="Department (leave blank to apply to all departments)")
    sequence = fields.Integer(string="Sequence", required=True, default=1, help="Sequence")
    attendance_ids = fields.One2many(
        'resource.calendar.attendance', 'calendar_id', 'Workingssss Time',
        copy=True, default=_get_default_attendance_ids)

    @api.constrains('sequence', 'hr_department')
    def validate_seq(self):
        # Only check sequence uniqueness within the same department
        # If no department is set, the shift applies to all departments (no sequence constraint needed)
        if self.hr_department:
            domain = [
                ('hr_department', '=', self.hr_department.id),
                ('sequence', '=', self.sequence),
                ('company_id', '=', self.company_id.id),
                ('id', '!=', self.id)  # Exclude current record
            ]
            duplicate_records = self.env['resource.calendar'].search(domain)
            if duplicate_records:
                raise ValidationError(
                    _("A shift with the same sequence (%s) already exists for department '%s'. "
                      "Please use a different sequence number.") % (self.sequence, self.hr_department.name)
                )


