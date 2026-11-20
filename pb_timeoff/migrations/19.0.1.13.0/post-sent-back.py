# -*- coding: utf-8 -*-
"""WORKFLOW-2 P6c (D36): mark the time-off requests that were SENT BACK.

The mark (`hr.leave.pb_sent_back`) is new in this version; requests sent back
before it existed are refused with nothing on them to say so. No guesswork:
a request gets the mark only where its approval provably was sent back —
the LATEST approval request for that time off (highest attempt, then id) is
in state ``returned`` (the engine's `_do_return`, which also keeps the
reason in ``return_note``) AND the time off is still refused. A request an
officer later moved back to waiting, or one refused on a later attempt, has a
different latest request and is left alone.

Idempotent: only rows not marked yet are touched; a second run marks 0. The
count is logged before anything is written. Nothing else changes: no status,
no balance, no message, no email.
"""
import logging

_logger = logging.getLogger(__name__)

_FIND = """
    WITH latest AS (
        SELECT DISTINCT ON (r.res_id) r.res_id, r.state
          FROM biz_approval_request r
         WHERE r.res_model = 'hr.leave'
         ORDER BY r.res_id, r.attempt DESC, r.id DESC
    )
    SELECT l.id
      FROM hr_leave l
      JOIN latest ON latest.res_id = l.id
     WHERE l.state = 'refuse'
       AND latest.state = 'returned'
       AND l.pb_sent_back IS NOT TRUE
     ORDER BY l.id
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('biz_approval_request') IS NOT NULL")
    if not cr.fetchone()[0]:
        _logger.info('pb_timeoff P6c: no approval requests here; '
                     '0 time-off requests marked sent back')
        return
    cr.execute(_FIND)
    ids = [row[0] for row in cr.fetchall()]
    _logger.info('pb_timeoff P6c: %s time-off request(s) were sent back '
                 'before the mark existed; marking them now', len(ids))
    if not ids:
        return
    cr.execute("UPDATE hr_leave SET pb_sent_back = TRUE "
               "WHERE id = ANY(%s) AND pb_sent_back IS NOT TRUE", (ids,))
    _logger.info('pb_timeoff P6c: %s time-off request(s) marked sent back',
                 cr.rowcount)
