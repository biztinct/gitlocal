# -*- coding: utf-8 -*-
"""Approval Matrix P7 — the settlement route, and the settlements that exist.

Every settlement created before this phase WAS produced and, in most cases,
paid. The new `state` column defaults to "being prepared", so without this
every historical settlement would read as about to happen and could no longer
be printed. They are marked approved, which is what they are.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        UPDATE hr_full_final_settlement
           SET state = 'approved'
         WHERE state IS NULL OR state = 'draft'
    """)
    _logger.info('pb_hr_fullandfinal: %s settlement(s) marked approved',
                 cr.rowcount)
    from odoo.addons.pb_hr_fullandfinal.models.fnf_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_hr_fullandfinal: the settlement route could '
                          'not be laid')
