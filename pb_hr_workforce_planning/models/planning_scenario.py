# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import json
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

    # Phase C: Audit trail & budget tracking
    approval_ids = fields.One2many(
        'wfp.scenario.approval', 'scenario_id',
        string='Audit Trail',
    )
    budget_actual_ids = fields.One2many(
        'wfp.budget.actual', 'scenario_id',
        string='Budget vs Actuals',
    )
    version_ids = fields.One2many(
        'wfp.scenario.version', 'scenario_id',
        string='Version History',
    )
    version_count = fields.Integer(
        compute='_compute_version_count',
    )

    def _compute_version_count(self):
        for rec in self:
            rec.version_count = len(rec.version_ids)

    def action_save_version(self):
        """Save current state as a new version snapshot."""
        self.ensure_one()
        result = self.env['wfp.scenario.version'].create_version(
            self.id,
            label=_('v%d — %s') % (
                self.version_count + 1, self.state or 'draft'
            ),
        )
        if result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Version Saved'),
                    'message': _('Saved as "%s"') % result['name'],
                    'type': 'success',
                    'sticky': False,
                },
            }

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

        old_state = self.state
        self.write({
            'state': 'calculated',
            'last_calculated': fields.Datetime.now(),
        })
        self._log_audit('calculate', old_state, 'calculated')
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
        for rec in self:
            old_state = rec.state
            rec.write({'state': 'approved'})
            rec._log_audit('approve', old_state, 'approved')

    def action_archive(self):
        for rec in self:
            old_state = rec.state
            rec.write({'state': 'archived'})
            rec._log_audit('archive', old_state, 'archived')

    def action_reset_draft(self):
        for rec in self:
            old_state = rec.state
            rec.write({'state': 'draft'})
            rec._log_audit('reset', old_state, 'draft')

    def _log_audit(self, action, from_state, to_state, note=''):
        """Create an audit trail entry with KPI snapshot."""
        self.ensure_one()
        snapshot = json.dumps({
            'headcount': self.headcount,
            'current_cost': self.total_current_cost,
            'forecast_cost': self.total_forecast_cost,
            'increase_pct': self.total_increase_pct,
            'budget': self.budget_amount,
            'variance': self.budget_variance,
        })
        self.env['wfp.scenario.approval'].sudo().create({
            'scenario_id': self.id,
            'action': action,
            'from_state': from_state if from_state in dict(
                self.env['wfp.scenario.approval']._fields['from_state'].selection
            ) else False,
            'to_state': to_state,
            'note': note,
            'snapshot_json': snapshot,
        })

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

    @api.model
    def get_labor_analytics_data(self, department_id=False, date_from=False, date_to=False):
        """Return labor analytics data for the Labor Analytics tab.

        Pulls data from hr.attendance, hr.shift.planning, hr.overtime.request
        via soft dependency on pb_hr_workforce.
        """
        from datetime import date as d_date, datetime, timedelta
        from collections import defaultdict
        import json

        # Use sudo for cross-company analytics reads
        sudo_env = self.sudo().env

        today = d_date.today()
        if not date_from:
            date_from = today.replace(day=1)
        else:
            date_from = fields.Date.from_string(date_from)
        if not date_to:
            date_to = today
        else:
            date_to = fields.Date.from_string(date_to)

        # Employee scope
        emp_domain = [('active', '=', True)]
        if department_id:
            emp_domain.append(('department_id', '=', department_id))
        employees = sudo_env['hr.employee'].search(emp_domain)
        emp_ids = employees.ids

        # ── KPIs ──
        total_employees = len(employees)

        # Present today
        today_start = datetime.combine(today, datetime.min.time())
        today_end = today_start + timedelta(days=1)
        Attendance = sudo_env['hr.attendance']
        checked_in_today = Attendance.search([
            ('employee_id', 'in', emp_ids),
            ('check_in', '>=', today_start),
            ('check_in', '<', today_end),
        ]).mapped('employee_id')
        present_today = len(set(checked_in_today.ids))
        absent_today = total_employees - present_today
        presence_rate = round(
            (present_today / total_employees * 100) if total_employees else 0, 1
        )

        # Average hours this week
        week_start = today - timedelta(days=today.weekday())
        week_atts = Attendance.search([
            ('employee_id', 'in', emp_ids),
            ('check_in', '>=', datetime.combine(week_start, datetime.min.time())),
            ('check_out', '!=', False),
        ])
        total_week_hrs = sum(a.worked_hours for a in week_atts)
        avg_hours_week = round(
            (total_week_hrs / total_employees) if total_employees else 0, 1
        )

        # Total worked hours in period
        period_atts = Attendance.search([
            ('employee_id', 'in', emp_ids),
            ('check_in', '>=', datetime.combine(date_from, datetime.min.time())),
            ('check_in', '<=', datetime.combine(date_to, datetime.max.time())),
            ('check_out', '!=', False),
        ])
        total_period_hrs = round(sum(a.worked_hours for a in period_atts), 1)

        # Standard hours (assumption: 8hr/day, 22 days/month)
        working_days = max(1, (date_to - date_from).days + 1)
        # Rough weekday count
        weekday_count = sum(
            1 for i in range(working_days)
            if (date_from + timedelta(days=i)).weekday() < 5
        )
        standard_hours = weekday_count * 8 * total_employees
        utilization_rate = round(
            (total_period_hrs / standard_hours * 100) if standard_hours else 0, 1
        )

        # OT hours
        ot_hours = 0.0
        try:
            OTLine = sudo_env['hr.attendance.overtime.line']
            ot_records = OTLine.search([
                ('employee_id', 'in', emp_ids),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            ot_hours = round(sum(o.duration for o in ot_records), 1)
        except Exception:
            pass

        # Pending OT requests
        pending_ot = 0
        try:
            pending_ot = sudo_env['hr.overtime.request'].search_count([
                ('employee_id', 'in', emp_ids),
                ('state', '=', 'submitted'),
            ])
        except Exception:
            pass

        # Shift compliance
        shift_compliance = 100.0
        total_shifts = 0
        try:
            shifts = sudo_env['hr.shift.planning'].search([
                ('employee_id', 'in', emp_ids),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('state', '=', 'completed'),
            ])
            total_shifts = len(shifts)
            if shifts:
                on_time = len(shifts.filtered(
                    lambda s: s.compliance_status == 'on_time'
                ))
                shift_compliance = round(on_time / len(shifts) * 100, 1)
        except Exception:
            pass

        # Pending leaves
        pending_leaves = sudo_env['hr.leave'].search_count([
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'confirm'),
        ])

        # ── Labor Cost Estimate ──
        # Hourly rate from contracts
        contracts = sudo_env['hr.contract'].search([
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'open'),
        ])
        total_monthly_wage = sum(c.wage for c in contracts)
        std_hours_month = 176  # 22 days x 8 hours
        avg_hourly_rate = round(
            (total_monthly_wage / len(contracts) / std_hours_month)
            if contracts else 0, 0
        )
        labor_cost_period = round(total_period_hrs * avg_hourly_rate, 0)
        ot_cost = round(ot_hours * avg_hourly_rate * 1.5, 0)  # 1.5x OT rate

        # ── Charts Data ──

        # 1. Attendance by day of week
        attendance_by_day = {d: 0 for d in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']}
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for att in period_atts:
            dow = att.check_in.weekday()
            attendance_by_day[day_names[dow]] += 1

        # 2. Hours trend (8 weeks)
        hours_trend = []
        for i in range(7, -1, -1):
            ws = today - timedelta(weeks=i, days=today.weekday())
            we = ws + timedelta(days=6)
            w_atts = Attendance.search([
                ('employee_id', 'in', emp_ids),
                ('check_in', '>=', datetime.combine(ws, datetime.min.time())),
                ('check_in', '<=', datetime.combine(we, datetime.max.time())),
                ('check_out', '!=', False),
            ])
            hrs = round(sum(a.worked_hours for a in w_atts), 1)
            hours_trend.append({
                'week': ws.strftime('W%V'),
                'hours': hrs,
                'target': total_employees * 40,  # 40hr standard week
            })

        # 3. Department breakdown
        dept_breakdown = []
        departments = sudo_env['hr.department'].search([])
        for dept in departments:
            dept_emps = employees.filtered(lambda e: e.department_id == dept)
            if not dept_emps:
                continue
            dept_atts = Attendance.search([
                ('employee_id', 'in', dept_emps.ids),
                ('check_in', '>=', datetime.combine(date_from, datetime.min.time())),
                ('check_in', '<=', datetime.combine(date_to, datetime.max.time())),
                ('check_out', '!=', False),
            ])
            dept_hrs = round(sum(a.worked_hours for a in dept_atts), 1)
            dept_target = len(dept_emps) * weekday_count * 8
            dept_breakdown.append({
                'name': dept.name,
                'headcount': len(dept_emps),
                'hours': dept_hrs,
                'target': dept_target,
                'utilization': round(
                    (dept_hrs / dept_target * 100) if dept_target else 0, 1
                ),
            })
        dept_breakdown.sort(key=lambda x: x['utilization'], reverse=True)

        # 4. Top employees by hours
        emp_hours = defaultdict(float)
        for att in period_atts:
            emp_hours[att.employee_id.id] += att.worked_hours

        top_employees = []
        for emp in employees:
            hrs = round(emp_hours.get(emp.id, 0), 1)
            ct = sudo_env['hr.contract'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'open'),
            ], limit=1)
            hourly = round(
                (ct.wage / std_hours_month) if ct and ct.wage else 0, 0
            )
            top_employees.append({
                'id': emp.id,
                'name': emp.name,
                'department': emp.department_id.name or '',
                'hours': hrs,
                'target': weekday_count * 8,
                'utilization': round(
                    (hrs / (weekday_count * 8) * 100)
                    if weekday_count else 0, 1
                ),
                'hourly_rate': hourly,
                'labor_cost': round(hrs * hourly, 0),
            })
        top_employees.sort(key=lambda x: x['hours'], reverse=True)

        # ── Phase F: OT Cost Breakdown by Type ──
        ot_breakdown = []
        try:
            # Use attendance overtime_hours for breakdown
            ot_atts = Attendance.search([
                ('employee_id', 'in', emp_ids),
                ('check_in', '>=', datetime.combine(date_from, datetime.min.time())),
                ('check_in', '<=', datetime.combine(date_to, datetime.max.time())),
                ('check_out', '!=', False),
                ('overtime_hours', '>', 0),
            ])
            weekday_ot = 0
            weekend_ot = 0
            for att in ot_atts:
                if att.check_in.weekday() >= 5:
                    weekend_ot += att.overtime_hours
                else:
                    weekday_ot += att.overtime_hours
            ot_breakdown = [
                {
                    'type': 'Weekday OT',
                    'hours': round(weekday_ot, 1),
                    'cost': round(weekday_ot * avg_hourly_rate * 1.5, 0),
                    'rate': 1.5,
                },
                {
                    'type': 'Weekend OT',
                    'hours': round(weekend_ot, 1),
                    'cost': round(weekend_ot * avg_hourly_rate * 2.0, 0),
                    'rate': 2.0,
                },
            ]
            ot_hours = round(weekday_ot + weekend_ot, 1)
            ot_cost = round(
                weekday_ot * avg_hourly_rate * 1.5 +
                weekend_ot * avg_hourly_rate * 2.0, 0
            )
        except Exception:
            pass

        # ── Phase F: Employee Utilization Heatmap ──
        # Last 14 days × top 15 employees
        heatmap_data = []
        heatmap_dates = []
        hm_start = today - timedelta(days=13)
        for i in range(14):
            d = hm_start + timedelta(days=i)
            heatmap_dates.append(d.strftime('%d %b'))

        # Take top 15 by hours
        top_15 = sorted(
            [(eid, hrs) for eid, hrs in emp_hours.items()],
            key=lambda x: x[1], reverse=True
        )[:15]

        for eid, _ in top_15:
            emp = sudo_env['hr.employee'].browse(eid)
            daily_hours = []
            for i in range(14):
                d = hm_start + timedelta(days=i)
                day_atts = Attendance.search([
                    ('employee_id', '=', eid),
                    ('check_in', '>=', datetime.combine(d, datetime.min.time())),
                    ('check_in', '<', datetime.combine(
                        d + timedelta(days=1), datetime.min.time()
                    )),
                    ('check_out', '!=', False),
                ])
                hrs = round(sum(a.worked_hours for a in day_atts), 1)
                daily_hours.append(hrs)
            heatmap_data.append({
                'name': emp.name[:20],
                'department': emp.department_id.name or '',
                'hours': daily_hours,
            })

        # ── Phase F: Labor Cost Forecast (12 weeks) ──
        # Trailing 8-week average projected forward 12 weeks
        recent_costs = []
        for trend in hours_trend:
            if trend['hours'] > 0:
                recent_costs.append(trend['hours'] * avg_hourly_rate)

        avg_weekly_cost = (
            sum(recent_costs) / len(recent_costs)
        ) if recent_costs else 0

        labor_forecast = []
        for i in range(1, 13):
            future_week = today + timedelta(weeks=i)
            # Simple linear with slight growth assumption (0.5% per week)
            projected = avg_weekly_cost * (1 + 0.005 * i)
            labor_forecast.append({
                'week': future_week.strftime('W%V'),
                'date': future_week.strftime('%d %b'),
                'projected': round(projected, 0),
                'lower': round(projected * 0.9, 0),
                'upper': round(projected * 1.1, 0),
            })

        # ── Phase F: Absence Impact Analysis ──
        Leave = sudo_env['hr.leave']
        leave_domain = [
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'validate'),
            ('request_date_from', '>=', date_from),
            ('request_date_to', '<=', date_to),
        ]
        try:
            leaves = Leave.search(leave_domain)
        except Exception:
            leaves = Leave.browse()

        # Group by leave type
        leave_by_type = defaultdict(lambda: {'count': 0, 'days': 0.0})
        for lv in leaves:
            type_name = lv.holiday_status_id.name or _('Other')
            leave_by_type[type_name]['count'] += 1
            leave_by_type[type_name]['days'] += lv.number_of_days or 0

        absence_data = []
        total_leave_days = 0
        for name, vals in sorted(
            leave_by_type.items(),
            key=lambda x: x[1]['days'], reverse=True
        ):
            cost_impact = round(vals['days'] * 8 * avg_hourly_rate, 0)
            absence_data.append({
                'type': name,
                'count': vals['count'],
                'days': round(vals['days'], 1),
                'cost_impact': cost_impact,
            })
            total_leave_days += vals['days']

        # Pending leaves
        pending_leaves = Leave.search_count([
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'confirm'),
        ])

        return {
            'kpis': {
                'total_employees': total_employees,
                'present_today': present_today,
                'absent_today': absent_today,
                'presence_rate': presence_rate,
                'avg_hours_week': avg_hours_week,
                'total_hours': total_period_hrs,
                'standard_hours': standard_hours,
                'utilization_rate': utilization_rate,
                'ot_hours': ot_hours,
                'ot_cost': ot_cost,
                'pending_ot': pending_ot,
                'pending_leaves': pending_leaves,
                'shift_compliance': shift_compliance,
                'total_shifts': total_shifts,
                'labor_cost': labor_cost_period,
                'avg_hourly_rate': avg_hourly_rate,
                'total_leave_days': round(total_leave_days, 1),
                'leave_cost_impact': round(
                    total_leave_days * 8 * avg_hourly_rate, 0
                ),
            },
            'attendance_by_day': attendance_by_day,
            'hours_trend': hours_trend,
            'dept_breakdown': dept_breakdown,
            'employees': top_employees,
            'ot_breakdown': ot_breakdown,
            'utilization_heatmap': {
                'dates': heatmap_dates,
                'employees': heatmap_data,
            },
            'labor_forecast': labor_forecast,
            'absence_impact': absence_data,
            'period': {
                'from': str(date_from),
                'to': str(date_to),
            },
        }

    # ==========================================
    # PHASE C: BUDGET vs ACTUAL API
    # ==========================================
    @api.model
    def get_budget_vs_actual_data(self, scenario_id):
        """Return budget vs actual data for a scenario.

        Pulls actual payroll costs from hr.payslip and compares
        to forecasted costs from the scenario's projections.
        """
        scenario = self.sudo().browse(scenario_id)
        if not scenario.exists():
            return {'months': [], 'departments': [], 'summary': {}}

        sudo_env = self.sudo().env
        company = scenario.company_id or sudo_env.company

        # Get forecast data from monthly projections
        projections = scenario.monthly_projection_ids.sorted(
            key=lambda p: (p.year, int(p.month))
        )
        forecast_by_month = {}
        for proj in projections:
            key = f"{proj.year}-{proj.month.zfill(2)}"
            forecast_by_month[key] = {
                'period': proj.period_label,
                'forecast_cost': proj.total_cost_to_company,
                'forecast_headcount': proj.headcount,
            }

        # Get actual payroll costs from hr.payslip
        # Find payslips in the scenario's fiscal year + company
        fy = scenario.fiscal_year or fields.Date.today().year
        date_start = fields.Date.from_string(f"{fy}-01-01")
        date_end = fields.Date.from_string(f"{fy}-12-31")

        payslip_domain = [
            ('state', '=', 'done'),
            ('company_id', '=', company.id),
            ('date_from', '>=', date_start),
            ('date_to', '<=', date_end),
        ]

        payslips = sudo_env['hr.payslip'].search(payslip_domain)

        # Group actuals by month
        actual_by_month = defaultdict(lambda: {'cost': 0, 'headcount': set()})
        for slip in payslips:
            month_key = slip.date_from.strftime('%Y-%m')
            # Get total from payslip lines
            total = sum(slip.line_ids.filtered(
                lambda l: l.category_id.code in ('GROSS', 'NET', 'COMP')
            ).mapped('total'))
            if not total:
                # Fallback: use contract wage
                total = slip.contract_id.wage if slip.contract_id else 0
            actual_by_month[month_key]['cost'] += total
            actual_by_month[month_key]['headcount'].add(slip.employee_id.id)

        # Merge forecast + actual into timeline
        all_months = sorted(set(
            list(forecast_by_month.keys()) +
            list(actual_by_month.keys())
        ))

        monthly_data = []
        total_forecast = 0
        total_actual = 0
        for month in all_months:
            fc = forecast_by_month.get(month, {})
            ac = actual_by_month.get(month, {'cost': 0, 'headcount': set()})
            f_cost = fc.get('forecast_cost', 0)
            a_cost = ac['cost']
            variance = f_cost - a_cost
            total_forecast += f_cost
            total_actual += a_cost

            monthly_data.append({
                'period': fc.get('period', month),
                'month_key': month,
                'forecast_cost': f_cost,
                'actual_cost': a_cost,
                'variance': variance,
                'variance_pct': round(
                    (variance / f_cost * 100) if f_cost else 0, 1
                ),
                'forecast_headcount': fc.get('forecast_headcount', 0),
                'actual_headcount': len(ac['headcount']),
            })

        # Department breakdown (actual vs budget)
        dept_data = defaultdict(lambda: {'forecast': 0, 'actual': 0})
        forecasts = scenario.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        )
        for f in forecasts:
            dept_name = f.department_id.name or _('No Department')
            dept_data[dept_name]['forecast'] += f.forecast_total_cost

        for slip in payslips:
            dept_name = slip.employee_id.department_id.name or _('No Department')
            total = sum(slip.line_ids.filtered(
                lambda l: l.category_id.code in ('GROSS', 'NET', 'COMP')
            ).mapped('total'))
            if not total:
                total = slip.contract_id.wage if slip.contract_id else 0
            dept_data[dept_name]['actual'] += total

        departments = []
        for name, vals in sorted(dept_data.items()):
            departments.append({
                'name': name,
                'forecast': vals['forecast'],
                'actual': vals['actual'],
                'variance': vals['forecast'] - vals['actual'],
            })

        # Audit trail
        audit_entries = []
        for entry in scenario.approval_ids[:20]:
            audit_entries.append({
                'date': str(entry.create_date),
                'user': entry.user_id.name,
                'action': entry.action,
                'from_state': entry.from_state or '',
                'to_state': entry.to_state or '',
                'note': entry.note or '',
            })

        return {
            'months': monthly_data,
            'departments': departments,
            'audit': audit_entries,
            'summary': {
                'total_forecast': total_forecast,
                'total_actual': total_actual,
                'total_variance': total_forecast - total_actual,
                'variance_pct': round(
                    ((total_forecast - total_actual) / total_forecast * 100)
                    if total_forecast else 0, 1
                ),
                'months_with_data': len([
                    m for m in monthly_data if m['actual_cost'] > 0
                ]),
                'months_total': len(monthly_data),
                'scenario_budget': scenario.budget_amount or 0,
                'budget_utilization': round(
                    (total_actual / scenario.budget_amount * 100)
                    if scenario.budget_amount else 0, 1
                ),
            },
        }

    # ==========================================
    # PHASE D: ADVANCED ANALYTICS API
    # ==========================================
    @api.model
    def get_advanced_analytics_data(self, scenario_id):
        """Return advanced analytics data for the Analytics tab.

        D1: Compa-ratio scatter (compa ratio vs increase %)
        D2: Department cost heatmap (dept × cost component matrix)
        D3: Component waterfall (current → forecast breakdown)
        D4: Total rewards summary
        """
        scenario = self.sudo().browse(scenario_id)
        if not scenario.exists():
            return {}

        forecasts = scenario.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        )

        # ─── D1: Compa-Ratio Scatter ───
        scatter_data = []
        for f in forecasts:
            compa = f.contract_id.compa_ratio if f.contract_id else 0
            rating = int(f.employee_id.wfp_performance_rating or '0')
            scatter_data.append({
                'name': f.employee_id.name,
                'department': f.department_id.name or '',
                'job': f.job_id.name or '',
                'compa_ratio': round(compa, 2) if compa else 0,
                'increase_pct': round(f.increase_pct, 2),
                'increase_amount': f.increase_amount,
                'current_base': f.current_base,
                'forecast_base': f.forecast_base,
                'performance': rating,
                'flight_risk': f.employee_id.wfp_flight_risk or 'low',
                'potential': f.employee_id.wfp_potential or 'medium',
                'grade': (
                    f.contract_id.grade_id.name
                    if f.contract_id and f.contract_id.grade_id else ''
                ),
            })

        # ─── D2: Department Cost Heatmap ───
        dept_components = defaultdict(lambda: {
            'base': 0, 'allowances': 0, 'employer_cost': 0,
            'gross': 0, 'total': 0, 'headcount': 0,
        })
        for f in forecasts:
            dept = f.department_id.name or _('No Department')
            dept_components[dept]['base'] += f.forecast_base
            dept_components[dept]['allowances'] += (
                f.forecast_gross - f.forecast_base
            )
            dept_components[dept]['employer_cost'] += (
                f.forecast_employer_cost
            )
            dept_components[dept]['gross'] += f.forecast_gross
            dept_components[dept]['total'] += f.forecast_total_cost
            dept_components[dept]['headcount'] += 1

        heatmap = []
        for dept, vals in sorted(
            dept_components.items(),
            key=lambda x: x[1]['total'], reverse=True
        ):
            hc = vals['headcount'] or 1
            heatmap.append({
                'department': dept,
                'headcount': vals['headcount'],
                'base_avg': round(vals['base'] / hc),
                'allowance_avg': round(vals['allowances'] / hc),
                'employer_avg': round(vals['employer_cost'] / hc),
                'total_avg': round(vals['total'] / hc),
                'base_total': vals['base'],
                'allowance_total': vals['allowances'],
                'employer_total': vals['employer_cost'],
                'total': vals['total'],
            })

        # ─── D3: Component Waterfall ───
        total_current_base = sum(forecasts.mapped('current_base'))
        total_current_allowance = sum(
            f.current_gross - f.current_base for f in forecasts
        )
        total_current_employer = sum(
            forecasts.mapped('current_employer_cost')
        )
        total_forecast_base = sum(forecasts.mapped('forecast_base'))
        total_forecast_allowance = sum(
            f.forecast_gross - f.forecast_base for f in forecasts
        )
        total_forecast_employer = sum(
            forecasts.mapped('forecast_employer_cost')
        )

        waterfall = {
            'current': {
                'base': total_current_base,
                'allowances': total_current_allowance,
                'employer': total_current_employer,
                'total': scenario.total_current_cost,
            },
            'forecast': {
                'base': total_forecast_base,
                'allowances': total_forecast_allowance,
                'employer': total_forecast_employer,
                'total': scenario.total_forecast_cost,
            },
            'delta': {
                'base': total_forecast_base - total_current_base,
                'allowances': (
                    total_forecast_allowance - total_current_allowance
                ),
                'employer': (
                    total_forecast_employer - total_current_employer
                ),
                'total': scenario.total_increase_amount,
            },
        }

        # ─── D4: Total Rewards Distribution ───
        grade_dist = defaultdict(lambda: {
            'count': 0, 'total_cost': 0, 'avg_compa': 0,
            'compa_sum': 0,
        })
        for f in forecasts:
            grade = (
                f.contract_id.grade_id.name
                if f.contract_id and f.contract_id.grade_id else 'Ungraded'
            )
            grade_dist[grade]['count'] += 1
            grade_dist[grade]['total_cost'] += f.forecast_total_cost
            compa = f.contract_id.compa_ratio if f.contract_id else 0
            grade_dist[grade]['compa_sum'] += (compa or 0)

        grades = []
        for name, vals in sorted(
            grade_dist.items(),
            key=lambda x: x[1]['total_cost'], reverse=True
        ):
            grades.append({
                'grade': name,
                'headcount': vals['count'],
                'total_cost': vals['total_cost'],
                'avg_cost': round(
                    vals['total_cost'] / vals['count']
                ) if vals['count'] else 0,
                'avg_compa': round(
                    vals['compa_sum'] / vals['count'], 2
                ) if vals['count'] else 0,
            })

        # Performance distribution
        perf_dist = defaultdict(int)
        for f in forecasts:
            rating = f.employee_id.wfp_performance_rating or '0'
            perf_dist[rating] += 1

        performance = {
            str(i): perf_dist.get(str(i), 0) for i in range(6)
        }

        return {
            'scatter': scatter_data,
            'heatmap': heatmap,
            'waterfall': waterfall,
            'grades': grades,
            'performance': performance,
            'summary': {
                'avg_compa': round(
                    sum(s['compa_ratio'] for s in scatter_data) /
                    len(scatter_data), 2
                ) if scatter_data else 0,
                'avg_increase': round(
                    sum(s['increase_pct'] for s in scatter_data) /
                    len(scatter_data), 2
                ) if scatter_data else 0,
                'high_performers': sum(
                    1 for s in scatter_data if s['performance'] >= 4
                ),
                'flight_risk_high': sum(
                    1 for s in scatter_data if s['flight_risk'] == 'high'
                ),
                'under_market': sum(
                    1 for s in scatter_data
                    if 0 < s['compa_ratio'] < 0.9
                ),
                'over_market': sum(
                    1 for s in scatter_data if s['compa_ratio'] > 1.1
                ),
            },
        }

    # ==========================================
    # PHASE G: WORKFORCE DEMAND & TALENT API
    # ==========================================
    @api.model
    def get_workforce_demand_data(self):
        """Return workforce demand, recruitment, and talent data.

        G1: Demand planning from pb_workforce (soft dependency)
        G2: Recruitment pipeline from hr.applicant
        G3: Attrition/turnover from headcount changes
        G4: Skills gap analysis from hr.employee.skill
        """
        sudo_env = self.sudo().env

        # ─── G2: Recruitment Pipeline ───
        pipeline = []
        try:
            Applicant = sudo_env['hr.applicant']
            stages = sudo_env['hr.recruitment.stage'].search(
                [], order='sequence'
            )
            total_applicants = Applicant.search_count([])
            for stage in stages:
                count = Applicant.search_count([
                    ('stage_id', '=', stage.id)
                ])
                if count > 0:
                    pipeline.append({
                        'stage': stage.name,
                        'count': count,
                        'pct': round(
                            count / total_applicants * 100
                        ) if total_applicants else 0,
                    })
        except Exception:
            total_applicants = 0

        # Recruitment by department
        dept_recruitment = []
        try:
            applicants = sudo_env['hr.applicant'].search([])
            dept_counts = defaultdict(int)
            for app in applicants:
                dept = (
                    app.department_id.name if app.department_id
                    else _('Unassigned')
                )
                dept_counts[dept] += 1
            for dept, cnt in sorted(
                dept_counts.items(),
                key=lambda x: x[1], reverse=True
            ):
                dept_recruitment.append({
                    'department': dept, 'count': cnt
                })
        except Exception:
            pass

        # ─── G1: Demand Planning (soft dependency) ───
        demand_data = []
        capabilities = []
        try:
            DemandPlan = sudo_env['pb.workforce.demand.plan']
            plans = DemandPlan.search([])
            for plan in plans:
                demand_data.append({
                    'role': plan.role_id.name if plan.role_id else '',
                    'year': plan.year or 0,
                    'planned_budget': plan.planned_budget or 0,
                    'status': plan.state or 'draft',
                })

            Capability = sudo_env['pb.workforce.capability']
            caps = Capability.search([])
            for cap in caps:
                roles = sudo_env['pb.workforce.role'].search([
                    ('capability_id', '=', cap.id)
                ])
                capabilities.append({
                    'name': cap.name,
                    'type': cap.capability_type or '',
                    'maturity': cap.maturity or '',
                    'role_count': len(roles),
                    'roles': [r.name for r in roles],
                })
        except Exception:
            pass

        # ─── G3: Attrition / Turnover ───
        attrition = []
        try:
            HChange = sudo_env['wfp.headcount.change']
            changes = HChange.search([], order='effective_date desc')
            hire_count = 0
            exit_count = 0
            promo_count = 0
            for ch in changes:
                if ch.change_type == 'hire':
                    hire_count += 1
                elif ch.change_type == 'attrition':
                    exit_count += 1
                elif ch.change_type == 'promotion':
                    promo_count += 1

            employees = sudo_env['hr.employee'].search_count([
                ('active', '=', True)
            ])
            turnover_rate = round(
                (exit_count / employees * 100) if employees else 0, 1
            )
            attrition = {
                'hires': hire_count,
                'exits': exit_count,
                'promotions': promo_count,
                'total_employees': employees,
                'turnover_rate': turnover_rate,
                'net_change': hire_count - exit_count,
            }
        except Exception:
            attrition = {
                'hires': 0, 'exits': 0, 'promotions': 0,
                'total_employees': 0, 'turnover_rate': 0,
                'net_change': 0,
            }

        # ─── G4: Skills Gap Analysis ───
        skills_data = []
        try:
            EmpSkill = sudo_env['hr.employee.skill']
            emp_skills = EmpSkill.search([])

            skill_coverage = defaultdict(lambda: {
                'count': 0, 'levels': defaultdict(int)
            })
            for es in emp_skills:
                name = es.skill_id.name if es.skill_id else 'Unknown'
                skill_coverage[name]['count'] += 1
                level = (
                    es.skill_level_id.name if es.skill_level_id
                    else 'No Level'
                )
                skill_coverage[name]['levels'][level] += 1

            total_emp = sudo_env['hr.employee'].search_count([
                ('active', '=', True)
            ])
            for name, vals in sorted(
                skill_coverage.items(),
                key=lambda x: x[1]['count'], reverse=True
            )[:20]:  # Top 20 skills
                skills_data.append({
                    'skill': name,
                    'employees': vals['count'],
                    'coverage_pct': round(
                        vals['count'] / total_emp * 100
                    ) if total_emp else 0,
                    'levels': dict(vals['levels']),
                })
        except Exception:
            pass

        return {
            'pipeline': pipeline,
            'total_applicants': total_applicants if pipeline else 0,
            'dept_recruitment': dept_recruitment,
            'demand_plans': demand_data,
            'capabilities': capabilities,
            'attrition': attrition,
            'skills': skills_data,
        }
