# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PayrollDashboard(models.Model):  # Changed to Model instead of TransientModel
    _name = 'payroll.dashboard'
    _description = 'Payroll Dashboard'
    
    name = fields.Char('Dashboard Name', compute='_compute_name', store=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', default='VN')
    
    @api.depends('country')
    def _compute_name(self):
        """Compute dashboard name based on country"""
        country_names = {
            'VN': 'Vietnam Payroll Dashboard',
            'ID': 'Indonesia Payroll Dashboard', 
            'IN': 'India Payroll Dashboard'
        }
        for record in self:
            record.name = country_names.get(record.country, 'Payroll Dashboard')
    
    @api.model
    def get_or_create_dashboard(self, country_code):
        """Get or create a single dashboard record for the country"""
        dashboard = self.search([('country', '=', country_code)], limit=1)
        if not dashboard:
            dashboard = self.create({'country': country_code})
        return dashboard
    
    @api.model
    def open_vietnam_dashboard(self):
        """Open Vietnam dashboard actions"""
        dashboard = self.get_or_create_dashboard('VN')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vietnam Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_indonesia.view_payroll_dashboard_vietnam').id,
            'res_id': dashboard.id,
            'target': 'current',
            'context': {'default_payroll_country': 'VN'}
        }
    
    @api.model
    def open_indonesia_dashboard(self):
        """Open Indonesia dashboard actions"""
        dashboard = self.get_or_create_dashboard('ID')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Indonesia Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_indonesia.view_payroll_dashboard_indonesia').id,
            'res_id': dashboard.id,
            'target': 'current',
            'context': {'default_payroll_country': 'ID'}
        }
    
    # Vietnam Actions
    def action_get_employee_data_vietnam(self):
        """Get employee data for Vietnam"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Get Employee Data - Vietnam',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': 'VN'}
        }
    
    def action_vietnam_edit_spreadsheet(self):
        """Edit Vietnam payroll spreadsheet"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
            if not spreadsheet:
                raise UserError(_(
                    'Vietnam payroll spreadsheet not found. '
                    'Please create it with external ID __custom__.payrollstaging'
                ))
            
            return spreadsheet.with_context(payroll_country='VN').open_spreadsheet()
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_vietnam_import_spreadsheet(self):
        """Import Vietnam spreadsheet data"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
            if not spreadsheet:
                raise UserError(_(
                    'Vietnam payroll spreadsheet not found. '
                    'Please create it with external ID __custom__.payrollstaging'
                ))
            
            # Try importing with proper error handling
            try:
                action = spreadsheet.with_context(payroll_country='VN').import_json_data()
                
                # If the import method returns a dictionary (action), return it
                if isinstance(action, dict):
                    return action
                
                # Otherwise show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Vietnam payroll data imported successfully'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except ValueError as ve:
                if 'work_location' in str(ve):
                    raise UserError(_(
                        'Configuration Error: Missing field in employee model. '
                        'Please update your module to the latest version. '
                        'The import process has been fixed to handle this issue.'
                    ))
                else:
                    raise UserError(_('Import validation error: %s') % str(ve))
                    
        except UserError:
            raise  # Re-raise UserError as-is
        except Exception as e:
            raise UserError(_('Unexpected error importing spreadsheet: %s') % str(e))
    
    # Indonesia Actions
    def action_get_employee_data_indonesia(self):
        """Get employee data for Indonesia"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Get Employee Data - Indonesia',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': 'ID'}
        }
    
    def action_indonesia_edit_spreadsheet(self):
        """Edit Indonesia payroll spreadsheet"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging_indonesia', raise_if_not_found=False)
            if not spreadsheet:
                # Fall back to the general spreadsheet if Indonesia-specific one doesn't exist
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(
                        'Indonesia payroll spreadsheet not found. '
                        'Please create it with external ID __custom__.payrollstaging_indonesia or __custom__.payrollstaging'
                    ))
            
            return spreadsheet.with_context(payroll_country='ID').open_spreadsheet()
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_indonesia_import_spreadsheet(self):
        """Import Indonesia spreadsheet data"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging_indonesia', raise_if_not_found=False)
            if not spreadsheet:
                # Fall back to the general spreadsheet if Indonesia-specific one doesn't exist
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(
                        'Indonesia payroll spreadsheet not found. '
                        'Please create it with external ID __custom__.payrollstaging_indonesia or __custom__.payrollstaging'
                    ))
            
            # Try importing with proper error handling
            try:
                action = spreadsheet.with_context(payroll_country='ID').import_json_data()
                
                # If the import method returns a dictionary (action), return it
                if isinstance(action, dict):
                    return action
                
                # Otherwise show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Indonesia payroll data imported successfully'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except ValueError as ve:
                if 'work_location' in str(ve):
                    raise UserError(_(
                        'Configuration Error: Missing field in employee model. '
                        'Please update your module to the latest version. '
                        'The import process has been fixed to handle this issue.'
                    ))
                else:
                    raise UserError(_('Import validation error: %s') % str(ve))
                    
        except UserError:
            raise  # Re-raise UserError as-is
        except Exception as e:
            raise UserError(_('Unexpected error importing spreadsheet: %s') % str(e))
    
    def action_thr_payment(self):
        """Process THR payment for Indonesia"""
        try:
            # Look for THR payment wizard action
            action = self.env.ref('pb_hr_payroll_indonesia.action_thr_payment_wizard', raise_if_not_found=False)
            if action:
                return {
                    'type': 'ir.actions.act_window',
                    'name': action.name,
                    'res_model': action.res_model,
                    'view_mode': action.view_mode,
                    'target': 'new',
                    'context': {'default_payroll_country': 'ID'}
                }
            else:
                raise UserError(_('THR Payment wizard not found. Please contact your administrator.'))
        except Exception as e:
            raise UserError(_('Error opening THR payment: %s') % str(e))