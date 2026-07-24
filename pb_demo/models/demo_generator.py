# -*- coding: utf-8 -*-
"""Demo generator — FORMULA-ENGINE native, stateless, idempotent.

Builds: translatable component label rules (for multilingual payslip lines), a
single Vietnam company + divisions, and the demo FORMULA CONFIGS (hr.formula.config
+ hr.formula.rule) that the unchanged engine computes from. No salary structures.

Entry points (UI button or `odoo shell`):
    env['pb.demo.generator'].create({}).action_build_foundation()
    env['pb.demo.generator'].create({}).action_generate_all()
    env['pb.demo.generator'].create({}).action_clean_demo()
"""
import logging
import re
from odoo import api, fields, models, _

from . import demo_catalog as cat

_logger = logging.getLogger(__name__)


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class HrFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)
    # Report dimension: which division this config serves (country/currency already
    # live on the config via country_code/currency_id; cycle via cycle_type).
    pb_division = fields.Char(string='Division', index=True)


class HrFormulaRule(models.Model):
    _inherit = 'hr.formula.rule'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class HrPayrollCycleComponentMapping(models.Model):
    # Mid→End transfer mapping (ADVPAY). Tag demo records for clean rebuilds.
    _inherit = 'hr.payroll.cycle.component.mapping'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class HrPayrollCycleCarryover(models.Model):
    _inherit = 'hr.payroll.cycle.carryover'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)


class HrPayrollStructure(models.Model):
    # Kept only to clean up the OLD (wrong) structure-based demo.
    _inherit = 'hr.payroll.structure'
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)
    pb_division = fields.Char(index=True)
    pb_cycle = fields.Selection([('mid', 'Mid-Month'), ('end', 'End-Month')])


