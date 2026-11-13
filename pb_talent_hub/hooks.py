# -*- coding: utf-8 -*-
"""Install step of the Talent hub (NAV P2).

`pb_vendor_access` writes the role lane of every left-menu entry, but it may
load before this module on the run that creates GROW › Talent, so its pass
finds nothing to gate. Ask it again now the entry exists. Additive and
idempotent; never fails an install; a database without `pb_vendor_access`
simply keeps the permission lane of the data file.
"""
import logging

_logger = logging.getLogger(__name__)


def gate_menu(env):
    if 'pb.role.profile' not in env:
        return
    try:
        from odoo.addons.pb_vendor_access.hooks import (ensure_catalogue,
                                                        ensure_screen_gates)
        # Create-only: the roles this entry is gated on may have arrived
        # with a module installed after pb_vendor_access.
        ensure_catalogue(env)
        ensure_screen_gates(env)
    except Exception:                   # noqa: BLE001
        _logger.exception('pb_talent_hub: the Talent entry could not be gated')


def post_init_hook(env):
    gate_menu(env)
