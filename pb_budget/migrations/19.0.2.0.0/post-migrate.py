# -*- coding: utf-8 -*-
"""Bring the budget rows home before the old planning module is removed.

Runs on the UPGRADE that adds `pb.budget.line`, so the new table exists by the
time this fires. Idempotent: every row is matched by company, team, month and
kind, so a second run moves nothing twice.

The old table is NOT dropped here. It goes when the module that owns it is
uninstalled, and only after the pre-flight gate has checked that the row counts
and the totals match on both sides.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        report = env['pb.budget.line'].sudo().migrate_from_planning()
        _logger.info('pb_budget 19.0.2.0.0: %s', report)
        if report.get('found') and abs(report.get('old_sum', 0.0)
                                       - report.get('new_sum', 0.0)) > 1.0:
            _logger.error(
                'pb_budget 19.0.2.0.0: the budget rows do NOT add up the same '
                'on both sides (%s against %s) — the old module must not be '
                'removed until this is looked at',
                report.get('old_sum'), report.get('new_sum'))
    except Exception:                           # noqa: BLE001
        _logger.exception('pb_budget 19.0.2.0.0: the budget rows could not '
                          'be moved')
