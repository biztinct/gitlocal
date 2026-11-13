# -*- coding: utf-8 -*-
"""Time and time off become roles somebody can give (rize, 2026-11-04).

Adds the "Handle everybody's time off" ability and three roles — Time and
attendance team, Time and attendance manager, Time off officer — so the
Workforce tabs no longer need Tenant administrator. post_init is not run on an
upgrade, so the catalogue is re-seeded here. Idempotent; grants nobody
anything.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import ensure_catalogue
    result = ensure_catalogue(env)
    _logger.info('pb_vendor_access 19.0.1.16.2: %s', result)
