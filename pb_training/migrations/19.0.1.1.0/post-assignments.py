# -*- coding: utf-8 -*-
"""E2 on a database that already has this module.

`post_init_hook` fires on INSTALL ONLY and never on `-u` — the Odoo 19 trap the
ledger records (AM70) — and every live database already has `pb_training`. So
the two things an install would have done have to be done here as well:

  1. **The switches E2 added.** Nothing BEHAVES wrong without them: every
     reader goes through `flag()`/`number()`, which fall back to the same
     defaults in code. But a switch nobody can find on the Settings screen is a
     switch nobody can turn, and one of these decides whether a new joiner's
     induction assigns itself (R181, E1's own version of this migration).
  2. **The approval route for "more time on a course".** Without it the
     request has no published route, the shim stays dormant and the record
     falls back to its own one-rung ladder — which works, but is not the
     Matrix, and the manager would never see it in their inbox.

Both are idempotent by construction: the switches are written only where there
is no row at all, and `Seed.lay` asks the database what is already there before
it creates anything.
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
    from odoo.addons.pb_training.models.training_common import DEFAULTS
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key, value in DEFAULTS.items():
        if not icp.get_param(key):
            icp.set_param(key, value)
            added.append(key)
    _logger.info('pb_training: %s switch(es) materialised: %s',
                 len(added), ', '.join(added) or 'none')


def _route(env):
    try:
        from odoo.addons.pb_training.models.delay_approval import seed_all
        laid = seed_all(env)
        _logger.info('pb_training: the "more time on a course" route was laid '
                     'for %s compan(ies)', laid)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_training: the default approval route could not '
                          'be seeded')
