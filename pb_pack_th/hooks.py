# -*- coding: utf-8 -*-
"""F113 — pb_pack_th install-time certification (D113.3).

Runs the Thailand template's sample-test suite through the validated engine after
the pack's data loads; a failing test blocks the install. Ships state=draft —
harness-green proves the structure, not the 2026 statutory figures (see report).
"""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_pack_templates


def post_init_hook(env):
    certify_pack_templates(env, ['pb_pack_th.tpl_th_standard_2026'])
