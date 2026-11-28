# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ETP E3 D3 — "Employees enter project time on their self-service pages", per
company. An `ir.config_parameter` (`pb_me_project_time.enabled.<company>`,
'1' / '0', unset = on), read and written here; never a column on res.company
(clone of pb_ess_workforce's clock switch, TIERS T3b D3)."""

from odoo import api, fields, models

from .project_time import PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_me_project_time_enabled = fields.Boolean(
        string='Employees enter project time on their self-service pages',
        help='When off, the Project time page shows that it is switched off, '
             'and its home tile and card are hidden. Time entered here before '
             'stays where it is.')

    @api.model
    def get_values(self):
        res = super().get_values()
        res['pb_me_project_time_enabled'] = self.env['pb.me.project.time'].enabled(
            self.env.company)
        return res

    def set_values(self):
        super().set_values()
        for settings in self:
            company = settings.company_id or self.env.company
            self.env['ir.config_parameter'].sudo().set_param(
                PARAM % company.id,
                '1' if settings.pb_me_project_time_enabled else '0')
