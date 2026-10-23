# -*- coding: utf-8 -*-
"""Retire `hr.payroll.import.batch.source_type == 'connector'`.

WHY
    It was a source a user could pick and the system could not load. There has never
    been an `action_load_from_connector` in this codebase; every door routes a
    connector batch to `action_load_from_data_store`, whose first guard refuses
    anything that is not `api_data_store`. A batch created with this value reached
    `draft` and stopped, with a refusal that blamed the user's choice for a loader
    nobody had written. JOURNEY J3 S5 removes the value from the selection, and a
    stored value with no selection entry renders as a BLANK radio button on the form
    and an empty cell in the list — so the rows have to move, not merely be orphaned.

    `api_data_store` is what the connector path has always MEANT here: the connector
    writes `hr.api.data.store` rows and the batch reads those. Converting is
    therefore not a re-interpretation of the row, it is spelling the same intent
    with the value that has a loader behind it.

WHAT IS NOT TOUCHED
    * Every other `source_type` — `excel`, `api_data_store`, `manual` are untouched
      and the UPDATE names `'connector'` explicitly rather than filtering by
      exclusion.
    * `connector_id` on the converted rows. It is the field `api_data_store` needs,
      it is already populated on any row that got this far, and clearing it would
      turn a convertible batch into an unloadable one.
    * Batch STATE, lines, employees, payslips. Nothing is re-loaded, re-matched or
      re-processed; `action_process` is not called and cannot be reached from here.
    * The `hr.api.data.store` rows themselves.

IDEMPOTENT: the second run matches zero rows and logs zero.
"""
import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    if not table_exists(cr, 'hr_payroll_import_batch'):
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'hr_payroll_import_batch'
           AND column_name = 'source_type'
    """)
    if not cr.fetchall():
        return

    cr.execute("SELECT count(*) FROM hr_payroll_import_batch")
    total = cr.fetchone()[0]
    cr.execute("""
        SELECT id, name, state FROM hr_payroll_import_batch
         WHERE source_type = 'connector' ORDER BY id
    """)
    rows = cr.fetchall()
    if not rows:
        _logger.info(
            "J3 S5: no batch carries the retired source_type 'connector' "
            "(%s batch row(s) on this database); nothing to convert.", total)
        return

    cr.execute("""
        UPDATE hr_payroll_import_batch
           SET source_type = 'api_data_store'
         WHERE source_type = 'connector'
    """)
    _logger.info(
        "J3 S5: converted %s of %s batch row(s) from the retired source_type "
        "'connector' to 'api_data_store': %s",
        len(rows), total,
        ', '.join('#%s %s (%s)' % (r[0], r[1], r[2]) for r in rows))
