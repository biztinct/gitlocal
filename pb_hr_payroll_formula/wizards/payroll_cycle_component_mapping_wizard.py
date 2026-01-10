# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayrollCycleComponentMappingWizard(models.TransientModel):
    _name = 'hr.payroll.cycle.component.mapping.wizard'
    _description = 'Mid-Cycle to End-Cycle Mapping Wizard'

    mid_cycle_config_id = fields.Many2one(
        'hr.formula.config',
        string='Mid-Cycle Configuration',
        required=True,
        domain="[('cycle_type', '=', 'mid_cycle')]"
    )
    end_cycle_config_id = fields.Many2one(
        'hr.formula.config',
        string='End-Cycle Configuration',
        required=True,
        domain="[('cycle_type', '=', 'end_cycle')]"
    )

    def action_open_mappings(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_cycle_component_mapping').read()[0]
        context = dict(self.env.context or {})
        context['default_mid_cycle_config_id'] = self.mid_cycle_config_id.id
        context['default_end_cycle_config_id'] = self.end_cycle_config_id.id
        context['search_default_mid_cycle_config_id'] = self.mid_cycle_config_id.id
        context['search_default_end_cycle_config_id'] = self.end_cycle_config_id.id
        action['context'] = context
        return action
