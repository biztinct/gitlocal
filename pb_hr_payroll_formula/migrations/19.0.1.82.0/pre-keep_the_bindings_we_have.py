# -*- coding: utf-8 -*-
"""JOURNEY J9 — take a copy of the single binding BEFORE the field becomes computed.

WHY A PRE-MIGRATION AT ALL

`source_binding`, `source_binding_key`, `source_binding_origin`,
`source_binding_date` and `source_binding_uid` stop being plain stored columns in
this version and become COMPUTED-and-stored views of `hr.formula.rule.source`
(J9 §4.1). The post-migration seeds one child row per existing binding, so the
computed values land back exactly where they were.

That works only if the post-migration can still READ the old values. Whether Odoo
recomputes an existing column when its field definition gains a `compute` is a
detail of `_auto_init` — on this build it does not, because recomputation is
flagged for columns that are NEW — but "it does not, on this build" is not a thing
to bet thirteen live bindings on when the alternative is a temporary table.

So: copy first, seed from the copy, drop the copy. The post-migration then never
depends on the state of the columns it is about to make consistent, which is also
what makes it re-runnable (T4, case 13).
"""
import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

BACKUP = 'j9_binding_backup'


def migrate(cr, version):
    if not version:
        return
    if not table_exists(cr, 'hr_formula_rule'):
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'hr_formula_rule'
           AND column_name IN ('source_binding', 'source_binding_key',
                               'source_binding_origin', 'source_binding_date',
                               'source_binding_uid', 'column_type')
    """)
    present = {r[0] for r in cr.fetchall()}
    needed = {'source_binding', 'source_binding_key', 'column_type'}
    if not needed <= present:
        _logger.info("J9: no binding columns to preserve.")
        return

    has_origin = 'source_binding_origin' in present
    has_date = 'source_binding_date' in present
    has_uid = 'source_binding_uid' in present
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP)
    cr.execute("""
        CREATE TABLE {tbl} AS
        SELECT id AS rule_id, column_type, source_binding AS kind,
               source_binding_key AS key,
               {origin} AS origin, {date} AS set_date, {uid} AS set_uid
          FROM hr_formula_rule
         WHERE source_binding IS NOT NULL
           AND COALESCE(source_binding_key, '') <> ''
    """.format(
        tbl=BACKUP,
        origin='source_binding_origin' if has_origin else "'migration'",
        date='source_binding_date' if has_date else 'NULL::timestamp',
        uid='source_binding_uid' if has_uid else 'NULL::integer',
    ))
    cr.execute("SELECT count(*) FROM %s" % BACKUP)
    _logger.info("J9: preserved %s single binding(s) for the plural form.",
                 cr.fetchone()[0])
