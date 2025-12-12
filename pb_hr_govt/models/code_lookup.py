# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PbGovtCodeLookup(models.Model):
    _name = "pb.govt.code.lookup"
    _description = "Government Code Lookup (Province/District/Commune/Hospital/Other)"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    lookup_type = fields.Selection(
        [
            ("province", "Province/City"),
            ("district", "District"),
            ("commune", "Commune/Ward"),
            ("hospital", "Hospital"),
            ("household", "Household"),
            ("other", "Other"),
        ],
        required=True,
    )
    parent_id = fields.Many2one(
        "pb.govt.code.lookup",
        string="Parent",
        help="Use for hierarchy (e.g., district under province).",
    )
