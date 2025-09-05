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
    _order = 'date_from desc, id desc'
    
    period_name = fields.Char(string='Period', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('TH', 'Thailand'),
        ('KH', 'Cambodia'),
        ('MY', 'Malaysia')
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
                    prev_total = comparison.get('previous_month_total', 0)
                    
                    _logger.info(f"Variance calculation for record {record.id}: current={current_total}, previous={prev_total}")
                    
                    if prev_total > 0 and current_total > 0:
                        # Both values exist - calculate actual variance
                        variance = ((current_total - prev_total) / prev_total) * 100
                        record.variance_percentage = round(variance, 2)
                        _logger.info(f"Calculated variance: {variance}%")
                    elif current_total > 0 and prev_total == 0:
                        # Current data exists but no previous data - new period
                        record.variance_percentage = 100.0
                        _logger.info("New period - variance set to 100%")
                    elif current_total == prev_total and current_total > 0:
                        # Same values - no change
                        record.variance_percentage = 0.0
                        _logger.info("Same values - variance set to 0%")
                    else:
                        # Default case - no meaningful comparison
                        record.variance_percentage = 0.0
                        _logger.info("Default case - variance set to 0%")
                else:
                    # No comparison data
                    record.variance_percentage = 0.0
                    _logger.info("No comparison data - variance set to 0%")
                        
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                _logger.warning(f"Error computing analytics for record {record.id}: {e}")
    
    def action_open_dashboard(self):
        """Open analytics dashboard for this record - regenerate with current data"""
        self.ensure_one()
        
        # Regenerate analytics with current payslip data to ensure accuracy
        _logger.info(f"Refreshing analytics data for record {self.id} - {self.period_name}")
        
        # Get current payslips for this period
        payslips = self._get_payslips_for_period(self.country, self.date_from, self.date_to)
        _logger.info(f"Found {len(payslips)} current payslips for {self.country} {self.date_from}-{self.date_to}")
        
        # Regenerate analytics data
        analytics_data = self._generate_analytics_data(payslips, self.country, self.date_from, self.date_to)
        
        # Update this record with fresh data
        self.write(analytics_data)
        
        # Force computation of stored fields
        self.invalidate_cache()
        self._compute_analytics()
        
        # Commit the transaction to ensure data is saved
        self.env.cr.commit()
        
        _logger.info(f"Updated analytics: {self.total_employees} employees, {self.total_payroll} total payroll")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Analytics Dashboard - {self.period_name}',
            'res_model': 'payroll.analytics',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard').id,
            'target': 'current',
            'context': {
                'create': False, 
                'edit': False,
                'force_refresh': True  # Signal to refresh dashboard
            }
        }
    
    @api.model
    def generate_analytics(self, country, date_from, date_to):
        """Generate analytics for given country and period"""
        period_name = f"{date_from.strftime('%B %Y')} - {country}"
        
        # Get payslips for the period
        payslips = self._get_payslips_for_period(country, date_from, date_to)
        
        # Generate analytics data
        analytics_data = self._generate_analytics_data(payslips, country, date_from, date_to)
        
        # Check if analytics already exists - find ALL duplicates, not just first one
        existing_records = self.search([
            ('country', '=', country),
            ('date_from', '=', date_from),
            ('date_to', '=', date_to)
        ])
        
        if existing_records:
            # If multiple records exist, delete all but keep the most recent one
            if len(existing_records) > 1:
                _logger.info(f"Found {len(existing_records)} duplicate analytics records for {country} {date_from}-{date_to}")
                # Sort by ID (most recent) and keep the last one
                records_to_delete = existing_records.sorted('id')[:-1]  # All except the last one
                _logger.info(f"Deleting {len(records_to_delete)} duplicate records")
                records_to_delete.unlink()
                # Keep the newest record
                existing = existing_records.sorted('id')[-1]
            else:
                existing = existing_records[0]
            
            # Update the existing record with fresh data
            existing.write(analytics_data)
            existing.invalidate_cache()  # Force refresh
            existing._compute_analytics()  # Recalculate stored fields
            _logger.info(f"Updated existing analytics record {existing.id} for {country}")
            return existing
        else:
            # Create new record
            analytics_data.update({
                'period_name': period_name,
                'country': country,
                'date_from': date_from,
                'date_to': date_to
            })
            new_record = self.create(analytics_data)
            _logger.info(f"Created new analytics record {new_record.id} for {country}")
            return new_record
    
    def _get_payslips_for_period(self, country, date_from, date_to):
        """Get payslips for the specific country and period"""
        # Map countries to salary structures (try multiple structure names)
        country_structure_map = {
            'VN': ['Vietnam Standard Payroll', 'Vietnam Full Payroll (Analytics)', 'Base for new structures'],
            'ID': ['Indonesia Standard Payroll', 'Base for new structures'],
            'IN': ['India Standard Payroll', 'Base for new structures'],
            'SG': ['Singapore Standard Payroll', 'Base for new structures'],
            'TH': ['Thailand Standard Payroll', 'Base for new structures'], 
            'KH': ['Cambodia Standard Payroll', 'Base for new structures'],
            'MY': ['Malaysia Standard Payroll', 'Base for new structures']
        }
        
        structure_names = country_structure_map.get(country, [])
        if not structure_names:
            # Try to find any structure and filter by country if possible
            structures = self.env['hr.payroll.structure'].search([])
            country_structures = structures.filtered(lambda s: country in s.name or country.lower() in s.name.lower())
            if not country_structures:
                return self.env['hr.payslip']
            structure = country_structures[0]
        else:
            # Try each structure name in order
            structure = None
            for structure_name in structure_names:
                structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
                if structure:
                    break
            
            if not structure:
                return self.env['hr.payslip']
        
        # Get payslips with more flexible search
        _logger.info(f"Searching for payslips with structure: {structure.name} (ID: {structure.id})")
        _logger.info(f"Date range: {date_from} to {date_to}")
        
        # First try with the specific structure
        payslips = self.env['hr.payslip'].search([
            ('struct_id', '=', structure.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['level2', 'done'])
        ])
        
        _logger.info(f"Found {len(payslips)} payslips with specific structure")
        
        # If no payslips found, try broader search for any payslips in level2 state
        if not payslips:
            _logger.info("No payslips found with specific structure, trying broader search...")
            all_level2_payslips = self.env['hr.payslip'].search([
                ('state', '=', 'level2'),
                ('date_from', '>=', date_from),
                ('date_to', '<=', date_to)
            ])
            _logger.info(f"Found {len(all_level2_payslips)} payslips in level2 state")
            
            if all_level2_payslips:
                _logger.info(f"Level2 payslip structures: {[p.struct_id.name for p in all_level2_payslips]}")
                # Use all level2 payslips if they exist
                payslips = all_level2_payslips
        
        # If still no payslips, try any recent payslips
        if not payslips:
            _logger.info("No level2 payslips found, trying any recent payslips...")
            recent_payslips = self.env['hr.payslip'].search([
                ('date_from', '>=', date_from),
                ('date_to', '<=', date_to)
            ], limit=10)
            _logger.info(f"Found {len(recent_payslips)} recent payslips with states: {[p.state for p in recent_payslips]}")
            payslips = recent_payslips
        
        _logger.info(f"Final result: {len(payslips)} payslips for analytics")
        if payslips:
            _logger.info(f"Payslip states: {[p.state for p in payslips]}")
            _logger.info(f"Payslip employees: {[p.employee_id.name for p in payslips[:5]]}")  # First 5 employees
        
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
        
        # Employee metrics - Calculate Total Cost to Employer (TCTE)
        # Priority order: TCTE > Sum of specific components > Sum of all positive
        tcte_lines = payslips.mapped('line_ids').filtered(lambda l: l.code == 'TCTE')
        
        if tcte_lines and sum(tcte_lines.mapped('total')) > 0:
            # Use TCTE if it exists and has value
            total_payroll = sum(tcte_lines.mapped('total'))
            _logger.info(f"Using TCTE values: {total_payroll}")
        else:
            # Calculate total cost by adding NET + Company contributions
            net_lines = payslips.mapped('line_ids').filtered(lambda l: l.code in ['NET', 'NETPAY'])
            company_lines = payslips.mapped('line_ids').filtered(lambda l: l.code in ['SI_COMP', 'HI_COMP', 'UI_COMP'])
            
            net_total = sum(net_lines.mapped('total')) if net_lines else 0
            company_total = sum(company_lines.mapped('total')) if company_lines else 0
            
            if net_total > 0:
                total_payroll = net_total + company_total
                _logger.info(f"Calculated TCTE: NET ({net_total}) + Company contributions ({company_total}) = {total_payroll}")
            else:
                # Final fallback: sum all positive components except deductions
                positive_lines = payslips.mapped('line_ids').filtered(
                    lambda l: l.total > 0 and l.code not in ['PIT', 'SI_EMP', 'HI_EMP', 'UI_EMP']
                )
                total_payroll = sum(positive_lines.mapped('total'))
                _logger.info(f"Using sum of positive components (excluding deductions): {total_payroll}")
        
        employee_metrics = {
            'total_employees': len(payslips),
            'total_payroll': total_payroll,
            'departments': {},
            'positions': {}
        }
        employee_metrics['average_salary'] = total_payroll / len(payslips) if payslips else 0
        
        # Salary components analysis - dynamically get all components from payslips
        salary_components = {}
        
        # Country-specific component codes - Updated to match actual Vietnam salary structure
        country_components = {
            'VN': ['BASIC', 'HRA', 'DA', 'Travel', 'Meal', 'Medical', 'TRANSPORT', 'GROSS', 
                   'SI_EMP', 'HI_EMP', 'UI_EMP', 'PIT', 'NET', 'SI_COMP', 'HI_COMP', 'UI_COMP',
                   'NETPAY', 'TCTE'],  # Include TCTE - Total Cost to Employer
            'ID': ['BASIC', 'MIONEFIVE', 'BPJS_JKK', 'BPJS_KES_COMP', 'LAINALL', 
                   'BPJS_JHT_COMP', 'BPJS_JP_COMP', 'BPJS_KES_EMP', 'BPJS_JHT_EMP', 
                   'BPJS_JP_EMP', 'MONPIT', 'NETPAY', 'TCTE'],
            'IN': ['BASIC', 'HRA', 'DA', 'Travel', 'Meal', 'Medical', 'PF_EMP', 'ESI_EMP', 'PT', 'TDS', 'NET', 'TCTE']
        }
        
        # Use country-specific components or fall back to all unique codes from payslips
        component_codes = country_components.get(country, [])
        if not component_codes:
            # Fall back to discovering all codes from actual payslip lines
            all_lines = payslips.mapped('line_ids')
            component_codes = list(set(all_lines.mapped('code')))
        
        # Always include actual codes from payslips to show current data
        actual_codes = list(set(payslips.mapped('line_ids').mapped('code')))
        component_codes = list(set(component_codes + actual_codes))
        
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
            # Vietnam components
            'BASIC': 'Basic Salary',
            'BASIC_VN': 'Basic Salary - Vietnam',
            'HRA': 'House Rent Allowance',
            'HOUSING_VN': 'Housing Allowance - Vietnam',
            'DA': 'Dearness Allowance', 
            'Travel': 'Travel Allowance',
            'Meal': 'Meal Allowance',
            'Medical': 'Medical Allowance',
            'TRANSPORT': 'Transport Allowance',
            'TRANSPORT_VN': 'Transport Allowance - Vietnam',
            'GROSS': 'Gross Salary',
            'SS_VN': 'Social Security - Vietnam',
            'SI_EMP': 'Social Insurance (Employee)',
            'HI_EMP': 'Health Insurance (Employee)',
            'UI_EMP': 'Unemployment Insurance (Employee)',
            'PIT': 'Personal Income Tax',
            'PIT_VN': 'Personal Income Tax - Vietnam',
            'NET': 'Net Salary',
            'NET_VN': 'Net Salary - Vietnam',
            'SI_COMP': 'Social Insurance (Company)',
            'HI_COMP': 'Health Insurance (Company)',
            'UI_COMP': 'Unemployment Insurance (Company)',
            'TCTE': 'Total Cost to Employer',
            
            # Indonesia components (for compatibility)
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
            'NETPAY': 'Net Pay',
            
            # India components (for compatibility)
            'PF_EMP': 'Provident Fund (Employee)',
            'ESI_EMP': 'Employee State Insurance',
            'PT': 'Professional Tax',
            'TDS': 'Tax Deducted at Source'
        }
        return mapping.get(code, code)
    
    def _get_historical_comparison(self, country, current_date, current_components):
        """Get historical data for comparison with improved variance calculation"""
        # Get previous month data more precisely
        prev_month_start = current_date - relativedelta(months=1)
        
        # Find the previous month analytics with more specific search
        prev_analytics = self.search([
            ('country', '=', country),
            ('date_from', '>=', prev_month_start.replace(day=1)),
            ('date_from', '<', current_date.replace(day=1))
        ], order='date_from desc', limit=1)
        
        comparison = {
            'previous_month': {},
            'variance': {},
            'trend': 'stable',
            'previous_month_total': 0
        }
        
        _logger.info(f"Looking for previous month analytics for {country}, current date: {current_date}")
        
        if prev_analytics:
            _logger.info(f"Found previous analytics: {prev_analytics.period_name} with {prev_analytics.total_payroll} total payroll")
            
            if prev_analytics.salary_components:
                try:
                    prev_components = json.loads(prev_analytics.salary_components)
                    
                    # Calculate totals properly
                    current_total_payroll = sum(comp['total'] for comp in current_components.values())
                    prev_total_payroll = sum(comp['total'] for comp in prev_components.values()) if prev_components else 0
                    
                    # Use the stored total_payroll from the previous record if available
                    if prev_analytics.total_payroll > 0:
                        prev_total_payroll = prev_analytics.total_payroll
                    
                    _logger.info(f"Current total: {current_total_payroll}, Previous total: {prev_total_payroll}")
                    
                    # Calculate individual component variances
                    for code, current in current_components.items():
                        current_total = current['total']
                        
                        if code in prev_components:
                            prev_total_comp = prev_components[code]['total']
                            
                            # Safe variance calculation per component
                            if prev_total_comp > 0:
                                variance = ((current_total - prev_total_comp) / prev_total_comp) * 100
                            elif current_total > 0:
                                variance = 100.0  # New component with value
                            else:
                                variance = 0.0  # Both zero
                            
                            comparison['previous_month'][code] = prev_components[code]
                            comparison['variance'][code] = round(variance, 2)
                        else:
                            # New component not in previous month
                            comparison['variance'][code] = 100.0 if current_total > 0 else 0.0
                    
                    # Set the correct previous month total
                    comparison['previous_month_total'] = prev_total_payroll
                    
                    # Overall variance calculation with proper totals
                    if prev_total_payroll > 0:
                        overall_variance = ((current_total_payroll - prev_total_payroll) / prev_total_payroll) * 100
                        _logger.info(f"Overall variance calculation: ({current_total_payroll} - {prev_total_payroll}) / {prev_total_payroll} * 100 = {overall_variance}%")
                        
                        if overall_variance > 5:
                            comparison['trend'] = 'increasing'
                        elif overall_variance < -5:
                            comparison['trend'] = 'decreasing'
                    else:
                        # No previous data or previous total is zero
                        overall_variance = 100.0 if current_total_payroll > 0 else 0.0
                        _logger.info(f"No previous payroll data, variance set to: {overall_variance}%")
                
                except Exception as e:
                    _logger.error(f"Error in historical comparison: {e}")
                    comparison['previous_month_total'] = 0
            else:
                _logger.warning(f"Previous analytics found but no salary_components data")
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
            'VN': 'Vietnam Standard Payroll',
            'ID': 'Indonesia Standard Payroll',
            'IN': 'India Standard Payroll',
            'SG': 'Singapore Standard Payroll',
            'TH': 'Thailand Standard Payroll',
            'KH': 'Cambodia Standard Payroll',
            'MY': 'Malaysia Standard Payroll'
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
    
    def action_refresh_analytics(self):
        """Refresh analytics data for records in list view"""
        for record in self:
            # Get current payslips for this period
            payslips = record._get_payslips_for_period(record.country, record.date_from, record.date_to)
            
            # Regenerate analytics data
            analytics_data = record._generate_analytics_data(payslips, record.country, record.date_from, record.date_to)
            
            # Update record with fresh data
            record.write(analytics_data)
            
            _logger.info(f"Refreshed analytics for {record.period_name}: {record.total_employees} employees")
        
        # Force refresh the view
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    @api.model
    def search(self, domain, offset=0, limit=None, order=None, count=False):
        """Override search to auto-refresh analytics when accessed via Approval Queue"""
        # Check if this search is from the Approval Queue (has auto_refresh_analytics context)
        if self.env.context.get('auto_refresh_analytics'):
            # First get the records with normal search
            records = super().search(domain, offset=offset, limit=limit, order=order, count=count)
            
            # If we're getting actual records (not just count)
            if not count and records:
                _logger.info(f"Auto-refreshing {len(records)} analytics records from Approval Queue")
                
                # Refresh each record with current data
                for record in records:
                    try:
                        # Get current payslips for this period
                        payslips = record._get_payslips_for_period(record.country, record.date_from, record.date_to)
                        
                        if payslips:
                            # Regenerate analytics data
                            analytics_data = record._generate_analytics_data(payslips, record.country, record.date_from, record.date_to)
                            
                            # Update record with fresh data (without triggering write hooks)
                            record.sudo().write(analytics_data)
                            
                            _logger.info(f"Auto-refreshed {record.period_name}: {record.total_employees} employees, {record.total_payroll} total payroll")
                    except Exception as e:
                        _logger.warning(f"Error auto-refreshing analytics record {record.id}: {e}")
                
                # Invalidate cache to ensure fresh data display
                records.invalidate_cache()
            
            return records
        else:
            # Normal search without auto-refresh
            return super().search(domain, offset=offset, limit=limit, order=order, count=count)
    
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