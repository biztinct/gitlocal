# -*- coding: utf-8 -*-
"""C1 on a database that already has this module.

`post_init_hook` fires on INSTALL ONLY and never on `-u` — the Odoo 19 trap
the ledger records (AM70) — so anything an install does has to be done here as
well, for the databases that got the module before this version existed.

Guarded on `version`: with no version this is the fresh install and the hook
has already done both jobs. `if not version: return` is the shape every RIZE
migration uses and it is what makes running both on one database safe.

Both jobs are idempotent: a switch is written only where there is no row at
all, and `Seed.lay` asks the database what is already there before it creates
anything. Neither is ever fatal.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _switches(env)
    _route(env)


def _switches(env):
    from odoo.addons.pb_hr_comm.models.comm_common import DEFAULTS
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key, value in DEFAULTS.items():
        existing = icp.get_param(key)
        if existing is False or existing is None:
            icp.set_param(key, value)
            added.append(key)
    if added:
        _logger.info('pb_hr_comm: %s switch(es) materialised: %s', len(added),
                     ', '.join(added))


def _route(env):
    try:
        from odoo.addons.pb_hr_comm.models.post_approval import seed_all
        laid = seed_all(env)
        _logger.info('pb_hr_comm: the announcement route was laid for %s '
                     'compan(ies)', laid)
    except Exception:                   # noqa: BLE001 — never fail an upgrade
        _logger.warning('pb_hr_comm: the announcement route could not be '
                        'seeded', exc_info=True)
