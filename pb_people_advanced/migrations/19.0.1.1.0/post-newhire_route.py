# -*- coding: utf-8 -*-
"""Approval Matrix P7 — the new-hire route, on an upgrade."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_people_advanced.models.newhire_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_people_advanced: the new-hire route could not '
                          'be laid')
