# -*- coding: utf-8 -*-
"""Approval Matrix P5 — the four money-out routes, on an upgrade.

`post_init_hook` runs on INSTALL only (ledger), and every live database has
this module installed already — so without this the bank file, the release, the
journal and the send-out would have adapters and no route, and the first press
of any of them would be refused with "there is no approval set up for this
yet". The seed asks the database what is already there before it writes, so an
install and this migration in the same pass create exactly one of everything.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_pay_delivery.models.approval_seed import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_pay_delivery: the money-out routes could not be '
                          'seeded')
