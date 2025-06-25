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
    
    # Computed Analytics
    total_employees = fields.Integer(string='Total Employees', compute='_compute_analytics')
    total_payroll = fields.Float(string='Total Payroll', compute='_compute_analytics')
    average_salary = fields.Float(string='Average Salary', compute='_compute_analytics')
    variance_percentage = fields.Float(string='Variance %', compute='_compute_analytics')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready for Approval'),
        ('approved', 'Approved'),
        ('exported', 'Exported')
    ], string='Status', default='draft')
    
    @api.depends('employee_metrics', 'salary_components')
    def _compute_analytics(self):
        """Compute key analytics from JSON data"""
        for record in self:
            try:
                if record.employee_metrics:
                    metrics = json.loads(record.employee_metrics)
                    record.total_employees = metrics.get('total_employees', 0)
                    record.total_payroll = metrics.get('total_payroll', 0.0)
                    record.average_salary = metrics.get('average_salary', 0.0)
                    record.variance_percentage = metrics.get('variance_percentage', 0.0)
                else:
                    record.total_employees = 0
                    record.total_payroll = 0.0
                    record.average_salary = 0.0
                    record.variance_percentage = 0.0
            except Exception as e:
                _logger.error(f"Error computing analytics: {e}")
                record.total_employees = 0
                record.total_payroll = 0.0
                record.average_salary = 0.0
                record.variance_percentage = 0.0
    
    @api.model
    def generate_analytics(self, country, date_from, date_to):
        """Generate comprehensive analytics for a period"""
        # Get payslip runs for the period
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', date_from),
            ('date_end', '<=', date_to),
            ('state', 'in', ['level1', 'level2', 'done'])
        ])
        
        # Filter by country structure
        country_structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure', 
            'IN': 'India Salary Structure'
        }
        structure_name = country_structure_map.get(country)
        
        if structure_name:
            structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
            if structure:
                payslips = payslip_runs.mapped('slip_ids').filtered(lambda p: p.struct_id.id == structure.id)
            else:
                payslips = self.env['hr.payslip']
        else:
            payslips = payslip_runs.mapped('slip_ids')
        
        # Generate analytics data
        analytics_data = self._generate_analytics_data(payslips, country, date_from, date_to)
        
        # Create or update analytics record
        period_name = f"{date_from.strftime('%B %Y')} - {country}"
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
    
    def _generate_analytics_data(self, payslips, country, date_from, date_to):
        """Generate detailed analytics data"""
        if not payslips:
            return {
                'employee_metrics': json.dumps({'total_employees': 0, 'total_payroll': 0, 'average_salary': 0}),
                'salary_components': json.dumps({}),
                'comparison_data': json.dumps({}),
                'anomaly_alerts': json.dumps([])
            }
        
        # Employee metrics
        employee_metrics = {
            'total_employees': len(payslips),
            'total_payroll': sum(p.line_ids.filtered(lambda l: l.code == 'NETPAY').mapped('total')),
            'departments': {},
            'positions': {}
        }
        employee_metrics['average_salary'] = employee_metrics['total_payroll'] / employee_metrics['total_employees'] if employee_metrics['total_employees'] > 0 else 0
        
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
        
        # Historical comparison
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
        """Get historical data for comparison"""
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
            'trend': 'stable'
        }
        
        if prev_analytics and prev_analytics.salary_components:
            try:
                prev_components = json.loads(prev_analytics.salary_components)
                
                for code, current in current_components.items():
                    if code in prev_components:
                        prev_total = prev_components[code]['total']
                        current_total = current['total']
                        
                        if prev_total > 0:
                            variance = ((current_total - prev_total) / prev_total) * 100
                        else:
                            variance = 100 if current_total > 0 else 0
                        
                        comparison['previous_month'][code] = prev_components[code]
                        comparison['variance'][code] = variance
                
                # Overall trend
                current_total = sum(comp['total'] for comp in current_components.values())
                prev_total = sum(comp['total'] for comp in prev_components.values())
                
                if prev_total > 0:
                    overall_variance = ((current_total - prev_total) / prev_total) * 100
                    if overall_variance > 5:
                        comparison['trend'] = 'increasing'
                    elif overall_variance < -5:
                        comparison['trend'] = 'decreasing'
                
            except Exception as e:
                _logger.error(f"Error in historical comparison: {e}")
        
        return comparison
    
    def _detect_anomalies(self, current_components, comparison_data):
        """Detect anomalies and generate alerts"""
        alerts = []
        
        # Check for large variances
        if 'variance' in comparison_data:
            for code, variance in comparison_data['variance'].items():
                if abs(variance) > 20:  # 20% threshold
                    severity = 'high' if abs(variance) > 50 else 'medium'
                    alerts.append({
                        'type': 'variance',
                        'component': code,
                        'component_name': self._get_component_name(code),
                        'variance': variance,
                        'severity': severity,
                        'message': f"{self._get_component_name(code)} has {variance:.1f}% variance from last month"
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
        for run in payslip_runs:
            run.write({'state': 'done'})
            # Also approve individual payslips
            for payslip in run.slip_ids:
                if payslip.state == 'level2':
                    payslip.write({'state': 'done'})
        
        self.write({'state': 'approved'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Payroll approved successfully. %d payslip runs have been finalized.') % len(payslip_runs),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_export_bank_file(self):
        """Export bank disbursement file"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError(_('Only approved payroll can be exported'))
        
        # Generate bank export file
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
                    prev = comparison['previous_month'].get(code, {}).get('total', 0)
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


class PayrollBankExportWizard(models.TransientModel):
    _name = 'payroll.bank.export.wizard'
    _description = 'Bank Export Wizard'
    
    analytics_id = fields.Many2one('payroll.analytics', string='Analytics', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('txt', 'Text File')
    ], string='Export Format', default='csv')
    include_headers = fields.Boolean(string='Include Headers', default=True)
    
    # Export file
    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)
    
    def action_generate_export(self):
        """Generate bank export file"""
        self.ensure_one()
        
        # Get payslips for the period and country
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('state', '=', 'done')
        ])
        
        # Filter by country structure
        country_structure_map = {
            'VN': 'Vietnam Salary Structure',
            'ID': 'Indonesia Salary Structure',
            'IN': 'India Salary Structure'
        }
        structure_name = country_structure_map.get(self.country)
        
        if structure_name:
            structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
            if structure:
                payslips = payslip_runs.mapped('slip_ids').filtered(lambda p: p.struct_id.id == structure.id)
            else:
                payslips = self.env['hr.payslip']
        else:
            payslips = payslip_runs.mapped('slip_ids')
        
        if not payslips:
            raise UserError(_('No payslips found for the selected period and country'))
        
        # Generate export data
        export_data = []
        for payslip in payslips:
            net_pay_line = payslip.line_ids.filtered(lambda l: l.code == 'NETPAY')
            net_pay = net_pay_line[0].total if net_pay_line else 0
            
            bank_account = payslip.employee_id.bank_account_id
            
            export_data.append({
                'Employee ID': payslip.employee_id.employee_id or '',
                'Employee Name': payslip.employee_id.name,
                'Bank Name': bank_account.bank_id.name if bank_account and bank_account.bank_id else '',
                'Account Number': bank_account.acc_number if bank_account else '',
                'Amount': net_pay,
                'Currency': payslip.company_id.currency_id.name,
                'Reference': payslip.number,
                'Date': payslip.date_to.strftime('%Y-%m-%d')
            })
        
        # Create file based on format
        if self.export_format == 'csv':
            file_content, filename = self._create_csv_file(export_data)
        elif self.export_format == 'excel':
            file_content, filename = self._create_excel_file(export_data)
        else:
            file_content, filename = self._create_txt_file(export_data)
        
        # Update wizard with file
        self.write({
            'export_file': base64.b64encode(file_content),
            'export_filename': filename
        })
        
        # Update analytics state
        self.analytics_id.write({'state': 'exported'})
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }
    
    def _create_csv_file(self, data):
        """Create CSV file"""
        output = io.StringIO()
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            
            if self.include_headers:
                writer.writeheader()
            
            for row in data:
                writer.writerow(row)
        
        filename = f"bank_export_{self.country}_{self.date_from.strftime('%Y%m%d')}.csv"
        return output.getvalue().encode('utf-8'), filename
    
    def _create_excel_file(self, data):
        """Create Excel file (simplified - would need xlsxwriter for full implementation)"""
        # For now, return CSV with .xlsx extension
        # In production, implement proper Excel generation
        content, _ = self._create_csv_file(data)
        filename = f"bank_export_{self.country}_{self.date_from.strftime('%Y%m%d')}.xlsx"
        return content, filename
    
    def _create_txt_file(self, data):
        """Create text file"""
        lines = []
        if self.include_headers and data:
            headers = list(data[0].keys())
            lines.append('\t'.join(headers))
        
        for row in data:
            lines.append('\t'.join(str(v) for v in row.values()))
        
        filename = f"bank_export_{self.country}_{self.date_from.strftime('%Y%m%d')}.txt"
        return '\n'.join(lines).encode('utf-8'), filename