# -*- coding: utf-8 -*-
"""Install step of the Learning hub (LEARNING L0).

Cloned from `pb_talent_hub`. `pb_vendor_access` writes the role lane of every
left-menu entry, but it may load before this module on the run that creates
GROW › Learning. Learning has NO row in `SCREEN_GATES` on purpose — it is
everybody's, like Home and Help — so today this pass finds nothing to gate;
the hook stays so that adding a row later needs no new install step.
Additive and idempotent; never fails an install.
"""
import logging

_logger = logging.getLogger(__name__)


def gate_menu(env):
    if 'pb.role.profile' not in env:
        return
    try:
        from odoo.addons.pb_vendor_access.hooks import (ensure_catalogue,
                                                        ensure_screen_gates)
        ensure_catalogue(env)
        ensure_screen_gates(env)
    except Exception:                   # noqa: BLE001
        _logger.exception('pb_learning_hub: the Learning entry could not be '
                          'gated')


def post_init_hook(env):
    gate_menu(env)
