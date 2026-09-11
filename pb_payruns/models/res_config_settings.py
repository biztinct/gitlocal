# -*- coding: utf-8 -*-
"""The Officer-review tier, as a setting somebody can find.

The switch itself is one system parameter (`pb_payruns.officer_review`, read by
`hr.payslip.run._pb_officer_tier`). A parameter nobody can see is a door that
only the people who built it know about, so it gets a real checkbox here as
well: the tier is a decision about how a company signs off its payroll, and that
is the owner's to make, not a support request.

Per DATABASE, not per company. Every tenant is its own database, and the
approval chain is drawn by a kanban's group_expand — which has no company to
read. Making it a company field would produce a board that is right for one
company and wrong for the next one on the same screen.
"""

from odoo import api, fields, models

from .hr_payslip_run import PB_OFFICER_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_payrun_officer_review = fields.Boolean(
        string='Payroll Officer reviews pay runs',
        help="Keep the Payroll Officer sign-off between Draft and HR review. "
             "Switch it off and a submitted pay run goes straight to HR "
             "review, then Finance approval.")

    @api.model
    def get_values(self):
        values = super().get_values()
        values['pb_payrun_officer_review'] = (
            self.env['hr.payslip.run']._pb_officer_tier())
        return values

    def set_values(self):
        super().set_values()
        # Written as '1'/'0' rather than Python's 'True'/'False': the reader
        # treats '0' as off, and a stray 'False' string would read as ON.
        self.env['ir.config_parameter'].sudo().set_param(
            PB_OFFICER_PARAM, '1' if self.pb_payrun_officer_review else '0')
