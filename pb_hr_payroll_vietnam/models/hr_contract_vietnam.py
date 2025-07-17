# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrContractVietnam(models.Model):
    _inherit = 'hr.contract'

    # Vietnam-specific contract fields
    vietnam_region = fields.Selection([
        ('region1', 'Region I (Hanoi, Ho Chi Minh City)'),
        ('region2', 'Region II (Can Tho, Da Nang, Hai Phong)'),
        ('region3', 'Region III (Bien Hoa, Vung Tau, Nha Trang)'),
        ('region4', 'Region IV (Other provinces)'),
    ], string='Vietnam Region', help='Minimum wage region for Vietnam payroll')
    
    vietnam_contract_type = fields.Selection([
        ('indefinite', 'Indefinite Term Contract'),
        ('definite', 'Definite Term Contract'),
        ('seasonal', 'Seasonal Contract'),
        ('probation', 'Probation Contract'),
    ], string='Vietnam Contract Type', default='indefinite')
    
    vietnam_social_insurance_number = fields.Char(string='Social Insurance Number')
    vietnam_tax_code = fields.Char(string='Vietnam Tax Code')
    vietnam_bank_account = fields.Char(string='Vietnam Bank Account')
    vietnam_bank_name = fields.Char(string='Bank Name')
    
    # Vietnam salary breakdown
    vietnam_basic_salary = fields.Monetary(string='Basic Salary (VND)', currency_field='currency_id')
    vietnam_house_allowance = fields.Monetary(string='House Allowance (VND)', currency_field='currency_id')
    vietnam_transport_allowance = fields.Monetary(string='Transport Allowance (VND)', currency_field='currency_id')
    vietnam_meal_allowance = fields.Monetary(string='Meal Allowance (VND)', currency_field='currency_id')
    vietnam_phone_allowance = fields.Monetary(string='Phone Allowance (VND)', currency_field='currency_id')
    vietnam_other_allowances = fields.Monetary(string='Other Allowances (VND)', currency_field='currency_id')
    
    # Vietnam leave entitlements
    vietnam_annual_leave_days = fields.Integer(string='Annual Leave Days', default=12)
    vietnam_sick_leave_days = fields.Integer(string='Sick Leave Days', default=30)
    vietnam_maternity_leave_days = fields.Integer(string='Maternity Leave Days', default=182)
    
    @api.depends('vietnam_basic_salary', 'vietnam_house_allowance', 'vietnam_transport_allowance', 
                 'vietnam_meal_allowance', 'vietnam_phone_allowance', 'vietnam_other_allowances')
    def _compute_vietnam_total_salary(self):
        """Compute total salary for Vietnam contract"""
        for contract in self:
            contract.vietnam_total_salary = (
                contract.vietnam_basic_salary +
                contract.vietnam_house_allowance +
                contract.vietnam_transport_allowance +
                contract.vietnam_meal_allowance +
                contract.vietnam_phone_allowance +
                contract.vietnam_other_allowances
            )
    
    vietnam_total_salary = fields.Monetary(
        string='Total Salary (VND)', 
        currency_field='currency_id',
        compute='_compute_vietnam_total_salary',
        store=True
    )

    @api.model
    def _get_vietnam_minimum_wage(self, region):
        """Get minimum wage for Vietnam region"""
        minimum_wages = {
            'region1': 4680000,  # VND per month
            'region2': 4160000,
            'region3': 3640000,
            'region4': 3250000,
        }
        return minimum_wages.get(region, 3250000)

    @api.constrains('vietnam_basic_salary', 'vietnam_region')
    def _check_vietnam_minimum_wage(self):
        """Ensure basic salary meets Vietnam minimum wage requirements"""
        for contract in self:
            if contract.vietnam_region and contract.vietnam_basic_salary:
                min_wage = contract._get_vietnam_minimum_wage(contract.vietnam_region)
                if contract.vietnam_basic_salary < min_wage:
                    raise ValueError(
                        _('Basic salary (%.0f VND) is below minimum wage (%.0f VND) for %s') % 
                        (contract.vietnam_basic_salary, min_wage, dict(contract._fields['vietnam_region'].selection)[contract.vietnam_region])
                    )