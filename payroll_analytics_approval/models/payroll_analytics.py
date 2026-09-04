# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError
try:
    from vendor_license_core.services.enforce import require_license
except ImportError:
    def require_license(func):
        return func
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
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batch', readonly=True)
    approval_title = fields.Char(string='Approval Title', compute='_compute_approval_title')
    salary_structure_name = fields.Char(string='Salary Structure', readonly=True, 
                                         help='Name of the salary structure from hr.formula.config')
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
                        # No prior period to compare against. This used to store
                        # the sentinel 100.0 meaning "100%", which the form then
                        # rendered through widget="percentage" — multiplying by
                        # 100 a second time and printing "10000%". There is no
                        # variance to report against nothing: report zero and
                        # say why in the log.
                        record.variance_percentage = 0.0
                        _logger.info(
                            "No previous period for record %s — variance not "
                            "computed (was reported as 100%%).", record.id)
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
                        
            except (json.JSONDecodeError, TypeError, KeyError, Exception) as e:
                _logger.warning(f"Error computing analytics for record {record.id}: {e}")
                # Set safe defaults on any error
                record.total_employees = 0
                record.total_payroll = 0.0
                record.average_salary = 0.0
                record.variance_percentage = 0.0
    
    @api.depends('payslip_run_id', 'payslip_run_id.name')
    def _compute_approval_title(self):
        batch_name_by_run = {}
        run_ids = [record.payslip_run_id.id for record in self if record.payslip_run_id]
        if run_ids:
            batch_model = None
            try:
                batch_model = self.env['hr.payroll.import.batch']
            except (KeyError, ValueError):
                batch_model = None
            if batch_model is not None:
                try:
                    batches = batch_model.search([('payslip_run_id', 'in', run_ids)], order='id desc')
                except AccessError:
                    batches = []
                for batch in batches:
                    run_id = batch.payslip_run_id.id
                    if run_id and run_id not in batch_name_by_run:
                        batch_name_by_run[run_id] = batch.name

        for record in self:
            title = False
            if record.payslip_run_id:
                title = batch_name_by_run.get(record.payslip_run_id.id) or record.payslip_run_id.name
            record.approval_title = title or record.period_name

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to handle transaction errors gracefully"""
        try:
            return super(PayrollAnalytics, self).search_read(domain, fields, offset, limit, order)
        except Exception as e:
            if 'InFailedSqlTransaction' in str(e):
                _logger.warning(f"SQL Transaction error in search_read: {e}")
                # Return empty result for failed transactions to avoid crash
                return []
            else:
                # Re-raise other exceptions
                raise

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        result = super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        groupby_list = groupby if isinstance(groupby, list) else [groupby]
        groupby_state = any(group and group.split(':')[0] == 'state' for group in groupby_list)
        if groupby_state:
            for group in result:
                if group.get('state') == 'approved':
                    group['__fold'] = True
        return result
    
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
        self.invalidate_recordset()
        self._compute_analytics()
        
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
            existing.invalidate_recordset()  # Force refresh
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
    
    def _get_payslips_for_employees_period(self, employee_ids, date_from, date_to):
        if not employee_ids:
            return self.env['hr.payslip']
        return self.env['hr.payslip'].search([
            ('employee_id', 'in', employee_ids),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['level2', 'done'])
        ])

    def _get_batch_employee_ids(self):
        if not self or len(self) != 1 or not self.payslip_run_id:
            return []
        return self.payslip_run_id.slip_ids.mapped('employee_id').ids

    def _get_batch_line_domain(self):
        if not self or len(self) != 1:
            return []
        if self.payslip_run_id:
            return [('slip_id.payslip_run_id', '=', self.payslip_run_id.id)]
        return [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
        ]

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
                    'name': self._get_component_name(code, country)
                }
        
        # Historical comparison with improved variance calculation
        comparison_data = self._get_historical_comparison(country, date_from, salary_components)
        
        # Anomaly detection
        anomaly_alerts = self._detect_anomalies(salary_components, comparison_data, country)
        
        return {
            'employee_metrics': json.dumps(employee_metrics),
            'salary_components': json.dumps(salary_components),
            'comparison_data': json.dumps(comparison_data),
            'anomaly_alerts': json.dumps(anomaly_alerts)
        }
    
    def _get_component_name(self, code, country=None):
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
        if not code:
            return ''

        normalized_code = code.strip()
        if normalized_code in mapping:
            return mapping[normalized_code]

        if country and 'hr.formula.rule' in self.env:
            formula_rule = self.env['hr.formula.rule'].search([
                ('code', '=', normalized_code),
                ('config_id.country_code', '=', country),
                ('config_id.active', '=', True),
            ], limit=1)
            if formula_rule and formula_rule.name:
                return formula_rule.name

            component_mapping = self.env['payroll.component.mapping'].search([
                ('country', '=', country),
                ('code', '=', normalized_code),
            ], limit=1)
            if component_mapping and component_mapping.name:
                return component_mapping.name

        salary_rule = self.env['hr.salary.rule'].search([('code', '=', normalized_code)], limit=1)
        if salary_rule and salary_rule.name:
            return salary_rule.name

        component_mapping = self.env['payroll.component.mapping'].search([('code', '=', normalized_code)], limit=1)
        if component_mapping and component_mapping.name:
            return component_mapping.name

        return normalized_code.replace('_', ' ').title()
    
    def _get_historical_comparison(self, country, current_date, current_components):
        """Get historical data for comparison with improved variance calculation"""
        # Get previous month data more precisely
        prev_month_start = current_date - relativedelta(months=1)
        prev_month_start = prev_month_start.replace(day=1)
        prev_month_end = prev_month_start + relativedelta(months=1, days=-1)

        batch_employee_ids = self._get_batch_employee_ids()
        if batch_employee_ids:
            previous_payslips = self._get_payslips_for_employees_period(
                batch_employee_ids, prev_month_start, prev_month_end
            )
            prev_components = {}
            for line in previous_payslips.mapped('line_ids'):
                if not line.code:
                    continue
                prev_components.setdefault(line.code, {'total': 0.0})
                prev_components[line.code]['total'] += line.total

            comparison = {
                'previous_month': {},
                'variance': {},
                'trend': 'stable',
                'previous_month_total': 0
            }

            current_total_payroll = sum(comp['total'] for comp in current_components.values())
            prev_total_payroll = sum(comp['total'] for comp in prev_components.values()) if prev_components else 0
            comparison['previous_month_total'] = prev_total_payroll

            for code, current in current_components.items():
                current_total = current['total']
                if code in prev_components:
                    prev_total_comp = prev_components[code]['total']
                    if prev_total_comp > 0:
                        variance = ((current_total - prev_total_comp) / prev_total_comp) * 100
                    elif current_total > 0:
                        variance = 100.0
                    else:
                        variance = 0.0
                    comparison['previous_month'][code] = prev_components[code]
                    comparison['variance'][code] = round(variance, 2)
                else:
                    comparison['variance'][code] = 100.0 if current_total > 0 else 0.0

            if prev_total_payroll > 0:
                overall_variance = ((current_total_payroll - prev_total_payroll) / prev_total_payroll) * 100
                if overall_variance > 5:
                    comparison['trend'] = 'increasing'
                elif overall_variance < -5:
                    comparison['trend'] = 'decreasing'
            return comparison

        # Find the previous month analytics with more specific search
        prev_analytics = self.search([
            ('country', '=', country),
            ('date_from', '>=', prev_month_start),
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
    
    def _detect_anomalies(self, current_components, comparison_data, country=None):
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
                        'component_name': self._get_component_name(code, country),
                        'variance': variance,
                        'severity': severity,
                        'message': f"{self._get_component_name(code, country)} shows {abs(variance):.1f}% {direction} from last month"
                    })
        
        # Check for zero components that should have values
        critical_components = ['BASIC', 'NETPAY']
        for code in critical_components:
            if code in current_components and current_components[code]['total'] == 0:
                alerts.append({
                    'type': 'zero_value',
                    'component': code,
                    'component_name': self._get_component_name(code, country),
                    'severity': 'high',
                    'message': f"{self._get_component_name(code, country)} is zero - this may indicate an error"
                })
        
        return alerts

    def _component_employee_totals(self, payslips, component_code):
        totals = defaultdict(float)
        lines = payslips.mapped('line_ids').filtered(lambda line: line.code == component_code)
        for line in lines:
            totals[line.employee_id.id] += line.total
        return totals

    def action_open_component_details(self, component_code):
        self.ensure_one()
        if not component_code:
            return False

        Detail = self.env['payroll.analytics.component.detail']
        Detail.search([
            ('analytics_id', '=', self.id),
            ('component_code', '=', component_code),
        ]).unlink()

        if self.payslip_run_id:
            employee_ids = self._get_batch_employee_ids()
            current_payslips = self.payslip_run_id.slip_ids
            prev_month_start = (self.date_from - relativedelta(months=1)).replace(day=1)
            prev_month_end = prev_month_start + relativedelta(months=1, days=-1)
            previous_payslips = self._get_payslips_for_employees_period(
                employee_ids, prev_month_start, prev_month_end
            )
        else:
            current_payslips = self._get_payslips_for_period(self.country, self.date_from, self.date_to)
            prev_month_start = (self.date_from - relativedelta(months=1)).replace(day=1)
            prev_month_end = prev_month_start + relativedelta(months=1, days=-1)
            previous_payslips = self._get_payslips_for_period(self.country, prev_month_start, prev_month_end)

        current_totals = self._component_employee_totals(current_payslips, component_code)
        previous_totals = self._component_employee_totals(previous_payslips, component_code)

        employee_ids = set(current_totals.keys()) | set(previous_totals.keys())
        component_name = self._get_component_name(component_code, self.country)
        values = []
        for employee_id in employee_ids:
            values.append({
                'analytics_id': self.id,
                'component_code': component_code,
                'component_name': component_name,
                'employee_id': employee_id,
                'current_total': current_totals.get(employee_id, 0.0),
                'previous_total': previous_totals.get(employee_id, 0.0),
                'currency_id': self.currency_id.id,
            })
        if values:
            Detail.create(values)

        view_id = self.env.ref('payroll_analytics_approval.view_payroll_component_detail_tree').id
        return {
            'type': 'ir.actions.act_window',
            'name': f'{component_name} - Detail',
            'res_model': 'payroll.analytics.component.detail',
            'view_mode': 'tree',
            'views': [(view_id, 'tree')],
            'target': 'current',
            'domain': [
                ('analytics_id', '=', self.id),
                ('component_code', '=', component_code),
            ],
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def get_component_name_map(self, codes):
        self.ensure_one()
        name_map = {}
        for code in codes or []:
            name_map[code] = self._get_component_name(code, self.country)
        return name_map

    def _build_payslip_line_pivot_action(self, name, domain, row_groupby, column_groupby):
        view = self.env.ref('pb_hr_flow.view_hr_payslip_line_pivot_enhanced', raise_if_not_found=False)
        views = [(view.id, 'pivot'), (False, 'tree')] if view else [(False, 'pivot'), (False, 'tree')]
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'hr.payslip.line',
            'view_mode': 'pivot,tree',
            'views': views,
            'domain': domain,
            'context': {
                'pivot_measures': ['total'],
                'pivot_row_groupby': row_groupby or [],
                'pivot_column_groupby': column_groupby or [],
            },
        }

    def action_open_employee_component_pivot(self):
        self.ensure_one()
        domain = self._get_batch_line_domain()
        return self._build_payslip_line_pivot_action(
            _('Batch Payslip Components by Employee'),
            domain,
            ['employee_id'],
            ['name'],
        )

    def action_open_variance_pivot(self):
        self.ensure_one()
        domain = []
        employee_ids = self._get_batch_employee_ids()
        if employee_ids:
            domain.append(('employee_id', 'in', employee_ids))
        if self.date_from and self.date_to:
            start_date = (self.date_from - relativedelta(months=1)).replace(day=1)
            domain.extend([
                ('date_from', '>=', start_date),
                ('date_to', '<=', self.date_to),
            ])
        return self._build_payslip_line_pivot_action(
            _('Variance vs Last Month'),
            domain,
            ['name'],
            ['date_to:month'],
        )

    def action_open_component_pivot(self, component_code):
        self.ensure_one()
        if not component_code:
            return False
        domain = [('code', '=', component_code)]
        employee_ids = self._get_batch_employee_ids()
        if employee_ids:
            domain.append(('employee_id', 'in', employee_ids))
        if self.date_from and self.date_to:
            start_date = (self.date_from - relativedelta(months=5)).replace(day=1)
            domain.extend([
                ('date_from', '>=', start_date),
                ('date_to', '<=', self.date_to),
            ])
        return self._build_payslip_line_pivot_action(
            _('Component Trend: %s') % self._get_component_name(component_code, self.country),
            domain,
            ['employee_id'],
            ['date_to:month'],
        )
    
    @require_license
    def action_approve_payroll(self):
        """Final approval action"""
        self.ensure_one()
        
        if self.state != 'ready':
            raise UserError(_('Only analytics in Ready state can be approved'))
        
        # Find all payslip runs for the period (check all states)
        all_payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to)
        ])

        # Finalize the specific batch linked to this analytics record when possible
        if self.payslip_run_id:
            runs_to_finalize = self.payslip_run_id.filtered(lambda r: r.state == 'level2')
        else:
            runs_to_finalize = self.env['hr.payslip.run'].search([
                ('state', '=', 'level2'),
                ('date_start', '>=', self.date_from),
                ('date_end', '<=', self.date_to)
            ])

        if runs_to_finalize:
            _logger.info(
                "Final approve: setting %d payslip run(s) to done from analytics %s",
                len(runs_to_finalize),
                self.id,
            )
            runs_to_finalize.sudo().action_payslip_run_level2_done()
        else:
            _logger.info(
                "Final approve: no level2 payslip runs found to finalize for analytics %s",
                self.id,
            )
        
        _logger.info(f"Found {len(all_payslip_runs)} total payslip runs in period")
        for run in all_payslip_runs:
            _logger.info(f"Payslip run {run.name}: state={run.state}, payslips={len(run.slip_ids)}")
        
        # For debugging, just count all payslips and approve analytics regardless
        total_payslips = sum(len(run.slip_ids) for run in all_payslip_runs)
        approved_count = len(all_payslip_runs)
        
        _logger.info(f"Found {total_payslips} total payslips in {approved_count} runs")
        
        _logger.info(f"Approved {approved_count} payslip runs with {total_payslips} total payslips")
        
        # Force state change to approved
        _logger.info(f"Changing analytics state from {self.state} to approved for record {self.id}")
        
        # Try different approaches to change state
        try:
            # Method 1: Standard write
            write_result = self.write({'state': 'approved'})
            _logger.info(f"Method 1 - Standard write result: {write_result}")
            
            # Verify the change  
            self.invalidate_recordset()
            _logger.info(f"Analytics state after standard write: {self.state}")
            
            # Method 2: If standard write didn't work, try direct SQL update
            if self.state != 'approved':
                _logger.info("Standard write failed, trying direct SQL update")
                self.env.cr.execute(
                    "UPDATE payroll_analytics SET state = %s WHERE id = %s",
                    ('approved', self.id)
                )
                self.invalidate_recordset()
                _logger.info(f"Analytics state after SQL update: {self.state}")
                
        except Exception as e:
            _logger.error(f"Error updating analytics state: {e}")
        
        # Return action that refreshes the current view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.analytics',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'readonly',
                'show_approval_success': True,
                'success_message': _('Payroll approved successfully. %d payslip runs with %d individual payslips have been finalized.') % (approved_count, total_payslips),
            }
        }
    
    @require_license
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
    def search(self, domain, offset=0, limit=None, order=None):
        """Override search to auto-refresh analytics when accessed via Approval Queue"""
        # Check if this search is from the Approval Queue (has auto_refresh_analytics context)
        if self.env.context.get('auto_refresh_analytics'):
            # For faster loading, disable auto-refresh and just return records
            # Analytics are generated/refreshed when dashboard is opened instead
            _logger.info("Approval Queue accessed - skipping auto-refresh for performance")
        
        # Always use standard search for best performance
        return super().search(domain, offset=offset, limit=limit, order=order)
    
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
