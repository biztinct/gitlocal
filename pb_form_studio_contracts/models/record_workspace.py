"""The complete premium contract form uses the drawer's approval path.

Ordinary native fields keep their native write. Terms and component commands
are translated into the existing facade, including its access/approval checks.
No proposal is approved by this adapter and no new approval route is created.
"""
from odoo import api, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.pb_form_studio.models.native_section import project_section_form
from odoo.addons.pb_contracts.models.contract_approval import MONEY_TERMS


AGREEMENT_GROUPS = (
    ('Agreement', ('name', 'employee_id', 'contract_type_id', 'structure_type_id', 'kanban_state')),
    ('Signed terms', ('pb_trial_date_start', 'pb_signed_date', 'pb_salary_basis', 'pb_payroll_contract_type', 'pb_payroll_nationality_status')),
    ('How pay is worked out', ('pb_vn_hours_per_day', 'pb_vn_pay_grade', 'pb_vn_annual_days', 'pb_vn_variable_bonus')),
    ('Worked out from dates', ('pb_vn_contract_months', 'pb_vn_service_days')),
    ('Tax exemption evidence', ('pb_vn_qual_ot_weekday', 'pb_vn_qual_ot_weekend', 'pb_vn_qual_ot_holiday', 'pb_vn_qual_night', 'pb_vn_qual_transport', 'pb_vn_qual_leave_encash', 'pb_vn_qual_other_exempt')),
    ('Notes', ('notes',)),
)


class ContractWorkspace(models.Model):
    _inherit = 'hr.contract'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type == 'form' and options.get('pb_workspace_section') == 'agreement':
            result = dict(result)
            result['arch'] = project_section_form(result['arch'],
                [(self.env._(title), names) for title, names in AGREEMENT_GROUPS],
                {name: field.get('domain', '') for name, field in self.fields_get(attributes=['domain']).items()})
        return result

    def _workspace_components(self, commands):
        result = {'edits': {}, 'adds': [], 'removes': []}
        for command in commands:
            op, row_id, payload = (list(command) + [False, False])[:3]
            if op == 0:
                extra = set(payload) - {'advantage_template_id', 'amount', 'text_value', 'contract_id'}
                if extra:
                    raise ValidationError(_('Use Components to change component definitions.'))
                result['adds'].append({'template_id': payload.get('advantage_template_id'),
                                       **{k: v for k, v in payload.items() if k in ('amount', 'text_value')}})
            elif op == 1:
                if set(payload) - {'amount', 'text_value'}:
                    raise ValidationError(_('Use Components to replace a component.'))
                result['edits'][str(row_id)] = payload
            elif op in (2, 3):
                result['removes'].append(row_id)
            elif op not in (4,):
                raise ValidationError(_('Use Components to replace the component list.'))
            else:
                # Linking another contract's component is never a shortcut.
                if row_id not in self.advantages_ids.ids:
                    raise AccessError(_('That component does not belong to this contract.'))
        return result

    def web_save(self, vals, specification, next_id=None):
        if not self or not self.env.context.get('pb_premium_record'):
            return super().web_save(vals, specification, next_id)
        self.ensure_one()
        self.check_access('write')
        for key in vals:
            field = self._fields.get(key)
            if not field or not self._has_field_access(field, 'write'):
                raise AccessError(_('You cannot change this field: %s', key))
        facade = self.env['pb.contracts']
        facade._cd_require_read()
        if not facade._cd_may_write():
            raise AccessError(_('Only an HR manager can change this contract.'))
        offered = facade._cd_writable_map(self, facade._cd_symbol(self), True, facade._cd_unmask_wage())
        values = dict(vals)
        terms = {k: values.pop(k) for k in list(values) if k in offered}
        protected = [k for k in values if k in MONEY_TERMS or k.startswith('x_pbfs_')]
        if protected:
            raise ValidationError(_('These fields cannot be changed on this contract: %s', ', '.join(protected)))
        components = self._workspace_components(values.pop('advantages_ids', []))
        if terms or any(components.values()):
            result = facade.save_contract_360(self.id, terms, components)
            if not result.get('ok') or result.get('refusals'):
                reasons = [r['why'] for r in result.get('refusals', [])]
                raise ValidationError('\n'.join(reasons) or result.get('msg') or _('The change could not be saved.'))
            if result.get('pending'):
                self.env.user._bus_send('simple_notification', {
                    'title': _('Contract change awaiting approval'),
                    'message': result.get('msg') or _('Current terms remain in effect until approval.'),
                    'sticky': True, 'type': 'info',
                })
        return super().web_save(values, specification, next_id)


class ContractWorkspaceTerms(models.AbstractModel):
    _inherit = 'pb.contracts'

    @api.model
    def _cd_writable_map(self, contract, symbol, can_write, unmask):
        result = super()._cd_writable_map(contract, symbol, can_write, unmask)
        # These native fields also move money and must travel through the
        # same proposal/apply path, including when the approver applies them.
        for name, kind in [('structure_type_id', 'm2o'), ('state', 'select')]:
            field = contract._fields.get(name)
            if field and contract._has_field_access(field, 'read'):
                entry = self._cd_field_entry(contract, field, name, field.string,
                                             kind, False, symbol, can_write, unmask)
                if entry:
                    result[name] = entry
        return result
