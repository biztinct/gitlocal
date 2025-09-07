# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ZohoStagingData(models.Model):
    _inherit = 'zoho.staging.data'
    
    # ===== INDIA-SPECIFIC STAGING FIELDS =====
    # Note: Reusing existing base_salary instead of basic_salary
    # Note: Using existing meal_allowance, phone_allowance where applicable
    
    # India Core Salary Components
    hra = fields.Float(string="House Rent Allowance (HRA)")  # India-specific: HRA component
    special_allowance = fields.Float(string="Special Allowance")  # India-specific: Special allowance
    
    # India Additional Allowances (reuse existing where possible)
    # Note: books_allowance reuses existing bonus fields structure
    # Note: lta uses existing travel allowance concept
    books_allowance = fields.Float(string="Books & Periodicals")  # India-specific: Educational allowance
    lta = fields.Float(string="Leave Travel Allowance")  # India-specific: LTA benefit
    # Note: medical_allowance reuses meal_allowance concept but with different purpose
    
    # India Statutory Deductions
    pf_employee = fields.Float(string="PF Employee (12%)")  # India-specific: Employee PF contribution  
    esi_employee = fields.Float(string="ESI Employee (0.75%)")  # India-specific: Employee ESI contribution
    professional_tax = fields.Float(string="Professional Tax")  # India-specific: State professional tax
    income_tax = fields.Float(string="Income Tax/TDS")  # India-specific: Income tax deduction
    
    # India Employer Contributions  
    pf_employer = fields.Float(string="PF Employer (12%)")  # India-specific: Employer PF contribution
    esi_employer = fields.Float(string="ESI Employer (3.25%)")  # India-specific: Employer ESI contribution
    
    # India Compliance Fields
    gratuity_provision = fields.Float(string="Gratuity Provision")  # India-specific: Gratuity calculation
    
    # India Employee ID Numbers (Note: uan_number and aadhaar_number already exist in base model)
    esi_number = fields.Char(string="ESI Number")  # India-specific: ESI registration number
    pf_number = fields.Char(string="PF Number")  # India-specific: PF account number
    
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