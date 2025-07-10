# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class AnalyticsWizard(models.TransientModel):
    _name = 'analytics.wizard'
    _description = 'Analytics Generation Wizard'

    # Period Configuration
    period_start = fields.Date('Period Start', required=True, 
                              default=lambda self: fields.Date.today().replace(day=1))
    period_end = fields.Date('Period End', required=True,
                            default=lambda self: (fields.Date.today().replace(day=1) + relativedelta(months=1) - timedelta(days=1)))
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Period'),
    ], default='monthly', string='Period Type')
    auto_name = fields.Boolean('Auto Generate Name', default=True)

    # Country & Scope
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),
        ('PH', 'Philippines'),
    ], string='Country', required=True)
    include_all_employees = fields.Boolean('Include All Employees', default=True)
    employee_ids = fields.Many2many('hr.employee', string='Specific Employees')

    # Analytics Options
    include_comparisons = fields.Boolean('Include Period Comparisons', default=True)
    previous_period_id = fields.Many2one('payroll.analytics', 'Compare with Period')
    include_anomaly_detection = fields.Boolean('Include Anomaly Detection', default=True)
    anomaly_threshold = fields.Float('Anomaly Threshold (%)', default=15.0)

    # Component Analysis
    analyze_salary_components = fields.Boolean('Analyze Salary Components', default=True)
    analyze_deductions = fields.Boolean('Analyze Deductions', default=True)
    analyze_benefits = fields.Boolean('Analyze Benefits', default=True)
    include_department_breakdown = fields.Boolean('Department Breakdown', default=True)

    # Data Sources
    data_source = fields.Selection([
        ('payslips', 'Payslips'),
        ('contracts', 'Contracts'),
        ('mixed', 'Mixed Sources'),
    ], default='payslips', string='Data Source')
    include_inactive_employees = fields.Boolean('Include Inactive Employees', default=False)
    payslip_state_filter = fields.Selection([
        ('all', 'All States'),
        ('done', 'Done Only'),
        ('paid', 'Paid Only'),
    ], default='done', string='Payslip State Filter')

    # Output Options
    auto_approve = fields.Boolean('Auto Approve', default=False)
    generate_charts = fields.Boolean('Generate Charts', default=True)
    export_to_excel = fields.Boolean('Export to Excel', default=False)
    send_notification = fields.Boolean('Send Notification', default=True)

    # Advanced Settings
    currency_id = fields.Many2one('res.currency', 'Currency')
    exchange_rate_date = fields.Date('Exchange Rate Date', default=fields.Date.today)
    rounding_precision = fields.Integer('Rounding Precision', default=2)
    batch_size = fields.Integer('Batch Size', default=100)
    parallel_processing = fields.Boolean('Parallel Processing', default=False)
    cache_results = fields.Boolean('Cache Results', default=True)

    # Custom Filters
    custom_domain = fields.Char('Custom Domain Filter')

    # Preview Fields
    estimated_employee_count = fields.Integer('Estimated Employee Count', readonly=True)
    estimated_payslip_count = fields.Integer('Estimated Payslip Count', readonly=True)
    estimated_processing_time = fields.Float('Estimated Processing Time (seconds)', readonly=True)

    @api.onchange('country_code')
    def _onchange_country_code(self):
        """Set currency based on country"""
        if self.country_code:
            currency_map = {
                'VN': 'VND', 'ID': 'IDR', 'IN': 'INR',
                'SG': 'SGD', 'MY': 'MYR', 'TH': 'THB', 'PH': 'PHP'
            }
            currency_code = currency_map.get(self.country_code)
            if currency_code:
                currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
                self.currency_id = currency.id if currency else self.env.company.currency_id.id

    @api.onchange('period_type', 'period_start')
    def _onchange_period_type(self):
        """Auto-set period end based on type"""
        if self.period_start and self.period_type:
            if self.period_type == 'monthly':
                self.period_end = self.period_start.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
            elif self.period_type == 'quarterly':
                self.period_end = self.period_start + relativedelta(months=3) - timedelta(days=1)
            elif self.period_type == 'yearly':
                self.period_end = self.period_start.replace(month=12, day=31)

    @api.onchange('include_comparisons', 'country_code', 'period_start')
    def _onchange_include_comparisons(self):
        """Find available previous periods for comparison"""
        if self.include_comparisons and self.country_code and self.period_start:
            # Find previous period analytics
            domain = [
                ('country_code', '=', self.country_code),
                ('period_end', '<', self.period_start),
                ('state', 'in', ['ready', 'approved'])
            ]
            previous_analytics = self.env['payroll.analytics'].search(domain, order='period_end desc', limit=1)
            if previous_analytics:
                self.previous_period_id = previous_analytics.id

    def action_preview_analytics(self):
        """Generate preview of analytics data"""
        self.ensure_one()
        
        try:
            # Get estimated counts
            domain = self._build_payslip_domain()
            payslips = self.env['hr.payslip'].search(domain)
            
            self.estimated_payslip_count = len(payslips)
            self.estimated_employee_count = len(payslips.mapped('employee_id'))
            
            # Estimate processing time (rough calculation)
            base_time = 5  # Base 5 seconds
            employee_factor = self.estimated_employee_count * 0.1
            payslip_factor = self.estimated_payslip_count * 0.05
            
            self.estimated_processing_time = base_time + employee_factor + payslip_factor
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Preview Generated'),
                    'message': _('Found %d employees and %d payslips for analysis.') % (
                        self.estimated_employee_count, self.estimated_payslip_count
                    ),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Error generating preview: %s') % str(e))

    def action_generate_analytics(self):
        """Generate the analytics report"""
        self.ensure_one()
        
        try:
            # Validate inputs
            self._validate_inputs()
            
            # Create analytics record
            analytics_data = self._prepare_analytics_data()
            analytics = self.env['payroll.analytics'].create(analytics_data)
            
            # Trigger computation
            analytics.action_compute_analytics()
            
            # Auto-approve if requested
            if self.auto_approve:
                analytics.action_approve()
            
            # Export to Excel if requested
            if self.export_to_excel:
                analytics.action_export_analytics()
            
            # Send notification if requested
            if self.send_notification:
                self._send_notification(analytics)
            
            return {
                'name': _('Generated Analytics'),
                'type': 'ir.actions.act_window',
                'res_model': 'payroll.analytics',
                'res_id': analytics.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            _logger.error(f"Error generating analytics: {str(e)}")
            raise UserError(_('Error generating analytics: %s') % str(e))

    def _validate_inputs(self):
        """Validate wizard inputs"""
        if self.period_start >= self.period_end:
            raise ValidationError(_('Period start must be before period end.'))
        
        if not self.include_all_employees and not self.employee_ids:
            raise ValidationError(_('Please select employees or choose to include all employees.'))
        
        if self.anomaly_threshold < 0 or self.anomaly_threshold > 100:
            raise ValidationError(_('Anomaly threshold must be between 0 and 100.'))

    def _prepare_analytics_data(self):
        """Prepare data for analytics creation"""
        period_name = self._generate_period_name()
        
        return {
            'period_name': period_name,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'country_code': self.country_code,
            'currency_id': self.currency_id.id or self._get_default_currency().id,
            'previous_period_id': self.previous_period_id.id if self.previous_period_id else False,
            'data_source': self.data_source,
            'state': 'draft',
        }

    def _generate_period_name(self):
        """Generate period name"""
        if self.auto_name:
            if self.period_type == 'monthly':
                return f"{self.period_start.strftime('%B %Y')} - {self.country_code}"
            elif self.period_type == 'quarterly':
                quarter = (self.period_start.month - 1) // 3 + 1
                return f"Q{quarter} {self.period_start.year} - {self.country_code}"
            elif self.period_type == 'yearly':
                return f"{self.period_start.year} - {self.country_code}"
            else:
                return f"{self.period_start.strftime('%d/%m/%Y')} - {self.period_end.strftime('%d/%m/%Y')} - {self.country_code}"
        else:
            return f"Analytics - {self.country_code}"

    def _build_payslip_domain(self):
        """Build domain for payslip search"""
        domain = [
            ('date_from', '>=', self.period_start),
            ('date_to', '<=', self.period_end),
        ]
        
        if self.payslip_state_filter != 'all':
            if self.payslip_state_filter == 'done':
                domain.append(('state', '=', 'done'))
            elif self.payslip_state_filter == 'paid':
                domain.append(('state', '=', 'paid'))
        
        if self.country_code:
            domain.append(('contract_id.payroll_country_code', '=', self.country_code))
        
        if not self.include_all_employees and self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        if not self.include_inactive_employees:
            domain.append(('employee_id.active', '=', True))
        
        if self.custom_domain:
            try:
                custom_domain = eval(self.custom_domain)
                domain.extend(custom_domain)
            except:
                _logger.warning("Invalid custom domain: %s", self.custom_domain)
        
        return domain

    def _get_default_currency(self):
        """Get default currency for country"""
        currency_map = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR',
            'SG': 'SGD', 'MY': 'MYR', 'TH': 'THB', 'PH': 'PHP'
        }
        
        currency_code = currency_map.get(self.country_code, 'USD')
        currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        return currency if currency else self.env.company.currency_id

    def _send_notification(self, analytics):
        """Send notification about generated analytics"""
        try:
            # Create notification message
            message = _(
                'Analytics report "%s" has been generated successfully.\n'
                'Period: %s to %s\n'
                'Country: %s\n'
                'Employees: %d\n'
                'Total Payroll: %s'
            ) % (
                analytics.period_name,
                analytics.period_start,
                analytics.period_end,
                analytics.country_code,
                analytics.total_employees,
                analytics.total_payroll
            )
            
            # Post message to analytics record
            analytics.message_post(
                body=message,
                subject=_('Analytics Generated'),
                message_type='notification'
            )
            
        except Exception as e:
            _logger.warning(f"Error sending notification: {str(e)}")

    @api.constrains('period_start', 'period_end')
    def _check_period_dates(self):
        """Validate period dates"""
        for record in self:
            if record.period_start and record.period_end:
                if record.period_start >= record.period_end:
                    raise ValidationError(_('Period start must be before period end.'))