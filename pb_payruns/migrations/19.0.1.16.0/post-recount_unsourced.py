# -*- coding: utf-8 -*-
"""Recompute `pb_unsourced_count` now that it skips payslips with no provenance.

VALUEKIND P5. The field shipped one version earlier WITHOUT the guard that a
payslip carrying no `formula_input_sources` blob predates the recording of
provenance and cannot be judged. Its stored values therefore flagged every run
whose payslips were computed before SOURCING S1 — 42 of them on the reference
demo database, none of which had anything wrong.

A stored compute does not re-run just because its code changed, so the wrong
answers would have sat there being wrong. This asks for them again.

Recomputing this field recomputes the whole KPI band with it (one compute
method covers all of them), which is harmless: the same SQL over the same rows
returns the same figures.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    runs = env['hr.payslip.run'].with_context(active_test=False).search([])
    if not runs:
        return
    env.add_to_compute(runs._fields['pb_unsourced_count'], runs)
    env.flush_all()
    flagged = runs.filtered(lambda r: r.pb_unsourced_count)
    _logger.info(
        "VALUEKIND P5: recounted %s pay run(s); %s now flagged as computed "
        "with no source data.", len(runs), len(flagged))
