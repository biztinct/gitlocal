# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Who picks up Ask HR questions, per company (D6: an `ir.config_parameter`,
never a column on an existing model)."""

from odoo import api, fields, models

from .ticket import OWNER_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_ask_hr_owner_id = fields.Many2one(
        'res.users', string='Who picks up Ask HR questions',
        domain=[('share', '=', False)],
        help='New questions are assigned to this person and appear on their '
             'to-do list. Leave empty to let the HR team pick them up from '
             'the queue.')

    @api.model
    def get_values(self):
        res = super().get_values()
        owner = self.env['pb.ask.hr.ticket']._pb_owner_for(self.env.company)
        res['pb_ask_hr_owner_id'] = owner.id or False
        return res

    def set_values(self):
        super().set_values()
        for settings in self:
            company = settings.company_id or self.env.company
            self.env['ir.config_parameter'].sudo().set_param(
                OWNER_PARAM % company.id,
                str(settings.pb_ask_hr_owner_id.id) if settings.pb_ask_hr_owner_id else '')
