# -*- coding:utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    _description = 'Employee'

    slip_ids = fields.One2many('hr.payslip', 'employee_id', string='Payslips', readonly=True)
    payslip_count = fields.Integer(compute='_compute_payslip_count', string='Payslip Count',
                                   groups="om_om_hr_payroll.group_hr_payroll_user")
    employee_id = fields.Char(string='Employee Id')
    location = fields.Char(string='Location')
    full_name_vn = fields.Char(string='Vietnamese Full Name')
    org_employee_type = fields.Char(string='Employee Type')
    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)
