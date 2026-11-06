# -*- coding: utf-8 -*-
"""LEARNING L2 on a database that already has this module.

Idempotent, never fatal:

  1. The new switch (`pb_training.enforce_cap`) is written where there is no
     row, so it shows on the Settings screen (readers default in code anyway).
  2. Every live day-one rule becomes one required-training rule per course
     (`kind=day_one`) and every live schedule one rule (`kind=recurring`,
     validity = how often it comes round), linked back through `rule_id` /
     `schedule_id`. The legacy rows keep running; the new morning leg skips
     anything converted, so nobody is assigned twice.

Country-pack TEMPLATES arrive through the data files (noupdate, company
empty, archived): nothing is switched on for any company here.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env['ir.config_parameter'].sudo()
    if icp.get_param('pb_training.enforce_cap') in (False, None):
        icp.set_param('pb_training.enforce_cap', '500')
    try:
        with cr.savepoint():
            env['pb.training.requirement']._convert_legacy()
    except Exception:                       # noqa: BLE001 — never fail an upgrade
        _logger.warning('pb_training: the legacy rules could not be '
                        'converted', exc_info=True)
