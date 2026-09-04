# -*- coding: utf-8 -*-
"""RD49 — put the new monthly fetch on the 5th at 02:00.

`post_init_hook` fires on INSTALL ONLY. Every existing database gets this
module by UPGRADE, so on all four of them the hook never ran and the job kept
the `nextcall` Odoo assigns when a cron record is created — "now", which then
advanced by one interval to the 30th. The owner asked for the 5th.

Unconditional here, and conservative in the hook, on purpose: the job is
created by this very upgrade, so nobody has had the chance to choose a time yet
and there is nothing to preserve. From the next upgrade on, `_rd49_schedule_
first_run` leaves a chosen time alone.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('pb_hr_payroll_formula.ir_cron_pull_previous_month',
                   raise_if_not_found=False)
    if not cron:
        _logger.warning("RD49: the monthly fetch job is not there to schedule.")
        return
    target = env['hr.integration.connector']._rd49_next_fifth()
    cron.nextcall = target
    _logger.info("RD49: monthly fetch scheduled for %s (was %s)",
                 target, version)
