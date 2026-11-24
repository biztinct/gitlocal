# -*- coding: utf-8 -*-
"""Offer letters get their own gallery group, "Hiring"."""
from odoo import api, fields, models

from .offer_common import HIRING, OFFER


class PbLetterTemplateOfferKind(models.Model):
    _inherit = 'pb.letter.template'

    # Plain labels (ledger DS-7: a lazy label in a selection stops the
    # registry load); translated as selection labels.
    pbds_kind_set = fields.Selection(selection_add=[(HIRING, 'Hiring')],
                                     ondelete={HIRING: 'set null'})
    pbds_kind = fields.Selection(selection_add=[(HIRING, 'Hiring')])

    @api.depends('letter_type', 'pbds_kind_set', 'pbds_replaces_id')
    def _compute_pbds_kind(self):
        super()._compute_pbds_kind()
        for rec in self:
            root = rec.pbds_replaces_id or rec
            if rec.letter_type == OFFER or root.letter_type == OFFER \
                    or (rec.pbds_kind_set or root.pbds_kind_set) == HIRING:
                rec.pbds_kind = HIRING
