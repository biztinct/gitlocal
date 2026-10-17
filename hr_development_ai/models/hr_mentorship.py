# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HRMentorship(models.Model):
    _name = 'hr.mentorship'
    _description = 'Mentorship Relationship'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Mentorship Name', compute='_compute_name', store=True)

    mentor_id = fields.Many2one(
        'hr.employee',
        string='Mentor',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    mentee_id = fields.Many2one(
        'hr.employee',
        string='Mentee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    start_date = fields.Date(
        string='Start Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )

    end_date = fields.Date(string='End Date', tracking=True)

    # Matching information
    match_score = fields.Float(
        string='AI Match Score',
        help='AI-calculated compatibility score (0-1)'
    )

    match_reason = fields.Text(
        string='Match Rationale',
        help='Why this mentor-mentee pairing was suggested'
    )

    matching_type = fields.Selection([
        ('ai_suggested', 'AI Suggested'),
        ('manual', 'Manually Assigned'),
        ('self_selected', 'Self-Selected')
    ], string='Matching Type', default='manual', tracking=True)

    # Focus areas
    focus_skill_ids = fields.Many2many(
        'hr.skill',
        string='Focus Skills',
        help='Skills being developed through mentorship'
    )

    focus_area = fields.Selection([
        ('technical', 'Technical Skills'),
        ('leadership', 'Leadership Development'),
        ('career_growth', 'Career Growth'),
        ('domain_expertise', 'Domain Expertise'),
        ('soft_skills', 'Soft Skills'),
        ('general', 'General Development')
    ], string='Focus Area', default='general')

    goals = fields.Html(string='Mentorship Goals')

    # Schedule
    meeting_frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('as_needed', 'As Needed')
    ], string='Meeting Frequency', default='biweekly')

    # Sessions
    session_ids = fields.One2many(
        'hr.mentorship.session',
        'mentorship_id',
        string='Sessions'
    )

    session_count = fields.Integer(
        string='Session Count',
        compute='_compute_session_count',
        store=True
    )

    last_session_date = fields.Date(
        string='Last Session',
        compute='_compute_last_session',
        store=True
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    # Evaluation
    mentee_satisfaction = fields.Selection([
        ('5', 'Excellent'),
        ('4', 'Very Good'),
        ('3', 'Good'),
        ('2', 'Fair'),
        ('1', 'Poor')
    ], string='Mentee Satisfaction')

    mentor_satisfaction = fields.Selection([
        ('5', 'Excellent'),
        ('4', 'Very Good'),
        ('3', 'Good'),
        ('2', 'Fair'),
        ('1', 'Poor')
    ], string='Mentor Satisfaction')

    progress_notes = fields.Html(string='Progress Notes')

    _sql_constraints = [
        ('mentor_mentee_unique', 'unique(mentor_id, mentee_id, start_date)',
         'This mentor-mentee pairing already exists!')
    ]

    @api.depends('mentor_id', 'mentee_id')
    def _compute_name(self):
        for record in self:
            if record.mentor_id and record.mentee_id:
                record.name = f"{record.mentor_id.name} mentoring {record.mentee_id.name}"
            else:
                record.name = "New Mentorship"

    @api.depends('session_ids')
    def _compute_session_count(self):
        for record in self:
            record.session_count = len(record.session_ids)

    @api.depends('session_ids.session_date')
    def _compute_last_session(self):
        for record in self:
            if record.session_ids:
                record.last_session_date = max(record.session_ids.mapped('session_date'))
            else:
                record.last_session_date = False

    @api.constrains('mentor_id', 'mentee_id')
    def _check_self_mentoring(self):
        """Prevent self-mentoring"""
        for record in self:
            if record.mentor_id == record.mentee_id:
                raise ValidationError(_('An employee cannot mentor themselves!'))

    def action_activate(self):
        """Activate mentorship"""
        self.ensure_one()
        self.state = 'active'

    def action_put_on_hold(self):
        """Put mentorship on hold"""
        self.ensure_one()
        self.state = 'on_hold'

    def action_complete(self):
        """Complete mentorship"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'end_date': fields.Date.today()
        })

    def action_cancel(self):
        """Cancel mentorship"""
        self.ensure_one()
        self.state = 'cancelled'

    def action_schedule_session(self):
        """Schedule new mentorship session"""
        self.ensure_one()

        return {
            'name': _('Schedule Session'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.mentorship.session',
            'view_mode': 'form',
            'context': {
                'default_mentorship_id': self.id,
                'default_mentor_id': self.mentor_id.id,
                'default_mentee_id': self.mentee_id.id
            },
            'target': 'new'
        }

    @api.model
    def ai_match_mentors(self, mentee_id, limit=5):
        """
        Find best mentor matches for mentee using AI

        Args:
            mentee_id: Mentee employee ID
            limit: Number of matches to return

        Returns:
            list: Ranked list of potential mentors with match scores
        """
        mentee = self.env['hr.employee'].browse(mentee_id)

        # Build mentee profile
        mentee_profile = {
            'id': mentee.id,
            'name': mentee.name,
            'skills': [
                {'skill': s.skill_id.name, 'level': s.proficiency_score}
                for s in mentee.skill_ids
            ],
            'job': mentee.job_id.name if mentee.job_id else '',
            'department': mentee.department_id.name if mentee.department_id else '',
            'career_goals': []  # TODO: Add from development plan
        }

        # Find potential mentors (exclude mentee, their subordinates, and current mentors)
        current_mentor_ids = self.search([
            ('mentee_id', '=', mentee_id),
            ('state', 'in', ['active', 'on_hold'])
        ]).mapped('mentor_id').ids

        potential_mentors = self.env['hr.employee'].search([
            ('id', '!=', mentee_id),
            ('id', 'not in', current_mentor_ids),
            ('active', '=', True)
        ])

        # Build mentor profiles
        mentor_profiles = []
        for mentor in potential_mentors:
            mentor_profiles.append({
                'id': mentor.id,
                'name': mentor.name,
                'skills': [
                    {'skill': s.skill_id.name, 'level': s.proficiency_score}
                    for s in mentor.skill_ids
                ],
                'job': mentor.job_id.name if mentor.job_id else '',
                'department': mentor.department_id.name if mentor.department_id else '',
                'mentoring_capacity': 3,  # TODO: Calculate actual capacity
                'career_path': []  # TODO: Add career history
            })

        # Use AI to match
        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            matches = ai_provider.match_mentor(mentee_profile, mentor_profiles)

            # Return top matches
            return matches[:limit]

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"AI mentor matching failed: {e}")
            return []
