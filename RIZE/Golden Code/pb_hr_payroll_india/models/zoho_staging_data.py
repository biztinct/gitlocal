# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ZohoStagingData(models.Model):
    _inherit = 'zoho.staging.data'
    
    # India Specific Salary Components
    basic_salary = fields.Float(string="Basic Salary")
    hra = fields.Float(string="House Rent Allowance (HRA)")
    special_allowance = fields.Float(string="Special Allowance")
    books_periodicals = fields.Float(string="Books and Periodicals")
    telephone_internet = fields.Float(string="Telephone and Internet")
    leave_travel_allowance = fields.Float(string="Leave Travel Allowance (LTA)")
    
    # India Deductions
    pf = fields.Float(string="Provident Fund (PF)")
    prof_tax = fields.Float(string="Professional Tax")
    income_tax = fields.Float(string="Income Tax (TDS)")
    
    # India Employee Details
    uan_number = fields.Char(string="UAN Number")
    esi_number = fields.Char(string="ESI Number")
    ifsc_code = fields.Char(string="IFSC Code")
    
    def get_india_salary_components(self):
        """Return dictionary of India salary components for this employee"""
        return {
            'basic_salary': self.basic_salary or 0,
            'hra': self.hra or 0,
            'special_allowance': self.special_allowance or 0,
            'books_periodicals': self.books_periodicals or 0,
            'telephone_internet': self.telephone_internet or 0,
            'leave_travel_allowance': self.leave_travel_allowance or 0,
            'pf': self.pf or 0,
            'prof_tax': self.prof_tax or 200,  # Default professional tax
            'income_tax': self.income_tax or 0,
        }


class ZohoEmployeeData(models.Model):
    _inherit = 'zoho.employee.data'
    
    # India Specific Salary Components (calculated from spreadsheet)
    actual_basic_salary = fields.Float(string="Actual Basic Salary")
    actual_hra = fields.Float(string="Actual HRA")
    actual_special_allowance = fields.Float(string="Actual Special Allowance")
    actual_books_periodicals = fields.Float(string="Actual Books and Periodicals")
    actual_telephone_internet = fields.Float(string="Actual Telephone and Internet")
    actual_lta = fields.Float(string="Actual LTA")
    
    # India Deductions (calculated)
    actual_pf = fields.Float(string="Actual PF")
    actual_prof_tax = fields.Float(string="Actual Professional Tax")
    actual_income_tax = fields.Float(string="Actual Income Tax")
    
    # India Employer Contributions
    pf_employer = fields.Float(string="PF Employer Contribution")
    esi_employer = fields.Float(string="ESI Employer Contribution")
    
    # India Totals
    india_gross_pay = fields.Float(string="India Gross Pay")
    india_total_deductions = fields.Float(string="India Total Deductions")
    india_net_pay = fields.Float(string="India Net Pay")