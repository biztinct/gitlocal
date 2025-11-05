# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsStatutoryContrib(models.Model):
    """Statutory Contributions Analysis - Employee & Employer contributions with compliance tracking"""

    _name = 'hr.analytics.statutory.contrib'
    _description = 'HR Analytics - Statutory Contributions'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from DESC'

    # ============================================================================
    # BASIC IDENTIFICATION FIELDS
    # ============================================================================

    period_name = fields.Char(
        string='Period Name',
        required=True,
        track_visibility='onchange',
        help='e.g., "January 2024 - Statutory Contributions"'
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

    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('TH', 'Thailand'),
        ('KH', 'Cambodia'),
        ('MY', 'Malaysia')
    ], required=True, track_visibility='onchange')

    # ============================================================================
    # CONTRIBUTION DATA - JSON STORAGE
    # ============================================================================

    contribution_summary = fields.Text(
        string='Contribution Summary (JSON)',
        help='JSON: {SI: {employee, employer, total}, HI: {...}, ...}'
    )

    employee_contrib_json = fields.Text(
        string='Employee Contributions (JSON)',
        help='JSON: {employee_id: {SI, HI, UI, CPF, SSF, NSSF, EPF, SOCSO, ...}}'
    )

    employer_contrib_json = fields.Text(
        string='Employer Contributions (JSON)',
        help='JSON: {employee_id: {SI, HI, UI, CPF, SSF, NSSF, EPF, SOCSO, ...}}'
    )

    contribution_types = fields.Text(
        string='Contribution Types (JSON)',
        help='JSON: {type: {due_date, paid_date, status}}'
    )

    pending_contributions = fields.Text(
        string='Pending Contributions (JSON)',
        help='JSON: {type: {amount, due_date, days_overdue}}'
    )

    # ============================================================================
    # GROUPING OPTIONS
    # ============================================================================

    group_by = fields.Selection([
        ('contribution_type', 'By Contribution Type'),
        ('employee', 'By Employee'),
        ('department', 'By Department'),
        ('combination', 'Combined View')
    ], default='contribution_type', required=True, track_visibility='onchange')

    # ============================================================================
    # COMPUTED & SEARCHABLE FIELDS
    # ============================================================================

    total_employee_contrib = fields.Float(
        string='Total Employee Contributions',
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

    total_contrib = fields.Float(
        string='Total Contributions',
        compute='_compute_totals',
        store=True,
        currency_field='company_currency_id'
    )

    employees_covered = fields.Integer(
        string='Employees Covered',
        compute='_compute_totals',
        store=True
    )

    # ============================================================================
    # COMPLIANCE FIELDS
    # ============================================================================

    compliance_status = fields.Selection([
        ('compliant', 'All Paid On Time'),
        ('pending', 'Some Pending'),
        ('overdue', 'Overdue Payments'),
        ('partial', 'Partial Payments')
    ], compute='_compute_compliance', store=True, track_visibility='onchange')

    compliance_details = fields.Text(
        string='Compliance Details (JSON)',
        help='Detailed compliance status per contribution type'
    )

    total_pending_amount = fields.Float(
        string='Total Pending Amount',
        compute='_compute_compliance',
        store=True,
        currency_field='company_currency_id'
    )

    overdue_amount = fields.Float(
        string='Overdue Amount',
        compute='_compute_compliance',
        store=True,
        currency_field='company_currency_id'
    )

    # ============================================================================
    # WORKFLOW FIELDS
    # ============================================================================

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('verified', 'Verified'),
        ('paid', 'Paid')
    ], default='draft', track_visibility='onchange')

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
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

    last_refresh = fields.Datetime(
        string='Last Refresh',
        readonly=True
    )

    # ============================================================================
    # COUNTRY-SPECIFIC CONTRIBUTION CODES
    # ============================================================================

    CONTRIBUTION_RULES = {
        'VN': {
            'SI': ('SI_EMP', 'SI_COMP', 'Social Insurance'),
            'HI': ('HI_EMP', 'HI_COMP', 'Health Insurance'),
            'UI': ('UI_EMP', 'UI_COMP', 'Unemployment Insurance'),
        },
        'ID': {
            'BPJS_KES': ('BPJS_KES_EMP', 'BPJS_KES_COMP', 'BPJS Kesehatan'),
            'BPJS_JHT': ('BPJS_JHT_EMP', 'BPJS_JHT_COMP', 'BPJS JHT'),
            'BPJS_JP': ('BPJS_JP_EMP', 'BPJS_JP_COMP', 'BPJS JP'),
        },
        'IN': {
            'PF': ('PF_EMP', 'PF_COMP', 'Provident Fund'),
            'ESI': ('ESI_EMP', 'ESI_COMP', 'Employee State Insurance'),
            'PT': ('PT_EMP', 'PT_COMP', 'Professional Tax'),
        },
        'SG': {
            'CPF': ('CPF_EE', 'CPF_ER', 'Central Provident Fund'),
            'SDL': ('SDL_EMP', 'SDL_ER', 'Skills Development Levy'),
        },
        'TH': {
            'SSF': ('SSF_EE', 'SSF_ER', 'Social Security Fund'),
            'PF': ('PF_EMP', 'PF_COMP', 'Provident Fund'),
        },
        'KH': {
            'NSSF': ('NSSF_EMP', 'NSSF_COMP', 'National Social Security Fund'),
        },
        'MY': {
            'EPF': ('EPF_EE', 'EPF_ER', 'Employees Provident Fund'),
            'SOCSO': ('SOCSO_EMP', 'SOCSO_COMP', 'SOCSO'),
            'EIS': ('EIS_EMP', 'EIS_ER', 'Employment Insurance System'),
        }
    }

    # ============================================================================
    # COMPUTED FIELD METHODS
    # ============================================================================

    @api.depends('employee_contrib_json', 'employer_contrib_json')
    def _compute_totals(self):
        """Compute total contributions from JSON data"""
        for record in self:
            try:
                emp_contrib = json.loads(record.employee_contrib_json or '{}')
                employer_contrib = json.loads(record.employer_contrib_json or '{}')

                # Sum all employee contributions
                record.total_employee_contrib = sum(
                    sum(v.values() if isinstance(v, dict) else [v])
                    for v in emp_contrib.values()
                )

                # Sum all employer contributions
                record.total_employer_contrib = sum(
                    sum(v.values() if isinstance(v, dict) else [v])
                    for v in employer_contrib.values()
                )

                record.total_contrib = record.total_employee_contrib + record.total_employer_contrib
                record.employees_covered = len(emp_contrib)

            except (json.JSONDecodeError, ValueError, TypeError):
                record.total_employee_contrib = 0
                record.total_employer_contrib = 0
                record.total_contrib = 0
                record.employees_covered = 0

    @api.depends('pending_contributions')
    def _compute_compliance(self):
        """Compute compliance status from pending contributions"""
        for record in self:
            try:
                pending = json.loads(record.pending_contributions or '{}')
                details = {}

                total_pending = 0
                total_overdue = 0
                all_compliant = True

                for contrib_type, data in pending.items():
                    amount = data.get('amount', 0)
                    due_date = data.get('due_date')
                    days_overdue = data.get('days_overdue', 0)

                    total_pending += amount

                    if days_overdue > 0:
                        total_overdue += amount
                        details[contrib_type] = 'overdue'
                        all_compliant = False
                    elif due_date:
                        details[contrib_type] = 'pending'
                        all_compliant = False
                    else:
                        details[contrib_type] = 'paid'

                record.compliance_details = json.dumps(details)
                record.total_pending_amount = total_pending
                record.overdue_amount = total_overdue

                # Set compliance status
                if all_compliant:
                    record.compliance_status = 'compliant'
                elif total_overdue > 0:
                    record.compliance_status = 'overdue'
                elif total_pending > 0:
                    record.compliance_status = 'pending'
                else:
                    record.compliance_status = 'compliant'

            except (json.JSONDecodeError, ValueError, TypeError):
                record.compliance_status = 'compliant'
                record.total_pending_amount = 0
                record.overdue_amount = 0
                record.compliance_details = '{}'

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def action_generate_analytics(self):
        """Generate statutory contributions analytics"""
        self.ensure_one()

        try:
            # Get payslips for the period and country
            payslips = self._get_payslips_for_period()

            if not payslips:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _('No payslips found for the selected period and country.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Generate analytics
            self._generate_analytics_data(payslips)

            self.state = 'ready'
            self.last_refresh = fields.Datetime.now()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Statutory contributions analytics generated successfully!'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.exception('Error generating statutory contributions analytics: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_verify(self):
        """Mark as verified"""
        self.ensure_one()
        self.state = 'verified'

    def action_mark_paid(self):
        """Mark all contributions as paid"""
        self.ensure_one()
        self.state = 'paid'
        self._clear_pending_contributions()

    def action_reset(self):
        """Reset to draft state"""
        self.ensure_one()
        self.state = 'draft'

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_payslips_for_period(self):
        """Get payslips for the period filtered by country"""
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', 'in', ['done', 'paid'])
        ]

        # Filter by country - match employee's country to selected country
        country_map = {
            'VN': 'Vietnam',
            'ID': 'Indonesia',
            'IN': 'India',
            'SG': 'Singapore',
            'TH': 'Thailand',
            'KH': 'Cambodia',
            'MY': 'Malaysia'
        }

        country_name = country_map.get(self.country)
        if country_name:
            domain.append(('employee_id.address_home_id.country_id.name', '=', country_name))

        return self.env['hr.payslip'].search(domain)

    def _generate_analytics_data(self, payslips):
        """Generate statutory contributions analytics"""
        contribution_summary = {}
        employee_contrib = {}
        employer_contrib = {}
        contribution_types = {}
        pending_contrib = {}

        # Get contribution rules for this country
        country_rules = self.CONTRIBUTION_RULES.get(self.country, {})

        # Initialize contribution summary
        for rule_code, (emp_code, empr_code, display_name) in country_rules.items():
            contribution_summary[rule_code] = {
                'employee': 0,
                'employer': 0,
                'total': 0,
                'display_name': display_name
            }

        # Process payslips
        for payslip in payslips:
            emp_id = payslip.employee_id.id

            # Initialize employee record
            if emp_id not in employee_contrib:
                employee_contrib[emp_id] = {
                    'employee_name': payslip.employee_id.name,
                    'total': 0
                }
            if emp_id not in employer_contrib:
                employer_contrib[emp_id] = {
                    'employee_name': payslip.employee_id.name,
                    'total': 0
                }

            # Extract contributions from payslip lines
            for line in payslip.line_ids:
                for rule_code, (emp_code, empr_code, display_name) in country_rules.items():
                    # Employee contribution
                    if line.salary_rule_id.code == emp_code:
                        contribution_summary[rule_code]['employee'] += line.total
                        employee_contrib[emp_id][emp_code] = line.total
                        employee_contrib[emp_id]['total'] += line.total

                    # Employer contribution
                    elif line.salary_rule_id.code == empr_code:
                        contribution_summary[rule_code]['employer'] += line.total
                        employer_contrib[emp_id][empr_code] = line.total
                        employer_contrib[emp_id]['total'] += line.total

            # Calculate totals
            for rule_code in contribution_summary:
                contribution_summary[rule_code]['total'] = (
                    contribution_summary[rule_code]['employee'] +
                    contribution_summary[rule_code]['employer']
                )

        # Track pending contributions (placeholder - would connect to payment tracking)
        for rule_code, data in contribution_summary.items():
            if data['total'] > 0 and self._is_contribution_pending(rule_code):
                pending_contrib[rule_code] = {
                    'amount': data['total'],
                    'due_date': (datetime.now() + timedelta(days=20)).strftime('%Y-%m-%d'),
                    'days_overdue': 0
                }

        # Store JSON data
        self.contribution_summary = json.dumps(contribution_summary)
        self.employee_contrib_json = json.dumps(employee_contrib)
        self.employer_contrib_json = json.dumps(employer_contrib)
        self.contribution_types = json.dumps(contribution_types)
        self.pending_contributions = json.dumps(pending_contrib)

    def _is_contribution_pending(self, rule_code):
        """Check if contribution is pending payment"""
        # Placeholder logic - would connect to actual payment records
        return False

    def _clear_pending_contributions(self):
        """Clear pending contributions when marked as paid"""
        self.pending_contributions = '{}'
