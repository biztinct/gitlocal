# -*- coding: utf-8 -*-
"""Integrations Cycle 7, WP-5 — take the connection test's clock off "Last sync".

`base_connector.update_connector_status()` stamped `last_sync` on every
CONNECTION-STATUS change, so a successful "Test connection" wrote the field the
cockpit header prints as "Last sync". The code is fixed; the rows it already
wrote are not, and they are the ones the owner is looking at.

The signature is exact rather than heuristic. That method is the ONLY writer of
`last_sync` in this codebase that does not also write `last_sync_status`:

    action_pull_data          last_sync + last_sync_status ('success'/'partial')
    receive_pushed_records    last_sync + last_sync_status ('success')
    _stamp_endpoint           the ENDPOINT's own last_sync
    update_connector_status   last_sync, and no status at all   <-- this one

So `last_sync IS NOT NULL AND last_sync_status IS NULL` selects connection
tests and nothing else. Measured before writing anything:

    abm       1 row  — "Zoho People (ABM)", 2026-08-20 23:25:11,
                       last_sync_message 'Connection successful',
                       total_synced_records NULL, 0 data-store rows,
                       and all seven feeds' last_sync NULL.
    payobook  0 rows — every connector carrying a last_sync there carries a
                       status with it.

The timestamp is MOVED, not deleted: it is a true fact about a real event, and
throwing it away to make a screen consistent is the paper-over this cycle was
told not to do. It lands in `last_connection_test`, where the header can say
what it actually means.

Idempotent by construction: after the move the source predicate matches nothing.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT count(*) FROM information_schema.columns
         WHERE table_name = 'hr_integration_connector'
           AND column_name = 'last_connection_test'
    """)
    if not cr.fetchone()[0]:
        # The field is added by the same upgrade that runs this script, so the
        # column is normally already there. If it is not, the ORM has not
        # reached this model yet and there is nothing safe to do (W121).
        _logger.warning(
            "Cycle 7 WP-5: last_connection_test does not exist yet; "
            "connection-test timestamps left on last_sync.")
        return

    cr.execute("""
        UPDATE hr_integration_connector
           SET last_connection_test = COALESCE(last_connection_test, last_sync),
               last_sync = NULL
         WHERE last_sync IS NOT NULL
           AND last_sync_status IS NULL
        RETURNING id, name
    """)
    moved = cr.fetchall()
    if moved:
        _logger.info(
            "Cycle 7 WP-5: %d connector(s) had a CONNECTION TEST recorded as a "
            "sync; the timestamp moved to last_connection_test — %s",
            len(moved), ', '.join('%s (id %s)' % (str(n), i) for i, n in moved))
    else:
        _logger.info(
            "Cycle 7 WP-5: no connector carried a connection test on its "
            "last_sync field.")
