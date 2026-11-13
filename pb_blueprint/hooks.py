# -*- coding: utf-8 -*-
"""Prove the starter on every install, exactly as a country pack does.

`pb_pack_vn` blocks its own install when the Vietnam Standard starter cannot
reproduce its certification numbers through the real engine. The guided setup
ships a starter of its own — Vietnam · Complete — and it earns the same gate:
if the five people in its test suite stop coming out at the numbers they were
signed off at, the module does not install and nobody finds out on payday.

The helper is the engine's own (`certify_module_templates`), discovered through
`ir.model.data`, so this file cannot certify somebody else's template by
accident.
"""
import logging

from odoo.addons.pb_hr_payroll_formula.hooks import certify_module_templates

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    certify_module_templates(env, __package__.rsplit('.', 1)[-1])
