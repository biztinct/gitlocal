# -*- coding: utf-8 -*-
# Payroll Dashboard Base Models

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PayrollDashboard(models.Model):
    """Multi-Country Payroll Dashboard"""
    _name = 'payroll.dashboard'
    _description = 'Payroll Dashboard'
    _order = 'sequence, name'
    
    name = fields.Char('Dashboard Name', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Country', required=True)
    
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Dashboard statistics (computed fields)
    employee_count = fields.Integer('Employee Count', compute='_compute_statistics')
    active_contracts = fields.Integer('Active Contracts', compute='_compute_statistics')
    pending_payslips = fields.Integer('Pending Payslips', compute='_compute_statistics')
    total_gross_salary = fields.Float('Total Gross Salary', compute='_compute_statistics')
    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_currency')
    
    # Related payroll structure
    structure_id = fields.Many2one('hr.payroll.structure', 'Payroll Structure', compute='_compute_statistics')
    
    @api.depends('country')
    def _compute_currency(self):
        """Compute currency based on country"""
        currency_map = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR', 'SG': 'SGD', 'MY': 'MYR'
        }
        
        for record in self:
            currency_code = currency_map.get(record.country, 'USD')
            currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
            record.currency_id = currency.id if currency else self.env.company.currency_id.id
    
    def _compute_statistics(self):
        """Compute dashboard statistics"""
        for record in self:
            # Get payroll structure for this country
            structure = self.env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', record.country),
                ('active', '=', True)
            ], limit=1)
            
            if structure:
                record.structure_id = structure.id
                
                # Get contracts using this structure
                contracts = self.env['hr.contract'].search([
                    ('struct_id', '=', structure.id),
                    ('state', '=', 'open')
                ])
                
                record.employee_count = len(contracts.mapped('employee_id'))
                record.active_contracts = len(contracts)
                record.total_gross_salary = sum(contracts.mapped('wage'))
                
                # Count pending payslips
                employees = contracts.mapped('employee_id')
                pending_payslips = self.env['hr.payslip'].search([
                    ('employee_id', 'in', employees.ids),
                    ('state', 'in', ['draft', 'verify'])
                ])
                record.pending_payslips = len(pending_payslips)
            else:
                record.structure_id = False
                record.employee_count = 0
                record.active_contracts = 0
                record.pending_payslips = 0
                record.total_gross_salary = 0.0
    
    def action_view_country_dashboard(self):
        """Open country-specific dashboard"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} Dashboard',
            'res_model': 'payroll.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_get_employee_data(self):
        """Get employee data - Base implementation, country modules can override"""
        # Check if country-specific method exists
        country_method = f'action_get_employee_data_{self.country.lower()}'
        if hasattr(self, country_method):
            return getattr(self, country_method)()
        
        # Fallback to generic Zoho staging import
        return {
            'type': 'ir.actions.act_window',
            'name': f'Import Employee Data - {self.country}',
            'res_model': 'zoho.staging.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_target_country': self.country}
        }
    
    def action_edit_spreadsheet(self):
        """Edit spreadsheet - Base implementation, country modules can override"""
        # Check if country-specific method exists
        country_method = f'action_edit_spreadsheet_{self.country.lower()}'
        if hasattr(self, country_method):
            return getattr(self, country_method)()
        
        # Fallback to generic spreadsheet action
        try:
            # Try to find country-specific spreadsheet first
            spreadsheet_id = f'__custom__.payrollstaging_{self.country.lower()}'
            spreadsheet = self.env.ref(spreadsheet_id, raise_if_not_found=False)
            
            if not spreadsheet:
                # Fallback to generic
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
            
            if spreadsheet:
                return spreadsheet.with_context(payroll_country=self.country).open_spreadsheet()
            else:
                # Generic action when no spreadsheet found
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Spreadsheet Not Available'),
                        'message': _(f'No spreadsheet configured for {self.country}. Please install the {self.country} payroll module.'),
                        'type': 'warning'
                    }
                }
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_import_spreadsheet(self):
        """Import spreadsheet - Base implementation, country modules can override"""
        # Check if country-specific method exists
        country_method = f'action_import_spreadsheet_{self.country.lower()}'
        if hasattr(self, country_method):
            return getattr(self, country_method)()
        
        # Fallback to generic import wizard
        return {
            'type': 'ir.actions.act_window',
            'name': f'Import {self.country} Payroll Data',
            'res_model': 'zoho.staging.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target_country': self.country,
                'default_import_mode': 'create_update'
            }
        }
    
    def action_view_employees_by_country(self):
        """View employees - Framework method, country modules can enhance"""
        # Get contracts for this country
        contracts = self.env['hr.contract'].search([
            ('struct_id.payroll_country_code', '=', self.country)
        ])
        employee_ids = contracts.mapped('employee_id').ids
        
        if not employee_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Employees Found'),
                    'message': _(f'No employees found for {self.country}. Please create payroll structures and contracts first.'),
                    'type': 'info'
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Employees',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', employee_ids)],
            'context': {'default_country_code': self.country}
        }
    
    def action_view_zoho_data_by_country(self):
        """View Zoho data - Framework method, available to all countries"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Zoho Data',
            'res_model': 'zoho.staging.data',
            'view_mode': 'tree,form',
            'domain': [('payroll_country', '=', self.country)],
            'context': {'default_payroll_country': self.country}
        }
    
    def action_create_salary_structure(self):
        """Create/edit salary structure - Framework method"""
        existing_structure = self.env['hr.payroll.structure'].search([
            ('payroll_country_code', '=', self.country),
            ('active', '=', True)
        ], limit=1)
        
        if existing_structure:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Edit {self.country} Salary Structure',
                'res_model': 'hr.payroll.structure',
                'res_id': existing_structure.id,
                'view_mode': 'form',
                'target': 'current'
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Create {self.country} Salary Structure',
                'res_model': 'hr.payroll.structure',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_payroll_country_code': self.country,
                    'default_name': f'{self.country} Payroll Structure',
                    'default_code': f'{self.country}_STD',
                    'default_structure_state': 'active'
                }
            }
    
    # Utility methods for country modules to use
    def get_country_employees(self):
        """Utility: Get all employees for this country"""
        contracts = self.env['hr.contract'].search([
            ('struct_id.payroll_country_code', '=', self.country)
        ])
        return contracts.mapped('employee_id')
    
    def get_country_payroll_structure(self):
        """Utility: Get payroll structure for this country"""
        return self.env['hr.payroll.structure'].search([
            ('payroll_country_code', '=', self.country),
            ('active', '=', True)
        ], limit=1)
    
    def get_country_salary_rules(self):
        """Utility: Get salary rules for this country"""
        return self.env['hr.salary.rule'].search([
            ('payroll_country_code', '=', self.country)
        ])
    
    def action_get_employee_data(self):
        """Get employee data from Zoho"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Import Employee Data - {self.country}',
            'res_model': 'zoho.staging.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_target_country': self.country}
        }
    
    def action_edit_spreadsheet(self):
        """Edit payroll spreadsheet"""
        try:
            # Try to find country-specific spreadsheet
            spreadsheet_id = f'__custom__.payrollstaging_{self.country.lower()}'
            spreadsheet = self.env.ref(spreadsheet_id, raise_if_not_found=False)
            
            if not spreadsheet:
                # Fallback to generic spreadsheet
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
            
            if not spreadsheet:
                # Create a basic spreadsheet action if none found
                return {
                    'type': 'ir.actions.client',
                    'tag': 'action_open_spreadsheet',
                    'name': f'{self.country} Payroll Spreadsheet',
                    'params': {
                        'spreadsheet_id': 'new',
                        'country': self.country,
                    }
                }
            
            return spreadsheet.with_context(payroll_country=self.country).open_spreadsheet()
            
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_import_spreadsheet(self):
        """Import data from spreadsheet"""
        try:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Import {self.country} Payroll Data',
                'res_model': 'zoho.staging.import.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_target_country': self.country,
                    'default_import_mode': 'create_update'
                }
            }
        except Exception as e:
            raise UserError(_('Error importing spreadsheet: %s') % str(e))
    
    def action_view_employees_by_country(self):
        """View employees for this country"""
        if not self.structure_id:
            # Try to find or create structure
            structure = self.env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', self.country),
                ('active', '=', True)
            ], limit=1)
            
            if not structure:
                # Offer to create structure
                return {
                    'type': 'ir.actions.act_window',
                    'name': f'Create {self.country} Payroll Structure',
                    'res_model': 'hr.payroll.structure',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_payroll_country_code': self.country,
                        'default_name': f'{self.country} Payroll Structure',
                        'default_code': f'{self.country}_STD'
                    }
                }
        
        # Get contracts using this country's structure
        contracts = self.env['hr.contract'].search([
            ('struct_id.payroll_country_code', '=', self.country)
        ])
        employee_ids = contracts.mapped('employee_id').ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Employees',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', employee_ids)] if employee_ids else [('id', '=', False)],
            'context': {'default_country_code': self.country}
        }
    
    def action_view_zoho_data_by_country(self):
        """View Zoho staging data for this country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Zoho Data',
            'res_model': 'zoho.staging.data',
            'view_mode': 'tree,form',
            'domain': [('payroll_country', '=', self.country)],
            'context': {'default_payroll_country': self.country}
        }
    
    def action_create_salary_structure(self):
        """Create or edit salary structure for this country"""
        existing_structure = self.env['hr.payroll.structure'].search([
            ('payroll_country_code', '=', self.country),
            ('active', '=', True)
        ], limit=1)
        
        if existing_structure:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Edit {self.country} Salary Structure',
                'res_model': 'hr.payroll.structure',
                'res_id': existing_structure.id,
                'view_mode': 'form',
                'target': 'current'
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Create {self.country} Salary Structure',
                'res_model': 'hr.payroll.structure',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_payroll_country_code': self.country,
                    'default_name': f'{self.country} Payroll Structure',
                    'default_code': f'{self.country}_STD',
                    'default_structure_state': 'active',
                    'default_is_base_structure': True
                }
            }
    
    def action_view_salary_rules_by_country(self):
        """View salary rules for this country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Salary Rules',
            'res_model': 'hr.salary.rule',
            'view_mode': 'tree,form',
            'domain': [('payroll_country_code', '=', self.country)],
            'context': {'default_payroll_country_code': self.country}
        }
    
    def action_view_contracts_by_country(self):
        """View contracts for this country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Contracts',
            'res_model': 'hr.contract',
            'view_mode': 'tree,form',
            'domain': [('payroll_country', '=', self.country)],
            'context': {'default_payroll_country': self.country}
        }
    
    def action_view_payslips_by_country(self):
        """View payslips for this country"""
        # Get employees for this country
        contracts = self.env['hr.contract'].search([
            ('struct_id.payroll_country_code', '=', self.country)
        ])
        employee_ids = contracts.mapped('employee_id').ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Payslips',
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('employee_id', 'in', employee_ids)] if employee_ids else [('id', '=', False)],
            'context': {'default_country': self.country}
        }'type': 'ir.actions.act_window',
            'name': f'{self.name} Dashboard',
            'res_model': 'payroll.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

