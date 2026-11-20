# -*- coding: utf-8 -*-
"""What a page layout carries that a screen layout does not (FS-12).

`sections` keeps the page's sections (id, title per language, columns,
fields with their width); `page` keeps the rest: the header (heading and
sub-line per language, banner picture, tint), the order of the side blocks,
the pages of single companies (only offered where there is more than one
company), and each field's My Payobook tick as it was before the page was
first published ("Reset to the standard page" puts them back).
"""
from odoo import fields, models


class PbFormLayout(models.Model):
    _inherit = 'pb.form.layout'

    page = fields.Json(help='My Payobook page: header, side blocks, company pages.')
