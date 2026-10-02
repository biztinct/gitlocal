# -*- coding: utf-8 -*-

from odoo import models, fields


class HRSkillLevel(models.Model):
    _inherit = 'hr.skill.level'
    _description = 'Skill Proficiency Level - Extended'
    _order = 'level_value'

    name = fields.Char(string='Level Name', required=True, translate=True)
    level_value = fields.Integer(string='Numeric Value', required=True,
                                  help='Numeric value for comparison (e.g., 1=Beginner, 5=Expert)')
    description = fields.Text(string='Description', translate=True,
                              help='What this proficiency level means')
    color = fields.Integer(string='Color Index', default=0)

    _sql_constraints = [
        ('level_value_positive', 'CHECK(level_value > 0)', 'Level value must be positive!'),
        ('level_value_uniq', 'UNIQUE(level_value)', 'Level value must be unique!')
    ]
