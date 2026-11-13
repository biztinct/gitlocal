# -*- coding: utf-8 -*-
"""LEARN REFRESH step 5 — carry learner progress onto the folded stations.

Three stations were retired by folding them into another:

    contracts  -> employees   (Contracts is a door inside People › Employees)
    proration  -> adjust      (Pay Run › Adjust holds Retro and Proration)
    retro      -> adjust

WHAT IT DOES, per learner and per retired key:
  * no row on the new key yet  -> the old row is re-keyed onto it;
  * a row on the new key already -> the two are merged into that row
    (the further state wins, the old row is deleted).
A retired row that said "done" arrives as "in_progress", step 0: the old
stations were outline-only, and the new ones are full lessons nobody has
taken yet. Saying "done" would tell a team lead someone finished a lesson
they have never seen; dropping the row would erase that they started.

`learn_event.station_key` is re-keyed too, so history stays attributed.

Idempotent: after one run no row carries a retired key, so a second run
finds nothing to do.
"""
import logging

_logger = logging.getLogger(__name__)

ALIASES = (('contracts', 'employees'), ('proration', 'adjust'), ('retro', 'adjust'))
RANK = {'not_started': 0, 'in_progress': 1, 'done': 2}


def migrate(cr, version):
    if not version:
        return
    moved = merged = 0
    for old, new in ALIASES:
        cr.execute("""SELECT id, user_id, state FROM learn_progress WHERE key = %s""", (old,))
        for row_id, user_id, state in cr.fetchall():
            carried = 'in_progress' if state in ('in_progress', 'done') else 'not_started'
            cr.execute("""SELECT id, state FROM learn_progress
                           WHERE key = %s AND user_id = %s""", (new, user_id))
            hit = cr.fetchone()
            if hit:
                keep_id, keep_state = hit
                if RANK.get(carried, 0) > RANK.get(keep_state, 0):
                    cr.execute("""UPDATE learn_progress SET state = %s WHERE id = %s""",
                               (carried, keep_id))
                cr.execute("DELETE FROM learn_progress WHERE id = %s", (row_id,))
                merged += 1
            else:
                cr.execute("""UPDATE learn_progress
                                 SET key = %s, state = %s, step_index = 0,
                                     completed_at = NULL
                               WHERE id = %s""", (new, carried, row_id))
                moved += 1
        cr.execute("""UPDATE learn_event SET station_key = %s WHERE station_key = %s""",
                   (new, old))
    _logger.info('pb_learn 19.0.19.0.0: %s progress row(s) re-keyed, %s merged '
                 'onto folded stations.', moved, merged)
