# -*- coding: utf-8 -*-

from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_download_full_and_final(self):
        self.ensure_one()
        return self.env.ref('pb_hr_fullandfinal.action_report_full_and_final').report_action(self)
