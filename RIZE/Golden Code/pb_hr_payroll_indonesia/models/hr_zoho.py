# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
import datetime

_logger = logging.getLogger(__name__)


class HrZohoIntegration(models.TransientModel):
    _inherit = 'zoho.staging.importer'
    
    def process_employees_for_payroll(self, payroll_country='VN'):
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
    
    def _process_single_employee_enhanced(self, zoho_employee, payroll_country):
        """Enhanced method to process a single employee with allowances and deductions"""
        # Find or create department
        department = self._get_or_create_department(zoho_employee.department)
        
        # Find or create job position
        job = self._get_or_create_job(zoho_employee.designation)
        
        # Check if employee already exists
        employee = self.env['hr.employee'].search([
            ('employee_id', '=', zoho_employee.employee_id)
        ], limit=1)
        
        # Prepare employee data (using the fixed method)
        employee_data = self._prepare_employee_data_fixed(zoho_employee, department, job)
        
        if employee:
            # Update existing employee
            employee.write(employee_data)
            _logger.info(f"Updated employee: {employee.name}")
        else:
            # Create new employee
            employee = self.env['hr.employee'].create(employee_data)
            _logger.info(f"Created new employee: {employee.name}")
        
        # Find or update employee contract
        contract = employee.contract_ids.filtered(lambda c: c.state == 'open')
        if not contract:
            contract = employee.contract_ids.sorted(lambda c: c.date_start, reverse=True)[:1]
        
        if contract:
            # Update existing contract advantages with enhanced fields
            self._update_contract_advantages_enhanced(contract, zoho_employee, payroll_country)
        else:
            # Create new contract with enhanced advantages
            contract = self._create_employee_contract_enhanced(employee, zoho_employee, payroll_country)
        
        return employee
    
    def _get_or_create_department(self, department_name):
        """Get or create department"""
        if not department_name:
            department_name = 'Unknown'
        
        department = self.env['hr.department'].search([('name', '=', department_name)], limit=1)
        if not department:
            department = self.env['hr.department'].create({'name': department_name})
        
        return department
    
    def _get_or_create_job(self, job_title):
        """Get or create job position"""
        if not job_title:
            job_title = 'Unknown'
        
        job = self.env['hr.job'].search([('name', '=', job_title)], limit=1)
        if not job:
            job = self.env['hr.job'].create({'name': job_title})
        
        return job
    
    def _prepare_employee_data_fixed(self, zoho_employee, department, job):
        """Prepare employee data dictionary - FIXED to remove work_location"""
        return {
            'name': zoho_employee.full_name_vn or zoho_employee.full_name_en,
            'department_id': department.id,
            'work_email': zoho_employee.email,
            # REMOVED: 'work_location': zoho_employee.location_name,  # This field doesn't exist
            'job_id': job.id,
            'gender': zoho_employee.gender,
            'org_employee_type': zoho_employee.employee_type,
            'birthday': zoho_employee.date_of_birth,
            'mobile_phone': zoho_employee.mobile,
            'marital': 'single' if zoho_employee.employee_status == 'Single' else 'married',
            'employee_id': zoho_employee.employee_id,
            'full_name_vn': zoho_employee.full_name_vn,
        }
    
    def _get_salary_structure(self, payroll_country):
        """Get salary structure based on country"""
        if payroll_country == 'ID':
            structure_name = 'Indonesia Salary Structure'
        elif payroll_country == 'IN':
            structure_name = 'India Salary Structure'
        else:
            structure_name = 'Vietnam Salary Structure'
        
        salary_structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
        if not salary_structure:
            raise UserError(f"Salary structure '{structure_name}' not found!")
        
        return salary_structure
    
    def _create_employee_contract_enhanced(self, employee, zoho_employee, payroll_country):
        """Create employee contract with enhanced advantages"""
        salary_structure = self._get_salary_structure(payroll_country)
        
        gen_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not gen_journal:
            raise UserError("No general journal found!")
        
        # Determine contract type
        contract_type_name = zoho_employee.employee_type or 'Permanent'
        contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type_name)], limit=1)
        if not contract_type:
            contract_type = self.env['hr.contract.type'].create({'name': contract_type_name})
        
        # Calculate contract dates
        date_start = zoho_employee.date_of_joining if hasattr(zoho_employee, 'date_of_joining') and zoho_employee.date_of_joining else datetime.date.today()
        
        # Prepare contract data
        contract_data = {
            'name': f"{employee.name} - {payroll_country} Contract",
            'employee_id': employee.id,
            'date_start': date_start,
            'state': 'open',
            'wage': getattr(zoho_employee, 'base_salary', 0) or 0,
            'type_id': contract_type.id,
            'journal_id': gen_journal.id,
            'struct_id': salary_structure.id,
            'dependents': getattr(zoho_employee, 'number_of_dependents', 0) or 0,
        }
        
        # Add location to contract if the field exists
        if hasattr(self.env['hr.contract']._fields, 'location'):
            contract_data['location'] = zoho_employee.location_name
        
        # Add country-specific contract fields
        if payroll_country == 'VN':
            # Vietnam specific fields
            if hasattr(self.env['hr.contract']._fields, 'tupart'):
                contract_data['tupart'] = getattr(zoho_employee, 'tu_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'shuipart'):
                contract_data['shuipart'] = getattr(zoho_employee, 'shui_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'costcenter'):
                contract_data['costcenter'] = getattr(zoho_employee, 'costcenter', '')
        
        # Create the contract
        contract = self.env['hr.contract'].create(contract_data)
        
        # Update contract advantages with enhanced fields
        self._update_contract_advantages_enhanced(contract, zoho_employee, payroll_country)
        
        return contract
    
    def _update_contract_advantages_enhanced(self, contract, zoho_employee, payroll_country):
        """Enhanced method to update contract advantages with new allowances and deductions"""
        
        # Standard advantage mappings (existing)
        standard_advantage_mappings = [
            ('gas_allowance', 'Gas Allowance', 'GASALL'),
            ('phone_allowance', 'Phone Allowance', 'PHONALL'),
            ('meal_allowance', 'Meal Allowance', 'MEALALL'),
            ('resp_allowance', 'Responsibility Allowance', 'RESPALL'),
            ('park_allowance', 'Parking Allowance', 'PARKALL'),
            ('taxi_allowance', 'Taxi Allowance', 'TAXIALL'),
        ]
        
        # Enhanced allowance mappings (new)
        enhanced_allowance_mappings = [
            ('fixed_allowance_1', 'Fixed Allowance 1', 'FIXALL1'),
            ('fixed_allowance_2', 'Fixed Allowance 2', 'FIXALL2'),
            ('commission', 'Commission', 'COMMIS'),
            ('sign_on_bonus', 'Sign on Bonus', 'SIGBON'),
            ('tunjangan_sewa_rumah', 'Tunjangan Sewa Rumah', 'TUNJSR'),
            ('tunjangan_duka', 'Tunjangan Duka', 'TUNJDK'),
            ('tunjangan_suka', 'Tunjangan Suka', 'TUNJSK'),
            ('severance_appreciation', 'Severance/ Appreciation', 'SEVAPP'),
            ('lain_lain_allowance', 'Lain-lain (Allowance)', 'LAINALL'),
        ]
        
        # Enhanced deduction mappings (new)
        enhanced_deduction_mappings = [
            ('deduction_1', 'Deduction 1', 'DEDUC1'),
            ('deduction_2', 'Deduction 2', 'DEDUC2'),
            ('deduction_3', 'Deduction 3', 'DEDUC3'),
            ('koperasi', 'Koperasi', 'KOPER'),
            ('pinjaman', 'Pinjaman', 'PINJAM'),
            ('cicilan', 'Cicilan', 'CICIL'),
            ('lain_lain_deduction', 'Lain-lain (Deduction)', 'LAINDED'),
        ]
        
        # Combine all mappings
        all_mappings = standard_advantage_mappings + enhanced_allowance_mappings + enhanced_deduction_mappings
        
        # Process each mapping
        for field_name, advantage_name, advantage_code in all_mappings:
            value = getattr(zoho_employee, field_name, 0)
            if value and value != 0:
                self._create_or_update_advantage(contract, advantage_name, advantage_code, value)
    
    def _create_or_update_advantage(self, contract, advantage_name, advantage_code, amount):
        """Create or update contract advantage"""
        try:
            # Check if contract advantages model exists
            if 'hr.contract.advantage' not in self.env:
                _logger.warning(f"hr.contract.advantage model not found, skipping {advantage_name}")
                return
            
            # Look for existing advantage template
            advantage_template = self.env['hr.contract.advantage.template'].search([
                ('code', '=', advantage_code)
            ], limit=1)
            
            if not advantage_template:
                # Create advantage template if it doesn't exist
                advantage_template = self.env['hr.contract.advantage.template'].create({
                    'name': advantage_name,
                    'code': advantage_code,
                    'lower_bound': -999999 if 'DEDUC' in advantage_code or advantage_code in ['KOPER', 'PINJAM', 'CICIL', 'LAINDED'] else 0,
                    'upper_bound': 0 if 'DEDUC' in advantage_code or advantage_code in ['KOPER', 'PINJAM', 'CICIL', 'LAINDED'] else 999999,
                    'default_value': amount,
                })
                _logger.info(f"Created new advantage template: {advantage_name} ({advantage_code})")
            
            # Look for existing advantage on contract
            existing_advantage = contract.advantages_ids.filtered(
                lambda a: a.advantage_template_id.code == advantage_code
            )
            
            if existing_advantage:
                # Update existing advantage
                existing_advantage.write({'amount': amount})
                _logger.info(f"Updated advantage {advantage_name}: {amount}")
            else:
                # Create new advantage
                contract.advantages_ids = [(0, 0, {
                    'name': advantage_name,
                    'advantage_template_id': advantage_template.id,
                    'advantage_template_code': advantage_code,
                    'amount': amount,
                    'contract_id': contract.id
                })]
                _logger.info(f"Created new advantage {advantage_name}: {amount}")
                
        except Exception as e:
            _logger.error(f"Error creating/updating advantage {advantage_name}: {str(e)}")


class SpreadsheetSpreadsheet(models.Model):
    _inherit = 'spreadsheet.spreadsheet'
    
    def import_json_data(self):
        """Enhanced import_json_data to handle allowances and deductions"""
        try:
            payroll_country = self.env.context.get('payroll_country', 'VN')
            
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
    
    def _process_enhanced_payroll_data(self, payroll_country):
        """Process enhanced payroll data from staging tables"""
        try:
            # Get all employees from staging data
            zoho_employees = self.env['zoho.staging.data'].search([])
            if not zoho_employees:
                zoho_employees = self.env['zoho.employee.data'].search([])
            
            if not zoho_employees:
                _logger.warning("No employee data found in staging tables")
                return
            
            # Process each employee
            integration_obj = self.env['zoho.staging.importer']
            for zoho_employee in zoho_employees:
                try:
                    integration_obj._process_single_employee_enhanced(zoho_employee, payroll_country)
                except Exception as e:
                    _logger.error(f"Error processing employee {zoho_employee.employee_id}: {str(e)}")
                    continue
            
            _logger.info(f"Processed {len(zoho_employees)} employees with enhanced allowances and deductions")
            
        except Exception as e:
            _logger.error(f"Error in _process_enhanced_payroll_data: {str(e)}")
            raise


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    @api.model
    def create(self, vals):
        """Override create to handle missing work_location field gracefully"""
        # Remove work_location if it exists in vals but not in model fields
        if 'work_location' in vals and 'work_location' not in self._fields:
            _logger.warning("work_location field not found in hr.employee model, removing from values")
            vals.pop('work_location', None)
        
        return super(HrEmployee, self).create(vals)
    
    def write(self, vals):
        """Override write to handle missing work_location field gracefully"""
        # Remove work_location if it exists in vals but not in model fields
        if 'work_location' in vals and 'work_location' not in self._fields:
            _logger.warning("work_location field not found in hr.employee model, removing from values")
            vals.pop('work_location', None)
        
        return super(HrEmployee, self).write(vals)