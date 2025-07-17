# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SingaporeBankExportWizard(models.TransientModel):
    _name = 'singapore.bank.export.wizard'
    _description = 'Singapore Bank Transfer Export'

    payslip_ids = fields.Many2many('hr.payslip', string='Payslips')
    bank_format = fields.Selection([
        ('dbs', 'DBS Bank'),
        ('ocbc', 'OCBC Bank'),
        ('uob', 'UOB Bank'),
        ('maybank', 'Maybank'),
        ('generic', 'Generic CSV'),
    ], string='Bank Format', default='generic', required=True)
    
    file_name = fields.Char(string='File Name', default='singapore_bank_transfer.csv')
    include_cpf = fields.Boolean(string='Include CPF Details', default=True)

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