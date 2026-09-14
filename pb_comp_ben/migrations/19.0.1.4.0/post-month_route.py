# -*- coding: utf-8 -*-
"""Approval Matrix P7 — the reopen-a-month route, on an upgrade."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_comp_ben.models.month_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_comp_ben: the reopen-a-month route could not '
                          'be laid')
