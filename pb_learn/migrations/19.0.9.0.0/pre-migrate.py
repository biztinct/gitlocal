# -*- coding: utf-8 -*-
"""Carry learner state across the deletion of the content models.

WHAT BREAKS WITHOUT THIS
------------------------
Phase 1a deletes learn.station and learn.mission. `learn.progress` pointed at
both with Many2ones and `learn.event` at the first; those columns go with the
models, and with them every learner's completed lessons, their resume point and
the whole event history's station attribution. A learner would open the Journey
after the upgrade and find their map blank.

Odoo drops the columns during the module update, AFTER this hook runs and
BEFORE the new `key` / `station_key` fields exist. So the columns are created
here, in SQL, and back-filled from the tables while they are still standing.
The ORM then finds them already present and populated.

Idempotent: `ADD COLUMN IF NOT EXISTS`, and every UPDATE is scoped to rows that
have not been converted yet. Re-running `-u pb_learn` cannot double-apply it.

WHAT IT DOES NOT DO
-------------------
It does not delete the old tables or their ir_model rows — Odoo's own module
update does that when the models disappear from the registry, and doing it here
would be racing the thing that owns it.
"""
import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, name):
    cr.execute("SELECT to_regclass(%s)", ('public.%s' % name,))
    return bool(cr.fetchone()[0])


def _column_exists(cr, table, column):
    cr.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""", (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        # Fresh install. There is nothing behind us.
        return

    # ---------------------------------------------------------- progress
    if _table_exists(cr, 'learn_progress'):
        cr.execute('ALTER TABLE learn_progress ADD COLUMN IF NOT EXISTS key varchar')
        if _column_exists(cr, 'learn_progress', 'station_id') \
                and _table_exists(cr, 'learn_station'):
            cr.execute("""
                UPDATE learn_progress p
                   SET key = s.key
                  FROM learn_station s
                 WHERE p.station_id = s.id
                   AND (p.key IS NULL OR p.key = '')
            """)
            _logger.info('pb_learn: carried %s station progress row(s) onto the '
                         'new key column.', cr.rowcount)
        if _column_exists(cr, 'learn_progress', 'mission_id') \
                and _table_exists(cr, 'learn_mission'):
            cr.execute("""
                UPDATE learn_progress p
                   SET key = 'mission:' || m.key
                  FROM learn_mission m
                 WHERE p.mission_id = m.id
                   AND (p.key IS NULL OR p.key = '')
            """)
            _logger.info('pb_learn: carried %s mission progress row(s) onto the '
                         'new key column.', cr.rowcount)
        # A row that pointed at neither (it could not, but the constraint that
        # said so is going) would fail the NOT NULL the field declares and take
        # the whole upgrade down. Drop those instead: a progress row that names
        # nothing is not progress in anything.
        cr.execute("DELETE FROM learn_progress WHERE key IS NULL OR key = ''")
        if cr.rowcount:
            _logger.warning('pb_learn: dropped %s progress row(s) that named '
                            'neither a station nor a mission.', cr.rowcount)
        # The old uniqueness was per (user, station) and per (user, mission);
        # the new one is per (user, key). Same partition, different name — but
        # the old constraints reference columns that are about to disappear.
        for name in ('learn_progress_user_station_uniq',
                     'learn_progress_user_mission_uniq'):
            cr.execute('ALTER TABLE learn_progress DROP CONSTRAINT IF EXISTS %s'
                       % name)

    # ------------------------------------------------------------- events
    if _table_exists(cr, 'learn_event'):
        cr.execute('ALTER TABLE learn_event ADD COLUMN IF NOT EXISTS station_key varchar')
        if _column_exists(cr, 'learn_event', 'station_id') \
                and _table_exists(cr, 'learn_station'):
            cr.execute("""
                UPDATE learn_event e
                   SET station_key = s.key
                  FROM learn_station s
                 WHERE e.station_id = s.id
                   AND (e.station_key IS NULL OR e.station_key = '')
            """)
            _logger.info('pb_learn: carried %s event row(s) onto the new '
                         'station_key column.', cr.rowcount)
