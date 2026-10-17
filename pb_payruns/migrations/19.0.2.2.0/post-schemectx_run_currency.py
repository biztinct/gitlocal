# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""SCHEMECTX P1 — re-stamp the money on pay runs that belong to a scheme.

`pb_currency_id` is stored and used to be taken from the run's company, so a
run of an India scheme was labelled dong. Only runs whose scheme currency
differs from the company's move; everything else is left exactly as it is.
No amount is converted or restated — the label is the whole of the change.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Run = env.get('hr.payslip.run')
    if Run is None or 'pb_currency_id' not in Run._fields:
        return
    cr.execute("""
        SELECT DISTINCT r.id
          FROM hr_payslip_run r
          JOIN hr_payslip s ON s.payslip_run_id = r.id
          JOIN hr_formula_config c ON c.id = s.formula_config_id
         WHERE c.currency_id IS DISTINCT FROM r.pb_currency_id
    """)
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        _logger.info("SCHEMECTX P1: no pay run needed a new currency label.")
        return
    runs = Run.browse(ids).exists()
    runs._compute_pb_totals()
    runs.flush_recordset(['pb_currency_id'])
    _logger.info("SCHEMECTX P1: re-stamped the currency on %s pay runs.",
                 len(runs))
