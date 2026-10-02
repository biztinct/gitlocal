# -*- coding: utf-8 -*-

from datetime import date

from odoo import api, fields, models, _


class WorkforceRole(models.Model):
    _name = 'pb.workforce.role'
    _description = 'Workforce Role Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'capability_id, name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        string='Role Code',
        tracking=True,
        help='Short unique identifier for integrations and dashboards.'
    )
    active = fields.Boolean(default=True, tracking=True)
    capability_id = fields.Many2one(
        'pb.workforce.capability',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    description = fields.Html(sanitize=True)
    mission = fields.Char(
        string='Role Mission',
        help='Concise purpose statement for the role.'
    )
    focus_area_ids = fields.One2many(
        'pb.workforce.role.focus',
        'role_id',
        string='Focus Areas',
    )
    kpi_ids = fields.One2many(
        'pb.workforce.role.kpi',
        'role_id',
        string='Key Performance Indicators',
    )
    skill_ids = fields.Many2many(
        'hr.skill',
        'pb_workforce_hr_skill_role_rel',
        'role_id',
        'skill_id',
        string='Required Skills',
    )
    proficiency_notes = fields.Text(
        help='Clarify proficiency expectations or certifications required.'
    )
    manager_id = fields.Many2one(
        'res.users',
        string='Role Owner',
        tracking=True,
        default=lambda self: self.env.user,
    )
    color = fields.Integer()
    state = fields.Selection(
        selection=[
            ('draft', 'Design'),
            ('ready', 'Ready'),
            ('approved', 'Approved'),
            ('archived', 'Archived'),
        ],
        default='draft',
        tracking=True,
    )
    segmentation_criticality = fields.Selection(
        selection=[
            ('minimal', 'Minimal'),
            ('important', 'Important'),
            ('critical', 'Critical'),
        ],
        default='important',
        tracking=True,
    )
    segmentation_scarcity = fields.Selection(
        selection=[
            ('minimal', 'Minimal Effort'),
            ('moderate', 'Some Effort'),
            ('significant', 'Significant Effort'),
        ],
        default='moderate',
        tracking=True,
    )
    segmentation_volume = fields.Selection(
        selection=[
            ('low', 'Low Volume'),
            ('medium', 'Medium Volume'),
            ('high', 'High Volume'),
        ],
        default='medium',
        tracking=True,
    )
    segmentation_business_impact = fields.Selection(
        selection=[
            ('low', 'Low Impact'),
            ('medium', 'Moderate Impact'),
            ('high', 'High Impact'),
        ],
        default='medium',
        tracking=True,
    )
    segmentation_effort_to_find = fields.Selection(
        selection=[
            ('minimal', 'Minimal Effort'),
            ('some', 'Some Effort'),
            ('extreme', 'Significant Effort'),
        ],
        default='some',
    )
    segmentation_demand = fields.Selection(
        selection=[
            ('minimal', 'Minimal Demand'),
            ('average', 'Average Demand'),
            ('significant', 'Significant Demand'),
        ],
        default='average',
    )
    segmentation_quadrant = fields.Selection(
        selection=[
            ('streamline', 'Streamline'),
            ('build', 'Build'),
            ('protect', 'Protect'),
            ('transform', 'Transform'),
        ],
        compute='_compute_segmentation_quadrant',
        store=True,
        tracking=True,
    )
    headcount_current = fields.Float(
        string='Current Headcount',
        digits=(16, 2),
        tracking=True,
    )
    headcount_target = fields.Float(
        string='Target Headcount',
        digits=(16, 2),
        tracking=True,
    )
    headcount_gap = fields.Float(
        compute='_compute_headcount_gap',
        digits=(16, 2),
        store=True,
        help='Difference between target and current headcount.',
    )
    salary_average = fields.Monetary(
        string='Average Monthly Cost',
        currency_field='company_currency_id',
        digits=(16, 2),
    )
    total_annual_cost = fields.Monetary(
        string='Estimated Annual Cost',
        currency_field='company_currency_id',
        compute='_compute_total_annual_cost',
        digits=(16, 2),
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    demand_plan_ids = fields.One2many(
        'pb.workforce.demand.plan',
        'role_id',
        string='Demand Plans',
    )
    last_review_by = fields.Many2one('res.users', string='Last Reviewed By')
    last_review_date = fields.Date()
    next_review_date = fields.Date(compute='_compute_next_review_date')
    comment = fields.Html(
        string='Narrative',
        sanitize=True,
        help='Provide context, risks, or assumptions for this role.'
    )

    _sql_constraints = [
        ('role_code_unique', 'unique(code)', 'The role code must be unique.'),
    ]

    @api.depends('segmentation_criticality', 'segmentation_scarcity', 'segmentation_business_impact')
    def _compute_segmentation_quadrant(self):
        for role in self:
            criticality = role.segmentation_criticality
            scarcity = role.segmentation_scarcity
            impact = role.segmentation_business_impact

            if criticality == 'critical' and scarcity == 'significant':
                quadrant = 'protect'
            elif criticality == 'critical' or impact == 'high':
                quadrant = 'transform'
            elif scarcity in ('significant',) or impact == 'high':
                quadrant = 'build'
            else:
                quadrant = 'streamline'
            role.segmentation_quadrant = quadrant

    @api.depends('headcount_current', 'headcount_target')
    def _compute_headcount_gap(self):
        for role in self:
            role.headcount_gap = (role.headcount_target or 0.0) - (role.headcount_current or 0.0)

    @api.depends('salary_average', 'headcount_target')
    def _compute_total_annual_cost(self):
        for role in self:
            monthly = (role.salary_average or 0.0) * (role.headcount_target or 0.0)
            role.total_annual_cost = monthly * 12.0

    @api.depends('last_review_date')
    def _compute_next_review_date(self):
        for role in self:
            if role.last_review_date:
                role.next_review_date = fields.Date.add(role.last_review_date, months=3)
            else:
                role.next_review_date = fields.Date.context_today(role)

    def action_mark_reviewed(self):
        for role in self:
            role.last_review_date = date.today()
            role.last_review_by = self.env.user

    def action_reset_draft(self):
        for role in self:
            role.state = 'draft'

    def action_open_demand_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.workforce.demand.plan',
            'view_mode': 'list,form,graph,pivot',
            'name': _('Demand Plans - %s') % self.name,
            'domain': [('role_id', '=', self.id)],
            'context': {
                'default_role_id': self.id,
                'search_default_group_by_state': 1,
            }
        }


class WorkforceRoleFocus(models.Model):
    _name = 'pb.workforce.role.focus'
    _description = 'Workforce Role Focus Area'
    _order = 'sequence, name'

    role_id = fields.Many2one(
        'pb.workforce.role',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(required=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    success_metric = fields.Char(
        help='What good looks like for this focus area.'
    )


class WorkforceRoleKPI(models.Model):
    _name = 'pb.workforce.role.kpi'
    _description = 'Workforce Role KPI'
    _order = 'sequence, name'

    role_id = fields.Many2one(
        'pb.workforce.role',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(required=True)
    unit_of_measure = fields.Char(string='Unit')
    target_value = fields.Float()
    frequency = fields.Selection(
        selection=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annual', 'Annual'),
            ('per_event', 'Per Event'),
        ],
        default='monthly',
    )
    sequence = fields.Integer(default=10)
    description = fields.Text()
