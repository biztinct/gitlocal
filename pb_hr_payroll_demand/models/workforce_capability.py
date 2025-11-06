# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WorkforceCapability(models.Model):
    _name = 'pb.workforce.capability'
    _description = 'Workforce Capability'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        string='Reference',
        tracking=True,
        help='Short code used when referencing the capability in dashboards.'
    )
    sequence = fields.Integer(default=10, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    capability_type = fields.Selection(
        selection=[
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
            ('enabler', 'Enabler'),
        ],
        default='primary',
        required=True,
        tracking=True,
    )
    description = fields.Html(sanitize=True)
    vision_statement = fields.Char(
        string='Outcome Statement',
        help='One line statement describing what success for this capability looks like.'
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Capability Owner',
        tracking=True,
        default=lambda self: self.env.user,
    )
    color = fields.Integer()
    maturity = fields.Selection(
        selection=[
            ('emerging', 'Emerging'),
            ('developing', 'Developing'),
            ('mature', 'Mature'),
            ('transform', 'Transformational'),
        ],
        default='developing',
        tracking=True,
        help='Subjective view of how established or modern the capability is today.'
    )
    subactivity_ids = fields.One2many(
        'pb.workforce.subactivity',
        'capability_id',
        string='Subactivities',
    )
    skill_ids = fields.Many2many(
        'pb.workforce.skill',
        'pb_workforce_skill_capability_rel',
        'capability_id',
        'skill_id',
        string='Key Skills',
    )
    role_ids = fields.One2many(
        'pb.workforce.role',
        'capability_id',
        string='Roles',
    )
    primary_role_count = fields.Integer(
        compute='_compute_role_metrics',
        store=False,
    )
    critical_role_count = fields.Integer(
        compute='_compute_role_metrics',
        store=False,
    )
    planned_fte = fields.Float(
        compute='_compute_role_metrics',
        store=False,
        digits=(16, 2),
    )
    approved_budget = fields.Monetary(
        compute='_compute_role_metrics',
        store=False,
        currency_field='company_currency_id',
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        default=lambda self: self.env.company.currency_id,
    )
    last_review_date = fields.Date(
        help='Date of the most recent portfolio review for this capability.'
    )
    next_review_date = fields.Date(
        compute='_compute_next_review_date',
        store=True,
    )
    note = fields.Html(
        string='Strategic Notes',
        sanitize=True,
        help='Capture context, priority, and upcoming initiatives.'
    )

    _sql_constraints = [
        ('capability_name_unique', 'unique(name, capability_type)',
         'Each capability type must have a unique name.'),
    ]

    @api.depends('role_ids', 'role_ids.state', 'role_ids.segmentation_quadrant',
                 'role_ids.demand_plan_ids.total_headcount', 'role_ids.demand_plan_ids.total_employee_cost')
    def _compute_role_metrics(self):
        for capability in self:
            primary_roles = capability.role_ids.filtered(lambda r: r.state != 'archived')
            capability.primary_role_count = len(primary_roles)
            capability.critical_role_count = len(primary_roles.filtered(
                lambda r: r.segmentation_quadrant in ('protect', 'transform')))
            total_fte = 0.0
            total_budget = 0.0
            for plan in capability.role_ids.mapped('demand_plan_ids'):
                total_fte += plan.total_headcount
                total_budget += plan.total_employee_cost
            capability.planned_fte = total_fte
            capability.approved_budget = total_budget

    @api.depends('last_review_date')
    def _compute_next_review_date(self):
        for capability in self:
            if capability.last_review_date:
                capability.next_review_date = fields.Date.add(capability.last_review_date, months=6)
            else:
                capability.next_review_date = False

    def action_open_roles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.workforce.role',
            'name': _('Roles for %s') % self.name,
            'view_mode': 'tree,kanban,form,pivot',
            'domain': [('capability_id', '=', self.id)],
            'context': {
                'default_capability_id': self.id,
            }
        }


class WorkforceSubactivity(models.Model):
    _name = 'pb.workforce.subactivity'
    _description = 'Workforce Subactivity'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    description = fields.Char()
    capability_id = fields.Many2one(
        'pb.workforce.capability',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    focus_level = fields.Selection(
        selection=[
            ('run', 'Run'),
            ('grow', 'Grow'),
            ('transform', 'Transform'),
        ],
        default='run',
    )
    is_automation_candidate = fields.Boolean(
        help='Flag subactivities that could benefit from automation or offshoring.'
    )


class WorkforceSkill(models.Model):
    _name = 'pb.workforce.skill'
    _description = 'Workforce Skill'
    _order = 'name'

    name = fields.Char(required=True)
    category = fields.Selection(
        selection=[
            ('technical', 'Technical'),
            ('business', 'Business'),
            ('leadership', 'Leadership'),
            ('compliance', 'Compliance'),
            ('digital', 'Digital'),
            ('other', 'Other'),
        ],
        default='technical',
    )
    description = fields.Text()
    color = fields.Integer()
    capability_ids = fields.Many2many(
        'pb.workforce.capability',
        'pb_workforce_skill_capability_rel',
        'skill_id',
        'capability_id',
        string='Capabilities',
    )
    role_ids = fields.Many2many(
        'pb.workforce.role',
        'pb_workforce_skill_role_rel',
        'skill_id',
        'role_id',
        string='Roles',
    )
    proficiency_scale = fields.Selection(
        selection=[
            ('awareness', 'Awareness'),
            ('working', 'Working'),
            ('proficient', 'Proficient'),
            ('expert', 'Expert'),
        ],
        default='working',
        help='Default proficiency required when linked to a role.'
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Skill Steward',
        default=lambda self: self.env.user,
    )

    _sql_constraints = [
        ('skill_name_unique', 'unique(name)', 'Skill names must be unique.'),
    ]
