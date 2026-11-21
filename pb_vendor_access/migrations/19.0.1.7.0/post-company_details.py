# -*- coding: utf-8 -*-
"""The ability that opens "Your company" (ACCESS P9).

R84/ledger A2 — `post_init_hook` fires on INSTALL ONLY, so a catalogue that
grows grows on fresh installs and nowhere else unless a migration asks for it.
This is that ask, and it is the fourth one: every version that adds to the
catalogue ships one.

WHAT IT ADDS. One ability, "Correct this company's own details", wrapping the
one permission P9 created. Seeding an ability hands nobody anything — an
ability no role names is a sentence in a list — so on its own this changes what
precisely zero people can do.

THE ONE JUDGEMENT IN HERE, AND WHY IT IS SAFE. `ensure_tenant_admin_role` is
CREATE-ONLY (ledger E3): a role that already exists is left exactly as it is,
because adding an ability to a role somebody already holds WIDENS what they can
do, silently, during an upgrade. That rule is right and it stays. But it leaves
a database that was seeded before today with a Tenant administrator bundle that
is one ability short of the one a new tenant gets, which is a difference nobody
would ever find.

So this migration closes it in the ONE case where closing it cannot widen
anybody's access: when NOBODY HOLDS THE ROLE. Then there is no "somebody"
to widen. Where the role does have holders it is left alone and the log says
so, and ticking the ability on is two clicks in the role builder with an audit
line — which is exactly what H2 said to do.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

_ABILITY = 'company-details'


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import (TENANT_ADMIN_XMLID,
                                                    ensure_catalogue)
    ensure_catalogue(env)

    ability = env['pb.role.ability'].sudo().with_context(
        active_test=False).by_keys([_ABILITY])
    if not ability:
        # The permission lives in `pb_settings`; a build without it is a build
        # where this ability has nothing to wrap, and the catalogue skips it by
        # design (it never seeds a record whose partner may not exist).
        _logger.info(
            'pb_vendor_access: the "%s" ability is not on this database — the '
            'company-details permission it wraps is not installed here',
            _ABILITY)
        return

    role = env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
    if not role or role._name != 'pb.role.profile':
        _logger.info(
            'pb_vendor_access: no Tenant administrator role on this database, '
            'so there is nothing to add the new ability to')
        return
    if ability.id in role.ability_ids.ids:
        return
    if role.holder_count:
        _logger.warning(
            'pb_vendor_access: "%s" already has %s holder(s), so the new "%s" '
            'ability is NOT added to it by this upgrade — widening a role '
            'somebody holds is never done by a deploy. Tick it on in the role '
            'builder if it is wanted; the audit trail will say who did.',
            role.name, role.holder_count, _ABILITY)
        return
    role.sudo().write({'ability_ids': [(4, ability.id)]})
    _logger.info(
        'pb_vendor_access: "%s" gained the "%s" ability — nobody held the role, '
        'so nobody\'s access was widened by adding it',
        role.name, _ABILITY)
