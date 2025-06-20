# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import datetime


class ZohoTimesheetImporter(models.TransientModel):
    _inherit = 'zoho.timesheet.importer'
    
    def _create_or_update_employee(self):
        """Override to handle country-specific payroll structure"""
        # Get the selected payroll country from context
        payroll_country = self.env.context.get('payroll_country', 'VN')
        
        # Fetch all records from zoho.employee.data
        zoho_employees = self.env['zoho.employee.data'].search([])
        
        for zoho_employee in zoho_employees:
            # Update payroll country in zoho employee data
            zoho_employee.payroll_country = payroll_country
            
            employee = self.env['hr.employee'].search([('employee_id', '=', zoho_employee.employee_id)], limit=1)
            
            # Validate required fields
            if not zoho_employee.department:
                raise ValidationError(f'Department is not specified for the employee with ID {zoho_employee.employee_id}')
            
            # Create/update department
            department = self.env['hr.department'].search([('name', '=', zoho_employee.department)], limit=1)
            if not department:
                department = self.env['hr.department'].create({'name': zoho_employee.department})
            
            # Create/update job
            if not zoho_employee.designation:
                raise ValidationError(f'Designation is not specified for the employee with ID {zoho_employee.employee_id}')
            
            job = self.env['hr.job'].search([('name', '=', zoho_employee.designation)], limit=1)
            if not job:
                job = self.env['hr.job'].create({
                    'name': zoho_employee.designation,
                    'department_id': department.id
                })
            
            # Prepare employee data
            employee_data = self._prepare_employee_data(zoho_employee, department, job)
            
            if employee:
                employee.write(employee_data)
            else:
                new_employee = self.env['hr.employee'].create(employee_data)
                self._create_employee_contract(new_employee, zoho_employee, payroll_country)
            
            # Update existing contract if employee exists
            if employee and employee.contract_ids:
                self._update_employee_contract(employee, zoho_employee, payroll_country)
    
    def _prepare_employee_data(self, zoho_employee, department, job):
        """Prepare employee data dictionary"""
        return {
            'name': zoho_employee.full_name_vn or zoho_employee.full_name_en,
            'department_id': department.id,
            'work_email': zoho_employee.email,
            'work_location': zoho_employee.location_name,
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
        else:
            structure_name = 'Vietnam Salary Structure'
        
        salary_structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
        if not salary_structure:
            raise UserError(f"Salary structure '{structure_name}' not found!")
        
        return salary_structure
    
    def _create_employee_contract(self, employee, zoho_employee, payroll_country):
        """Create employee contract with country-specific structure"""
        salary_structure = self._get_salary_structure(payroll_country)
        
        gen_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not gen_journal:
            raise UserError("No general journal found!")
        
        # Determine contract type
        contract_type = zoho_employee.employee_type or 'Permanent'
        existing_contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type)], limit=1)
        if not existing_contract_type:
            existing_contract_type = self.env['hr.contract.type'].create({'name': contract_type})
        
        contract_data = {
            'name': f"{employee.name} Contract",
            'employee_id': employee.id,
            'date_start': zoho_employee.contract_from or datetime.date(2000, 1, 1),
            'date_end': zoho_employee.contract_to or datetime.date(2100, 1, 1),
            'state': 'open',
            'struct_id': salary_structure.id,
            'wage': zoho_employee.base_salary,
            'journal_id': gen_journal.id,
            'type_id': existing_contract_type.id,
        }
        
        # Add country-specific fields
        if payroll_country == 'ID':
            contract_data.update(self._get_indonesia_contract_fields(zoho_employee))
        else:
            contract_data.update(self._get_vietnam_contract_fields(zoho_employee))
        
        self.env['hr.contract'].create(contract_data)
    
    def _update_employee_contract(self, employee, zoho_employee, payroll_country):
        """Update employee contract with country-specific data"""
        latest_contract = employee.contract_ids.sorted(lambda c: c.date_start, reverse=True)[0]
        
        salary_structure = self._get_salary_structure(payroll_country)
        
        contract_data = {
            'date_start': zoho_employee.contract_from or datetime.date(2000, 1, 1),
            'date_end': zoho_employee.contract_to or datetime.date(2100, 1, 1),
            'state': 'open',
            'struct_id': salary_structure.id,
            'wage': zoho_employee.base_salary,
        }
        
        # Add country-specific fields
        if payroll_country == 'ID':
            contract_data.update(self._get_indonesia_contract_fields(zoho_employee))
        else:
            contract_data.update(self._get_vietnam_contract_fields(zoho_employee))
        
        latest_contract.write(contract_data)
        
        # Update advantages
        self._update_contract_advantages(latest_contract, zoho_employee, payroll_country)
    
    def _get_indonesia_contract_fields(self, zoho_employee):
        """Get Indonesia-specific contract fields"""
        return {
            'pph21_rate': 5.0,  # Default PPh 21 rate
            'bpjs_kesehatan_employee': 1.0,
            'bpjs_kesehatan_employer': 4.0,
            'bpjs_tk_jht_employee': 2.0,
            'bpjs_tk_jht_employer': 3.7,
            'bpjs_tk_jp_employee': 1.0,
            'bpjs_tk_jp_employer': 2.0,
            'bpjs_tk_jkm': 0.3,
            'bpjs_tk_jkk': 0.24,
            'union_dues': zoho_employee.union_dues or 0,
            'loan_deduction': zoho_employee.loan_deductions or 0,
        }
    
    def _get_vietnam_contract_fields(self, zoho_employee):
        """Get Vietnam-specific contract fields"""
        return {
            'tupart': zoho_employee.tu_part,
            'shuipart': zoho_employee.shui_part,
            'costcenter': zoho_employee.costcenter,
            'location': zoho_employee.location_name,
            'dependents': zoho_employee.number_of_dependents,
        }
    
    def _update_contract_advantages(self, contract, zoho_employee, payroll_country):
        """Update contract advantages based on country"""
        # This method can be extended to handle country-specific advantages
        advantage_mappings = [
            ('gas_allowance', 'Gas Allowance'),
            ('phone_allowance', 'Phone Allowance'),
            ('meal_allowance', 'Meal Allowance'),
            ('resp_allowance', 'Responsibility Allowance'),
            ('park_allowance', 'Parking Allowance'),
            ('taxi_allowance', 'Taxi Allowance'),
        ]
        
        for field_name, advantage_name in advantage_mappings:
            value = getattr(zoho_employee, field_name, 0)
            if value:
                advantage = contract.advantage_ids.filtered(lambda a: a.name == advantage_name)
                if advantage:
                    advantage.amount = value
                else:
                    contract.advantage_ids = [(0, 0, {
                        'name': advantage_name,
                        'amount': value,
                        'contract_id': contract.id
                    })]


class SpreadsheetSpreadsheet(models.Model):
    _inherit = 'spreadsheet.spreadsheet'
    
    def import_json_data(self):
        """Override to handle country-specific spreadsheet"""
        payroll_country = self.env.context.get('payroll_country', 'VN')
        
        # Call parent method with context
        return super(SpreadsheetSpreadsheet, self.with_context(payroll_country=payroll_country)).import_json_data()
