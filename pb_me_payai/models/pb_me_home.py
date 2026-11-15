# -*- coding: utf-8 -*-
"""The "Company policies" tile on the employee home.

Placed in People beside Ask HR, from this module's side at import (the
`pb_training/models/me_home_tile.py` precedent; pb_me_portal is not edited).
The tile is drawn only when the person is offered PayAI at all
(`pb.policy.answer._ready_for`): company switch on, AI account set up, a
published policy with words. Otherwise the home is exactly as it was.
"""
import logging

_logger = logging.getLogger(__name__)

POLICY_TILE = '/my/ask-policy'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home as _pbme
    _pbme.TILES.setdefault(POLICY_TILE, {
        'group': 'people',
        'icon': 'file-text',
        'tone': 'indigo',
        'seq': _pbme.GROUPS.index('people') * 100 + 2,
    })
except Exception:                       # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_me_payai: the policies tile could not be placed on '
                    'the employee home', exc_info=True)
