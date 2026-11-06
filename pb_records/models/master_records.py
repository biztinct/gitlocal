"""Master-record maintenance without a payroll configuration or mapping."""
from odoo import api, models, _

from odoo.addons.pb_hr_payroll_formula.models.application_domain_sources import (
    EMPLOYEE_FIELDS, CONTRACT_FIELDS)


class MasterRecords(models.AbstractModel):
    _inherit = 'pb.records.desk'

    @api.model
    def _master_fields(self):
        # Deliberate domain catalogue, never every field on hr.employee.
        return {
            'hr.employee': tuple(dict.fromkeys(EMPLOYEE_FIELDS + (
                'full_name_vn', 'location', 'mobile_phone', 'parent_id', 'coach_id', 'work_location_id',
                'resource_calendar_id'))),
            'hr.contract': tuple(dict.fromkeys(CONTRACT_FIELDS + (
                'resource_calendar_id', 'type_id', 'department_id', 'shuipart'))),
        }

    @api.model
    def get_schemes(self):
        result = super().get_schemes()
        result['schemes'] = [{
            'id': 0, 'name': _('Master records'), 'mapped_count': len(self._cards(0)),
            'is_default': True,
        }] + [dict(row, is_default=False) for row in result['schemes'] if row['id']]
        result['default_id'] = 0
        return result

    @api.model
    def _mappings(self, config_id):
        if config_id:
            return super()._mappings(config_id)
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        mappings = Mapping.browse()
        for model, names in self._master_fields().items():
            for name in names:
                field = self.env[model]._fields.get(name)
                if not field or (field.groups and not any(
                        self.env.user.has_group(g) for g in field.groups.split(','))):
                    continue
                metadata = self.env['ir.model.fields'].sudo()._get(model, name)
                if metadata:
                    mappings |= Mapping.new({
                        'destination_type': 'field',
                        'target_model_id': self.env['ir.model']._get(model).id,
                        'target_field_id': metadata.id,
                    })
        for role in ('acc_number', 'bank_name', 'bank_bic', 'acc_holder_name'):
            mappings |= Mapping.new({'destination_type': 'bank_account', 'bank_role': role})
        return mappings

    @api.model
    def _component_rules(self, config_id):
        return super()._component_rules(config_id) if config_id else self.env['hr.formula.rule']

    @api.model
    def _probe(self, config_id):
        if config_id:
            return super()._probe(config_id)
        return self.env['hr.payroll.import.batch'].sudo().new({})

    @api.model
    def _cards(self, config_id):
        cards = super()._cards(config_id)
        if config_id:
            return cards
        # Existing compensation records are discoverable even after the
        # payroll rule that originally populated them has been retired.
        lines = self.env['hr.contract.advantage'].sudo().search([
            ('contract_id.company_id', 'in', self.env.companies.ids)])
        for template in lines.mapped('advantage_template_id').sorted('id'):
            code = (template.code or '').strip()
            fid = 'c:' + code
            if not code or fid in cards:
                continue
            text = template.value_type == 'text'
            cards[fid] = {
                'id': fid, 'group': 'component', 'label': template.name,
                'sub': _('Saved contract component'), 'ttype': 'text_component' if text else 'amount',
                'selection': [], 'm2o': None, 'hint': None, 'component': None,
                'editable': True, 'model': 'hr.contract', 'code': code,
                '_template': template,
            }
        return cards
