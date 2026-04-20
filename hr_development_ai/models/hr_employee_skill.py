# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta


class HREmployeeSkill(models.Model):
    _inherit = 'hr.employee.skill'
    _description = 'Employee Skill - Extended'
    _order = 'employee_id, proficiency_score desc'

    # Extended fields only - base fields (employee_id, skill_id, skill_level_id, skill_type_id) inherited from hr.employee.skill
    skill_category_id = fields.Many2one(
        related='skill_id.category_id',
        string='Category',
        store=True,
        readonly=True
    )

    # Rename level_id to avoid conflict with base skill_level_id field
    level_id = fields.Many2one(
        related='skill_level_id',
        string='Proficiency Level',
        store=False,
        readonly=True
    )

    proficiency_score = fields.Float(
        string='Proficiency Score (0-100)',
        default=0.0,
        tracking=True,
        help='Aggregated proficiency score from all sources'
    )

    # Multi-source tracking
    source = fields.Selection([
        ('self', 'Self Assessment'),
        ('manager', 'Manager Assessment'),
        ('ai_inferred', 'AI Inferred from Work'),
        ('peer', 'Peer Endorsement'),
        ('certification', 'From Certification'),
        ('course', 'From Course Completion')
    ], string='Primary Source', default='self', tracking=True)

    # Source-specific scores (for weighted aggregation)
    self_assessment_score = fields.Float(string='Self Assessment Score')
    manager_assessment_score = fields.Float(string='Manager Assessment Score')
    ai_inference_score = fields.Float(string='AI Inference Score')
    peer_endorsement_score = fields.Float(string='Peer Endorsement Score')
    certification_score = fields.Float(string='Certification Score')
    course_completion_score = fields.Float(string='Course Completion Score')

    # Metadata
    confidence = fields.Float(
        string='Confidence',
        default=1.0,
        help='AI confidence score for inferred skills (0-1)'
    )

    last_used_date = fields.Date(
        string='Last Used',
        help='Last time this skill was used in work (from project tasks)'
    )

    acquired_date = fields.Date(
        string='Acquired Date',
        default=fields.Date.today
    )

    endorsement_count = fields.Integer(
        string='Endorsements',
        compute='_compute_endorsement_count',
        store=True
    )

    endorsement_ids = fields.One2many(
        'hr.skill.endorsement',
        'employee_skill_id',
        string='Endorsements'
    )

    # Evidence and notes
    evidence_text = fields.Text(
        string='Evidence',
        help='Projects, tasks, or achievements demonstrating this skill'
    )

    notes = fields.Text(string='Notes')

    # Status
    active = fields.Boolean(default=True)
    is_outdated = fields.Boolean(
        string='Outdated',
        compute='_compute_is_outdated',
        store=True,
        help='Skill not used in over 2 years'
    )

    _sql_constraints = [
        ('employee_skill_uniq', 'unique(employee_id, skill_id)',
         'An employee cannot have the same skill twice!'),
        ('proficiency_range', 'CHECK(proficiency_score >= 0 AND proficiency_score <= 100)',
         'Proficiency score must be between 0 and 100!')
    ]

    @api.depends('endorsement_ids')
    def _compute_endorsement_count(self):
        for record in self:
            record.endorsement_count = len(record.endorsement_ids)

    @api.depends('last_used_date')
    def _compute_is_outdated(self):
        two_years_ago = (datetime.now() - timedelta(days=730)).date()
        for record in self:
            if record.last_used_date and record.last_used_date < two_years_ago:
                record.is_outdated = True
            else:
                record.is_outdated = False

    @api.onchange('proficiency_score')
    def _onchange_proficiency_score(self):
        """Auto-assign level based on score"""
        if self.proficiency_score:
            levels = self.env['hr.skill.level'].search([], order='level_value')
            if levels:
                # Map score ranges to levels
                score_ranges = len(levels)
                range_size = 100 / score_ranges

                for idx, level in enumerate(levels):
                    if self.proficiency_score <= (idx + 1) * range_size:
                        self.skill_level_id = level
                        break

    def aggregate_proficiency_score(self):
        """
        Aggregate proficiency from all sources with weighted average
        Weights:
        - AI Inference from work: 40%
        - Manager assessment: 30%
        - Peer endorsements: 15%
        - Self assessment: 10%
        - Course completions: 5%
        """
        for record in self:
            total_weight = 0
            weighted_sum = 0

            sources = [
                (record.ai_inference_score, 0.40, 'ai_inferred'),
                (record.manager_assessment_score, 0.30, 'manager'),
                (record.peer_endorsement_score, 0.15, 'peer'),
                (record.self_assessment_score, 0.10, 'self'),
                (record.course_completion_score, 0.05, 'course')
            ]

            primary_source = 'self'
            max_score = 0

            for score, weight, source_name in sources:
                if score > 0:
                    weighted_sum += score * weight
                    total_weight += weight

                    if score > max_score:
                        max_score = score
                        primary_source = source_name

            if total_weight > 0:
                record.proficiency_score = weighted_sum / total_weight
                record.source = primary_source
            else:
                record.proficiency_score = 0

    def action_view_endorsements(self):
        """View endorsements for this skill"""
        self.ensure_one()
        return {
            'name': f'Endorsements for {self.skill_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.skill.endorsement',
            'view_mode': 'list,form',
            'domain': [('employee_skill_id', '=', self.id)],
            'context': {'default_employee_skill_id': self.id}
        }
