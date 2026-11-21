# -*- coding: utf-8 -*-
"""One more word for the pay-line trail: "From the pay scale"."""
from odoo import fields, models


class HrContractAdvantageChange(models.Model):
    _inherit = 'hr.contract.advantage.change'

    change_source = fields.Selection(
        selection_add=[('pay_scale', 'From the pay scale')],
        # Uninstalling never deletes trail rows: they read "Manual" instead.
        ondelete={'pay_scale': lambda recs: recs.write({'change_source': 'manual'})})
