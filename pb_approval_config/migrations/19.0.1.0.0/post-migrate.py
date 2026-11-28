# -*- coding: utf-8 -*-
"""`post_init_hook` runs on INSTALL only (ledger). This mirrors it for `-u`, so
a database that was upgraded rather than freshly installed still ends up with a
default route for every company. The seed asks before it writes, so running
both in the same pass creates exactly one of everything."""

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_approval_config.models.seed import seed_all


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    seed_all(env)
