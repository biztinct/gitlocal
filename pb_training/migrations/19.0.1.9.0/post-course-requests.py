# -*- coding: utf-8 -*-
"""LEARNING L5 on a database that already has this module.

`post_init_hook` fires on install only (AM70), so the two things a fresh
install does for L5 are done here as well:

  1. The four new switches (re-read cap, feedback, follow-up and its days),
     written only where there is no row at all — every reader falls back to
     the same defaults in code, the rows exist so the switches can be found.
  2. The approval route for a course request on every company (their manager,
     then the HR lead when the course costs money). `Seed.lay` asks the
     database what is already there first, so a second run lays nothing.

No data is rewritten: the new tables are empty, the new columns carry their
defaults (every course version 1, every course open to requests).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

L5_KEYS = ('pb_training.reread_cap', 'pb_training.feedback_on',
           'pb_training.followup_on', 'pb_training.followup_days')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_training.models.training_common import DEFAULTS
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key in L5_KEYS:
        if not icp.get_param(key):
            icp.set_param(key, DEFAULTS[key])
            added.append(key)
    _logger.info('pb_training: %s L5 switch(es) materialised: %s',
                 len(added), ', '.join(added) or 'none')
    try:
        from odoo.addons.pb_training.models.request_approval import seed_all
        laid = seed_all(env)
        _logger.info('pb_training: the course-request route was laid for %s '
                     'compan(ies)', laid)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_training: the default course-request route '
                          'could not be seeded')
