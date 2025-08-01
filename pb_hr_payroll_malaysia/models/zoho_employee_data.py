# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ZohoEmployeeDataMalaysia(models.Model):
    _name = 'zoho.employee.data.malaysia'
    _description = 'Malaysia Zoho Employee Data'

    name = fields.Char('Employee Name', required=True)
    employee_id = fields.Char('Employee ID', required=True)
    epf_number = fields.Char('EPF Number')
    socso_number = fields.Char('SOCSO Number')
    income_tax_number = fields.Char('Income Tax Number')
    basic_salary = fields.Float('Basic Salary (MYR)')
    allowances = fields.Float('Allowances (MYR)')
    
    department = fields.Char('Department')
    position = fields.Char('Position')
    join_date = fields.Date('Join Date')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('imported', 'Imported'),
        ('error', 'Error')
    ], default='draft')

    @api.model
    def validate_malaysia_data(self):
        """Validate employee data for Malaysia compliance"""
        records = self.search([('state', '=', 'draft')])
        for record in records:
            if record.epf_number and record.basic_salary > 0:
                record.state = 'validated'
        return True