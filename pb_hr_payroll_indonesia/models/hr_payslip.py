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
        if payroll_country == 'VN':
            structure_name = 'Vietnam Salary Structure'
        elif payroll_country == 'ID':
            structure_name = 'Indonesia Salary Structure'
        else:
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