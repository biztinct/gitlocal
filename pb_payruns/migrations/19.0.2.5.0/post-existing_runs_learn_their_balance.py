# -*- coding: utf-8 -*-
"""Existing pay runs learn whether their own figures add up.

`pb_balance_ok` and `pb_balance_gap` are new stored computes, and a stored
compute does NOT re-run because its code appeared — the column is simply
created empty. An empty Boolean reads as False, and False is the value that
SHOWS the warning, so without this every pay run in every database would open
with "These figures do not add up" across the top of it, including the ones
that add up perfectly.

WHY SQL AND NOT A RECOMPUTE. The three figures this compares are already
stored on the run (`pb_total_gross`, `pb_total_deductions`, `pb_total_net`) and
they are correct; only the comparison between them is missing. Re-aggregating
every payslip line on the demo world to re-derive numbers that are already
right would take minutes and could move nothing.

The arithmetic is `_pb_set_balance`'s, kept deliberately in step with it:

  * no net figure at all -> nothing to reconcile against, so `ok`;
  * otherwise out by more than one unit per payslip AND more than 1% of
    gross -> not ok.
"""
import logging

from odoo.tools.sql import column_exists, table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    if not (table_exists(cr, 'hr_payslip_run')
            and column_exists(cr, 'hr_payslip_run', 'pb_balance_ok')):
        return

    cr.execute("""
        UPDATE hr_payslip_run r
           SET pb_balance_gap = COALESCE(r.pb_total_gross, 0)
                              - COALESCE(r.pb_total_deductions, 0)
                              - COALESCE(r.pb_total_net, 0),
               pb_balance_ok = (
                   COALESCE(r.pb_total_net, 0) = 0
                   OR ABS(COALESCE(r.pb_total_gross, 0)
                          - COALESCE(r.pb_total_deductions, 0)
                          - COALESCE(r.pb_total_net, 0))
                      <= GREATEST(COALESCE(r.pb_employee_count, 1), 1,
                                  ABS(COALESCE(r.pb_total_gross, 0)) * 0.01)
               )
    """)
    touched = cr.rowcount
    cr.execute("SELECT COUNT(*) FROM hr_payslip_run WHERE pb_balance_ok IS NOT TRUE")
    flagged = cr.fetchone()[0]
    _logger.info(
        "pb_payruns: balance checked on %s pay run(s); %s do not reconcile and "
        "will say so on screen.", touched, flagged)
