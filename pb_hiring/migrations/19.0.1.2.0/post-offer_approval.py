# -*- coding: utf-8 -*-
"""The two NEW routes this version adds, on an upgrade rather than an install.

`post_init_hook` runs on INSTALL only (ledger AM70), so on any database that
already has this module the offer and cover routes would never be laid — the
catalogue would show two processes with nothing published behind them, and the
first offer anybody sent in would sit on the record's own dormant ladder with
nothing in anybody's inbox.

This lays them. Every step asks the database what is already there first
(`Seed.lay` is idempotent), so running it beside the install hook creates
exactly one of everything.

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
    from odoo.addons.pb_hiring.models.offer_approval import (
        seed_all as seed_offers)
    from odoo.addons.pb_hiring.models.cover_approval import (
        seed_all as seed_covers)
    for fn, label in ((seed_offers, 'offer'),
                      (seed_covers, 'recruiter cover')):
        try:
            fn(env)
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_hiring: the default %s route could not be '
                              'seeded', label)
