# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRLearningPath(models.Model):
    _name = 'hr.learning.path'
    _description = 'Learning Path'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Learning Path Name', required=True, tracking=True, translate=True)
    description = fields.Html(string='Description', translate=True)
    sequence = fields.Integer(string='Sequence', default=10)

    category = fields.Selection([
        ('technical', 'Technical Skills'),
        ('leadership', 'Leadership'),
        ('soft_skills', 'Soft Skills'),
        ('compliance', 'Compliance'),
        ('onboarding', 'Onboarding'),
        ('certification', 'Certification Prep')
    ], string='Category', default='technical')

    level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert')
    ], string='Level', default='beginner')

    # Skills developed
    skill_ids = fields.Many2many(
        'hr.skill',
        string='Skills Developed',
        help='Skills that will be developed by completing this learning path'
    )

    # Courses in sequence
    item_ids = fields.One2many(
        'hr.learning.path.item',
        'learning_path_id',
        string='Learning Items'
    )

    item_count = fields.Integer(
        string='Items',
        compute='_compute_item_count',
        store=True
    )

    total_duration = fields.Integer(
        string='Total Duration (hours)',
        compute='_compute_total_duration',
        store=True
    )

    # Enrollments
    enrollment_ids = fields.One2many(
        'hr.learning.enrollment',
        'learning_path_id',
        string='Enrollments'
    )

    enrollment_count = fields.Integer(
        string='Enrollments',
        compute='_compute_enrollment_count',
        store=True
    )

    # AI recommendations
    is_ai_recommended = fields.Boolean(
        string='AI Recommended',
        default=False,
        help='This path was AI-generated based on skill gaps'
    )

    active = fields.Boolean(default=True)

    @api.depends('item_ids')
    def _compute_item_count(self):
        for path in self:
            path.item_count = len(path.item_ids)

    @api.depends('item_ids.estimated_duration')
    def _compute_total_duration(self):
        for path in self:
            path.total_duration = sum(path.item_ids.mapped('estimated_duration'))

    @api.depends('enrollment_ids')
    def _compute_enrollment_count(self):
        for path in self:
            path.enrollment_count = len(path.enrollment_ids.filtered(lambda e: e.state != 'cancelled'))

    def action_enroll_employee(self):
        """Enroll employee in learning path"""
        self.ensure_one()

        return {
            'name': 'Enroll in Learning Path',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.learning.enrollment',
            'view_mode': 'form',
            'context': {
                'default_learning_path_id': self.id
            },
            'target': 'new'
        }


class HRLearningPathItem(models.Model):
    _name = 'hr.learning.path.item'
    _description = 'Learning Path Item'
    _order = 'learning_path_id, sequence'

    learning_path_id = fields.Many2one(
        'hr.learning.path',
        string='Learning Path',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(string='Sequence', required=True, default=10)

    course_id = fields.Many2one(
        'slide.channel',
        string='Course',
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(related='course_id.name', string='Course Name', readonly=True)

    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Is this course required to complete the learning path?'
    )

    estimated_duration = fields.Integer(
        string='Duration (hours)',
        help='Estimated time to complete this course'
    )

    prerequisite_item_ids = fields.Many2many(
        'hr.learning.path.item',
        'learning_path_item_prerequisite_rel',
        'item_id',
        'prerequisite_id',
        string='Prerequisites',
        help='Items that must be completed before this one'
    )
