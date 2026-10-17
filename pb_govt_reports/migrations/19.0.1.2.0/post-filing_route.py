# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Every company gets the filing route on an upgrade too.

`post_init_hook` runs on INSTALL only, and every database this ships to
already has this module (ledger AM70/AM91). A fresh database runs no migration
at all, so both halves exist and both are idempotent.
"""

from odoo.addons.pb_govt_reports.models.filing_approval import seed_all


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    seed_all(env)
