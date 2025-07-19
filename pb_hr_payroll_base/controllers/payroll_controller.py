# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollController(http.Controller):

    @http.route('/payroll/dashboard', type='http', auth='user', website=True)
    def payroll_dashboard_main(self, **kwargs):
        """Main payroll dashboard with country selection"""
        try:
            # Get user's accessible countries
            user = request.env.user
            accessible_countries = self._get_user_accessible_countries(user)
            
            # Get dashboard data
            dashboard_data = request.env['payroll.dashboard'].get_dashboard_data()
            
            # Filter by accessible countries
            accessible_data = [
                data for data in dashboard_data 
                if data['country'] in accessible_countries
            ]
            
            return request.render('pb_hr_payroll_base.payroll_country_selector_template', {
                'dashboards': accessible_data,
                'access_rights': {country: True for country in accessible_countries},
                'user': user,
            })
            
        except Exception as e:
            _logger.error(f"Error in main dashboard: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'error_message': 'Unable to load payroll dashboard.'
            })

    @http.route('/payroll/dashboard/<string:country>', type='http', auth='user', website=True)
    def payroll_dashboard_country(self, country, **kwargs):
        """Country-specific payroll dashboard"""
        try:
            # Check access
            if not self._has_country_access(request.env.user, country):
                return request.render('web.http_error', {
                    'status_code': 403,
                    'status_message': 'Access Denied',
                    'error_message': f'You do not have access to {country} payroll.'
                })
            
            # Get dashboard for country
            dashboard = request.env['payroll.dashboard'].search([
                ('country', '=', country),
                ('active', '=', True)
            ], limit=1)
            
            if not dashboard:
                # Create default dashboard if not exists
                dashboard = self._create_default_dashboard(country)
            
            # Get real-time metrics
            dashboard._compute_metrics()
            
            # Determine which template to use
            template_map = {
                'VN': 'pb_hr_payroll_base.view_payroll_dashboard_vietnam',
                'ID': 'pb_hr_payroll_base.view_payroll_dashboard_indonesia',
                'IN': 'pb_hr_payroll_base.view_payroll_dashboard_india',
            }
            
            template = template_map.get(country, 'pb_hr_payroll_base.view_payroll_dashboard_generic')
            
            return request.render(template, {
                'dashboard': dashboard,
                'country': country,
                'metrics': dashboard._get_formatted_metrics(),
                'user': request.env.user,
            })
            
        except Exception as e:
            _logger.error(f"Error in country dashboard for {country}: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'error_message': f'Unable to load {country} payroll dashboard.'
            })

    @http.route('/payroll/api/metrics/<string:country>', type='json', auth='user')
    def get_country_metrics(self, country, **kwargs):
        """API endpoint to get real-time metrics for a country"""
        try:
            if not self._has_country_access(request.env.user, country):
                return {'error': 'Access denied'}
            
            dashboard = request.env['payroll.dashboard'].search([
                ('country', '=', country),
                ('active', '=', True)
            ], limit=1)
            
            if not dashboard:
                return {'error': 'Dashboard not found'}
            
            # Force refresh metrics
            dashboard._compute_metrics()
            
            return {
                'success': True,
                'data': {
                    'employee_count': dashboard.employee_count,
                    'active_contracts': dashboard.active_contracts,
                    'pending_payslips': dashboard.pending_payslips,
                    'total_gross_salary': dashboard.total_gross_salary,
                    'currency': dashboard.currency_id.name,
                    'last_updated': dashboard.last_updated.isoformat() if dashboard.last_updated else None,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error getting metrics for {country}: {str(e)}")
            return {'error': str(e)}

    @http.route('/payroll/select-country', type='json', auth='user')
    def select_country(self, country_code, **kwargs):
        """Handle country selection from the main dashboard"""
        try:
            if not self._has_country_access(request.env.user, country_code):
                return {
                    'success': False,
                    'error': 'access_denied',
                    'message': f'You do not have access to {country_code} payroll system. Please contact your administrator.'
                }
            
            # Get or create dashboard
            dashboard = request.env['payroll.dashboard'].search([
                ('country', '=', country_code),
                ('active', '=', True)
            ], limit=1)
            
            if not dashboard:
                dashboard = self._create_default_dashboard(country_code)
            
            # Determine action based on country
            action_map = {
                'VN': {
                    'action': 'dashboard',
                    'action_id': request.env.ref('pb_hr_payroll_base.action_payroll_dashboard_vietnam').id,
                },
                'ID': {
                    'action': 'dashboard', 
                    'action_id': request.env.ref('pb_hr_payroll_base.action_payroll_dashboard_indonesia').id,
                },
                'IN': {
                    'action': 'menu',
                    'menu_id': request.env.ref('pb_hr_payroll_base.menu_payroll_india').id,
                },
            }
            
            action_data = action_map.get(country_code, {
                'action': 'dashboard',
                'action_id': dashboard.id,
            })
            
            return {
                'success': True,
                **action_data
            }
            
        except Exception as e:
            _logger.error(f"Error selecting country {country_code}: {str(e)}")
            return {
                'success': False,
                'error': 'server_error',
                'message': 'An error occurred while accessing the payroll system.'
            }

    @http.route('/payroll/spreadsheet/<string:country>', type='http', auth='user')
    def open_spreadsheet(self, country, **kwargs):
        """Open the payroll spreadsheet for a country"""
        try:
            if not self._has_country_access(request.env.user, country):
                return request.render('web.http_error', {
                    'status_code': 403,
                    'status_message': 'Access Denied',
                    'error_message': f'You do not have access to {country} payroll spreadsheet.'
                })
            
            # Map countries to their spreadsheet URLs/actions
            spreadsheet_map = {
                'VN': '/web#action=spreadsheet_oca.action_spreadsheet&model=hr.payslip&country=VN',
                'ID': '/web#action=spreadsheet_oca.action_spreadsheet&model=hr.payslip&country=ID',
                'IN': '/web#action=spreadsheet_oca.action_spreadsheet&model=hr.payslip&country=IN',
            }
            
            url = spreadsheet_map.get(country, '/web#action=spreadsheet_oca.action_spreadsheet')
            return request.redirect(url)
            
        except Exception as e:
            _logger.error(f"Error opening spreadsheet for {country}: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'error_message': 'Unable to open spreadsheet.'
            })

    @http.route('/payroll/analytics/dashboard', type='http', auth='user', website=True)
    def analytics_dashboard(self, country=None, period=None, **kwargs):
        """Advanced analytics dashboard"""
        try:
            # Get user's accessible countries
            accessible_countries = self._get_user_accessible_countries(request.env.user)
            
            # Filter by country if specified
            domain = [('state', 'in', ['ready', 'approved'])]
            if country and country in accessible_countries:
                domain.append(('country_code', '=', country))
            else:
                domain.append(('country_code', 'in', accessible_countries))
            
            # Get latest analytics
            analytics = request.env['payroll.analytics'].search(domain, limit=20, order='period_start desc')
            
            # Get summary data
            summary_data = self._get_analytics_summary(analytics)
            
            return request.render('pb_hr_payroll_base.payroll_analytics_dashboard_template', {
                'analytics': analytics,
                'summary': summary_data,
                'countries': accessible_countries,
                'selected_country': country,
                'user': request.env.user,
            })
            
        except Exception as e:
            _logger.error(f"Error in analytics dashboard: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'error_message': 'Unable to load analytics dashboard.'
            })

    @http.route('/payroll/api/analytics/generate', type='json', auth='user')
    def generate_analytics(self, country_code, period_start, period_end, **kwargs):
        """API to generate analytics for a period"""
        try:
            if not self._has_country_access(request.env.user, country_code):
                return {'error': 'Access denied'}
            
            # Create analytics record
            analytics = request.env['payroll.analytics'].create({
                'period_name': f"{period_start} to {period_end} - {country_code}",
                'period_start': period_start,
                'period_end': period_end,
                'country_code': country_code,
                'currency_id': self._get_country_currency(country_code),
            })
            
            # Trigger computation
            analytics.action_compute_analytics()
            
            return {
                'success': True,
                'analytics_id': analytics.id,
                'message': 'Analytics generated successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error generating analytics: {str(e)}")
            return {'error': str(e)}

    # Helper Methods
    
    def _get_user_accessible_countries(self, user):
        """Get list of countries user has access to"""
        accessible_countries = []
        
        # Check group memberships
        if user.has_group('pb_hr_payroll_base.group_payroll_vietnam'):
            accessible_countries.append('VN')
        if user.has_group('pb_hr_payroll_base.group_payroll_indonesia'):
            accessible_countries.append('ID')
        if user.has_group('pb_hr_payroll_base.group_payroll_india'):
            accessible_countries.append('IN')
        if user.has_group('pb_hr_payroll_base.group_payroll_singapore'):
            accessible_countries.append('SG')
        if user.has_group('pb_hr_payroll_base.group_payroll_malaysia'):
            accessible_countries.append('MY')
        if user.has_group('pb_hr_payroll_base.group_payroll_thailand'):
            accessible_countries.append('TH')
        
        # Super users have access to all
        if user.has_group('base.group_system'):
            accessible_countries = ['VN', 'ID', 'IN', 'SG', 'MY', 'TH']
        
        return accessible_countries

    def _has_country_access(self, user, country_code):
        """Check if user has access to specific country"""
        return country_code in self._get_user_accessible_countries(user)

    def _create_default_dashboard(self, country_code):
        """Create default dashboard for country"""
        country_names = {
            'VN': 'Vietnam Payroll Dashboard',
            'ID': 'Indonesia Payroll Dashboard', 
            'IN': 'India Payroll Dashboard',
            'SG': 'Singapore Payroll Dashboard',
            'MY': 'Malaysia Payroll Dashboard',
            'TH': 'Thailand Payroll Dashboard',
        }
        
        dashboard = request.env['payroll.dashboard'].create({
            'name': country_names.get(country_code, f'{country_code} Payroll Dashboard'),
            'country': country_code,
            'sequence': 10,
        })
        
        return dashboard

    def _get_country_currency(self, country_code):
        """Get currency for country"""
        currency_map = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR',
            'SG': 'SGD', 'MY': 'MYR', 'TH': 'THB'
        }
        
        currency_code = currency_map.get(country_code, 'USD')
        currency = request.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        return currency.id if currency else request.env.company.currency_id.id

    def _get_analytics_summary(self, analytics_records):
        """Get summary statistics from analytics records"""
        if not analytics_records:
            return {}
        
        countries = list(set(analytics_records.mapped('country_code')))
        latest_period = max(analytics_records.mapped('period_start'))
        
        summary = {
            'total_countries': len(countries),
            'total_periods': len(analytics_records),
            'latest_period': latest_period,
            'countries': countries,
            'total_employees': sum(analytics_records.mapped('total_employees')),
            'total_payroll': sum(analytics_records.mapped('total_payroll')),
        }
        
        return summary


