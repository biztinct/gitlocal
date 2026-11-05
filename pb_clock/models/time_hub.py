# -*- coding: utf-8 -*-
"""The Time clocks lens badge on the Time hub tab (CLOCK ledger D8): unknown
numbers with punches in the context week."""

from odoo import api, models


class PbTimeHub(models.AbstractModel):
    _inherit = 'pb.time.hub'

    @api.model
    def _extra_lens_counts(self, ctx):
        res = super()._extra_lens_counts(ctx)
        res['clocks'] = self.env['pb.clock.lens']._unknown_count(ctx.get('week_start'))
        return res
