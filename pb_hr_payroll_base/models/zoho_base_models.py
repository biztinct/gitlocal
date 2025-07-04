# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class ZohoEmployeeDataBase(models.Model):
    _name = 'zoho.employee.data'
    _description = 'Base Zoho Employee Data'
    _order = 'employee_id desc'
    
    # Common fields across all countries
    employee_id = fields.Char('Employee ID', required=True)
    full_name_en = fields.Char('Full Name (English)', required=True)
    full_name_vn = fields.Char('Full Name (Vietnamese)')
    email = fields.Char('Email', required=True)
    mobile = fields.Char('Mobile')
    date_of_birth = fields.Date('Date of Birth')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')
    ], string='Gender')
    
    # Employment details
    department = fields.Char('Department')
    designation = fields.Char('Designation')
    employee_type = fields.Char('Employee Type')
    employee_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('terminated', 'Terminated')
    ], string='Employee Status', default='active')
    
    # Location and contact
    location_name = fields.Char('Location')
    address = fields.Text('Address')
    
    # Dates
    date_of_joining = fields.Date('Date of Joining')
    confirmation_date = fields.Date('Confirmation Date')
    termination_date = fields.Date('Termination Date')
    
    # Salary information
    basic_salary = fields.Float('Basic Salary')
    gross_salary = fields.Float('Gross Salary')
    
    # Country payroll identification
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country', required=True)
    
    # Processing status
    processed = fields.Boolean('Processed', default=False)
    processing_notes = fields.Text('Processing Notes')
    employee_id_odoo = fields.Many2one('hr.employee', string='Linked Employee')
    
    def name_get(self):
        """Override name_get to show meaningful name"""
        result = []
        for record in self:
            name = f"[{record.employee_id}] {record.full_name_en or record.full_name_vn}"
            result.append((record.id, name))
        return result
    
    @api.model
    def create_employee_and_contract(self, payroll_country):
        """Create employee and contract - to be implemented by country modules"""
        raise NotImplementedError(_('This method must be implemented by country-specific modules'))
    
    def action_create_employee(self):
        """Create Odoo employee from Zoho data"""
        if self.processed:
            raise UserError(_('This employee has already been processed'))
        
        try:
            # This will be overridden by country-specific modules
            employee = self.create_employee_and_contract(self.payroll_country)
            self.write({
                'processed': True,
                'employee_id_odoo': employee.id,
                'processing_notes': f'Successfully created employee on {fields.Datetime.now()}'
            })
            return {
                'type': 'ir.actions.act_window',
                'name': 'Created Employee',
                'res_model': 'hr.employee',
                'view_mode': 'form',
                'res_id': employee.id,
                'target': 'current'
            }
        except Exception as e:
            self.write({
                'processing_notes': f'Error: {str(e)}'
            })
            raise UserError(_('Error creating employee: %s') % str(e))
    
    def action_update_employee(self):
        """Update existing Odoo employee with Zoho data"""
        if not self.employee_id_odoo:
            raise UserError(_('No linked employee found. Create employee first.'))
        
        try:
            # Update basic employee information
            employee_data = self._prepare_employee_update_data()
            self.employee_id_odoo.write(employee_data)
            
            self.write({
                'processing_notes': f'Successfully updated employee on {fields.Datetime.now()}'
            })
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Updated Employee',
                'res_model': 'hr.employee',
                'view_mode': 'form',
                'res_id': self.employee_id_odoo.id,
                'target': 'current'
            }
        except Exception as e:
            self.write({
                'processing_notes': f'Update Error: {str(e)}'
            })
            raise UserError(_('Error updating employee: %s') % str(e))
    
    def action_view_employee(self):
        """View the linked Odoo employee - MISSING METHOD ADDED"""
        if not self.employee_id_odoo:
            raise UserError(_('No linked employee found. Create employee first.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Employee',
            'res_model': 'hr.employee',
            'view_mode': 'form',
            'res_id': self.employee_id_odoo.id,
            'target': 'current'
        }
    
    def _prepare_employee_update_data(self):
        """Prepare data for employee update"""
        return {
            'name': self.full_name_en or self.full_name_vn,
            'work_email': self.email,
            'mobile_phone': self.mobile,
            'birthday': self.date_of_birth,
            'gender': self.gender,
        }

class ZohoStagingImporter(models.TransientModel):
    _name = 'zoho.staging.importer'
    _description = 'Zoho Employee Data Importer'
    
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country', required=True, default='VN')
    
    import_mode = fields.Selection([
        ('new_only', 'Import New Employees Only'),
        ('update_existing', 'Update Existing Employees'),
        ('both', 'Import New and Update Existing')
    ], string='Import Mode', default='both', required=True)
    
    def action_import_employees(self):
        """Import employees from Zoho staging"""
        zoho_employees = self.env['zoho.employee.data'].search([
            ('payroll_country', '=', self.payroll_country),
            ('processed', '=', False)
        ])
        
        if not zoho_employees:
            raise UserError(_('No unprocessed employees found for %s') % self.payroll_country)
        
        success_count = 0
        error_count = 0
        
        for zoho_employee in zoho_employees:
            try:
                zoho_employee.action_create_employee()
                success_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f"Failed to process employee {zoho_employee.employee_id}: {str(e)}")
        
        message = _(
            'Import completed:\n'
            '- Successfully processed: %d\n'
            '- Errors: %d\n'
            '- Total: %d'
        ) % (success_count, error_count, len(zoho_employees))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Results'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True
            }
        }
    
    def action_view_staging_data(self):
        """View staging data for selected country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.payroll_country} Staging Data',
            'res_model': 'zoho.employee.data',
            'view_mode': 'tree,form',
            'domain': [('payroll_country', '=', self.payroll_country)],
            'context': {'default_payroll_country': self.payroll_country}
        }