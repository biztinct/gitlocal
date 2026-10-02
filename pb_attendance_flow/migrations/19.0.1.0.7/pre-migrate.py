# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P4 WP-1 — seed the Close tolerance on every existing rule row.

WHY A MIGRATION AT ALL
----------------------
`data/attendance_rule_data.xml` is `<odoo noupdate="1">`, so the global rule row
is FROZEN on every existing database: adding the two new fields to that XML
record would apply to fresh installs only and silently do nothing here (W13.1,
proven live in P0 and again in P1b). Unfreezing it (W27's pre-migrate trick) is
the wrong tool this time — the file also declares grace_in/out and the
open-checkout threshold, and an admin who has tuned those for their factory must
not have them reset by a tolerance change.

So: a PRE-migrate that creates the columns itself and fills them, before the ORM
adds them. That order matters. `_init_column` does fill a new column with the
field default, but only for a column IT creates; doing it here makes the seeding
explicit and auditable rather than a behaviour we are trusting, and it is what
`pb_attendance_flow/tests/test_close_tolerance.py::test_the_migration_seeded_the
_global_row` reads back from the DATABASE (W13.1: a repo-only fix is
indistinguishable from a real one unless something reads the database back).

Idempotent by construction: `ADD COLUMN IF NOT EXISTS` plus an `IS NULL` filter,
so a re-run cannot overrule an admin who has since changed the numbers.
"""
import logging

_logger = logging.getLogger(__name__)

# (column, sql type, default) — the P4 §3.1 defaults, kept in ONE place beside
# the field definitions they mirror (pb_attendance_flow/models/attendance_rule.py).
_COLUMNS = (
    ('variance_minutes', 'integer', 10),
    ('variance_hours_week', 'double precision', 0.5),
)


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT to_regclass('public.pb_attendance_rule')")
    row = cr.fetchone()
    if not row or not row[0]:
        _logger.info("pb_attendance_flow: no pb_attendance_rule table yet")
        return

    for column, sqltype, default in _COLUMNS:
        cr.execute(
            "ALTER TABLE pb_attendance_rule "
            "ADD COLUMN IF NOT EXISTS %s %s" % (column, sqltype))
        cr.execute(
            "UPDATE pb_attendance_rule SET %s = %%s WHERE %s IS NULL"
            % (column, column), (default,))
        if cr.rowcount:
            _logger.info(
                "pb_attendance_flow: seeded %s = %s on %s attendance rule(s) "
                "(Workforce P4 close tolerance)", column, default, cr.rowcount)
