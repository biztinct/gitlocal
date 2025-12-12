# -*- coding: utf-8 -*-

from odoo import models


class PayrollDashboardVietnam(models.Model):
    _inherit = 'payroll.dashboard'

    def action_open_govt_reports(self):
        """Open government reports selection wizard"""
        return {
            'name': 'Select Government Report',
            'type': 'ir.actions.act_window',
            'res_model': 'pb.govt.report.selector',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_country': 'vietnam'},
        }
