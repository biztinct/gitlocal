# -*- coding: utf-8 -*-
"""NAV P2 — Hiring is its own left-menu entry; give it its role lane.

The entry (`data/pb_sidebar.xml`) is created by this upgrade; `pb_vendor_access`
loads before this module and so could not gate it. Additive and idempotent.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_hiring.hooks import gate_hiring_menu
    gate_hiring_menu(env)
