# -*- coding: utf-8 -*-
"""Install-time setup: the default approval route for org chart plans.

`post_init_hook` runs on INSTALL only; every live database already has this
module, so `migrations/19.0.1.2.0/post-migrate.py` lays the route on an
upgrade. Both are idempotent and never fatal (approval ledger AM70)."""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    try:
        from .models.pb_orgchart_plan import seed_all
        seed_all(env)
    except Exception:   # noqa: BLE001
        _logger.exception("pb_orgchart: the default plan route could not be laid")
