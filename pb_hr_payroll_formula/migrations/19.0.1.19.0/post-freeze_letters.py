# -*- coding: utf-8 -*-
"""F111 — freeze column letters as permanent identities (D111.1).

Materialise today's computed `column_letter` into `forced_column_letter` for
every existing rule. After this, `sequence` is pure display order and
`_compute_column_letter` always returns the frozen letter — a reorder can never
move a letter, so letter-based formula references can never be silently
re-pointed. Idempotent: only fills rules whose forced letter is still empty.
"""
import logging

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
