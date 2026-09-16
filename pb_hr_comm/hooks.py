# -*- coding: utf-8 -*-
"""Install-time setup: the switches, and the default sign-off route.

`post_init_hook` fires on INSTALL ONLY — never on `-u`, a known Odoo 19 trap —
which is exactly right for both jobs here. The switches want their shipped
value once and never again (an upgrade that re-set them would undo whatever
the company had chosen), and the route wants laying once per company.

WHY THE ROUTE IS SEEDED HERE **AND** IN A MIGRATION, and it is not a
duplicate. A migration runs on a database that already HAS the module and
never on a fresh install; this runs on a fresh install and never on `-u`. The
two together are the whole of "every database ends up with a route", and
either one alone leaves half of them without one — which does not break
anything visibly (R208) and quietly means that the day somebody switches
sign-off on, nothing reaches anybody's inbox.

`Seed.lay` asks the database what is already there before it creates anything,
so running both on the same database is running one.

NEITHER IS EVER FATAL. A module that refuses to install because a default
route could not be laid is a worse outcome than a route somebody lays by hand
a minute later — and on this module the route ships switched OFF anyway.
"""

import logging

from .models.comm_common import DEFAULTS

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _seed_switches(env)
    _seed_route(env)


def _seed_switches(env):
    """Materialise the shipped defaults so an administrator can FIND them.

    Every reader still goes through `flag()`/`number()`, which fall back to
    the same table in code — so a database where these rows are missing
    behaves identically. They exist to be found and changed.
    """
    icp = env['ir.config_parameter'].sudo()
    for key, value in DEFAULTS.items():
        existing = icp.get_param(key)
        if existing is False or existing is None:
            icp.set_param(key, value)


def _seed_route(env):
    try:
        from .models.post_approval import seed_all
        laid = seed_all(env)
        _logger.info('pb_hr_comm: the announcement route was laid for %s '
                     'compan(ies)', laid)
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.warning('pb_hr_comm: the default announcement route could not '
                        'be seeded', exc_info=True)
