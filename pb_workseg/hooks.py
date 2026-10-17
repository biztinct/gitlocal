# -*- coding: utf-8 -*-
"""Install-time bootstrap.

`post_init_hook` fires on INSTALL ONLY on this release, so an upgrade of an
already-installed module never reaches it. The migration script beside it does
the same job for `-u`, and both call the ONE bootstrap on the model — there is
no second implementation of "give everybody a person".
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(env_or_cr, registry=None):
    """Give every active employment a person of its own."""
    env = env_or_cr
    if not hasattr(env_or_cr, 'ref'):      # a cursor, on older signatures
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    try:
        made = env['pb.person'].sudo().bootstrap()
        _logger.info('pb_workseg: bootstrap created %s person record(s)', made)
    except Exception:       # noqa: BLE001 — an install must not fail on this
        _logger.exception('pb_workseg: the person bootstrap could not run')
