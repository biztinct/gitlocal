# -*- coding: utf-8 -*-
"""Give every existing company the route it has always followed.

`post_init_hook` runs on install only (ledger), so an upgraded database would
otherwise have the adapter and no route to resolve — every submission refused
with "there is no approval set up for this yet". Same function, same
idempotence; it simply has to be called from here too.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_payruns.models.approval_seed import seed_all


def migrate(cr, version):
    if not version:
        return
    seed_all(api.Environment(cr, SUPERUSER_ID, {}))