class PayrollCountrySelector(models.Model):
    """Country selector for payroll navigation"""
    _name = 'payroll.country.selector'
    _description = 'Payroll Country Selector'
    
    name = fields.Char('Name', compute='_compute_name')
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Country', required=True)
    
    description = fields.Text('Description')
    is_active = fields.Boolean('Is Active', default=True)
    
    @api.depends('country_code')
    def _compute_name(self):
        country_names = {
            'VN': 'Vietnam Payroll',
            'ID': 'Indonesia Payroll', 
            'IN': 'India Payroll',
            'SG': 'Singapore Payroll',
            'MY': 'Malaysia Payroll',
        }
        
        for record in self:
            record.name = country_names.get(record.country_code, 'Unknown Country')
    
    def action_open_country_payroll(self):
        """Open country-specific payroll views"""
        country_actions = {
            'VN': 'pb_hr_payroll_base.action_vietnam_employees',
            'ID': 'pb_hr_payroll_base.action_indonesia_employees',
            'IN': 'pb_hr_payroll_base.action_india_employees',
        }
        
        action_id = country_actions.get(self.country_code)
        if action_id:
            return {
                'type': 'ir.actions.act_window',
                'name': f'{self.name} Management',
                'res_model': 'hr.employee',
                'view_mode': 'tree,form',
                'domain': [('payroll_country', '=', self.country_code)],
                'context': {'default_payroll_country': self.country_code},
            }
        else:
            raise UserError(_('No payroll management configured for %s') % self.name)

