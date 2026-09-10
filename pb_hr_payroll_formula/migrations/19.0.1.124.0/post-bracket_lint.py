# -*- coding: utf-8 -*-
"""Re-check every formula that uses a progressive band table (BP-R12).

`is_valid` is a stored flag, written the last time somebody validated a
configuration. Fixing the checker therefore changes nothing on its own: every
`BRACKET(...)` rule stays marked invalid, the configuration keeps
`has_errors = True`, and its card on the Payroll configurations screen keeps
saying "2 errors" about a formula that computes perfectly.

This re-runs the syntax check for exactly those rules — nothing else is
touched, and a rule that is genuinely broken stays broken.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.formula.rule']
    RateTable = env['hr.formula.rate.table']
    from odoo.addons.pb_hr_payroll_formula.formula_engine import FormulaValidator

    cr.execute("""
        SELECT id FROM hr_formula_rule
         WHERE column_type = 'formula'
           AND excel_formula IS NOT NULL
           AND UPPER(excel_formula) LIKE '%%BRACKET%%'
    """)
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        return

    validator = FormulaValidator()
    fixed = 0
    configs = set()
    for rule in Rule.browse(ids):
        if not rule.exists() or not rule.config_id:
            continue
        config = rule.config_id
        column_map = {r.column_letter: r.code for r in config.rule_ids}
        missing = config._missing_rate_tables(rule.excel_formula)
        if missing:
            continue
        expanded = RateTable.expand_brackets(rule.excel_formula, config)
        ok, message = validator.validate_formula(expanded, column_map)
        if ok and not rule.is_valid:
            fixed += 1
            configs.add(config.id)
        rule.write({'is_valid': ok,
                    'validation_message': '' if ok else message})
    _logger.info("BP-R12: re-checked %d band-table formulas, %d now valid "
                 "across %d configurations", len(ids), fixed, len(configs))
