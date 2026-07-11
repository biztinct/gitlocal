# -*- coding: utf-8 -*-
"""F113 — pb_pack_my install-time certification (D113.3).

Runs the Malaysia template's sample-test suite through the validated engine after
the pack's data loads; a failing test blocks the install. Ships state=draft —
harness-green proves the structure, not the 2026 statutory figures (see report).
"""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_module_templates


def post_init_hook(env):
    # certify THIS module's own templates (discovered via ir.model.data) —
    # immune to the copy-a-pack-and-forget-to-edit-the-xmlid mistake
    certify_module_templates(env, __package__.rsplit('.', 1)[-1])
