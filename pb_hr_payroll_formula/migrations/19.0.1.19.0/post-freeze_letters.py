# -*- coding: utf-8 -*-
"""F111 — freeze column letters as permanent identities (D111.1).

Materialise today's computed `column_letter` into `forced_column_letter` for
every existing rule. After this, `sequence` is pure display order and
`_compute_column_letter` always returns the frozen letter — a reorder can never
move a letter, so letter-based formula references can never be silently
re-pointed. Idempotent: only fills rules whose forced letter is still empty.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE hr_formula_rule
           SET forced_column_letter = column_letter
         WHERE (forced_column_letter IS NULL OR forced_column_letter = '')
           AND column_letter IS NOT NULL
           AND column_letter != ''
    """)
    _logger.info("F111: froze column letters on %s rule(s).", cr.rowcount)

    # Seed each config's letter high-water mark to its current max letter, so a
    # freed top letter is never handed out again (D111.3). Without this, hwm
    # stays 0 after upgrade and "delete the last column, add one" reuses the
    # deleted letter, silently re-pointing any surviving reference to it.
    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.formula.rule']
    seeded = 0
    for config in env['hr.formula.config'].search([]):
        used = [Rule._letter_to_num(r.column_letter) for r in config.rule_ids
                if r.column_letter and not Rule._is_constant_namespace(r.column_letter)]
        hwm = max(used) if used else 0
        if hwm and (config.col_letter_hwm or 0) < hwm:
            config.col_letter_hwm = hwm
            seeded += 1
    _logger.info("F111: seeded column-letter high-water mark on %s config(s).", seeded)
