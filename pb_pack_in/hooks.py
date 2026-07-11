# -*- coding: utf-8 -*-
"""F113 — pb_pack_in install-time certification (D113.3). Ships draft."""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_pack_templates


def post_init_hook(env):
    certify_pack_templates(env, ['pb_pack_in.tpl_in_standard_2026'])
