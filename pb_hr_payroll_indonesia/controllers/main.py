# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class PayrollCountrySelector(http.Controller):
    
    @http.route('/payroll/country-selector', type='http', auth='user', website=True)
    def country_selector(self, **kw):
        """Render the country selection landing page"""
        # Get user's groups to show which countries they have access to
        user = request.env.user
        access_rights = {
            'VN': user.has_group('pb_hr_payroll_indonesia.group_vietnam_payroll_user'),
            'ID': user.has_group('pb_hr_payroll_indonesia.group_indonesia_payroll_user'),
            'IN': user.has_group('pb_hr_payroll_indonesia.group_india_payroll_user'),
        }
        
        return request.render('pb_hr_payroll_indonesia.payroll_country_selector_template', {
            'access_rights': access_rights
        })
    
    @http.route('/payroll/select-country', type='json', auth='user')
    def select_country(self, country_code, **kw):
        """Handle country selection and check user permissions"""
        user = request.env.user
        
        # Check if user has access to selected country
        group_mapping = {
            'VN': 'pb_hr_payroll_indonesia.group_vietnam_payroll_user',
            'ID': 'pb_hr_payroll_indonesia.group_indonesia_payroll_user',
            'IN': 'pb_hr_payroll_indonesia.group_india_payroll_user',
        }
        
        if not user.has_group(group_mapping.get(country_code)):
            return {
                'success': False,
                'error': 'access_denied',
                'message': f'You do not have access to {self._get_country_name(country_code)} payroll. Please contact your administrator to request access.'
            }
        
        # Store selected country in session only
        request.session['payroll_country'] = country_code
        
        # Return the appropriate menu action based on country
        menu_mapping = {
            'VN': 'pb_hr_payroll_indonesia.menu_vietnam_payroll_root',
            'ID': 'pb_hr_payroll_indonesia.menu_indonesia_payroll_root',
            'IN': 'pb_hr_payroll_indonesia.menu_india_payroll_root',
        }
        
        # Dashboard mapping
        dashboard_mapping = {
            'VN': 'pb_hr_payroll_indonesia.action_vietnam_dashboard',
            'ID': 'pb_hr_payroll_indonesia.action_indonesia_dashboard',
        }
        
        menu_id = request.env.ref(menu_mapping.get(country_code))
        
        # Try to get dashboard action
        dashboard_action = dashboard_mapping.get(country_code)
        if dashboard_action:
            try:
                action = request.env.ref(dashboard_action)
                return {
                    'success': True,
                    'action_id': action.id,
                    'action': 'dashboard'
                }
            except:
                pass
        
        return {
            'success': True,
            'menu_id': menu_id.id,
            'action': 'redirect'
        }
    
    def _get_country_name(self, country_code):
        """Get country name from code"""
        country_names = {
            'VN': 'Vietnam',
            'ID': 'Indonesia',
            'IN': 'India'
        }
        return country_names.get(country_code, 'Unknown')