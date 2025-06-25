# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollAnalytics(models.Model):
    _name = 'payroll.analytics'
    _description = 'Payroll Analytics'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Basic Information
    name = fields.Char(string='Analytics Name', compute='_compute_name', store=True)
    period_name = fields.Char(string='Period Name', required=True, tracking=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True, tracking=True)
    
    # Period
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    
    # Summary Data
    total_employees = fields.Integer(string='Total Employees', readonly=True)
    total_payroll = fields.Monetary(string='Total Payroll', readonly=True)
    average_salary = fields.Monetary(string='Average Salary', readonly=True)
    variance_percentage = fields.Float(string='Variance %', readonly=True)
    
    # Change indicators (for dashboard display)
    employee_change = fields.Integer(string='Employee Change', readonly=True)
    payroll_change = fields.Float(string='Payroll Change %', readonly=True)
    avg_salary_change = fields.Float(string='Avg Salary Change %', readonly=True)
    
    # Analytics Data (JSON fields)
    employee_metrics = fields.Text(string='Employee Metrics', readonly=True)
    salary_components = fields.Text(string='Salary Components', readonly=True)
    comparison_data = fields.Text(string='Comparison Data', readonly=True)
    anomaly_alerts = fields.Text(string='Anomaly Alerts', readonly=True)
    
    # Approval Information
    approval_notes = fields.Text(string='Approval Notes')
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Datetime(string='Approval Date', readonly=True)
    
    # Counts for button badges
    payslip_run_count = fields.Integer(string='Payslip Runs', compute='_compute_counts')
    anomaly_count = fields.Integer(string='Anomalies', compute='_compute_counts')
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready for Approval'),
        ('approved', 'Approved'),
        ('exported', 'Exported')
    ], string='State', default='draft', tracking=True)
    
    # Company
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.depends('period_name', 'country')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.country} - {record.period_name or 'Analytics'}"

    def _compute_counts(self):
        for record in self:
            # Count related payslip runs
            record.payslip_run_count = self.env['hr.payslip.run'].search_count([
                ('date_start', '>=', record.date_from),
                ('date_end', '<=', record.date_to)
            ])
            
            # Count anomalies (from JSON data)
            try:
                anomalies = json.loads(record.anomaly_alerts or '{}')
                record.anomaly_count = len(anomalies)
            except:
                record.anomaly_count = 0

    @api.model
    def generate_analytics(self, country, date_from, date_to):
        """Generate analytics for a specific period and country"""
        period_name = f"{date_from.strftime('%B %Y')}"
        
        # Create analytics record
        analytics = self.create({
            'period_name': period_name,
            'country': country,
            'date_from': date_from,
            'date_to': date_to,
            'state': 'draft'
        })
        
        # Generate analytics data
        analytics._generate_analytics_data()
        analytics.state = 'ready'
        
        return analytics

    def _generate_analytics_data(self):
        """Generate analytics data for the period"""
        self.ensure_one()
        
        # Get payslip runs for the period
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('state', '=', 'done')
        ])
        
        total_employees = 0
        total_payroll = 0
        components = {}
        
        # Process payslips
        for run in payslip_runs:
            for payslip in run.slip_ids:
                total_employees += 1
                
                for line in payslip.line_ids:
                    if line.code == 'NETPAY':
                        total_payroll += line.total
                    
                    # Collect component data
                    if line.code not in components:
                        components[line.code] = {
                            'name': line.name,
                            'total': 0,
                            'count': 0,
                            'average': 0
                        }
                    components[line.code]['total'] += line.total
                    components[line.code]['count'] += 1
        
        # Calculate averages
        for code, comp in components.items():
            if comp['count'] > 0:
                comp['average'] = comp['total'] / comp['count']
        
        # Get previous month data for comparison
        previous_data = self._get_previous_month_data()
        comparison_data = self._calculate_variance(components, previous_data)
        anomaly_alerts = self._detect_anomalies(components, comparison_data)
        
        # Update analytics
        self.write({
            'total_employees': total_employees,
            'total_payroll': total_payroll,
            'average_salary': total_payroll / total_employees if total_employees else 0,
            'variance_percentage': comparison_data.get('total_variance', 0),
            'employee_change': comparison_data.get('employee_change', 0),
            'payroll_change': comparison_data.get('payroll_change', 0),
            'avg_salary_change': comparison_data.get('avg_salary_change', 0),
            'salary_components': json.dumps(components, default=str),
            'employee_metrics': json.dumps({
                'total': total_employees,
                'payslip_runs': len(payslip_runs),
                'average_per_run': total_employees / len(payslip_runs) if payslip_runs else 0
            }),
            'comparison_data': json.dumps(comparison_data, default=str),
            'anomaly_alerts': json.dumps(anomaly_alerts, default=str)
        })

    def _get_previous_month_data(self):
        """Get previous month analytics data for comparison"""
        from dateutil.relativedelta import relativedelta
        
        prev_month_start = self.date_from - relativedelta(months=1)
        prev_month_end = self.date_to - relativedelta(months=1)
        
        # Look for existing analytics
        prev_analytics = self.search([
            ('country', '=', self.country),
            ('date_from', '>=', prev_month_start),
            ('date_to', '<=', prev_month_end)
        ], limit=1)
        
        if prev_analytics:
            return {
                'total_employees': prev_analytics.total_employees,
                'total_payroll': prev_analytics.total_payroll,
                'average_salary': prev_analytics.average_salary,
                'components': json.loads(prev_analytics.salary_components or '{}')
            }
        
        # If no previous analytics, calculate from payslips
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', prev_month_start),
            ('date_end', '<=', prev_month_end),
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
                        components[line.code] = {'total': 0, 'count': 0}
                    components[line.code]['total'] += line.total
                    components[line.code]['count'] += 1
        
        return {
            'total_employees': total_employees,
            'total_payroll': total_payroll,
            'average_salary': total_payroll / total_employees if total_employees else 0,
            'components': components
        }

    def _calculate_variance(self, current_components, previous_data):
        """Calculate variance between current and previous period"""
        comparison = {
            'previous_month': previous_data,
            'variance': {},
            'employee_change': 0,
            'payroll_change': 0,
            'avg_salary_change': 0,
            'total_variance': 0
        }
        
        # Calculate employee change
        if previous_data['total_employees'] > 0:
            comparison['employee_change'] = self.total_employees - previous_data['total_employees']
        
        # Calculate payroll change
        if previous_data['total_payroll'] > 0:
            comparison['payroll_change'] = ((self.total_payroll - previous_data['total_payroll']) / previous_data['total_payroll']) * 100
            comparison['total_variance'] = abs(comparison['payroll_change'])
        
        # Calculate average salary change
        if previous_data['average_salary'] > 0:
            current_avg = self.total_payroll / self.total_employees if self.total_employees else 0
            comparison['avg_salary_change'] = ((current_avg - previous_data['average_salary']) / previous_data['average_salary']) * 100
        
        # Calculate component-wise variance
        for code, current_comp in current_components.items():
            previous_comp = previous_data['components'].get(code, {})
            previous_total = previous_comp.get('total', 0)
            
            if previous_total > 0:
                variance = ((current_comp['total'] - previous_total) / previous_total) * 100
                comparison['variance'][code] = variance
            else:
                comparison['variance'][code] = 100.0 if current_comp['total'] > 0 else 0.0
        
        return comparison

    def _detect_anomalies(self, components, comparison_data):
        """Detect anomalies in payroll data"""
        anomalies = {}
        variance_threshold = 15.0  # 15% variance threshold
        
        # Check for high variances
        for code, variance in comparison_data.get('variance', {}).items():
            if abs(variance) > variance_threshold:
                severity = 'high' if abs(variance) > 25 else 'medium'
                anomalies[f'variance_{code}'] = {
                    'title': f'High Variance in {code}',
                    'message': f'{code} shows {variance:.1f}% variance from previous month',
                    'severity': severity,
                    'details': f'Previous: {comparison_data["previous_month"]["components"].get(code, {}).get("total", 0)}, Current: {components[code]["total"]}'
                }
        
        # Check for missing components
        previous_components = set(comparison_data.get('previous_month', {}).get('components', {}).keys())
        current_components = set(components.keys())
        
        missing_components = previous_components - current_components
        new_components = current_components - previous_components
        
        if missing_components:
            anomalies['missing_components'] = {
                'title': 'Missing Salary Components',
                'message': f'Components missing this month: {", ".join(missing_components)}',
                'severity': 'medium',
                'details': 'These components were present last month but missing this month'
            }
        
        if new_components:
            anomalies['new_components'] = {
                'title': 'New Salary Components',
                'message': f'New components this month: {", ".join(new_components)}',
                'severity': 'low',
                'details': 'These components are new this month'
            }
        
        # Check for employee count anomalies
        employee_change = comparison_data.get('employee_change', 0)
        if abs(employee_change) > 5:  # More than 5 employees change
            anomalies['employee_count'] = {
                'title': 'Significant Employee Count Change',
                'message': f'Employee count {"increased" if employee_change > 0 else "decreased"} by {abs(employee_change)}',
                'severity': 'medium' if abs(employee_change) > 10 else 'low',
                'details': f'Previous: {comparison_data["previous_month"]["total_employees"]}, Current: {self.total_employees}'
            }
        
        return anomalies

    def action_approve_payroll(self):
        """Final approval of payroll"""
        self.ensure_one()
        
        if self.state != 'ready':
            raise UserError(_('Only payroll in ready state can be approved'))
        
        # Get related payslip runs and mark them as done
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('state', '!=', 'done')
        ])
        
        # Mark payslip runs as done
        for run in payslip_runs:
            if hasattr(run, 'action_close'):
                run.action_close()
            else:
                run.write({'state': 'done'})
        
        # Update analytics
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payroll Approved'),
                'message': _('%d payslip runs have been finalized.') % len(payslip_runs),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_export_bank_file(self):
        """Export bank disbursement file"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError(_('Only approved payroll can be exported'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Export Bank File',
            'res_model': 'payroll.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_analytics_id': self.id,
                'default_country': self.country,
                'default_date_from': self.date_from,
                'default_date_to': self.date_to,
            }
        }

    def action_view_payslip_runs(self):
        """View related payslip runs"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payslip Runs',
            'res_model': 'hr.payslip.run',
            'view_mode': 'tree,form',
            'domain': [
                ('date_start', '>=', self.date_from),
                ('date_end', '<=', self.date_to)
            ],
            'context': {}
        }

    def action_view_anomalies(self):
        """View anomaly details"""
        self.ensure_one()
        # This could open a detailed view of anomalies
        # For now, just return a notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Anomaly Details'),
                'message': self.anomaly_alerts or _('No anomalies detected'),
                'type': 'info',
            }
        }

    def action_open_dashboard(self):
        """Open the analytics dashboard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Analytics Dashboard',
            'res_model': 'payroll.analytics',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard').id,
            'target': 'current',
        }

    def get_chart_data(self):
        """Get formatted data for charts"""
        self.ensure_one()
        
        try:
            components = json.loads(self.salary_components) if self.salary_components else {}
            comparison = json.loads(self.comparison_data) if self.comparison_data else {}
            
            # Prepare chart data
            chart_data = {
                'components': {
                    'labels': [comp.get('name', code) for code, comp in components.items()],
                    'totals': [comp.get('total', 0) for comp in components.values()],
                    'averages': [comp.get('average', 0) for comp in components.values()]
                },
                'comparison': {
                    'current': [comp.get('total', 0) for comp in components.values()],
                    'previous': [],
                    'variance': []
                }
            }
            
            # Add comparison data if available
            if 'previous_month' in comparison and 'variance' in comparison:
                for code in components.keys():
                    prev = comparison['previous_month'].get('components', {}).get(code, {}).get('total', 0)
                    variance = comparison['variance'].get(code, 0)
                    chart_data['comparison']['previous'].append(prev)
                    chart_data['comparison']['variance'].append(variance)
            
            return chart_data
            
        except Exception as e:
            _logger.error(f"Error getting chart data: {e}")
            return {
                'components': {'labels': [], 'totals': [], 'averages': []},
                'comparison': {'current': [], 'previous': [], 'variance': []}
            }

    @api.model
    def auto_generate_analytics(self):
        """Auto-generate analytics for payslip runs that reach Level 2 approval"""
        # This method would be called by a cron job
        # Implementation depends on your payslip approval workflow
        
        # Example implementation:
        # Find payslip runs that are done but don't have analytics
        runs = self.env['hr.payslip.run'].search([
            ('state', '=', 'done'),
            ('analytics_id', '=', False)
        ])
        
        for run in runs:
            # Group runs by country and period
            country = self._detect_country_from_run(run)
            if country:
                # Check if analytics already exists for this period
                existing = self.search([
                    ('country', '=', country),
                    ('date_from', '<=', run.date_start),
                    ('date_to', '>=', run.date_end)
                ])
                
                if not existing:
                    analytics = self.generate_analytics(country, run.date_start, run.date_end)
                    run.analytics_id = analytics.id

    def _detect_country_from_run(self, payslip_run):
        """Detect country from payslip run"""
        # This depends on how you determine country in your payslip structure
        # Example implementation:
        if payslip_run.slip_ids:
            first_slip = payslip_run.slip_ids[0]
            if first_slip.struct_id:
                # You might have country-specific structures
                if 'indonesia' in first_slip.struct_id.name.lower():
                    return 'ID'
                elif 'vietnam' in first_slip.struct_id.name.lower():
                    return 'VN'
                elif 'india' in first_slip.struct_id.name.lower():
                    return 'IN'
        return 'ID'  # Default to Indonesia