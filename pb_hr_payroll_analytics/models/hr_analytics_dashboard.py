# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


def _demo_world(env):
    """True only where `pb_demo` is installed.

    LEARNOS ledger rule 1: fabricated figures are allowed in a demo world and
    nowhere else. Every sample-data path in this module asks this first.
    """
    try:
        return bool(env['ir.module.module'].sudo().search_count([
            ('name', '=', 'pb_demo'), ('state', '=', 'installed'),
        ]))
    except Exception:  # pragma: no cover — a registry without the model
        return False


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

    @api.depends('company_id')
    def _compute_dashboard_stats(self):
        """The four headline stats, read from the payslips themselves.

        These used to be a per-country dict of invented constants, whose
        global row leaked onto every brand-new tenant's home dashboard through
        `pb_dashboard`'s fallback. (Do not restate those figures here: the
        phase's verification greps this file for them.) The aggregate is now
        exactly the one `pb.dashboard.get_dashboard_data` runs: the latest
        `date_from` month, company-scoped, GROSS for payroll, the INSCO/COMP
        categories for contributions, distinct employees for headcount, and
        END-cycle payslips only (with a Mid+End cycle both slips carry the full
        GROSS, so counting both would double everything).

        `selected_country` is deliberately ignored: it was never anything but a
        key into the sample dict.
        """
        # A database without the formula engine has no `hr_formula_config`
        # table, and a failed statement poisons the whole transaction — so ask
        # the registry before writing the JOIN.
        has_cfg = 'hr.formula.config' in self.env
        cycle_clause = (
            "AND (fc.cycle_type = 'end_cycle' OR fc.id IS NULL)" if has_cfg else "")
        cfg_join = (
            "LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id" if has_cfg else "")

        for record in self:
            company = record.company_id or self.env.company
            headcount = 0
            payroll = contributions = 0.0
            try:
                # Savepoint so a failed statement cannot leave the whole request
                # transaction in InFailedSqlTransaction — "zeros" must really
                # mean zeros, not a poisoned cursor.
                with self.env.cr.savepoint():
                    self.env.cr.execute(
                        "SELECT max(date_from) FROM hr_payslip WHERE company_id = %s",
                        (company.id,))
                    ref = (self.env.cr.fetchone() or [None])[0]
                    if ref:
                        self.env.cr.execute("""
                            SELECT count(DISTINCT p.employee_id),
                                   coalesce(sum(CASE WHEN pl.code='GROSS' THEN pl.total ELSE 0 END), 0),
                                   coalesce(sum(CASE WHEN cat.code IN ('INSCO', 'COMP') THEN pl.total ELSE 0 END), 0)
                            FROM hr_payslip p
                            JOIN hr_payslip_line pl ON pl.slip_id = p.id
                            JOIN hr_salary_rule_category cat ON cat.id = pl.category_id
                            %s
                            WHERE p.company_id = %%s AND p.date_from = %%s
                              %s
                        """ % (cfg_join, cycle_clause), (company.id, ref))
                        row = self.env.cr.fetchone() or (0, 0.0, 0.0)
                        headcount, payroll, contributions = row[0] or 0, row[1] or 0.0, row[2] or 0.0
            except Exception:
                _logger.exception('Analytics dashboard stats failed; reporting zeros.')
                headcount = 0
                payroll = contributions = 0.0

            record.total_headcount = headcount
            record.total_personnel_cost = payroll
            record.total_contributions = contributions
            record.average_salary = (payroll / headcount) if headcount else 0.0

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

    # ------------------------------------------------------------------
    # RETIRED (Sudima Phase N). This action created FOUR analytics records —
    # personnel costs, statutory contributions, headcount and a budget
    # variance seeded with a literal 500,000 — on every dashboard open, and it
    # was called from `create()`, from `action_onload_generate_data()` and from
    # the Refresh/Apply buttons. Merely LOOKING at the dashboard therefore grew
    # the database by four rows, which is where the stray draft records users
    # kept finding came from.
    #
    # The records it produced were not usable anyway: the statutory total sums
    # a dict containing a string and swallows the resulting TypeError
    # (hr_analytics_statutory_contrib.py:244), generation reads the removed
    # `address_home_id` field (:405), and the budget figure was invented.
    #
    # The generator is kept behind an explicit opt-in so nothing that calls it
    # crashes, but the automatic path is closed. The live replacement is the
    # Analytics Explorer (pb_explorer), which derives everything from payslip
    # truth and writes no analytics records at all.
    # ------------------------------------------------------------------
    def action_refresh_all_analytics(self):
        """Retired: no longer generates records unless explicitly forced."""
        self.ensure_one()
        if not self.env.context.get('pb_allow_legacy_analytics_generation'):
            _logger.info(
                'pb_hr_payroll_analytics: legacy generation is retired; '
                'use the Analytics Explorer instead.')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Replaced by the Analytics Explorer'),
                    'message': _(
                        'This legacy dashboard no longer generates data. Open '
                        'Insights > Analytics Explorer for live figures read '
                        'straight from your payslips.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return self._legacy_refresh_all_analytics()

    def _legacy_refresh_all_analytics(self):
        """The original generator, retained for explicit/manual use only."""
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
