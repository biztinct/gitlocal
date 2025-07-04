# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class CountrySelectorWizard(models.TransientModel):
    _name = 'country.selector.wizard'
    _description = 'Country Selector Wizard'
    
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Select Payroll Country', required=True, default='VN')
    
    def action_open_country_payroll(self):
        """Open country-specific payroll dashboard"""
        country_selector = self.env['payroll.country.selector'].create({
            'country': self.country
        })
        return country_selector.action_select_country()