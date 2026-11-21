# -*- coding: utf-8 -*-
"""The last uncovered groups get roles, and Tenant administrator is widened.

1. ROLES. Approvals (five), the AI assistant (three), learning content, the
   seven per-country payroll switches and the demo login each gate on groups
   no role carried (owner, 2026-10-01). `ensure_catalogue` seeds them — R84,
   the hook runs on install only.

2. TENANT ADMINISTRATOR, WIDENED ONCE AND ON PURPOSE. `ensure_tenant_admin_role`
   is create-only precisely so an upgrade can never widen somebody's access by
   itself. The owner decided on 2026-10-01 that the role should carry the top
   tier of the areas added since (hiring, goals, training, announcements,
   where they work, group set-up), so it is done HERE, once, and logged.

   A role is held by holding all of its permissions, so widening it would
   quietly turn every current holder into a non-holder. Each person who held
   it BEFORE the change is therefore granted the new part through the board's
   own `grant`, which writes the History row — nobody gains anything without a
   record saying who, what and why.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import (
        TENANT_ADMIN_ADDED_20261001, TENANT_ADMIN_DESCRIPTION,
        TENANT_ADMIN_XMLID, ensure_catalogue)

    result = ensure_catalogue(env)
    _logger.info('pb_vendor_access 1.10.0: catalogue reseeded — created %s, '
                 'not offered %s', result.get('created'), result.get('absent'))

    role = env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
    if not role or role._name != 'pb.role.profile':
        return
    extra = env['pb.role.ability'].by_keys(list(TENANT_ADMIN_ADDED_20261001))
    missing = extra - role.ability_ids
    holders = role._holder_users()
    if missing:
        role.sudo().write({'ability_ids': [(4, a.id) for a in missing],
                           'description': TENANT_ADMIN_DESCRIPTION})
        role.invalidate_recordset()
        # The Vietnamese of the NEW sentence. `apply_catalogue_vi` leaves a
        # row alone once it holds Vietnamese, and this one holds the old
        # sentence's — so the widening writes its own.
        from odoo.addons.pb_vendor_access.catalogue_vi import LANG, VI
        vi = VI.get(TENANT_ADMIN_DESCRIPTION)
        if vi and env['res.lang'].sudo().search_count([('code', '=', LANG)]):
            role.sudo().update_field_translations('description', {LANG: vi})
    _logger.info(
        'pb_vendor_access 1.10.0: Tenant administrator gained %s; holders '
        'before the change: %s',
        ', '.join(missing.mapped('technical_key')) or 'nothing',
        ', '.join(holders.mapped('login')) or 'nobody')
    Access = env['pb.access']
    for user in holders:
        try:
            with env.cr.savepoint():
                Access.grant(role.id, user.id, reason=(
                    "The owner widened Tenant administrator to hiring, goals, "
                    "training, announcements, where they work and group "
                    "set-up (1 October 2026); this person already held it."))
        except Exception as exc:                # noqa: BLE001
            # "already has it" is the harmless case — nothing was missing.
            _logger.info('pb_vendor_access 1.10.0: %s not re-granted (%s)',
                         user.login, exc)
