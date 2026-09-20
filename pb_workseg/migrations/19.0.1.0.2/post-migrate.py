# -*- coding: utf-8 -*-
"""The same bootstrap, for an upgrade rather than an install.

`post_init_hook` fires on INSTALL only, so a database that gets this module
through `-u` would otherwise have the tables and no people in them.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'pb.person' not in env:
        return
    try:
        made = env['pb.person'].sudo().bootstrap()
        _logger.info('pb_workseg: bootstrap created %s person record(s)', made)
    except Exception:       # noqa: BLE001
        _logger.exception('pb_workseg: the person bootstrap could not run')
