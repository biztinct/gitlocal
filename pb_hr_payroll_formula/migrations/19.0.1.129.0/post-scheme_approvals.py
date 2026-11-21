# -*- coding: utf-8 -*-
"""Approval Matrix P4 — what an upgrade has to do that an install does for free.

Two things:

1. Every release that already exists was signed off by the person who sealed
   it, under the rules of the day. The new `state` column defaults to
   `approved` for new rows; this writes it onto the old ones, because a NULL
   there would read as "nobody has approved this" about a release that is
   already live.

2. `post_init_hook` does NOT run on `-u` (ledger), so the scheme-change route
   is seeded here as well. It is idempotent, so a database that got it from the
   install hook is untouched.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE hr_formula_release SET state = 'approved'
        WHERE state IS NULL
    """)
    _logger.info('pb_hr_payroll_formula: %s existing release(s) marked '
                 'approved', cr.rowcount)
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_hr_payroll_formula.models.scheme_seed import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_hr_payroll_formula: the scheme-change route '
                          'could not be seeded')
