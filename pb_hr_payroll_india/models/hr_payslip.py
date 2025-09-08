# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    
    @api.model
    def create(self, vals):
        """Override create to ensure payslips use correct structure based on context"""
        payroll_country = self.env.context.get('payroll_country')
        
        if payroll_country and 'employee_id' in vals:
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            
            # Get active contract for the employee
            active_contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)
            
            if active_contract:
                # Ensure the contract has the correct structure for the payroll country
                correct_structure = self._get_structure_for_country(payroll_country)
                if correct_structure and active_contract.struct_id.id != correct_structure.id:
                    # Update contract structure
                    active_contract.write({
                        'struct_id': correct_structure.id,
                        'name': f"{employee.name} - {payroll_country} Contract"
                    })
                    _logger.info(f"Updated contract structure for {employee.name} to {payroll_country}")
                
                # Ensure contract and payslip use the same structure
                vals['contract_id'] = active_contract.id
                vals['struct_id'] = active_contract.struct_id.id
        
        return super(HrPayslip, self).create(vals)
    
    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        """Enhanced onchange to respect payroll country context"""
        result = super(HrPayslip, self).onchange_employee()
        
        payroll_country = self.env.context.get('payroll_country')
        if payroll_country and self.employee_id:
            # Ensure we're using the correct structure for the country
            correct_structure = self._get_structure_for_country(payroll_country)
            if correct_structure:
                # Check if employee has active contract with correct structure
                active_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('state', '=', 'open'),
                    ('struct_id', '=', correct_structure.id)
                ], limit=1)
                
                if active_contract:
                    self.contract_id = active_contract
                    self.struct_id = correct_structure
                elif self.contract_id and self.contract_id.struct_id.id != correct_structure.id:
                    # Update existing contract structure
                    self.contract_id.write({'struct_id': correct_structure.id})
                    self.struct_id = correct_structure
        
        return result
    
    def _get_structure_for_country(self, payroll_country):
        """Get the salary structure for the specified country"""
        structure_mapping = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure', 
            'IN': 'India Salary Structure'
        }
        
        structure_name = structure_mapping.get(payroll_country)
        if not structure_name:
            return None
        
        return self.env['hr.payroll.structure'].search([
            ('name', '=', structure_name)
        ], limit=1)
    
    def compute_sheet(self):
        """Override compute_sheet to ensure correct structure is used"""
        for payslip in self:
            payroll_country = self.env.context.get('payroll_country')
            
            if payroll_country:
                correct_structure = self._get_structure_for_country(payroll_country)
                if correct_structure and payslip.struct_id.id != correct_structure.id:
                    # Update payslip structure if needed
                    payslip.write({'struct_id': correct_structure.id})
                    
                    # Also update contract structure if needed
                    if payslip.contract_id and payslip.contract_id.struct_id.id != correct_structure.id:
                        payslip.contract_id.write({'struct_id': correct_structure.id})
        
        return super(HrPayslip, self).compute_sheet()

    def update_payslip_lines_from_zoho_data(self, payslip):
        """
        India-specific override: Use India field mappings only for India payslips.
        For all other payslips, use the parent method.
        """
        # Check if this is an India payslip by examining the structure
        is_india_payslip = (payslip.struct_id and 
                           'india' in payslip.struct_id.name.lower()) or \
                          self.env.context.get('payroll_country') == 'IN'
        
        if not is_india_payslip:
            # Use parent method for non-India payslips (preserves Vietnam/Indonesia functionality)
            return super().update_payslip_lines_from_zoho_data(payslip)
        
        # India-specific processing only
        payroll_from_spreadsheet = self.env['ir.config_parameter'].sudo().get_param('payroll_from_spreadsheet')
        if payroll_from_spreadsheet == 'True':
            zoho_data = self.env['zoho.employee.data'].search(
                [('employee_id', '=', payslip.employee_id.employee_id)]
            )
            if zoho_data:
                # India-specific field mapping (completely isolated)
                india_field_mapping = {
                    # ===== INDIA-SPECIFIC PAYROLL MAPPINGS =====
                    # Basic salary components
                    'BASIC': 'base_salary',  # Reuse existing base_salary field
                    'BASIC_SALARY': 'base_salary',  # Alternative basic salary code
                    
                    # India allowances
                    'HRA': 'hra',  # India-specific: House Rent Allowance
                    'SPECIAL_ALLOWANCE': 'special_allowance',  # India-specific allowance
                    'BOOKS_ALLOWANCE': 'books_allowance',  # India-specific: Books/education allowance
                    'LTA': 'lta',  # India-specific: Leave Travel Allowance
                    'MEDICAL_ALLOWANCE': 'meal_allowance',  # Reuse existing meal_allowance
                    'TRANSPORT_ALLOWANCE': 'taxi_allowance',  # Reuse existing taxi_allowance
                    'PHONE_ALLOWANCE': 'phone_allowance',  # Reuse existing phone_allowance
                    'OTHER_ALLOWANCES': 'other_income',  # Reuse existing other_income
                    
                    # India deductions (employee contributions)
                    'PF_EMPLOYEE': 'pf_employee',  # India-specific: PF employee (12%)
                    'ESI_EMPLOYEE': 'esi_employee',  # India-specific: ESI employee (0.75%)
                    'PROFESSIONAL_TAX': 'professional_tax',  # India-specific: Professional tax
                    'INCOME_TAX': 'income_tax',  # India-specific: Income tax (TDS)
                    
                    # India employer contributions
                    'PF_EMPLOYER': 'pf_employer',  # India-specific: PF employer (12%)
                    'ESI_EMPLOYER': 'esi_employer',  # India-specific: ESI employer (3.25%)
                    'GRATUITY': 'gratuity_provision',  # India-specific: Gratuity provision
                    
                    # Generic mappings for India compatibility
                    'GROSS': 'gross_salary',
                    'NET': 'net_pay',
                    'NETPAY': 'net_pay',
                }
                
                # Apply India-specific field mapping
                for line in payslip.line_ids:
                    zoho_field = india_field_mapping.get(line.code)
                    if zoho_field and hasattr(zoho_data, zoho_field):
                        line.amount = getattr(zoho_data, zoho_field) or 0.0


class HrContract(models.Model):
    _inherit = 'hr.contract'
    
    def write(self, vals):
        """Override write to log structure changes"""
        if 'struct_id' in vals:
            for contract in self:
                if contract.struct_id.id != vals['struct_id']:
                    old_structure = contract.struct_id.name if contract.struct_id else 'None'
                    new_structure = self.env['hr.payroll.structure'].browse(vals['struct_id']).name
                    _logger.info(f"Contract structure changed for {contract.employee_id.name}: {old_structure} -> {new_structure}")
        
        return super(HrContract, self).write(vals)


class ZohoStagingImporter(models.TransientModel):
    _inherit = 'zoho.staging.importer'
    
    def import_employee_data(self):
        """Override to ensure contracts are created with correct structure"""
        result = super(ZohoStagingImporter, self).import_employee_data()
        
        payroll_country = self.env.context.get('payroll_country', self.payroll_country)
        if payroll_country:
            # Process employees for the specific payroll country
            self.process_employees_for_payroll(payroll_country)
        
        return result