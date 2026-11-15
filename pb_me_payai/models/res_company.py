# -*- coding: utf-8 -*-
"""The company switch and the daily limits (owner ruling E5).

OFF BY DEFAULT on every company of every database: installing this module
asks nobody anything and shows nobody anything until HR switches it on.
Company fields, as PayAI's other switches are (`pb_payai_actions`), so a group
with several companies can have it on in one and off in another.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pb_policy_ai_on = fields.Boolean(
        string='Employees may ask PayAI about company policies',
        default=False,
        help='PayAI answers only from the policy files HR publishes, never '
             'with personal figures. Every question uses this company\'s AI '
             'account.')
    pb_policy_ai_person_day = fields.Integer(
        string='Questions per person per day', default=10,
        help='Each question PayAI answers costs a little on the AI account.')
    pb_policy_ai_company_day = fields.Integer(
        string='Questions per company per day', default=200)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_policy_ai_on = fields.Boolean(
        related='company_id.pb_policy_ai_on', readonly=False)
    pb_policy_ai_person_day = fields.Integer(
        related='company_id.pb_policy_ai_person_day', readonly=False)
    pb_policy_ai_company_day = fields.Integer(
        related='company_id.pb_policy_ai_company_day', readonly=False)
