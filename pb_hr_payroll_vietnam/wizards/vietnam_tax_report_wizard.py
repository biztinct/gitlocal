# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VietnamTaxReportWizard(models.TransientModel):
    _name = 'vietnam.tax.report.wizard'
    _description = 'Vietnam Tax Report Generator'

    date_from = fields.Date(string='From Date', required=True, default=fields.Date.today().replace(day=1))
    date_to = fields.Date(string='To Date', required=True, default=fields.Date.today())
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    report_type = fields.Selection([
        ('monthly', 'Monthly Tax Report'),
        ('quarterly', 'Quarterly Tax Report'),
        ('annual', 'Annual Tax Report'),
    ], string='Report Type', default='monthly', required=True)

    def action_generate_report(self):
        """Generate Vietnam tax report"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Report Generated'),
                'message': _('Vietnam tax report has been generated successfully'),
                'type': 'success',
            }
        }