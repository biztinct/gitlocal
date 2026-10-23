# -*- coding: utf-8 -*-
"""Approval Matrix P5 — the arrivals route, on an upgrade.

`post_init_hook` runs on INSTALL only (ledger), and it is also the hook that
mints the webhook key — which is exactly why it must not be re-run. This seeds
the route and nothing else. Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_zoho_bridge.models.arrival_batch import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_zoho_bridge: the arrivals route could not be '
                          'seeded')
