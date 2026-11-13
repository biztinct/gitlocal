# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b D3 — "Employees can clock in from their self-service pages", per
company. An `ir.config_parameter` (`pb_ess_workforce.portal_clock.<company>`,
'1' / '0', unset = on), read and written here; never a column on res.company."""

from odoo import api, fields, models

from .ess_workforce import CLOCK_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_ess_portal_clock = fields.Boolean(
        string='Employees can clock in from their self-service pages',
        help='When off, the Clock page and the home button are hidden; '
             'devices and the field app still work.')

    @api.model
    def get_values(self):
        res = super().get_values()
        res['pb_ess_portal_clock'] = self.env['pb.ess.workforce'].portal_clock_enabled(
            self.env.company)
        return res

    def set_values(self):
        super().set_values()
        for settings in self:
            company = settings.company_id or self.env.company
            self.env['ir.config_parameter'].sudo().set_param(
                CLOCK_PARAM % company.id,
                '1' if settings.pb_ess_portal_clock else '0')
