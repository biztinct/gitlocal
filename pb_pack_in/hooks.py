# -*- coding: utf-8 -*-
"""F113 — pb_pack_in install-time certification (D113.3). Ships draft."""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_module_templates


def post_init_hook(env):
    # certify THIS module's own templates (discovered via ir.model.data) —
    # immune to the copy-a-pack-and-forget-to-edit-the-xmlid mistake
    certify_module_templates(env, __package__.rsplit('.', 1)[-1])
