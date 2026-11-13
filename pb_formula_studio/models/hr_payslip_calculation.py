# -*- coding: utf-8 -*-
"""RD46 — the door from a payslip to "how was this worked out?".

WHY THE PAYSLIP AND NOT THE EMPLOYEE RECORD. "How was this calculated" is a
question about ONE PERSON IN ONE PERIOD, and a payslip is exactly that pair. An
employee record carries no period, so the same button there would have to open
by asking "which month?" — a question the payslip has already answered. The
employee's route to this screen is therefore through their payslip, which is
also where somebody looking at a number they doubt already is.

IT OPENS READ-ONLY. Arriving from a real payment means auditing, not authoring,
and the studio's own `canEdit` flag is what gets switched off — the same flag a
read-only Formula User already lands with, rather than a second locking
mechanism that would have to be kept in step with the first. This is a guard
against changing a live scheme by accident while explaining one person's pay; it
is not a permission boundary, and it does not pretend to be one. The permission
boundary is the ACL, which is unchanged.
"""
from odoo import _, models
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_show_calculation(self):
        """Open the Formula Engine on this payslip's numbers, read-only."""
        self.ensure_one()
        config = self.formula_config_id or self._find_formula_config()
        if not config:
            raise UserError(_(
                "This payslip was not worked out by a payroll scheme, so there "
                "are no formulas to show. It was computed with salary rules."))
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_formula_studio',
            'name': _("How %s's pay was worked out") % (
                self.employee_id.display_name or _('this employee')),
            'params': {
                'config_id': config.id,
                # The two signals the studio reads. `pbfs_preview_payslip_id`
                # loads the person; `pbfs_readonly` locks the formulas. They are
                # separate on purpose: the Live Preview picker sets the first
                # WITHOUT the second, because there the whole point is to try a
                # change against a real case.
                'pbfs_preview_payslip_id': self.id,
                'pbfs_readonly': True,
            },
        }
