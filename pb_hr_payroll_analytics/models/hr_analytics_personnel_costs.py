# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsPersonnelCosts(models.Model):
    """Personnel Cost Analysis - Multi-dimensional by Department, Job Title, Designation, Cost Center"""

    _name = 'hr.analytics.personnel.costs'
    _description = 'HR Analytics - Personnel Costs for Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from DESC'

    # ============================================================================
    # BASIC IDENTIFICATION FIELDS
    # ============================================================================

    period_name = fields.Char(
        string='Period Name',
        required=True,
        track_visibility='onchange',
        help='e.g., "January 2024 - Personnel Costs"'
    )

    date_from = fields.Date(
        string='Date From',
        required=True,
        track_visibility='onchange'
    )

    date_to = fields.Date(
        string='Date To',
        required=True,
        track_visibility='onchange'
    )

    # ============================================================================
    # COUNTRY FILTER FIELDS
    # ============================================================================

    country_ids = fields.Many2many(
        'res.country',
        string='Available Countries',
        help='Countries included in this analysis'
    )

    selected_country = fields.Selection(
        string='Selected Country',
        selection=lambda self: self._get_country_selection(),
        track_visibility='onchange'
    )

    # ============================================================================
    # ANALYSIS DIMENSION FIELDS
    # ============================================================================

    analysis_by = fields.Selection([
        ('department', 'By Department'),
        ('job_title', 'By Job Title'),
        ('designation', 'By Designation'),
        ('cost_center', 'By Cost Center'),
        ('combination', 'Combined View (All Dimensions)')
    ], default='department', required=True, track_visibility='onchange')

    # ============================================================================
    # JSON STORAGE FIELDS - Cost Breakdown
    # ============================================================================

    direct_salaries_json = fields.Text(
        string='Direct Salaries (JSON)',
        help='JSON: {dimension: {basic: amount, allowances: amount, ...}}'
    )

    employer_contributions_json = fields.Text(
        string='Employer Contributions (JSON)',
        help='JSON: {dimension: {SI: amount, HI: amount, CPF: amount, ...}}'
    )

    benefits_json = fields.Text(
        string='Benefits (JSON)',
        help='JSON: {dimension: {health_insurance: amount, housing: amount, ...}}'
    )

    training_costs_json = fields.Text(
        string='Training Costs (JSON)',
        help='JSON: {dimension: {amount: total, employees: count}}'
    )

    recruitment_costs_json = fields.Text(
        string='Recruitment Costs (JSON)',
        help='JSON: {dimension: {amount: total, new_hires: count}}'
    )

    total_cost_json = fields.Text(
        string='Total Cost of Employment (JSON)',
        help='JSON: {dimension: {total: amount, per_employee: amount}}'
    )

    # ============================================================================
    # COMPUTED & SEARCHABLE FIELDS
    # ============================================================================

    total_direct_salaries = fields.Float(
        string='Total Direct Salaries',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    total_employer_contrib = fields.Float(
        string='Total Employer Contributions',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    total_benefits = fields.Float(
        string='Total Benefits',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    total_training_costs = fields.Float(
        string='Total Training Costs',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    total_recruitment_costs = fields.Float(
        string='Total Recruitment Costs',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    total_personnel_cost = fields.Float(
        string='Total Personnel Cost',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    average_cost_per_employee = fields.Float(
        string='Average Cost Per Employee',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    total_employees = fields.Integer(
        string='Total Employees',
        compute='_compute_totals',
        store=True
    )

    # ============================================================================
    # COMPARISON & VARIANCE FIELDS
    # ============================================================================

    previous_period_data = fields.Text(
        string='Previous Period Data (JSON)',
        help='Historical data for comparison'
    )

    variance_by_dimension = fields.Text(
        string='Variance by Dimension (JSON)',
        help='Variance % by dept/title/designation'
    )

    variance_percentage = fields.Float(
        string='Overall Variance %',
        compute='_compute_variance',
        store=True
    )

    largest_cost_drivers = fields.Text(
        string='Largest Cost Drivers (JSON)',
        help='Top 5 cost items and their impact'
    )

    # ============================================================================
    # WORKFLOW FIELDS
    # ============================================================================

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('approved', 'Approved'),
        ('exported', 'Exported')
    ], default='draft', track_visibility='onchange')

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
    )

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )

    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )

    # ============================================================================
    # CACHE & PERFORMANCE FIELDS
    # ============================================================================

    last_refresh = fields.Datetime(
        string='Last Refresh',
        readonly=True
    )

    cache_valid = fields.Boolean(
        string='Cache Valid',
        default=True
    )

    # ============================================================================
    # HELPER FIELDS
    # ============================================================================

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    # ============================================================================
    # COMPUTED FIELD METHODS
    # ============================================================================

    @api.depends('direct_salaries_json', 'employer_contributions_json',
                 'benefits_json', 'training_costs_json', 'recruitment_costs_json')
    def _compute_totals(self):
        """Compute total amounts from JSON data"""
        for record in self:
            try:
                salaries_data = json.loads(record.direct_salaries_json or '{}')
                contrib_data = json.loads(record.employer_contributions_json or '{}')
                benefits_data = json.loads(record.benefits_json or '{}')
                training_data = json.loads(record.training_costs_json or '{}')
                recruitment_data = json.loads(record.recruitment_costs_json or '{}')
                total_cost_data = json.loads(record.total_cost_json or '{}')

                # Extract totals from nested JSON
                def extract_total(data_dict):
                    if isinstance(data_dict, dict):
                        total = 0
                        for key, value in data_dict.items():
                            if isinstance(value, dict):
                                total += value.get('total', 0) or extract_total(value)
                            elif isinstance(value, (int, float)):
                                total += value
                        return total
                    return 0

                record.total_direct_salaries = extract_total(salaries_data)
                record.total_employer_contrib = extract_total(contrib_data)
                record.total_benefits = extract_total(benefits_data)
                record.total_training_costs = extract_total(training_data)
                record.total_recruitment_costs = extract_total(recruitment_data)

                # Total personnel cost = salary + contributions + benefits + training + recruitment
                record.total_personnel_cost = (
                    record.total_direct_salaries +
                    record.total_employer_contrib +
                    record.total_benefits +
                    record.total_training_costs +
                    record.total_recruitment_costs
                )

                # Average cost per employee
                total_cost_all = extract_total(total_cost_data)
                total_emps = 0
                for key, value in total_cost_data.items():
                    if isinstance(value, dict):
                        total_emps += value.get('employees', 0) or 1

                record.total_employees = total_emps if total_emps > 0 else 0
                record.average_cost_per_employee = (
                    record.total_personnel_cost / total_emps
                    if total_emps > 0
                    else 0
                )

            except (json.JSONDecodeError, ValueError, TypeError):
                record.total_direct_salaries = 0
                record.total_employer_contrib = 0
                record.total_benefits = 0
                record.total_training_costs = 0
                record.total_recruitment_costs = 0
                record.total_personnel_cost = 0
                record.average_cost_per_employee = 0
                record.total_employees = 0

    @api.depends('total_personnel_cost', 'previous_period_data')
    def _compute_variance(self):
        """Compute variance percentage from previous period"""
        for record in self:
            try:
                if record.previous_period_data:
                    prev_data = json.loads(record.previous_period_data)
                    prev_total = prev_data.get('total_personnel_cost', 0)

                    if prev_total > 0:
                        variance = ((record.total_personnel_cost - prev_total) / prev_total) * 100
                        record.variance_percentage = variance
                    else:
                        record.variance_percentage = 0
                else:
                    record.variance_percentage = 0
            except (json.JSONDecodeError, ValueError, TypeError):
                record.variance_percentage = 0

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def action_generate_analytics(self):
        """Generate personnel cost analytics"""
        self.ensure_one()

        try:
            # Get payslips for the period
            payslips = self._get_payslips_for_period()

            if not payslips:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _('No payslips found for the selected period.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Generate analytics data
            self._generate_analytics_data(payslips)

            # Set state
            self.state = 'ready'
            self.last_refresh = fields.Datetime.now()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Personnel costs analytics generated successfully!'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.exception('Error generating personnel cost analytics: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Error generating analytics: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_approve(self):
        """Approve the analysis"""
        self.ensure_one()
        self.state = 'approved'
        self.approved_by = self.env.user
        self.approval_date = fields.Datetime.now()

    def action_reset(self):
        """Reset to draft state"""
        self.ensure_one()
        self.state = 'draft'
        self.approved_by = None
        self.approval_date = None

    def action_open_dashboard(self):
        """Open dashboard view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.analytics.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_analytics.view_hr_analytics_dashboard').id,
            'target': 'current',
        }

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_country_selection(self):
        """Get available countries for selection"""
        countries = self.env['res.country'].search([
            ('code', 'in', ['VN', 'ID', 'IN', 'SG', 'TH', 'KH', 'MY'])
        ])
        return [(c.code, c.name) for c in countries]

    def _get_payslips_for_period(self):
        """Get payslips for the analysis period"""
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', 'in', ['done', 'paid'])
        ]

        if self.selected_country:
            # Filter by country if selected
            domain.append(('employee_id.address_home_id.country_id.code', '=', self.selected_country))

        return self.env['hr.payslip'].search(domain)

    def _generate_analytics_data(self, payslips):
        """Generate analytics data from payslips"""
        # Initialize data structures
        salary_by_dim = {}
        contrib_by_dim = {}
        benefits_by_dim = {}
        training_by_dim = {}
        recruitment_by_dim = {}
        total_cost_by_dim = {}

        # Salary and contribution rule codes by country
        salary_rules = {
            'VN': ['BASIC_VN', 'BASIC', 'HRA', 'DA', 'TRANSPORT', 'MEAL', 'MEDICAL'],
            'ID': ['BASIC', 'BASIC_ID', 'MIONEFIVE'],
            'IN': ['BASIC', 'HRA', 'DA'],
            'SG': ['BASIC', 'HRA'],
            'TH': ['BASIC', 'HRA', 'DA'],
            'KH': ['BASIC'],
            'MY': ['BASIC']
        }

        contrib_rules = {
            'VN': ['SI_EMP', 'SI_COMP', 'HI_EMP', 'HI_COMP', 'UI_EMP', 'UI_COMP'],
            'ID': ['BPJS_KES_EMP', 'BPJS_JHT_EMP', 'BPJS_KES_COMP', 'BPJS_JHT_COMP'],
            'IN': ['PF_EMP', 'ESI_EMP', 'PF_COMP', 'ESI_COMP'],
            'SG': ['CPF_EE', 'CPF_ER', 'SDL_EMP'],
            'TH': ['SSF_EE', 'SSF_ER', 'PF_EMP', 'PF_COMP'],
            'KH': ['NSSF_EMP', 'NSSF_COMP'],
            'MY': ['EPF_EE', 'EPF_ER', 'SOCSO_EMP', 'SOCSO_COMP']
        }

        # Process each payslip
        for payslip in payslips:
            # Determine dimension (department, job_title, designation, cost_center)
            if self.analysis_by == 'department':
                dim_key = payslip.employee_id.department_id.name or 'Unassigned'
            elif self.analysis_by == 'job_title':
                dim_key = payslip.employee_id.job_id.name or 'Unassigned'
            elif self.analysis_by == 'designation':
                dim_key = payslip.employee_id.name or 'Unassigned'
            elif self.analysis_by == 'cost_center':
                dim_key = payslip.employee_id.department_id.name or 'Unassigned'
            else:  # combination
                dim_key = f"{payslip.employee_id.department_id.name or 'Unassigned'} - {payslip.employee_id.job_id.name or 'N/A'}"

            # Initialize dimension in dictionaries
            if dim_key not in salary_by_dim:
                salary_by_dim[dim_key] = {'total': 0, 'basic': 0, 'allowances': 0}
                contrib_by_dim[dim_key] = {'total': 0}
                benefits_by_dim[dim_key] = {'total': 0}
                training_by_dim[dim_key] = {'total': 0, 'employees': 0}
                recruitment_by_dim[dim_key] = {'total': 0, 'new_hires': 0}
                total_cost_by_dim[dim_key] = {'total': 0, 'employees': 0, 'cost_per_emp': 0}

            # Extract salary components from payslip lines
            for line in payslip.line_ids:
                if line.salary_rule_id.code in (salary_rules.get(self.selected_country, []) + ['BASIC', 'HRA', 'DA']):
                    salary_by_dim[dim_key]['total'] += line.total
                    if line.salary_rule_id.code == 'BASIC' or 'BASIC' in line.salary_rule_id.code:
                        salary_by_dim[dim_key]['basic'] += line.total
                    else:
                        salary_by_dim[dim_key]['allowances'] += line.total

                # Extract contributions
                if line.salary_rule_id.code in contrib_rules.get(self.selected_country, []):
                    if dim_key not in contrib_by_dim:
                        contrib_by_dim[dim_key] = {'total': 0}
                    contrib_by_dim[dim_key]['total'] += line.total
                    contrib_by_dim[dim_key][line.salary_rule_id.code] = line.total

            # Aggregate
            total_cost_by_dim[dim_key]['total'] += salary_by_dim[dim_key]['total'] + contrib_by_dim[dim_key].get('total', 0)
            total_cost_by_dim[dim_key]['employees'] += 1
            total_cost_by_dim[dim_key]['cost_per_emp'] = (
                total_cost_by_dim[dim_key]['total'] / total_cost_by_dim[dim_key]['employees']
            )

        # Store JSON data
        self.direct_salaries_json = json.dumps(salary_by_dim)
        self.employer_contributions_json = json.dumps(contrib_by_dim)
        self.benefits_json = json.dumps(benefits_by_dim)
        self.training_costs_json = json.dumps(training_by_dim)
        self.recruitment_costs_json = json.dumps(recruitment_by_dim)
        self.total_cost_json = json.dumps(total_cost_by_dim)

        # Calculate variance from previous period if available
        self._calculate_variance()

        # Identify largest cost drivers
        self._identify_cost_drivers()

    def _calculate_variance(self):
        """Calculate variance from previous period"""
        # Find previous period record
        previous = self.search([
            ('selected_country', '=', self.selected_country),
            ('analysis_by', '=', self.analysis_by),
            ('date_to', '<', self.date_from),
            ('state', '!=', 'draft')
        ], order='date_to DESC', limit=1)

        if previous:
            self.previous_period_data = json.dumps({
                'total_personnel_cost': previous.total_personnel_cost,
                'by_dimension': previous.total_cost_json
            })

            # Calculate variance by dimension
            try:
                current_costs = json.loads(self.total_cost_json or '{}')
                previous_costs = json.loads(previous.total_cost_json or '{}')

                variance_data = {}
                for dim in current_costs:
                    if dim in previous_costs:
                        curr_total = current_costs[dim].get('total', 0)
                        prev_total = previous_costs[dim].get('total', 0)

                        if prev_total > 0:
                            var_pct = ((curr_total - prev_total) / prev_total) * 100
                            variance_data[dim] = {
                                'variance_pct': var_pct,
                                'variance_amount': curr_total - prev_total
                            }

                self.variance_by_dimension = json.dumps(variance_data)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    def _identify_cost_drivers(self):
        """Identify top 5 cost drivers"""
        try:
            cost_data = json.loads(self.total_cost_json or '{}')

            # Sort by total cost
            sorted_dims = sorted(
                cost_data.items(),
                key=lambda x: x[1].get('total', 0),
                reverse=True
            )[:5]

            drivers = {}
            for dim, data in sorted_dims:
                drivers[dim] = {
                    'total': data.get('total', 0),
                    'employees': data.get('employees', 0),
                    'cost_per_emp': data.get('cost_per_emp', 0)
                }

            self.largest_cost_drivers = json.dumps(drivers)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
