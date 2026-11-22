# -*- coding: utf-8 -*-
"""Hiring's offer panel says which wording the letter really uses.

When a company or country has its own copy of the offer letter, the panel's
"Which letter" names the copy (the one that prints) and carries the plain
note "Using DEMO B's wording" — the studio's own sentence.
"""
from odoo import api, models


class PbHiringDocStudio(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _offer_row(self, offer, full=False):
        row = super()._offer_row(offer, full=full)
        if not full:
            return row
        tmpl = offer._pbds_offer_template()
        if tmpl and tmpl != offer.letter_template_id.sudo():
            row['template'] = tmpl.name or row.get('template', '')
            row['template_note'] = tmpl._pbds_wording_note() or ''
        return row
