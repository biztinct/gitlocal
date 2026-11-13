# -*- coding: utf-8 -*-
"""Tenant administrator chooses who approves what (owner, 2026-11-12, D22).

UPDATES P6. A client's own administrator opens approvals set-up for their own
company — the Approval Matrix: routes, who holds each step, backups — and
publishes the routes they choose. The role gains ONE ability, "Approval
routes — publish" (`biz_approval_workflow.group_approval_publish`, which
implies "write"). Not "Approvals administrator": arranging somebody else's
cover and moving a waiting step stay a role given on purpose.

`ensure_tenant_admin_role` is create-only, so the widening of an EXISTING
role is done here, once, through the role service itself
(`biz_access/models/role_assignments.py`, `ManagedRole.write`):

  * the ability is added to the role (an administrator who has since taken
    abilities off the role keeps that: only this one is added);
  * the role service gives the new part to every person the role is ASSIGNED
    to (`pb.role.assignment`; a permanent hand-over of the role too) and
    writes the role's History row (`pb.role.change`): who changed it, why,
    the role before and after, and the people it reached;
  * the role's sentence is replaced only where it still reads exactly as
    shipped on 2026-10-01 (a reworded sentence is somebody's own).

The rails that make this safe — the engine's catalogue, the platform's own
row and seat, and the platform's support login — are `pb_approval_config`
19.0.1.8.0 (`models/setup_rails.py`).
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

REASON = ("Owner decision 12 November 2026: a client's own administrator "
          "chooses who approves what in their company (approvals set-up).")


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import (
        TENANT_ADMIN_ADDED_20261112, TENANT_ADMIN_DESCRIPTION,
        TENANT_ADMIN_DESCRIPTION_20261001, TENANT_ADMIN_XMLID,
        ensure_catalogue)

    ensure_catalogue(env)
    role = env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
    if not role or role._name != 'pb.role.profile':
        _logger.info('pb_vendor_access 1.17.0: no Tenant administrator role '
                     'on this database — nothing widened')
        return
    role = role.sudo()
    extra = env['pb.role.ability'].by_keys(list(TENANT_ADMIN_ADDED_20261112))
    if not extra:
        _logger.warning('pb_vendor_access 1.17.0: the approvals publish '
                        'ability is not on this database — nothing widened')
        return
    missing = extra - role.ability_ids
    if not missing:
        _logger.info('pb_vendor_access 1.17.0: Tenant administrator already '
                     'carries approvals set-up — nothing to do')
        return
    vals = {'ability_ids': [(4, a.id) for a in missing]}
    env.cr.execute(
        "SELECT description->>'en_US' FROM pb_role_profile WHERE id = %s",
        [role.id])
    current = (env.cr.fetchone() or [''])[0] or ''
    reworded = current.strip() != TENANT_ADMIN_DESCRIPTION_20261001.strip()
    if not reworded:
        vals['description'] = TENANT_ADMIN_DESCRIPTION
    role.with_context(lang='en_US', pb_access_reason=REASON).write(vals)
    role.invalidate_recordset()
    if not reworded:
        from odoo.addons.pb_vendor_access.catalogue_vi import LANG, VI
        vi = VI.get(TENANT_ADMIN_DESCRIPTION)
        if vi and env['res.lang'].sudo().search_count([('code', '=', LANG)]):
            role.update_field_translations('description', {LANG: vi})
    change = env['pb.role.change'].sudo().search(
        [('profile_id', '=', role.id)], order='id desc', limit=1) \
        if 'pb.role.change' in env else None
    _logger.info(
        'pb_vendor_access 1.17.0: Tenant administrator gained %s (revision '
        '%s); reached: %s; sentence %s',
        ', '.join(missing.mapped('technical_key')), role.revision,
        ', '.join(change.user_ids.mapped('login')) if change else 'n/a',
        'kept (reworded)' if reworded else 'updated')
