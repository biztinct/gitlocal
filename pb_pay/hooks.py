# -*- coding: utf-8 -*-
"""Install-time bootstrap.

`post_init_hook` fires on INSTALL ONLY on this release, so an upgrade of an
already-installed module never reaches it. The migration script beside it does
the same job for `-u`, and both call the ONE entry point on the model — there
is no second implementation of "carry the old Pay Grades over".

Both halves are IDEMPOTENT: running them twice migrates nothing twice and
recomputes the same positions.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(env_or_cr, registry=None):
    """Carry the old Pay Grades over, then place everybody in a band."""
    env = env_or_cr
    if not hasattr(env_or_cr, 'ref'):      # a cursor, on older signatures
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    try:
        report = env['pb.pay.band'].sudo().migrate_legacy()
        _logger.info('pb_pay: migration %s', report)
    except Exception:       # noqa: BLE001 — an install must not fail on this
        _logger.exception('pb_pay: the Pay Grades migration could not run')
    try:
        made = env['pb.pay.position'].sudo().recompute_all()
        _logger.info('pb_pay: %s position row(s) built', made)
    except Exception:       # noqa: BLE001
        _logger.exception('pb_pay: the first position pass could not run')
