# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ZohoStagingDataMalaysia(models.Model):
    _name = 'zoho.staging.data.malaysia'
    _description = 'Malaysia Zoho Staging Data'

    employee_name = fields.Char('Employee Name')
    employee_code = fields.Char('Employee Code') 
    epf_number = fields.Char('EPF Number')
    socso_number = fields.Char('SOCSO Number')
    basic_salary_myr = fields.Float('Basic Salary (MYR)')
    epf_employee_myr = fields.Float('EPF Employee (MYR)')
    epf_employer_myr = fields.Float('EPF Employer (MYR)')
    socso_employee_myr = fields.Float('SOCSO Employee (MYR)')
    socso_employer_myr = fields.Float('SOCSO Employer (MYR)')
    eis_employee_myr = fields.Float('EIS Employee (MYR)')
    eis_employer_myr = fields.Float('EIS Employer (MYR)')
    income_tax_myr = fields.Float('Income Tax (MYR)')
    net_salary_myr = fields.Float('Net Salary (MYR)')
    
    processing_date = fields.Date('Processing Date', default=fields.Date.today)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('error', 'Error')
    ], default='pending')

    @api.model
    def process_malaysia_staging_data(self):
        """Process staged Malaysia payroll data"""
        records = self.search([('state', '=', 'pending')])
        for record in records:
            try:
                # Process EPF, SOCSO, EIS calculations
                record.state = 'processed'
            except Exception as e:
                record.state = 'error'
        return len(records)