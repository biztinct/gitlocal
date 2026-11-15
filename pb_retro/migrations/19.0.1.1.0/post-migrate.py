# -*- coding: utf-8 -*-
"""WDGAP W2-D2: a database that already has pb_retro (19.0.1.0.0) gets the
default back-pay route on every company — the install hook does not run on an
upgrade. A company that already has a route keeps it (`Seed.lay` is
idempotent)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_retro.models.retro_backpay import seed_all
    done = seed_all(env)
    _logger.info('pb_retro W2-D2: back-pay routes in place on %s companies', done)
