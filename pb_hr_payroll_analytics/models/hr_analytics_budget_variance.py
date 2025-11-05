# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsBudgetVariance(models.Model):
    """Budget vs Actual Variance Analysis (Placeholder with Sample Data)"""

    _name = 'hr.analytics.budget.variance'
    _description = 'HR Analytics - Budget Variance (Placeholder)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from DESC'

    period_name = fields.Char(string='Period Name', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)

    # Budget vs Actual Data
    budget_data = fields.Text(string='Budget Data (JSON)')
    actual_data = fields.Text(string='Actual Data (JSON)')
    variance_json = fields.Text(string='Variance (JSON)')

    # Metrics
    total_budget = fields.Float(string='Total Budget', currency_field='company_currency_id')
    total_actual = fields.Float(string='Total Actual', compute='_compute_metrics', store=True, currency_field='company_currency_id')
    total_variance = fields.Float(string='Total Variance', compute='_compute_metrics', store=True, currency_field='company_currency_id')
    variance_percentage = fields.Float(string='Variance %', compute='_compute_metrics', store=True)

    # Alerts
    budget_alerts = fields.Text(string='Budget Alerts (JSON)')
    use_sample_data = fields.Boolean(string='Using Sample Data', default=True, readonly=True)

    state = fields.Selection([('draft', 'Draft'), ('ready', 'Ready')], default='draft')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    last_refresh = fields.Datetime(string='Last Refresh', readonly=True)

    @api.depends('budget_data', 'actual_data')
    def _compute_metrics(self):
        """Compute budget variance metrics"""
        for record in self:
            try:
                budget = json.loads(record.budget_data or '{}')
                actual = json.loads(record.actual_data or '{}')

                # Extract total amounts
                def get_total(data_dict):
                    total = 0
                    for v in data_dict.values():
                        if isinstance(v, dict):
                            total += v.get('total', 0) or v.get('actual', 0)
                        elif isinstance(v, (int, float)):
                            total += v
                    return total

                total_budget = get_total(budget)
                total_actual = get_total(actual)

                record.total_actual = total_actual
                record.total_variance = total_actual - total_budget

                if total_budget > 0:
                    record.variance_percentage = (record.total_variance / total_budget) * 100
                else:
                    record.variance_percentage = 0

            except (json.JSONDecodeError, ValueError, TypeError):
                record.total_actual = 0
                record.total_variance = 0
                record.variance_percentage = 0

    def action_generate_analytics(self):
        """Generate budget variance analytics with sample data"""
        self.ensure_one()
        try:
            # Create sample budget and actual data
            budget_data = {
                'Sales': {'budget': 500000, 'employees': 15},
                'HR': {'budget': 120000, 'employees': 5},
                'IT': {'budget': 280000, 'employees': 12},
                'Finance': {'budget': 110000, 'employees': 4},
                'Admin': {'budget': 80000, 'employees': 3}
            }

            actual_data = {
                'Sales': {'actual': 520000, 'employees': 15},
                'HR': {'actual': 119000, 'employees': 5},
                'IT': {'actual': 275000, 'employees': 12},
                'Finance': {'actual': 115000, 'employees': 4},
                'Admin': {'actual': 78000, 'employees': 3}
            }

            # Calculate variances
            variance_data = {}
            alerts = []

            for dept in budget_data:
                budget_amt = budget_data[dept]['budget']
                actual_amt = actual_data[dept]['actual']
                variance = actual_amt - budget_amt
                var_pct = (variance / budget_amt) * 100 if budget_amt > 0 else 0

                variance_data[dept] = {
                    'variance_amount': variance,
                    'variance_pct': var_pct,
                    'budget': budget_amt,
                    'actual': actual_amt
                }

                # Flag if variance > 10%
                if abs(var_pct) > 10:
                    alerts.append({
                        'department': dept,
                        'variance_pct': var_pct,
                        'severity': 'high' if abs(var_pct) > 15 else 'medium'
                    })

            self.budget_data = json.dumps(budget_data)
            self.actual_data = json.dumps(actual_data)
            self.variance_json = json.dumps(variance_data)
            self.budget_alerts = json.dumps(alerts)
            self.use_sample_data = True

            self.state = 'ready'
            self.last_refresh = fields.Datetime.now()

            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Budget variance analysis generated (sample data)!'), 'type': 'success'}}
        except Exception as e:
            _logger.exception('Error: %s', str(e))
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Error: %s') % str(e), 'type': 'danger'}}
