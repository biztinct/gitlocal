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
                currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
                record.currency_id = currency.id if currency else False
            else:
                record.currency_id = False
    
    @api.depends('country')
    def _compute_structure(self):
        """Get default payroll structure for country"""
        for record in self:
            structure = self.env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', record.country)
            ], limit=1)
            record.structure_id = structure.id if structure else False
    
    def _compute_statistics(self):
        """Compute dashboard statistics"""
        for record in self:
            if record.country:
                # Get employees by country
                employees = self.env['hr.employee'].search([
                    ('contract_ids.struct_id.payroll_country_code', '=', record.country)
                ])
                record.total_employees = len(employees)
                
                # Get active contracts by country
                contracts = self.env['hr.contract'].search([
                    ('struct_id.payroll_country_code', '=', record.country),
                    ('state', '=', 'open')
                ])
                record.active_contracts = len(contracts)
                
                # Get pending payslips by country
                pending_payslips = self.env['hr.payslip'].search([
                    ('contract_id.struct_id.payroll_country_code', '=', record.country),
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
    
    # === DASHBOARD ACTIONS - RENAMED TO AVOID CONFLICTS ===
    
    def action_get_employee_data(self):
        """Get employee data from external sources"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Import Employee Data - {self.country}',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': self.country}
        }
    
    def action_edit_spreadsheet(self):
        """Edit country-specific payroll spreadsheet"""
        try:
            # Try to find country-specific spreadsheet first
            spreadsheet_id = f'__custom__.payrollstaging_{self.country.lower()}'
            spreadsheet = self.env.ref(spreadsheet_id, raise_if_not_found=False)
            
            if not spreadsheet:
                # Fallback to generic spreadsheet
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                
            if not spreadsheet:
                raise UserError(_(f'No payroll spreadsheet found for {self.country}. Please contact your administrator.'))
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'{self.country} Payroll Spreadsheet',
                'res_model': 'spreadsheet.spreadsheet',
                'view_mode': 'form',
                'res_id': spreadsheet.id,
                'target': 'current'
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Spreadsheet Not Available'),
                    'message': _(f'Could not access {self.country} payroll spreadsheet: {str(e)}'),
                    'type': 'warning',
                    'sticky': False
                }
            }
    
    def action_import_spreadsheet(self):
        """Import data from spreadsheet"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Import {self.country} Payroll Data',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payroll_country': self.country,
                'default_import_mode': 'both'
            }
        }
    
    def action_dashboard_view_employees(self):
        """View employees for this country - RENAMED to avoid conflict"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Employees',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('contract_ids.struct_id.payroll_country_code', '=', self.country)],
            'context': {'default_country_code': self.country}
        }
    
    def action_dashboard_view_payslips(self):
        """View payslips for this country - RENAMED to avoid conflict"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Payslips',
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('contract_id.struct_id.payroll_country_code', '=', self.country)],
            'context': {'default_country_code': self.country}
        }

    def action_dashboard_view_contracts(self):
        """View contracts for this country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Contracts',
            'res_model': 'hr.contract',
            'view_mode': 'tree,form',
            'domain': [('struct_id.payroll_country_code', '=', self.country)],
            'context': {'default_country_code': self.country}
        }

    def action_dashboard_view_structures(self):
        """View payroll structures for this country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Payroll Structures',
            'res_model': 'hr.payroll.structure',
            'view_mode': 'tree,form',
            'domain': [('payroll_country_code', '=', self.country)],
            'context': {'default_payroll_country_code': self.country}
        }

    def action_dashboard_view_zoho_data(self):
        """View Zoho data for this country"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Zoho Data',
            'res_model': 'zoho.employee.data',
            'view_mode': 'tree,form',
            'domain': [('payroll_country', '=', self.country)],
            'context': {'default_payroll_country': self.country}
        }

    def action_open_country_selector(self):
        """Open country selector dialog"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Payroll Country',
            'res_model': 'payroll.country.selector',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_country': self.country}
        }