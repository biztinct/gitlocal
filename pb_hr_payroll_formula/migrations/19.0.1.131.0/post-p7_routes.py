# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The four P7 routes this module owns, on an upgrade as well as an install.

`post_init_hook` runs on INSTALL only and every live database already has this
module, so a route laid only by the hook is a route no live database has
(ledger AM70). A fresh database runs no migration at all, so both halves exist
and both are idempotent (ledger AM91).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_hr_payroll_formula.models.demo_approval import (
    seed_all as seed_demo,
)
from odoo.addons.pb_hr_payroll_formula.models.mapping_approval import (
    seed_all as seed_mappings,
)
from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import (
    seed_all as seed_schememap,
)
from odoo.addons.pb_hr_payroll_formula.models.statutory_approval import (
    seed_all as seed_statutory,
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    seed_statutory(env)
    seed_mappings(env)
    seed_schememap(env)
    seed_demo(env)
