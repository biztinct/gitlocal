# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrContractSingapore(models.Model):
    _inherit = 'hr.contract'

    # Singapore-specific contract fields
    singapore_employment_type = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ], string='Employment Type', default='full_time')
    
    singapore_work_permit_type = fields.Selection([
        ('citizen', 'Singapore Citizen'),
        ('pr', 'Permanent Resident'),
        ('ep', 'Employment Pass'),
        ('sp', 'S Pass'),
        ('wp', 'Work Permit'),
        ('lwp', 'Long Term Visit Pass'),
    ], string='Work Permit Type', default='citizen')
    
    singapore_tax_residency = fields.Selection([
        ('resident', 'Tax Resident'),
        ('non_resident', 'Non-Resident'),
    ], string='Tax Residency Status', default='resident')
    
    singapore_nric_fin = fields.Char(string='NRIC/FIN Number')
    singapore_iras_number = fields.Char(string='IRAS Tax Reference Number')
    singapore_cpf_number = fields.Char(string='CPF Number')
    
    # Singapore salary breakdown
    singapore_basic_salary = fields.Monetary(string='Basic Salary (SGD)', currency_field='currency_id')
    singapore_fixed_allowance = fields.Monetary(string='Fixed Allowance (SGD)', currency_field='currency_id')
    singapore_transport_allowance = fields.Monetary(string='Transport Allowance (SGD)', currency_field='currency_id')
    singapore_meal_allowance = fields.Monetary(string='Meal Allowance (SGD)', currency_field='currency_id')
    singapore_mobile_allowance = fields.Monetary(string='Mobile Allowance (SGD)', currency_field='currency_id')
    singapore_aws_rate = fields.Float(string='AWS Rate (months)', default=1.0, help='Annual Wage Supplement rate')
    
    # Singapore CPF settings
    singapore_cpf_eligible = fields.Boolean(string='CPF Eligible', default=True)
    singapore_cpf_rate_override = fields.Boolean(string='Override CPF Rates', default=False)
    singapore_cpf_employee_rate = fields.Float(string='Employee CPF Rate (%)', default=20.0)
    singapore_cpf_employer_rate = fields.Float(string='Employer CPF Rate (%)', default=17.0)
    
    # Singapore leave entitlements
    singapore_annual_leave_days = fields.Integer(string='Annual Leave Entitlement', default=14)
    singapore_medical_leave_days = fields.Integer(string='Medical Leave Entitlement', default=14)
    singapore_maternity_leave_days = fields.Integer(string='Maternity Leave Days', default=112)  # 16 weeks
    singapore_paternity_leave_days = fields.Integer(string='Paternity Leave Days', default=14)   # 2 weeks
    
    # Bank details
    singapore_bank_name = fields.Selection([
        ('dbs', 'DBS Bank'),
        ('ocbc', 'OCBC Bank'), 
        ('uob', 'UOB Bank'),
        ('maybank', 'Maybank'),
        ('citibank', 'Citibank'),
        ('hsbc', 'HSBC'),
        ('scb', 'Standard Chartered'),
        ('other', 'Other'),
    ], string='Bank Name')
    
    singapore_bank_account = fields.Char(string='Bank Account Number')
    singapore_bank_swift = fields.Char(string='SWIFT Code')
    
    @api.depends('singapore_basic_salary', 'singapore_fixed_allowance', 'singapore_transport_allowance',
                 'singapore_meal_allowance', 'singapore_mobile_allowance')
    def _compute_singapore_total_salary(self):
        """Compute total salary for Singapore contract"""
        for contract in self:
            contract.singapore_total_salary = (
                contract.singapore_basic_salary +
                contract.singapore_fixed_allowance +
                contract.singapore_transport_allowance +
                contract.singapore_meal_allowance +
                contract.singapore_mobile_allowance
            )
    
    singapore_total_salary = fields.Monetary(
        string='Total Monthly Salary (SGD)', 
        currency_field='currency_id',
        compute='_compute_singapore_total_salary',
        store=True
    )

    @api.depends('singapore_total_salary', 'singapore_aws_rate')
    def _compute_singapore_annual_salary(self):
        """Compute annual salary including AWS"""
        for contract in self:
            monthly_salary = contract.singapore_total_salary or 0
            aws_months = contract.singapore_aws_rate or 0
            contract.singapore_annual_salary = monthly_salary * (12 + aws_months)
    
    singapore_annual_salary = fields.Monetary(
        string='Annual Salary (SGD)', 
        currency_field='currency_id',
        compute='_compute_singapore_annual_salary',
        store=True
    )

    @api.model
    def _get_singapore_cpf_rates(self, age, citizenship_status):
        """Get CPF contribution rates based on age and citizenship status"""
        if citizenship_status not in ['citizen', 'pr']:
            return {'employee': 0, 'employer': 0}
            
        # CPF rates for citizens and PRs based on age
        if age < 35:
            return {'employee': 20.0, 'employer': 17.0}
        elif age < 50:
            return {'employee': 20.0, 'employer': 17.0}
        elif age < 55:
            return {'employee': 20.0, 'employer': 17.0}
        elif age < 60:
            return {'employee': 13.5, 'employer': 9.0}
        elif age < 65:
            return {'employee': 7.5, 'employer': 6.0}
        else:
            return {'employee': 5.0, 'employer': 7.5}

    @api.constrains('singapore_basic_salary')
    def _check_singapore_minimum_wage(self):
        """Check if salary meets Singapore requirements"""
        for contract in self:
            if contract.singapore_work_permit_type == 'ep' and contract.singapore_basic_salary:
                # Employment Pass minimum salary requirement
                if contract.singapore_basic_salary < 5000:
                    raise ValueError(_('Employment Pass holders must have minimum salary of SGD 5,000'))
            elif contract.singapore_work_permit_type == 'sp' and contract.singapore_basic_salary:
                # S Pass minimum salary requirement  
                if contract.singapore_basic_salary < 3000:
                    raise ValueError(_('S Pass holders must have minimum salary of SGD 3,000'))

    @api.onchange('singapore_work_permit_type')
    def _onchange_singapore_work_permit_type(self):
        """Update CPF eligibility based on work permit type"""
        if self.singapore_work_permit_type in ['citizen', 'pr']:
            self.singapore_cpf_eligible = True
            self.singapore_tax_residency = 'resident'
        else:
            self.singapore_cpf_eligible = False
            if self.singapore_work_permit_type in ['wp', 'lwp']:
                self.singapore_tax_residency = 'non_resident'