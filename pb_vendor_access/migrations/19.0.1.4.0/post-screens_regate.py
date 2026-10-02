# -*- coding: utf-8 -*-
"""The left menu was open to everybody. This puts the roles on it.

WHAT WAS WRONG. Every one of the nine live entries carried ZERO permissions
(ledger B6) — the 104 group links from before the menu was redesigned sit on the
entries that were retired — so every internal user saw the whole menu and every
role's "opens on the left menu" column was honestly empty. The Access home could
say who held what and could not say what any of it opened, because nothing was
gated.

WHAT THIS DOES, AND WHAT IT DELIBERATELY DOES NOT. It adds the ROLE lane: the
roles that open each entry, written onto the rows themselves. The PERMISSION lane
— the older groups the screens behind each entry actually check — is shipped in
the hub modules' own data files in the same change, because those files are
`noupdate="0"` and an upgrade re-asserts them (ledger C2); a gate written only
here would be wiped by the next `-u` of the module that owns the row.

NOBODY LOSES A DOOR THEY HAD A REASON TO HAVE. The two lanes are an OR, and the
permission lane names exactly the groups the screens behind each entry already
gate on — so somebody who could use Pay Run yesterday can still reach it today,
whether they get there through a role or through the permission they have held
all along.

IT ONLY EVER ADDS. `ensure_screen_gates` writes with a `(4, id)` and never a
`(6, 0, …)`, so a gate somebody has since edited on the Screens lens survives
the next upgrade, and running this twice changes nothing.

R84/ledger A2 — `post_init_hook` fires on INSTALL ONLY, so an upgrade puts these
gates on only because this file asks it to.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import (ensure_catalogue,
                                                    ensure_screen_gates)
    # The catalogue first: a gate is a pointer at a role, and a role that was
    # never seeded on this database cannot be pointed at. Idempotent.
    ensure_catalogue(env)
    res = ensure_screen_gates(env)

    cr.execute("""
        SELECT COUNT(*) FROM pb_sidebar_item i
         WHERE i.active
           AND NOT EXISTS (SELECT 1 FROM pb_sidebar_item_role_rel r
                            WHERE r.item_id = i.id)
           AND NOT EXISTS (SELECT 1 FROM pb_sidebar_item_res_groups_rel g
                            WHERE g.pb_sidebar_item_id = i.id)
    """)
    open_to_all = cr.fetchone()[0]
    _logger.info(
        'pb_vendor_access: left-menu gates — %s entries gated, %s role links '
        'added, %s skipped; %s entries remain open to everybody with a login',
        res['gated'], res['added'], res['absent'], open_to_all)
