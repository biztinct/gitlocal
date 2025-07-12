# -*- coding: utf-8 -*-
# Enhanced Payroll Dashboard Base Models - Maintains backward compatibility while adding advanced features

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pudb import set_trace

_logger = logging.getLogger(__name__)


class PayrollDashboard(models.Model):
    """Enhanced Multi-Country Payroll Dashboard - Full Version"""
    _name = 'payroll.dashboard'
    _description = 'Multi-Country Payroll Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # ADD THIS LINE
    _order = 'sequence, name'
    _rec_name = 'name'

    # === BASIC FIELDS (EXISTING - BACKWARD COMPATIBLE) ===
    name = fields.Char('Dashboard Name', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),  # NEW: Added Thailand
        ('PH', 'Philippines'),  # NEW: Added Philippines
    ], string='Country', required=True)
    
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    # === EXISTING COMPUTED FIELDS (BACKWARD COMPATIBLE) ===
    employee_count = fields.Integer('Employee Count', compute='_compute_statistics', store=False)
    active_contracts = fields.Integer('Active Contracts', compute='_compute_statistics', store=False)
    pending_payslips = fields.Integer('Pending Payslips', compute='_compute_statistics', store=False)
    total_gross_salary = fields.Float('Total Gross Salary', compute='_compute_statistics', store=False)
    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_currency', store=True)
    # Change the field definition
    structure_id = fields.Many2one('hr.payroll.structure', 'Payroll Structure', compute='_compute_structure_id', store=False)


    # === NEW ENHANCED FIELDS ===
    # Country Configuration
    country_id = fields.Many2one('res.country', string='Country Reference', compute='_compute_country_reference', store=True)
    
    # Enhanced Dashboard Features
    auto_refresh = fields.Boolean('Auto Refresh', default=True)
    refresh_interval = fields.Integer('Refresh Interval (minutes)', default=60)
    last_updated = fields.Datetime('Last Updated', default=fields.Datetime.now)
    
    # Analytics Cache (for performance)
    cached_metrics = fields.Text('Cached Metrics JSON')
    metrics_last_computed = fields.Datetime('Metrics Last Computed')
    
    # Access Control
    user_groups = fields.Many2many('res.groups', string='Allowed Groups')
    
    # Dashboard Configuration
    show_charts = fields.Boolean('Show Charts', default=True)
    show_analytics = fields.Boolean('Show Analytics', default=True)
    dashboard_theme = fields.Selection([
        ('default', 'Default'),
        ('dark', 'Dark Mode'),
        ('modern', 'Modern'),
        ('minimal', 'Minimal'),
    ], default='default', string='Dashboard Theme')

    # ===========================================
    # ADD THESE COMPUTED FIELDS IF MISSING
    # ===========================================

    # Add these fields if they don't exist in your model:
    # Enhanced Analytics Fields
    # Enhanced Analytics Fields
    total_employees = fields.Integer(
        string='Total Employees',
        compute='_compute_enhanced_statistics',
        store=True,  # Make searchable
        help="Total number of employees in payroll system"
    )
    
    total_payroll = fields.Monetary(
        string='Total Payroll',
        compute='_compute_enhanced_statistics',
        currency_field='currency_id',
        store=True,  # Make searchable
        help="Total payroll amount for current period"
    )
    
    average_salary = fields.Monetary(
        string='Average Salary',
        compute='_compute_enhanced_statistics',
        currency_field='currency_id',
        store=True,  # Make searchable
        help="Average salary across all employees"
    )
    
    last_payroll_date = fields.Date(
        string='Last Payroll Date',
        compute='_compute_enhanced_statistics',
        store=True,  # Make searchable
        help="Date of last processed payroll"
    )
    
    # Enhanced Integration Status
    zoho_connection_status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
    ], default='disconnected', string='Zoho Status', tracking=True)
    
    last_sync_date = fields.Datetime(string='Last Sync Date')
    auto_sync_enabled = fields.Boolean(string='Auto Sync Enabled', default=False)
    analytics_enabled = fields.Boolean(string='Analytics Enabled', default=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'Maintenance'),
        ('inactive', 'Inactive'),
    ], default='active', string='Status', tracking=True)  # ADD tracking=True for mail.thread

    # Enhanced Integration Status
    zoho_connection_status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
    ], default='disconnected', string='Zoho Status', tracking=True)
    
    last_sync_date = fields.Datetime(string='Last Sync Date')
    auto_sync_enabled = fields.Boolean(string='Auto Sync Enabled', default=False)
    analytics_enabled = fields.Boolean(string='Analytics Enabled', default=True)

    def debug_currency_issue(self):
        """Debug currency computation issues"""
        for record in self:
            _logger.info(f"=== DEBUG {record.name} ===")
            _logger.info(f"Country: {record.country}")
            _logger.info(f"Current currency_id: {record.currency_id}")
            _logger.info(f"Current currency name: {record.currency_id.name if record.currency_id else 'None'}")
            _logger.info(f"Current currency symbol: {record.currency_id.symbol if record.currency_id else 'None'}")
            
            # Test currency search
            expected_code = {'VN': 'VND', 'ID': 'IDR', 'IN': 'INR'}.get(record.country, 'USD')
            found_currency = self.env['res.currency'].search([('name', '=', expected_code)], limit=1)
            _logger.info(f"Expected currency: {expected_code}")
            _logger.info(f"Found currency: {found_currency.name if found_currency else 'NOT FOUND'}")
            
            # Check all available currencies
            all_currencies = self.env['res.currency'].search([])
            currency_names = [c.name for c in all_currencies]
            _logger.info(f"Available currencies: {currency_names}")
            
            # Return message for user
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Debug Complete',
                    'message': f'Check logs for {record.name} currency debug info',
                    'type': 'info',
                }
            }



    # === EXISTING METHODS (BACKWARD COMPATIBLE) ===
    

    @api.depends('country')
    def _compute_currency(self):
        """FIXED: Force proper currency assignment"""
        for record in self:
            if not record.country:
                record.currency_id = self.env.company.currency_id.id
                continue
                
            # Currency mapping
            currency_map = {
                'VN': 'VND',  # Vietnamese Dong
                'ID': 'IDR',  # Indonesian Rupiah  
                'IN': 'INR',  # Indian Rupee
                'SG': 'SGD',  # Singapore Dollar
                'MY': 'MYR',  # Malaysian Ringgit
                'TH': 'THB',  # Thai Baht
                'PH': 'PHP'   # Philippine Peso
            }
            
            expected_currency_code = currency_map.get(record.country, 'USD')
            
            # Search for the currency
            currency = self.env['res.currency'].search([('name', '=', expected_currency_code)], limit=1)
            
            if currency:
                # FORCE the assignment - don't just set it, write it
                record.write({'currency_id': currency.id})
                _logger.info(f"✅ FORCED currency {expected_currency_code} for {record.country} dashboard")
            else:
                record.currency_id = self.env.company.currency_id.id
                _logger.warning(f"❌ Currency {expected_currency_code} not found for {record.country}")

    @api.depends('country')
    def _compute_country_reference(self):
        """Compute country reference field"""
        country_map = {
            'VN': 'VN', 'ID': 'ID', 'IN': 'IN',
            'SG': 'SG', 'MY': 'MY', 'TH': 'TH', 'PH': 'PH'
        }
        
        for record in self:
            if record.country:
                country_rec = self.env['res.country'].search([('code', '=', country_map.get(record.country))], limit=1)
                record.country_id = country_rec.id if country_rec else False
            else:
                record.country_id = False

    # Add separate compute method
    @api.depends('country')
    def _compute_structure_id(self):
        """Compute payroll structure for country"""
        for record in self:
            if record.country:
                structure = self.env['hr.payroll.structure'].search([
                    ('payroll_country_code', '=', record.country),
                    ('active', '=', True)
                ], limit=1)
                record.structure_id = structure.id if structure else False
            else:
                record.structure_id = False



    # Replace or enhance your existing _compute_statistics method:
    @api.depends('country', 'active')
    def _compute_statistics(self):
        """Enhanced statistics computation"""
        for record in self:
            try:
                # Initialize all fields to prevent compute errors
                record.employee_count = 0
                record.active_contracts = 0
                record.pending_payslips = 0
                record.total_gross_salary = 0.0
                
                if not record.country:
                    continue
                    
                # Employee count
                employees = self.env['hr.employee'].search([
                    ('active', '=', True)
                    # Add country filter if you have one
                ])
                record.employee_count = len(employees)
                
                # Active contracts
                contracts = self.env['hr.contract'].search([
                    ('state', '=', 'open')
                    # Add country filter if you have one
                ])
                record.active_contracts = len(contracts)
                
                # Pending payslips
                payslips = self.env['hr.payslip'].search([
                    ('state', 'in', ['draft', 'verify'])
                    # Add country filter if you have one
                ])
                record.pending_payslips = len(payslips)
                
                # Total gross salary
                done_payslips = self.env['hr.payslip'].search([
                    ('state', '=', 'done'),
                    ('date_from', '>=', fields.Date.today().replace(day=1)),
                    ('date_to', '<=', fields.Date.today())
                ])
                record.total_gross_salary = sum(payslip.total_wage or 0 for payslip in done_payslips)
                
            except Exception as e:
                _logger.warning(f"Error computing statistics for {record.name}: {str(e)}")
                # Set safe default values
                record.employee_count = 0
                record.active_contracts = 0
                record.pending_payslips = 0
                record.total_gross_salary = 0.0


    @api.depends('country', 'active')
    def _compute_enhanced_statistics(self):
        """Enhanced statistics computation for new fields"""
        for record in self:
            try:
                # Use existing logic and extend it
                record._compute_statistics()  # Call your existing method
                
                # Enhanced calculations for new fields
                record.total_employees = record.employee_count
                
                # Calculate total payroll from recent payslips
                today = fields.Date.today()
                start_of_month = today.replace(day=1)
                payslips = self.env['hr.payslip'].search([
                    ('state', '=', 'done'),
                    ('date_from', '>=', start_of_month),
                    ('date_to', '<=', today)
                ])
                record.total_payroll = sum(payslip.net_wage for payslip in payslips)
                
                # Calculate average salary
                if record.total_employees > 0:
                    record.average_salary = record.total_payroll / record.total_employees
                else:
                    record.average_salary = 0.0
                    
                # Get last payroll date
                latest_payslip = self.env['hr.payslip'].search([
                    ('state', '=', 'done')
                ], order='date_to desc', limit=1)
                record.last_payroll_date = latest_payslip.date_to if latest_payslip else False
                
            except Exception as e:
                _logger.warning(f"Error computing enhanced statistics for {record.name}: {str(e)}")
                record.total_employees = 0
                record.total_payroll = 0.0
                record.average_salary = 0.0
                record.last_payroll_date = False


    def _use_cached_metrics(self):
        """Check if we can use cached metrics"""
        if not self.cached_metrics or not self.metrics_last_computed:
            return False
        
        # Use cache if metrics were computed less than refresh_interval minutes ago
        cache_expiry = self.metrics_last_computed + timedelta(minutes=self.refresh_interval)
        return datetime.now() <= cache_expiry

    def _load_cached_metrics(self):
        """Load metrics from cache"""
        try:
            if self.cached_metrics:
                metrics = json.loads(self.cached_metrics)
                self.employee_count = metrics.get('employee_count', 0)
                self.active_contracts = metrics.get('active_contracts', 0)
                self.pending_payslips = metrics.get('pending_payslips', 0)
                self.total_gross_salary = metrics.get('total_gross_salary', 0.0)
        except Exception as e:
            _logger.warning(f"Error loading cached metrics: {str(e)}")
            self._set_zero_metrics()

    def _cache_metrics(self):
        """Cache the current metrics"""
        try:
            metrics_data = {
                'employee_count': self.employee_count,
                'active_contracts': self.active_contracts,
                'pending_payslips': self.pending_payslips,
                'total_gross_salary': self.total_gross_salary,
                'last_computed': fields.Datetime.now().isoformat(),
            }
            self.cached_metrics = json.dumps(metrics_data)
            self.metrics_last_computed = fields.Datetime.now()
        except Exception as e:
            _logger.warning(f"Error caching metrics: {str(e)}")

    def _set_zero_metrics(self):
        """Set all metrics to zero"""
        self.employee_count = 0
        self.active_contracts = 0
        self.pending_payslips = 0
        self.total_gross_salary = 0.0
        self.structure_id = False

    # === EXISTING ACTION METHODS (BACKWARD COMPATIBLE) ===

    def action_view_country_dashboard(self):
        """Open country-specific dashboard - ENHANCED"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} Dashboard',
            'res_model': 'payroll.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_country': self.country,
                'dashboard_mode': 'enhanced'
            }
        }

    def action_get_employee_data(self):
        """Get employee data - ENHANCED with multiple import options"""
        return {
            'name': f'Import {self.country} Employee Data',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_country_code': self.country,
                'default_dashboard_id': self.id,
            }
        }

    def action_import_spreadsheet(self):
        """Import spreadsheet - ENHANCED version"""
        try:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Import {self.country} Payroll Data',
                'res_model': 'payroll.import.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_country_code': self.country,
                    'default_target_country': self.country,
                    'default_import_mode': 'create_update'
                }
            }
        except Exception as e:
            raise UserError(_('Error importing spreadsheet: %s') % str(e))

    def action_view_employees_by_country(self):
        """View employees for this country - ENHANCED"""
        if not self.structure_id:
            # Try to find or create structure
            structure = self.env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', self.country),
                ('active', '=', True)
            ], limit=1)
            
            if not structure:
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
        
        if not employee_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Employees Found'),
                    'message': _('Please create payroll structures and contracts first.'),
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
        """Create or edit salary structure for this country - ENHANCED"""
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
            'context': {
                'default_country_code': self.country,
                'group_by': ['date_from:month']
            }
        }

    # === NEW ENHANCED METHODS ===

    def action_refresh_metrics(self):
        """Manual refresh of dashboard metrics"""
        self.ensure_one()
        self.cached_metrics = False  # Clear cache to force recomputation
        self._compute_statistics()
        self.last_updated = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dashboard Refreshed'),
                'message': _('Metrics have been updated successfully.'),
                'type': 'success',
            }
        }

    def action_open_analytics(self):
        """Open analytics for this country"""
        return {
            'name': f'{self.country} Payroll Analytics',
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.analytics',
            'view_mode': 'tree,form,graph,pivot',
            'domain': [('country_code', '=', self.country)],
            'context': {
                'default_country_code': self.country,
                'search_default_current_year': 1,
            }
        }

    def action_generate_analytics(self):
        """Generate analytics for this country"""
        return {
            'name': f'Generate {self.country} Analytics',
            'type': 'ir.actions.act_window',
            'res_model': 'analytics.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_country_code': self.country,
                'default_dashboard_id': self.id,
            }
        }

    def action_edit_spreadsheet(self):
        """Open spreadsheet editor for this country"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/payroll/spreadsheet/{self.country}',
            'target': 'new',
        }

    def action_process_payroll(self):
        """Process payroll for this country"""
        return {
            'name': f'Process {self.country} Payroll',
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_country_code': self.country,
                'default_dashboard_id': self.id,
            }
        }

    # === UTILITY METHODS FOR COUNTRY MODULES ===

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

    def get_country_currency(self):
        """Utility: Get currency for this country"""
        return self.currency_id

    def get_formatted_metrics(self):
        """Get formatted metrics for display"""
        return {
            'employee_count': self.employee_count,
            'active_contracts': self.active_contracts,
            'pending_payslips': self.pending_payslips,
            'total_gross_salary': self.total_gross_salary,
            'currency': self.currency_id.name if self.currency_id else 'USD',
            'last_updated': self.last_updated,
            'country_flag': self._get_country_flag(),
        }

    def _get_country_flag(self):
        """Get emoji flag for country"""
        flags = {
            'VN': '🇻🇳', 'ID': '🇮🇩', 'IN': '🇮🇳',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'PH': '🇵🇭'
        }
        return flags.get(self.country, '🏴')

    # === API METHODS FOR FRONTEND ===

    @api.model
    def get_dashboard_data(self, country_code=None):
        """API method to get dashboard data for frontend"""
        domain = [('active', '=', True)]
        if country_code:
            domain.append(('country', '=', country_code))
        
        dashboards = self.search(domain)
        
        result = []
        for dashboard in dashboards:
            # Force compute metrics
            dashboard._compute_statistics()
            
            result.append({
                'id': dashboard.id,
                'name': dashboard.name,
                'country': dashboard.country,
                'country_name': dict(dashboard._fields['country'].selection).get(dashboard.country),
                'employee_count': dashboard.employee_count,
                'active_contracts': dashboard.active_contracts,
                'pending_payslips': dashboard.pending_payslips,
                'total_gross_salary': dashboard.total_gross_salary,
                'currency': dashboard.currency_id.name if dashboard.currency_id else 'USD',
                'last_updated': dashboard.last_updated,
            })
        
        return result

    @api.model
    def create_default_dashboards(self):
        """Create default dashboards for supported countries"""
        countries = [
            ('VN', 'Vietnam Payroll Dashboard'),
            ('ID', 'Indonesia Payroll Dashboard'),
            ('IN', 'India Payroll Dashboard'),
            ('SG', 'Singapore Payroll Dashboard'),
            ('MY', 'Malaysia Payroll Dashboard'),
            ('TH', 'Thailand Payroll Dashboard'),
            ('PH', 'Philippines Payroll Dashboard'),
        ]
        
        for country_code, name in countries:
            existing = self.search([('country', '=', country_code)], limit=1)
            if not existing:
                self.create({
                    'name': name,
                    'country': country_code,
                    'sequence': 10,
                })
                _logger.info(f"Created dashboard for {country_code}")

    # === CONSTRAINTS AND VALIDATIONS ===

    @api.constrains('country')
    def _check_unique_country(self):
        """Ensure only one dashboard per country"""
        for record in self:
            if record.country:
                existing = self.search([
                    ('country', '=', record.country),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        _('A dashboard for %s already exists.') % 
                        dict(record._fields['country'].selection).get(record.country)
                    )

    @api.constrains('refresh_interval')
    def _check_refresh_interval(self):
        """Validate refresh interval"""
        for record in self:
            if record.refresh_interval < 1:
                raise ValidationError(_('Refresh interval must be at least 1 minute.'))

    def action_open_country_dashboard(self):
        """Open country dashboard - Alias for backward compatibility"""
        return self.action_view_country_dashboard()

    def action_export_bank_file(self):
        """Export bank file for payroll"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Export {self.country} Bank File',
            'res_model': 'payroll.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_country_code': self.country,
                'default_dashboard_id': self.id,
            }
        }

    def action_open_analytics_dashboard(self):
        """Open analytics dashboard"""
        return self.action_open_analytics()
    
    # 5. ADD UTILITY METHODS FOR ENHANCED FEATURES
    
    @api.model
    def get_user_access_rights(self, user_id=None):
        """Get user access rights for countries"""
        if not user_id:
            user_id = self.env.user.id
            
        user = self.env['res.users'].browse(user_id)
        
        # Enhanced access rights checking
        access_rights = {
            'VN': True,  # Vietnam always available
            'ID': True,  # Indonesia always available
            'IN': True,  # India always available
            'SG': False, # Singapore - request access
            'MY': False, # Malaysia - request access
        }
        
        return access_rights
    
    @api.model
    def get_dashboard_summary(self):
        """Get enhanced dashboard summary for all countries"""
        summary = {}
        dashboards = self.search([('active', '=', True)])
        
        for dashboard in dashboards:
            summary[dashboard.country] = {
                'name': dashboard.name,
                'total_employees': dashboard.total_employees,
                'total_payroll': dashboard.total_payroll,
                'average_salary': dashboard.average_salary,
                'currency': dashboard.currency_id.name if dashboard.currency_id else 'USD',
                'last_payroll_date': dashboard.last_payroll_date,
                'state': dashboard.state,
                'zoho_status': dashboard.zoho_connection_status,
            }
            
        return summary
    
    @api.model
    def send_access_request(self, user_id, country_code):
        """Send access request to administrators"""
        user = self.env['res.users'].browse(user_id)
        country_name = dict(self._fields['country'].selection)[country_code]
        
        # Create activity for administrators
        admin_users = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('base.group_system').id)
        ])
        
        for admin in admin_users:
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': f'Access Request: {country_name} Payroll',
                'note': f'User {user.name} ({user.login}) has requested access to {country_name} payroll system.',
                'user_id': admin.id,
                'res_model_id': self.env.ref('base.model_res_users').id,
                'res_id': user_id,
            })
        
        return {'success': True, 'message': f'Access request sent for {country_name}'}

    # 6. OVERRIDE WRITE METHOD FOR ENHANCED TRACKING
    def write(self, vals):
        """Override write to add enhanced tracking"""
        if 'state' in vals:
            for record in self:
                old_state = record.state
                new_state = vals['state']
                if old_state != new_state:
                    record.message_post(
                        body=f'Dashboard state changed from {old_state} to {new_state}',
                        message_type='notification'
                    )
        return super().write(vals)
    
    # ===========================================
    # ADD THESE METHODS TO YOUR EXISTING CLASS
    # ===========================================

    # 4. ADD ENHANCED ACTION METHODS
    
    def action_refresh_analytics(self):
        """Refresh analytics data with enhanced features"""
        self.ensure_one()
        _logger.info(f"Refreshing analytics for {self.name} ({self.country})")
        
        # Refresh all computed fields
        self._compute_statistics()
        self._compute_enhanced_statistics()
        
        # Post message to chatter
        self.message_post(
            body=f"Analytics refreshed for {self.name}",
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_export_dashboard(self):
        """Export dashboard data with enhanced options"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Export {self.name} Dashboard',
            'res_model': 'ir.actions.report',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_name': f'{self.name} Dashboard Export',
                'default_model': self._name,
                'default_report_type': 'qweb-pdf',
            }
        }
    
    def action_import_employee_data(self):
        """Enhanced employee data import"""
        self.ensure_one()
        
        # Check if enhanced import wizard exists, fallback to existing method
        try:
            return {
                'name': f'Import {self.country} Employee Data',
                'type': 'ir.actions.act_window',
                'res_model': 'employee.import.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_country_code': self.country,
                    'default_dashboard_id': self.id,
                }
            }
        except:
            # Fallback to existing method
            return self.action_get_employee_data()
    
    def action_process_payroll(self):
        """Enhanced payroll processing"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Process {self.country} Payroll',
            'res_model': 'hr.payslip.run',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_name': f'{self.name} - {fields.Date.today()}',
                'default_state': 'draft',
            }
        }
    
    def action_open_payroll_spreadsheet(self):
        """Enhanced payroll spreadsheet access"""
        self.ensure_one()
        
        try:
            # Try existing spreadsheet method first
            return self.action_import_spreadsheet()
        except:
            # Fallback to generic spreadsheet
            return {
                'type': 'ir.actions.act_window',
                'name': f'{self.country} Payroll Spreadsheet',
                'res_model': 'spreadsheet.spreadsheet',
                'view_mode': 'form',
                'target': 'current',
            }
    
    def action_view_analytics(self):
        """Enhanced analytics dashboard"""
        self.ensure_one()
        
        # Try payroll analytics module if available
        try:
            action = self.env.ref('payroll_analytics_approval.action_payroll_analytics_dashboard')
            return action.read()[0]
        except:
            # Fallback to payslip analytics
            return {
                'type': 'ir.actions.act_window',
                'name': f'{self.country} Analytics',
                'res_model': 'hr.payslip',
                'view_mode': 'graph,tree',
                'domain': [],
                'context': {'search_default_group_by_date': 1}
            }
    
    def action_export_bank_file(self):
        """Enhanced bank file export"""
        self.ensure_one()
        
        country_messages = {
            'VN': 'Please use Vietnam-specific bank export in pb_hr_payroll_vietnam module',
            'ID': 'Please use Indonesia-specific bank export in pb_hr_payroll_indonesia module',
            'IN': 'Please use India-specific bank export in pb_hr_payroll_india module',
        }
        
        message = country_messages.get(
            self.country,
            'Bank export not available for this country yet'
        )
        
        raise UserError(message)
    
    def action_approval_dashboard(self):
        """Enhanced approval dashboard"""
        self.ensure_one()
        
        # Try approval module if available
        try:
            action = self.env.ref('payroll_analytics_approval.action_payroll_approval_dashboard')
            return action.read()[0]
        except:
            # Fallback to payslip approval
            return {
                'type': 'ir.actions.act_window',
                'name': f'{self.country} Payroll Approval',
                'res_model': 'hr.payslip',
                'view_mode': 'tree,form',
                'domain': [('state', '=', 'draft')],
            }
