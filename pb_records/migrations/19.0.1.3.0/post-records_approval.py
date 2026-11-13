# -*- coding: utf-8 -*-
"""Approval Matrix P5 — the Records Desk route, and the rows that came before.

TWO THINGS.

1. Every `pb.records.apply` row that already exists IS a change that happened.
   The new `applied` flag defaults False and `state` defaults `draft`, so
   without this every past change would read on the History tab as "being
   prepared" — a screen saying four hundred records are about to be changed
   when they were changed last March.
2. `post_init_hook` runs on INSTALL only (ledger), so the route is seeded here
   too. Idempotent, so an install and this in the same pass create one of
   everything.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE pb_records_apply
           SET applied = TRUE,
               state = 'applied',
               applied_at = COALESCE(applied_at, date),
               plan_json = COALESCE(plan_json, '[]'),
               changes_json = COALESCE(changes_json, '[]'),
               people_count = COALESCE(NULLIF(people_count, 0), count_people),
               values_count = COALESCE(NULLIF(values_count, 0), count_values)
         WHERE applied IS NOT TRUE
    """)
    _logger.info('pb_records: %s existing change(s) marked as carried out',
                 cr.rowcount)
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_records.models.records_approval import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_records: the Records Desk route could not be '
                          'seeded')
