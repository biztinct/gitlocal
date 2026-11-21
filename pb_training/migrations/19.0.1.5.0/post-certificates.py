# -*- coding: utf-8 -*-
"""LEARNING L1 on a database that already has this module.

Two jobs, both idempotent and neither ever fatal:

  1. **The three switches L1 added** (`renew_before_days`, `cert_reminders`,
     `cert_manager_days`) are written where there is no row at all, so they
     show on the Settings screen. Readers fall back to the same defaults in
     code either way (`post_init_hook` fires on install only — AM70).
  2. **The certificates filed before L1** are brought onto the register by
     `pb.training.certificate._backfill()`: "— certificate" rows in the CERT
     category get `training_source` (test, or claim when the name ends in a
     bracketed provider), their course / test / passed attempt or claim when
     those can be found, and a valid-until date ONLY where the test now has
     validity months (`hr_skills_survey`). A test with no validity never gets
     an invented date. The counts are logged.

(The handover named this folder 19.0.1.4.0; the live databases are already at
19.0.1.4.1, so a 19.0.1.4.0 migration would never run there. It is 19.0.1.5.0,
the version this phase ships.)
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_L1_KEYS = ('pb_training.renew_before_days', 'pb_training.cert_reminders',
            'pb_training.cert_manager_days')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _switches(env)
    try:
        with cr.savepoint():
            counts = env['pb.training.certificate']._backfill()
        _logger.info('pb_training 19.0.1.5.0: certificate back-fill %s',
                     counts)
    except Exception:                       # noqa: BLE001 — never fatal
        _logger.warning('pb_training 19.0.1.5.0: the certificate back-fill '
                        'failed; nothing was changed', exc_info=True)


def _switches(env):
    from odoo.addons.pb_training.models.training_common import DEFAULTS
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key in _L1_KEYS:
        if not icp.get_param(key):
            icp.set_param(key, DEFAULTS[key])
            added.append(key)
    _logger.info('pb_training 19.0.1.5.0: %s switch(es) materialised: %s',
                 len(added), ', '.join(added) or 'none')
