# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import csv
import io
import base64

_logger = logging.getLogger(__name__)


class PayrollAnalytics(models.Model):
    _name = 'payroll.analytics'
    _description = 'Advanced Payroll Analytics'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # ✅ ADD THIS LINE
    _order = 'period_start desc'
    _rec_name = 'period_name'

    # Period Information
    period_name = fields.Char('Period Name', required=True)
    period_start = fields.Date('Period Start', required=True)
    period_end = fields.Date('Period End', required=True)
    
    # Country and Currency
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Country', required=True, tracking=True)  # ✅ ADD tracking=True
    
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    
    # Core Metrics
    total_employees = fields.Integer('Total Employees', compute='_compute_analytics', store=True)
    total_payroll = fields.Monetary('Total Payroll', compute='_compute_analytics', store=True)
    average_salary = fields.Monetary('Average Salary', compute='_compute_analytics', store=True)
    median_salary = fields.Monetary('Median Salary', compute='_compute_analytics', store=True)
    
    # Comparison Metrics
    previous_period_id = fields.Many2one('payroll.analytics', 'Previous Period')
    employee_growth = fields.Float('Employee Growth %', compute='_compute_comparisons', store=True)
    payroll_growth = fields.Float('Payroll Growth %', compute='_compute_comparisons', store=True)
    average_salary_growth = fields.Float('Avg Salary Growth %', compute='_compute_comparisons', store=True)
    
    # Component Analysis (JSON fields for flexibility)
    salary_components = fields.Text('Salary Components Analysis')
    deduction_components = fields.Text('Deduction Components Analysis')
    benefit_components = fields.Text('Benefit Components Analysis')
    
    # Variance Analysis
    variance_alerts = fields.Text('Variance Alerts')
    anomaly_count = fields.Integer('Anomaly Count', compute='_compute_anomalies', store=True)
    
    # Detailed Breakdowns
    department_breakdown = fields.Text('Department Breakdown')
    position_breakdown = fields.Text('Position Breakdown')
    contract_type_breakdown = fields.Text('Contract Type Breakdown')
    
    # Status and Workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computing', 'Computing Analytics'),
        ('ready', 'Ready for Review'),
        ('approved', 'Approved'),
        ('archived', 'Archived'),
    ], default='draft', string='Status', tracking=True)  # ✅ ADD tracking=True
        
    # Processing Information
    computation_date = fields.Datetime('Computation Date')
    computation_duration = fields.Float('Computation Time (seconds)')
    data_source = fields.Selection([
        ('payslips', 'Payslips'),
        ('contracts', 'Contracts'),
        ('mixed', 'Mixed Sources'),
    ], default='payslips', string='Data Source')
    
    # Access Control
    is_confidential = fields.Boolean('Confidential', default=True)
    approver_ids = fields.Many2many('res.users', string='Approved By')

    @api.depends('period_start', 'period_end', 'country_code')
    def _compute_analytics(self):
        """Compute comprehensive analytics for the period"""
        for record in self:
            if not record.period_start or not record.period_end:
                continue
                
            try:
                record.state = 'computing'
                start_time = datetime.now()
                
                # Get payslips for the period
                payslips = self._get_period_payslips(record)
                
                if not payslips:
                    record._set_zero_metrics()
                    continue
                
                # Basic metrics
                record.total_employees = len(payslips.mapped('employee_id'))
                
                # Get salary totals
                gross_lines = payslips.line_ids.filtered(lambda l: l.category_id.code == 'GROSS')
                record.total_payroll = sum(gross_lines.mapped('total'))
                
                if record.total_employees > 0:
                    record.average_salary = record.total_payroll / record.total_employees
                    
                    # Calculate median salary
                    salaries = gross_lines.mapped('total')
                    salaries.sort()
                    n = len(salaries)
                    if n > 0:
                        if n % 2 == 0:
                            record.median_salary = (salaries[n//2-1] + salaries[n//2]) / 2
                        else:
                            record.median_salary = salaries[n//2]
                
                # Detailed component analysis
                record._compute_component_analysis(payslips)
                record._compute_department_breakdown(payslips)
                record._compute_position_breakdown(payslips)
                
                # Computation metadata
                end_time = datetime.now()
                record.computation_date = end_time
                record.computation_duration = (end_time - start_time).total_seconds()
                record.state = 'ready'
                
            except Exception as e:
                _logger.error(f"Error computing analytics for {record.period_name}: {str(e)}")
                record.state = 'draft'
                record._set_zero_metrics()

    def _get_period_payslips(self, record):
        """Get payslips for the analytics period"""
        domain = [
            ('date_from', '>=', record.period_start),
            ('date_to', '<=', record.period_end),
            ('state', 'in', ['done', 'paid']),
        ]
        
        if record.country_code:
            domain.append(('contract_id.payroll_country_code', '=', record.country_code))
        
        return self.env['hr.payslip'].search(domain)

    def _set_zero_metrics(self):
        """Set all metrics to zero when no data available"""
        self.total_employees = 0
        self.total_payroll = 0.0
        self.average_salary = 0.0
        self.median_salary = 0.0

    def _compute_component_analysis(self, payslips):
        """Analyze salary components"""
        self.ensure_one()
        
        # Group by salary rule categories
        component_data = {}
        
        for line in payslips.line_ids:
            category = line.category_id.name
            if category not in component_data:
                component_data[category] = {
                    'total': 0.0,
                    'count': 0,
                    'average': 0.0,
                    'percentage': 0.0,
                }
            
            component_data[category]['total'] += line.total
            component_data[category]['count'] += 1
        
        # Calculate percentages and averages
        total_amount = sum(data['total'] for data in component_data.values())
        
        for category, data in component_data.items():
            if data['count'] > 0:
                data['average'] = data['total'] / data['count']
            if total_amount > 0:
                data['percentage'] = (data['total'] / total_amount) * 100
        
        # Store as JSON
        self.salary_components = json.dumps(component_data, default=str)

    def _compute_department_breakdown(self, payslips):
        """Analyze by department"""
        self.ensure_one()
        
        dept_data = {}
        
        for payslip in payslips:
            dept = payslip.employee_id.department_id.name or 'No Department'
            if dept not in dept_data:
                dept_data[dept] = {
                    'employee_count': 0,
                    'total_payroll': 0.0,
                    'average_salary': 0.0,
                }
            
            gross_total = sum(payslip.line_ids.filtered(
                lambda l: l.category_id.code == 'GROSS'
            ).mapped('total'))
            
            dept_data[dept]['employee_count'] += 1
            dept_data[dept]['total_payroll'] += gross_total
        
        # Calculate averages
        for dept, data in dept_data.items():
            if data['employee_count'] > 0:
                data['average_salary'] = data['total_payroll'] / data['employee_count']
        
        self.department_breakdown = json.dumps(dept_data, default=str)

    def _compute_position_breakdown(self, payslips):
        """Analyze by job position"""
        self.ensure_one()
        
        position_data = {}
        
        for payslip in payslips:
            position = payslip.employee_id.job_id.name or 'No Position'
            if position not in position_data:
                position_data[position] = {
                    'employee_count': 0,
                    'total_payroll': 0.0,
                    'average_salary': 0.0,
                    'min_salary': float('inf'),
                    'max_salary': 0.0,
                }
            
            gross_total = sum(payslip.line_ids.filtered(
                lambda l: l.category_id.code == 'GROSS'
            ).mapped('total'))
            
            position_data[position]['employee_count'] += 1
            position_data[position]['total_payroll'] += gross_total
            position_data[position]['min_salary'] = min(
                position_data[position]['min_salary'], gross_total
            )
            position_data[position]['max_salary'] = max(
                position_data[position]['max_salary'], gross_total
            )
        
        # Calculate averages and fix infinity values
        for position, data in position_data.items():
            if data['employee_count'] > 0:
                data['average_salary'] = data['total_payroll'] / data['employee_count']
            if data['min_salary'] == float('inf'):
                data['min_salary'] = 0.0
        
        self.position_breakdown = json.dumps(position_data, default=str)

    @api.depends('previous_period_id', 'total_employees', 'total_payroll', 'average_salary')
    def _compute_comparisons(self):
        """Compute growth comparisons with previous period"""
        for record in self:
            if not record.previous_period_id:
                record.employee_growth = 0.0
                record.payroll_growth = 0.0
                record.average_salary_growth = 0.0
                continue
            
            prev = record.previous_period_id
            
            # Employee growth
            if prev.total_employees > 0:
                record.employee_growth = (
                    (record.total_employees - prev.total_employees) / prev.total_employees
                ) * 100
            else:
                record.employee_growth = 100.0 if record.total_employees > 0 else 0.0
            
            # Payroll growth
            if prev.total_payroll > 0:
                record.payroll_growth = (
                    (record.total_payroll - prev.total_payroll) / prev.total_payroll
                ) * 100
            else:
                record.payroll_growth = 100.0 if record.total_payroll > 0 else 0.0
            
            # Average salary growth
            if prev.average_salary > 0:
                record.average_salary_growth = (
                    (record.average_salary - prev.average_salary) / prev.average_salary
                ) * 100
            else:
                record.average_salary_growth = 100.0 if record.average_salary > 0 else 0.0

    @api.depends('variance_alerts')
    def _compute_anomalies(self):
        """Count anomalies from variance alerts"""
        for record in self:
            if record.variance_alerts:
                try:
                    alerts = json.loads(record.variance_alerts)
                    record.anomaly_count = len(alerts.get('anomalies', []))
                except:
                    record.anomaly_count = 0
            else:
                record.anomaly_count = 0

    def action_compute_analytics(self):
        """Manual trigger for analytics computation"""
        self.ensure_one()
        self._compute_analytics()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Analytics Computed'),
                'message': _('Analytics have been successfully computed.'),
                'type': 'success',
            }
        }

    def action_export_analytics(self):
        """Export analytics to Excel"""
        self.ensure_one()
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'Period', 'Country', 'Total Employees', 'Total Payroll',
            'Average Salary', 'Median Salary', 'Employee Growth %',
            'Payroll Growth %', 'Anomaly Count'
        ])
        
        # Data
        writer.writerow([
            self.period_name,
            self.country_code,
            self.total_employees,
            self.total_payroll,
            self.average_salary,
            self.median_salary,
            self.employee_growth,
            self.payroll_growth,
            self.anomaly_count,
        ])
        
        # Create attachment
        csv_data = output.getvalue().encode('utf-8')
        attachment = self.env['ir.attachment'].create({
            'name': f'Analytics_{self.period_name}_{self.country_code}.csv',
            'type': 'binary',
            'datas': base64.b64encode(csv_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/csv',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_approve(self):
        """Approve analytics"""
        self.ensure_one()
        self.state = 'approved'
        self.approver_ids = [(4, self.env.user.id)]
        return True

    @api.model
    def auto_generate_monthly_analytics(self):
        """Cron job to auto-generate monthly analytics"""
        # Get last month's date range
        today = fields.Date.today()
        last_month = today.replace(day=1) - timedelta(days=1)
        month_start = last_month.replace(day=1)
        
        # Generate for each country
        countries = ['VN', 'ID', 'IN', 'SG', 'MY', 'TH']
        
        for country in countries:
            # Check if analytics already exist
            existing = self.search([
                ('period_start', '=', month_start),
                ('period_end', '=', last_month),
                ('country_code', '=', country),
            ])
            
            if not existing:
                # Create new analytics
                analytics = self.create({
                    'period_name': f"{last_month.strftime('%B %Y')} - {country}",
                    'period_start': month_start,
                    'period_end': last_month,
                    'country_code': country,
                    'currency_id': self._get_country_currency(country),
                })
                
                # Find previous period for comparison
                prev_month_start = (month_start - relativedelta(months=1))
                prev_month_end = month_start - timedelta(days=1)
                
                previous = self.search([
                    ('period_start', '=', prev_month_start),
                    ('period_end', '=', prev_month_end),
                    ('country_code', '=', country),
                ], limit=1)
                
                if previous:
                    analytics.previous_period_id = previous.id
                
                _logger.info(f"Auto-generated analytics for {country} - {last_month.strftime('%B %Y')}")

    def _get_country_currency(self, country_code):
        """Get currency for country"""
        currency_map = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR',
            'SG': 'SGD', 'MY': 'MYR'
        }
        
        currency_code = currency_map.get(country_code, 'USD')
        currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        return currency.id if currency else self.env.company.currency_id.id