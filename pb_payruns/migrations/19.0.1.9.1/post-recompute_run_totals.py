# -*- coding: utf-8 -*-
"""Recompute every pay run's KPI band, because what it means has changed.

`pb_total_gross` used to be read from a salary-rule category coded `GROSS`
alone. A scheme built by importing a payroll workbook has a basic and a list of
allowances and no such category, so every one of those runs stored a gross of
zero — ABM's June 2026 run showed ₫0 gross above ₫1.9bn of basic pay.

The totals are STORED computed fields, and a module upgrade does not recompute
a stored field just because the Python behind it changed. Without this, every
run already in the system would keep the answer the old rule gave it, and only
runs touched afterwards would tell the truth — the worst of both.

Cheap and safe: the compute is a two-query SQL roll-up per batch, and it writes
nothing but the four totals it owns.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BATCH = 200


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Run = env.get('hr.payslip.run')
    if Run is None or 'pb_total_gross' not in Run._fields:
        return

    runs = Run.with_context(active_test=False).search([])
    if not runs:
        return
    fields_to_redo = [
        Run._fields[name] for name in
        ('pb_employee_count', 'pb_total_net', 'pb_total_gross',
         'pb_total_deductions')
        if name in Run._fields
    ]
    for start in range(0, len(runs), BATCH):
        chunk = runs[start:start + BATCH]
        for field in fields_to_redo:
            env.add_to_compute(field, chunk)
        chunk.flush_recordset()
    _logger.info(
        "Pay-run totals recomputed for %s run(s): gross now falls back to "
        "basic + allowances where a scheme has no explicit Gross component.",
        len(runs))
