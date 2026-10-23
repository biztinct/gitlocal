# -*- coding: utf-8 -*-
"""NAV P2 — the role lane on the regrouped left menu.

`SCREEN_GATES` gained Hiring, Expenses and Talent and lost Lifecycle (now off
the menu). `post_init_hook` fires on INSTALL only, so an upgrade has to ask.
Additive and idempotent: it never takes a role off an entry, and an entry
somebody has edited on the Screens lens (`access_customized`) is left alone.

Entries owned by modules that load AFTER this one (pb_hiring, pb_expenses_hub,
pb_talent_hub) may not exist yet when this runs; they are skipped here and
gated by those modules' own install/upgrade step, which calls the same
function.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import (ensure_catalogue,
                                                    ensure_screen_gates)
    # Create-only: a role whose permission arrived with a module installed
    # after this one (the hiring tiers) is added before the gates ask for it.
    ensure_catalogue(env)
    result = ensure_screen_gates(env)
    _logger.info('pb_vendor_access NAV P2: left-menu role gates %s', result)
