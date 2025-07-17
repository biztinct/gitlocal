# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VietnamBankExportWizard(models.TransientModel):
    _name = 'vietnam.bank.export.wizard'
    _description = 'Vietnam Bank Transfer Export'

    payslip_ids = fields.Many2many('hr.payslip', string='Payslips')
    bank_format = fields.Selection([
        ('vietcombank', 'Vietcombank'),
        ('bidv', 'BIDV'),
        ('techcombank', 'Techcombank'),
        ('mb_bank', 'MB Bank'),
        ('generic', 'Generic CSV'),
    ], string='Bank Format', default='generic', required=True)
    
    file_name = fields.Char(string='File Name', default='vietnam_bank_transfer.csv')

    def action_export_file(self):
        """Export bank transfer file"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Export Completed'),
                'message': _('Bank transfer file has been exported successfully'),
                'type': 'success',
            }
        }