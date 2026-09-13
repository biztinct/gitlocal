# -*- coding: utf-8 -*-
"""Install-time bootstrap.

`post_init_hook` fires on INSTALL ONLY on this release, so an upgrade of an
already-installed module never reaches it. The migration scripts beside it do
the same job for `-u`, and both call the ONE entry point on each model — there
is no second implementation of "carry the old data over".

Every half is IDEMPOTENT: running them twice migrates nothing twice and
recomputes the same positions.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _env(env_or_cr):
    if hasattr(env_or_cr, 'ref'):
        return env_or_cr
    return api.Environment(env_or_cr, SUPERUSER_ID, {})


def post_init_hook(env_or_cr, registry=None):
    """Carry the old screens over, then place everybody in a band."""
    env = _env(env_or_cr)
    try:
        report = env['pb.pay.band'].sudo().migrate_legacy()
        _logger.info('pb_pay: grade migration %s', report)
    except Exception:       # noqa: BLE001 — an install must not fail on this
        _logger.exception('pb_pay: the Pay Grades migration could not run')
    try:
        report = env['pb.pay.migrate'].sudo().run()
        _logger.info('pb_pay: planning migration %s', report)
    except Exception:       # noqa: BLE001
        _logger.exception('pb_pay: the planning migration could not run')
    try:
        made = env['pb.pay.position'].sudo().recompute_all()
        _logger.info('pb_pay: %s position row(s) built', made)
    except Exception:       # noqa: BLE001
        _logger.exception('pb_pay: the first position pass could not run')
    # A fresh install runs no migration, so this is where a brand-new database
    # gets the pay-change and pay-review routes. Idempotent (ledger AM70/AM75).
    try:
        from .models.pb_pay_approval import seed_all
        seed_all(env)
    except Exception:       # noqa: BLE001
        _logger.exception('pb_pay: the default approval routes could not be '
                          'laid')
