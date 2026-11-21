# -*- coding: utf-8 -*-
"""The company's choice (owner ruling E6): approved claims are paid back by
finance (the default, today's behaviour) or in the next pay run."""
from odoo import fields, models

from .common import PAY_ROUTES


class ResCompanyClaimsPay(models.Model):
    _inherit = 'res.company'

    pb_claims_paid_by = fields.Selection(
        PAY_ROUTES, string='Approved claims are paid', default='finance',
        required=True,
        help='By finance: finance pays approved claims back as today. In the '
             'next pay run: each approved claim is a separate line on the '
             'person\'s next regular payslip, with no tax.')
    pb_claims_paid_by_changed_by = fields.Many2one(
        'res.users', string='Changed by', readonly=True, copy=False)
    pb_claims_paid_by_changed_on = fields.Datetime(
        string='Changed on', readonly=True, copy=False)
