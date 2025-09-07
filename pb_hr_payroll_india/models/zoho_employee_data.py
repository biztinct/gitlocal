# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ZohoEmployeeData(models.Model):
    _inherit = 'zoho.employee.data'
    
    # India specific fields - Basic Components
    basic_salary = fields.Float(string='Basic Salary')
    hra = fields.Float(string='House Rent Allowance (HRA)')
    special_allowance = fields.Float(string='Special Allowance')
    
    # Additional India Allowances
    books_periodicals = fields.Float(string='Books and Periodicals')
    telephone_internet = fields.Float(string='Telephone and Internet')
    leave_travel_allowance = fields.Float(string='Leave Travel Allowance (LTA)')
    medical_allowance = fields.Float(string='Medical Allowance')
    transport_allowance = fields.Float(string='Transport Allowance')
    meal_allowance = fields.Float(string='Meal Allowance')
    performance_bonus = fields.Float(string='Performance Bonus')
    other_allowances = fields.Float(string='Other Allowances')
    
    # Employee Deductions
    pf_employee = fields.Float(string='Provident Fund (Employee)')
    esi_employee = fields.Float(string='ESI (Employee)')
    professional_tax = fields.Float(string='Professional Tax')
    income_tax = fields.Float(string='Income Tax (TDS)')
    loan_deduction = fields.Float(string='Loan Deduction')
    advance_deduction = fields.Float(string='Advance Deduction')
    other_deductions = fields.Float(string='Other Deductions')
    
    # Employer Contributions
    pf_employer = fields.Float(string='Provident Fund (Employer)')
    esi_employer = fields.Float(string='ESI (Employer)')
    total_employer_contrib = fields.Float(string='Total Employer Contributions')
    gratuity = fields.Float(string='Gratuity')
    
    # Indian ID Numbers
    pan_number = fields.Char(string='PAN Number', help='Permanent Account Number')
    aadhaar_number = fields.Char(string='Aadhaar Number')
    pf_number = fields.Char(string='PF Number')
    esi_number = fields.Char(string='ESI Number')
    
    # Calculated Fields
    gross_salary = fields.Float(string='Gross Salary')
    total_deductions = fields.Float(string='Total Deductions')
    net_pay = fields.Float(string='Net Pay')
    
    # Payroll country selection
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Payroll Country', default='IN')