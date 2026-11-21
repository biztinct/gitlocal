"""Readable, typed Studio contracts. Read endpoints never reclassify a scheme."""
import json
import math

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.addons.pb_hr_payroll_formula.models import formula_operand_context as operands
from odoo.addons.pb_hr_payroll_formula.models import value_kind_classifier as kinds
from odoo.addons.pb_hr_payroll_formula.models.formula_net_role import looks_like_a_quantity


class StudioExperience(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @api.model
    def get_studio_data(self, config_id=None):
        data = super().get_studio_data(config_id)
        if data.get('empty'):
            return data
        config = self._pick_config(data['config']['id'])
        rules = {r.id: r for r in config.rule_ids}
        for row in data['components']:
            rule = rules[row['id']]
            row['display_group'] = rule.component_type or (rule.category_id.name if rule.category_id else '')
            row['value_kind_source'] = rule.value_kind_source or 'auto'
            row['is_valid'] = row['is_valid'] and (rule.column_type != 'formula' or bool((rule.excel_formula or '').strip()))
        net = config._net_role_find_net_rule(config._net_role_rules())
        data['config']['net_code'] = net.code if net else False
        data['config']['outcomes'] = [
            {'id': r.id, 'code': r.code, 'col': r.column_letter, 'name': r.name,
             'role': r.net_role or '', 'kind': r.value_kind}
            for r in config._net_role_rules()
            if r.value_kind == 'money' and r.column_type == 'formula']
        return data

    def _payslip_comp(self, rule, values):
        data = super()._payslip_comp(rule, values)
        data.update(value_kind=rule.value_kind, is_text_component=rule.is_text_component)
        return data

    @api.model
    def replay_trace(self, config_id=None, sample_id=None):
        data = super().replay_trace(config_id, sample_id)
        if not data.get('ok'):
            return data
        config = self._pick_config(config_id)
        values = self._compute(config, data['sample_id']).get('values', {})
        rules = {r.column_letter: r for r in config.rule_ids}
        for key, value_key in (('seeded', 'value'), ('steps', 'result')):
            for row in data.get(key, []):
                rule = rules.get(row.get('col'))
                if rule:
                    row.update(value_kind=rule.value_kind, is_text_component=rule.is_text_component)
                    row[value_key] = values.get(rule.column_letter)
        return data

    @api.model
    def experience_review_types(self, config_id):
        config = self._pick_config(config_id)
        scheme = config._scheme_operand_contexts()
        samples = config._value_kind_samples()
        rows = []
        for r in config.rule_ids:
            if r.value_kind_source == 'user':
                continue
            kind, reason = kinds.classify_value_kind(
                code=r.code or '', name=r.name or '', column_role=r.column_role or 'payroll',
                net_role=r.net_role or '', column_type=r.column_type,
                contexts=config._rule_operand_contexts(r, scheme),
                quantity=bool(looks_like_a_quantity(r.name or '', r.code or '')),
                sample_values=samples.get(r.code) or [], appears_on_payslip=r.appears_on_payslip)
            evidence = samples.get(r.code) or []
            if kind == 'boolean' and not any(
                    isinstance(v, bool) or str(v).strip().lower() in
                    ('yes', 'no', 'true', 'false', 'có', 'không') for v in evidence):
                continue
            if kind != r.value_kind:
                rows.append({'code': r.code, 'name': r.name, 'current': r.value_kind,
                             'proposed': kind, 'reason': reason})
        return {'ok': True, 'rows': rows}

    @api.model
    def get_problems(self, config_id=None):
        data = super().get_problems(config_id)
        config = self._pick_config(config_id)
        if not config:
            return data
        numeric = set()
        for rule in config.rule_ids.filtered(lambda r: r.column_type == 'formula'):
            numeric.update(ref for ref, ctx in operands.operand_contexts(rule.excel_formula).items()
                           if operands.CTX_ARITH in ctx)
        rules = {r.id: r for r in config.rule_ids}
        def keep(p):
            if p['kind'] != 'refinformula':
                return True
            r = rules.get(p.get('rule_id'))
            # Equality and text lookup references are legitimate formula inputs.
            return bool(r and (r.is_text_component or r.value_kind in ('text', 'identifier', 'date', 'boolean'))
                        and ({(r.code or '').upper(), (r.column_letter or '').upper()} & numeric))
        data['problems'] = [p for p in data.get('problems', []) if keep(p)]
        for r in config.rule_ids.filtered(lambda r: r.column_type == 'formula' and not (r.excel_formula or '').strip()):
            data['problems'].append({'key': 'blankformula:%s' % r.id, 'kind': 'blankformula',
                'severity': 'error', 'title': _('Formula is empty'),
                'detail': _('Add a formula or change this component to an input.'),
                'rule_id': r.id, 'col': r.column_letter, 'code': r.code, 'note_id': False})
        data['counts'] = {key: sum(p['severity'] == key for p in data['problems'])
                          for key in ('error', 'warning', 'hint')}
        data['count'] = len(data['problems'])
        return data

    @api.model
    def add_component(self, config_id, vals=None):
        vals = vals or {}
        if not str(vals.get('name') or '').strip():
            raise UserError(_('Give the component a name before adding it.'))
        if vals.get('column_type', 'formula') == 'formula' and not str(vals.get('excel_formula') or '').strip():
            raise UserError(_('Enter a formula before adding this component.'))
        result = super().add_component(config_id, vals)
        if result.get('ok') and vals.get('value_kind'):
            self.env['hr.formula.rule'].browse(result['rule_id']).write({'value_kind': vals['value_kind']})
        return result

    @api.model
    def get_sample_detail(self, sample_id):
        data = super().get_sample_detail(sample_id)
        sample = self.env['hr.formula.sample.data'].browse(int(sample_id)).exists()
        if not sample:
            return data
        rules = {r.code: r for r in sample.config_id.rule_ids}
        for row in data['rows']:
            rule = rules.get(row['code'])
            if rule:
                row.update(value_kind=rule.value_kind, number_format=rule.number_format,
                           is_text_component=rule.is_text_component)
        return data

    @api.model
    def save_sample_inputs(self, sample_id, inputs):
        sample = self.env['hr.formula.sample.data'].browse(int(sample_id)).exists()
        if not sample:
            return {'ok': False}
        values = json.loads(sample.input_values_json or '{}')
        rules = {r.code: r for r in sample.config_id.rule_ids if r.column_type == 'input'}
        for code, value in (inputs or {}).items():
            rule = rules.get(code)
            if not rule:
                raise UserError(_('Unknown sample input: %s') % code)
            if rule.is_text_component or rule.value_kind in ('identifier', 'text', 'date', 'boolean'):
                values[code] = value
            else:
                try:
                    number = float(value)
                    if not math.isfinite(number):
                        raise ValueError()
                    values[code] = number
                except (TypeError, ValueError):
                    raise UserError(_('Enter a valid number for %s.') % rule.name)
            # Remove stale letter alias so changing a visible input changes computation.
            if rule.column_letter != code:
                values.pop(rule.column_letter, None)
        sample.input_values_json = json.dumps(values)
        return self.get_sample_detail(sample.id)

    def _experience_headline(self, config, code=None):
        rule = config.rule_ids.filtered(lambda r: r.code == code)[:1] if code else config._net_role_find_net_rule(config._net_role_rules())
        if not rule or rule.value_kind != 'money' or rule.column_type != 'formula':
            raise UserError(_('Choose a monetary outcome to measure. Set Net pay in Component treatment to use it by default.'))
        return rule.code

    @api.model
    def whatif_prepare(self, config_id, target_code, new_value, limit=None, run_id=None, headline_code=None):
        config = self._pick_config(config_id)
        headline = self._experience_headline(config, headline_code)
        target = config.rule_ids.filtered(lambda r: r.code == target_code and r.column_type == 'constant')
        if not target or not math.isfinite(float(new_value)):
            raise UserError(_('Choose a constant and a finite value to simulate.'))
        Sim = self.env['hr.formula.simulation']
        created = Sim.sim_create(config.id, value_overrides={target_code: float(new_value)})
        if not created.get('ok'):
            return created
        sim = Sim.browse(created['sim_id'])
        sim.headline_code = headline
        prep = Sim.sim_prepare(sim.id, limit=limit, run_id=run_id)
        rule = config.rule_ids.filtered(lambda r: r.code == headline)[:1]
        prep.update(headline=headline, headline_name=rule.name, ok=prep.get('ok', True))
        if not prep['ok']:
            sim.unlink()
            prep['sim_id'] = False
        return prep

    @api.model
    def compare_prepare(self, config_id, run_a_id, run_b_id, headline_code=None):
        config = self._pick_config(config_id)
        headline = self._experience_headline(config, headline_code)
        Cmp = self.env['hr.formula.period.comparison']
        created = Cmp.cmp_create(config.id, run_a_id, run_b_id)
        if not created.get('ok'):
            return created
        cmp = Cmp.browse(created['cmp_id'])
        cmp.headline_code = headline
        prep = Cmp.cmp_prepare(cmp.id)
        prep.update(ok=True, headline=headline)
        return prep
