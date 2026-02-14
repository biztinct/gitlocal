# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class HrPayslipVietnam(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip']

    # Add currency_id field if it doesn't exist in base model
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)

    # Vietnam-specific fields
    vietnam_region = fields.Selection([
        ('region1', 'Region I (Hanoi, Ho Chi Minh City)'),
        ('region2', 'Region II (Can Tho, Da Nang, Hai Phong)'),
        ('region3', 'Region III (Bien Hoa, Vung Tau, Nha Trang)'),
        ('region4', 'Region IV (Other provinces)'),
    ], string='Vietnam Region', help='Minimum wage region in Vietnam')
    
    vietnam_tax_code = fields.Char(string='Vietnam Tax Code', help='Personal Income Tax code')
    vietnam_social_insurance_number = fields.Char(string='Social Insurance Number')
    vietnam_dependents = fields.Integer(string='Number of Dependents', default=0)
    
    # Vietnam salary components
    vietnam_basic_salary = fields.Monetary(string='Basic Salary (VND)', currency_field='currency_id')
    vietnam_allowances = fields.Monetary(string='Allowances (VND)', currency_field='currency_id')
    vietnam_overtime_amount = fields.Monetary(string='Overtime Amount (VND)', currency_field='currency_id')
    vietnam_bonus = fields.Monetary(string='Bonus/13th Month (VND)', currency_field='currency_id')
    
    # Vietnam deductions
    vietnam_personal_income_tax = fields.Monetary(string='Personal Income Tax (VND)', currency_field='currency_id')
    vietnam_social_insurance_employee = fields.Monetary(string='Social Insurance - Employee (VND)', currency_field='currency_id')
    vietnam_health_insurance_employee = fields.Monetary(string='Health Insurance - Employee (VND)', currency_field='currency_id')
    vietnam_unemployment_insurance_employee = fields.Monetary(string='Unemployment Insurance - Employee (VND)', currency_field='currency_id')
    
    # Employer contributions
    vietnam_social_insurance_employer = fields.Monetary(string='Social Insurance - Employer (VND)', currency_field='currency_id')
    vietnam_health_insurance_employer = fields.Monetary(string='Health Insurance - Employer (VND)', currency_field='currency_id')
    vietnam_unemployment_insurance_employer = fields.Monetary(string='Unemployment Insurance - Employer (VND)', currency_field='currency_id')
    vietnam_accident_insurance_employer = fields.Monetary(string='Accident Insurance - Employer (VND)', currency_field='currency_id')

    @api.model
    def _get_vietnam_minimum_wage(self, region, date_from):
        """Get minimum wage based on Vietnam region and date"""
        # Vietnam minimum wage rates (example - should be updated with current rates)
        minimum_wages = {
            'region1': 4680000,  # VND per month for Region I
            'region2': 4160000,  # VND per month for Region II  
            'region3': 3640000,  # VND per month for Region III
            'region4': 3250000,  # VND per month for Region IV
        }
        return minimum_wages.get(region, 3250000)

    @api.depends('vietnam_basic_salary', 'vietnam_allowances', 'vietnam_overtime_amount', 'vietnam_bonus')
    def _compute_vietnam_gross_salary(self):
        """Compute gross salary for Vietnam"""
        for payslip in self:
            payslip.vietnam_gross_salary = (
                payslip.vietnam_basic_salary + 
                payslip.vietnam_allowances + 
                payslip.vietnam_overtime_amount + 
                payslip.vietnam_bonus
            )

    vietnam_gross_salary = fields.Monetary(
        string='Gross Salary (VND)', 
        currency_field='currency_id',
        compute='_compute_vietnam_gross_salary',
        store=True
    )

    def action_get_employee_data_vn(self):
        """Vietnam-specific employee data import from Zoho"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Vietnam Employee Data'),
            'res_model': 'vietnam.employee.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_country': 'vietnam'}
        }

    def action_edit_spreadsheet_vn(self):
        """Vietnam-specific spreadsheet editing"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Payroll Spreadsheet'),
            'res_model': 'spreadsheet.spreadsheet',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_country': 'vietnam',
                'default_currency': 'VND'
            }
        }

    def _vietnam_calculate_personal_income_tax(self):
        """Calculate Vietnam Personal Income Tax based on progressive rates"""
        for payslip in self:
            # Taxable income = Gross - Social Insurance - Dependent deductions
            social_insurance_total = (
                payslip.vietnam_social_insurance_employee +
                payslip.vietnam_health_insurance_employee +
                payslip.vietnam_unemployment_insurance_employee
            )
            
            # Personal deduction: 11,000,000 VND + 4,400,000 VND per dependent
            personal_deduction = 11000000 + (payslip.vietnam_dependents * 4400000)
            
            taxable_income = payslip.vietnam_gross_salary - social_insurance_total - personal_deduction
            
            # Progressive tax rates for Vietnam
            tax_amount = 0
            if taxable_income <= 5000000:
                tax_amount = taxable_income * 0.05
            elif taxable_income <= 10000000:
                tax_amount = 250000 + (taxable_income - 5000000) * 0.10
            elif taxable_income <= 18000000:
                tax_amount = 750000 + (taxable_income - 10000000) * 0.15
            elif taxable_income <= 32000000:
                tax_amount = 1950000 + (taxable_income - 18000000) * 0.20
            elif taxable_income <= 52000000:
                tax_amount = 4750000 + (taxable_income - 32000000) * 0.25
            elif taxable_income <= 80000000:
                tax_amount = 9750000 + (taxable_income - 52000000) * 0.30
            else:
                tax_amount = 18150000 + (taxable_income - 80000000) * 0.35
                
            payslip.vietnam_personal_income_tax = max(0, tax_amount)

    def _vietnam_calculate_social_insurance(self):
        """Calculate Vietnam Social Insurance contributions"""
        for payslip in self:
            # Base salary for social insurance calculation (capped)
            si_base = min(payslip.vietnam_basic_salary, 29800000)  # Max SI base salary
            
            # Employee contributions
            payslip.vietnam_social_insurance_employee = si_base * 0.08      # 8%
            payslip.vietnam_health_insurance_employee = si_base * 0.015     # 1.5%
            payslip.vietnam_unemployment_insurance_employee = si_base * 0.01 # 1%
            
            # Employer contributions  
            payslip.vietnam_social_insurance_employer = si_base * 0.175     # 17.5%
            payslip.vietnam_health_insurance_employer = si_base * 0.03      # 3%
            payslip.vietnam_unemployment_insurance_employer = si_base * 0.01 # 1%
            payslip.vietnam_accident_insurance_employer = si_base * 0.005   # 0.5%