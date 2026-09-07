# -*- coding: utf-8 -*-
"""Phase 6b — carry the old planning data over on an UPGRADE.

`post_init_hook` fires on install only, so a database that already had this
module never reaches it. This does the same job, through the same one entry
point, and is idempotent for the same reason.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        report = env['pb.pay.migrate'].sudo().run()
        _logger.info('pb_pay 19.0.2.0.0: carried over %s', report)
    except Exception:                           # noqa: BLE001
        _logger.exception('pb_pay 19.0.2.0.0: the migration could not run')
    try:
        env['pb.pay.position'].sudo().recompute_all()
    except Exception:                           # noqa: BLE001
        _logger.exception('pb_pay 19.0.2.0.0: the position pass failed')
