# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRCareerPath(models.Model):
    _name = 'hr.career.path'
    _description = 'Career Path Template'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(string='Career Path Name', required=True, tracking=True)
    description = fields.Html(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)

    start_job_id = fields.Many2one(
        'hr.job',
        string='Starting Position',
        required=True,
        help='Entry-level position for this career path'
    )

    step_ids = fields.One2many(
        'hr.career.path.step',
        'career_path_id',
        string='Career Steps'
    )

    step_count = fields.Integer(
        string='Steps',
        compute='_compute_step_count',
        store=True
    )

    total_skills_required = fields.Integer(
        string='Total Skills',
        compute='_compute_total_skills',
        store=True
    )

    avg_time_to_complete = fields.Integer(
        string='Avg. Time (months)',
        help='Average time to complete this career path'
    )

    active = fields.Boolean(default=True)

    @api.depends('step_ids')
    def _compute_step_count(self):
        for path in self:
            path.step_count = len(path.step_ids)

    @api.depends('step_ids.job_id.skill_ids')
    def _compute_total_skills(self):
        for path in self:
            all_skills = set()
            for step in path.step_ids:
                all_skills.update(step.job_id.skill_ids.mapped('skill_id').ids)
            path.total_skills_required = len(all_skills)

    def action_view_employees_on_path(self):
        """View employees currently on this career path"""
        self.ensure_one()

        # Find employees in jobs along this path
        job_ids = [self.start_job_id.id] + self.step_ids.mapped('job_id').ids

        return {
            'name': f'Employees on {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('job_id', 'in', job_ids)]
        }


class HRCareerPathStep(models.Model):
    _name = 'hr.career.path.step'
    _description = 'Career Path Step'
    _order = 'career_path_id, sequence'

    career_path_id = fields.Many2one(
        'hr.career.path',
        string='Career Path',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(string='Step Number', required=True, default=10)

    job_id = fields.Many2one(
        'hr.job',
        string='Position',
        required=True,
        help='Target position at this step'
    )

    name = fields.Char(related='job_id.name', string='Position Name', readonly=True)

    required_skills = fields.Many2many(
        'hr.skill',
        string='Required Skills',
        compute='_compute_required_skills',
        store=True
    )

    min_time_in_current_role = fields.Integer(
        string='Min. Time in Current Role (months)',
        default=12,
        help='Minimum time required before moving to this step'
    )

    learning_path_ids = fields.Many2many(
        'hr.learning.path',
        string='Recommended Learning Paths',
        help='Learning paths to prepare for this role'
    )

    description = fields.Html(string='Description')

    @api.depends('job_id.skill_ids')
    def _compute_required_skills(self):
        for step in self:
            step.required_skills = step.job_id.skill_ids.mapped('skill_id')
