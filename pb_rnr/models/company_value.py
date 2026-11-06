# -*- coding: utf-8 -*-
"""`pb.company.value` — what the company says it cares about, as records.

A poster on a wall is a decoration. A value that every piece of praise has to
NAME is a definition: "Candour" stops being a word and becomes the forty stories
filed under it, which is the only way anybody ever learns what a company means
by one.

Five are seeded, deliberately generic and deliberately real, so the first
nomination has something to point at on the first day. They are ordinary records
— an owner renames them, reorders them, archives the ones they do not use, and
adds their own.
"""

from odoo import _, api, fields, models

from .rnr_common import VALUE_COLORS


class PbCompanyValue(models.Model):
    _name = 'pb.company.value'
    _description = 'Company value'
    _order = 'sequence, id'

    name = fields.Char(string='Value', required=True, translate=True)
    motto = fields.Char(
        string='In a sentence', translate=True,
        help='What this looks like on a Tuesday. It is shown beside the value '
             'wherever somebody has to pick one, so it is worth writing.')
    description = fields.Text(string='More about it', translate=True)
    icon = fields.Char(
        string='Icon', default='award',
        help='The name of one of the icons this product ships. Leave it as it '
             'is unless somebody has told you a different name.')
    color = fields.Selection(VALUE_COLORS, string='Colour', default='primary',
                             required=True)
    sequence = fields.Integer(string='Order', default=10)
    active = fields.Boolean(string='In use', default=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)
    nomination_count = fields.Integer(string='Times named',
                                      compute='_compute_nomination_count')

    @api.depends('name')
    def _compute_nomination_count(self):
        """How often colleagues have reached for this one.

        Counted over the AGREED praise only — a value's weight is what people
        were recognised for, not what somebody typed and had turned down.
        """
        counts = {}
        if self.ids:
            Nom = self.env['pb.rnr.nomination'].sudo()
            try:
                groups = Nom._read_group(
                    [('value_id', 'in', self.ids), ('state', '=', 'done'),
                     ('outcome', 'in', ('recognised', 'awarded'))],
                    ['value_id'], ['__count'])
                counts = {val.id: n for val, n in groups}
            except Exception:               # noqa: BLE001 — a count, never a page
                counts = {}
        for rec in self:
            rec.nomination_count = counts.get(rec.id, 0)

    def _compute_display_name(self):
        """Friendly titles are `_compute_display_name` on Odoo 19 (no name_get)."""
        for rec in self:
            rec.display_name = rec.name or _('Value')
