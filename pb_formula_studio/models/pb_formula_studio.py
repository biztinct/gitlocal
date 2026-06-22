# -*- coding: utf-8 -*-
import json
import logging
import re

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from odoo import api, models

_logger = logging.getLogger(__name__)

# Config parameters (Settings > Technical > Parameters). Empty api_key => PayAI
# uses the built-in deterministic mapper. base_url can point at ANY
# OpenAI-compatible endpoint (OpenAI, Ollama, vLLM, LM Studio, OpenRouter…).
LLM_BASE_URL = 'pb_formula_studio.llm_base_url'
LLM_API_KEY = 'pb_formula_studio.llm_api_key'
LLM_MODEL = 'pb_formula_studio.llm_model'
DEFAULT_BASE_URL = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-4o-mini'

# Map an Excel operator to a friendly chip glyph
OP_GLYPH = {'+': '+', '-': '−', '*': '×', '/': '÷'}

# Category grouping for the outline (by code/name heuristics)
def _group_for(rule):
    code = (rule.code or '').upper()
    name = (rule.name or '').lower()
    if rule.column_type == 'input':
        return 'Inputs'
    if any(k in code or k in name for k in ('NET', 'GROSS', 'TOTAL', 'thực nhận', 'tổng')):
        return 'Totals'
    if any(k in code or k in name for k in ('SI', 'HI', 'UI', 'PIT', 'TAX', 'DED', 'insurance', 'deduction', 'bảo hiểm', 'thuế')):
        return 'Deductions'
    return 'Earnings'


