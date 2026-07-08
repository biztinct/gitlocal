# -*- coding: utf-8 -*-
import json
import logging
import re
from collections import defaultdict

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Config parameters (Settings > Technical > Parameters). Empty api_key => PayAI
# uses the built-in deterministic mapper. base_url can point at ANY
# OpenAI-compatible endpoint (OpenAI, Ollama, vLLM, LM Studio, OpenRouter…).
LLM_BASE_URL = 'pb_formula_studio.llm_base_url'
LLM_API_KEY = 'pb_formula_studio.llm_api_key'
LLM_MODEL = 'pb_formula_studio.llm_model'
DEFAULT_BASE_URL = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-4o-mini'


class LLMUnavailable(Exception):
    """Raised by _llm_chat when the LLM cannot be reached — no API key, no
    `requests`, timeout, non-200, or invalid JSON. Callers catch this to fall
    back to deterministic behaviour."""


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
    def _col_num(self, col):
        n = 0
        for ch in (col or '').upper():
            v = ord(ch) - 64
            if v < 1 or v > 26:
                return 0
            n = n * 26 + v
        return n

    @api.model
    def _num_to_col(self, n):
        """Inverse of _col_num: 1 -> 'A', 27 -> 'AA'."""
        s = ''
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    @api.model
    def _expand_refs(self, formula, by_col):
        """Set of referenced columns in a formula, expanding A#:B# ranges to
        every existing member column (matches the engine's range expansion)."""
        f = formula or ''
        out = set()
        for s, e in re.findall(r'([A-Za-z]+)\d+:([A-Za-z]+)\d+', f):
            lo, hi = sorted((self._col_num(s), self._col_num(e)))
            for col in by_col:
                if lo <= self._col_num(col) <= hi:
                    out.add(col)
        # plain refs (blank out ranges so endpoints aren't missed nor double-handled)
        rest = re.sub(r'([A-Za-z]+)\d+:([A-Za-z]+)\d+', ' ', f)
        for c in re.findall(r'([A-Za-z]+)\d+', rest):
            out.add(c.upper())
        return out

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

        # dependency maps (expand A#:B# ranges to every member column)
        depends = {}
        used_by = {}
        for r in rules:
            refs = self._expand_refs(r.excel_formula, by_col) if r.column_type == 'formula' else set()
            depends[r.id] = [by_col[c].name for c in refs if c in by_col]
            for c in refs:
                rr = by_col.get(c)
                if rr:
                    used_by.setdefault(rr.id, []).append(r.name)

        components = []
        for r in rules:
            components.append({
                'id': r.id,
                'col': r.column_letter or '?',
                'code': r.code or '',
                # Multilingual: prefer the translatable linked salary rule's label
                # (resolves to the reader's language); fall back to the rule name.
                'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or '(unnamed)',
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
                'appears_on_payslip': bool(r.appears_on_payslip),
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
            'field_meta': self._field_meta(),
            'can_edit': self._can_edit(),
            'scenarios': [self._scenario_payload(s) for s in self.env['hr.formula.scenario']
                          .search([('config_id', '=', config.id)])],
            'rate_tables': [self._rate_table_payload(t) for t in
                            self.env['hr.formula.rate.table'].search([('config_id', '=', config.id)])],
        }

    # ------------------------------------------------------------------
    # Formula Intelligence v1 (deterministic dependency graph)
    # ------------------------------------------------------------------
    @api.model
    def _normalized_dep_cols(self, rules):
        """Normalize each rule's ``formula_dependencies`` to the column letters
        of real rules in the config.

        ``formula_dependencies`` (see hr.formula.rule._compute_dependencies) is a
        stored Char holding a comma-separated MIX of column letters (A, AA) AND
        component codes (BASIC, GROSS) plus incidental noise. We resolve every
        token exactly the way the engine's evaluator does — column_letter first,
        then code — and keep only tokens that land on a rule that lives in this
        config, so spurious tokens (function fragments, unknown codes) drop out.

        Returns ``{rule.id: set(column_letter, ...)}`` — the columns each formula
        rule depends on (data-flow *sources*).
        """
        by_col = {r.column_letter: r for r in rules if r.column_letter}
        by_code = {r.code: r for r in rules if r.code}
        deps = {}
        for r in rules:
            cols = set()
            raw = r.formula_dependencies or ''
            if r.column_type == 'formula' and raw:
                for tok in raw.split(','):
                    tok = tok.strip()
                    if not tok:
                        continue
                    dep = by_col.get(tok) or by_code.get(tok)
                    if dep and dep.column_letter:
                        cols.add(dep.column_letter)
            deps[r.id] = cols
        return deps

    @api.model
    def get_intelligence(self, config_id=None):
        """Deterministic dependency-graph payload for the Formula Intelligence
        panels (and the grid-highlight primitives in Feature 2).

        Shape::

            {nodes: [{id, code, col, name, category, appears_on_payslip, is_valid}],
             edges: [[from_col, to_col], ...],   # data-flow: source -> consumer
             execution_order: [col, ...],        # formula rules, dependencies first
             unused: [col, ...],
             cycles: [{cols, codes, human_explanation}, ...]}
        """
        config = self._pick_config(config_id)
        if not config:
            return {'empty': True, 'nodes': [], 'edges': [],
                    'execution_order': [], 'unused': [], 'cycles': []}

        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        deps = self._normalized_dep_cols(rules)
        col_to_code = {r.column_letter: (r.code or r.column_letter)
                       for r in rules if r.column_letter}

        nodes = [{
            'id': r.id,
            'code': r.code or '',
            'col': r.column_letter or '',
            'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or '(unnamed)',
            'category': r.category_id.name if r.category_id else (r.column_type or '').title(),
            'appears_on_payslip': bool(r.appears_on_payslip),
            'is_valid': bool(r.is_valid) and not r.has_evaluation_error,
        } for r in rules]

        # Edges point in data-flow direction: [dependency_col, consumer_col], so an
        # edge's source is evaluated before its target (matches execution_order).
        edge_set = set()
        for r in rules:
            if not r.column_letter:
                continue
            for dep_col in deps[r.id]:
                edge_set.add((dep_col, r.column_letter))
        edges = [[a, b] for a, b in edge_set]

        # ---- execution order: topological sort over formula rules only --------
        # (dependencies on inputs/constants never constrain ordering — they are
        # always ready — so we only count formula->formula edges, exactly the
        # relation the evaluator's Kahn sort walks.)
        formula_rules = [r for r in rules if r.column_type == 'formula' and r.column_letter]
        fcols = {r.column_letter for r in formula_rules}
        indeg = {}
        succ = defaultdict(list)
        for r in formula_rules:
            fdeps = {d for d in deps[r.id] if d in fcols and d != r.column_letter}
            indeg[r.column_letter] = len(fdeps)
            for d in fdeps:
                succ[d].append(r.column_letter)

        # deterministic: process ready nodes in column order
        queue = sorted((c for c, d in indeg.items() if d == 0), key=self._col_num)
        execution_order = []
        while queue:
            col = queue.pop(0)
            execution_order.append(col)
            newly_ready = []
            for nxt in succ.get(col, []):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    newly_ready.append(nxt)
            # keep the queue in column order so the result is stable
            for c in sorted(newly_ready, key=self._col_num):
                queue.append(c)
            queue.sort(key=self._col_num)
        # cycle members never reach in-degree 0 — append them so the order still
        # accounts for every formula rule (AC1: len == number of formula rules).
        if len(execution_order) != len(formula_rules):
            emitted = set(execution_order)
            for r in formula_rules:
                if r.column_letter not in emitted:
                    execution_order.append(r.column_letter)

        # ---- unused: nothing downstream depends on it AND not on the payslip ---
        # A column with dependents is "consumed" (this is what excludes an input
        # that feeds a formula), so the two conditions together mean truly dead.
        has_dependents = {src for src, _tgt in edge_set}
        unused = [r.column_letter for r in rules
                  if r.column_letter
                  and r.column_letter not in has_dependents
                  and not r.appears_on_payslip]

        # ---- cycles: DFS back-edge detection with full path recovery ----------
        adj = {r.column_letter: [d for d in deps[r.id] if d in fcols]
               for r in formula_rules}
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {c: WHITE for c in adj}
        cycles = []
        seen = set()

        def _dfs(u, stack):
            color[u] = GRAY
            stack.append(u)
            for v in adj.get(u, []):
                if color.get(v) == GRAY:
                    # back edge — the cycle is the stack slice from v to u
                    cyc = stack[stack.index(v):]
                    key = frozenset(cyc)
                    if key not in seen:
                        seen.add(key)
                        codes = [col_to_code.get(c, c) for c in cyc]
                        cycles.append({
                            'cols': cyc[:],
                            'codes': codes,
                            'human_explanation': _(
                                "Circular dependency: %s") % ' → '.join(codes + [codes[0]]),
                        })
                elif color.get(v) == WHITE:
                    _dfs(v, stack)
            stack.pop()
            color[u] = BLACK

        for c in sorted(adj, key=self._col_num):
            if color[c] == WHITE:
                _dfs(c, [])

        return {
            'empty': False,
            'nodes': nodes,
            'edges': edges,
            'execution_order': execution_order,
            'unused': unused,
            'cycles': cycles,
        }

    @api.model
    def _closure(self, start, adj):
        """Transitive closure of ``start`` over adjacency map ``adj`` (col -> set
        of neighbour cols), excluding ``start`` itself. Cycle-safe via seen-set."""
        seen = set()
        stack = list(adj.get(start, ()))
        while stack:
            c = stack.pop()
            if c in seen or c == start:
                continue
            seen.add(c)
            stack.extend(adj.get(c, ()))
        return seen

    @api.model
    def _config_employee_count(self, config):
        """Employees attached to this config's scheme: distinct employees on
        payslips computed with it (the truest 'who does this affect' measure),
        falling back to a division match so a not-yet-run config still reports."""
        Payslip = self.env['hr.payslip']
        if 'formula_config_id' in Payslip._fields:
            emps = Payslip.search([('formula_config_id', '=', config.id)]).employee_id
            if emps:
                return len(emps)
        Emp = self.env['hr.employee']
        div = getattr(config, 'pb_division', False)
        if div and 'pb_division' in Emp._fields:
            return Emp.search_count([('pb_division', '=', div)])
        if div and 'division' in Emp._fields:
            return Emp.search_count([('division', '=', div)])
        return 0

    @api.model
    def get_impact_analysis(self, rule_id):
        """Impact of one component: its transitive upstream (what feeds it),
        transitive downstream (what it feeds), the payslip-visible slice of that
        downstream, and how many employees the config touches.

        Shape::

            {rule: {id, col, code, name},
             upstream: [node, ...], downstream: [node, ...],
             payslip_visible: [node, ...], employee_count: int}

        where ``node = {id, col, code, name, appears_on_payslip}``.
        """
        Rule = self.env['hr.formula.rule']
        rule = Rule.browse(int(rule_id))
        empty = {'empty': True, 'rule': {}, 'upstream': [], 'downstream': [],
                 'payslip_visible': [], 'employee_count': 0}
        if not rule.exists() or not rule.column_letter:
            return empty

        config = rule.config_id
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        deps = self._normalized_dep_cols(rules)
        by_col = {r.column_letter: r for r in rules if r.column_letter}

        # depends_cols: col -> cols it consumes; dependents: col -> cols consuming it
        depends_cols = {}
        dependents = defaultdict(set)
        for r in rules:
            if not r.column_letter:
                continue
            dcols = deps.get(r.id, set())
            depends_cols[r.column_letter] = set(dcols)
            for d in dcols:
                dependents[d].add(r.column_letter)

        start = rule.column_letter
        up_cols = self._closure(start, depends_cols)
        down_cols = self._closure(start, dependents)

        def _node(col):
            r = by_col.get(col)
            if not r:
                return None
            return {
                'id': r.id,
                'col': col,
                'code': r.code or '',
                'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or '(unnamed)',
                'appears_on_payslip': bool(r.appears_on_payslip),
            }

        upstream = [n for n in (_node(c) for c in sorted(up_cols, key=self._col_num)) if n]
        downstream = [n for n in (_node(c) for c in sorted(down_cols, key=self._col_num)) if n]
        payslip_visible = [n for n in downstream if n['appears_on_payslip']]

        return {
            'empty': False,
            'rule': {
                'id': rule.id,
                'col': start,
                'code': rule.code or '',
                'name': (rule.salary_rule_id.name if rule.salary_rule_id else False) or rule.name or '(unnamed)',
            },
            'upstream': upstream,
            'downstream': downstream,
            'payslip_visible': payslip_visible,
            'employee_count': self._config_employee_count(config),
        }

    @api.model
    def _can_edit(self):
        """Edit/Delete/PayAI affordances are for Formula Managers/Admins (who hold
        write access). A read-only 'Formula User' gets them hidden — the ACL would
        block the write anyway. Fail open so a missing group never locks out admins."""
        try:
            u = self.env.user
            return bool(u.has_group('base.group_system')
                        or u.has_group('pb_hr_payroll_formula.group_formula_manager'))
        except Exception:
            return True

    @api.model
    def _field_meta(self):
        """Option lists for the inline component editor (loaded once)."""
        Rule = self.env['hr.formula.rule']

        def _sel(field):
            return [{'value': v, 'label': l}
                    for v, l in Rule._fields[field].selection]

        cats = self.env['hr.salary.rule.category'].search([], order='name')
        rules = self.env['hr.salary.rule'].search([], order='name', limit=400)
        connectors = (self.env['hr.integration.connector'].search([], order='name')
                      if 'hr.integration.connector' in self.env else self.env['hr.formula.config'].browse())
        return {
            'categories': [{'id': c.id, 'name': c.name} for c in cats],
            'salary_rules': [{'id': r.id, 'name': r.name, 'code': r.code or ''} for r in rules],
            'connectors': [{'id': c.id, 'name': c.name} for c in connectors],
            'column_types': _sel('column_type'),
            'number_formats': _sel('number_format'),
            'data_sources': _sel('data_source'),
            'text_aligns': _sel('text_align'),
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
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        by_code = {r.code: r.column_letter for r in rules}
        values = {}
        try:
            sample = self.env['hr.formula.sample.data'].browse(int(sample_id))
            if sample.exists():
                input_values = json.loads(sample.input_values_json or '{}')
                # Use the rule.evaluate() path (same evaluator real payslips and the
                # test workbench use) so IF / BRACKET / self._if formulas compute
                # correctly — the FormulaEvaluator fast path cannot handle those and
                # silently returns 0 (F11).
                values = sample._evaluate_rules_with_dependencies(input_values)
        except Exception as e:
            _logger.warning("Studio compute failed: %s", e)
        # key by column letter for the UI
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
    # Fields the grid may bulk-edit across a column selection. Everything else is
    # rejected so a stray key can never mass-mutate formulas/codes/types.
    _BULK_FIELDS = {'category_id', 'number_format', 'appears_on_payslip', 'is_visible_in_grid'}

    @api.model
    def bulk_update_components(self, rule_ids, vals):
        """Apply whitelisted field changes to many components in ONE write.
        Non-whitelisted keys raise a UserError before anything is written, so a
        rejected call never leaves a partial update."""
        bad = set((vals or {}).keys()) - self._BULK_FIELDS
        if bad:
            raise UserError(_("These fields cannot be bulk-edited: %s") % ', '.join(sorted(bad)))
        rules = self.env['hr.formula.rule'].browse([int(i) for i in (rule_ids or [])]).exists()
        if not rules:
            return {'ok': False, 'msg': _("No components selected")}
        clean = {k: v for k, v in (vals or {}).items() if k in self._BULK_FIELDS}
        if clean:
            # F7: one 'bulk' version row per changed rule (write override loops self)
            rules.with_context(formula_version_reason='bulk').write(clean)
        return {'ok': True, 'updated': len(rules)}

    @api.model
    def _translate_formula_horizontal(self, formula, offset):
        """Shift every COLUMN-relative reference in ``formula`` by ``offset``
        columns (fill-right). ``$``-column-absolute refs (e.g. $D2) are left
        untouched; the row part (and any $ on it) is preserved verbatim."""
        if not offset:
            return formula

        def repl(m):
            col_dollar, col, rest = m.group(1), m.group(2), m.group(3)
            if col_dollar == '$':
                return m.group(0)                 # absolute column — unchanged
            n = self._col_num(col) + offset
            if n < 1:
                return m.group(0)                 # would fall off the left edge
            return col_dollar + self._num_to_col(n) + rest

        # (col-$)(letters)(row-$? digits) — matches D2, $D2, D$2, $D$2, AA11 …
        return re.sub(r'(\$?)([A-Za-z]+)(\$?\d+)', repl, formula)

    @api.model
    def translate_formula(self, rule_id, target_column_letters):
        """Drag-fill preview: translate the source rule's formula to each target
        column. Returns ``[{col, proposed_formula, valid}]`` — nothing is written."""
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists() or rule.column_type != 'formula':
            return []
        src_num = self._col_num(rule.column_letter)
        formula = rule.excel_formula or ''
        config = rule.config_id
        by_col = {r.column_letter: r for r in config.rule_ids if r.column_letter}
        out = []
        for tgt in (target_column_letters or []):
            tgt = (tgt or '').upper()
            proposed = self._translate_formula_horizontal(formula, self._col_num(tgt) - src_num)
            refs = self._expand_refs(proposed, by_col)
            target_rule = by_col.get(tgt)
            valid = (all(c in by_col for c in refs)
                     and bool(target_rule) and target_rule.column_type == 'formula')
            out.append({'col': tgt, 'proposed_formula': proposed, 'valid': valid})
        return out

    @api.model
    def bulk_save_formulas(self, items):
        """Persist several formulas at once (drag-fill commit). ``items`` =
        ``[{rule_id, formula}, ...]``."""
        Rule = self.env['hr.formula.rule']
        saved = 0
        for it in (items or []):
            rule = Rule.browse(int(it.get('rule_id')))
            if not rule.exists() or rule.column_type != 'formula':
                continue
            config = rule.config_id
            column_map = {r.column_letter: r.code for r in config.rule_ids if r.column_letter}
            # F7: drag-fill commits N formulas — each its own 'fill' version row
            rule = rule.with_context(formula_version_reason='fill')
            try:
                rule.excel_formula = it.get('formula') or ''
                rule.python_formula = rule._convert_excel_to_python(rule.excel_formula, column_map)
                rule.is_valid = True
                rule.validation_message = ''
                saved += 1
            except Exception as e:
                _logger.debug("bulk_save_formulas skip %s: %s", rule.id, e)
        return {'ok': True, 'saved': saved}

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

    # ---- inline component editor -------------------------------------
    # Editable fields the inline editor may write. Computed/auto fields
    # (column_letter, python_formula, formula_dependencies, has_circular_ref)
    # and import-tracking readonly fields are deliberately excluded.
    _EDIT_FIELDS = (
        'name', 'code', 'column_type', 'sequence', 'category_id', 'salary_rule_id',
        'constant_value', 'data_source_field', 'default_value',
        'data_source', 'integration_connector_id', 'source_field_mapping',
        'number_format', 'decimal_places', 'column_width', 'text_align',
        'appears_on_payslip', 'is_visible_in_grid', 'report_visible',
        'is_required', 'is_editable', 'is_contract_component', 'requires_new_contract',
    )
    _EDIT_M2O = ('category_id', 'salary_rule_id', 'integration_connector_id')

    @api.model
    def get_component_edit(self, rule_id):
        """Full editable + readonly-diagnostic snapshot for one component."""
        r = self.env['hr.formula.rule'].browse(int(rule_id))
        if not r.exists():
            return {'ok': False}
        return {
            'ok': True,
            'id': r.id,
            'column_letter': r.column_letter or '',
            'name': r.name or '',
            'code': r.code or '',
            'column_type': r.column_type or 'formula',
            'sequence': r.sequence or 0,
            'category_id': r.category_id.id or False,
            'salary_rule_id': r.salary_rule_id.id or False,
            'excel_formula': r.excel_formula or '',
            'constant_value': r.constant_value or 0.0,
            'data_source_field': r.data_source_field or '',
            'default_value': r.default_value or 0.0,
            'data_source': r.data_source or 'excel',
            'integration_connector_id': r.integration_connector_id.id or False,
            'source_field_mapping': r.source_field_mapping or '',
            'number_format': r.number_format or 'number',
            'decimal_places': r.decimal_places or 0,
            'column_width': r.column_width or 120,
            'text_align': r.text_align or 'right',
            'appears_on_payslip': bool(r.appears_on_payslip),
            'is_visible_in_grid': bool(r.is_visible_in_grid),
            'report_visible': bool(r.report_visible),
            'is_required': bool(r.is_required),
            'is_editable': bool(r.is_editable),
            'is_contract_component': bool(r.is_contract_component),
            'requires_new_contract': bool(r.requires_new_contract),
            # readonly diagnostics
            'python_formula': r.python_formula or '',
            'formula_dependencies': r.formula_dependencies or '',
            'has_circular_ref': bool(r.has_circular_ref),
            'validation_message': r.validation_message or '',
        }

    @api.model
    def save_component(self, rule_id, vals):
        """Comprehensive save for the inline editor. Returns refreshed validity."""
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'msg': 'Component not found'}
        vals = vals or {}
        write_vals = {}
        for k in self._EDIT_FIELDS:
            if k not in vals:
                continue
            v = vals[k]
            if k in self._EDIT_M2O:
                v = int(v) if v else False
            write_vals[k] = v
        # proactive duplicate-code guard (the DB unique constraint is not
        # reliably enforced on this table, so check here).
        if write_vals.get('code'):
            dup = rule.config_id.rule_ids.filtered(
                lambda r: r.id != rule.id and (r.code or '') == write_vals['code'])
            if dup:
                return {'ok': False,
                        'msg': 'Code "%s" is already used by column %s.'
                               % (write_vals['code'], dup[0].column_letter or '?')}
        # excel_formula handled separately so we can convert + validate
        new_formula = vals.get('excel_formula')
        # F7: this method may write metadata AND the formula in two steps — a
        # shared 'seen' set collapses both into ONE version row for the rule.
        rule = rule.with_context(formula_version_reason='edit',
                                 formula_version_seen=set())
        try:
            if write_vals:
                rule.write(write_vals)
            ctype = write_vals.get('column_type', rule.column_type)
            if new_formula is not None:
                rule.excel_formula = new_formula
            if ctype == 'formula':
                column_map = {r.column_letter: r.code
                              for r in rule.config_id.rule_ids if r.column_letter}
                rule.python_formula = rule._convert_excel_to_python(rule.excel_formula or '', column_map)
                ok, msg = self._check_formula(rule.config_id, rule.excel_formula or '', exclude_id=rule.id)
                rule.is_valid = ok
                rule.validation_message = '' if ok else msg
        except Exception as e:
            return {'ok': False, 'msg': str(e)}
        return {'ok': True, 'is_valid': bool(rule.is_valid),
                'validation_message': rule.validation_message or ''}

    # =====================================================================
    #  F7 — Formula version history (rail + token diff + restore)
    # =====================================================================
    @api.model
    def _tokenize_text(self, formula):
        """Lex a raw Excel formula string into a flat token list for diffing.
        Broader than `_tokenize` (which builds chips for a live rule): this also
        captures bare function names (ROUND/VLOOKUP), commas and comparison
        operators, so a diff reads sensibly across structural rewrites."""
        formula = (formula or '').lstrip('=').strip()
        if not formula:
            return []
        return re.findall(r'[A-Za-z_]+\$?\d*|\$?\d+\.?\d*|[+\-*/()%,^&<>=!:]', formula)

    def _version_row_payload(self, ver):
        try:
            snap = json.loads(ver.snapshot_json or '{}')
        except Exception:
            snap = {}
        return {
            'seq': ver.seq,
            'reason': ver.reason,
            'reason_label': dict(ver._fields['reason']._description_selection(self.env)).get(ver.reason, ver.reason),
            'note': ver.note or '',
            'user': ver.user_id.name or '',
            'date': fields.Datetime.to_string(ver.create_date) if ver.create_date else '',
            'excel_formula': ver.excel_formula or '',
            'snapshot': snap,
        }

    @api.model
    def get_rule_history(self, rule_id):
        """Full history for one rule: the live state as a synthetic 'current'
        node plus every stored version (newest first). Versions hold OUTGOING
        pre-edit states, so `current` is the head and each version is a past."""
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'versions': []}
        versions = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id)], order='seq desc')
        return {
            'ok': True,
            'rule_id': rule.id,
            'code': rule.code or '',
            'name': rule.name or '',
            'config_name': rule.config_id.display_name or rule.config_id.name or '',
            'current': {
                'seq': None,           # None == the live head
                'excel_formula': rule.excel_formula or '',
                'user': (rule.write_uid.name if rule.write_uid else ''),
                'date': fields.Datetime.to_string(rule.write_date) if rule.write_date else '',
                'snapshot': rule._version_snapshot(),
            },
            'versions': [self._version_row_payload(v) for v in versions],
        }

    def _version_formula(self, rule, seq):
        """Resolve a seq (int) or None (=live head) to its Excel formula text."""
        if seq in (None, False, 'current'):
            return rule.excel_formula or '', _('Current')
        ver = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id), ('seq', '=', int(seq))], limit=1)
        if not ver:
            return '', _('v%s') % seq
        return ver.excel_formula or '', _('v%s') % seq

    @api.model
    def diff_versions(self, rule_id, seq_a, seq_b):
        """Token-level diff between two versions (or a version and 'current').
        Returns runs of equal/insert/delete/replace for chip rendering. `seq_*`
        may be an int seq or null/'current' for the live head. A precedes B in
        reading order (A = older, B = newer)."""
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'runs': []}
        fa, la = self._version_formula(rule, seq_a)
        fb, lb = self._version_formula(rule, seq_b)
        runs = self._token_diff_runs(self._tokenize_text(fa), self._tokenize_text(fb))
        return {'ok': True, 'runs': runs, 'a_label': la, 'b_label': lb,
                'a_formula': fa, 'b_formula': fb}

    def _token_diff_runs(self, a, b):
        """LCS diff over two token lists → merged runs. Adjacent delete+insert
        collapse into a single 'replace' so `0.10 → 0.12` reads as one change."""
        n, m = len(a), len(b)
        # LCS length table
        dp = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n - 1, -1, -1):
            for j in range(m - 1, -1, -1):
                dp[i][j] = (dp[i + 1][j + 1] + 1) if a[i] == b[j] \
                    else max(dp[i + 1][j], dp[i][j + 1])
        # walk to emit ops
        ops = []
        i = j = 0
        while i < n and j < m:
            if a[i] == b[j]:
                ops.append(('equal', a[i])); i += 1; j += 1
            elif dp[i + 1][j] >= dp[i][j + 1]:
                ops.append(('delete', a[i])); i += 1
            else:
                ops.append(('insert', b[j])); j += 1
        while i < n:
            ops.append(('delete', a[i])); i += 1
        while j < m:
            ops.append(('insert', b[j])); j += 1
        # coalesce consecutive ops of the same kind, then fuse delete+insert
        merged = []
        for op, tok in ops:
            if merged and merged[-1]['op'] == op and 'tokens' in merged[-1]:
                merged[-1]['tokens'].append(tok)
            else:
                merged.append({'op': op, 'tokens': [tok]})
        runs = []
        k = 0
        while k < len(merged):
            cur = merged[k]
            nxt = merged[k + 1] if k + 1 < len(merged) else None
            if cur['op'] == 'delete' and nxt and nxt['op'] == 'insert':
                runs.append({'op': 'replace', 'old': cur['tokens'], 'new': nxt['tokens']})
                k += 2
            elif cur['op'] == 'insert' and nxt and nxt['op'] == 'delete':
                runs.append({'op': 'replace', 'old': nxt['tokens'], 'new': cur['tokens']})
                k += 2
            else:
                runs.append(cur)
                k += 1
        return runs

    @api.model
    def restore_version(self, rule_id, seq):
        """Write a past version's formula back onto the live rule. This is itself
        a versioned event (reason='restore'), so history is never rewritten —
        the current head is snapshotted before being overwritten."""
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'msg': _('Component not found')}
        ver = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id), ('seq', '=', int(seq))], limit=1)
        if not ver:
            return {'ok': False, 'msg': _('Version not found')}
        target = ver.excel_formula or ''
        rule = rule.with_context(formula_version_reason='restore',
                                 formula_version_note=_('Restored v%s') % seq)
        try:
            rule.excel_formula = target
            if rule.column_type == 'formula':
                column_map = {r.column_letter: r.code
                              for r in rule.config_id.rule_ids if r.column_letter}
                rule.python_formula = rule._convert_excel_to_python(target, column_map)
                ok, msg = self._check_formula(rule.config_id, target, exclude_id=rule.id)
                rule.is_valid = ok
                rule.validation_message = '' if ok else msg
        except Exception as e:
            return {'ok': False, 'msg': str(e)}
        return {'ok': True, 'excel_formula': target,
                'is_valid': bool(rule.is_valid)}

    @api.model
    def get_config_milestones(self, config_id):
        """Milestones for a config, newest first, for the compare picker."""
        ms = self.env['hr.formula.config.milestone'].sudo().search(
            [('config_id', '=', int(config_id))], order='milestone_date desc')
        return [{
            'id': m.id, 'name': m.name,
            'date': fields.Datetime.to_string(m.milestone_date),
            'user': m.user_id.name or '',
        } for m in ms]

    def _formula_at(self, rule, when):
        """The rule's Excel formula in effect at datetime `when`. Version rows
        store OUTGOING states, so the value live at T is the earliest version
        captured at-or-after T; if none, nothing changed since T → current."""
        ver = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id), ('create_date', '>=', when)],
            order='create_date asc, seq asc', limit=1)
        return (ver.excel_formula if ver else rule.excel_formula) or ''

    @api.model
    def compare_to_milestone(self, config_id, milestone_id):
        """Diff a whole config against a milestone: only rules whose formula
        changed since the milestone, each with its token diff."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        milestone = self.env['hr.formula.config.milestone'].sudo().browse(int(milestone_id))
        if not config.exists() or not milestone.exists():
            return {'ok': False, 'changed': []}
        when = milestone.milestone_date
        changed = []
        for rule in config.rule_ids:
            old = self._formula_at(rule, when)
            cur = rule.excel_formula or ''
            if (old or '') == (cur or ''):
                continue
            changed.append({
                'rule_id': rule.id,
                'code': rule.code or '',
                'name': rule.name or '',
                'col': rule.column_letter or '',
                'old_formula': old,
                'cur_formula': cur,
                'runs': self._token_diff_runs(
                    self._tokenize_text(old), self._tokenize_text(cur)),
            })
        return {
            'ok': True,
            'milestone_name': milestone.name,
            'milestone_date': fields.Datetime.to_string(when),
            'changed_count': len(changed),
            'changed': changed,
        }

    # ==================================================================
    # F8 — Simulate-before-activate (thin facade over hr.formula.simulation)
    # ==================================================================
    @api.model
    def simulate_prepare(self, config_id, overrides=None, limit=None):
        """Create a simulation and return the payslip work-list to drive through
        it in chunks. ``overrides`` = {code: draft_excel_formula} previews a
        specific edit (baseline = current rules); no overrides = whole config vs
        the last actual payrun (D8.1)."""
        Sim = self.env['hr.formula.simulation']
        created = Sim.sim_create(config_id, overrides=overrides or {})
        if not created.get('ok'):
            return created
        prep = Sim.sim_prepare(created['sim_id'], limit=limit)
        prep.update({'ok': True, 'headline': created.get('headline'),
                     'overrides': created.get('overrides', 0)})
        return prep

    @api.model
    def simulate_batch(self, payload):
        """One chunk (~50 payslips). Idempotent-free (accumulates) — the client
        sends each slice of the prepare payslip_ids exactly once."""
        return self.env['hr.formula.simulation'].sim_batch(payload or {})

    @api.model
    def simulate_result(self, sim_id):
        """Finalize (mark done) and return the folded distribution."""
        return self.env['hr.formula.simulation'].sim_finalize(sim_id)

    @api.model
    def simulate_drop(self, sim_id):
        """Discard a simulation — leaves no residue (transient + no rule writes)."""
        sim = self.env['hr.formula.simulation'].browse(int(sim_id))
        sim.sim_drop()
        return {'ok': True}

    # ==================================================================
    # F14 — Scenario columns (what-if overlays on one component)
    # ==================================================================
    def _scenario_payload(self, sc):
        """One scenario as the grid consumes it (with live validity)."""
        ok, msg = self._check_formula(sc.config_id, sc.override_formula or '',
                                      exclude_id=sc.rule_id.id)
        return {
            'id': sc.id, 'rule_id': sc.rule_id.id,
            'code': sc.rule_id.code or '', 'col': sc.rule_id.column_letter or '',
            'name': sc.name or '', 'override_formula': sc.override_formula or '',
            'color': sc.color_key or 'violet',
            'valid': bool(ok), 'message': msg or '',
        }

    @api.model
    def list_scenarios(self, config_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'scenarios': []}
        scs = self.env['hr.formula.scenario'].search([('config_id', '=', config.id)])
        return {'scenarios': [self._scenario_payload(s) for s in scs]}

    @api.model
    def create_scenario(self, rule_id, name=None):
        """Duplicate a component as a scenario overlay, seeded with its current
        formula. NEVER touches the base rule (D14.1)."""
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'msg': _('Component not found')}
        if rule.column_type != 'formula':
            return {'ok': False, 'msg': _('Only formula components can be scenarioed')}
        Scenario = self.env['hr.formula.scenario']
        n = Scenario.search_count([('rule_id', '=', rule.id)])
        label = name or (_('Scenario %s') % chr(ord('A') + n))
        sc = Scenario.create({
            'config_id': rule.config_id.id, 'rule_id': rule.id,
            'name': label, 'override_formula': rule.excel_formula or '',
            'sequence': 10 + n, 'color_key': Scenario.next_color(rule.id),
        })
        return {'ok': True, 'scenario': self._scenario_payload(sc)}

    @api.model
    def save_scenario_formula(self, scenario_id, formula):
        sc = self.env['hr.formula.scenario'].browse(int(scenario_id))
        if not sc.exists():
            return {'ok': False}
        sc.override_formula = formula or ''
        ok, msg = self._check_formula(sc.config_id, formula or '', exclude_id=sc.rule_id.id)
        return {'ok': True, 'valid': bool(ok), 'message': msg or ''}

    @api.model
    def eval_scenario(self, scenario_id, sample_id):
        """Overlay-evaluate the scenario against a sample's inputs (F8 engine).
        Returns the base and scenario value for the component + the take-home
        (net) ripple, all for that one sample. No rule is written (D14.1)."""
        from odoo.addons.pb_hr_payroll_formula.models.formula_simulation import (
            _evaluate_config_overlay)
        sc = self.env['hr.formula.scenario'].browse(int(scenario_id))
        if not sc.exists():
            return {'ok': False}
        config, rule = sc.config_id, sc.rule_id
        try:
            sample = self.env['hr.formula.sample.data'].browse(int(sample_id))
            inputs = json.loads(sample.input_values_json or '{}') if sample.exists() else {}
        except Exception:
            inputs = {}
        base = _evaluate_config_overlay(config, inputs, None)
        cand = _evaluate_config_overlay(config, inputs, {rule.code: sc.override_formula or ''})
        # net/take-home ripple, if the config exposes one
        net_code = None
        for r in config.rule_ids:
            if (r.code or '').upper().replace(' ', '') in (
                    'NET', 'NETPAY', 'NET_PAY', 'NETSALARY', 'TAKEHOME', 'TAKE_HOME'):
                net_code = r.code
                break

        def _num(d, k):
            try:
                return float(d.get(k) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        out = {
            'ok': True, 'col': rule.column_letter or '', 'code': rule.code or '',
            'base_value': _num(base, rule.code),
            'scenario_value': _num(cand, rule.code),
        }
        if net_code:
            out.update({
                'net_code': net_code,
                'net_base': _num(base, net_code),
                'net_scenario': _num(cand, net_code),
            })
        return out

    @api.model
    def promote_scenario(self, scenario_id):
        """Write the scenario's draft into the base rule (versioned, reason=edit)
        then delete the scenario. This is the ONLY path that mutates the rule."""
        sc = self.env['hr.formula.scenario'].browse(int(scenario_id))
        if not sc.exists():
            return {'ok': False}
        rule, config = sc.rule_id, sc.config_id
        formula = sc.override_formula or ''
        ok, msg = self._check_formula(config, formula, exclude_id=rule.id)
        if not ok:
            return {'ok': False, 'msg': msg or _('Scenario formula is invalid')}
        column_map = {r.column_letter: r.code for r in config.rule_ids if r.column_letter}
        rule.with_context(formula_version_reason='edit').write({
            'excel_formula': formula,
            'python_formula': rule._convert_excel_to_python(formula, column_map)
                if rule.column_type == 'formula' else rule.python_formula,
            'is_valid': True, 'validation_message': '',
        })
        sc.unlink()
        return {'ok': True, 'rule_id': rule.id, 'code': rule.code or '', 'formula': formula}

    @api.model
    def discard_scenario(self, scenario_id):
        sc = self.env['hr.formula.scenario'].browse(int(scenario_id))
        if sc.exists():
            sc.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # F13 — Problems rail + lint + rename-refactor
    # ------------------------------------------------------------------
    # Numeric literals worth flagging: big enough to be a "magic amount"
    # (row numbers, small multipliers like 2/12 are noise) and repeated across
    # formulas so extracting a constant actually removes duplication.
    _MAGIC_MIN = 1000.0
    _MAGIC_MIN_COUNT = 2

    @api.model
    def _strip_for_lint(self, formula):
        """Blank out string literals and cell references so only bare numeric
        literals (and operators/functions) remain — the row digits of A2/X2
        must never be mistaken for magic numbers."""
        f = formula or ''
        f = re.sub(r'"[^"]*"', ' ', f)              # string literals
        f = re.sub(r"'[^']*'", ' ', f)
        f = re.sub(r'\$?[A-Za-z]+\$?\d+', ' ', f)   # cell refs A2, $X$2, AA10
        f = re.sub(r'[A-Za-z_][A-Za-z0-9_]*', ' ', f)  # function names / bare codes
        return f

    @api.model
    def get_problems(self, config_id=None):
        """Aggregate everything wrong (or smelly) about a config into one ranked
        list for the Problems rail. Pure metadata + regex — never computes a
        payslip.

        Shape::

            {ok, count, counts: {error, warning, hint},
             problems: [{key, kind, severity, title, detail, rule_id, col, code}]}
        """
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'count': 0,
                    'counts': {'error': 0, 'warning': 0, 'hint': 0}, 'problems': []}

        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        by_col = self._col_to_rule(rules)
        problems = []

        def _add(kind, severity, title, detail, rule=None, col=None):
            problems.append({
                'key': '%s:%s' % (kind, rule.id if rule else (col or len(problems))),
                'kind': kind,
                'severity': severity,
                'title': title,
                'detail': detail,
                'rule_id': rule.id if rule else False,
                'col': (rule.column_letter if rule else col) or '',
                'code': (rule.code if rule else '') or '',
            })

        # 1) invalid / empty formulas -------------------------------------
        for r in rules:
            if r.column_type != 'formula':
                continue
            if not (r.excel_formula or '').strip():
                _add('empty', 'warning',
                     _("%s has no formula") % (r.name or r.column_letter),
                     _("This calculated component is blank — it evaluates to nothing."),
                     rule=r)
            elif (not r.is_valid) or r.has_evaluation_error:
                msg = r.validation_message or r.last_evaluation_error or _("Formula does not evaluate.")
                _add('invalid', 'error',
                     _("%s (%s) is invalid") % (r.name or '', r.column_letter),
                     msg, rule=r)

        # 2) cycles + unused (reuse the deterministic dependency graph) -----
        intel = self.get_intelligence(config.id)
        for cy in intel.get('cycles', []):
            first = by_col.get((cy.get('cols') or [None])[0])
            _add('cycle', 'error', _("Circular dependency"),
                 cy.get('human_explanation') or '', rule=first,
                 col=(cy.get('cols') or [''])[0])
        for col in intel.get('unused', []):
            rr = by_col.get(col)
            if not rr:
                continue
            if rr.column_type == 'input':
                _add('unused', 'hint',
                     _("%s (%s) is never used") % (rr.name or '', col),
                     _("This input feeds no formula and is not shown on the payslip."),
                     rule=rr)
            else:
                _add('unused', 'warning',
                     _("%s (%s) is never used") % (rr.name or '', col),
                     _("Nothing depends on this component and it does not appear on the payslip."),
                     rule=rr)

        # 3) magic-number lint --------------------------------------------
        from collections import Counter
        counter = Counter()
        rules_for_lit = {}
        for r in rules:
            if r.column_type != 'formula' or not r.excel_formula:
                continue
            seen_here = set()
            for tok in re.findall(r'(?<![A-Za-z0-9._])\d+(?:\.\d+)?', self._strip_for_lint(r.excel_formula)):
                try:
                    val = float(tok)
                except ValueError:
                    continue
                if val >= self._MAGIC_MIN and tok not in seen_here:
                    seen_here.add(tok)
                    counter[tok] += 1
                    rules_for_lit.setdefault(tok, []).append(r)
        for tok, cnt in counter.items():
            if cnt >= self._MAGIC_MIN_COUNT:
                where = rules_for_lit[tok]
                cols = ', '.join(rr.column_letter for rr in where if rr.column_letter)
                _add('magic', 'hint',
                     _("Repeated number %s") % '{:,.0f}'.format(float(tok)),
                     _("Appears in %s formulas (%s) — consider extracting a named "
                       "constant so a rate change is a one-line edit.") % (cnt, cols),
                     rule=where[0])

        # 4) totals that are not shown on the payslip ----------------------
        for r in rules:
            if (r.column_type == 'formula' and _group_for(r) == 'Totals'
                    and not r.appears_on_payslip):
                _add('offpayslip', 'warning',
                     _("%s (%s) is a total but hidden") % (r.name or '', r.column_letter),
                     _("This looks like a total or net figure yet it is not shown on "
                       "the payslip. Employees will not see it."),
                     rule=r)

        order = {'error': 0, 'warning': 1, 'hint': 2}
        problems.sort(key=lambda p: (order.get(p['severity'], 9),
                                     self._col_num(p.get('col') or 'ZZ')))
        counts = {'error': 0, 'warning': 0, 'hint': 0}
        for p in problems:
            counts[p['severity']] = counts.get(p['severity'], 0) + 1
        return {'ok': True, 'count': len(problems), 'counts': counts,
                'problems': problems}

    @api.model
    def rename_component(self, rule_id, new_code):
        """Rename a component's CODE, rewriting any formula that references the
        old code as a bare token — in one transaction.

        Asymmetry (surfaced in the UI): formulas reference other components by
        their COLUMN LETTER, not their code, so renaming a code is normally
        metadata-only and every formula keeps evaluating identically. We still
        scan for the old code appearing as a whole-word token (some imported
        formulas carry code refs that the converter resolves) and rewrite those
        too, so the rename is safe in every case. Renaming column *letters* is
        deliberately not offered — letters are positional identity.
        """
        Rule = self.env['hr.formula.rule']
        rule = Rule.browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'msg': _("Component not found.")}
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to edit this configuration.")}

        old = (rule.code or '').strip()
        new = (new_code or '').strip().upper()
        if not new:
            return {'ok': False, 'msg': _("The code cannot be empty.")}
        # Formula-converter contract: codes must be plain identifiers, no
        # underscores/spaces (they mangle the Excel→Python conversion).
        if not re.match(r'^[A-Z][A-Z0-9]*$', new):
            return {'ok': False, 'msg': _("Use letters and digits only, starting with a letter "
                                          "(no spaces or underscores).")}
        if new == old:
            return {'ok': False, 'msg': _("That is already the code.")}
        config = rule.config_id
        clash = config.rule_ids.filtered(lambda x: x.id != rule.id and (x.code or '').upper() == new)
        if clash:
            return {'ok': False, 'msg': _("Another component (%s) already uses that code.") % clash[0].column_letter}

        # Rewrite formulas that mention the old code as a whole word. In
        # practice formulas reference components by COLUMN LETTER, never by
        # code (verified across real configs), so this is normally a no-op —
        # a metadata-only rename. It is a safety net for imported formulas that
        # carry genuine code refs. We deliberately skip it when the old code
        # coincides with a column letter used in the config: a bare token like
        # `=GM` is then a letter reference, not a code reference, and rewriting
        # it would corrupt the formula. In that (rare) case the rename stays
        # metadata-only — formulas keep evaluating identically either way.
        rewritten = []
        config_letters = {r.column_letter for r in config.rule_ids if r.column_letter}
        if old and old not in config_letters:
            pat = re.compile(r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(old))
            for r in config.rule_ids:
                if r.id == rule.id or r.column_type != 'formula' or not r.excel_formula:
                    continue
                if pat.search(r.excel_formula):
                    r.with_context(formula_version_reason='rename').write(
                        {'excel_formula': pat.sub(new, r.excel_formula)})
                    rewritten.append(r.column_letter or r.code)

        # Migrate code-keyed data so the rename is behaviour-preserving. Sample
        # test data stores input/expected/computed vectors keyed by CODE — for an
        # INPUT component the code is the dictionary key the engine reads, so
        # without this the renamed input would read as missing (→ 0) and cascade.
        migrated_samples = 0
        if old:
            for s in config.sample_data_ids:
                touched = False
                svals = {}
                for fname in ('input_values_json', 'expected_values_json', 'computed_values_json'):
                    raw = getattr(s, fname, False)
                    if not raw:
                        continue
                    try:
                        d = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(d, dict) and old in d and new not in d:
                        d[new] = d.pop(old)
                        svals[fname] = json.dumps(d)
                        touched = True
                if touched:
                    s.write(svals)
                    migrated_samples += 1

        rule.with_context(formula_version_reason='rename').write({'code': new})
        return {'ok': True, 'msg': _("Renamed %s → %s") % (old or '(blank)', new),
                'rewritten': rewritten, 'new_code': new,
                'migrated_samples': migrated_samples}

    # ------------------------------------------------------------------
    # F11 — Rate (bracket) tables
    # ------------------------------------------------------------------
    def _rate_table_payload(self, t):
        return {
            'id': t.id,
            'code': t.code or '',
            'name': t.name or '',
            'kind': t.kind or 'progressive',
            'note': t.note or '',
            'brackets': [{'id': b.id, 'lower': b.lower, 'rate': b.rate}
                         for b in t.line_ids.sorted(key=lambda b: b.lower)],
            'used_by': t._dependent_rules().mapped('column_letter'),
        }

    @api.model
    def list_rate_tables(self, config_id):
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'tables': []}
        tables = self.env['hr.formula.rate.table'].search([('config_id', '=', config.id)])
        return {'ok': True, 'tables': [self._rate_table_payload(t) for t in tables]}

    @api.model
    def save_rate_table(self, config_id, payload):
        """Create or update a rate table + its brackets in one call. Brackets are
        replaced wholesale from payload['brackets'] (list of {lower, rate})."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'msg': _("No configuration loaded.")}
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to edit this configuration.")}
        payload = payload or {}
        code = (payload.get('code') or '').strip().upper()
        if not re.match(r'^[A-Z][A-Z0-9]*$', code):
            return {'ok': False, 'msg': _("Table code must be letters and digits only, "
                                          "starting with a letter (no spaces or underscores).")}
        Table = self.env['hr.formula.rate.table']
        tid = payload.get('id')
        table = Table.browse(int(tid)) if tid else Table
        # uniqueness of code within config
        clash = Table.search([('config_id', '=', config.id), ('code', '=', code),
                              ('id', '!=', table.id or 0)], limit=1)
        if clash:
            return {'ok': False, 'msg': _("Another table already uses the code %s.") % code}
        vals = {'code': code, 'name': (payload.get('name') or code).strip(),
                'note': (payload.get('note') or '').strip(), 'config_id': config.id}
        if table:
            table.write(vals)
        else:
            table = Table.create(vals)
        # rebuild brackets
        rows = [b for b in (payload.get('brackets') or [])
                if b.get('rate') not in (None, '') or b.get('lower') not in (None, '')]
        table.line_ids.unlink()
        self.env['hr.formula.rate.bracket'].create([{
            'table_id': table.id,
            'lower': float(b.get('lower') or 0.0),
            'rate': float(b.get('rate') or 0.0),
        } for b in rows])
        return {'ok': True, 'table': self._rate_table_payload(table)}

    @api.model
    def delete_rate_table(self, table_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to edit this configuration.")}
        t = self.env['hr.formula.rate.table'].browse(int(table_id))
        used = t._dependent_rules() if t.exists() else self.env['hr.formula.rule']
        if used:
            return {'ok': False, 'msg': _("This table is used by %s formula(s): %s. "
                                          "Remove the BRACKET references first.")
                    % (len(used), ', '.join(used.mapped('column_letter')))}
        if t.exists():
            t.unlink()
        return {'ok': True}

    @api.model
    def eval_bracket(self, table_id, value):
        """Compute this table's progressive value at a sample income, plus the
        compiled Excel — for the editor's live preview."""
        t = self.env['hr.formula.rate.table'].browse(int(table_id))
        if not t.exists():
            return {'ok': False}
        try:
            v = float(value or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        brackets = t.line_ids.sorted(key=lambda b: b.lower)
        result = 0.0
        lowers = [b.lower for b in brackets]
        rates = [b.rate for b in brackets]
        base = 0.0
        for i, b in enumerate(brackets):
            upper = lowers[i + 1] if i + 1 < len(brackets) else None
            if v > b.lower:
                top = v if upper is None else min(v, upper)
                result = base + rates[i] * (top - b.lower)
            base += rates[i] * ((upper - b.lower) if upper is not None else 0.0)
        return {'ok': True, 'value': v, 'result': max(0.0, result),
                'compiled': t.compile_excel('x')}

    @api.model
    def _check_formula(self, config, formula, exclude_id=None):
        """Validate a formula string against a config's columns. -> (ok, message)."""
        from odoo.addons.pb_hr_payroll_formula.formula_engine import FormulaValidator
        cols = {r.column_letter: r.code for r in config.rule_ids
                if r.column_letter and r.id != exclude_id}
        try:
            # F11 — expand BRACKET(code, value) first so the validator sees the
            # compiled nested-IF (BRACKET is not one of its known functions).
            expanded = self.env['hr.formula.rate.table'].expand_brackets(formula or '', config)
            return FormulaValidator().validate_formula(expanded, cols)
        except Exception as e:  # pragma: no cover
            return False, str(e)

    @api.model
    def validate_formula_live(self, config_id, formula, exclude_rule_id=None):
        """Live (unsaved) validation for the editor's preview pill."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'valid': False, 'message': 'No configuration loaded.'}
        ok, msg = self._check_formula(config, formula, exclude_id=int(exclude_rule_id) if exclude_rule_id else None)
        return {'valid': bool(ok), 'message': msg or ''}

    @api.model
    def add_component(self, config_id, vals):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False}
        vals = vals or {}
        # unique code per config (the model enforces uniqueness; a 2nd plain
        # 'NEW' would otherwise raise) + next free column letter.
        existing_codes = set(config.rule_ids.mapped('code'))
        base = (vals.get('code') or 'NEW').upper().replace(' ', '_') or 'NEW'
        code, n = base, 1
        while code in existing_codes:
            n += 1
            code = '%s_%s' % (base, n)
        existing_letters = set(config.rule_ids.mapped('column_letter'))
        i = 0
        while self._idx_letter(i) in existing_letters:
            i += 1
        rule = self.env['hr.formula.rule'].create({
            'config_id': config.id,
            'name': vals.get('name') or 'New Component',
            'code': code,
            'column_type': vals.get('column_type') or 'formula',
            'excel_formula': vals.get('excel_formula') or '',
            'constant_value': vals.get('constant_value') or 0.0,
            'sequence': max(config.rule_ids.mapped('sequence') or [0]) + 1,
            'column_letter': self._idx_letter(i),
        })
        return {'ok': True, 'rule_id': rule.id}

    @api.model
    def delete_component(self, rule_id):
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if rule.exists():
            rule.unlink()
        return {'ok': True}

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
    # config settings surface (bespoke OWL editor for hr.formula.config)
    # ------------------------------------------------------------------
    # Trimmed to fields that actually drive behavior. Dropped from the UI (and
    # thus this payload): mid_cycle_* and the grid-display set + description are
    # vestigial / only used by the legacy excel_grid_widget, never the cockpit.
    _CFG_FIELDS = (
        'name', 'code', 'country_code', 'structure_id', 'cycle_type', 'connector_id',
        'use_color_coded_excel_import', 'payroll_journal_id', 'debit_account_id',
        'credit_account_id', 'company_id',
        'use_proration', 'proration_basis', 'proration_component_ids', 'proration_rounding',
        'use_auto_retro', 'retro_component_id',
    )
    _CFG_M2O = ('structure_id', 'connector_id', 'payroll_journal_id', 'debit_account_id',
                'credit_account_id', 'company_id', 'retro_component_id')
    _CFG_M2M = ('proration_component_ids',)

    @api.model
    def _config_status(self, c):
        return {
            'state': c.state,
            'validation_status': c.validation_status or 'pending',
            'last_validated': c.last_validated and str(c.last_validated) or '',
            'last_validated_by': c.last_validated_by.name or '',
            'currency': {'symbol': c.currency_id.symbol or '', 'name': c.currency_id.name or ''},
            'score': self._score(c),
            'has_errors': bool(c.has_errors),
            'error_details': c.error_details or '',
            'has_circular_refs': bool(c.has_circular_refs),
            'circular_ref_details': c.circular_ref_details or '',
            'validation_message': c.validation_message or '',
            'rule_count': c.rule_count,
            'formula_rule_count': c.formula_rule_count,
            'input_rule_count': c.input_rule_count,
            'sample_count': c.sample_count,
            'proration_count': c.proration_count,
            'retro_count': c.retro_count,
            'carryover_count': c.carryover_count,
        }

    @api.model
    def _config_meta(self, c):
        Cfg = self.env['hr.formula.config']

        def _sel(field):
            return [{'value': v, 'label': l} for v, l in Cfg._fields[field].selection]

        comp = lambda model, **kw: [{'id': r.id, 'name': r.display_name}
                                    for r in self.env[model].search([], **kw)]
        connectors = (comp('hr.integration.connector', order='name')
                      if 'hr.integration.connector' in self.env else [])
        accts = self.env['account.account'].search(
            [('company_ids', 'in', c.company_id.ids)] if 'company_ids' in self.env['account.account']._fields
            else [], order='code', limit=400)
        journals = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', c.company_id.id)], order='name')
        return {
            'structures': comp('hr.payroll.structure', order='name'),
            'connectors': connectors,
            'journals': [{'id': j.id, 'name': j.name} for j in journals],
            'accounts': [{'id': a.id, 'name': '%s %s' % (a.code or '', a.name or '')} for a in accts],
            'companies': comp('res.company', order='name'),
            'components': [{'id': r.id, 'col': r.column_letter or '?', 'code': r.code or '', 'name': r.name or ''}
                           for r in c.rule_ids.sorted(key=lambda r: r.sequence)],
            'country_codes': _sel('country_code'),
            'cycle_types': _sel('cycle_type'),
            'proration_bases': _sel('proration_basis'),
            'multi_company': len(self.env['res.company'].search([])) > 1,
        }

    @api.model
    def get_config_settings(self, config_id):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        values = {}
        for f in self._CFG_FIELDS:
            if f in self._CFG_M2O:
                values[f] = c[f].id or False
            elif f in self._CFG_M2M:
                values[f] = c[f].ids
            else:
                values[f] = c[f] if c[f] is not False else False
        samples = [{'id': s.id, 'name': s.name, 'source_type': s.source_type or '',
                    'status': s.validation_status or '', 'discrepancy_count': s.discrepancy_count,
                    'last_computed': s.last_computed and str(s.last_computed) or ''}
                   for s in c.sample_data_ids]
        results = [{'sample': r.sample_id.name or '', 'rule_code': r.rule_code or '',
                    'expected': r.expected_value, 'computed': r.computed_value,
                    'difference': r.difference, 'status': r.status or '',
                    'error': r.error_message or ''}
                   for r in c.test_result_ids]
        return {
            'ok': True,
            'values': values,
            'status': self._config_status(c),
            'meta': self._config_meta(c),
            'samples': samples,
            'results': results,
        }

    @api.model
    def save_config_settings(self, config_id, vals):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': 'Configuration not found'}
        vals = vals or {}
        write_vals = {}
        for k in self._CFG_FIELDS:
            if k not in vals:
                continue
            v = vals[k]
            if k in self._CFG_M2O:
                write_vals[k] = int(v) if v else False
            elif k in self._CFG_M2M:
                write_vals[k] = [(6, 0, [int(x) for x in (v or [])])]
            else:
                write_vals[k] = v
        try:
            if write_vals:
                c.write(write_vals)
        except Exception as e:
            return {'ok': False, 'msg': str(e).splitlines()[0] if str(e) else 'Could not save.'}
        return {'ok': True, 'status': self._config_status(c)}

    @api.model
    def _cfg_run(self, config_id, method):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': 'Configuration not found'}
        notif = ''
        try:
            res = getattr(c, method)()
            if isinstance(res, dict) and res.get('params'):
                notif = res['params'].get('message') or ''
        except Exception as e:
            return {'ok': False, 'msg': str(e).splitlines()[0] if str(e) else 'Action failed.',
                    'status': self._config_status(c)}
        return {'ok': True, 'notif': notif, 'status': self._config_status(c)}

    @api.model
    def cfg_start_testing(self, config_id):
        return self._cfg_run(config_id, 'action_start_testing')

    @api.model
    def cfg_validate(self, config_id):
        return self._cfg_run(config_id, 'action_validate')

    @api.model
    def cfg_activate(self, config_id):
        return self._cfg_run(config_id, 'action_activate')

    @api.model
    def cfg_set_draft(self, config_id):
        return self._cfg_run(config_id, 'action_set_draft')

    @api.model
    def cfg_archive(self, config_id):
        return self._cfg_run(config_id, 'action_archive')

    @api.model
    def cfg_regenerate_formulas(self, config_id):
        return self._cfg_run(config_id, 'action_regenerate_formulas')

    @api.model
    def cfg_generate_sample_data(self, config_id):
        """One-click synthetic sample: build *realistic* random inputs (same
        generator as the Test "Generate" button — NOT the rules' zero defaults),
        compute current outputs, store them as an expected baseline so the Live
        Preview AND Run Tests are immediately meaningful (no wizard dialog)."""
        from odoo.addons.pb_hr_payroll_formula.formula_engine import FormulaEvaluator
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': 'Configuration not found'}
        rules = c.rule_ids.sorted(key=lambda r: r.sequence)
        wiz = self.env['hr.formula.sample.data.wizard'].create({
            'config_id': c.id, 'source': 'random',
            'sample_count': 1, 'min_salary': 5000000.0, 'max_salary': 50000000.0,
        })
        inputs = {}
        for r in rules:
            if r.column_type == 'input' and r.code:
                inputs[r.code] = wiz._generate_random_value(r)
        try:
            computed = FormulaEvaluator().evaluate_all(rules, inputs)
            expected = {code: v for code, v in computed.items()}
        except Exception as e:
            _logger.warning("Sample generate compute failed: %s", e)
            expected = {}
        n = len(c.sample_data_ids) + 1
        try:
            self.env['hr.formula.sample.data'].create({
                'config_id': c.id,
                'name': 'Sample %s' % n,
                'source_type': 'manual',
                'input_values_json': json.dumps(inputs),
                'expected_values_json': json.dumps(expected),
            })
        except Exception as e:
            return {'ok': False, 'msg': str(e).splitlines()[0] if str(e) else 'Could not create sample.'}
        return {'ok': True, 'notif': 'Sample data generated',
                'settings': self.get_config_settings(config_id)}

    @api.model
    def cfg_run_tests(self, config_id):
        r = self._cfg_run(config_id, 'action_run_tests')
        if r.get('ok'):
            r['settings'] = self.get_config_settings(config_id)
        return r

    @api.model
    def cfg_import_excel(self, config_id):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        return {'ok': True, 'action': c.action_import_from_excel_multisheet()}

    # ------------------------------------------------------------------
    # Test & Validate workbench
    # ------------------------------------------------------------------
    def _sample_verdict(self, s):
        """Preview when no expected; else the model's validation_status."""
        if not (s.expected_values_json and s.expected_values_json not in ('{}', '')):
            return 'preview'
        return s.validation_status or 'pending'

    def _sample_row(self, s):
        return {
            'id': s.id, 'name': s.name or '(unnamed)',
            'source_type': s.source_type or 'manual',
            'verdict': self._sample_verdict(s),
            'has_expected': bool(s.expected_values_json and s.expected_values_json not in ('{}', '')),
            'discrepancy_count': s.discrepancy_count,
            'last_computed': s.last_computed and str(s.last_computed) or '',
        }

    @api.model
    def get_test_data(self, config_id):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        rules = c.rule_ids.sorted(key=lambda r: r.sequence)
        inputs = [{'code': r.code, 'col': r.column_letter or '?', 'name': r.name or '',
                   'default': r.default_value or 0.0}
                  for r in rules if r.column_type == 'input']
        return {
            'ok': True,
            'samples': [self._sample_row(s) for s in c.sample_data_ids],
            'input_components': inputs,
            'currency': c.currency_id.symbol if c.currency_id else '',
        }

    @api.model
    def get_sample_detail(self, sample_id):
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if not s.exists():
            return {'ok': False}
        return {
            'ok': True,
            'id': s.id, 'name': s.name or '',
            'source_type': s.source_type or 'manual',
            'verdict': self._sample_verdict(s),
            'has_expected': bool(s.expected_values_json and s.expected_values_json not in ('{}', '')),
            'rows': s.get_comparison_data(),
        }

    @api.model
    def save_sample_inputs(self, sample_id, inputs):
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if not s.exists():
            return {'ok': False}
        vals = json.loads(s.input_values_json or '{}')
        for k, v in (inputs or {}).items():
            try:
                vals[k] = float(v)
            except (TypeError, ValueError):
                vals[k] = v
        s.input_values_json = json.dumps(vals)  # triggers _compute_results
        return self.get_sample_detail(s.id)

    @api.model
    def rename_sample(self, sample_id, name):
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if s.exists() and name:
            s.name = name
        return {'ok': True}

    @api.model
    def add_manual_sample(self, config_id):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        inputs = {r.code: (r.default_value or 0.0)
                  for r in c.rule_ids if r.column_type == 'input' and r.code}
        n = len(c.sample_data_ids) + 1
        s = self.env['hr.formula.sample.data'].create({
            'config_id': c.id, 'name': 'Sample %s' % n, 'source_type': 'manual',
            'input_values_json': json.dumps(inputs),
        })
        return {'ok': True, 'sample_id': s.id, 'samples': [self._sample_row(x) for x in c.sample_data_ids]}

    @api.model
    def generate_random_samples(self, config_id, count=3, min_salary=5000000, max_salary=50000000):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        wiz = self.env['hr.formula.sample.data.wizard'].create({
            'config_id': c.id, 'source': 'random',
            'sample_count': int(count or 3),
            'min_salary': float(min_salary or 5000000),
            'max_salary': float(max_salary or 50000000),
        })
        try:
            for vals in wiz._generate_random():
                self.env['hr.formula.sample.data'].create(vals)
        except Exception as e:
            return {'ok': False, 'msg': str(e).splitlines()[0] if str(e) else 'Could not generate.'}
        return {'ok': True, 'samples': [self._sample_row(x) for x in c.sample_data_ids]}

    @api.model
    def export_test_template(self, config_id):
        """Build a blank .xlsx whose header row is the config's input component
        names (in column order). This is the exact format accepted by
        import_test_samples — fill rows under the headers and re-import."""
        import base64
        import io
        try:
            import openpyxl
        except Exception:
            return {'ok': False, 'msg': 'openpyxl is not available on the server.'}
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': 'Configuration not found'}
        inputs = [r for r in c.rule_ids.sorted(key=lambda r: r.sequence)
                  if r.column_type == 'input']
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Test Inputs'
        headers = [(r.name or r.code or r.column_letter or '') for r in inputs]
        ws.append(headers)
        for col_idx, _h in enumerate(headers, start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 22
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        code = (c.code or c.name or 'config').strip().replace(' ', '_')
        return {
            'ok': True,
            'file_b64': base64.b64encode(out.read()).decode(),
            'filename': '%s_test_template.xlsx' % code,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }

    @api.model
    def import_test_samples(self, config_id, file_b64, filename=None):
        """Read an uploaded .xlsx whose header row matches input component names
        and create one sample per data row (added alongside existing samples).
        Header→input is matched by name (case-insensitive) → code → letter."""
        import base64
        import io
        try:
            import openpyxl
        except Exception:
            return {'ok': False, 'msg': 'openpyxl is not available on the server.'}
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': 'Configuration not found'}
        try:
            raw = base64.b64decode(file_b64 or '')
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        except Exception as e:
            return {'ok': False, 'msg': 'Could not read the file: %s' % (str(e).splitlines()[0] if str(e) else 'invalid xlsx')}
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {'ok': False, 'msg': 'The spreadsheet is empty.'}
        header = [(str(h).strip() if h is not None else '') for h in rows[0]]

        # Build lookup: lower(name) / lower(code) / lower(letter) -> code
        inputs = [r for r in c.rule_ids.sorted(key=lambda r: r.sequence)
                  if r.column_type == 'input']
        lookup = {}
        for r in inputs:
            for key in (r.name, r.code, r.column_letter):
                if key:
                    lookup.setdefault(str(key).strip().lower(), r.code)
        # Map each spreadsheet column index -> input code (skip unknown columns)
        col_to_code = {}
        for idx, h in enumerate(header):
            code = lookup.get(h.lower())
            if code:
                col_to_code[idx] = code
        if not col_to_code:
            return {'ok': False, 'msg': 'No header matched an input component. Use the exported template.'}

        base_n = len(c.sample_data_ids)
        created = 0
        for r_i, row in enumerate(rows[1:], start=1):
            if row is None or all(v is None or v == '' for v in row):
                continue
            vals = {}
            for idx, code in col_to_code.items():
                v = row[idx] if idx < len(row) else None
                if v is None or v == '':
                    continue
                try:
                    vals[code] = float(v)
                except (TypeError, ValueError):
                    vals[code] = v
            created += 1
            self.env['hr.formula.sample.data'].create({
                'config_id': c.id,
                'name': 'Sample %s' % (base_n + created),
                'source_type': 'manual',
                'input_values_json': json.dumps(vals),
            })
        if not created:
            return {'ok': False, 'msg': 'No data rows found under the header.'}
        new_ids = c.sample_data_ids.sorted(key=lambda s: s.id)[-created:]
        return {
            'ok': True, 'count': created,
            'first_id': new_ids[0].id if new_ids else False,
            'samples': [self._sample_row(x) for x in c.sample_data_ids],
        }

    @api.model
    def snapshot_expected(self, sample_id):
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if not s.exists():
            return {'ok': False}
        s.expected_values_json = s.computed_values_json or '{}'
        return self.get_sample_detail(s.id)

    @api.model
    def clear_expected(self, sample_id):
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if not s.exists():
            return {'ok': False}
        s.expected_values_json = '{}'
        return self.get_sample_detail(s.id)

    @api.model
    def delete_sample(self, sample_id):
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        cid = s.config_id.id if s.exists() else False
        if s.exists():
            s.unlink()
        samples = []
        if cid:
            c = self.env['hr.formula.config'].browse(cid)
            samples = [self._sample_row(x) for x in c.sample_data_ids]
        return {'ok': True, 'samples': samples}

    @api.model
    def cfg_generate_wizard(self, config_id, source):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        action = c.action_generate_sample_data()
        action.setdefault('context', {})['default_source'] = source
        # client-side doAction needs an explicit views array (server action
        # only sets view_mode, which makes web's _preprocessAction crash on .map)
        action['views'] = [(False, 'form')]
        return {'ok': True, 'action': action}

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
    @api.model
    def _llm_chat(self, messages, json_mode=False):
        """One OpenAI-compatible chat call. Raises LLMUnavailable on a missing
        key, missing `requests`, timeout, non-200 or bad JSON — callers catch it
        for a deterministic fallback. Returns the assistant message text, or the
        parsed JSON object when json_mode=True.

        Missing key raises IMMEDIATELY, before any network call."""
        if requests is None:
            raise LLMUnavailable("HTTP client 'requests' is not available")
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = (ICP.get_param(LLM_API_KEY) or '').strip()
        if not api_key:
            raise LLMUnavailable("No LLM API key configured")   # no network call
        base_url = (ICP.get_param(LLM_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip('/')
        model = (ICP.get_param(LLM_MODEL) or DEFAULT_MODEL).strip()
        payload = {'model': model, 'messages': messages, 'temperature': 0}
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        try:
            resp = requests.post(
                base_url + '/chat/completions',
                headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'},
                json=payload, timeout=25)
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']
        except Exception as e:
            raise LLMUnavailable("LLM call failed: %s" % e)
        if json_mode:
            try:
                return json.loads(content)
            except Exception as e:
                raise LLMUnavailable("LLM returned invalid JSON: %s" % e)
        return content

    def _llm_propose(self, config, text, rules):
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
            data = self._llm_chat(
                [{'role': 'system', 'content': system},
                 {'role': 'user', 'content': user}],
                json_mode=True)
        except LLMUnavailable as e:
            _logger.info("PayAI LLM unavailable, falling back: %s", e)
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
    # Explain a formula (T5.2) — LLM with deterministic floor, EN/VI
    # ------------------------------------------------------------------
    @api.model
    def explain_formula_ai(self, rule_id, lang='en'):
        """Plain-language explanation of one component. Tries the LLM; on ANY
        failure returns the deterministic _explain output. Never raises to the
        client. Returns {'text', 'source': 'ai'|'deterministic'}."""
        lang = 'vi' if str(lang or '').lower().startswith('vi') else 'en'
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'text': '', 'source': 'deterministic'}
        by_col = self._col_to_rule(rule.config_id.rule_ids)
        floor = self._explain_localized(rule, by_col, lang)   # always computable
        try:
            text = (self._llm_chat(self._build_explain_prompt(rule, by_col, lang)) or '').strip()
            if text:
                return {'text': text, 'source': 'ai'}
        except LLMUnavailable:
            pass
        except Exception as e:                                # never leak a traceback
            _logger.info("explain_formula_ai fell back: %s", e)
        return {'text': floor, 'source': 'deterministic'}

    @api.model
    def _build_explain_prompt(self, rule, by_col, lang):
        toks = self._tokenize(rule, by_col)
        deps = []
        for t in toks:
            if t.get('kind') == 'ref' and t['text'] not in deps:
                deps.append(t['text'])
        lang_name = 'Vietnamese' if lang == 'vi' else 'English'
        system = ("You are PayAI, a payroll assistant. Explain what a salary component "
                  "computes in plain %s — 1-2 short sentences for a non-technical payroll "
                  "officer. No formulas, code or column letters." % lang_name)
        facts = {
            'component': rule.name or '',
            'category': rule.category_id.name if rule.category_id else (rule.column_type or ''),
            'excel_formula': rule.excel_formula or '',
            'depends_on': deps,
        }
        user = "Explain this component in %s:\n%s" % (lang_name, json.dumps(facts, ensure_ascii=False))
        return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]

    @api.model
    def _explain_localized(self, rule, by_col, lang):
        return self._explain_vi(rule, by_col) if lang == 'vi' else self._explain(rule, by_col)

    @api.model
    def _explain_vi(self, rule, by_col):
        if rule.column_type == 'input':
            return "Lấy từ hợp đồng của mỗi nhân viên hoặc từ dữ liệu nhập hàng tháng."
        if rule.column_type == 'constant':
            return "Một giá trị cố định áp dụng cho tất cả nhân viên."
        names = []
        for t in self._tokenize(rule, by_col):
            if t['kind'] == 'ref' and t['text'] not in names:
                names.append(t['text'])
        if names:
            tail = " và các thành phần khác." if len(names) > 6 else "."
            return "%s được tính từ %s%s" % (rule.name or '', ', '.join(names[:6]), tail)
        return "%s là một thành phần được tính toán." % (rule.name or '')

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
        """Delete a configuration from the cockpit (any state)."""
        cfg = self.env['hr.formula.config'].browse(int(config_id))
        if not cfg.exists():
            return {'ok': True}
        try:
            cfg.unlink()
        except Exception as e:
            # e.g. referenced by payslips / restrict FK
            return {'ok': False, 'msg': 'Could not delete: %s' % (str(e).splitlines()[0] if str(e) else 'it may be in use.')}
        return {'ok': True}


class SampleDataWizardStudio(models.TransientModel):
    """Let the Test workbench's restyled generator return to the cockpit
    instead of navigating to the stock 'created samples' list view."""
    _inherit = 'hr.formula.sample.data.wizard'

    def action_generate_and_close(self):
        self.action_generate_samples()
        return {'type': 'ir.actions.act_window_close'}
