# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PayrollSetupGuide(models.TransientModel):
    _name = 'payroll.setup.guide'
    _description = 'Payroll Setup Guide'
    
    # This is just a guide model, no fields needed
    # The view will show static content
    
    @api.model
    def default_get(self, fields_list):
        """Always return a record for the guide"""
        return {'id': 1}