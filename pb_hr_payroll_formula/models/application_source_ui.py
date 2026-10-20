from odoo import fields, models, _


class ApplicationSourceSettings(models.Model):
    _inherit = 'hr.formula.config'

    application_input_rule_ids = fields.One2many(
        'hr.formula.rule', 'config_id', domain=[('column_type', '=', 'input')],
        string='Application input mappings')

    def application_source_options(self):
        self.ensure_one()
        self._application_require_access()
        return [dict(v, key=k) for k, v in self._application_source_catalogue().items()]

    def action_application_source_settings(self):
        self.ensure_one()
        self._application_require_access()
        return {'type': 'ir.actions.act_window', 'name': _('Application payroll · %s') % self.name,
                'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'views': [(self.env.ref('pb_hr_payroll_formula.view_application_source_settings').id, 'form')],
                'target': 'current'}
