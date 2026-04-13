# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class WfpPlanningScenario(models.Model):
    """
    Workforce Planning Scenario — top-level container.
    Each scenario is tied to ONE hr.formula.config (one country/structure).
    Contains increase rules, generates employee forecasts and monthly projections.
    """
    _name = 'wfp.planning.scenario'
    _description = 'Workforce Planning Scenario'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ==========================================
    # IDENTITY
    # ==========================================
    name = fields.Char(
        string='Scenario Name',
        required=True,
        tracking=True,
        help="e.g. 'FY27 Budget — Conservative 3%'"
    )
    description = fields.Html(
        string='Assumptions & Notes',
        help="Document the rationale and assumptions behind this scenario."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    # ==========================================
    # FORMULA CONFIG LINK (1 scenario = 1 config)
    # ==========================================
    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure (Formula Config)',
        required=True,
        tracking=True,
        domain="[('state', '=', 'active')]",
        help="The formula configuration that defines salary components and "
             "calculation formulas for this scenario. Each scenario must use "
             "a single config (could be per country, department, or branch)."
    )
    country_code = fields.Selection(
        related='formula_config_id.country_code',
        string='Country',
        store=True,
        readonly=True,
    )

    # ==========================================
    # PLANNING PERIOD
    # ==========================================
    fiscal_year = fields.Integer(
        string='Fiscal Year',
        default=lambda self: fields.Date.today().year + 1,
        required=True,
        tracking=True,
    )
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        tracking=True,
        help="Date when salary increases take effect."
    )

    # ==========================================
    # STATE
    # ==========================================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('approved', 'Approved'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', tracking=True, required=True)

    owner_id = fields.Many2one(
        'res.users',
        string='Owner',
        default=lambda self: self.env.user,
        tracking=True,
    )

    # ==========================================
    # INCREASE RULES
    # ==========================================
    rule_ids = fields.One2many(
        'wfp.increase.rule',
        'scenario_id',
        string='Increase Rules',
        copy=True,
    )
    rule_count = fields.Integer(
        string='Rules',
        compute='_compute_counts',
    )

    # ==========================================
    # FORECAST RESULTS
    # ==========================================
    employee_forecast_ids = fields.One2many(
        'wfp.employee.forecast',
        'scenario_id',
        string='Employee Forecasts',
    )
    monthly_projection_ids = fields.One2many(
        'wfp.monthly.projection',
        'scenario_id',
        string='Monthly Projections',
    )

    # ==========================================
    # BUDGET
    # ==========================================
    budget_amount = fields.Monetary(
        string='Approved Budget',
        tracking=True,
        help="The approved budget cap for this scenario."
    )

    # ==========================================
    # AGGREGATES (computed from forecasts)
    # ==========================================
    headcount = fields.Integer(
        string='Headcount',
        compute='_compute_aggregates',
        store=True,
    )
    total_current_cost = fields.Monetary(
        string='Current Total Cost',
        compute='_compute_aggregates',
        store=True,
        help="Sum of current total employer costs for all employees."
    )
    total_forecast_cost = fields.Monetary(
        string='Forecast Total Cost',
        compute='_compute_aggregates',
        store=True,
        help="Sum of projected total employer costs for all employees."
    )
    total_increase_amount = fields.Monetary(
        string='Total Increase',
        compute='_compute_aggregates',
        store=True,
    )
    total_increase_pct = fields.Float(
        string='Increase %',
        compute='_compute_aggregates',
        store=True,
        digits=(5, 2),
    )
    budget_variance = fields.Monetary(
        string='Budget Variance',
        compute='_compute_aggregates',
        store=True,
        help="Budget - Forecast Total Cost. Positive = under budget."
    )
    forecast_count = fields.Integer(
        string='Forecasts',
        compute='_compute_counts',
    )

    # ==========================================
    # SCOPE FILTERS
    # ==========================================
    filter_department_ids = fields.Many2many(
        'hr.department',
        'wfp_scenario_department_rel',
        'scenario_id', 'department_id',
        string='Departments',
        help="Leave empty for all departments."
    )
    filter_job_ids = fields.Many2many(
        'hr.job',
        'wfp_scenario_job_rel',
        'scenario_id', 'job_id',
        string='Job Positions',
        help="Leave empty for all job positions."
    )
    filter_location = fields.Char(
        string='Location Filter',
        help="Filter by contract location / cost center."
    )

    last_calculated = fields.Datetime(
        string='Last Calculated',
        readonly=True,
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('rule_ids', 'employee_forecast_ids')
    def _compute_counts(self):
        for rec in self:
            rec.rule_count = len(rec.rule_ids)
            rec.forecast_count = len(rec.employee_forecast_ids)

    @api.depends(
        'employee_forecast_ids.current_total_cost',
        'employee_forecast_ids.forecast_total_cost',
        'employee_forecast_ids.is_excluded',
        'budget_amount',
    )
    def _compute_aggregates(self):
        for rec in self:
            forecasts = rec.employee_forecast_ids.filtered(
                lambda f: not f.is_excluded
            )
            rec.headcount = len(forecasts)
            rec.total_current_cost = sum(
                forecasts.mapped('current_total_cost')
            )
            rec.total_forecast_cost = sum(
                forecasts.mapped('forecast_total_cost')
            )
            rec.total_increase_amount = (
                rec.total_forecast_cost - rec.total_current_cost
            )
            if rec.total_current_cost:
                rec.total_increase_pct = (
                    rec.total_increase_amount / rec.total_current_cost
                ) * 100
            else:
                rec.total_increase_pct = 0.0
            rec.budget_variance = (
                (rec.budget_amount or 0) - rec.total_forecast_cost
            )

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_calculate(self):
        """Run the simulation engine for this scenario."""
        self.ensure_one()
        if not self.rule_ids:
            raise UserError(_(
                "Please add at least one increase rule before calculating."
            ))
        if not self.formula_config_id:
            raise UserError(_(
                "Please select a Salary Structure (Formula Config) first."
            ))
        # Check that formula rules have WFP categories tagged
        rules = self.formula_config_id.rule_ids
        tagged = rules.filtered(lambda r: r.wfp_category)
        if not tagged:
            raise UserError(_(
                "No formula rules have been tagged with WFP categories. "
                "Please use the 'Tag Formula Components' wizard first to "
                "classify components (Base Salary, Allowance, Employer Cost, "
                "Gross, Net, etc.)."
            ))

        engine = self.env['wfp.simulation.engine']
        engine.run_scenario(self)

        self.write({
            'state': 'calculated',
            'last_calculated': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scenario Calculated'),
                'message': _(
                    'Forecasts generated for %d employees.'
                ) % self.headcount,
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_archive(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_duplicate_scenario(self):
        """Clone this scenario for comparison."""
        self.ensure_one()
        new = self.copy({
            'name': _('%s (Copy)') % self.name,
            'state': 'draft',
            'last_calculated': False,
        })
        # Clear forecast data from copy
        new.employee_forecast_ids.unlink()
        new.monthly_projection_ids.unlink()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wfp.planning.scenario',
            'res_id': new.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_forecasts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Employee Forecasts — %s') % self.name,
            'res_model': 'wfp.employee.forecast',
            'view_mode': 'list,pivot,graph',
            'domain': [('scenario_id', '=', self.id)],
            'context': {'default_scenario_id': self.id},
        }

    def action_view_projections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Monthly Projections — %s') % self.name,
            'res_model': 'wfp.monthly.projection',
            'view_mode': 'list,graph',
            'domain': [('scenario_id', '=', self.id)],
            'context': {'default_scenario_id': self.id},
        }

    # ==========================================
    # DASHBOARD API
    # ==========================================
    @api.model
    def get_dashboard_data(self, scenario_id):
        """Return all data needed by the OWL dashboard."""
        scenario = self.browse(scenario_id)
        if not scenario.exists():
            return {}

        forecasts = scenario.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        )

        # Department breakdown
        dept_data = {}
        for f in forecasts:
            dept = f.department_id.name or _('No Department')
            if dept not in dept_data:
                dept_data[dept] = {
                    'headcount': 0,
                    'current': 0, 'forecast': 0,
                }
            dept_data[dept]['headcount'] += 1
            dept_data[dept]['current'] += f.current_total_cost
            dept_data[dept]['forecast'] += f.forecast_total_cost

        # Monthly projections
        monthly = []
        for proj in scenario.monthly_projection_ids.sorted(
            key=lambda p: (p.year, int(p.month))
        ):
            monthly.append({
                'period': proj.period_label,
                'headcount': proj.headcount,
                'total_gross': proj.total_gross,
                'total_employer_cost': proj.total_employer_cost,
                'total_cost': proj.total_cost_to_company,
                'delta': proj.delta_vs_current,
                'is_pre': proj.is_pre_effective,
            })

        # Employee list
        employees = []
        for f in forecasts.sorted(
            key=lambda f: abs(f.increase_amount), reverse=True
        ):
            employees.append({
                'id': f.employee_id.id,
                'name': f.employee_id.name,
                'department': f.department_id.name or '',
                'job': f.job_id.name or '',
                'country': f.country_code or '',
                'location': f.location or '',
                'current_base': f.current_base,
                'current_gross': f.current_gross,
                'current_employer': f.current_employer_cost,
                'current_total': f.current_total_cost,
                'forecast_base': f.forecast_base,
                'forecast_gross': f.forecast_gross,
                'forecast_employer': f.forecast_employer_cost,
                'forecast_total': f.forecast_total_cost,
                'increase_amount': f.increase_amount,
                'increase_pct': f.increase_pct,
                'rule_name': f.applied_rule_name or _('No Rule'),
                'compa_ratio': f.contract_id.compa_ratio if f.contract_id else 0,
                'grade': f.contract_id.grade_id.name if f.contract_id and f.contract_id.grade_id else '',
            })

        return {
            'scenario': {
                'id': scenario.id,
                'name': scenario.name,
                'state': scenario.state,
                'fiscal_year': scenario.fiscal_year,
                'effective_date': str(scenario.effective_date),
                'formula_config': scenario.formula_config_id.display_name,
                'country_code': scenario.country_code,
            },
            'kpis': {
                'headcount': scenario.headcount,
                'current_cost': scenario.total_current_cost,
                'forecast_cost': scenario.total_forecast_cost,
                'increase_amount': scenario.total_increase_amount,
                'increase_pct': scenario.total_increase_pct,
                'budget': scenario.budget_amount or 0,
                'variance': scenario.budget_variance,
            },
            'departments': dept_data,
            'monthly': monthly,
            'employees': employees,
        }