class PbFormulaStudio(models.AbstractModel):
    _name = 'pb.formula.studio'
    _description = 'Payobook Formula Studio data layer (wraps the formula engine)'

    # ------------------------------------------------------------------
    # config selection / list
    # ------------------------------------------------------------------
    @api.model
    def get_config_list(self):
        configs = self.env['hr.formula.config'].search([], order='sequence, id desc')
        return [{
            'id': c.id,
            'name': c.name,
            'code': c.code or '',
            'country': c.country_code or '',
            'state': c.state,
            'rule_count': len(c.rule_ids),
        } for c in configs]

    @api.model
    def _pick_config(self, config_id=None):
        Config = self.env['hr.formula.config']
        if config_id:
            c = Config.browse(int(config_id))
            if c.exists():
                return c
        # prefer an active config with rules, else newest with rules, else newest
        c = Config.search([('state', '=', 'active'), ('rule_ids', '!=', False)], order='id desc', limit=1)
        if c:
            return c
        c = Config.search([('rule_ids', '!=', False)], order='id desc', limit=1)
        return c or Config.search([], order='id desc', limit=1)

    # ------------------------------------------------------------------
    # formula tokenizing (for the friendly chip view + plain-language)
    # ------------------------------------------------------------------
    @api.model
    def _col_to_rule(self, rules):
        return {r.column_letter: r for r in rules if r.column_letter}

    @api.model
    def _tokenize(self, rule, by_col):
        """Turn '=A1*0.2' into chip tokens referencing component names."""
        if rule.column_type == 'input':
            return [{'kind': 'src', 'text': 'From contract / import'}]
        if rule.column_type == 'constant':
            val = rule.constant_value or 0.0
            return [{'kind': 'num', 'text': '{:,.0f}'.format(val)}]
        formula = (rule.excel_formula or '').lstrip('=').strip()
        if not formula:
            return [{'kind': 'src', 'text': 'No formula yet'}]
        tokens = []
        # split keeping operators and parens
        parts = re.findall(r'[A-Za-z]+\d+|\d+\.?\d*|[+\-*/()%]', formula)
        for p in parts:
            m = re.match(r'^([A-Za-z]+)\d+$', p)
            if m:
                col = m.group(1).upper()
                ref = by_col.get(col)
                tokens.append({'kind': 'ref', 'col': col,
                               'text': ref.name if ref else col})
            elif p in OP_GLYPH:
                tokens.append({'kind': 'op', 'text': OP_GLYPH[p]})
            elif p in ('(', ')', '%'):
                tokens.append({'kind': 'op', 'text': p})
            else:
                tokens.append({'kind': 'num', 'text': p})
        return tokens

    @api.model
    def _explain(self, rule, by_col):
        if rule.column_type == 'input':
            return "Comes from each employee's contract or the monthly import."
        if rule.column_type == 'constant':
            return "A fixed value applied to every employee."
        toks = self._tokenize(rule, by_col)
        refs = [t for t in toks if t['kind'] == 'ref']
        ops = [t for t in toks if t['kind'] == 'op']
        has_paren = any(t['text'] in ('(', ')') for t in ops)
        # For simple formulas, build a readable sentence; for complex ones,
        # summarise by the components it draws from (the chip view shows the rest).
        if has_paren or len(refs) > 3:
            names = []
            for t in refs:
                if t['text'] not in names:
                    names.append(t['text'])
            if names:
                return rule.name + ' is calculated from ' + ', '.join(names[:6]) + \
                    ('and others.' if len(names) > 6 else '.')
            return rule.name + ' is a calculated component.'
        words = []
        for t in toks:
            if t['kind'] == 'ref':
                words.append(t['text'])
            elif t['kind'] == 'op':
                words.append({'+': 'plus', '−': 'minus', '×': 'times', '÷': 'divided by'}.get(t['text'], t['text']))
            elif t['kind'] == 'num':
                words.append(t['text'])
        return rule.name + ' is computed as ' + ' '.join(words) + '.'

    # ------------------------------------------------------------------
    # main payload
    # ------------------------------------------------------------------
    @api.model
    def get_studio_data(self, config_id=None):
        config = self._pick_config(config_id)
        if not config:
            return {'empty': True, 'configs': self.get_config_list()}

        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        by_col = self._col_to_rule(rules)

        # dependency maps
        depends = {}
        used_by = {}
        for r in rules:
            refs = set(re.findall(r'([A-Za-z]+)\d+', (r.excel_formula or ''))) if r.column_type == 'formula' else set()
            depends[r.id] = [by_col[c.upper()].name for c in refs if c.upper() in by_col]
            for c in refs:
                rr = by_col.get(c.upper())
                if rr:
                    used_by.setdefault(rr.id, []).append(r.name)

        components = []
        for r in rules:
            components.append({
                'id': r.id,
                'col': r.column_letter or '?',
                'code': r.code or '',
                'name': r.name or '(unnamed)',
                'type': r.column_type,
                'group': _group_for(r),
                'excel_formula': r.excel_formula or '',
                'constant_value': r.constant_value or 0.0,
                'tokens': self._tokenize(r, by_col),
                'explain': self._explain(r, by_col),
                'category': r.category_id.name if r.category_id else (r.column_type or '').title(),
                'number_format': r.number_format or 'number',
                'is_valid': bool(r.is_valid) and not r.has_evaluation_error,
                'validation_message': r.validation_message or r.last_evaluation_error or '',
                'depends_on': depends.get(r.id, []),
                'used_by': used_by.get(r.id, []),
            })

        samples = [{'id': s.id, 'name': s.name} for s in config.sample_data_ids]
        preview = self._compute(config, samples[0]['id']) if samples else {'sample_id': False, 'values': {}}

        score = self._score(config)
        return {
            'empty': False,
            'configs': self.get_config_list(),
            'config': {
                'id': config.id,
                'name': config.name,
                'code': config.code or '',
                'country': config.country_code or '',
                'currency': config.currency_id.symbol if config.currency_id else '',
                'state': config.state,
                'score': score,
                'validation_message': config.validation_message or '',
                'rule_count': len(rules),
                'sample_count': len(config.sample_data_ids),
            },
            'components': components,
            'samples': samples,
            'preview': preview,
        }

    @api.model
    def _score(self, config):
        rules = config.rule_ids.filtered(lambda r: r.column_type == 'formula')
        if not rules:
            return 100
        bad = len(rules.filtered(lambda r: (not r.is_valid) or r.has_evaluation_error or r.has_circular_ref))
        return int(round(100 * (len(rules) - bad) / max(len(rules), 1)))

    # ------------------------------------------------------------------
    # live compute (reuses the engine evaluator)
    # ------------------------------------------------------------------
    @api.model
    def _compute(self, config, sample_id):
        from odoo.addons.pb_hr_payroll_formula.formula_engine import FormulaEvaluator
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        values = {}
        try:
            sample = self.env['hr.formula.sample.data'].browse(int(sample_id))
            input_values = json.loads(sample.input_values_json or '{}') if sample.exists() else {}
            values = FormulaEvaluator().evaluate_all(rules, input_values)
        except Exception as e:
            _logger.warning("Studio compute failed: %s", e)
        # key by column letter for the UI
        by_code = {r.code: r.column_letter for r in rules}
        out = {}
        for code, v in values.items():
            col = by_code.get(code)
            if col:
                try:
                    out[col] = float(v)
                except (TypeError, ValueError):
                    out[col] = 0.0
        return {'sample_id': int(sample_id), 'values': out}

    @api.model
    def compute_preview(self, config_id, sample_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        return self._compute(config, sample_id) if config.exists() else {'sample_id': sample_id, 'values': {}}

    # ------------------------------------------------------------------
    # edit operations
    # ------------------------------------------------------------------
    @api.model
    def save_formula(self, rule_id, excel_formula):
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'msg': 'Component not found'}
        config = rule.config_id
        column_map = {r.column_letter: r.code for r in config.rule_ids if r.column_letter}
        try:
            rule.excel_formula = excel_formula
            if rule.column_type == 'formula':
                rule.python_formula = rule._convert_excel_to_python(excel_formula, column_map)
            rule.is_valid = True
            rule.validation_message = ''
        except Exception as e:
            return {'ok': False, 'msg': str(e)}
        return {'ok': True}

    @api.model
    def update_component(self, rule_id, vals):
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False}
        allowed = {k: v for k, v in (vals or {}).items()
                   if k in ('name', 'number_format', 'constant_value', 'decimal_places', 'appears_on_payslip')}
        if allowed:
            rule.write(allowed)
        return {'ok': True}

    @api.model
    def add_component(self, config_id, vals):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False}
        vals = vals or {}
        rule = self.env['hr.formula.rule'].create({
            'config_id': config.id,
            'name': vals.get('name') or 'New Component',
            'code': (vals.get('code') or 'NEW').upper().replace(' ', '_'),
            'column_type': vals.get('column_type') or 'formula',
            'excel_formula': vals.get('excel_formula') or '',
            'constant_value': vals.get('constant_value') or 0.0,
            'sequence': max(config.rule_ids.mapped('sequence') or [0]) + 1,
        })
        return {'ok': True, 'rule_id': rule.id}

    @api.model
    def delete_component(self, rule_id):
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if rule.exists():
            rule.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # lifecycle (reuses config methods)
    # ------------------------------------------------------------------
    @api.model
    def _state_result(self, config):
        return {'ok': True, 'state': config.state, 'score': self._score(config),
                'message': config.validation_message or ''}

    @api.model
    def validate(self, config_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        try:
            config.action_validate()
        except Exception as e:
            return {'ok': False, 'state': config.state, 'message': str(e)}
        return self._state_result(config)

    @api.model
    def run_tests(self, config_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        try:
            config.action_run_tests()
        except Exception as e:
            return {'ok': False, 'message': str(e)}
        results = config.test_result_ids
        passed = len(results.filtered(lambda r: r.status == 'passed'))
        return {'ok': True, 'total': len(results), 'passed': passed,
                'failed': len(results) - passed, 'state': config.state, 'score': self._score(config)}

    @api.model
    def advance(self, config_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False}
        st = config.state
        try:
            if st == 'draft':
                config.action_start_testing()
            elif st == 'testing':
                config.action_validate()
            elif st == 'validated':
                config.action_activate()
        except Exception as e:
            return {'ok': False, 'state': config.state, 'message': str(e)}
        return self._state_result(config)

    @api.model
    def set_draft(self, config_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if config.exists():
            config.action_set_draft()
        return self._state_result(config)

    # ------------------------------------------------------------------
    # PayAI : natural-language -> formula (deterministic mapper)
    # ------------------------------------------------------------------
    @api.model
    def ai_propose(self, config_id, text):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False, 'reply': 'No configuration loaded.'}
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        text_l = (text or '').strip().lower()
        if not text_l:
            return {'ok': False, 'reply': 'Tell me what the component should compute.'}

        # Prefer a real LLM when configured; it only proposes — we validate its
        # output against the real columns below and fall back if anything is off.
        llm = self._llm_propose(config, text, rules)
        if llm is not None:
            return llm

        # build keyword -> rule index from names + codes
        def keywords(r):
            ks = set()
            ks.add((r.code or '').lower())
            for w in re.split(r'[\s_()/-]+', (r.name or '').lower()):
                if len(w) > 2:
                    ks.add(w)
            return {k for k in ks if k}

        kw_index = [(r, keywords(r)) for r in rules]

        # explain intent
        if text_l.startswith('explain') or 'what is' in text_l or 'how is' in text_l:
            target = self._match_rule(text_l, kw_index, rules)
            if target:
                by_col = self._col_to_rule(rules)
                return {'ok': True, 'kind': 'explain', 'reply': self._explain(target, by_col),
                        'target_name': target.name}
            return {'ok': True, 'kind': 'explain',
                    'reply': "I couldn't find that component. Try its exact name."}

        # detect target ("net is ...", "net = ...", "net pay is ...")
        target = None
        head = re.split(r'\b(is|equals?|=)\b', text_l, maxsplit=1)
        if len(head) >= 2:
            target = self._match_rule(head[0], kw_index, rules)
            body = head[-1]
        else:
            body = text_l

        # map operators + operands in order of appearance
        op_words = [
            (r'\bminus\b|\bless\b|\bsubtract(ing)?\b|\bafter\b|−|-', '-'),
            (r'\bplus\b|\band\b|\badd(ing)?\b|\+', '+'),
            (r'\btimes\b|\bmultipl\w*\b|×|\*|\bof\b', '*'),
            (r'\bdivided by\b|\bover\b|÷|/', '/'),
        ]
        # percentage like "20%" or "20 percent"
        pct = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', body)

        # Find referenced components by matching their FULL NAME (or code) as a
        # contiguous substring of the request — far more precise than per-word
        # matching on configs with many overlapping names.
        matches = []  # (start, end, rule)
        for r in rules:
            if r == target:
                continue
            for needle in (r.name or '').lower().strip(), (r.code or '').lower().strip():
                if len(needle) >= 3:
                    p = body.find(needle)
                    if p >= 0:
                        matches.append((p, p + len(needle), r))
                        break
        # prefer longer (more specific) names; drop matches whose span is
        # contained within an already-accepted, longer match
        matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        accepted = []
        for st, en, r in matches:
            if any(st >= a_st and en <= a_en and r is not ar for a_st, a_en, ar in accepted):
                continue
            accepted.append((st, en, r))
        accepted.sort(key=lambda m: m[0])
        ref_rules = [r for _, _, r in accepted]

        # fallback: loose per-word match only if no full-name match landed
        if not ref_rules:
            positions = []
            for r, ks in kw_index:
                best = None
                for k in ks:
                    if len(k) >= 4:
                        p = body.find(k)
                        if p >= 0 and (best is None or p < best):
                            best = p
                if best is not None and r != target:
                    positions.append((best, r))
            positions.sort()
            ref_rules = [r for _, r in positions]

        # special phrases
        if 'all deduction' in body or 'total deduction' in body:
            ded = next((r for r in rules if 'ded' in (r.code or '').lower() or 'deduction' in (r.name or '').lower()), None)
            if ded and ded not in ref_rules:
                ref_rules = [r for r in ref_rules if 'ded' not in (r.code or '').lower()]
                ref_rules.append(ded)

        if not ref_rules and not pct:
            return {'ok': False, 'reply': "I couldn't map that to your existing components. "
                    "Mention them by name, e.g. \"gross minus total deductions\"."}

        # determine operator
        op = '+'
        for pat, o in op_words:
            if re.search(pat, body):
                op = o
                break

        mapping = []
        if pct and len(ref_rules) >= 1:
            base = ref_rules[0]
            factor = float(pct.group(1)) / 100.0
            formula = '=%s1*%s' % (base.column_letter, factor)
            mapping.append({'phrase': pct.group(0), 'col': base.column_letter, 'name': base.name})
            mapping.append({'phrase': base.name, 'col': base.column_letter, 'name': base.name})
            human = '%s%% of %s' % (pct.group(1), base.name)
        else:
            cols = []
            for r in ref_rules:
                cols.append('%s1' % r.column_letter)
                mapping.append({'phrase': r.name, 'col': r.column_letter, 'name': r.name})
            formula = '=' + (' %s ' % op).join(cols)
            human = (' %s ' % OP_GLYPH.get(op, op)).join(r.name for r in ref_rules)

        result = {
            'ok': True,
            'kind': 'formula',
            'formula': formula,
            'human': human,
            'mapping': mapping,
            'reply': 'Here is the formula I built from your description.',
        }
        if target:
            result['target_id'] = target.id
            result['target_col'] = target.column_letter
            result['target_name'] = target.name
        else:
            result['target_name'] = None  # would be a new component
        return result

    @api.model
    def _match_rule(self, fragment, kw_index, rules):
        frag = (fragment or '').lower()
        # 1) prefer the longest full component name that appears in the fragment
        best_name, best_len = None, 0
        for r in rules:
            nm = (r.name or '').lower().strip()
            if len(nm) >= 3 and nm in frag and len(nm) > best_len:
                best_name, best_len = r, len(nm)
        if best_name:
            return best_name
        # 2) fall back to keyword overlap
        best, best_score = None, 0
        for r, ks in kw_index:
            score = sum(1 for k in ks if k and len(k) >= 4 and k in frag)
            if score > best_score:
                best, best_score = r, score
        return best

    @api.model
    def apply_ai_formula(self, rule_id, formula):
        return self.save_formula(rule_id, formula)

    # ------------------------------------------------------------------
    # LLM-backed proposal (provider-agnostic, OpenAI-compatible)
    # ------------------------------------------------------------------
    @api.model
    def _llm_propose(self, config, text, rules):
        if requests is None:
            return None
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = (ICP.get_param(LLM_API_KEY) or '').strip()
        if not api_key:
            return None  # not configured -> deterministic mapper
        base_url = (ICP.get_param(LLM_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip('/')
        model = (ICP.get_param(LLM_MODEL) or DEFAULT_MODEL).strip()

        by_col = {r.column_letter: r for r in rules if r.column_letter}
        catalog = [{'col': r.column_letter, 'code': r.code, 'name': r.name,
                    'type': r.column_type} for r in rules if r.column_letter]
        system = (
            "You are PayAI, a payroll formula assistant inside Payobook. "
            "You translate a plain-language request into an Excel-style formula that "
            "references ONLY the existing components by their column letter followed by 1 "
            "(e.g. A1, BT1). Never invent column letters. Operators: + - * / and parentheses. "
            "Percentages become decimals (20% -> *0.2).\n"
            "Reply with STRICT JSON only, no prose, shaped exactly:\n"
            '{"kind":"formula"|"explain","target_col":"<existing letter or null>",'
            '"formula":"=<excel using LETTER1 refs>","human":"<short plain-english>",'
            '"mapping":[{"name":"<component name>","col":"<letter>"}],"reply":"<one sentence>"}\n'
            "For an explain request set kind=explain and put the explanation in reply; "
            "formula/mapping may be empty. target_col is the component being defined if the "
            "user names one (else null = a new component)."
        )
        user = "Components:\n" + json.dumps(catalog, ensure_ascii=False) + "\n\nRequest: " + (text or '')
        try:
            resp = requests.post(
                base_url + '/chat/completions',
                headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'},
                json={
                    'model': model,
                    'messages': [{'role': 'system', 'content': system},
                                 {'role': 'user', 'content': user}],
                    'temperature': 0,
                    'response_format': {'type': 'json_object'},
                },
                timeout=25,
            )
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']
            data = json.loads(content)
        except Exception as e:
            _logger.warning("PayAI LLM call failed, falling back: %s", e)
            return None

        return self._validate_llm(data, by_col)

    @api.model
    def _validate_llm(self, data, by_col):
        """Trust nothing: every referenced column must exist; else reject."""
        try:
            kind = data.get('kind') or 'formula'
            if kind == 'explain':
                return {'ok': True, 'kind': 'explain',
                        'reply': data.get('reply') or data.get('human') or 'Here is what that does.'}
            formula = (data.get('formula') or '').strip()
            if not formula:
                return None
            refs = set(re.findall(r'([A-Za-z]+)\d+', formula))
            bad = [c for c in refs if c.upper() not in by_col]
            if bad or not refs:
                _logger.info("PayAI LLM referenced unknown columns %s; falling back.", bad)
                return None
            target_col = data.get('target_col')
            target = by_col.get((target_col or '').upper()) if target_col else None
            # rebuild mapping from real components for trustworthy display
            mapping = [{'name': by_col[c.upper()].name, 'col': c.upper()} for c in sorted(refs)]
            result = {
                'ok': True, 'kind': 'formula',
                'formula': formula if formula.startswith('=') else '=' + formula,
                'human': self._readable_formula(formula, by_col),
                'mapping': mapping,
                'reply': data.get('reply') or data.get('human') or 'Here is the formula I built from your description.',
            }
            if target:
                result['target_id'] = target.id
                result['target_col'] = target.column_letter
                result['target_name'] = target.name
            else:
                result['target_name'] = None
            return result
        except Exception as e:
            _logger.warning("PayAI LLM validation error: %s", e)
            return None

    @api.model
    def _readable_formula(self, formula, by_col):
        """Render '=AV1-BB1' as 'Tổng thu nhập − TỔng BHXH' for display."""
        out = []
        for tok in re.findall(r'[A-Za-z]+\d+|\d+\.?\d*|[+\-*/()%]', (formula or '').lstrip('=')):
            m = re.match(r'^([A-Za-z]+)\d+$', tok)
            if m and m.group(1).upper() in by_col:
                out.append(by_col[m.group(1).upper()].name)
            elif tok in OP_GLYPH:
                out.append(OP_GLYPH[tok])
            else:
                out.append(tok)
        return ' '.join(out) if out else (formula or '')

    @api.model
    def ai_status(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {'llm': bool((ICP.get_param(LLM_API_KEY) or '').strip()),
                'model': ICP.get_param(LLM_MODEL) or DEFAULT_MODEL}

    # ------------------------------------------------------------------
    # First-setup wizard
    # ------------------------------------------------------------------
    # Vietnam Standard starter set (code, name, type, excel_formula, constant)
    VN_STANDARD = [
        ('BASIC', 'Basic Salary', 'input', '', 0.0),
        ('HRA', 'Housing Allowance', 'formula', '=A1*0.2', 0.0),
        ('TRANSPORT', 'Transport Allowance', 'constant', '', 500000.0),
        ('MEAL', 'Meal Allowance', 'constant', '', 730000.0),
        ('GROSS', 'Gross Salary', 'formula', '=A1+B1+C1+D1', 0.0),
        ('SI_EMP', 'Social Insurance (Employee)', 'formula', '=A1*0.08', 0.0),
        ('HI_EMP', 'Health Insurance (Employee)', 'formula', '=A1*0.015', 0.0),
        ('UI_EMP', 'Unemployment Insurance (Employee)', 'formula', '=A1*0.01', 0.0),
        ('TOTAL_DED', 'Total Deductions', 'formula', '=F1+G1+H1', 0.0),
        ('NET', 'Net Salary', 'formula', '=E1-I1', 0.0),
    ]

    @api.model
    def _idx_letter(self, i):
        """0->A, 25->Z, 26->AA … (Excel-style)."""
        s = ''
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    @api.model
    def wizard_templates(self):
        return [
            {'key': 'vn_standard', 'name': 'Vietnam Standard',
             'desc': '10 components pre-wired: Basic, allowances, SI/HI/UI, Gross & Net — VN statutory rates.',
             'preview': [{'col': 'A', 'name': 'Basic Salary', 'f': 'input'},
                         {'col': 'B', 'name': 'Housing Allowance', 'f': '= Basic × 20%'},
                         {'col': 'E', 'name': 'Gross Salary', 'f': '= A+B+C+D'},
                         {'col': 'J', 'name': 'Net Salary', 'f': '= Gross − Deductions'}]},
            {'key': 'blank', 'name': 'Blank canvas',
             'desc': 'Start empty and build components one by one — or ask PayAI to draft them.',
             'preview': []},
        ]

    @api.model
    def create_config(self, vals):
        vals = vals or {}
        Config = self.env['hr.formula.config']
        cvals = {
            'name': vals.get('name') or 'New Payroll Config',
            'country_code': vals.get('country_code') or 'VN',
            'cycle_type': vals.get('cycle_type') or 'regular',
            'state': 'draft',
        }
        # only set code if the caller explicitly supplied one; otherwise let
        # hr.formula.config.create() auto-generate a unique code from the name.
        if vals.get('code'):
            cvals['code'] = vals['code']
        cfg = Config.create(cvals)
        self._seed_template(cfg, vals.get('template') or 'blank')
        return {'ok': True, 'config_id': cfg.id, 'rule_count': len(cfg.rule_ids)}

    def _seed_template(self, cfg, key):
        """Populate an empty config from a starter template. Shared by the
        creation wizard and the cockpit 'Use Vietnam Standard' resume CTA."""
        if key == 'vn_standard':
            # Assign column letters explicitly. The model's position-based
            # compute is unreliable during batch create (o2m cache staleness
            # makes every new rule resolve to 'A'), so we provide the stored
            # value directly — it persists via the field's inverse and skips
            # the faulty compute, keeping A..J distinct for the constraint.
            vals_list = []
            for i, (code, name, ctype, formula, const) in enumerate(self.VN_STANDARD):
                vals_list.append({
                    'config_id': cfg.id, 'code': code, 'name': name,
                    'column_type': ctype, 'excel_formula': formula,
                    'constant_value': const, 'sequence': i + 1,
                    'column_letter': self._idx_letter(i),
                })
            self.env['hr.formula.rule'].create(vals_list)
            try:
                cfg.action_regenerate_formulas()
            except Exception as e:
                _logger.warning("Template formula regen failed: %s", e)
            # seed a sample so the live preview works immediately
            try:
                self.env['hr.formula.sample.data'].create({
                    'config_id': cfg.id, 'name': 'Sample — Standard',
                    'input_values_json': json.dumps({'BASIC': 15000000}),
                })
            except Exception as e:
                _logger.warning("Template sample seed failed: %s", e)

    @api.model
    def apply_starter(self, config_id, key):
        """Apply a starter template to an EXISTING empty config (cockpit
        'finish setup' resume). Guarded so it never duplicates rules."""
        cfg = self.env['hr.formula.config'].browse(int(config_id))
        if not cfg.exists():
            return {'ok': False, 'error': 'not_found'}
        if cfg.rule_ids:
            return {'ok': False, 'error': 'not_empty'}
        self._seed_template(cfg, key or 'vn_standard')
        return {'ok': True, 'config_id': cfg.id, 'rule_count': len(cfg.rule_ids)}

    @api.model
    def delete_config(self, config_id):
        """Discard a (draft) config from the cockpit."""
        cfg = self.env['hr.formula.config'].browse(int(config_id))
        if cfg.exists():
            cfg.unlink()
        return {'ok': True}
