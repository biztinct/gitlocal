# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


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

    def action_generate_report(self, *args, **kwargs):
        """WDGAP S2-A (S2F-4): RETIRED. This door used to say a file was
        made (or data imported) and made none. It now says so and makes
        no claim. (Vietnam tax report wizard)"""
        raise UserError(_("This tax report is not available here, so nothing was made. The monthly and quarterly tax declaration is prepared on Compliance › Filings."))

