# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipConfigWizard(models.TransientModel):
    _name = 'hr.payslip.config.wizard'
    _description = 'Payslip Configuration Wizard'

    salary_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        required=True
    )

    def action_open_config(self):
        self.ensure_one()
        action = self.env['ir.actions.actions'].sudo()._for_xml_id(
            'pb_hr_payroll_formula.action_payslip_config'
        )
        context = dict(self.env.context or {})
        context['default_salary_structure_id'] = self.salary_structure_id.id
        context['search_default_salary_structure_id'] = self.salary_structure_id.id
        action['context'] = context
        return action
