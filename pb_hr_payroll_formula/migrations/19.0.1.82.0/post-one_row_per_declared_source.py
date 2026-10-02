# -*- coding: utf-8 -*-
"""JOURNEY J9 — turn every single binding into a row of `hr.formula.rule.source`.

WHAT IT DOES
    One child row per existing non-empty binding, carrying `origin`, `date` and
    `uid` across unchanged, and then makes the five legacy columns agree with the
    rows — they are computed-and-stored from here on, so a value not backed by a
    row is a statement the next recompute would erase anyway.

WHAT IT DOES NOT TOUCH — T4, and it is the one that could take a live database
    down mid-upgrade. `_check_source_binding` raises when a binding is set on a
    column that is not an `input`, so seeding a row for a sealed column would
    abort the upgrade of a ninety-nine-column scheme half-way through. Non-input
    rules are therefore SKIPPED and their stale columns are cleared rather than
    converted, and the count is logged so an operator can see it happened. (On
    all four live databases this count is zero: every bound rule is an input.)

IDEMPOTENT by construction: the insert is `WHERE NOT EXISTS` on `(rule_id, kind)`,
which is the same invariant the model's `@api.constrains` enforces, so a second
run inserts nothing and rewrites the same five columns to the same five values.

Plain SQL, and deliberately so: this runs before any client of the new field can
read it, the arithmetic is a join and a rank, and an ORM pass over every rule on a
four-thousand-employee database is a cost with nothing to buy.
"""
import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

BACKUP = 'j9_binding_backup'

#: The resolver's order, as SQL. It mirrors `hr.formula.rule._SOURCE_RANK`; the
#: model is the definition and this is a one-time projection of it.
RANK_SQL = "CASE kind WHEN 'feed' THEN 1 WHEN 'rule' THEN 2 ELSE 3 END"


def migrate(cr, version):
    if not version:
        return
    if not table_exists(cr, 'hr_formula_rule_source'):
        _logger.warning("J9: the source table is absent; nothing converted.")
        return

    converted = skipped = 0
    if table_exists(cr, BACKUP):
        cr.execute("""SELECT count(*) FROM {tbl}
                       WHERE column_type IS DISTINCT FROM 'input'""".format(tbl=BACKUP))
        skipped = cr.fetchone()[0]
        cr.execute("""
            INSERT INTO hr_formula_rule_source
                   (rule_id, kind, key, origin, set_date, set_uid,
                    create_uid, create_date, write_uid, write_date)
            SELECT b.rule_id, b.kind, btrim(b.key),
                   COALESCE(b.origin, 'migration'), b.set_date, b.set_uid,
                   1, now() AT TIME ZONE 'UTC', 1, now() AT TIME ZONE 'UTC'
              FROM {tbl} b
              JOIN hr_formula_rule r ON r.id = b.rule_id
             WHERE b.column_type = 'input'
               AND b.kind IN ('excel', 'feed', 'rule')
               AND COALESCE(btrim(b.key), '') <> ''
               AND NOT EXISTS (SELECT 1 FROM hr_formula_rule_source s
                                WHERE s.rule_id = b.rule_id AND s.kind = b.kind)
        """.format(tbl=BACKUP))
        converted = cr.rowcount
        cr.execute("DROP TABLE IF EXISTS %s" % BACKUP)

    # The five legacy columns become a view of the highest-ranked row. Written
    # here rather than left to a recompute, so the upgrade closes with the stored
    # values and the rows already agreeing, on every rule, whichever way this
    # server happens to treat a column that has just gained a `compute`.
    cr.execute("""
        WITH top AS (
            SELECT DISTINCT ON (rule_id)
                   rule_id, kind, key, origin, set_date, set_uid
              FROM hr_formula_rule_source
             WHERE COALESCE(btrim(key), '') <> ''
             ORDER BY rule_id, {rank}, id
        )
        UPDATE hr_formula_rule r
           SET source_binding = t.kind,
               source_binding_key = btrim(t.key),
               source_binding_origin = COALESCE(t.origin, 'user'),
               source_binding_date = t.set_date,
               source_binding_uid = t.set_uid
          FROM top t
         WHERE t.rule_id = r.id
           AND (r.source_binding IS DISTINCT FROM t.kind
                OR r.source_binding_key IS DISTINCT FROM btrim(t.key))
    """.format(rank=RANK_SQL))
    aligned = cr.rowcount

    cr.execute("""
        UPDATE hr_formula_rule r
           SET source_binding = NULL, source_binding_key = NULL,
               source_binding_origin = NULL, source_binding_date = NULL,
               source_binding_uid = NULL
         WHERE r.source_binding IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM hr_formula_rule_source s
                            WHERE s.rule_id = r.id
                              AND COALESCE(btrim(s.key), '') <> '')
    """)
    cleared = cr.rowcount

    _logger.info(
        "J9 plural sources: converted=%s skipped_non_input=%s realigned=%s "
        "cleared_unbacked=%s", converted, skipped, aligned, cleared)
