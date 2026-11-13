# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRSkillCategory(models.Model):
    _name = 'hr.skill.category'
    _description = 'Skill Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color Index', default=0)
    skill_ids = fields.One2many('hr.skill', 'category_id', string='Skills')
    skill_count = fields.Integer(string='Skill Count', compute='_compute_skill_count', store=True)
    active = fields.Boolean(default=True)

    @api.depends('skill_ids')
    def _compute_skill_count(self):
        for category in self:
            category.skill_count = len(category.skill_ids)
