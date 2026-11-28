# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrContract(models.Model):
    _inherit = 'hr.contract'
    
    # India specific fields
    pf_employee_rate = fields.Float(string='PF Employee Rate (%)', default=12.0)
    pf_employer_rate = fields.Float(string='PF Employer Rate (%)', default=12.0)
    esi_employee_rate = fields.Float(string='ESI Employee Rate (%)', default=0.75)
    esi_employer_rate = fields.Float(string='ESI Employer Rate (%)', default=3.25)
    
    # Tax related fields
    income_tax_rate = fields.Float(string='Income Tax Rate (%)', default=10.0)
    professional_tax = fields.Monetary(string='Professional Tax', default=200.0)
    
    # Additional India specific fields
    uan_number = fields.Char(string='UAN Number', help='Universal Account Number for PF')
    esi_number = fields.Char(string='ESI Number', help='Employee State Insurance Number')
    pan_number = fields.Char(string='PAN Number', help='Permanent Account Number')
    
    # Gratuity related
    gratuity_eligible = fields.Boolean(string='Gratuity Eligible', default=True)
    gratuity_rate = fields.Float(string='Gratuity Rate (days per year)', default=15.0)
    
    @api.model
    def create_india_contract_advantages(self, contract_id, zoho_employee):
        """Create contract advantages based on India salary components"""
        contract = self.browse(contract_id)
        
        # Define India salary components mapping
        india_components = {
            'BASIC': getattr(zoho_employee, 'basic_salary', 0) or 0,
            'HRA': getattr(zoho_employee, 'hra', 0) or 0,
            'SPECIAL_ALLOWANCE': getattr(zoho_employee, 'special_allowance', 0) or 0,
            'BOOKS_PERIODICALS': getattr(zoho_employee, 'books_periodicals', 0) or 0,
            'TELEPHONE_INTERNET': getattr(zoho_employee, 'telephone_internet', 0) or 0,
            'LEAVE_TRAVEL_ALLOWANCE': getattr(zoho_employee, 'leave_travel_allowance', 0) or 0,
            'PF': getattr(zoho_employee, 'pf', 0) or 0,
            'PROF_TAX': getattr(zoho_employee, 'prof_tax', 0) or 200,
            'INCOME_TAX': getattr(zoho_employee, 'income_tax', 0) or 0,
        }
        
        # Create advantages for each component
        for component_code, amount in india_components.items():
            if amount > 0:
                # Find the advantage template
                template = self.env['hr.contract.advantage.template'].search([
                    ('code', '=', component_code)
                ], limit=1)
                
                if template:
                    # Create the advantage
                    self.env['hr.contract.advantage'].create({
                        'contract_id': contract.id,
                        'advantage_template_id': template.id,
                        'amount': amount,
                    })
        
        return True