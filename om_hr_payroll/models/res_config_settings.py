# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']

    module_om_hr_payroll_account = fields.Boolean(string='Payroll Accounting')
    payroll_from_spreadsheet = fields.Boolean(string="Payroll From Spreadsheet", 
                                                help="Enable computation of payroll from spreadsheet")
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        # This will store the value in the config.parameters table
        self.env['ir.config_parameter'].set_param('payroll_from_spreadsheet', self.payroll_from_spreadsheet)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        # This will fetch the value from the config.parameters table
        res.update(
            payroll_from_spreadsheet=self.env['ir.config_parameter'].sudo().get_param('payroll_from_spreadsheet'),
        )
        return res