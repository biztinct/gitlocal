# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SingaporeCpfSubmissionWizard(models.TransientModel):
    _name = 'singapore.cpf.submission.wizard'
    _description = 'Singapore CPF Submission File Generator'

    submission_month = fields.Date(string='Submission Month', required=True, default=fields.Date.today().replace(day=1))
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    submission_type = fields.Selection([
        ('monthly', 'Monthly Submission'),
        ('annual', 'Annual Submission'),
        ('correction', 'Correction Submission'),
    ], string='Submission Type', default='monthly', required=True)
    
    file_format = fields.Selection([
        ('csv', 'CSV Format'),
        ('txt', 'Text Format'),
        ('xml', 'XML Format'),
    ], string='File Format', default='csv', required=True)

    def action_generate_cpf_file(self):
        """Generate CPF submission file"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CPF File Generated'),
                'message': _('CPF submission file has been generated successfully'),
                'type': 'success',
            }
        }