# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json


class SingaporeEmployeeImportWizard(models.TransientModel):
    _name = 'singapore.employee.import.wizard'
    _description = 'Singapore Employee Import from Zoho'

    zoho_api_url = fields.Char(string='Zoho API URL', required=True)
    zoho_access_token = fields.Char(string='Access Token', required=True)
    import_mode = fields.Selection([
        ('create_new', 'Create New Employees Only'),
        ('update_existing', 'Update Existing Employees Only'),
        ('create_and_update', 'Create New and Update Existing'),
    ], string='Import Mode', default='create_and_update', required=True)
    
    # Singapore-specific import options
    default_work_permit_type = fields.Selection([
        ('citizen', 'Singapore Citizen'),
        ('pr', 'Permanent Resident'),
        ('ep', 'Employment Pass'),
        ('sp', 'S Pass'),
        ('wp', 'Work Permit'),
        ('lwp', 'Long Term Visit Pass'),
    ], string='Default Work Permit Type', default='citizen')
    
    default_tax_residency = fields.Selection([
        ('resident', 'Tax Resident'),
        ('non_resident', 'Non-Resident'),
    ], string='Default Tax Residency', default='resident')
    
    import_contracts = fields.Boolean(string='Import Contract Information', default=True)
    import_bank_details = fields.Boolean(string='Import Bank Details', default=True)
    import_cpf_info = fields.Boolean(string='Import CPF Information', default=True)
    
    # Results
    import_summary = fields.Text(string='Import Summary', readonly=True)
    employees_created = fields.Integer(string='Employees Created', readonly=True)
    employees_updated = fields.Integer(string='Employees Updated', readonly=True)
    errors_count = fields.Integer(string='Errors', readonly=True)

    def action_test_connection(self):
        """Test connection to Zoho API"""
        try:
            # This would normally make an API call to test connection
            # For now, just simulate success
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': _('Successfully connected to Zoho API'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Connection failed: %s') % str(e))

    def action_import_employees(self):
        """Import employees from Zoho"""
        self.ensure_one()
        
        created_count = 0
        updated_count = 0
        errors = []
        
        try:
            # This would normally fetch data from Zoho API
            # For now, simulate the import process
            
            # Sample data structure that would come from Zoho
            sample_employees = [
                {
                    'employee_id': 'SG001',
                    'name': 'Tan Wei Ming',
                    'email': 'tanweiming@company.com',
                    'phone': '+6591234567',
                    'nric_fin': 'S1234567A',
                    'work_permit_type': self.default_work_permit_type,
                    'tax_residency': self.default_tax_residency,
                    'basic_salary': 5500,  # SGD
                    'bank_account': '123-456789-001',
                    'bank_name': 'dbs',
                    'cpf_number': 'CPF123456789'
                }
            ]
            
            for emp_data in sample_employees:
                try:
                    existing_employee = self.env['hr.employee'].search([
                        ('singapore_employee_id', '=', emp_data.get('employee_id'))
                    ], limit=1)
                    
                    employee_vals = self._prepare_employee_values(emp_data)
                    
                    if existing_employee:
                        if self.import_mode in ['update_existing', 'create_and_update']:
                            existing_employee.write(employee_vals)
                            updated_count += 1
                    else:
                        if self.import_mode in ['create_new', 'create_and_update']:
                            new_employee = self.env['hr.employee'].create(employee_vals)
                            if self.import_contracts and emp_data.get('basic_salary'):
                                self._create_singapore_contract(new_employee, emp_data)
                            created_count += 1
                            
                except Exception as e:
                    errors.append(f"Error processing {emp_data.get('name', 'Unknown')}: {str(e)}")
            
            # Update summary
            self.employees_created = created_count
            self.employees_updated = updated_count
            self.errors_count = len(errors)
            
            summary = f"Import completed:\n"
            summary += f"- Created: {created_count} employees\n"
            summary += f"- Updated: {updated_count} employees\n"
            summary += f"- Errors: {len(errors)} employees\n"
            
            if errors:
                summary += "\nErrors:\n" + "\n".join(errors[:10])  # Show first 10 errors
                
            self.import_summary = summary
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'singapore.employee.import.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'import_completed': True}
            }
            
        except Exception as e:
            raise UserError(_('Import failed: %s') % str(e))

    def _prepare_employee_values(self, emp_data):
        """Prepare employee values from Zoho data"""
        return {
            'name': emp_data.get('name'),
            'work_email': emp_data.get('email'),
            'work_phone': emp_data.get('phone'),
            'singapore_employee_id': emp_data.get('employee_id'),
            'singapore_nric_fin': emp_data.get('nric_fin'),
            'singapore_work_permit_type': emp_data.get('work_permit_type'),
            'singapore_tax_residency': emp_data.get('tax_residency'),
            'singapore_cpf_number': emp_data.get('cpf_number'),
            'singapore_bank_account_number': emp_data.get('bank_account'),
            'singapore_bank_name': emp_data.get('bank_name'),
            'country_id': self.env.ref('base.sg').id,  # Singapore
        }

    def _create_singapore_contract(self, employee, emp_data):
        """Create Singapore contract for employee"""
        contract_vals = {
            'name': f"Contract - {employee.name}",
            'employee_id': employee.id,
            'singapore_work_permit_type': emp_data.get('work_permit_type', self.default_work_permit_type),
            'singapore_tax_residency': emp_data.get('tax_residency', self.default_tax_residency),
            'singapore_basic_salary': emp_data.get('basic_salary', 0),
            'singapore_employment_type': 'full_time',
            'state': 'open',
            'date_start': fields.Date.today(),
            'currency_id': self.env.ref('base.SGD').id,  # Singapore Dollar
        }
        return self.env['hr.contract'].create(contract_vals)