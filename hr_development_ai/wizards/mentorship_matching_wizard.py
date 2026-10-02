# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MentorshipMatchingWizard(models.TransientModel):
    _name = 'mentorship.matching.wizard'
    _description = 'AI Mentorship Matching Wizard'

    mentee_id = fields.Many2one(
        'hr.employee',
        string='Mentee',
        required=True,
        default=lambda self: self.env.user.employee_id
    )

    focus_area = fields.Selection([
        ('technical', 'Technical Skills'),
        ('leadership', 'Leadership Development'),
        ('career_growth', 'Career Growth'),
        ('domain_expertise', 'Domain Expertise'),
        ('soft_skills', 'Soft Skills'),
        ('general', 'General Development')
    ], string='Focus Area', required=True, default='general')

    focus_skill_ids = fields.Many2many(
        'hr.skill',
        string='Focus Skills',
        help='Specific skills you want to develop'
    )

    match_ids = fields.One2many(
        'mentorship.matching.wizard.line',
        'wizard_id',
        string='AI-Recommended Mentors'
    )

    def action_find_matches(self):
        """Find mentor matches using AI"""
        self.ensure_one()

        # Clear existing matches
        self.match_ids.unlink()

        # Get AI recommendations
        mentorship_model = self.env['hr.mentorship']
        matches = mentorship_model.ai_match_mentors(self.mentee_id.id, limit=5)

        # Create match lines
        lines = []
        for match in matches:
            lines.append((0, 0, {
                'mentor_id': match.get('mentor_id'),
                'match_score': match.get('match_score', 0) * 100,  # Convert to percentage
                'match_reason': match.get('reason', '')
            }))

        self.match_ids = lines

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mentorship.matching.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }

    def action_create_mentorship(self, mentor_id):
        """Create mentorship relationship"""
        self.ensure_one()

        match_line = self.match_ids.filtered(lambda m: m.mentor_id.id == mentor_id)

        mentorship = self.env['hr.mentorship'].create({
            'mentor_id': mentor_id,
            'mentee_id': self.mentee_id.id,
            'focus_area': self.focus_area,
            'focus_skill_ids': [(6, 0, self.focus_skill_ids.ids)],
            'matching_type': 'ai_suggested',
            'match_score': match_line.match_score / 100 if match_line else 0,
            'match_reason': match_line.match_reason if match_line else '',
            'state': 'active'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.mentorship',
            'res_id': mentorship.id,
            'view_mode': 'form',
            'target': 'current'
        }


class MentorshipMatchingWizardLine(models.TransientModel):
    _name = 'mentorship.matching.wizard.line'
    _description = 'Mentorship Match Line'

    wizard_id = fields.Many2one(
        'mentorship.matching.wizard',
        required=True,
        ondelete='cascade'
    )

    mentor_id = fields.Many2one(
        'hr.employee',
        string='Mentor',
        required=True
    )

    match_score = fields.Float(
        string='Match Score (%)',
        help='AI-calculated compatibility score'
    )

    match_reason = fields.Text(string='Why This Match?')

    def action_select_mentor(self):
        """Select this mentor"""
        self.ensure_one()
        return self.wizard_id.action_create_mentorship(self.mentor_id.id)