class PayrollAPIController(http.Controller):
    """REST API endpoints for payroll data"""

    @http.route('/api/payroll/countries', type='json', auth='user', methods=['GET'])
    def get_countries(self, **kwargs):
        """Get list of available countries"""
        try:
            user = request.env.user
            accessible_countries = PayrollController()._get_user_accessible_countries(user)
            
            countries_data = []
            for country in accessible_countries:
                dashboard = request.env['payroll.dashboard'].search([
                    ('country', '=', country),
                    ('active', '=', True)
                ], limit=1)
                
                if dashboard:
                    dashboard._compute_metrics()
                    countries_data.append({
                        'code': country,
                        'name': dashboard.name,
                        'employee_count': dashboard.employee_count,
                        'active_contracts': dashboard.active_contracts,
                        'pending_payslips': dashboard.pending_payslips,
                        'total_gross_salary': dashboard.total_gross_salary,
                        'currency': dashboard.currency_id.name,
                    })
            
            return {
                'success': True,
                'data': countries_data
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/api/payroll/employees/<string:country>', type='json', auth='user', methods=['GET'])
    def get_employees(self, country, **kwargs):
        """Get employees for a country"""
        try:
            controller = PayrollController()
            if not controller._has_country_access(request.env.user, country):
                return {'success': False, 'error': 'Access denied'}
            
            # Get employees for country
            domain = [
                '|',
                ('contract_ids.payroll_country_code', '=', country),
                ('country_id.code', '=', country)
            ]
            
            employees = request.env['hr.employee'].search(domain)
            
            employee_data = []
            for emp in employees:
                employee_data.append({
                    'id': emp.id,
                    'name': emp.name,
                    'employee_number': emp.employee_number or '',
                    'department': emp.department_id.name or '',
                    'job_title': emp.job_id.name or '',
                    'contract_state': emp.contract_id.state if emp.contract_id else 'no_contract',
                    'wage': emp.contract_id.wage if emp.contract_id else 0.0,
                })
            
            return {
                'success': True,
                'data': employee_data,
                'count': len(employee_data)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/api/payroll/payslips/<string:country>', type='json', auth='user', methods=['GET'])
    def get_payslips(self, country, state=None, date_from=None, date_to=None, **kwargs):
        """Get payslips for a country with filters"""
        try:
            controller = PayrollController()
            if not controller._has_country_access(request.env.user, country):
                return {'success': False, 'error': 'Access denied'}
            
            # Build domain
            domain = [('contract_id.payroll_country_code', '=', country)]
            
            if state:
                domain.append(('state', '=', state))
            if date_from:
                domain.append(('date_from', '>=', date_from))
            if date_to:
                domain.append(('date_to', '<=', date_to))
            
            payslips = request.env['hr.payslip'].search(domain, limit=100)
            
            payslip_data = []
            for payslip in payslips:
                gross_total = sum(payslip.line_ids.filtered(
                    lambda l: l.category_id.code == 'GROSS'
                ).mapped('total'))
                
                net_total = sum(payslip.line_ids.filtered(
                    lambda l: l.category_id.code == 'NET'
                ).mapped('total'))
                
                payslip_data.append({
                    'id': payslip.id,
                    'number': payslip.number,
                    'employee_name': payslip.employee_id.name,
                    'period': f"{payslip.date_from} - {payslip.date_to}",
                    'state': payslip.state,
                    'gross_total': gross_total,
                    'net_total': net_total,
                    'currency': payslip.contract_id.currency_id.name,
                })
            
            return {
                'success': True,
                'data': payslip_data,
                'count': len(payslip_data)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/api/payroll/import/employees', type='json', auth='user', methods=['POST'])
    def import_employees(self, country, employee_data, **kwargs):
        """Import employee data for a country"""
        try:
            controller = PayrollController()
            if not controller._has_country_access(request.env.user, country):
                return {'success': False, 'error': 'Access denied'}
            
            imported_count = 0
            errors = []
            
            for emp_data in employee_data:
                try:
                    # Create or update employee
                    existing = request.env['hr.employee'].search([
                        ('employee_number', '=', emp_data.get('employee_number'))
                    ], limit=1)
                    
                    values = {
                        'name': emp_data.get('name'),
                        'employee_number': emp_data.get('employee_number'),
                        'work_email': emp_data.get('email'),
                        'work_phone': emp_data.get('phone'),
                    }
                    
                    # Set country
                    country_rec = request.env['res.country'].search([('code', '=', country)], limit=1)
                    if country_rec:
                        values['country_id'] = country_rec.id
                    
                    if existing:
                        existing.write(values)
                    else:
                        request.env['hr.employee'].create(values)
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Error importing {emp_data.get('name', 'Unknown')}: {str(e)}")
            
            return {
                'success': True,
                'imported_count': imported_count,
                'errors': errors
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/api/payroll/export/bank-file/<string:country>', type='http', auth='user', methods=['GET'])
    def export_bank_file(self, country, period_start=None, period_end=None, **kwargs):
        """Export bank disbursement file"""
        try:
            controller = PayrollController()
            if not controller._has_country_access(request.env.user, country):
                return request.make_response(
                    json.dumps({'error': 'Access denied'}),
                    headers=[('Content-Type', 'application/json')]
                )
            
            # Get payslips for period
            domain = [
                ('contract_id.payroll_country_code', '=', country),
                ('state', '=', 'done')
            ]
            
            if period_start:
                domain.append(('date_from', '>=', period_start))
            if period_end:
                domain.append(('date_to', '<=', period_end))
            
            payslips = request.env['hr.payslip'].search(domain)
            
            # Generate bank file content
            bank_data = []
            for payslip in payslips:
                net_amount = sum(payslip.line_ids.filtered(
                    lambda l: l.category_id.code == 'NET'
                ).mapped('total'))
                
                if net_amount > 0:
                    bank_data.append({
                        'employee_number': payslip.employee_id.employee_number or '',
                        'employee_name': payslip.employee_id.name,
                        'account_number': payslip.employee_id.bank_account_id.acc_number if payslip.employee_id.bank_account_id else '',
                        'amount': net_amount,
                        'currency': payslip.contract_id.currency_id.name,
                        'reference': payslip.number,
                    })
            
            # Create CSV content
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['employee_number', 'employee_name', 'account_number', 'amount', 'currency', 'reference'])
            writer.writeheader()
            writer.writerows(bank_data)
            
            csv_content = output.getvalue()
            
            # Return as download
            filename = f'bank_disbursement_{country}_{period_start or "all"}.csv'
            
            return request.make_response(
                csv_content,
                headers=[
                    ('Content-Type', 'text/csv'),
                    ('Content-Disposition', f'attachment; filename="{filename}"')
                ]
            )
            
        except Exception as e:
            _logger.error(f"Error exporting bank file: {str(e)}")
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')]
            )

    @http.route('/payroll/country-selector', type='http', auth='user', website=True)
    def country_selector(self, **kwargs):
        """Render the country selection landing page"""
        try:
            # Get user's groups to show which countries they have access to
            user = request.env.user
            
            # Check access rights for each country
            access_rights = {
                'VN': user.has_group('pb_hr_payroll_base.group_payroll_vietnam') or user.has_group('pb_hr_payroll_base.group_payroll_base_manager'),
                'ID': user.has_group('pb_hr_payroll_base.group_payroll_indonesia') or user.has_group('pb_hr_payroll_base.group_payroll_base_manager'),
                'IN': user.has_group('pb_hr_payroll_base.group_payroll_india') or user.has_group('pb_hr_payroll_base.group_payroll_base_manager'),
                'SG': user.has_group('pb_hr_payroll_base.group_payroll_singapore') or user.has_group('pb_hr_payroll_base.group_payroll_base_manager'),
                'MY': user.has_group('pb_hr_payroll_base.group_payroll_malaysia') or user.has_group('pb_hr_payroll_base.group_payroll_base_manager'),
            }
            
            # Get dashboard data for accessible countries
            accessible_countries = [country for country, has_access in access_rights.items() if has_access]
            
            dashboard_data = []
            for country in accessible_countries:
                dashboard = request.env['payroll.dashboard'].search([
                    ('country', '=', country),
                    ('active', '=', True)
                ], limit=1)
                
                if not dashboard:
                    # Create dashboard if it doesn't exist
                    country_names = {
                        'VN': 'Vietnam Payroll Dashboard',
                        'ID': 'Indonesia Payroll Dashboard',
                        'IN': 'India Payroll Dashboard',
                        'SG': 'Singapore Payroll Dashboard',
                        'MY': 'Malaysia Payroll Dashboard',
                    }
                    
                    dashboard = request.env['payroll.dashboard'].create({
                        'name': country_names.get(country, f'{country} Payroll Dashboard'),
                        'country': country,
                        'sequence': 10,
                        'active': True,
                    })
                
                dashboard_data.append({
                    'country': country,
                    'name': dashboard.name,
                    'id': dashboard.id,
                })
            
            return request.render('pb_hr_payroll_base.payroll_country_selector_template', {
                'access_rights': access_rights,
                'dashboards': dashboard_data,
                'user': user,
            })
            
        except Exception as e:
            _logger.error(f"Error in country selector: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'error_message': 'Unable to load country selector.'
            })