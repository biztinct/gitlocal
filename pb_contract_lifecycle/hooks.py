# -*- coding: utf-8 -*-
"""Install-time setup.

TWO THINGS, both idempotent, both also reachable from the daily job.

  1. The two contract types this module wants to exist — ENSURED by name, never
     seeded as records, because the standard `hr` module already ships twelve
     types on this database and "Intern" is one of them. A `<record>` of our own
     would put a second row called Intern in the picker.
  2. An honest employment type on everybody already here. Without it the
     Contracts lens opens on a database of five thousand people and shows only
     the handful with an end date on their paperwork, and the analytics
     contractor count has nothing new to read.

`post_init_hook` fires on INSTALL ONLY — never on `-u` (a known Odoo 19 trap) —
which is exactly right: the backfill must not re-decide anything on every
upgrade. The body is written idempotently anyway (it only ever looks at records
still on the field's default), so calling it by hand is safe, and the daily job
calls the same two methods as a top-up for records that arrived through a route
which bypassed it (R44).
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _ensure_types(env)
    _backfill_types(env)
    _seed_approval_routes(env)


def _ensure_types(env):
    try:
        return env['hr.employee']._pb_ensure_contract_types()
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.exception('pb_contract_lifecycle: the contract types could '
                          'not be ensured')
        return {}


def _backfill_types(env):
    try:
        counts = env['hr.employee']._pb_backfill_employment_type()
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.exception('pb_contract_lifecycle: the employment-type '
                          'backfill did not run')
        return False
    env['ir.config_parameter'].sudo().set_param(
        'pb_contract_lifecycle.backfill_done',
        '%s looked at, %s interns, %s contractors, %s other' % (
            counts.get('looked_at', 0), counts.get('intern', 0),
            counts.get('contractor', 0), counts.get('other', 0)))
    return counts


# ---------------------------------------------------------------- approvals
# A fresh install runs no migration, so this is where a brand-new database
# gets its default approval route. Idempotent, and deliberately never fatal:
# a module that cannot be installed because a route could not be laid is a
# worse outcome than a route somebody lays later (ledger AM70/AM75).
def _seed_approval_routes(env):
    import logging
    logger = logging.getLogger(__name__)
    try:
        from .models.contract_extension_approval import seed_all
        seed_all(env)
    except Exception:       # noqa: BLE001
        logger.exception('the default approval route could not be laid')
