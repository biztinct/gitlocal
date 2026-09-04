# -*- coding: utf-8 -*-
"""A kind of thing the company hands out.

The category decides three things and nothing else: the two letters in the
asset's code, whether the item is physical or digital, and whether a new joiner
should automatically get one.
"""

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .asset_common import ASSET_KINDS

_CODE_RE = re.compile(r'^[A-Z0-9]{2,4}$')


class PbAssetCategory(models.Model):
    _name = 'pb.asset.category'
    _description = 'Asset Category'
    # `sequence` already runs physical 10-60 then digital 70-100, so it
    # carries the grouping AND the priority: the first category a screen
    # offers is a laptop, not an email account. Ordering by `kind` first
    # sorted 'digital' above 'tangible' alphabetically and made the
    # commonest thing in the register the last one anybody would pick.
    _order = 'sequence, name'

    name = fields.Char(string='Category', required=True, translate=True)
    code = fields.Char(
        string='Code', required=True, size=4,
        help='Two to four letters. They appear in the middle of every asset '
             'code, so keep them recognisable: LT for a laptop, PH for a phone.')
    kind = fields.Selection(
        ASSET_KINDS, string='Kind', required=True, default='tangible',
        help='Physical things come back when somebody leaves. Digital things '
             'are switched off instead.')
    auto_assign_at_joining = fields.Boolean(
        string='Every joiner gets one',
        help='Tick this and a joining checklist will ask for one of these '
             'before day one.')
    icon = fields.Char(
        string='Icon', default='package',
        help='The small picture this category wears on the assets board.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty to share this category with every company.')
    asset_count = fields.Integer(string='Items', compute='_compute_asset_count')

    _code_uniq = models.Constraint(
        'unique(code)',
        'Two categories cannot share the same code — the code is what makes an '
        'asset code readable.')

    @api.depends('name')
    def _compute_asset_count(self):
        Asset = self.env['pb.asset']
        for rec in self:
            rec.asset_count = Asset.search_count(
                [('category_id', '=', rec.id)]) if rec.id else 0

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s (%s)' % (rec.name or '', rec.code or '')

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not _CODE_RE.match((rec.code or '').strip().upper()):
                raise ValidationError(_(
                    "“%s” will not work as a category code. Use two to four "
                    "letters or numbers, like LT or PHN.", rec.code or ''))

    @api.onchange('code')
    def _onchange_code_upper(self):
        if self.code:
            self.code = self.code.strip().upper()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = vals['code'].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = vals['code'].strip().upper()
        return super().write(vals)
