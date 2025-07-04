# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PayrollDashboard(models.Model):
    _name = 'payroll.dashboard'
    _description = 'Multi-Country Payroll Dashboard'
    
    name = fields.Char('Dashboard Name', compute='_compute_name', store=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Country', default='VN', required=True)
    
    # Country-specific configuration
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency')
    structure_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', compute='_compute_structure')
    
    # Dashboard statistics
    total_employees = fields.Integer('Total Employees', compute='_compute_statistics')
    active_contracts = fields.Integer('Active Contracts', compute='_compute_statistics')
    pending_payslips = fields.Integer('Pending Payslips', compute='_compute_statistics')
    
    @api.depends('country')
    def _compute_name(self):
        """Compute dashboard name based on country"""
        country_names = {
            'VN': 'Vietnam Payroll Dashboard',
            'ID': 'Indonesia Payroll Dashboard', 
            'IN': 'India Payroll Dashboard',
            'SG': 'Singapore Payroll Dashboard',
            'MY': 'Malaysia Payroll Dashboard',
        }
        for record in self:
            record.name = country_names.get(record.country, f'{record.country} Payroll Dashboard')
    
    @api.depends('country')
    def _compute_currency(self):
        """Get currency based on country"""
        currency_map = {
            'VN': 'VND',
            'ID': 'IDR',
            'IN': 'INR',
            'SG': 'SGD',
            'MY': 'MYR',
        }
        for record in self:
            currency_code = currency_map.get(record.country)
            if currency_code:
                record.currency_id = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
            else:
                record.currency_id = False
    
    @api.depends('country')
    def _compute_structure(self):
        """Get salary structure based on country"""
        structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure',
            'IN': 'India Salary Structure',
            'SG': 'Singapore Salary Structure',
            'MY': 'Malaysia Salary Structure',
        }
        for record in self:
            structure_name = structure_map.get(record.country)
            if structure_name:
                record.structure_id = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
            else:
                record.structure_id = False
    
    def _compute_statistics(self):
        """Compute dashboard statistics"""
        for record in self:
            # Get country-specific employees based on contract structure
            if record.structure_id:
                contracts = self.env['hr.contract'].search([
                    ('struct_id', '=', record.structure_id.id),
                    ('state', 'in', ['open', 'pending'])
                ])
                employees = contracts.mapped('employee_id')
                record.total_employees = len(employees)
                record.active_contracts = len(contracts.filtered(lambda c: c.state == 'open'))
                
                # Count pending payslips for this country's employees
                pending_payslips = self.env['hr.payslip'].search([
                    ('employee_id', 'in', employees.ids),
                    ('state', '=', 'draft')
                ])
                record.pending_payslips = len(pending_payslips)
            else:
                record.total_employees = 0
                record.active_contracts = 0
                record.pending_payslips = 0
    
    @api.model
    def get_or_create_dashboard(self, country_code):
        """Get or create a single dashboard record for the country"""
        dashboard = self.search([('country', '=', country_code)], limit=1)
        if not dashboard:
            dashboard = self.create({'country': country_code})
        return dashboard
    
    def get_country_config(self):
        """Get country-specific configuration"""
        return {
            'country': self.country,
            'currency': self.currency_id.name if self.currency_id else None,
            'structure': self.structure_id.name if self.structure_id else None,
        }
    
    # Base actions that can be overridden by country modules
    def action_get_employee_data(self):
        """Get employee data - to be overridden by country modules"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Get Employee Data - {self.country}',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': self.country}
        }
    
    def action_edit_spreadsheet(self):
        """Edit spreadsheet - to be overridden by country modules"""
        try:
            spreadsheet_id = f'__custom__.payrollstaging_{self.country.lower()}'
            spreadsheet = self.env.ref(spreadsheet_id, raise_if_not_found=False)
            if not spreadsheet:
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(f'{self.country} payroll spreadsheet not found.'))
            
            return spreadsheet.with_context(payroll_country=self.country).open_spreadsheet()
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_import_spreadsheet(self):
        """Import spreadsheet - to be overridden by country modules"""
        try:
            return self.with_context(payroll_country=self.country).import_spreadsheet()
        except Exception as e:
            raise UserError(_('Error importing spreadsheet: %s') % str(e))
    
    def action_view_employees(self):
        """View employees for this country"""
        if not self.structure_id:
            raise UserError(_('No salary structure configured for %s') % self.country)
        
        contracts = self.env['hr.contract'].search([
            ('struct_id', '=', self.structure_id.id)
        ])
        employee_ids = contracts.mapped('employee_id').ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Employees',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', employee_ids)],
            'context': {'create': False}
        }
    
    def action_view_payslips(self):
        """View payslips for this country"""
        if not self.structure_id:
            raise UserError(_('No salary structure configured for %s') % self.country)
        
        contracts = self.env['hr.contract'].search([
            ('struct_id', '=', self.structure_id.id)
        ])
        employee_ids = contracts.mapped('employee_id').ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Payslips',
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('employee_id', 'in', employee_ids)],
        }
    def action_view_employees_by_country(self):
        """View employees for specific country"""
        action_map = {
            'VN': 'pb_hr_payroll_base.action_vietnam_employees',
            'ID': 'pb_hr_payroll_base.action_indonesia_employees', 
            'IN': 'pb_hr_payroll_base.action_india_employees',
        }
        
        action_id = action_map.get(self.country)
        if action_id:
            return {
                'type': 'ir.actions.act_window',
                'name': f'{self.country} Employees',
                'res_model': 'hr.employee',
                'view_mode': 'tree,form',
                'domain': [('contract_ids.struct_id.payroll_country_code', '=', self.country)],
                'context': {'default_country_code': self.country}
            }
        else:
            return self.action_view_employees()

    def action_view_zoho_data_by_country(self):
        """View Zoho data for specific country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Zoho Data',
            'res_model': 'zoho.employee.data',
            'view_mode': 'tree,form',
            'domain': [('payroll_country', '=', self.country)],
            'context': {'default_payroll_country': self.country}
        }

    def action_create_salary_structure(self):
        """Create country-specific salary structure"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Create {self.country} Salary Structure',
            'res_model': 'hr.payroll.structure',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payroll_country_code': self.country,
                'default_name': f'{self.country} Salary Structure'
            }
        }