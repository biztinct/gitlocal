# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_recompute_formula_lines_batch(self):
        total = 0
        for run in self:
            slips = run.slip_ids.filtered(lambda s: s.calculation_method == 'formula')
            if slips:
                slips.action_recompute_formula_lines()
                total += len(slips)
        if not total:
            raise UserError(_("No formula-based payslips found to recompute."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputed'),
                'message': _("Recomputed %s payslip(s).") % total,
                'type': 'success',
            }
        }
