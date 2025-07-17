# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class PayrollCountrySelector(models.TransientModel):
    _name = 'payroll.country.selector'
    _description = 'Payroll Country Selector'
    
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Select Country', required=True, default='VN')
    
    def action_select_country(self):
        """Select country and open respective dashboard"""
        dashboard = self.env['payroll.dashboard'].get_or_create_dashboard(self.country)
        
        # Get country-specific dashboard view
        view_map = {
            'VN': 'pb_hr_payroll_vietnam.view_payroll_dashboard_vietnam',
            'ID': 'pb_hr_payroll_indonesia.view_payroll_dashboard_indonesia',
            'IN': 'pb_hr_payroll_india.view_payroll_dashboard_india',
            'SG': 'pb_hr_payroll_singapore.view_payroll_dashboard_singapore',
            'MY': 'pb_hr_payroll_malaysia.view_payroll_dashboard_malaysia',
        }
        
        view_id = view_map.get(self.country)
        if view_id:
            try:
                view_ref = self.env.ref(view_id)
                return {
                    'type': 'ir.actions.act_window',
                    'name': f'{self.country} Payroll Dashboard',
                    'res_model': 'payroll.dashboard',
                    'view_mode': 'form',
                    'view_id': view_ref.id,
                    'target': 'current',
                    'domain': [('country', '=', self.country)],
                    'context': {'create': False, 'edit': False, 'delete': False, 'default_country': self.country, 'force_view': True}
                }
            except:
                _logger.warning(f"Country-specific view {view_id} not found, using base view")
        
        # Fallback to base view
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.country} Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'target': 'current',
            'domain': [('country', '=', self.country)],
            'context': {'create': False, 'edit': False, 'delete': False, 'default_country': self.country}
        }
    
    @api.model
    def get_available_countries(self):
        """Get list of available country modules"""
        available_countries = []
        country_modules = {
            'VN': 'pb_hr_payroll_vietnam',
            'ID': 'pb_hr_payroll_indonesia', 
            'IN': 'pb_hr_payroll_india',
            'SG': 'pb_hr_payroll_singapore',
            'MY': 'pb_hr_payroll_malaysia',
        }
        
        for country_code, module_name in country_modules.items():
            module = self.env['ir.module.module'].search([
                ('name', '=', module_name),
                ('state', '=', 'installed')
            ], limit=1)
            if module:
                available_countries.append(country_code)
        
        return available_countries