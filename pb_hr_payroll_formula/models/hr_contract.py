# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrContract(models.Model):
    _inherit = 'hr.contract'

    advantage_change_count = fields.Integer(
        string='Component Changes',
        compute='_compute_advantage_change_count',
    )

    def _compute_advantage_change_count(self):
        change_model = self.env['hr.contract.advantage.change']
        for contract in self:
            contract.advantage_change_count = change_model.search_count([
                ('contract_id', '=', contract.id),
            ])

    def action_view_advantage_changes(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_contract_component_changes').read()[0]
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {
            'default_contract_id': self.id,
            'default_employee_id': self.employee_id.id,
        }
        return action
