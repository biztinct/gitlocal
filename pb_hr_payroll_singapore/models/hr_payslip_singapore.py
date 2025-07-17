# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class HrPayslipSingapore(models.Model):
    _inherit = 'hr.payslip'

    # Add currency_id field if it doesn't exist in base model
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)

    # Singapore-specific fields
    singapore_tax_residency = fields.Selection([
        ('resident', 'Tax Resident'),
        ('non_resident', 'Non-Resident'),
    ], string='Tax Residency Status', default='resident')
    
    singapore_work_permit_type = fields.Selection([
        ('citizen', 'Singapore Citizen'),
        ('pr', 'Permanent Resident'),
        ('ep', 'Employment Pass'),
        ('sp', 'S Pass'),
        ('wp', 'Work Permit'),
        ('lwp', 'Long Term Visit Pass'),
    ], string='Work Permit Type', default='citizen')
    
    singapore_nric_fin = fields.Char(string='NRIC/FIN Number')
    singapore_iras_number = fields.Char(string='IRAS Tax Reference Number')
    
    # Singapore salary components
    singapore_basic_salary = fields.Monetary(string='Basic Salary (SGD)', currency_field='currency_id')
    singapore_allowances = fields.Monetary(string='Allowances (SGD)', currency_field='currency_id')
    singapore_overtime_amount = fields.Monetary(string='Overtime Amount (SGD)', currency_field='currency_id')
    singapore_bonus = fields.Monetary(string='Bonus/AWS (SGD)', currency_field='currency_id')
    singapore_commission = fields.Monetary(string='Commission (SGD)', currency_field='currency_id')
    
    # Singapore deductions
    singapore_income_tax = fields.Monetary(string='Income Tax (SGD)', currency_field='currency_id')
    singapore_cpf_employee = fields.Monetary(string='CPF - Employee (SGD)', currency_field='currency_id')
    singapore_sdl_employee = fields.Monetary(string='SDL - Employee (SGD)', currency_field='currency_id')
    
    # Employer contributions
    singapore_cpf_employer = fields.Monetary(string='CPF - Employer (SGD)', currency_field='currency_id')
    singapore_sdl_employer = fields.Monetary(string='SDL - Employer (SGD)', currency_field='currency_id')
    singapore_fwl_employer = fields.Monetary(string='Foreign Worker Levy (SGD)', currency_field='currency_id')
    
    # CPF breakdown
    singapore_cpf_ordinary = fields.Monetary(string='CPF Ordinary Account (SGD)', currency_field='currency_id')
    singapore_cpf_special = fields.Monetary(string='CPF Special Account (SGD)', currency_field='currency_id')
    singapore_cpf_medisave = fields.Monetary(string='CPF Medisave (SGD)', currency_field='currency_id')

    @api.model
    def _get_singapore_cpf_rates(self, age, citizenship_status):
        """Get CPF contribution rates based on age and citizenship status"""
        if citizenship_status not in ['citizen', 'pr']:
            return {'employee': 0, 'employer': 0}
            
        # CPF rates for citizens and PRs based on age
        if age < 35:
            return {'employee': 0.20, 'employer': 0.17}  # 20% employee, 17% employer
        elif age < 50:
            return {'employee': 0.20, 'employer': 0.17}
        elif age < 55:
            return {'employee': 0.20, 'employer': 0.17}
        elif age < 60:
            return {'employee': 0.135, 'employer': 0.09}  # Reduced rates
        elif age < 65:
            return {'employee': 0.075, 'employer': 0.06}  # Further reduced
        else:
            return {'employee': 0.05, 'employer': 0.075}   # Senior rates

    @api.depends('singapore_basic_salary', 'singapore_allowances', 'singapore_overtime_amount', 'singapore_bonus', 'singapore_commission')
    def _compute_singapore_gross_salary(self):
        """Compute gross salary for Singapore"""
        for payslip in self:
            payslip.singapore_gross_salary = (
                payslip.singapore_basic_salary + 
                payslip.singapore_allowances + 
                payslip.singapore_overtime_amount + 
                payslip.singapore_bonus +
                payslip.singapore_commission
            )

    singapore_gross_salary = fields.Monetary(
        string='Gross Salary (SGD)', 
        currency_field='currency_id',
        compute='_compute_singapore_gross_salary',
        store=True
    )

    def action_get_employee_data_sg(self):
        """Singapore-specific employee data import from Zoho"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Singapore Employee Data'),
            'res_model': 'singapore.employee.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_country': 'singapore'}
        }

    def action_edit_spreadsheet_sg(self):
        """Singapore-specific spreadsheet editing"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Singapore Payroll Spreadsheet'),
            'res_model': 'spreadsheet.spreadsheet',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_country': 'singapore',
                'default_currency': 'SGD'
            }
        }

    def _singapore_calculate_income_tax(self):
        """Calculate Singapore Income Tax based on residency status"""
        for payslip in self:
            if payslip.singapore_tax_residency == 'resident':
                # Progressive tax rates for residents
                taxable_income = payslip.singapore_gross_salary - payslip.singapore_cpf_employee
                
                # Singapore tax brackets (annual rates, need to prorate for monthly)
                tax_amount = 0
                annual_income = taxable_income * 12
                
                if annual_income <= 20000:
                    tax_amount = 0
                elif annual_income <= 30000:
                    tax_amount = (annual_income - 20000) * 0.02
                elif annual_income <= 40000:
                    tax_amount = 200 + (annual_income - 30000) * 0.035
                elif annual_income <= 80000:
                    tax_amount = 550 + (annual_income - 40000) * 0.07
                elif annual_income <= 120000:
                    tax_amount = 3350 + (annual_income - 80000) * 0.115
                elif annual_income <= 160000:
                    tax_amount = 7950 + (annual_income - 120000) * 0.15
                elif annual_income <= 200000:
                    tax_amount = 13950 + (annual_income - 160000) * 0.18
                elif annual_income <= 240000:
                    tax_amount = 21150 + (annual_income - 200000) * 0.19
                elif annual_income <= 280000:
                    tax_amount = 28750 + (annual_income - 240000) * 0.195
                elif annual_income <= 320000:
                    tax_amount = 36550 + (annual_income - 280000) * 0.20
                else:
                    tax_amount = 44550 + (annual_income - 320000) * 0.22
                
                # Convert annual tax to monthly
                payslip.singapore_income_tax = tax_amount / 12
            else:
                # Non-resident flat rate (15% or 22% depending on income level)
                if payslip.singapore_gross_salary * 12 <= 22000:
                    payslip.singapore_income_tax = payslip.singapore_gross_salary * 0.15
                else:
                    payslip.singapore_income_tax = payslip.singapore_gross_salary * 0.22

    def _singapore_calculate_cpf(self):
        """Calculate Singapore CPF contributions"""
        for payslip in self:
            if not payslip.employee_id.birthday:
                continue
                
            # Calculate employee age
            today = fields.Date.today()
            age = today.year - payslip.employee_id.birthday.year
            
            # Get CPF rates
            cpf_rates = payslip._get_singapore_cpf_rates(age, payslip.singapore_work_permit_type)
            
            # CPF salary ceiling (SGD 6,000 per month)
            cpf_salary = min(payslip.singapore_gross_salary, 6000)
            
            # Calculate contributions
            payslip.singapore_cpf_employee = cpf_salary * cpf_rates['employee']
            payslip.singapore_cpf_employer = cpf_salary * cpf_rates['employer']
            
            # Calculate CPF account allocations for employee contribution
            total_employee_cpf = payslip.singapore_cpf_employee
            if age < 35:
                payslip.singapore_cpf_ordinary = total_employee_cpf * 0.6167  # 61.67%
                payslip.singapore_cpf_special = total_employee_cpf * 0.1667   # 16.67%
                payslip.singapore_cpf_medisave = total_employee_cpf * 0.2166  # 21.66%
            elif age < 55:
                payslip.singapore_cpf_ordinary = total_employee_cpf * 0.6167
                payslip.singapore_cpf_special = total_employee_cpf * 0.1667
                payslip.singapore_cpf_medisave = total_employee_cpf * 0.2166
            else:
                # Different allocations for older workers
                payslip.singapore_cpf_ordinary = total_employee_cpf * 0.15
                payslip.singapore_cpf_special = total_employee_cpf * 0.0
                payslip.singapore_cpf_medisave = total_employee_cpf * 0.85

    def _singapore_calculate_sdl(self):
        """Calculate Skills Development Levy"""
        for payslip in self:
            # SDL is 0.25% of gross salary, capped at SGD 11.25 per month
            sdl_amount = payslip.singapore_gross_salary * 0.0025
            payslip.singapore_sdl_employer = min(sdl_amount, 11.25)
            payslip.singapore_sdl_employee = 0  # SDL is employer responsibility only

    def _singapore_calculate_foreign_worker_levy(self):
        """Calculate Foreign Worker Levy for applicable workers"""
        for payslip in self:
            if payslip.singapore_work_permit_type == 'wp':
                # Work Permit holders subject to FWL (rates vary by sector)
                # This is a simplified calculation - actual rates depend on sector and quota
                payslip.singapore_fwl_employer = 650  # Example rate for manufacturing
            elif payslip.singapore_work_permit_type == 'sp':
                # S Pass holders subject to FWL
                payslip.singapore_fwl_employer = 330  # Fixed rate for S Pass
            else:
                payslip.singapore_fwl_employer = 0