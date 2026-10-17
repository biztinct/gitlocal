# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SkillAssessmentWizard(models.TransientModel):
    _name = 'skill.assessment.wizard'
    _description = 'Skill Assessment Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env.user.employee_id
    )

    assessment_type = fields.Selection([
        ('self', 'Self Assessment'),
        ('manager', 'Manager Assessment'),
        ('peer', 'Peer Assessment')
    ], string='Assessment Type', required=True, default='self')

    skill_line_ids = fields.One2many(
        'skill.assessment.wizard.line',
        'wizard_id',
        string='Skills to Assess'
    )

    notes = fields.Text(string='Notes')

    @api.model
    def default_get(self, fields_list):
        """Load employee existing skills"""
        res = super().default_get(fields_list)

        if 'employee_id' in res:
            employee = self.env['hr.employee'].browse(res['employee_id'])

            lines = []
            for employee_skill in employee.skill_ids:
                lines.append((0, 0, {
                    'skill_id': employee_skill.skill_id.id,
                    'current_level_id': employee_skill.level_id.id,
                    'current_score': employee_skill.proficiency_score
                }))

            # Add popular skills not yet in employee profile
            if len(lines) < 10:
                popular_skills = self.env['hr.skill'].search([
                    ('id', 'not in', employee.skill_ids.mapped('skill_id').ids)
                ], order='employee_count desc', limit=10 - len(lines))

                for skill in popular_skills:
                    lines.append((0, 0, {
                        'skill_id': skill.id
                    }))

            res['skill_line_ids'] = lines

        return res

    def action_save_assessment(self):
        """Save skill assessments"""
        self.ensure_one()

        for line in self.skill_line_ids:
            if line.assessed_level_id or line.assessed_score > 0:
                employee_skill = self.env['hr.employee.skill'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('skill_id', '=', line.skill_id.id)
                ], limit=1)

                vals = {
                    'employee_id': self.employee_id.id,
                    'skill_id': line.skill_id.id,
                    'level_id': line.assessed_level_id.id if line.assessed_level_id else False
                }

                # Update source-specific score
                if self.assessment_type == 'self':
                    vals['self_assessment_score'] = line.assessed_score
                elif self.assessment_type == 'manager':
                    vals['manager_assessment_score'] = line.assessed_score

                if employee_skill:
                    employee_skill.write(vals)
                    employee_skill.aggregate_proficiency_score()
                else:
                    new_skill = self.env['hr.employee.skill'].create(vals)
                    new_skill.aggregate_proficiency_score()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Assessment Saved',
                'message': f'Assessed {len(self.skill_line_ids)} skills',
                'type': 'success',
            }
        }


class SkillAssessmentWizardLine(models.TransientModel):
    _name = 'skill.assessment.wizard.line'
    _description = 'Skill Assessment Line'

    wizard_id = fields.Many2one(
        'skill.assessment.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    skill_id = fields.Many2one(
        'hr.skill',
        string='Skill',
        required=True
    )

    current_level_id = fields.Many2one(
        'hr.skill.level',
        string='Current Level',
        readonly=True
    )

    current_score = fields.Float(
        string='Current Score',
        readonly=True
    )

    assessed_level_id = fields.Many2one(
        'hr.skill.level',
        string='Assessed Level'
    )

    assessed_score = fields.Float(
        string='Assessed Score (0-100)',
        default=0.0
    )

    @api.onchange('assessed_level_id')
    def _onchange_assessed_level(self):
        """Auto-fill score from level"""
        if self.assessed_level_id:
            levels = self.env['hr.skill.level'].search([], order='level_value')
            if levels:
                max_level = max(levels.mapped('level_value'))
                self.assessed_score = (self.assessed_level_id.level_value / max_level) * 100
