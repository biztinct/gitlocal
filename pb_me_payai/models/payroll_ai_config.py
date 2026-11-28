# -*- coding: utf-8 -*-
"""A purpose of its own on the existing AI account settings.

A company may keep a separate AI account row for employee policy answers
(purpose "Policy answers for employees"). Without one, the company's own
PayAI account is used. NEVER another company's: `get_config_for_purpose`
falls back to any active row in the database (FACTS §6.2), which here would
spend one customer company's account on another's employees, so this module
has its own lookup (`pb.policy.answer._config`).
"""
from odoo import fields, models


class PayrollAIConfigPolicy(models.Model):
    _inherit = 'payroll.ai.config'

    purpose = fields.Selection(
        selection_add=[('policy_answers', 'Policy answers for employees')],
        ondelete={'policy_answers': 'set default'})
