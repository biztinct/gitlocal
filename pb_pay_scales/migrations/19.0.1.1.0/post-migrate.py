# -*- coding: utf-8 -*-
"""WDGAP S8-D: a database that already had pay scales gets the "Pay scale
rises" route seeded for every company (a fresh install does it in the
post-init hook). Writes no contract, no pay line, no payslip."""
from odoo import SUPERUSER_ID, api

from odoo.addons.pb_pay_scales.models.scale_raise import seed_all


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    seed_all(env)
