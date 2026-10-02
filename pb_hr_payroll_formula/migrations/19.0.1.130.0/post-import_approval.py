# -*- coding: utf-8 -*-
"""Approval Matrix P5 — the two pay-data routes, on an upgrade.

`post_init_hook` runs on INSTALL only (ledger). Without this a pay-data file
would have an adapter and no route, and the first press of Commit import would
be refused with "there is no approval set up for this yet". Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_hr_payroll_formula.models.payroll_import_approval \
        import seed_all
    try:
        seed_all(env)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_hr_payroll_formula: the pay-data routes could '
                          'not be seeded')
