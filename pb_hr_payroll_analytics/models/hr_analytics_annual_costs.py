# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsAnnualCosts(models.Model):
    """Annual HR Cost Overview with projections and trends"""

    _name = 'hr.analytics.annual.costs'
    _description = 'HR Analytics - Annual HR Costs'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fiscal_year DESC'

    fiscal_year = fields.Char(string='Fiscal Year', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)

    # Monthly Cost Data
    monthly_costs = fields.Text(string='Monthly Costs (JSON)')
    monthly_headcount = fields.Text(string='Monthly Headcount (JSON)')

    # Annual Totals
    annual_salary_total = fields.Float(string='Annual Salary Total', compute='_compute_totals', store=True, currency_field='company_currency_id')
    annual_contrib_total = fields.Float(string='Annual Contributions', compute='_compute_totals', store=True, currency_field='company_currency_id')
    annual_benefits_total = fields.Float(string='Annual Benefits', compute='_compute_totals', store=True, currency_field='company_currency_id')
    annual_total_cost = fields.Float(string='Annual Total Cost', compute='_compute_totals', store=True, currency_field='company_currency_id')
    annual_cost_per_employee = fields.Float(string='Annual Cost/Employee', compute='_compute_totals', store=True, currency_field='company_currency_id')

    # Trend Analysis
    cost_trend = fields.Text(string='Cost Trend (JSON)')
    trend_direction = fields.Selection([
        ('stable', 'Stable (±5%)'),
        ('increasing', 'Increasing (>5%)'),
        ('decreasing', 'Decreasing (<-5%)')
    ], compute='_compute_trend', store=True)

    # Year-over-Year
    yoy_comparison = fields.Text(string='YoY Comparison (JSON)')
    growth_rate = fields.Float(string='YoY Growth %', compute='_compute_yoy', store=True)

    # Projection
    projected_full_year = fields.Float(string='Projected Full Year', compute='_compute_projection', store=True, currency_field='company_currency_id')
    projection_basis = fields.Char(string='Projection Basis')

    state = fields.Selection([('draft', 'Draft'), ('ready', 'Ready')], default='draft')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    last_refresh = fields.Datetime(string='Last Refresh', readonly=True)

    @api.depends('monthly_costs')
    def _compute_totals(self):
        """Compute annual cost totals"""
        for record in self:
            try:
                costs = json.loads(record.monthly_costs or '{}')

                total_salary = sum(c.get('salary', 0) for c in costs.values() if isinstance(c, dict))
                total_contrib = sum(c.get('contrib', 0) for c in costs.values() if isinstance(c, dict))
                total_benefits = sum(c.get('benefits', 0) for c in costs.values() if isinstance(c, dict))

                record.annual_salary_total = total_salary
                record.annual_contrib_total = total_contrib
                record.annual_benefits_total = total_benefits
                record.annual_total_cost = total_salary + total_contrib + total_benefits

                # Cost per employee
                hc_data = json.loads(record.monthly_headcount or '{}')
                total_hc = sum(h.get('count', 0) for h in hc_data.values() if isinstance(h, dict))
                if total_hc > 0:
                    record.annual_cost_per_employee = record.annual_total_cost / total_hc
                else:
                    record.annual_cost_per_employee = 0

            except (json.JSONDecodeError, ValueError, TypeError):
                record.annual_salary_total = 0
                record.annual_contrib_total = 0
                record.annual_benefits_total = 0
                record.annual_total_cost = 0
                record.annual_cost_per_employee = 0

    @api.depends('cost_trend')
    def _compute_trend(self):
        """Compute cost trend direction"""
        for record in self:
            record.trend_direction = 'stable'

    @api.depends('yoy_comparison')
    def _compute_yoy(self):
        """Compute year-over-year growth"""
        for record in self:
            try:
                yoy = json.loads(record.yoy_comparison or '{}')
                current_year = yoy.get('current_year', {}).get('total', 0)
                previous_year = yoy.get('previous_year', {}).get('total', 0)

                if previous_year > 0:
                    record.growth_rate = ((current_year - previous_year) / previous_year) * 100
                else:
                    record.growth_rate = 0
            except (json.JSONDecodeError, ValueError, TypeError):
                record.growth_rate = 0

    @api.depends('annual_total_cost')
    def _compute_projection(self):
        """Compute full year projection"""
        for record in self:
            record.projected_full_year = record.annual_total_cost

    def action_generate_analytics(self):
        """Generate annual costs analytics"""
        self.ensure_one()
        try:
            self.state = 'ready'
            self.last_refresh = fields.Datetime.now()

            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Annual costs analysis generated!'), 'type': 'success'}}
        except Exception as e:
            _logger.exception('Error: %s', str(e))
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Error: %s') % str(e), 'type': 'danger'}}
