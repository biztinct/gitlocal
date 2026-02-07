# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrFormulaConfigVietnam(models.Model):
    """
    Extends hr.formula.config with Vietnam-specific insurance and tax links
    """
    _inherit = ['hr.formula.config']

    # ==========================================
    # VIETNAM INSURANCE CONFIGURATION
    # ==========================================
    vn_insurance_policy_id = fields.Many2one(
        'vietnam.insurance.policy',
        string='Insurance Policy',
        domain="[('company_id', '=', company_id)]",
        help="Link to Vietnam insurance policy for this salary configuration"
    )
    vn_copy_insurance_from_company = fields.Boolean(
        string='Use Company Insurance Policy',
        default=True,
        help="Use the company's default insurance policy instead of defining one for this config"
    )
    
    # ==========================================
    # VIETNAM TAX CONFIGURATION
    # ==========================================
    vn_tax_table_id = fields.Many2one(
        'vietnam.tax.table',
        string='Tax Table',
        domain="[('company_id', '=', company_id)]",
        help="Link to Vietnam tax table for this salary configuration"
    )
    vn_copy_tax_from_company = fields.Boolean(
        string='Use Company Tax Table',
        default=True,
        help="Use the company's default tax table instead of defining one for this config"
    )
