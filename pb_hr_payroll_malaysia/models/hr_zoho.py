# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
import datetime

_logger = logging.getLogger(__name__)


class HrZohoIntegration(models.TransientModel):
    _inherit = 'zoho.staging.importer'
    
    def process_employees_for_payroll(self, payroll_country='MY'):
        """Process employees based on payroll country"""
        # Get all zoho staging data
        zoho_employees = self.env['zoho.staging.data'].search([])
        
        if not zoho_employees:
            raise UserError(_('No employee data found. Please import employee data first.'))
        
        processed_count = 0
        error_count = 0
        
        for zoho_employee in zoho_employees:
            try:
                self._process_single_employee_enhanced(zoho_employee, payroll_country)
                processed_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f"Error processing employee {zoho_employee.employee_id}: {str(e)}")
                continue
        
        return {
            'processed': processed_count,
            'errors': error_count,
            'total': len(zoho_employees)
        }
    
    def _get_salary_structure(self, payroll_country):
        """Get salary structure based on country"""
        if payroll_country == 'MY':
            structure_name = 'Malaysia Salary Structure'
        elif payroll_country == 'ID':
            structure_name = 'Indonesia Salary Structure'
        elif payroll_country == 'IN':
            structure_name = 'India Salary Structure'
        else:
            structure_name = 'Vietnam Salary Structure'
        
        salary_structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
        if not salary_structure:
            raise UserError(f"Salary structure '{structure_name}' not found!")
        
        return salary_structure
    
    def _update_contract_advantages_enhanced(self, contract, zoho_employee, payroll_country):
        """Enhanced method to update contract advantages with Malaysia-specific allowances"""
        
        # Malaysia-specific advantage mappings
        malaysia_advantage_mappings = [
            ('gas_allowance', 'Gas Allowance', 'GASALL'),
            ('phone_allowance', 'Phone Allowance', 'PHONALL'),
            ('meal_allowance', 'Meal Allowance', 'MEALALL'),
            ('transport_allowance', 'Transport Allowance', 'TRANSALL'),
            ('housing_allowance', 'Housing Allowance', 'HOUSEALL'),
            ('epf_employer', 'EPF Employer', 'EPFEMP'),
            ('socso_employer', 'SOCSO Employer', 'SOCSOEMP'),
            ('eis_employer', 'EIS Employer', 'EISEMP'),
        ]
        
        # Malaysia-specific deduction mappings
        malaysia_deduction_mappings = [
            ('epf_employee', 'EPF Employee', 'EPFDED'),
            ('socso_employee', 'SOCSO Employee', 'SOCSOEED'),
            ('eis_employee', 'EIS Employee', 'EISDED'),
            ('pcb_tax', 'PCB Income Tax', 'PCBDED'),
            ('loan_deduction', 'Loan Deduction', 'LOANDD'),
        ]
        
        # Combine all mappings
        all_mappings = malaysia_advantage_mappings + malaysia_deduction_mappings
        
        # Process each mapping
        for field_name, advantage_name, advantage_code in all_mappings:
            value = getattr(zoho_employee, field_name, 0)
            if value and value != 0:
                self._create_or_update_advantage(contract, advantage_name, advantage_code, value)


class SpreadsheetSpreadsheet(models.Model):
    _inherit = 'spreadsheet.spreadsheet'
    
    def import_json_data(self):
        """Enhanced import_json_data to handle Malaysia allowances and deductions"""
        try:
            payroll_country = self.env.context.get('payroll_country', 'MY')
            
            # Call parent method first to get existing functionality
            result = super(SpreadsheetSpreadsheet, self).import_json_data()
            
            # Process enhanced allowances and deductions for each employee
            self._process_enhanced_payroll_data(payroll_country)
            
            return result
            
        except ValueError as e:
            error_msg = str(e)
            if 'work_location' in error_msg:
                raise UserError(_(
                    "Configuration Error: The 'work_location' field is not available in your system. "
                    "This has been fixed in the latest version. Please update your module or contact your administrator."
                ))
            else:
                raise UserError(_("Import Error: %s") % error_msg)
        except Exception as e:
            _logger.error(f"Error importing enhanced spreadsheet data: {str(e)}")
            raise UserError(_("An error occurred while importing the spreadsheet: %s") % str(e))