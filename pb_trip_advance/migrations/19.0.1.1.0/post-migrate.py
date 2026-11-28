# -*- coding: utf-8 -*-
"""Owner ruling TA1: a database that already has pb_trip_advance 19.0.1.0.0
gets the default settlement route (Head of pay) for every company. On a
fresh install this file does not run (the post_init_hook lays the routes);
on a database without the module nothing runs at all."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        from odoo.addons.pb_trip_advance.models.advance_approval import seed_all
        done = seed_all(env)
        _logger.info('pb_trip_advance: settlement routes laid for %s companies', done)
    except Exception:       # noqa: BLE001 — an upgrade must not die here
        _logger.exception('pb_trip_advance: settlement routes not laid')
