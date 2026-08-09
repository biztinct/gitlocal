# -*- coding: utf-8 -*-
from odoo import fields, models


class LearnGlossaryTerm(models.Model):
    _name = 'learn.glossary.term'
    _description = 'Learn glossary term'
    _order = 'sequence, key'

    key = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    term = fields.Char(required=True, translate=True)
    definition = fields.Text(required=True, translate=True)

    _sql_constraints = [
        ('key_uniq', 'unique(key)', 'A glossary key must be unique.'),
    ]
