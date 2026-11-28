# -*- coding: utf-8 -*-
"""The role a tenant's own administrator holds (ACCESS P5).

R84/ledger A2 — `post_init_hook` fires on INSTALL ONLY. A catalogue that grows
therefore grows on fresh installs and nowhere else unless a migration asks for
it, and the difference is invisible until somebody goes looking for a role that
is not there. So every version that adds to the catalogue ships one of these.

WHAT IT ADDS. One role, "Tenant administrator", built out of abilities that were
already seeded — the administrator tier of pay, people, joining and leaving,
budgets, reporting, the connected systems, the calculation rules, the supplier
register, the audit trail, and who here can do what. It is what a customer's own
administrator will hold INSTEAD of the system administrator permission they hold
today.

WHAT IT CAREFULLY DOES NOT DO. It changes nobody's permissions. Seeding a role
hands it to no one — somebody has to be given it, on the board, by a person who
holds it. Demoting an account that currently holds the system administrator
permission is a separate, explicit act (`pb.tenants`), it is armed only for
databases created after this, and it never runs by itself.

It also re-runs the left-menu gates, because the new role belongs on the entries
its abilities already open. That pass is additive and idempotent: it only ever
ADDS a role to an entry, so nobody loses a door and nothing anybody has since
edited on the Screens lens is undone. On a database where nobody holds the new
role — which is every database on the day this runs — it changes what precisely
zero people can see, and the report for this phase proves it.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import (TENANT_ADMIN_XMLID,
                                                    ensure_catalogue,
                                                    ensure_screen_gates)
    ensure_catalogue(env)
    ensure_screen_gates(env)

    role = env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
    if not role:
        _logger.warning(
            'pb_vendor_access: the Tenant administrator role was not seeded on '
            'this database — see the catalogue log above for which ability was '
            'missing')
        return
    _logger.info(
        'pb_vendor_access: Tenant administrator ready — %s abilities, %s '
        'permissions, held by %s people (which should be nobody on the day of '
        'the upgrade)',
        len(role.ability_ids), len(role.group_ids), role.holder_count)
