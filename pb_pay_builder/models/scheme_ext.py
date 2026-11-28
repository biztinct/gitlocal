import re
import hashlib

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.addons.pb_formula_studio.models.take_home import _Engine
from odoo.addons.pb_hr_payroll_formula.models.contract_fill_in import NUMERIC_FILL_KINDS


BANDS = {'GROSS': 'earn', 'ALW': 'earn', 'BASIC': 'earn', 'DED': 'ded', 'ERCOST': 'er'}
ANNUAL = re.compile(r'\b(?:annual|yearly|per\s+year|ctc|p\.a\b\.?)\b', re.I)


class PayBuilderRule(models.Model):
    _inherit = 'hr.formula.rule'

    pbpb_period = fields.Selection([('month', 'Month'), ('year', 'Year')], string='Typed per')

    def _pbpb_name(self):
        self.ensure_one()
        if (self.name or '').strip().casefold() == 'annual fixed ctc':
            return self.env._('Annual fixed pay')
        return self.name

    def _pbpb_period_guess(self):
        self.ensure_one()
        words = ('%s %s' % (self.name or '', self.code or '')).replace('_', ' ')
        return self.pbpb_period or ('year' if (self.code or '').upper().startswith('INANN')
                                    or ANNUAL.search(words) else 'month')

    @api.constrains('is_contract_component', 'column_type', 'value_kind', 'config_id')
    def _pbpb_main_still_valid(self):
        self.env['hr.formula.config'].sudo().search([('pbpb_main_rule_id', 'in', self.ids)])._pbpb_check_main()


