# -*- coding: utf-8 -*-
"""Existing payslip lines learn what net pay does with them.

`hr_payslip_line.pay_role` is new, so every line already in the database is
null and every report that classifies by it would read those runs as
unclassified. The value is not a guess: the scheme that produced the line
already holds it as `hr.formula.rule.net_role`, derived from its own net-pay
formula.

WHY A MIGRATION. The field is stamped at line CREATION, so it fills in from the
next computation onward. Historic runs are precisely the ones people open a
report about, and they would otherwise stay blank forever.

MATCHED ON (code, scheme). A payslip line's `code` is unique within a scheme,
and the payslip names the scheme, so the pair is exact. Lines whose payslip has
no scheme — structure-based payroll — are left null on purpose: those classify
through `hr_salary_rule_category.category_type`, which is correct for them.

NOTHING IS RECOMPUTED. This writes one column on existing rows. No amount
moves, no payslip is re-evaluated, no run total changes — `pb_payruns` computes
the header from `component_detail`, which this does not touch.

Re-running is a no-op: the UPDATE only touches rows whose value differs.
"""
import logging

from odoo.tools.sql import column_exists, table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    if not (table_exists(cr, 'hr_payslip_line')
            and table_exists(cr, 'hr_formula_rule')
            and column_exists(cr, 'hr_payslip_line', 'pay_role')):
        return

    cr.execute("""
        UPDATE hr_payslip_line pl
           SET pay_role = r.net_role
          FROM hr_payslip p, hr_formula_rule r
         WHERE p.id = pl.slip_id
           AND r.config_id = p.formula_config_id
           AND r.code = pl.code
           AND r.net_role IS NOT NULL
           AND pl.pay_role IS DISTINCT FROM r.net_role
    """)
    filled = cr.rowcount

    cr.execute("""
        SELECT COUNT(*) FILTER (WHERE pl.pay_role IS NULL),
               COUNT(*)
          FROM hr_payslip_line pl
          JOIN hr_payslip p ON p.id = pl.slip_id
         WHERE p.formula_config_id IS NOT NULL
    """)
    still_null, scheme_lines = cr.fetchone()

    _logger.info(
        "VALUEKIND P4: pay_role written on %s payslip line(s); %s of %s "
        "scheme-computed line(s) still unclassified (their component carries "
        "no net role yet)", filled, still_null, scheme_lines)

    # The Explorer's derived tables are stale after this, but flagging them is
    # NOT done here: module load order runs this migration before pb_explorer's
    # models reach the registry, so the guard that would protect the write is
    # always False and the flag is silently never set (C18.125). pb_explorer
    # flags its own tables in its own 19.0.1.3.0 migration.
