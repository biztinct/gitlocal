# -*- coding: utf-8 -*-
"""UI chrome for the learning surfaces.

Why a model and not ``_t()`` in the JS
--------------------------------------
``_t()`` binds to the **session** language. The brief requires both languages
"switchable live" — a learner flips EN/VI inside the Journey and the whole
surface must change without a reload, because the person who needs that toggle
is usually mid-lesson and reading a Vietnamese sentence they did not expect.

So the bundle carries BOTH languages for every string, chrome included, and the
frontend picks. That means chrome has to be readable twice from the server,
which means it has to be a record. In exchange the ``.po`` workflow still owns
the translations, exactly as it does for lesson prose.
"""
from odoo import api, fields, models


class LearnString(models.Model):
    _name = 'learn.string'
    _description = 'Learn UI chrome string'
    _order = 'key'

    key = fields.Char(
        required=True, index=True,
        help="Dotted path as the frontend reads it, e.g. 'roles.crm'.")
    value = fields.Char(required=True, translate=True)

    _sql_constraints = [
        ('key_uniq', 'unique(key)', 'A chrome string key must be unique.'),
    ]

    @api.model
    def _as_map(self):
        """Flat {key: value} in the current context language."""
        return {r.key: r.value for r in self.search([])}
