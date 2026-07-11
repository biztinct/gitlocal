# -*- coding: utf-8 -*-
"""F113 — pb_pack_vn install-time certification (D113.3).

Runs the Vietnam Standard template's sample-test suite through the validated
engine after the pack's data loads. A failing test raises and blocks the
install — a wrong statutory value or a broken formula can never ship silently.
"""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_module_templates


def post_init_hook(env):
    # certify THIS module's own templates (discovered via ir.model.data) —
    # immune to the copy-a-pack-and-forget-to-edit-the-xmlid mistake
    certify_module_templates(env, __package__.rsplit('.', 1)[-1])
