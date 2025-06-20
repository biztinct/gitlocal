# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    
    is_thr = fields.Boolean(string='Is THR Payslip', default=False, 
                           help='Check if this is a THR (Religious Holiday Allowance) payslip')
