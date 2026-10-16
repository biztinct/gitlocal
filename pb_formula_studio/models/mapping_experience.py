"""Connection desk: projections of existing source contracts, never a resolver."""
import hashlib
import json

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError


class MappingExperience(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    def _desk_config(self, config_id, write=False):
        config = self.env['hr.formula.config'].browse(int(config_id or 0)).exists()
        if not config:
            raise UserError(_('Choose a payroll scheme first.'))
        config.check_access('write' if write else 'read')
        if write and not self._desk_can_edit():
            raise AccessError(_('You do not have permission to change this scheme.'))
        return config

    def _desk_can_edit(self):
        return self.env.user.has_group('base.group_system') or self.env.user.has_group(
            'pb_hr_payroll_formula.group_formula_manager')

    @api.model
    def _declared_sources(self, rule, record_dests, wire_dests=None):
        # Keep the shared display contract (including `period`), but honour the
        # same enabled lanes/order as the resolver. No new ranking vocabulary.
        sources = super()._declared_sources(rule, record_dests, wire_dests)
        if rule.column_type != 'input':
            return sources
        rank = rule._config_kind_rank()
        sources = [s for s in sources if ('pay_run' if s['kind'] == 'period' else s['kind']) in rank]
        sources.sort(key=lambda s: rank.index('pay_run' if s['kind'] == 'period' else s['kind']))
        return sources or [{'kind': 'none', 'key': '', 'wirable': True}]

    def _desk_priority(self, config):
        order = [v for v in (config.source_priority or '').replace(' ', '').split(',') if v in ('api', 'excel', 'records')]
        order = list(dict.fromkeys(order + ['api', 'excel', 'records']))
        flags = {k: bool(config['source_%s_enabled' % k]) for k in order}
        records, wires = self._source_record_dests(config), self._source_wire_dests(config)
        revision = [(r.id, str(r.write_date),
                     [(s.id, s.kind, s.key, str(s.write_date)) for s in r.source_ids.sorted('id')])
                    for r in config.rule_ids.sorted('id')]
        record_revision = [(rid, value['kind'], value['key']) for rid, value in sorted(records.items())]
        wire_revision = [(rid, value['kind'], value['key']) for rid, value in sorted(wires.items())]
        token = hashlib.sha256(json.dumps([order, flags, str(config.write_date), revision,
                                           record_revision, wire_revision], sort_keys=True).encode()).hexdigest()
        return {'order': order, 'enabled': flags, 'token': token}

    @api.model
    def mapping_workspace_data(self, config_id):
        if not config_id:
            return {'ok': False, 'reason': 'no_config'}
        config = self._desk_config(config_id)
        data = self.get_studio_data(config.id)
        records, wires = self._source_record_dests(config), self._source_wire_dests(config)
        rules = {r.id: r for r in config.rule_ids}
        for row in data['components']:
            row['sources'] = self._declared_sources(rules[row['id']], records, wires)
            row['storage'] = records.get(row['id']) or None
        data.update(ok=True, can_edit=self._desk_can_edit(), priority=self._desk_priority(config),
                    kinds=config._value_kind_options(),
                    pay_roles=[{'key': k or '', 'label': label} for k, label in
                               self.env['hr.formula.rule']._fields['net_role'].selection])
        return data

    def _desk_check_order(self, order):
        if not isinstance(order, list) or len(order) != 3 or set(order) != {'api', 'excel', 'records'}:
            raise UserError(_('Keep each source lane exactly once.'))
        return order

    @api.model
    def mapping_priority_preview(self, config_id, order):
        config = self._desk_config(config_id)
        order = self._desk_check_order(order)
        enabled = self._desk_priority(config)['enabled']
        lanes = {'api': ('feed', 'rule'), 'excel': ('excel',),
                 'records': ('employee_field', 'contract_field', 'bank_account', 'contract_component')}
        rank = [kind for lane in order if enabled[lane] for kind in lanes[lane]] + ['period']
        records, wires = self._source_record_dests(config), self._source_wire_dests(config)
        affected = []
        for rule in config.rule_ids.filtered(lambda r: r.column_type == 'input'):
            before = self._declared_sources(rule, records, wires)
            after = sorted(before, key=lambda s: rank.index(s['kind']) if s['kind'] in rank else 999)
            if [(s['kind'], s['key']) for s in before] != [(s['kind'], s['key']) for s in after]:
                affected.append({'id': rule.id, 'name': rule.name, 'code': rule.code,
                                 'before': before, 'after': after})
        return {'ok': True, 'affected': affected, 'token': self._desk_priority(config)['token']}

    @api.model
    def mapping_priority_save(self, config_id, order, token):
        config = self._desk_config(config_id, write=True)
        order = self._desk_check_order(order)
        # Serialize concurrent changes before comparing the review token.
        self.env.cr.execute('SELECT id FROM hr_formula_config WHERE id=%s FOR UPDATE', [config.id])
        config.invalidate_recordset(['source_priority', 'source_api_enabled', 'source_excel_enabled',
                                     'source_records_enabled', 'write_date'])
        if token != self._desk_priority(config)['token']:
            raise UserError(_('This scheme changed while you were reviewing it. Reload and review the order again.'))
        config.write({'source_priority': ','.join(order)})
        return {'ok': True}

    @api.model
    def mapping_component_setup(self, config_id, rule_id, kind, pay_role, storage=None):
        config = self._desk_config(config_id, write=True)
        rule = config.rule_ids.filtered(lambda r: r.id == int(rule_id))
        if not rule:
            raise UserError(_('This component is not on this scheme.'))
        with self.env.cr.savepoint():
            if storage:
                if storage not in ('text', 'amount'):
                    raise UserError(_('Choose text or amount storage.'))
                if (storage == 'text') != (kind in ('text', 'identifier', 'date', 'boolean')):
                    raise UserError(_('Choose a value type that matches the contract storage.'))
                result = self.employee_mapping_make_component(rule.id, storage)
                if not result.get('ok'):
                    raise UserError(result.get('msg') or _('The contract component was not changed.'))
            config.set_component_setup({rule.code: {'kind': kind, 'pay_role': pay_role}})
        return {'ok': True}

    @api.model
    def mapping_component_create(self, config_id, name, kind='money', storage=None):
        config = self._desk_config(config_id, write=True)
        with self.env.cr.savepoint():
            result = self.add_component(config.id, {'name': str(name or '').strip(),
                         'column_type': 'input', 'value_kind': kind})
            if not result.get('ok'):
                raise UserError(_('The component was not created.'))
            self.mapping_component_setup(config.id, result['rule_id'], kind, '', storage)
        return result

    @api.model
    def mapping_rule_targets(self, config_id):
        config = self._desk_config(config_id)
        mapping = self.env['hr.integration.field.mapping']
        if not all(mapping.has_access(op) for op in ('create', 'write', 'unlink')):
            return []
        records, wires = self._source_record_dests(config), self._source_wire_dests(config)
        return [{'id': r.id, 'name': r.name, 'code': r.code,
                 'sources': [{**s, 'kind_label': self._source_label(s['kind'])}
                             for s in self._declared_sources(r, records, wires)]}
                for r in config.rule_ids if r.column_type == 'input'
                and not r.is_text_component and r.value_kind not in ('text', 'identifier', 'date', 'boolean')]

    @api.model
    def mapping_rule_save(self, config_id, connector_id, spec, rule_id=None, target_id=None):
        config = self._desk_config(config_id, write=True)
        if target_id:
            mapping = self.env['hr.integration.field.mapping']
            for op in ('create', 'write', 'unlink'):
                mapping.check_access(op)
        if target_id and int(target_id) not in [r['id'] for r in self.mapping_rule_targets(config.id)]:
            raise UserError(_('Choose a numeric input on this scheme.'))
        with self.env.cr.savepoint():
            result = self.env['pb.integrations'].rule_save(connector_id, spec, rule_id)
            if not result.get('ok'):
                raise UserError(result.get('msg') or _('The transformation was not saved.'))
            if target_id:
                wire = self.api_mapping_create(config.id, connector_id, result['rule']['output_key'],
                                               int(target_id), resolve='keep')
                if not wire.get('ok'):
                    raise UserError(wire.get('msg') or _('The rule could not be connected. Nothing was saved.'))
        return result
