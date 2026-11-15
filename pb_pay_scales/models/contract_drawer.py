# -*- coding: utf-8 -*-
"""The scale chip in the contract drawer's header.

`pb_contracts` renders any `header.extra_chips` it is handed (the generic seam
added in S8-A); this module hands it one. A chip may offer ONE of two doors:
`stage_wage` (the drawer stages that wage in the open form — nothing is
written until Save, which then follows the contract's normal approval) or
`action` (a server method on this module, e.g. "Keep this pay", which writes
a placement row and never the contract).
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbContractsScaleChip(models.AbstractModel):
    _inherit = 'pb.contracts'

    @api.model
    def _cd_header(self, contract, symbol, unmask):
        header = super()._cd_header(contract, symbol, unmask)
        try:
            chip = self.env['pb.pay.scales'].contract_chip(contract.id)
        except Exception:       # noqa: BLE001 — an extra never costs the drawer
            _logger.debug("pb_pay_scales: chip failed", exc_info=True)
            chip = None
        if chip:
            if not unmask:
                # A masked wage stays masked: no figure, no staging door.
                chip.pop('stage_wage', None)
                chip.pop('stage_label', None)
                if chip.get('tone') == 'warn':
                    chip['title'] = ''
            header.setdefault('extra_chips', []).append(chip)
        return header
