# -*- coding: utf-8 -*-
"""Install-time setup.

ONE THING: every employee already on this database gets a trial state. Without
it the Probation lens opens on a database of five thousand people and shows
nothing, the buddy check has no state to read, and the daily job cannot tell a
person who is still in their trial period from a person who joined in 2019.

`post_init_hook` fires on INSTALL ONLY — never on `-u` (a known Odoo 19 trap) —
which is exactly right here: the backfill must not re-run and re-decide
anything on every upgrade. The body is written idempotently anyway (it only
ever touches rows that have NO state), so calling it by hand from a shell is
safe, and the daily job calls the same method as a top-up for records that
arrived through a route which bypassed `create`.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _backfill_probation(env)
    _stamp_defaults(env)


def _backfill_probation(env):
    try:
        counts = env['hr.employee']._pb_backfill_probation_state()
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.exception('pb_probation: the trial-state backfill did not run')
        return False
    env['ir.config_parameter'].sudo().set_param(
        'pb_probation.backfill_done',
        '%s na, %s in probation, %s passed' % (
            counts.get('na', 0), counts.get('in_probation', 0),
            counts.get('passed', 0)))
    return counts


def _stamp_defaults(env):
    """Nothing to force — every parameter has a working default in code.

    Kept as an explicit no-op rather than deleted, because the next person to
    read this file will look for it: the SWITCHES deliberately live in
    `probation_common.DEFAULTS` and not in a `noupdate="1"` data file, for the
    reason P3 and P4 both wrote down — a record shipped for a switch freezes
    whatever value a test run happened to leave behind, because the next
    upgrade never corrects it.
    """
    return True
