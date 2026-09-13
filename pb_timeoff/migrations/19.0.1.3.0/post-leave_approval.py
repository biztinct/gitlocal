# -*- coding: utf-8 -*-
"""Approval Matrix P6 — pb_timeoff's default approval route, on an upgrade.

`post_init_hook` runs on INSTALL only (ledger AM70) and every live database
already has this module, so the route it ships with would never be laid. This
lays it. Every step asks the database what is already there first, so running
it beside the configuration module's own `end-` relay creates exactly one of
everything.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_timeoff.models.hr_leave_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_timeoff: the default approval route could not '
                          'be seeded')
