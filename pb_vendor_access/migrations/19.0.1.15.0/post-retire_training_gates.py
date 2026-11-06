# -*- coding: utf-8 -*-
"""LEARNING L1 (ledger LN11) — Talent no longer opens for a training role.

Training left Talent for its own Learning entry (owner decision LD3), but the
three training roles stayed in Talent's role gate, so somebody whose only role
was a training role saw an empty Talent entry. `SCREEN_GATES` no longer lists
them; gates are additive, so this takes them off the existing Talent row on
every database — except where a role still holds a Talent ability (goals,
growth plans, recognition). The "kept across upgrades" stamp is not honoured
here, deliberately (see `retire_screen_gates`): it was set on every entry in
bulk, and a training role opens nothing inside Talent any more. Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import retire_screen_gates
    result = retire_screen_gates(env)
    _logger.info('pb_vendor_access 19.0.1.15.0: %s', result)