class CountrySelectorWizard(models.TransientModel):
    """Wizard for country selection"""
    _name = 'country.selector.wizard'
    _description = 'Country Selector Wizard'
    
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Select Country', required=True)
    
    target_action = fields.Selection([
        ('employees', 'View Employees'),
        ('contracts', 'View Contracts'),
        ('payslips', 'View Payslips'),
        ('structures', 'View Payroll Structures'),
        ('rules', 'View Salary Rules'),
        ('dashboard', 'View Dashboard'),
    ], string='Action', default='employees')
    
    def action_open_selected_country(self):
        """Open selected country action"""
        if self.target_action == 'employees':
            return {
                'type': 'ir.actions.act_window',
                'name': f'{dict(self._fields["country_code"].selection)[self.country_code]} Employees',
                'res_model': 'hr.employee',
                'view_mode': 'tree,form',
                'domain': [('payroll_country', '=', self.country_code)],
                'context': {'default_payroll_country': self.country_code},
            }
        elif self.target_action == 'contracts':
            return {
                'type': 'ir.actions.act_window',
                'name': f'{dict(self._fields["country_code"].selection)[self.country_code]} Contracts',
                'res_model': 'hr.contract',
                'view_mode': 'tree,form',
                'domain': [('payroll_country', '=', self.country_code)],
                'context': {'default_payroll_country': self.country_code},
            }
        elif self.target_action == 'structures':
            return {
                'type': 'ir.actions.act_window',
                'name': f'{dict(self._fields["country_code"].selection)[self.country_code]} Payroll Structures',
                'res_model': 'hr.payroll.structure',
                'view_mode': 'tree,form',
                'domain': [('payroll_country_code', '=', self.country_code)],
                'context': {'default_payroll_country_code': self.country_code},
            }
        elif self.target_action == 'rules':
            return {
                'type': 'ir.actions.act_window',
                'name': f'{dict(self._fields["country_code"].selection)[self.country_code]} Salary Rules',
                'res_model': 'hr.salary.rule',
                'view_mode': 'tree,form',
                'domain': [('payroll_country_code', '=', self.country_code)],
                'context': {'default_payroll_country_code': self.country_code},
            }
        # Add more target actions as needed
        
        return {'type': 'ir.actions.act_window_close'}