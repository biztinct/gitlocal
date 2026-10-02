# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollComparison(models.Model):
    _name = 'payroll.comparison'
    _description = 'Payroll Comparison Analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Analysis Name', required=True, tracking=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True, tracking=True)
    
    # Current Period
    current_period_from = fields.Date(string='Current Period From', required=True)
    current_period_to = fields.Date(string='Current Period To', required=True)
    current_total_employees = fields.Integer(string='Current Employees', readonly=True)
    current_total_payroll = fields.Monetary(string='Current Total Payroll', readonly=True)
    
    # Previous Period
    comparison_type = fields.Selection([
        ('previous_month', 'Previous Month'),
        ('previous_quarter', 'Previous Quarter'),
        ('same_month_last_year', 'Same Month Last Year'),
        ('custom', 'Custom Period')
    ], string='Comparison Type', required=True, default='previous_month')
    previous_period_from = fields.Date(string='Previous Period From')
    previous_period_to = fields.Date(string='Previous Period To')
    previous_total_employees = fields.Integer(string='Previous Employees', readonly=True)
    previous_total_payroll = fields.Monetary(string='Previous Total Payroll', readonly=True)
    
    # Analysis Results
    employee_variance = fields.Float(string='Employee Variance %', readonly=True)
    payroll_variance = fields.Float(string='Payroll Variance %', readonly=True)
    average_salary_variance = fields.Float(string='Average Salary Variance %', readonly=True)
    
    # Configuration
    variance_threshold = fields.Float(string='Variance Threshold %', default=10.0)
    include_charts = fields.Boolean(string='Include Charts', default=True)
    
    # Analysis Data
    component_analysis = fields.Text(string='Component Analysis', readonly=True)
    analysis_results = fields.Text(string='Analysis Results', readonly=True)
    chart_data = fields.Text(string='Chart Data', readonly=True)
    recommendations = fields.Text(string='Recommendations', readonly=True)
    alerts = fields.Text(string='Alerts', readonly=True)
    
    # States
    state = fields.Selection([
        ('draft', 'Draft'),
        ('analyzing', 'Analyzing'),
        ('done', 'Completed'),
        ('error', 'Error')
    ], string='State', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    def action_regenerate_analysis(self):
        """Regenerate analysis"""
        self.ensure_one()
        self.state = 'analyzing'
        
        try:
            # Set previous period dates if not custom
            if self.comparison_type != 'custom':
                self._set_previous_period_dates()
            
            # Get payroll data for both periods
            current_data = self._get_period_data(self.current_period_from, self.current_period_to)
            previous_data = self._get_period_data(self.previous_period_from, self.previous_period_to)
            
            # Calculate variances
            self._calculate_variances(current_data, previous_data)
            
            # Generate analysis
            self._generate_component_analysis(current_data, previous_data)
            self._generate_recommendations()
            self._generate_alerts()
            
            self.state = 'done'
            
        except Exception as e:
            _logger.error(f"Error generating comparison analysis: {e}")
            self.state = 'error'
            raise UserError(_('Error generating analysis: %s') % str(e))

    def action_export_report(self):
        """Export comparison report"""
        return {
            'type': 'ir.actions.report',
            'report_name': 'payroll_analytics_approval.report_payroll_comparison',
            'report_type': 'qweb-pdf',
            'data': {},
            'context': self.env.context,
        }

    def action_open_dashboard(self):
        """Open comparison dashboard"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Comparison Dashboard',
            'res_model': 'payroll.comparison',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('payroll_analytics_approval.view_payroll_comparison_dashboard').id,
            'target': 'current',
        }

    def _set_previous_period_dates(self):
        """Set previous period dates based on comparison type"""
        from dateutil.relativedelta import relativedelta
        
        if self.comparison_type == 'previous_month':
            self.previous_period_from = self.current_period_from - relativedelta(months=1)
            self.previous_period_to = self.current_period_to - relativedelta(months=1)
        elif self.comparison_type == 'previous_quarter':
            self.previous_period_from = self.current_period_from - relativedelta(months=3)
            self.previous_period_to = self.current_period_to - relativedelta(months=3)
        elif self.comparison_type == 'same_month_last_year':
            self.previous_period_from = self.current_period_from - relativedelta(years=1)
            self.previous_period_to = self.current_period_to - relativedelta(years=1)

    def _get_period_data(self, date_from, date_to):
        """Get payroll data for a specific period"""
        # Get payslip runs for the period
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', date_from),
            ('date_end', '<=', date_to),
            ('state', '=', 'done')
        ])
        
        total_employees = 0
        total_payroll = 0
        components = {}
        
        for run in payslip_runs:
            for payslip in run.slip_ids:
                total_employees += 1
                for line in payslip.line_ids:
                    if line.code == 'NETPAY':
                        total_payroll += line.total
                    
                    if line.code not in components:
                        components[line.code] = {
                            'name': line.name,
                            'total': 0,
                            'count': 0
                        }
                    components[line.code]['total'] += line.total
                    components[line.code]['count'] += 1
        
        return {
            'total_employees': total_employees,
            'total_payroll': total_payroll,
            'components': components
        }

    def _calculate_variances(self, current_data, previous_data):
        """Calculate variance percentages"""
        # Update current period data
        self.current_total_employees = current_data['total_employees']
        self.current_total_payroll = current_data['total_payroll']
        self.previous_total_employees = previous_data['total_employees']
        self.previous_total_payroll = previous_data['total_payroll']
        
        # Calculate variances
        if previous_data['total_employees'] > 0:
            self.employee_variance = ((current_data['total_employees'] - previous_data['total_employees']) / previous_data['total_employees']) * 100
        
        if previous_data['total_payroll'] > 0:
            self.payroll_variance = ((current_data['total_payroll'] - previous_data['total_payroll']) / previous_data['total_payroll']) * 100
        
        current_avg = current_data['total_payroll'] / current_data['total_employees'] if current_data['total_employees'] else 0
        previous_avg = previous_data['total_payroll'] / previous_data['total_employees'] if previous_data['total_employees'] else 0
        
        if previous_avg > 0:
            self.average_salary_variance = ((current_avg - previous_avg) / previous_avg) * 100

    def _generate_component_analysis(self, current_data, previous_data):
        """Generate detailed component analysis"""
        analysis = {
            'summary': 'Component-wise analysis completed',
            'current_period': current_data.get('components', {}),
            'previous_period': previous_data.get('components', {}),
            'variances': {}
        }
        
        # Calculate component variances
        for code in current_data.get('components', {}):
            current_total = current_data['components'][code]['total']
            previous_total = previous_data.get('components', {}).get(code, {}).get('total', 0)
            
            if previous_total > 0:
                variance = ((current_total - previous_total) / previous_total) * 100
                analysis['variances'][code] = variance
        
        self.component_analysis = json.dumps(analysis, indent=2, default=str)

    def _generate_recommendations(self):
        """Generate recommendations based on analysis"""
        recommendations = []
        
        if abs(self.payroll_variance) <= 5:
            recommendations.append("Payroll variance is within normal range")
        elif abs(self.payroll_variance) > 15:
            recommendations.append("Investigate high payroll variance - consider reviewing individual component changes")
        
        if abs(self.employee_variance) <= 2:
            recommendations.append("Employee count is stable")
        elif self.employee_variance > 10:
            recommendations.append("Significant employee increase detected - ensure all new hires are properly onboarded")
        elif self.employee_variance < -10:
            recommendations.append("Significant employee decrease detected - review retention strategies")
        
        if abs(self.average_salary_variance) <= 3:
            recommendations.append("Average salary changes are within expected range")
        
        self.recommendations = json.dumps(recommendations, indent=2)

    def _generate_alerts(self):
        """Generate alerts for significant changes"""
        alerts = []
        
        if abs(self.payroll_variance) > self.variance_threshold:
            alerts.append({
                'type': 'high_variance',
                'message': f"High payroll variance detected: {self.payroll_variance:.1f}%",
                'severity': 'high' if abs(self.payroll_variance) > 20 else 'medium'
            })
        
        if abs(self.employee_variance) > 10:
            alerts.append({
                'type': 'employee_change',
                'message': f"Significant employee count change: {self.employee_variance:.1f}%",
                'severity': 'medium'
            })
        
        if abs(self.average_salary_variance) > 15:
            alerts.append({
                'type': 'salary_variance',
                'message': f"High average salary variance: {self.average_salary_variance:.1f}%",
                'severity': 'medium'
            })
        
        self.alerts = json.dumps(alerts, indent=2)