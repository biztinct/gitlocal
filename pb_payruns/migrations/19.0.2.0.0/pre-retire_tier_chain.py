# -*- coding: utf-8 -*-
"""Retire the three-tier ladder — but never on top of a run that is in it.

THE SAFETY CHECK IS THE POINT. After this upgrade `level0`, `level1` and
`level2` are not states a pay run can be in, so a run sitting in one of them
would become a row nothing can read, nothing can approve and nothing can walk
back. If any exist the upgrade STOPS and names them, so somebody can finish or
reject them on the old ladder first and run the upgrade again.

Everything else here is tidying: the columns the old ladder wrote to, and the
system parameter that switched the Officer tier on and off.
"""

import logging

_logger = logging.getLogger(__name__)

_OLD_STATES = ('level0', 'level1', 'level2')
_DROPPED_COLUMNS = (
    'pb_sendback_note', 'pb_sendback_uid', 'pb_sendback_date',
    'pb_sendback_from',
)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT id, name, state FROM hr_payslip_run
        WHERE state IN %s ORDER BY id
    """, (_OLD_STATES,))
    stuck = cr.fetchall()
    if stuck:
        listed = ', '.join('%s' % (name or '#%s' % rid)
                           for rid, name, _state in stuck[:20])
        more = ' and %s more' % (len(stuck) - 20) if len(stuck) > 20 else ''
        raise Exception(
            "This update cannot be installed while %s pay run(s) are still "
            "part-way through the old approval chain: %s%s. Finish or reject "
            "them first, then update again."
            % (len(stuck), listed, more))

    for column in _DROPPED_COLUMNS:
        cr.execute("ALTER TABLE hr_payslip_run DROP COLUMN IF EXISTS %s"
                   % column)
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s",
               ('pb_payruns.officer_review',))
    _logger.info('pb_payruns: the three-tier approval chain is retired')
