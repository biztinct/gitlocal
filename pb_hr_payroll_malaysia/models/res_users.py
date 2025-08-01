# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResUsersMalaysia(models.Model):
    _inherit = 'res.users'

    malaysia_payroll_access = fields.Boolean('Malaysia Payroll Access', default=False)
    malaysia_epf_manager = fields.Boolean('Malaysia EPF Manager', default=False)

    @api.model
    def has_malaysia_access(self):
        """Check if user has Malaysia payroll access"""
        return self.env.user.has_group('pb_hr_payroll_base.group_payroll_malaysia') or \
               self.env.user.has_group('pb_hr_payroll_base.group_payroll_base_manager')