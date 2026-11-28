# -*- coding: utf-8 -*-
"""A role was one permission group. It is now a bundle of abilities.

WHAT THIS HAS TO ACHIEVE, AND THE BAR IT HAS TO CLEAR. Nothing on the Access &
delegation board may look one pixel different afterwards. Every role that
existed still exists, with the same name, the same sentence, the same area, the
same place in the list and the same people holding it — because every one of
them becomes a bundle of exactly ONE ability, wrapping exactly the one
permission that role already handed out. Not a single user's permissions are
read, written or touched by this script.

WHY IT IS A CALL AND NOT A SCRIPT. `ensure_catalogue()` already knows how to
find a role from before bundles existed (its frozen `group_id` column is unique,
so it is an exact key), how to create the ability behind it, and how to attach
the two. Writing that logic a second time here is how the two copies come to
disagree on the third database. R84 is the other half of it: `post_init_hook`
fires on INSTALL ONLY, so an upgrade adds nothing to the catalogue unless a
migration asks it to — which is exactly why the twelve new abilities this
version introduces need this file to exist at all.

IT IS SAFE TO RUN TWICE. Abilities are found by their unique key and roles by
the permission they used to carry, so a second pass creates nothing and links
nothing.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import ensure_catalogue
    res = ensure_catalogue(env)

    cr.execute("""
        SELECT COUNT(*) FROM pb_role_profile p
         WHERE p.group_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM pb_role_profile_ability_rel r
                            WHERE r.profile_id = p.id)
    """)
    unbundled = cr.fetchone()[0]
    _logger.info(
        'pb_vendor_access: roles are bundles now — %s abilities created, '
        '%s roles given theirs, %s roles created, %s left unbundled',
        res['abilities']['created'], res['linked'], res['created'], unbundled)
    if unbundled:
        # R92 — the failure that matters here is silent by nature: a role with
        # an empty bundle reads as "nobody holds this" on a board that was
        # right yesterday.
        _logger.warning(
            'pb_vendor_access: %s roles still carry a permission with no '
            'ability behind it and will show no holders — look at them',
            unbundled)
