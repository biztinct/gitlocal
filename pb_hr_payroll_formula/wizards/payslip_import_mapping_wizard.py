# -*- coding: utf-8 -*-

from odoo import fields, models


class HrPayslipImportMappingWizard(models.TransientModel):
    _name = 'hr.payslip.import.mapping.wizard'
    _description = 'Payslip Import Mapping Wizard'

    salary_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        required=True
    )

    def action_open_mappings(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payslip_import_mapping').read()[0]
        context = dict(self.env.context or {})
        context['default_salary_structure_id'] = self.salary_structure_id.id
        context['search_default_salary_structure_id'] = self.salary_structure_id.id
        action['context'] = context
        return action
