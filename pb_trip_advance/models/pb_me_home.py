# -*- coding: utf-8 -*-
"""My Payobook: a card while a trip cash advance is out or being taken back
(quiet at zero: no advance, no card). Read under sudo for the caller's own
employee only (`pb.trip.advance.my_advances` refuses anybody else)."""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbMeHomeAdvance(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        try:
            data = self.env['pb.trip.advance'].my_advances(emp)
        except Exception:       # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_trip_advance: the home card failed', exc_info=True)
            data = None
        if data and data.get('count'):
            cards.append({'key': 'trip_advance',
                          'template': 'pb_trip_advance.pbme_card_advance', 'data': data})
        return cards
