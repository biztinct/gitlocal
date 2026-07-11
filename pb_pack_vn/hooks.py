# -*- coding: utf-8 -*-
"""F113 — pb_pack_vn install-time certification (D113.3).

Runs the Vietnam Standard template's sample-test suite through the validated
engine after the pack's data loads. A failing test raises and blocks the
install — a wrong statutory value or a broken formula can never ship silently.
"""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_pack_templates


def post_init_hook(env):
    certify_pack_templates(env, ['pb_pack_vn.tpl_vn_standard_2026'])
