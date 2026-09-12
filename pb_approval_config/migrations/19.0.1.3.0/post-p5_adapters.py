# -*- coding: utf-8 -*-
"""Approval Matrix P5 — relay the seed to every adapter that gained one.

`seed_adapters` is a duck-typed loop over the registry: any model that declares
`_approval_process_key` AND `_approval_seed_default` gets asked to lay its own
default route. Phase 5 added five such models, and a database that had this
module installed before them never asked.

Running it from HERE as well as from each adapter's own migration is the same
belt-and-braces the module was built with: which module an upgrade happens to
touch first is not something either end chooses, and every seed is idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_approval_config.models.seed import seed_all

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_approval_config: the adapter routes could not '
                          'be seeded')