class PayBuilderScheme(models.Model):
    _inherit = 'hr.formula.config'

    pbpb_main_rule_id = fields.Many2one('hr.formula.rule', string='Main pay amount', ondelete='set null',
        domain="[('config_id', '=', id), ('column_type', '=', 'input'), ('is_contract_component', '=', True), ('value_kind', '=', 'money')]")

    @api.constrains('pbpb_main_rule_id')
    def _pbpb_check_main(self):
        for scheme in self:
            rule = scheme.pbpb_main_rule_id
            if rule and (rule.config_id != scheme or rule not in scheme._pbpb_person_rules() or rule.value_kind != 'money'):
                raise ValidationError(_("Choose a per-person money amount from this pay scheme."))

    def _pbpb_person_rules(self):
        self.ensure_one()
        return self.rule_ids.filtered(lambda r: r.column_type == 'input' and r.is_contract_component
            and not r.is_text_component and r.value_kind in NUMERIC_FILL_KINDS and (r.code or '').strip()
        ).sorted(lambda r: (r.sequence, r.id))

    def _pbpb_head_rule(self, engine=None, wage_codes=None):
        """An empty rule means the contract wage. A reference-only mapping cannot hide agreed pay."""
        self.ensure_one()
        if self.pbpb_main_rule_id:
            return self.pbpb_main_rule_id
        candidates = self._pbpb_person_rules().filtered(lambda r: r.value_kind == 'money')
        if not candidates:
            return candidates
        engine = engine or _Engine(self.env, self)
        wage_codes = self.env['pb.formula.studio']._th_wage_codes(self) if wage_codes is None else wage_codes
        upstream = engine.upstream([s['code'] for s in engine.net_specs[:1]])
        if upstream.intersection(wage_codes):
            return candidates[:0]
        return candidates.filtered(lambda r: r.code in upstream)[:1]

    def _pbpb_program(self):
        self.ensure_one()
        rules = self.rule_ids
        wages = tuple(self.env['pb.formula.studio']._th_wage_codes(self))
        # Include content because write_date can stay fixed inside a transaction.
        fields_used = ('id', 'sequence', 'code', 'name', 'column_letter', 'column_type',
                       'excel_formula', 'formula_dependencies', 'net_role', 'net_role_detail',
                       'appears_on_payslip', 'value_kind', 'is_text_component', 'is_contract_component',
                       'default_value', 'pbpb_period', 'value_labels', 'period_key')
        content = [(tuple(r[f] for f in fields_used), r.category_id.code,
                    tuple((source.kind, source.key) for source in r.source_ids),
                    getattr(r, 'pb_clock_key', False)) for r in rules]
        signature = hashlib.sha256(repr((content, self.source_priority, self.pbpb_main_rule_id.id,
                                         self.write_date)).encode()).hexdigest()
        specs, layout = self._pbpb_cached_layout(signature, wages)
        return _Engine(self.env, self, line_specs=specs), layout

    @tools.ormcache('self.id', 'self.env.lang', 'signature', 'wages')
    def _pbpb_cached_layout(self, signature, wages):
        engine = _Engine(self.env, self)
        return engine.specs, self._pbpb_classify(engine, wages)

    def _pbpb_layout(self):
        return self._pbpb_program()[1]

    def _pbpb_classify(self, engine, wages):
        main = self._pbpb_head_rule(engine, wages)
        person = self._pbpb_person_rules()
        specs = {s['code']: s for s in engine.specs}
        visible = [k for k, s in specs.items() if s['band'] in BANDS or s['band'] == 'NET']
        upstream = engine.upstream(visible)
        by_letter = {r.column_letter: r.code for r in self.rule_ids}
        by_code = set(self.rule_ids.mapped('code'))
        asks, rows = [], []
        sources = set()
        for rule in self.rule_ids.sorted(lambda r: (r.sequence, r.id)):
            if rule.is_text_component or rule.value_kind not in NUMERIC_FILL_KINDS or rule.column_type == 'constant':
                continue
            spec = specs.get(rule.code, {})
            section = BANDS.get(spec.get('band'))
            kind = 'calc' if rule.column_type == 'formula' else 'set' if rule in person else 'each'
            if rule.code in wages and not main:
                kind = 'wage'
            source = ''
            if kind == 'each':
                declared = rule.declared_sources()
                source = declared[0]['kind'] if declared else ''
                if rule.period_key or rule.code.startswith(('WD_', 'HOURS')) or getattr(rule, 'pb_clock_key', False):
                    source = 'pay_run'
                if rule.code in upstream:
                    sources.add(source)
            if rule == main or spec.get('band') == 'NET':
                continue
            deps = set()
            for token in (rule.formula_dependencies or '').split(','):
                key = token.strip().upper()
                if key in by_letter:
                    deps.add(by_letter[key])
                if key in by_code:
                    deps.add(key)
            deps.discard(rule.code)
            ctl = {'toggle': 'toggle', 'select': 'choice'}.get(rule.value_label_control(),
                      'money' if rule.value_kind == 'money' else 'number')
            line = {'code': rule.code, 'name': rule.name, 'usual': rule.default_value or 0,
                    'kind': kind, 'control': ctl, 'period': rule._pbpb_period_guess(),
                    'options': rule.value_word_choices() if ctl in ('choice', 'toggle') else [],
                    'section': section, 'detail': bool(spec.get('component_detail')),
                    'source_kind': source, 'uses': sorted(deps), 'hint': _('Usual answer: %s', rule.value_label_for(rule.default_value)) if rule.value_label_for(rule.default_value) else ''}
            if kind == 'set' and (line['period'] == 'year' or not section or ctl != 'money'):
                if section or rule.code in upstream or line['period'] == 'year':
                    asks.append(line)
            elif section:
                rows.append(line)
        totals = {}
        for group in ('earn', 'ded', 'er'):
            group_rows = [r for r in rows if r['section'] == group]
            counts = [r for r in group_rows if not r['detail']]
            if len(counts) == 1 and counts[0]['kind'] == 'calc' and len(group_rows) > 1:
                totals[group] = counts[0]['code']
                for r in group_rows:
                    r['detail'] = False
        title = main._pbpb_name() if main else _('Monthly wage')
        return {'head': {'code': main.code if main else 'wage', 'name': title,
                         'period': main._pbpb_period_guess() if main else 'month', 'usual': main.default_value if main else 0,
                         'is_wage': not main, 'required': True},
                'wages': wages, 'asks': asks, 'rows': rows, 'total_codes': totals,
                'sources': sorted(sources), 'has_net': bool(engine.net_specs),
                'file_only': not main and not wages and not person}
