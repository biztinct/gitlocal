# -*- coding: utf-8 -*-
"""The two places the rest of the product can now name a vendor.

BOTH INHERITS LIVE HERE, IN THE MODULE THAT OWNS THE MODEL THEY POINT AT. That
is what makes `-i pb_vendor_access` sufficient: neither `pb_assets` nor
`pb_budget` has to be upgraded, neither has a file changed, and a database
without this module installed is exactly as it was.

BOTH FREE-TEXT COLUMNS KEEP WORKING. `pb.asset.supplier_note` ("Bought from")
and `pb.budget.expense.supplier` are still there, still writable, still on their
screens. That is not politeness — those columns hold thousands of characters of
history typed before this register existed, and a phase that replaced them with
an empty many2one would delete that history by making it invisible. The pointer
is the BETTER answer where somebody has bothered to make it; the text is the
answer everywhere else, and both are shown.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PbAssetVendor(models.Model):
    _inherit = 'pb.asset'

    vendor_id = fields.Many2one(
        'pb.vendor', string='Bought from (register)', index=True,
        ondelete='set null',
        help='The supplier on the vendor register. Leave it empty and the '
             '"Bought from" line beside it is still what the record says.')

    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        """Fill the free-text line in from the register, and NEVER overwrite
        something somebody typed.

        A person who wrote "Phong Vu, Q1 store" knows something the register
        does not.
        """
        for rec in self:
            if rec.vendor_id and not rec.supplier_note:
                rec.supplier_note = rec.vendor_id.name


class PbBudgetExpenseVendor(models.Model):
    """Optional, and only where `pb_budget` is installed.

    `_inherit` on a model that is not in the registry raises at load, so the
    class is registered unconditionally and the manifest carries `pb_budget` as
    a dependency — the honest way round. A build that genuinely wanted this
    module without budgets would drop this class, not the dependency.
    """
    _inherit = 'pb.budget.expense'

    vendor_id = fields.Many2one(
        'pb.vendor', string='Supplier (register)', index=True,
        ondelete='set null',
        help='Who was paid, from the vendor register. The typed "Supplier" '
             'line beside it still works and is what most rows use.')

    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        for rec in self:
            if rec.vendor_id and not rec.supplier:
                rec.supplier = rec.vendor_id.name
