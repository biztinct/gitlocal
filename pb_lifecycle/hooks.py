# -*- coding: utf-8 -*-
"""Install-time bootstrap.

`post_init_hook` runs on INSTALL only; the migration beside it does the same
on `-u` (ledger AM70/AM91). Both are idempotent.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(env_or_cr, registry=None):
    env = env_or_cr if hasattr(env_or_cr, 'ref') \
        else api.Environment(env_or_cr, SUPERUSER_ID, {})
    try:
        from .models.letter_approval import seed_all
        seed_all(env)
    except Exception:       # noqa: BLE001 — an install must not die on a seed
        _logger.exception('pb_lifecycle: the letter route could not be laid')
