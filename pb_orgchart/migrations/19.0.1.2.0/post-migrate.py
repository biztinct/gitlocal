# -*- coding: utf-8 -*-
"""ORG CHART P3 — lay the ``orgplan`` approval route on every company of a
database that already had the module (post_init_hook runs on install only)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_orgchart.models.pb_orgchart_plan import seed_all
    try:
        n = seed_all(env)
        _logger.info("pb_orgchart: plan route laid on %s companies", n)
    except Exception:   # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception("pb_orgchart: the default plan route could not be seeded")
