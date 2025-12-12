# -*- coding: utf-8 -*-

from odoo import fields, models


class PbGovtReportSelector(models.TransientModel):
    """Wizard to select government report type with visual tiles"""
    _name = 'pb.govt.report.selector'
    _description = 'Government Report Selector'

    country = fields.Char(string='Country', default='vietnam')

    def action_select_report(self, report_type):
        """Open the government report wizard with pre-selected report type"""
        return {
            'name': 'Vietnam Government XLS Reports',
            'type': 'ir.actions.act_window',
            'res_model': 'pb.govt.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_report_type': report_type,
            },
        }

    def action_bhxh630(self):
        return self.action_select_report('bhxh630')

    def action_bhxhdstk01(self):
        return self.action_select_report('bhxhdstk01')

    def action_bangke_d01(self):
        return self.action_select_report('bangke_d01')

    def action_giam_ld(self):
        return self.action_select_report('giam_ld')

    def action_tang_ld(self):
        return self.action_select_report('tang_ld')
