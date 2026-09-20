# -*- coding: utf-8 -*-
"""Backfill `hr_payslip.pb_sourced_inputs` from provenance already stored.

VALUEKIND P5. The new counter is what the pay run's "computed with no source
data" banner reads. Without this, EVERY payslip computed before the field
existed reads 0 and every historical run flags — turning a warning that means
"this payroll ran on nothing" into one that means nothing at all.

The data was always there: `formula_input_sources` has recorded, per component,
where the value came from since SOURCING S1. This only counts it.

The distinction the module header already insists on is preserved: a payslip
with no blob is one that PREDATES provenance, which is a different statement
from "this payslip sourced nothing". Those are left NULL and the banner's query
skips them.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT count(*) FROM hr_payslip
        WHERE formula_input_sources IS NOT NULL
          AND formula_input_sources LIKE '{%'
    """)
    total = cr.fetchone()[0]
    if not total:
        return
    try:
        cr.execute("""
            UPDATE hr_payslip p
               SET pb_sourced_inputs = sub.n
              FROM (
                    SELECT s.id,
                           (SELECT count(*)
                              FROM json_each(s.formula_input_sources::json) AS e
                             WHERE COALESCE(e.value->>'src', 'none') <> 'none'
                           ) AS n
                      FROM hr_payslip s
                     WHERE s.formula_input_sources IS NOT NULL
                       AND s.formula_input_sources LIKE '{%'
                   ) sub
             WHERE p.id = sub.id
        """)
        _logger.info("VALUEKIND P5: counted sourced inputs on %s payslip(s)", total)
    except Exception:       # noqa: BLE001
        # One malformed blob must not stop an upgrade. Left NULL, such a payslip
        # is simply never judged — which is the honest answer for a record whose
        # provenance cannot be read.
        cr.rollback()
        _logger.exception(
            "VALUEKIND P5: could not count sourced inputs; the pay run "
            "'no source data' banner will ignore payslips computed before now.")
