# -*- coding: utf-8 -*-
"""INBOX-BULK-BANK — bank-detail changes may be approved several at once,
after an extra confirmation.

The new `bulk_confirm` column arrives empty (False) on every existing
catalogue row, so the upgrade itself changes nothing. This then switches it
on, ONCE, for the keys listed in `process.BULK_CONFIRM_KEYS` (bank-detail
changes, never a kind that pays money out) — the owner asked for exactly
this. `_seed_bulk_confirm_defaults` keeps a marker parameter, so running it
again changes nothing and a customer's own choice survives later upgrades.
No request, decision, mail or job is touched.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    keys = env['biz.approval.process']._seed_bulk_confirm_defaults()
    _logger.info('approval: several-at-once with an extra confirmation '
                 'switched on for %s', keys)
