# -*- coding: utf-8 -*-
"""Approval Matrix P7 — pb_pay's pay-band route, on an upgrade.

`post_init_hook` runs on INSTALL only (ledger AM70/AM91); every live database
already has this module. Idempotent, so it sits happily beside the
configuration module's `end-` relay.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_pay.models.bands_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_pay: the pay band route could not be laid')
