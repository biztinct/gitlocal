# -*- coding: utf-8 -*-
"""Approval Matrix P6 — the support-access route, on an upgrade.

`post_init_hook` runs on INSTALL only (ledger AM70), and every live database
already has this module. Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_tenancy.models.support_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_tenancy: the support-access route could not be '
                          'seeded')
