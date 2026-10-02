# -*- coding: utf-8 -*-
"""`pb.pay.family` — the job families a band is drawn for.

A family is a group of jobs that share a shape of pay: Operations, Sales,
Engineering, Finance. It exists so a band can be written once for "Engineering,
level 4, Vietnam" instead of once per job title, and so the picture has
something to stack by.

The families are SUGGESTED from the job titles a company already has
(`pb.pay.bands.suggest_families`) rather than typed from nothing — a company
with fifty-two job titles should not have to invent its own taxonomy before it
can see a single band.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PbPayFamily(models.Model):
    _name = 'pb.pay.family'
    _description = 'Job family'
    _order = 'sequence, name'

    name = fields.Char(string='Job family', required=True, translate=False)
    code = fields.Char(string='Short code')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    band_ids = fields.One2many('pb.pay.band', 'family_id', string='Bands')
    band_count = fields.Integer(string='Bands', compute='_compute_band_count')

    _name_uniq = models.Constraint(
        'unique(name)',
        'Two job families cannot have the same name.')

    def _compute_band_count(self):
        counts = {}
        if self.ids:
            rows = self.env['pb.pay.band'].sudo()._read_group(
                [('family_id', 'in', self.ids)], ['family_id'], ['__count'])
            counts = {family.id: count for family, count in rows if family}
        for record in self:
            record.band_count = counts.get(record.id, 0)

    @api.constrains('name')
    def _check_name(self):
        for record in self:
            if not (record.name or '').strip():
                raise ValidationError(_("A job family needs a name."))
