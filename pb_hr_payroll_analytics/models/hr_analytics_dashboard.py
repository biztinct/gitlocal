# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsDashboard(models.Model):
    """Main Analytics Dashboard - Integration point for all analytics"""

    _name = 'hr.analytics.dashboard'
    _description = 'HR Analytics Dashboard'
    _order = 'id DESC'

    # ============================================================================
    # DASHBOARD STATE
    # ============================================================================

    name = fields.Char(
        string='Dashboard Name',
        default='HR Analytics Dashboard',
        readonly=True
    )

    active_tab = fields.Selection([
        ('personnel_costs', 'Personnel Costs'),
        ('cross_country', 'Cross Country Analytics'),
        ('statutory_contrib', 'Statutory Contributions'),
        ('headcount', 'Headcount Analysis'),
        ('dependents', 'Dependents & Benefits'),
        ('budget_variance', 'Budget Variance'),
        ('annual_costs', 'Annual HR Costs')
    ], default='personnel_costs', string='Active Tab')

    # ============================================================================
    # GLOBAL FILTERS
    # ============================================================================

    selected_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('TH', 'Thailand'),
        ('KH', 'Cambodia'),
        ('MY', 'Malaysia'),
        ('ALL', 'All Countries (Global View)')
    ], default='ALL', string='Country Filter')

    country_filter_ids = fields.Many2many(
        'res.country',
        string='Available Countries',
        compute='_compute_available_countries'
    )

    date_from = fields.Date(
        string='Date From',
        default=lambda self: datetime(datetime.now().year, datetime.now().month, 1).date()
    )

    date_to = fields.Date(
        string='Date To',
        default=lambda self: datetime.now().date()
    )

    # ============================================================================
    # ANALYTICS RECORD REFERENCES
    # ============================================================================

    personnel_costs_id = fields.Many2one(
        'hr.analytics.personnel.costs',
        string='Personnel Costs Analysis'
    )

    statutory_contrib_id = fields.Many2one(
        'hr.analytics.statutory.contrib',
        string='Statutory Contributions'
    )

    headcount_id = fields.Many2one(
        'hr.analytics.headcount',
        string='Headcount Analysis'
    )

    dependents_id = fields.Many2one(
        'hr.analytics.dependents',
        string='Dependents Analysis'
    )

    budget_variance_id = fields.Many2one(
        'hr.analytics.budget.variance',
        string='Budget Variance'
    )

    annual_costs_id = fields.Many2one(
        'hr.analytics.annual.costs',
        string='Annual Costs'
    )

    # ============================================================================
    # QUICK STATS FOR DISPLAY
    # ============================================================================

    total_personnel_cost = fields.Float(
        string='Total Personnel Cost',
        compute='_compute_dashboard_stats',
        currency_field='company_currency_id'
    )

    total_contributions = fields.Float(
        string='Total Contributions',
        compute='_compute_dashboard_stats',
        currency_field='company_currency_id'
    )

    total_headcount = fields.Integer(
        string='Total Headcount',
        compute='_compute_dashboard_stats'
    )

    average_salary = fields.Float(
        string='Average Salary',
        compute='_compute_dashboard_stats',
        currency_field='company_currency_id'
    )

    # ============================================================================
    # CACHE & PERFORMANCE
    # ============================================================================

    last_refresh = fields.Datetime(
        string='Last Refresh',
        readonly=True
    )

    cache_valid = fields.Boolean(
        string='Cache Valid',
        default=True
    )

    auto_refresh = fields.Boolean(
        string='Auto Refresh',
        default=True,
        help='Automatically refresh when related records change'
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
    # COMPUTED METHODS
    # ============================================================================

    def _compute_available_countries(self):
        """Get list of available countries"""
        for record in self:
            record.country_filter_ids = self.env['res.country'].search([
                ('code', 'in', ['VN', 'ID', 'IN', 'SG', 'TH', 'KH', 'MY'])
            ])

    @api.depends('selected_country')
    def _compute_dashboard_stats(self):
        """Compute quick stats with sample data based on country"""
        # Sample data by country
        sample_data = {
            'VN': {
                'headcount': 245,
                'personnel_cost': 5200000.00,
                'contributions': 850000.00,
                'average_salary': 21224.49
            },
            'ID': {
                'headcount': 180,
                'personnel_cost': 3600000.00,
                'contributions': 620000.00,
                'average_salary': 20000.00
            },
            'IN': {
                'headcount': 320,
                'personnel_cost': 8500000.00,
                'contributions': 1200000.00,
                'average_salary': 26562.50
            },
            'SG': {
                'headcount': 95,
                'personnel_cost': 2800000.00,
                'contributions': 450000.00,
                'average_salary': 29473.68
            },
            'TH': {
                'headcount': 150,
                'personnel_cost': 3200000.00,
                'contributions': 520000.00,
                'average_salary': 21333.33
            },
            'KH': {
                'headcount': 110,
                'personnel_cost': 1800000.00,
                'contributions': 280000.00,
                'average_salary': 16363.64
            },
            'MY': {
                'headcount': 130,
                'personnel_cost': 2900000.00,
                'contributions': 470000.00,
                'average_salary': 22307.69
            },
            'ALL': {
                'headcount': 1230,
                'personnel_cost': 28000000.00,
                'contributions': 4390000.00,
                'average_salary': 22764.23
            }
        }

        for record in self:
            country = record.selected_country or 'ALL'
            data = sample_data.get(country, sample_data['ALL'])

            record.total_headcount = data['headcount']
            record.total_personnel_cost = data['personnel_cost']
            record.total_contributions = data['contributions']
            record.average_salary = data['average_salary']

    # ============================================================================
    # CHANGE HANDLERS
    # ============================================================================

    @api.onchange('selected_country', 'date_from', 'date_to')
    def _onchange_filters(self):
        """Trigger metric recalculation when filters change"""
        # The @api.depends decorator on _compute_dashboard_stats will automatically
        # trigger the computation when these fields change
        pass

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    @api.model
    def get_or_create_dashboard(self):
        """Get or create the main dashboard and auto-initialize with data"""
        dashboard = self.search([('name', '=', 'HR Analytics Dashboard')], limit=1)

        if not dashboard:
            # Create main dashboard
            dashboard = self.create({
                'name': 'HR Analytics Dashboard',
                'selected_country': 'ALL'
            })

        # Auto-initialize data if missing
        if not dashboard.personnel_costs_id:
            try:
                dashboard.action_refresh_all_analytics()
            except Exception as e:
                _logger.warning(f'Auto-refresh failed: {str(e)}')

        return dashboard

    @api.model
    def default_get(self, fields):
        """Set defaults and auto-initialize dashboard"""
        res = super().default_get(fields)

        # Ensure date defaults are set
        if not res.get('date_from'):
            res['date_from'] = datetime(datetime.now().year, datetime.now().month, 1).date()
        if not res.get('date_to'):
            res['date_to'] = datetime.now().date()
        if not res.get('selected_country'):
            res['selected_country'] = 'ALL'

        return res

    def action_onload_generate_data(self):
        """Called when dashboard is loaded - auto-generate data if needed"""
        for record in self:
            if not record.personnel_costs_id and record.date_from and record.date_to:
                try:
                    record.action_refresh_all_analytics()
                except Exception as e:
                    _logger.warning(f'Onload generation failed: {str(e)}')
        return True

    def action_refresh_all_analytics(self):
        """Refresh all analytics data"""
        self.ensure_one()

        try:
            # Generate personnel costs
            if self.date_from and self.date_to:
                personnel_costs = self.env['hr.analytics.personnel.costs'].create({
                    'period_name': f'Personnel Costs {self.date_from} to {self.date_to}',
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'selected_country': self.selected_country if self.selected_country != 'ALL' else False,
                    'analysis_by': 'department'
                })
                personnel_costs.action_generate_analytics()
                self.personnel_costs_id = personnel_costs

                # Generate statutory contributions if country selected
                if self.selected_country != 'ALL':
                    statutory = self.env['hr.analytics.statutory.contrib'].create({
                        'period_name': f'Statutory Contributions {self.date_from} to {self.date_to}',
                        'date_from': self.date_from,
                        'date_to': self.date_to,
                        'country': self.selected_country,
                        'group_by': 'contribution_type'
                    })
                    statutory.action_generate_analytics()
                    self.statutory_contrib_id = statutory

                # Generate headcount
                headcount = self.env['hr.analytics.headcount'].create({
                    'period_name': f'Headcount Analysis {self.date_from} to {self.date_to}',
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'group_by': 'department'
                })
                headcount.action_generate_analytics()
                self.headcount_id = headcount

                # Generate budget variance with sample data
                budget = self.env['hr.analytics.budget.variance'].create({
                    'period_name': f'Budget Variance {self.date_from} to {self.date_to}',
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'total_budget': 500000
                })
                budget.action_generate_analytics()
                self.budget_variance_id = budget

            self.last_refresh = fields.Datetime.now()
            self.cache_valid = True

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('All analytics refreshed successfully!'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.exception('Error refreshing analytics: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Error refreshing analytics: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_export_current_report(self, format_type='pdf'):
        """Export current tab report"""
        self.ensure_one()

        try:
            if self.active_tab == 'personnel_costs' and self.personnel_costs_id:
                return self._export_personnel_costs(format_type)
            elif self.active_tab == 'statutory_contrib' and self.statutory_contrib_id:
                return self._export_statutory_contrib(format_type)
            elif self.active_tab == 'headcount' and self.headcount_id:
                return self._export_headcount(format_type)
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _('No data available to export for this report'),
                        'type': 'warning'
                    }
                }

        except Exception as e:
            _logger.exception('Export error: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Export failed: %s') % str(e),
                    'type': 'danger'
                }
            }

    def _export_personnel_costs(self, format_type):
        """Export personnel costs report"""
        if format_type == 'pdf':
            return self.env.ref('pb_hr_payroll_analytics.action_report_personnel_costs').report_action(
                self.personnel_costs_id
            )
        elif format_type == 'xlsx':
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'hr.analytics.export.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_report_type': 'personnel_costs',
                    'default_file_format': 'xlsx'
                }
            }

    def _export_statutory_contrib(self, format_type):
        """Export statutory contributions report"""
        if format_type == 'pdf':
            return self.env.ref('pb_hr_payroll_analytics.action_report_statutory_contrib').report_action(
                self.statutory_contrib_id
            )

    def _export_headcount(self, format_type):
        """Export headcount report"""
        if format_type == 'pdf':
            return self.env.ref('pb_hr_payroll_analytics.action_report_headcount').report_action(
                self.headcount_id
            )

    def action_switch_tab(self, tab_name):
        """Switch active tab"""
        self.ensure_one()
        self.active_tab = tab_name

    def action_clear_cache(self):
        """Clear analytics cache"""
        self.ensure_one()

        cache_model = self.env['hr.analytics.cache']
        cleared_count = cache_model.clear_cache()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Cleared %d cached records') % cleared_count,
                'type': 'success'
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Create dashboard - only one per company"""
        results = self.env['hr.analytics.dashboard']
        
        for vals in vals_list:
            # Check if dashboard already exists for this company
            company_id = vals.get('company_id', self.env.company.id)
            existing = self.search([
                ('company_id', '=', company_id)
            ], limit=1)

            if existing:
                results |= existing
            else:
                results |= super().create([vals])
        
        return results
