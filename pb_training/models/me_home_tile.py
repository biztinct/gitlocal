# -*- coding: utf-8 -*-
"""LEARNING L1 — the "My certificates" card's place on the employee home.

The employee home (`pb_me_portal`, MEHOME) sorts every `/my` card into a
section through its tile registry, a module-level dict that the modules
putting tiles on `/my` are not supposed to edit in place (M-R2). An unknown
card lands under "More" with a plain icon, so this module adds its own row to
the registry from its own side, at import — no change to `pb_me_portal`.

Growth section, beside "My training" and "My training allowance"; order 204
ties with the allowance card and the page keeps the template order on a tie
(this card's template has priority 47, the allowance's 46), so it sits right
after it.
"""

import logging

_logger = logging.getLogger(__name__)

CERT_TILE = '/my/training/certificates'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home
    pb_me_home.TILES.setdefault(CERT_TILE, {
        'group': 'growth',
        'icon': 'shield',
        'tone': 'indigo',
        'seq': pb_me_home.GROUPS.index('growth') * 100 + 4,
        # No short `text`: the home page's own test wants every short text in
        # pb_me_portal's .po, so the card keeps its template's description
        # (translated in this module's .po).
    })
except Exception:                           # noqa: BLE001 — a card is not fatal
    _logger.warning('pb_training: the certificates card could not be placed '
                    'on the employee home', exc_info=True)
