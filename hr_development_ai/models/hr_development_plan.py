# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRDevelopmentPlan(models.Model):
    _name = 'hr.development.plan'
    _description = 'Individual Development Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Plan Name', required=True, tracking=True)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    manager_id = fields.Many2one(
        related='employee_id.parent_id',
        string='Manager',
        store=True,
        readonly=True
    )

    start_date = fields.Date(
        string='Start Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )

    end_date = fields.Date(string='Target Completion', tracking=True)

    # Objectives
    objective_ids = fields.One2many(
        'hr.development.objective',
        'development_plan_id',
        string='Development Objectives'
    )

    objective_count = fields.Integer(
        string='Objectives',
        compute='_compute_objective_count',
        store=True
    )

    # Learning paths
    learning_enrollment_ids = fields.Many2many(
        'hr.learning.enrollment',
        string='Learning Enrollments',
        help='Learning paths included in this development plan'
    )

    # Mentorship
    mentorship_ids = fields.Many2many(
        'hr.mentorship',
        string='Mentorships',
        help='Mentorship relationships part of this plan'
    )

    # Focus areas
    focus_skill_ids = fields.Many2many(
        'hr.skill',
        string='Focus Skills',
        help='Key skills to develop in this plan'
    )

    career_goal = fields.Html(string='Career Goal')

    # Progress
    progress = fields.Float(
        string='Overall Progress (%)',
        compute='_compute_progress',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    # Review
    last_review_date = fields.Date(string='Last Review Date')
    next_review_date = fields.Date(string='Next Review Date')
    review_notes = fields.Html(string='Review Notes')

    @api.depends('objective_ids')
    def _compute_objective_count(self):
        for plan in self:
            plan.objective_count = len(plan.objective_ids)

    @api.depends('objective_ids.progress')
    def _compute_progress(self):
        for plan in self:
            if plan.objective_ids:
                plan.progress = sum(plan.objective_ids.mapped('progress')) / len(plan.objective_ids)
            else:
                plan.progress = 0.0

    def action_activate(self):
        """Activate development plan"""
        self.ensure_one()
        self.state = 'active'

    def action_complete(self):
        """Mark as completed"""
        self.ensure_one()
        self.state = 'completed'

    def action_cancel(self):
        """Cancel plan"""
        self.ensure_one()
        self.state = 'cancelled'

    def action_schedule_review(self):
        """Schedule review meeting"""
        self.ensure_one()

        return {
            'name': 'Schedule Review',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'context': {
                'default_name': f'Development Plan Review: {self.employee_id.name}',
                'default_partner_ids': [(6, 0, [
                    self.employee_id.user_id.partner_id.id,
                    self.manager_id.user_id.partner_id.id
                ])]
            },
            'target': 'new'
        }


class HRDevelopmentObjective(models.Model):
    _name = 'hr.development.objective'
    _description = 'Development Objective'
    _inherit = ['mail.thread']
    _order = 'development_plan_id, sequence'

    development_plan_id = fields.Many2one(
        'hr.development.plan',
        string='Development Plan',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(string='Sequence', default=10)

    name = fields.Char(string='Objective', required=True, tracking=True)
    description = fields.Html(string='Description')

    objective_type = fields.Selection([
        ('skill', 'Skill Development'),
        ('certification', 'Certification'),
        ('course', 'Course Completion'),
        ('project', 'Project/Task'),
        ('mentorship', 'Mentorship'),
        ('other', 'Other')
    ], string='Type', required=True, default='skill')

    # Related records
    skill_id = fields.Many2one('hr.skill', string='Related Skill', ondelete='set null')
    course_id = fields.Many2one('slide.channel', string='Related Course', ondelete='set null')
    task_id = fields.Many2one('project.task', string='Related Task', ondelete='set null')

    # SMART criteria
    target_date = fields.Date(string='Target Date', tracking=True)
    success_criteria = fields.Html(string='Success Criteria')

    # Progress
    progress = fields.Float(string='Progress (%)', default=0.0, tracking=True)

    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='not_started', required=True, tracking=True)

    completion_date = fields.Date(string='Completion Date', readonly=True)

    notes = fields.Text(string='Notes')

    def action_start(self):
        """Start objective"""
        self.ensure_one()
        self.state = 'in_progress'

    def action_complete(self):
        """Mark as completed"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'progress': 100.0,
            'completion_date': fields.Date.today()
        })
