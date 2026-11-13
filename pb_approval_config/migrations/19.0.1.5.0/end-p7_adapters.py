# -*- coding: utf-8 -*-
"""Approval Matrix P7 — relay the seed to every adapter that gained one.

Phase 7 connects the last of the catalogue: set-up and rules, the platform,
and the people and time doors that were still writing the moment they were
pressed. `seed_adapters` is the same duck-typed loop Phases 5 and 6 used, so
nothing here names a module — a model in the registry that has a default route
waiting gets asked for it.

AN `end-` SCRIPT, AND THAT IS THE WHOLE POINT (ledger AM75). A `post-` script
runs while THIS module is being loaded, and every adapter module depends on
it — so at that moment none of them are in the registry and the loop silently
finds nothing. `end-` scripts run after the whole graph is loaded
(`odoo/modules/loading.py`, STEP 3.5).
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
        _logger.exception('pb_approval_config: the P7 adapter routes could '
                          'not be seeded')
