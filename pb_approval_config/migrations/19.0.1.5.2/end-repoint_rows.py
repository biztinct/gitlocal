# -*- coding: utf-8 -*-
"""Point every catalogue row at its record, and say which rows cover which.

TWO THINGS A SEED LEARNED TO DO AFTER IT HAD ALREADY RUN.

  * A row names the record that can hold a request as soon as the ADAPTER
    exists — not only where this database has a reason to lay a route. The
    demo-data adapter is in the registry on every payroll database and its
    row was left unpointed wherever no demo module was installed, so the
    Matrix said "Not connected yet", which says nobody is checking it, about
    a row that is wired up and unused.
  * Two rows are answered by ANOTHER row rather than by an adapter of their
    own — a retro line travels its pay-data load, a reopen is the pay-run
    request's own send-back — and `covered_by_key` is how they say so.

Both are written by the owning adapter's own seed, so re-running the seed is
the whole of this script. An `end-` script for the reason every relay in this
module is one (ledger AM75): it asks the REGISTRY what it contains, and that
question only has its real answer after the whole graph is loaded.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_approval_config.models.seed import seed_all

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_approval_config: the catalogue rows could not '
                          'be repointed')
    cr.execute("""
        SELECT count(*) FROM biz_approval_process
         WHERE (model_name IS NULL OR model_name = '')
           AND (covered_by_key IS NULL OR covered_by_key = '')
    """)
    left = cr.fetchone()[0]
    _logger.info('pb_approval_config: %s catalogue row(s) still name neither '
                 'a record nor a row that covers them (each one is a module '
                 'this database does not have)', left)
