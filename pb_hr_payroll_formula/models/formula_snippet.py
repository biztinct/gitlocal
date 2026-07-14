# -*- coding: utf-8 -*-
"""W104 — Formula snippet library.

A *snippet* is a reusable Excel-formula fragment with ``${CODE}`` placeholders
(e.g. workday proration, cap-at-a-ceiling, a progressive-tax BRACKET call). The
studio inserts a snippet into an open cell editor, resolving each ``${CODE}`` to
that component's column-letter reference at INSERTION time (client-side, D-F8) —
an unresolvable placeholder is inserted verbatim so live validation flags the
cell red (C7), never silently dropped or zeroed.

C1 boundary: the model + seed data are the ONLY engine-side footprint of W104.
All CRUD RPCs and insertion logic live in ``pb_formula_studio`` (no eval-path
change here — snippets are inert text until pasted into a rule).
"""
from odoo import _, fields, models


class HrFormulaSnippet(models.Model):
    _name = 'hr.formula.snippet'
    _description = 'Formula Snippet (reusable Excel fragment)'
    _order = 'sequence, name, id'

    name = fields.Char(required=True)
    category = fields.Selection(
        [('proration', 'Proration'),
         ('cap', 'Cap / floor'),
         ('bracket', 'Bracket / rate table'),
         ('rounding', 'Rounding'),
         ('other', 'Other')],
        default='other', required=True,
        help="Groups the snippet in the studio's snippet picker.")
    body = fields.Text(
        required=True,
        help="Excel fragment with ${CODE} placeholders. Each placeholder resolves "
             "to that component's column-letter reference when inserted.")
    description = fields.Char(help="One-line hint shown beside the snippet.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help="Leave empty to share the snippet across every company.")
