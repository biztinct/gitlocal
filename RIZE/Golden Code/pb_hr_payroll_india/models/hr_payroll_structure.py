# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    
    def get_india_spreadsheet_reference(self):
        """Get the external ID for India payroll spreadsheet"""
        return '__custom__.payrollstaging_india'


class ZohoTimesheetImporter(models.TransientModel):
    _inherit = 'zoho.timesheet.importer'
    
    def _create_employee_contract_india(self, employee, zoho_employee):
        """Create employee contract specifically for India"""
        # Get India salary structure
        india_structure = self.env['hr.payroll.structure'].search([
            ('name', '=', 'India Salary Structure')
        ], limit=1)
        
        if not india_structure:
            raise UserError("India Salary Structure not found!")
        
        # Get general journal
        gen_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not gen_journal:
            raise UserError("No general journal found!")
        
        # Determine contract type
        contract_type_name = getattr(zoho_employee, 'employee_type', 'Permanent') or 'Permanent'
        contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type_name)], limit=1)
        if not contract_type:
            contract_type = self.env['hr.contract.type'].create({'name': contract_type_name})
        
        # Calculate contract dates
        date_start = getattr(zoho_employee, 'date_of_joining', datetime.date.today()) or datetime.date.today()
        
        # Calculate total wage from India components
        basic = getattr(zoho_employee, 'basic_salary', 0) or 0
        hra = getattr(zoho_employee, 'hra', 0) or 0
        special_allowance = getattr(zoho_employee, 'special_allowance', 0) or 0
        books_periodicals = getattr(zoho_employee, 'books_periodicals', 0) or 0
        telephone_internet = getattr(zoho_employee, 'telephone_internet', 0) or 0
        lta = getattr(zoho_employee, 'leave_travel_allowance', 0) or 0
        
        total_wage = basic + hra + special_allowance + books_periodicals + telephone_internet + lta
        
        # Prepare contract data
        contract_data = {
            'name': f"{employee.name} - India Contract",
            'employee_id': employee.id,
            'date_start': date_start,
            'state': 'open',
            'wage': total_wage,
            'type_id': contract_type.id,
            'journal_id': gen_journal.id,
            'struct_id': india_structure.id,
            'dependents': getattr(zoho_employee, 'number_of_dependents', 0) or 0,
            
            # India specific fields
            'pf_employee_rate': 12.0,
            'pf_employer_rate': 12.0,
            'esi_employee_rate': 0.75,
            'esi_employer_rate': 3.25,
            'professional_tax': getattr(zoho_employee, 'prof_tax', 200) or 200,
            'uan_number': getattr(zoho_employee, 'uan_number', '') or '',
            'pan_number': getattr(zoho_employee, 'pan_number', '') or '',
        }
        
        # Create contract
        contract = self.env['hr.contract'].create(contract_data)
        
        # Create contract advantages for India salary components
        self.env['hr.contract'].create_india_contract_advantages(contract.id, zoho_employee)
        
        return contract