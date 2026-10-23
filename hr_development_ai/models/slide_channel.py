# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    # Skills developed by this course
    skill_ids = fields.Many2many(
        'hr.skill',
        string='Skills Developed',
        help='Skills that will be developed by completing this course'
    )

    # Prerequisites
    prerequisite_skill_ids = fields.Many2many(
        'hr.skill',
        'slide_channel_prerequisite_skill_rel',
        'channel_id',
        'skill_id',
        string='Prerequisite Skills',
        help='Skills required before taking this course'
    )

    # Difficulty level
    difficulty_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert')
    ], string='Difficulty Level')

    # Learning path usage
    learning_path_item_ids = fields.One2many(
        'hr.learning.path.item',
        'course_id',
        string='Learning Paths'
    )

    learning_path_count = fields.Integer(
        string='Learning Paths',
        compute='_compute_learning_path_count',
        store=True
    )

    # Development objectives
    development_objective_ids = fields.One2many(
        'hr.development.objective',
        'course_id',
        string='Development Objectives'
    )

    # Certifications awarded
    certification_ids = fields.One2many(
        'hr.certification',
        'course_id',
        string='Certifications Awarded'
    )

    awards_certification = fields.Boolean(
        string='Awards Certification',
        default=False,
        help='Completing this course awards a certification'
    )

    certification_name = fields.Char(
        string='Certification Name',
        help='Name of the certification awarded upon completion'
    )

    # AI-generated content
    is_ai_curated = fields.Boolean(
        string='AI Curated',
        default=False,
        help='This course was recommended by AI'
    )

    @api.depends('learning_path_item_ids')
    def _compute_learning_path_count(self):
        for channel in self:
            channel.learning_path_count = len(channel.learning_path_item_ids.mapped('learning_path_id'))

    def action_view_learning_paths(self):
        """View learning paths using this course"""
        self.ensure_one()

        path_ids = self.learning_path_item_ids.mapped('learning_path_id').ids

        return {
            'name': f'Learning Paths - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.learning.path',
            'view_mode': 'list,form',
            'domain': [('id', 'in', path_ids)]
        }


class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    def write(self, vals):
        """Auto-update employee skills when course completed"""
        res = super().write(vals)

        # If course just completed, update employee skills
        if vals.get('completed'):
            for record in self:
                if record.channel_id.skill_ids and record.partner_id.employee_ids:
                    employee = record.partner_id.employee_ids[0]

                    for skill in record.channel_id.skill_ids:
                        employee_skill = self.env['hr.employee.skill'].search([
                            ('employee_id', '=', employee.id),
                            ('skill_id', '=', skill.id)
                        ], limit=1)

                        # Calculate score based on completion percentage
                        score = min(100, record.completion * 0.7)  # Max 70% from course completion

                        if employee_skill:
                            employee_skill.course_completion_score = max(
                                employee_skill.course_completion_score,
                                score
                            )
                            employee_skill.aggregate_proficiency_score()
                        else:
                            new_skill = self.env['hr.employee.skill'].create({
                                'employee_id': employee.id,
                                'skill_id': skill.id,
                                'course_completion_score': score,
                                'source': 'course',
                                'evidence_text': f'Completed course: {record.channel_id.name}'
                            })
                            new_skill.aggregate_proficiency_score()

                    # Award certification if configured
                    if record.channel_id.awards_certification:
                        self.env['hr.certification'].create({
                            'name': record.channel_id.certification_name or record.channel_id.name,
                            'employee_id': employee.id,
                            'certification_type': 'course_completion',
                            'course_id': record.channel_id.id,
                            'skill_ids': [(6, 0, record.channel_id.skill_ids.ids)]
                        })

        return res
