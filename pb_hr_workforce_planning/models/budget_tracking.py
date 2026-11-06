# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class WfpBudgetActual(models.Model):
    """Track actual payroll spend vs forecasted costs per scenario/period."""
    _name = 'wfp.budget.actual'
    _description = 'Budget vs Actual Tracking'
    _order = 'period_month desc, department_id'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='scenario_id.company_id', store=True,
    )
    currency_id = fields.Many2one(
        related='scenario_id.currency_id',
    )

    period_month = fields.Date(
        string='Period (1st of Month)',
        required=True,
        help="First day of the month this record covers.",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
    )

    # Forecasted (from scenario)
    forecast_headcount = fields.Integer(string='Forecast Headcount')
    forecast_cost = fields.Monetary(string='Forecast Cost')

    # Actual (from payslips)
    actual_headcount = fields.Integer(string='Actual Headcount')
    actual_cost = fields.Monetary(string='Actual Cost')

    # Computed deltas
    variance_amount = fields.Monetary(
        string='Variance (₫)',
        compute='_compute_variance',
        store=True,
    )
    variance_pct = fields.Float(
        string='Variance %',
        compute='_compute_variance',
        store=True,
        digits=(5, 2),
    )

    @api.depends('forecast_cost', 'actual_cost')
    def _compute_variance(self):
        for rec in self:
            rec.variance_amount = (rec.forecast_cost or 0) - (rec.actual_cost or 0)
            if rec.forecast_cost:
                rec.variance_pct = (
                    rec.variance_amount / rec.forecast_cost
                ) * 100
            else:
                rec.variance_pct = 0.0
