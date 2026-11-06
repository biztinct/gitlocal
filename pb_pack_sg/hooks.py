# -*- coding: utf-8 -*-
"""F113 — pb_pack_sg install-time certification (D113.3).

Runs the Singapore Standard template's sample-test suite through the validated
engine after the pack's data loads; a failing test blocks the install. NOTE the
template ships state='draft': the harness proving the tests reproduce is
necessary but NOT sufficient for certification — the senior-band CPF splits and
SHG automation remain VERIFY items pending a country reviewer's sign-off.
"""
from odoo.addons.pb_hr_payroll_formula.hooks import certify_module_templates


def post_init_hook(env):
    # certify THIS module's own templates (discovered via ir.model.data) —
    # immune to the copy-a-pack-and-forget-to-edit-the-xmlid mistake
    certify_module_templates(env, __package__.rsplit('.', 1)[-1])
