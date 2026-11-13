# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRSkill(models.Model):
    _inherit = 'hr.skill'
    _description = 'Skill - Extended'
    _order = 'category_id, name'

    name = fields.Char(string='Skill Name', required=True, translate=True, tracking=True)
    description = fields.Html(string='Description', translate=True)

    category_id = fields.Many2one(
        'hr.skill.category',
        string='Category',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # Relationships
    employee_skill_ids = fields.One2many('hr.employee.skill', 'skill_id', string='Employee Skills')
    job_skill_ids = fields.One2many('hr.job.skill', 'skill_id', string='Job Requirements')
    course_ids = fields.Many2many('slide.channel', string='Related Courses',
                                   help='Courses that teach this skill')

    # Statistics
    employee_count = fields.Integer(string='Employees with Skill', compute='_compute_employee_count', store=True)
    avg_proficiency = fields.Float(string='Average Proficiency', compute='_compute_avg_proficiency', store=True)
    demand_score = fields.Float(string='Demand Score', compute='_compute_demand_score', store=True,
                                 help='How many jobs require this skill')

    # Metadata
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index', default=0)

    @api.depends('employee_skill_ids')
    def _compute_employee_count(self):
        for skill in self:
            skill.employee_count = len(skill.employee_skill_ids.filtered(lambda s: s.employee_id.active))

    @api.depends('employee_skill_ids.proficiency_score')
    def _compute_avg_proficiency(self):
        for skill in self:
            active_skills = skill.employee_skill_ids.filtered(lambda s: s.employee_id.active)
            if active_skills:
                skill.avg_proficiency = sum(active_skills.mapped('proficiency_score')) / len(active_skills)
            else:
                skill.avg_proficiency = 0.0

    @api.depends('job_skill_ids')
    def _compute_demand_score(self):
        for skill in self:
            # Count how many jobs require this skill
            skill.demand_score = len(skill.job_skill_ids)

    def action_view_employees(self):
        """View employees with this skill"""
        self.ensure_one()
        return {
            'name': f'Employees with {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.employee_skill_ids.mapped('employee_id').ids)],
            'context': {'default_skill_id': self.id}
        }

    def action_view_courses(self):
        """View related courses"""
        self.ensure_one()
        return {
            'name': f'Courses for {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.course_ids.ids)]
        }
