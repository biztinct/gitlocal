# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import csv
import io
import base64

_logger = logging.getLogger(__name__)


class PayrollAnalytics(models.Model):
    _name = 'payroll.analytics'
    _description = 'Payroll Analytics Dashboard'
    _rec_name = 'period_name'
    
    period_name = fields.Char(string='Period', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    
    # Analytics Data (JSON fields for flexibility)
    employee_metrics = fields.Text(string='Employee Metrics JSON')
    salary_components = fields.Text(string='Salary Components JSON') 
    comparison_data = fields.Text(string='Comparison Data JSON')
    anomaly_alerts = fields.Text(string='Anomaly Alerts JSON')
    
    # Computed Analytics - NOW WITH STORE=TRUE to make them searchable
    total_employees = fields.Integer(string='Total Employees', compute='_compute_analytics', store=True)
    total_payroll = fields.Float(string='Total Payroll', compute='_compute_analytics', store=True)
    average_salary = fields.Float(string='Average Salary', compute='_compute_analytics', store=True)
    variance_percentage = fields.Float(string='Variance %', compute='_compute_analytics', store=True)

    # Add these missing fields:
    preview_record_count = fields.Integer(string='Preview Record Count', readonly=True)
    preview_total_amount = fields.Monetary(string='Preview Total Amount', readonly=True)
    
    # Make sure you also have the currency field for the monetary field 
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready for Approval'),
        ('approved', 'Approved'),
        ('exported', 'Exported')
    ], string='Status', default='draft')
    
    @api.depends('employee_metrics', 'salary_components', 'comparison_data')
    def _compute_analytics(self):
        """Compute key analytics from JSON data"""
        for record in self:
            # Initialize defaults
            record.total_employees = 0
            record.total_payroll = 0.0
            record.average_salary = 0.0
            record.variance_percentage = 0.0
            
            try:
                if record.employee_metrics:
                    metrics = json.loads(record.employee_metrics)
                    record.total_employees = metrics.get('total_employees', 0)
                    record.total_payroll = metrics.get('total_payroll', 0.0)
                    record.average_salary = metrics.get('average_salary', 0.0)
                
                # Calculate variance percentage with proper handling
                if record.comparison_data:
                    comparison = json.loads(record.comparison_data)
                    current_total = record.total_payroll
                    
                    if comparison.get('previous_month_total', 0) > 0:
                        prev_total = comparison['previous_month_total']
                        record.variance_percentage = ((current_total - prev_total) / prev_total) * 100
                    elif current_total > 0:
                        # If there's current data but no previous data, show 100% increase
                        record.variance_percentage = 100.0
                    else:
                        # Both are zero or no data
                        record.variance_percentage = 0.0
                        
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                _logger.warning(f"Error computing analytics for record {record.id}: {e}")
    
    def action_open_dashboard(self):
        """Open analytics dashboard for this record"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Analytics Dashboard - {self.period_name}',
            'res_model': 'payroll.analytics',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard').id,
            'target': 'current',
            'context': {'create': False, 'edit': False}
        }
    
    @api.model
    def generate_analytics(self, country, date_from, date_to):
        """Generate analytics for given country and period"""
        period_name = f"{date_from.strftime('%B %Y')} - {country}"
        
        # Get payslips for the period
        payslips = self._get_payslips_for_period(country, date_from, date_to)
        
        # Generate analytics data
        analytics_data = self._generate_analytics_data(payslips, country, date_from, date_to)
        
        # Check if analytics already exists
        existing = self.search([
            ('country', '=', country),
            ('date_from', '=', date_from),
            ('date_to', '=', date_to)
        ], limit=1)
        
        if existing:
            existing.write(analytics_data)
            return existing
        else:
            analytics_data.update({
                'period_name': period_name,
                'country': country,
                'date_from': date_from,
                'date_to': date_to
            })
            return self.create(analytics_data)
    
    def _get_payslips_for_period(self, country, date_from, date_to):
        """Get payslips for the specific country and period"""
        # Map countries to salary structures
        country_structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure',
            'IN': 'India Salary Structure'
        }
        
        structure_name = country_structure_map.get(country)
        if not structure_name:
            return self.env['hr.payslip']
        
        structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
        if not structure:
            return self.env['hr.payslip']
        
        # Get payslips
        payslips = self.env['hr.payslip'].search([
            ('struct_id', '=', structure.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['level2', 'done'])
        ])
        
        return payslips
    
    def _generate_analytics_data(self, payslips, country, date_from, date_to):
        """Generate detailed analytics data"""
        if not payslips:
            return {
                'employee_metrics': json.dumps({'total_employees': 0, 'total_payroll': 0, 'average_salary': 0}),
                'salary_components': json.dumps({}),
                'comparison_data': json.dumps({'previous_month_total': 0}),
                'anomaly_alerts': json.dumps([])
            }
        
        # Employee metrics
        total_payroll = sum(p.line_ids.filtered(lambda l: l.code == 'NETPAY').mapped('total'))
        employee_metrics = {
            'total_employees': len(payslips),
            'total_payroll': total_payroll,
            'departments': {},
            'positions': {}
        }
        employee_metrics['average_salary'] = total_payroll / len(payslips) if payslips else 0
        
        # Salary components analysis
        salary_components = {}
        component_codes = ['BASIC', 'MIONEFIVE', 'BPJS_JKK', 'BPJS_KES_COMP', 'LAINALL', 
                          'BPJS_JHT_COMP', 'BPJS_JP_COMP', 'BPJS_KES_EMP', 'BPJS_JHT_EMP', 
                          'BPJS_JP_EMP', 'MONPIT', 'NETPAY']
        
        for code in component_codes:
            lines = payslips.mapped('line_ids').filtered(lambda l: l.code == code)
            if lines:
                total = sum(lines.mapped('total'))
                average = total / len(lines) if lines else 0
                salary_components[code] = {
                    'total': total,
                    'average': average,
                    'count': len(lines),
                    'name': self._get_component_name(code)
                }
        
        # Historical comparison with improved variance calculation
        comparison_data = self._get_historical_comparison(country, date_from, salary_components)
        
        # Anomaly detection
        anomaly_alerts = self._detect_anomalies(salary_components, comparison_data)
        
        return {
            'employee_metrics': json.dumps(employee_metrics),
            'salary_components': json.dumps(salary_components),
            'comparison_data': json.dumps(comparison_data),
            'anomaly_alerts': json.dumps(anomaly_alerts)
        }
    
    def _get_component_name(self, code):
        """Get display name for component code"""
        mapping = {
            'BASIC': 'Basic Salary',
            'MIONEFIVE': 'Life Insurance',
            'BPJS_JKK': 'Work Accident Insurance',
            'BPJS_KES_COMP': 'BPJS Healthcare (Company)',
            'LAINALL': 'THR',
            'BPJS_JHT_COMP': 'Old Age Fund (Company)',
            'BPJS_JP_COMP': 'Pension Fund (Company)',
            'BPJS_KES_EMP': 'BPJS Healthcare (Employee)',
            'BPJS_JHT_EMP': 'Old Age Fund (Employee)',
            'BPJS_JP_EMP': 'Pension (Employee)',
            'MONPIT': 'Income Tax',
            'NETPAY': 'Net Pay'
        }
        return mapping.get(code, code)
    
    def _get_historical_comparison(self, country, current_date, current_components):
        """Get historical data for comparison with improved variance calculation"""
        # Get previous month
        prev_month = current_date - relativedelta(months=1)
        prev_analytics = self.search([
            ('country', '=', country),
            ('date_from', '>=', prev_month),
            ('date_from', '<', current_date)
        ], limit=1)
        
        comparison = {
            'previous_month': {},
            'variance': {},
            'trend': 'stable',
            'previous_month_total': 0
        }
        
        if prev_analytics and prev_analytics.salary_components:
            try:
                prev_components = json.loads(prev_analytics.salary_components)
                prev_total = 0
                
                for code, current in current_components.items():
                    current_total = current['total']
                    
                    if code in prev_components:
                        prev_total_comp = prev_components[code]['total']
                        prev_total += prev_total_comp
                        
                        # Safe variance calculation
                        if prev_total_comp > 0:
                            variance = ((current_total - prev_total_comp) / prev_total_comp) * 100
                        elif current_total > 0:
                            variance = 100.0  # New component with value
                        else:
                            variance = 0.0  # Both zero
                        
                        comparison['previous_month'][code] = prev_components[code]
                        comparison['variance'][code] = round(variance, 2)
                    else:
                        # New component
                        comparison['variance'][code] = 100.0 if current_total > 0 else 0.0
                
                comparison['previous_month_total'] = prev_total
                
                # Overall trend calculation
                current_total = sum(comp['total'] for comp in current_components.values())
                
                if prev_total > 0:
                    overall_variance = ((current_total - prev_total) / prev_total) * 100
                    if overall_variance > 5:
                        comparison['trend'] = 'increasing'
                    elif overall_variance < -5:
                        comparison['trend'] = 'decreasing'
                
            except Exception as e:
                _logger.error(f"Error in historical comparison: {e}")
                comparison['previous_month_total'] = 0
        else:
            # No previous data - mark as new
            for code in current_components:
                comparison['variance'][code] = 100.0 if current_components[code]['total'] > 0 else 0.0
        
        return comparison
    
    def _detect_anomalies(self, current_components, comparison_data):
        """Detect anomalies and generate alerts"""
        alerts = []
        
        # Check for large variances
        if 'variance' in comparison_data:
            for code, variance in comparison_data['variance'].items():
                if abs(variance) > 20 and variance != 100:  # Ignore 100% for new components
                    severity = 'high' if abs(variance) > 50 else 'medium'
                    direction = 'increase' if variance > 0 else 'decrease'
                    alerts.append({
                        'type': 'variance',
                        'component': code,
                        'component_name': self._get_component_name(code),
                        'variance': variance,
                        'severity': severity,
                        'message': f"{self._get_component_name(code)} shows {abs(variance):.1f}% {direction} from last month"
                    })
        
        # Check for zero components that should have values
        critical_components = ['BASIC', 'NETPAY']
        for code in critical_components:
            if code in current_components and current_components[code]['total'] == 0:
                alerts.append({
                    'type': 'zero_value',
                    'component': code,
                    'component_name': self._get_component_name(code),
                    'severity': 'high',
                    'message': f"{self._get_component_name(code)} is zero - this may indicate an error"
                })
        
        return alerts
    
    def action_approve_payroll(self):
        """Final approval action"""
        self.ensure_one()
        
        if self.state != 'ready':
            raise UserError(_('Only analytics in Ready state can be approved'))
        
        # Update all related payslip runs to done status
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('state', '=', 'level2')
        ])
        
        # Filter by country if needed
        country_structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure',
            'IN': 'India Salary Structure'
        }
        structure_name = country_structure_map.get(self.country)
        
        if structure_name:
            structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
            if structure:
                payslip_runs = payslip_runs.filtered(
                    lambda r: any(p.struct_id.id == structure.id for p in r.slip_ids)
                )
        
        # Approve payslip runs
        approved_count = 0
        for run in payslip_runs:
            run.write({'state': 'done'})
            # Also approve individual payslips
            for payslip in run.slip_ids:
                if payslip.state == 'level2':
                    payslip.write({'state': 'done'})
            approved_count += 1
        
        self.write({'state': 'approved'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Payroll approved successfully. %d payslip runs have been finalized.') % approved_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_export_bank_file(self):
        """Export bank file for approved payroll"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError(_('Only approved analytics can be exported'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Export Bank File',
            'res_model': 'payroll.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_country': self.country,
                'default_date_from': self.date_from,
                'default_date_to': self.date_to,
                'default_analytics_id': self.id,
            }
        }
    
    @api.model
    def get_analytics_stats(self, country):
        """Get analytics statistics for dashboard tiles"""
        stats = {
            'pending_approvals': 0,
            'ready_exports': 0,
            'last_approval_date': None,
            'total_employees_current': 0,
            'total_payroll_current': 0
        }
        
        try:
            # Pending approvals (analytics in ready state)
            pending = self.search([
                ('country', '=', country),
                ('state', '=', 'ready')
            ])
            stats['pending_approvals'] = len(pending)
            
            # Ready for export (approved analytics)
            ready_exports = self.search([
                ('country', '=', country),
                ('state', '=', 'approved')
            ])
            stats['ready_exports'] = len(ready_exports)
            
            # Last approval date
            last_approved = self.search([
                ('country', '=', country),
                ('state', '=', 'approved')
            ], order='write_date desc', limit=1)
            
            if last_approved:
                stats['last_approval_date'] = last_approved.write_date.strftime('%Y-%m-%d')
            
            # Current month stats
            import datetime
            today = datetime.date.today()
            first_day = today.replace(day=1)
            
            current_analytics = self.search([
                ('country', '=', country),
                ('date_from', '>=', first_day),
                ('state', 'in', ['ready', 'approved'])
            ], limit=1)
            
            if current_analytics:
                stats['total_employees_current'] = current_analytics.total_employees
                stats['total_payroll_current'] = current_analytics.total_payroll
                
        except Exception as e:
            _logger.error(f"Error getting analytics stats: {e}")
        
        return stats