# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_download_full_and_final(self):
        self.ensure_one()
        settlement = self.env['hr.full.final.settlement'].search(
            [('employee_id', '=', self.id)],
            order='settlement_date desc',
            limit=1,
        )
        if not settlement:
            raise UserError(_("No full and final settlement found for this employee."))
        return self.env.ref('pb_hr_fullandfinal.action_report_full_and_final').report_action(settlement)