class PbDemoGenerator(models.TransientModel):
    _name = 'pb.demo.generator'
    _description = 'Payobook Demo Generator'

    headcount_factor = fields.Float(string='Headcount Factor', default=1.0)
    months = fields.Integer(string='History Months', default=7)
    include_history = fields.Boolean(string='Include Payroll History', default=True)

    _GEN_CTX = {'tracking_disable': True, 'mail_create_nolog': True,
                'mail_create_nosubscribe': True, 'mail_notrack': True}

    # ------------------------------------------------------------------ helpers
    def _ensure_languages(self):
        ResLang = self.env['res.lang']
        for code in ('en_US', 'vi_VN'):
            try:
                ResLang._activate_lang(code)
            except Exception as e:  # pragma: no cover
                _logger.warning('lang %s: %s', code, e)
        return bool(ResLang.with_context(active_test=False).search(
            [('code', '=', 'vi_VN'), ('active', '=', True)], limit=1))

    def _ensure_currency(self, code):
        Currency = self.env['res.currency'].with_context(active_test=False)
        cur = Currency.search([('name', '=', code)], limit=1)
        if cur and not cur.active:
            cur.active = True
        return cur

    def _tr(self, record, field, en, vi, has_vi):
        record.with_context(lang='en_US').write({field: en})
        if has_vi:
            record.with_context(lang='vi_VN').write({field: vi})

    def get_group_company(self):
        return self.env['res.company'].sudo().with_context(active_test=False).search(
            [('name', '=', cat.GROUP_COMPANY_NAME)], limit=1)

    def get_division_dept(self, company, key):
        return self.env['hr.department'].sudo().search(
            [('name', '=', cat.DIVISIONS[key]['name_en']), ('company_id', '=', company.id),
             ('parent_id', '=', False)], limit=1)

    def get_cost_centre_dept(self, parent, cc):
        return self.env['hr.department'].sudo().search(
            [('name', '=', cc), ('parent_id', '=', parent.id)], limit=1)

    def get_calendar(self, company):
        Cal = self.env['resource.calendar'].sudo()
        return company.resource_calendar_id or Cal.search([('company_id', '=', company.id)], limit=1)

    @api.model
    def resolve_config(self, division, cycle='end'):
        """(division, cycle) -> the division's demo formula config (12 total)."""
        code = 'DEMO_%s_%s' % (division.upper(), 'END' if cycle == 'end' else 'MID')
        return self.env['hr.formula.config'].sudo().with_context(active_test=False).search(
            [('code', '=', code), ('is_demo', '=', True)], limit=1)

    # --------------------------------------------------------------- categories
    def build_categories(self, has_vi):
        Cat = self.env['hr.salary.rule.category'].sudo()
        records = {}
        for code, en, vi, parent, ctype, seq in cat.CATEGORIES:
            rec = Cat.with_context(active_test=False).search([('code', '=', code)], limit=1)
            vals = {'code': code, 'name': en, 'company_id': False,
                    'category_type': ctype, 'display_order': seq, 'is_demo': True}
            rec.write(vals) if rec else (rec := Cat.create(vals))
            self._tr(rec, 'name', en, vi, has_vi)
            records[code] = rec
        for code, en, vi, parent, ctype, seq in cat.CATEGORIES:
            if parent:
                records[code].parent_id = records[parent].id
        return records

    # ---------------------------------------------- translatable label rules
    def build_label_rules(self, cats, has_vi):
        """One translatable hr.salary.rule per component CODE — used only as the
        multilingual label that formula rules + payslip lines link to."""
        Rule = self.env['hr.salary.rule'].sudo()
        labels = {}
        for code, en, vi, catcode, kind, spec, appears in cat.all_components():
            rec = Rule.with_context(active_test=False).search([('code', '=', code)], limit=1)
            vals = {'code': code, 'name': en, 'category_id': cats[catcode].id,
                    'company_id': False, 'is_demo': True, 'appears_on_payslip': appears,
                    'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 0.0}
            rec.write(vals) if rec else (rec := Rule.create(vals))
            self._tr(rec, 'name', en, vi, has_vi)
            labels[code] = rec
        return labels

    # ------------------------------------------------------------------ topology
    def build_topology(self):
        Company = self.env['res.company'].sudo()
        vnd = self._ensure_currency('VND')
        vn_country = self.env['res.country'].search([('code', '=', 'VN')], limit=1)
        group = self.get_group_company()
        if not group:
            group = Company.create({'name': cat.GROUP_COMPANY_NAME, 'currency_id': vnd.id,
                                    'country_id': vn_country.id})
        else:
            group.write({'currency_id': vnd.id, 'country_id': vn_country.id})
        if 'presentation_currency_id' in group._fields:
            group.presentation_currency_id = vnd.id
        Dept = self.env['hr.department'].sudo()
        for key, dv in cat.DIVISIONS.items():
            parent = self.get_division_dept(group, key)
            if not parent:
                parent = Dept.create({'name': dv['name_en'], 'company_id': group.id})
            for cc in dv['cost_centres']:
                if not self.get_cost_centre_dept(parent, cc):
                    Dept.create({'name': cc, 'parent_id': parent.id, 'company_id': group.id})
        if not self.get_calendar(group):
            self.env['resource.calendar'].sudo().create({'name': 'VN Standard 48h', 'company_id': group.id})
        return group

    # ------------------------------------------------------- formula configs
    _COL_TYPE = {'input': 'input', 'const': 'constant', 'formula': 'formula', 'helper': 'formula'}

    def _letterize_formulas(self, cfg):
        """Rewrite code-based excel_formulas into Excel CELL references (<letter>2).

        The studio's formula visual + dependency graph only recognise cell refs
        (letter+digit, e.g. G2) — bare codes render as empty chips. The compute
        converter handles both, so this is display-only. Codes are collision-free
        ([[formula-converter-contract]]) so a single word-boundary pass is safe;
        the digit is ignored by both tokenizer and converter.
        """
        rules = cfg.rule_ids
        code_to_letter = {r.code: r.column_letter for r in rules if r.code and r.column_letter}
        if not code_to_letter:
            return
        codes = sorted(code_to_letter, key=len, reverse=True)
        pat = re.compile(r'\b(' + '|'.join(re.escape(c) for c in codes) + r')\b')
        for r in rules:
            if r.column_type != 'formula' or not r.excel_formula:
                continue
            # mask quoted strings so codes inside them aren't touched (none expected)
            literals = []

            def _mask(m):
                literals.append(m.group(0))
                return '\x00%d\x00' % (len(literals) - 1)

            masked = re.sub(r'"([^"]|"")*"', _mask, r.excel_formula)
            new = pat.sub(lambda m: code_to_letter[m.group(1)] + '2', masked)
            for i, lit in enumerate(literals):
                new = new.replace('\x00%d\x00' % i, lit)
            if new != r.excel_formula:
                r.excel_formula = new

    def _build_cycle_mappings(self, config_by_code):
        """One Mid→End component mapping per division (ADVPAY), so the engine's
        cycle-carryover machinery transfers the mid advance into the end input."""
        Mapping = self.env['hr.payroll.cycle.component.mapping'].sudo().with_context(active_test=False)
        Mapping.search([('is_demo', '=', True)]).unlink()
        for div in cat._DIV_ORDER:
            mid = config_by_code.get('DEMO_%s_MID' % div.upper())
            end = config_by_code.get('DEMO_%s_END' % div.upper())
            if not (mid and end):
                continue
            mid_rule = mid.rule_ids.filtered(lambda r: r.code == cat.TRANSFER_CODE)[:1]
            end_rule = end.rule_ids.filtered(lambda r: r.code == cat.TRANSFER_CODE)[:1]
            if not (mid_rule and end_rule):
                continue
            Mapping.create({
                'mid_cycle_config_id': mid.id, 'mid_component_id': mid_rule.id,
                'end_cycle_config_id': end.id, 'end_component_id': end_rule.id,
                'is_demo': True,
            })
            _logger.info('pb_demo: cycle mapping %s mid→end (%s).', div, cat.TRANSFER_CODE)

    def build_configs(self, cats, labels, company):
        Config = self.env['hr.formula.config'].sudo()
        Rule = self.env['hr.formula.rule'].sudo()
        keep = []
        config_by_code = {}
        for code, name_en, name_vi, division, cycle in cat.CONFIGS:
            keep.append(code)
            components = cat.build_components(division, cycle)
            cfg = Config.with_context(active_test=False).search([('code', '=', code)], limit=1)
            cvals = {'name': name_en, 'code': code, 'country_code': cat.COUNTRY_CODE,
                     'cycle_type': 'end_cycle' if cycle == 'end' else 'mid_cycle',
                     'company_id': company.id, 'state': 'active', 'structure_id': False,
                     'is_demo': True, 'pb_division': division,
                     # Feature the Retail End config (low sequence) so the studio /
                     # tutorial lands on a real, richly-named division config by
                     # default rather than the highest-id scale-test (_pick_config
                     # orders by sequence first). Mirrored in hooks._feature_demo_config.
                     'sequence': 1 if code == 'DEMO_RETAIL_END' else 10}
            if cfg:
                cfg.rule_ids.unlink()
                cfg.write(cvals)
            else:
                cfg = Config.create(cvals)
            vals_list = []
            for i, (ccode, en, vi, catcode, kind, spec, appears) in enumerate(components):
                rv = {'config_id': cfg.id, 'code': ccode, 'name': en, 'is_demo': True,
                      'column_type': self._COL_TYPE[kind], 'sequence': (i + 1) * 10,
                      'category_id': cats[catcode].id, 'appears_on_payslip': appears,
                      'salary_rule_id': labels[ccode].id}
                if kind == 'const':
                    rv['constant_value'] = float(spec)
                    rv['data_source'] = 'manual'
                elif kind in ('formula', 'helper'):
                    rv['excel_formula'] = spec
                    rv['data_source'] = 'formula'
                else:  # input
                    rv['data_source'] = 'manual'
                vals_list.append(rv)
            Rule.create(vals_list)
            self._letterize_formulas(cfg)   # code refs -> cell refs (for the studio visual)
            config_by_code[code] = cfg
            _logger.info('pb_demo: config %s built with %s rules.', code, len(vals_list))
        # Mid→End transfer mappings (ADVPAY) once all configs exist.
        self._build_cycle_mappings(config_by_code)
        # Drop stale demo configs no longer in the catalog (e.g. the old single
        # DEMO_VN_END/MID). Archive if payslips still reference them.
        stale = Config.with_context(active_test=False).search(
            [('is_demo', '=', True), ('code', 'not in', keep)])
        for cfg in stale:
            code = cfg.code
            try:
                cfg.rule_ids.unlink()
                cfg.unlink()
                _logger.info('pb_demo: removed stale demo config %s.', code)
            except Exception:
                try:
                    cfg.write({'active': False})
                    _logger.info('pb_demo: archived stale demo config %s (still referenced).', code)
                except Exception:
                    _logger.info('pb_demo: could not remove/archive stale config %s.', code)

    # --------------------------------------------------------------- orchestration
    def action_build_foundation(self):
        self = self.with_context(**self._GEN_CTX)
        has_vi = self._ensure_languages()
        cats = self.build_categories(has_vi)
        labels = self.build_label_rules(cats, has_vi)
        group = self.build_topology()
        self.build_configs(cats, labels, group)
        _logger.info('pb_demo: formula-config foundation built.')
        return True

    def action_generate_all(self):
        self = self.with_context(**self._GEN_CTX)
        self.action_build_foundation()
        self.generate_employees()      # demo_employees.py
        self.ensure_ess_demo_users()   # demo_ess.py — MSS/ESS demo logins + queue
        if self.include_history:
            self.generate_history()    # demo_history.py
        self.generate_extras()         # demo_extras.py (F&F, proration, retro, insurance adj, dependents)
        self.generate_integrations()   # demo_integrations.py
        return self._notify(_('Demo environment generated successfully.'))

    def action_clean_demo(self):
        self.clean_demo_employees()    # demo_employees.py
        return self._notify(_('Demo employees and payroll history cleared.'))

    def _notify(self, message):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Payobook Demo'), 'message': message,
                           'type': 'success', 'sticky': False}}
