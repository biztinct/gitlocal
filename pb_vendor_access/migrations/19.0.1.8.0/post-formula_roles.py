# -*- coding: utf-8 -*-
"""Three roles for the calculation engine, so somebody can find one.

THE HOLE THIS CLOSES. `formula-view`, `formula-build` and `formula-admin` have
been in the ability catalogue since it was first seeded, and NO ROLE NAMED ANY
OF THEM. The only way to reach the Formula Studio was the Tenant administrator
bundle, which means an administrator looking down a list of twenty-four roles
for "the formula one" found nothing — because there was nothing to find — while
the studio itself went on refusing them by name. Found on a newly provisioned
tenant whose own administrator could not open it.

R84/ledger A2 — `post_init_hook` fires on INSTALL ONLY, so a catalogue that
grows grows on fresh installs and nowhere else unless a migration asks for it.
This is that ask, and it is the fifth one: every version that adds to the
catalogue ships one.

IT GRANTS NOBODY ANYTHING. Seeding a role writes a row in a catalogue; somebody
still has to press "Give a role" against a name, and the audit trail records
that they did. Nothing about anybody's permissions changes here.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

_KEYS = ('formula-view', 'formula-build', 'formula-admin')


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import ensure_catalogue
    ensure_catalogue(env)

    Profile = env['pb.role.profile'].sudo().with_context(active_test=False)
    abilities = env['pb.role.ability'].sudo().with_context(
        active_test=False).by_keys(list(_KEYS))
    if not abilities:
        # The permissions live in `pb_hr_payroll_formula`; a build without it
        # is a build where these abilities have nothing to wrap, and the
        # catalogue skips them by design.
        _logger.info(
            'pb_vendor_access: the formula-engine abilities are not on this '
            'database — the calculation engine is not installed here')
        return
    for ability in abilities:
        roles = Profile.search([('ability_ids', 'in', ability.ids)]).filtered(
            lambda p, a=ability: set(p.ability_ids.ids) == {a.id})
        if roles:
            _logger.info(
                'pb_vendor_access: "%s" is on the roles list as "%s"',
                ability.technical_key, roles[0].name)
        else:
            _logger.warning(
                'pb_vendor_access: no role stands for "%s" after reseeding — '
                'the Formula Studio can still only be reached through a wider '
                'bundle', ability.technical_key)
