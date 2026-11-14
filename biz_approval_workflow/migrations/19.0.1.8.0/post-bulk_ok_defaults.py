# -*- coding: utf-8 -*-
"""WDGAP QF1 — which kinds of request may be approved several at once.

The new `bulk_ok` column arrives empty (False) on every existing catalogue
row. This switches it on, ONCE, for the kinds listed in
`process.BULK_DEFAULT_KEYS` (leave, overtime, timesheets, …) and never for a
money process. `_seed_bulk_defaults` keeps a marker parameter, so running it
again — a later upgrade, a re-run — changes nothing and a customer's own
choice survives.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    keys = env['biz.approval.process']._seed_bulk_defaults()
    _logger.info('approval: several-at-once switched on for %s', keys)
