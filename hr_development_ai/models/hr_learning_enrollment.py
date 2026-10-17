# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRLearningEnrollment(models.Model):
    _name = 'hr.learning.enrollment'
    _description = 'Learning Path Enrollment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    learning_path_id = fields.Many2one(
        'hr.learning.path',
        string='Learning Path',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    learning_path_name = fields.Char(
        related='learning_path_id.name',
        string='Path Name',
        readonly=True
    )

    start_date = fields.Date(
        string='Start Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )

    target_completion_date = fields.Date(
        string='Target Completion',
        tracking=True
    )

    actual_completion_date = fields.Date(
        string='Actual Completion',
        readonly=True
    )

    # Progress tracking
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True
    )

    completed_items = fields.Integer(
        string='Completed Items',
        compute='_compute_progress',
        store=True
    )

    total_items = fields.Integer(
        related='learning_path_id.item_count',
        string='Total Items',
        readonly=True
    )

    # Status
    state = fields.Selection([
        ('enrolled', 'Enrolled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='enrolled', required=True, tracking=True)

    # Source
    enrollment_source = fields.Selection([
        ('manual', 'Manual Enrollment'),
        ('ai_recommended', 'AI Recommended'),
        ('manager_assigned', 'Manager Assigned'),
        ('self_enrolled', 'Self Enrolled')
    ], string='Source', default='manual')

    notes = fields.Html(string='Notes')

    @api.depends('learning_path_id.item_ids', 'employee_id')
    def _compute_progress(self):
        for enrollment in self:
            if not enrollment.learning_path_id or not enrollment.employee_id:
                enrollment.progress = 0
                enrollment.completed_items = 0
                continue

            total = len(enrollment.learning_path_id.item_ids)
            if total == 0:
                enrollment.progress = 0
                enrollment.completed_items = 0
                continue

            # Count completed courses
            completed = 0
            for item in enrollment.learning_path_id.item_ids:
                channel_partner = self.env['slide.channel.partner'].search([
                    ('channel_id', '=', item.course_id.id),
                    ('partner_id', '=', enrollment.employee_id.user_id.partner_id.id),
                    ('completed', '=', True)
                ], limit=1)

                if channel_partner:
                    completed += 1

            enrollment.completed_items = completed
            enrollment.progress = (completed / total) * 100 if total > 0 else 0

            # Auto-complete enrollment when all items done
            if enrollment.progress >= 100 and enrollment.state != 'completed':
                enrollment.action_complete()

    def action_start(self):
        """Start learning path"""
        self.ensure_one()
        self.state = 'in_progress'

    def action_complete(self):
        """Mark as completed"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'actual_completion_date': fields.Date.today()
        })

        # Award gamification badge if configured
        # TODO: Integrate with gamification

    def action_put_on_hold(self):
        """Put on hold"""
        self.ensure_one()
        self.state = 'on_hold'

    def action_cancel(self):
        """Cancel enrollment"""
        self.ensure_one()
        self.state = 'cancelled'
