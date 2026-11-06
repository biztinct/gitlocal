# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRJobSkill(models.Model):
    _name = 'hr.job.skill'
    _description = 'Job Skill Requirement'
    _order = 'job_id, is_required desc, required_level_id desc'

    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        required=True,
        ondelete='cascade',
        index=True
    )

    skill_id = fields.Many2one(
        'hr.skill',
        string='Skill',
        required=True,
        ondelete='cascade',
        index=True
    )

    skill_category_id = fields.Many2one(
        related='skill_id.category_id',
        string='Category',
        store=True,
        readonly=True
    )

    # Required by base Odoo for computed fields on hr.job
    skill_type_id = fields.Many2one(
        related='skill_id.skill_type_id',
        string='Skill Type',
        store=True,
        readonly=True
    )

    required_level_id = fields.Many2one(
        'hr.skill.level',
        string='Required Level',
        required=True
    )

    required_score = fields.Float(
        string='Required Score (0-100)',
        compute='_compute_required_score',
        store=True,
        help='Numeric score from required level'
    )

    is_required = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Is this skill required or just nice-to-have?'
    )

    weight = fields.Float(
        string='Weight',
        default=1.0,
        help='Importance weight for this skill in job matching'
    )

    description = fields.Text(
        string='Description',
        help='How this skill is used in this role'
    )

    _sql_constraints = [
        ('job_skill_uniq', 'unique(job_id, skill_id)',
         'A job cannot require the same skill twice!')
    ]

    @api.depends('required_level_id')
    def _compute_required_score(self):
        """Convert level to numeric score"""
        for record in self:
            if record.required_level_id:
                # Map level_value to 0-100 scale
                all_levels = self.env['hr.skill.level'].search([], order='level_value')
                if all_levels:
                    max_level = max(all_levels.mapped('level_value'))
                    record.required_score = (record.required_level_id.level_value / max_level) * 100
            else:
                record.required_score = 0.0


class HRJob(models.Model):
    _inherit = 'hr.job'

    skill_ids = fields.One2many(
        'hr.job.skill',
        'job_id',
        string='Required Skills'
    )

    required_skill_count = fields.Integer(
        string='Required Skills',
        compute='_compute_skill_counts',
        store=True
    )

    total_skill_count = fields.Integer(
        string='Total Skills',
        compute='_compute_skill_counts',
        store=True
    )

    @api.depends('skill_ids', 'skill_ids.is_required')
    def _compute_skill_counts(self):
        for job in self:
            job.total_skill_count = len(job.skill_ids)
            job.required_skill_count = len(job.skill_ids.filtered('is_required'))

    def action_view_skill_gaps(self):
        """View skill gaps for employees applying for this job"""
        self.ensure_one()

        return {
            'name': f'Skill Gaps for {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.skill.gap',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id}
        }
