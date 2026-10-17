# -*- coding: utf-8 -*-
"""Finish the routes a broken adapter left half-laid, and lay the rest.

TWO ROUTES SPENT A PHASE AS DRAFTS NOBODY COULD SEE. `letters` and `verdict`
each had an adapter whose `_approval_capabilities()` or whose definition the
engine refused — a related Selection read as a callable, and a manager step on
a process that said it had no manager mode. `biz.approval.seed.lay` created
the workflow and the draft, hit the refusal, and returned before the binding.
Nothing crashed and nothing was in force; the Matrix simply showed them as not
set up.

Both causes are fixed, and `lay` no longer leaves a workflow behind when it is
refused. What it cannot do is go back for the ones already written down, so
this does: `seed_all` finds each half-laid route, validates it — now
successfully — publishes it and binds it.

An `end-` script for the reason every relay in this module is one (ledger
AM75): it asks the REGISTRY which adapters exist, and that question only has
its real answer after the whole graph is loaded.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_approval_config.models.seed import seed_all

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT p.key, count(*)
          FROM biz_approval_workflow w
          JOIN biz_approval_process p ON p.id = w.process_id
          JOIN biz_approval_workflow_version v ON v.workflow_id = w.id
         WHERE v.status = 'draft'
           AND NOT EXISTS (SELECT 1 FROM biz_approval_binding b
                            WHERE b.workflow_id = w.id AND b.active)
         GROUP BY p.key
    """)
    half = cr.fetchall()
    if half:
        _logger.info('pb_approval_config: finishing half-laid routes: %s',
                     dict(half))
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_approval_config: the adapter routes could not '
                          'be seeded')
