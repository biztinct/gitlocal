# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import json


class WfpEmployeeForecast(models.Model):
    """
    Employee-level forecast output — one record per employee per scenario.
    Contains current costs, forecast costs, delta, and component breakdown.
    """
    _name = 'wfp.employee.forecast'
    _description = 'Workforce Planning Employee Forecast'
    _order = 'increase_amount desc'
    _rec_name = 'employee_id'

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

    # ==========================================
    # EMPLOYEE REFERENCE
    # ==========================================
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
    )
    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        related='employee_id.job_id',
        store=True,
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Manager',
        related='employee_id.parent_id',
        store=True,
    )
    country_code = fields.Char(
        string='Country',
        help="Country code from formula config."
    )
    location = fields.Char(
        string='Location / Cost Center',
    )

    # ==========================================
    # CURRENT COSTS (from formula engine)
    # ==========================================
    current_base = fields.Monetary(
        string='Current Base Salary',
    )
    current_allowances = fields.Monetary(
        string='Current Allowances',
    )
    current_gross = fields.Monetary(
        string='Current Gross',
    )
    current_deductions = fields.Monetary(
        string='Current Deductions',
    )
    current_net = fields.Monetary(
        string='Current Net',
    )
    current_employer_cost = fields.Monetary(
        string='Current Employer Cost',
        help="Sum of all employer-side contributions (SI, HI, etc.)"
    )
    current_total_cost = fields.Monetary(
        string='Current Total Cost (TCOW)',
        help="Gross + Employer Cost = Total Cost of Workforce"
    )
    current_components_json = fields.Text(
        string='Current Components (JSON)',
        help="Full component breakdown: [{code, name, wfp_category, amount}]"
    )

    # ==========================================
    # FORECAST COSTS (re-calculated)
    # ==========================================
    forecast_base = fields.Monetary(
        string='Forecast Base Salary',
    )
    forecast_allowances = fields.Monetary(
        string='Forecast Allowances',
    )
    forecast_gross = fields.Monetary(
        string='Forecast Gross',
    )
    forecast_deductions = fields.Monetary(
        string='Forecast Deductions',
    )
    forecast_net = fields.Monetary(
        string='Forecast Net',
    )
    forecast_employer_cost = fields.Monetary(
        string='Forecast Employer Cost',
    )
    forecast_total_cost = fields.Monetary(
        string='Forecast Total Cost (TCOW)',
    )
    forecast_components_json = fields.Text(
        string='Forecast Components (JSON)',
    )

    # ==========================================
    # DELTA (computed)
    # ==========================================
    increase_amount = fields.Monetary(
        string='Increase Amount',
        compute='_compute_deltas',
        store=True,
    )
    increase_pct = fields.Float(
        string='Increase %',
        compute='_compute_deltas',
        store=True,
        digits=(5, 2),
    )
    monthly_delta = fields.Monetary(
        string='Monthly Delta',
        compute='_compute_deltas',
        store=True,
    )
    annual_delta = fields.Monetary(
        string='Annual Delta',
        compute='_compute_deltas',
        store=True,
    )
    annualized_delta = fields.Monetary(
        string='Annualized Delta',
        compute='_compute_deltas',
        store=True,
        help="Impact factoring effective date (months remaining in FY)."
    )

    # ==========================================
    # METADATA
    # ==========================================
    applied_rule_id = fields.Many2one(
        'wfp.increase.rule',
        string='Applied Rule',
    )
    applied_rule_name = fields.Char(
        string='Rule Name',
        related='applied_rule_id.name',
        store=True,
    )
    tenure_months = fields.Integer(
        string='Tenure (months)',
    )
    is_excluded = fields.Boolean(
        string='Excluded',
        default=False,
    )
    exclusion_reason = fields.Char(
        string='Exclusion Reason',
    )

    # ==========================================
    # COMPUTED DELTAS
    # ==========================================
    @api.depends(
        'current_total_cost', 'forecast_total_cost',
        'scenario_id.effective_date', 'scenario_id.fiscal_year',
    )
    def _compute_deltas(self):
        for rec in self:
            rec.increase_amount = (
                rec.forecast_total_cost - rec.current_total_cost
            )
            if rec.current_total_cost:
                rec.increase_pct = (
                    rec.increase_amount / rec.current_total_cost
                ) * 100
            else:
                rec.increase_pct = 0.0
            rec.monthly_delta = (
                (rec.forecast_total_cost - rec.current_total_cost)
            )
            rec.annual_delta = rec.monthly_delta * 12

            # Annualized: months remaining from effective date to FY end
            if rec.scenario_id.effective_date:
                eff = rec.scenario_id.effective_date
                fy_end_month = 12  # Assume Dec year-end
                months_remaining = max(0, fy_end_month - eff.month + 1)
                rec.annualized_delta = rec.monthly_delta * months_remaining
            else:
                rec.annualized_delta = rec.annual_delta

    def get_current_components(self):
        """Return current components as list of dicts."""
        self.ensure_one()
        if self.current_components_json:
            try:
                return json.loads(self.current_components_json)
            except Exception:
                pass
        return []

    def get_forecast_components(self):
        """Return forecast components as list of dicts."""
        self.ensure_one()
        if self.forecast_components_json:
            try:
                return json.loads(self.forecast_components_json)
            except Exception:
                pass
        return []
