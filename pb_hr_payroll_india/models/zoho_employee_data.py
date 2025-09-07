# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ZohoEmployeeData(models.Model):
    _inherit = 'zoho.employee.data'
    
    # ===== INDIA-SPECIFIC PAYROLL FIELDS =====
    # Note: Reusing existing base_salary field instead of basic_salary to avoid duplication
    # Note: Using existing allowance fields where possible (gas_allowance, phone_allowance, etc.)
    
    # India-Specific Basic Components
    hra = fields.Float(string='House Rent Allowance (HRA)')  # India-specific HRA component
    special_allowance = fields.Float(string='Special Allowance')  # India-specific special allowance
    
    # India-Specific Additional Allowances (only essential ones)
    books_allowance = fields.Float(string='Books & Periodicals')  # India-specific: Reimbursable books allowance
    lta = fields.Float(string='Leave Travel Allowance (LTA)')  # India-specific: Tax-exempt travel allowance
    medical_allowance = fields.Float(string='Medical Allowance')  # India-specific: Medical reimbursement
    
    # India Statutory Deductions (Employee)
    pf_employee = fields.Float(string='PF - Employee (12%)')  # India-specific: Provident Fund employee contribution
    esi_employee = fields.Float(string='ESI - Employee (0.75%)')  # India-specific: ESI employee contribution  
    professional_tax = fields.Float(string='Professional Tax')  # India-specific: State-wise professional tax
    income_tax = fields.Float(string='Income Tax/TDS')  # India-specific: Tax deducted at source
    
    # India Statutory Contributions (Employer)
    pf_employer = fields.Float(string='PF - Employer (12%)')  # India-specific: Provident Fund employer contribution
    esi_employer = fields.Float(string='ESI - Employer (3.25%)')  # India-specific: ESI employer contribution
    
    # India Benefits and Compliance
    gratuity = fields.Float(string='Gratuity Provision')  # India-specific: Gratuity as per Payment of Gratuity Act
    
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