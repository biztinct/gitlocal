# -*- coding: utf-8 -*-
"""SC-2 — turn the monthly cron into the hourly dispatcher, without moving
anybody's fetch.

Two facts to reconcile:

  * the cron data file is `noupdate`, so flipping its interval there reaches
    only FRESH databases — existing ones get it here;
  * every connector that had the fetch switched on was running on RD49's
    cadence (the 5th, 02:00 UTC). Their `sync_next_run` is seeded to exactly
    that occurrence, so the migration itself changes nothing about when their
    next fetch happens. From then on the cadence follows the connector's own
    schedule fields (default: monthly, day 5, 02:00 on the company clock).

Idempotent: a second run finds the interval already hourly and every enabled
connector already stamped.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_cron
           SET interval_type = 'hours', interval_number = 1
         WHERE id IN (SELECT res_id FROM ir_model_data
                       WHERE module = 'pb_hr_payroll_formula'
                         AND name = 'ir_cron_pull_previous_month'
                         AND model = 'ir.cron')
           AND (interval_type, interval_number) != ('hours', 1)
    """)
    if cr.rowcount:
        _logger.info("SC-2: dispatcher cadence set to hourly")

    env = api.Environment(cr, SUPERUSER_ID, {})
    Conn = env['hr.integration.connector']
    for conn in Conn.with_context(active_test=False).search(
            [('cron_pull_enabled', '=', True)]):
        if not conn.sync_next_run:
            conn.with_context(sc2_stamping=True).sync_next_run = \
                Conn._rd49_next_fifth()
            _logger.info(
                "SC-2: %s keeps its RD49 occurrence — next fetch %s",
                conn.display_name, conn.sync_next_run)
