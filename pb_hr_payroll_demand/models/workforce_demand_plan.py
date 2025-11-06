# -*- coding: utf-8 -*-

import logging
from collections import defaultdict

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WorkforceDemandPlan(models.Model):
    _name = 'pb.workforce.demand.plan'
    _description = 'Workforce Demand Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, role_id, id desc'

    name = fields.Char(default='New', readonly=True, copy=False, tracking=True)
    role_id = fields.Many2one(
        'pb.workforce.role',
        required=True,
        tracking=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    year = fields.Integer(default=lambda self: fields.Date.context_today(self).year, tracking=True)
    plan_type = fields.Selection(
        selection=[
            ('shift', 'Shift & Hourly Based'),
            ('project', 'Project & Outcome Based'),
            ('hybrid', 'Hybrid'),
        ],
        default='shift',
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('review', 'In Review'),
            ('approved', 'Approved'),
            ('archived', 'Archived'),
        ],
        default='draft',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
    )
    monthly_line_ids = fields.One2many(
        'pb.workforce.demand.line',
        'plan_id',
        string='Monthly Plan',
    )
    total_headcount = fields.Float(
        compute='_compute_totals',
        digits=(16, 2),
        store=True,
        string='Planned Headcount'
    )
    total_fte = fields.Float(
        compute='_compute_totals',
        digits=(16, 2),
        store=True,
        string='Planned FTE'
    )
    total_employee_cost = fields.Monetary(
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        string='Planned Cost'
    )
    planned_budget = fields.Monetary(
        currency_field='currency_id',
        string='Budget Cap',
        tracking=True,
    )
    actual_spend = fields.Monetary(
        currency_field='currency_id',
        string='Actual Spend',
        tracking=True,
    )
    variance_amount = fields.Monetary(
        compute='_compute_variance',
        currency_field='currency_id',
        store=True,
    )
    variance_percent = fields.Float(
        compute='_compute_variance',
        store=True,
        digits=(16, 2),
    )
    escalation_needed = fields.Boolean(
        compute='_compute_variance',
        store=True,
        help='Automatically flagged if spend variance is over threshold.'
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Plan Owner',
        default=lambda self: self.env.user,
        tracking=True,
    )
    last_calculated = fields.Datetime(readonly=True)
    narrative = fields.Html(
        sanitize=True,
        help='Capture assumptions, dependencies, or mitigation plans.'
    )

    _sql_constraints = [
        ('unique_role_year', 'unique(role_id, year)', 'Duplicate demand plan for the same year is not allowed.'),
    ]

    def _compute_sequence(self):
        for plan in self:
            if plan.name == 'New':
                sequence = self.env['ir.sequence'].next_by_code('pb.workforce.demand.plan')
                plan.name = sequence or _('New')

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        plans._compute_sequence()
        return plans

    def write(self, vals):
        res = super().write(vals)
        if any(key in vals for key in ['monthly_line_ids', 'planned_budget', 'actual_spend']):
            self._compute_totals()
            self._compute_variance()
        return res

    @api.depends('monthly_line_ids.employees_required', 'monthly_line_ids.fte_per_month',
                 'monthly_line_ids.employee_cost')
    def _compute_totals(self):
        for plan in self:
            headcount = sum(plan.monthly_line_ids.mapped('employees_required'))
            fte = sum(plan.monthly_line_ids.mapped('fte_per_month'))
            cost = sum(plan.monthly_line_ids.mapped('employee_cost'))
            plan.total_headcount = headcount
            plan.total_fte = fte
            plan.total_employee_cost = cost
            plan.last_calculated = fields.Datetime.now()

    @api.depends('total_employee_cost', 'planned_budget', 'actual_spend')
    def _compute_variance(self):
        for plan in self:
            baseline = plan.planned_budget or plan.total_employee_cost or 0.0
            actual = plan.actual_spend or plan.total_employee_cost or 0.0
            variance = actual - baseline
            plan.variance_amount = variance
            plan.variance_percent = baseline and (variance / baseline) * 100.0 or 0.0
            plan.escalation_needed = abs(plan.variance_percent) >= 10.0

    def action_submit(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_archive(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_role(self):
        self.ensure_one()
        if not self.role_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.workforce.role',
            'res_id': self.role_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def get_dashboard_snapshot(self, year=False, capability_id=False, role_id=False):
        domain = []
        if year:
            domain.append(('year', '=', year))
        if role_id:
            domain.append(('role_id', '=', role_id))
        elif capability_id:
            domain.append(('role_id.capability_id', '=', capability_id))

        plans = self.search(domain)
        currency = plans[:1].currency_id or self.env.company.currency_id
        totals = {
            'plan_count': len(plans),
            'role_count': len(plans.mapped('role_id')),
            'capability_count': len(plans.mapped('role_id.capability_id')),
            'total_headcount': sum(plans.mapped('total_headcount')),
            'total_cost': sum(plans.mapped('total_employee_cost')),
            'variance_amount': sum(plans.mapped('variance_amount')),
            'currency_symbol': currency.symbol,
            'currency_position': currency.position,
            'currency_name': currency.name,
        }

        state_breakdown = {}
        for row in self.read_group(domain, ['state'], ['state']):
            state_breakdown[row['state']] = row.get('state_count', row.get('__count', 0))

        month_series = []
        line_domain = [('plan_id', 'in', plans.ids)]
        line_data = self.env['pb.workforce.demand.line'].read_group(
            line_domain,
            ['month', 'employees_required:sum', 'employee_cost:sum', 'variance_headcount:sum', 'variance_cost:sum'],
            ['month'],
            lazy=False,
        )
        month_lookup = {item['month']: item for item in line_data}
        for idx, month_name in enumerate(self.env['pb.workforce.demand.line']._get_month_selection(), start=1):
            code, label = month_name
            row = month_lookup.get(code, {})
            month_series.append({
                'month': label,
                'employees': row.get('employees_required_sum', 0.0),
                'cost': row.get('employee_cost_sum', 0.0),
                'variance': row.get('variance_cost_sum', 0.0),
            })

        quadrant_counts = defaultdict(int)
        for role in plans.mapped('role_id'):
            quadrant_counts[role.segmentation_quadrant] += 1

        top_variances = sorted(
            plans,
            key=lambda p: abs(p.variance_amount or 0.0),
            reverse=True
        )[:5]

        top_variance_rows = [{
            'plan_id': plan.id,
            'plan_name': plan.name,
            'role': plan.role_id.name,
            'capability': plan.role_id.capability_id.name,
            'variance_amount': plan.variance_amount,
            'variance_percent': plan.variance_percent,
            'state': plan.state,
        } for plan in top_variances]

        payload = {
            'totals': totals,
            'states': state_breakdown,
            'month_series': month_series,
            'quadrants': quadrant_counts,
            'top_variances': top_variance_rows,
        }
        _logger.info(
            'Workforce demand snapshot domain=%s filters(year=%s, capability=%s, role=%s) totals=%s states=%s month_rows=%s top_variances=%s',
            domain,
            year,
            capability_id,
            role_id,
            totals,
            state_breakdown,
            len(month_series),
            len(top_variance_rows),
        )
        return payload

    @api.model
    def get_dashboard_filters(self):
        current_year = fields.Date.context_today(self).year
        years_data = self.read_group([], ['year'], ['year'])
        years = sorted(
            {row['year'] for row in years_data if row.get('year')}
            | {current_year, current_year - 1},
            reverse=True,
        )
        capabilities = self.env['pb.workforce.capability'].search([('active', '=', True)], order='name')
        roles = self.env['pb.workforce.role'].search([('active', '=', True)], order='name')
        payload = {
            'years': years[:6],
            'capabilities': [{'id': cap.id, 'name': cap.name} for cap in capabilities],
            'roles': [{'id': role.id, 'name': f'{role.name} ({role.capability_id.display_name})'} for role in roles],
        }
        _logger.info(
            'Workforce demand dashboard filters years=%s capabilities=%s roles=%s',
            payload['years'],
            len(payload['capabilities']),
            len(payload['roles']),
        )
        return payload


class WorkforceDemandLine(models.Model):
    _name = 'pb.workforce.demand.line'
    _description = 'Workforce Demand Plan Line'
    _order = 'month_index'

    plan_id = fields.Many2one(
        'pb.workforce.demand.plan',
        required=True,
        ondelete='cascade',
    )
    plan_type = fields.Selection(related='plan_id.plan_type', store=True)
    month = fields.Selection(
        selection=lambda self: self._get_month_selection(),
        required=True,
    )
    month_index = fields.Integer(compute='_compute_month_index', store=True)
    target_output = fields.Float(
        help='Target quantity or deliverable count for the month.'
    )
    target_projects = fields.Float(
        help='Number of projects, releases, or large initiatives to deliver.'
    )
    shifts_per_month = fields.Float(
        help='Number of shifts the role needs to cover each month.'
    )
    demand_per_shift = fields.Float(
        help='Volume per shift (units, tickets, calls, etc.).'
    )
    capacity_per_resource = fields.Float(
        help='Average monthly capacity per resource (projects or outputs).'
    )
    operator_capacity_per_shift = fields.Float(
        help='Average throughput an operator can handle per shift.'
    )
    shifts_per_employee = fields.Float(
        help='Number of shifts one employee can cover per month.',
        default=20.0,
    )
    employee_cost_unit = fields.Monetary(
        string='Cost per Employee',
        currency_field='currency_id',
        help='Monthly cost per FTE / operator.',
    )
    employees_required = fields.Float(
        compute='_compute_statistics',
        store=True,
        digits=(16, 2),
    )
    fte_per_month = fields.Float(
        compute='_compute_statistics',
        store=True,
        digits=(16, 2),
    )
    employee_cost = fields.Monetary(
        compute='_compute_statistics',
        currency_field='currency_id',
        store=True,
    )
    actual_employees = fields.Float(
        string='Actual Employees',
        digits=(16, 2),
    )
    actual_cost = fields.Monetary(
        currency_field='currency_id',
        help='Actual spend for the month.',
    )
    variance_headcount = fields.Float(
        compute='_compute_variance',
        digits=(16, 2),
        store=True,
    )
    variance_cost = fields.Monetary(
        compute='_compute_variance',
        currency_field='currency_id',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='plan_id.currency_id',
        store=True,
    )
    note = fields.Char()

    @staticmethod
    def _get_month_selection():
        return [
            ('01', _('January')),
            ('02', _('February')),
            ('03', _('March')),
            ('04', _('April')),
            ('05', _('May')),
            ('06', _('June')),
            ('07', _('July')),
            ('08', _('August')),
            ('09', _('September')),
            ('10', _('October')),
            ('11', _('November')),
            ('12', _('December')),
        ]

    @api.depends('month')
    def _compute_month_index(self):
        month_map = {m[0]: idx for idx, m in enumerate(self._get_month_selection(), start=1)}
        for line in self:
            line.month_index = month_map.get(line.month, 0)

    @api.depends(
        'plan_id.plan_type', 'target_projects',
        'shifts_per_month', 'demand_per_shift', 'capacity_per_resource',
        'operator_capacity_per_shift', 'shifts_per_employee', 'employee_cost_unit'
    )
    def _compute_statistics(self):
        for line in self:
            employees = 0.0
            if line.plan_type in ('project', 'hybrid'):
                capacity = line.capacity_per_resource or 0.0
                if capacity:
                    employees += (line.target_projects or 0.0) / capacity
            if line.plan_type in ('shift', 'hybrid'):
                numerator = (line.demand_per_shift or 0.0) * (line.shifts_per_month or 0.0)
                denominator = (line.operator_capacity_per_shift or 0.0) * (line.shifts_per_employee or 0.0)
                if denominator:
                    employees += numerator / denominator
            line.employees_required = max(employees, 0.0)
            line.fte_per_month = max(employees, 0.0)
            line.employee_cost = (line.employee_cost_unit or 0.0) * line.employees_required

    @api.depends('employees_required', 'actual_employees', 'employee_cost', 'actual_cost')
    def _compute_variance(self):
        for line in self:
            line.variance_headcount = (line.actual_employees or 0.0) - (line.employees_required or 0.0)
            line.variance_cost = (line.actual_cost or 0.0) - (line.employee_cost or 0.0)
