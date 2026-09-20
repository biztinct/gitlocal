# -*- coding: utf-8 -*-
"""The two default hiring routes, on an upgrade rather than an install.

`post_init_hook` runs on INSTALL only (ledger AM70), so on any database that
already has this module the routes it ships with would never be laid. This
lays them. Every step asks the database what is already there first, so
running it beside the install hook creates exactly one of everything.

Guarded on `version`: without the guard it also runs on a fresh install, where
the hook has already done the work.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_hiring.models.requisition_approval import (
        seed_all as seed_requests)
    from odoo.addons.pb_hiring.models.jd_approval import (
        seed_all as seed_adverts)
    for fn, label in ((seed_requests, 'hiring request'),
                      (seed_adverts, 'job description')):
        try:
            fn(env)
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_hiring: the default %s route could not be '
                              'seeded', label)
