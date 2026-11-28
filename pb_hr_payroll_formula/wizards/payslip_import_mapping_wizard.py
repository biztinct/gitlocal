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
    copy_from_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Copy From'
    )

    def action_open_mappings(self):
        self.ensure_one()
        if self.copy_from_structure_id:
            self._copy_mapping_fields(self.copy_from_structure_id)
        action = self.env['ir.actions.actions'].sudo()._for_xml_id(
            'pb_hr_payroll_formula.action_payslip_import_mapping'
        )
        context = dict(self.env.context or {})
        context['default_salary_structure_id'] = self.salary_structure_id.id
        context['search_default_salary_structure_id'] = self.salary_structure_id.id
        action['context'] = context
        return action

    def _copy_mapping_fields(self, source_structure):
        self.ensure_one()
        if not source_structure or source_structure == self.salary_structure_id:
            return
        mapping_model = self.env['hr.payslip.import.mapping']
        existing = mapping_model.search([
            ('salary_structure_id', '=', self.salary_structure_id.id),
        ])
        # COLROLES P3 — the identity of a mapping is now its DESTINATION, not just a
        # model/field pair: two bank rows both have (False, False) there and would
        # have collapsed into one. The bank role joins the key so a structure can be
        # copied with its account number, bank name and holder name intact.
        def destination_key(mapping):
            return (mapping.destination_type,
                    mapping.target_model_id.id,
                    mapping.target_field_id.id,
                    mapping.bank_role or False)

        existing_keys = {destination_key(mapping) for mapping in existing}
        source_mappings = mapping_model.search([
            ('salary_structure_id', '=', source_structure.id),
        ])
        vals_list = []
        for mapping in source_mappings:
            key = destination_key(mapping)
            if key in existing_keys:
                continue
            vals_list.append({
                'salary_structure_id': self.salary_structure_id.id,
                'destination_type': mapping.destination_type,
                'target_model_id': mapping.target_model_id.id,
                'target_field_id': mapping.target_field_id.id,
                'bank_role': mapping.bank_role,
                'component_id': False,
            })
            existing_keys.add(key)
        if vals_list:
            mapping_model.create(vals_list)
