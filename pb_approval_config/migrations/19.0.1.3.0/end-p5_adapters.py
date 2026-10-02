# -*- coding: utf-8 -*-
"""Approval Matrix P5 — relay the seed to every adapter that gained one.

`seed_adapters` is a duck-typed loop over the registry: any model that declares
`_approval_process_key` AND `_approval_seed_default` gets asked to lay its own
default route. Phase 5 added five such models, and a database that had this
module installed before them never asked.

AN `end-` SCRIPT, AND THAT IS THE WHOLE POINT. A `post-` script runs while THIS
module is being loaded — and every adapter module depends on this one, so at
that moment `pb.records.apply`, `pb.zoho.arrival.batch` and the rest are not in
the registry yet and the loop silently finds nothing. `end-` scripts run after
every module in the graph has been loaded (`odoo/modules/loading.py`, STEP
3.5), which is the first moment the question "which models have a default route
waiting to be laid?" has its real answer.

It is belt-and-braces beside each adapter's own migration, not a replacement:
which module an upgrade happens to touch is not something either end chooses,
and a database where only ONE of them is upgraded still converges. Every seed
is idempotent, so running both changes nothing.
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
