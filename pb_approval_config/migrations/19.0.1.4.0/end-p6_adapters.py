# -*- coding: utf-8 -*-
"""Approval Matrix P6 — relay the seed to every adapter that gained one.

Phase 6 puts thirteen more kinds of request on the engine, and a database that
had this module installed before them never asked any of them for a default
route. `seed_adapters` is the duck-typed loop that asks; this runs it for
every company.

AN `end-` SCRIPT, AND THAT IS THE WHOLE POINT (ledger AM75). A `post-` script
runs while THIS module is being loaded, and every adapter module depends on
it — so at that moment none of them are in the registry and the loop silently
finds nothing. `end-` scripts run after the whole graph is loaded
(`odoo/modules/loading.py`, STEP 3.5).

It also mends one catalogue row's NAME. "Resignations and contract extensions"
was one row for two opposite events; the extension now has a row of its own,
so the old row should say what it is. The catalogue data file is `noupdate`,
which is right — a business may have renamed a row — so this only rewrites the
name when it is still the one that shipped.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_approval_config.models.seed import seed_all

_logger = logging.getLogger(__name__)

OLD_RESIGN_NAME = 'Resignations and contract extensions'
NEW_RESIGN_NAME = 'Resignations'


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    process = env['biz.approval.process']._by_key('resign')
    if process and process.name == OLD_RESIGN_NAME:
        process.sudo().write({'name': NEW_RESIGN_NAME})
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_approval_config: the P6 adapter routes could '
                          'not be seeded')
