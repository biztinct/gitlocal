# -*- coding: utf-8 -*-
"""The "Privacy" tile's place on the employee home (pb_me_portal's registry,
extended from this side at import — M-R2, the pb_training precedent).

Under "More", beside Sign-in & security: it is looked at rarely and is not a
task. No short `text` in the registry: pb_me_portal's home test wants every
short text in its own .po, so the tile keeps its template's words (this
module's .po)."""

import logging

_logger = logging.getLogger(__name__)

PRIVACY_TILE = '/my/privacy'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home
    pb_me_home.TILES.setdefault(PRIVACY_TILE, {
        'group': 'more',
        'icon': 'check-circle',
        'tone': 'teal',
        'seq': pb_me_home.GROUPS.index('more') * 100 + 2,
    })
except Exception:                           # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_me_privacy: the privacy tile could not be placed on '
                    'the employee home', exc_info=True)
