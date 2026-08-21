# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import re
from collections import defaultdict

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

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

# W48 — number guard for LLM-polished narration (D-D2). Pure + unit-testable:
# every money-scale figure (>= _NARR_MONEY_FLOOR) in the rewritten text must
# exist in the compare fold's allowed set, else the rewrite invented a number
# and is rejected in favour of the deterministic text. Counts/dates/percentages
# (small numbers) are not policed — they are low-risk and hard to enumerate.
_NARR_MONEY_FLOOR = 1000
_NARR_NUM_RE = re.compile(r'-?\d[\d,]*(?:\.\d+)?')


def _narr_numbers_ok(text, allowed):
    """True unless the text contains a money-scale number absent from `allowed`
    (a set of rounded-abs integers). `allowed` should already hold every sum /
    delta / count from the fold."""
    for raw in _NARR_NUM_RE.findall(text or ''):
        s = raw.replace(',', '')
        try:
            n = round(abs(float(s)))
        except Exception:
            continue
        if n < _NARR_MONEY_FLOOR:
            continue                      # counts / dates / small pcts: not policed
        if n not in allowed:
            return False                  # an invented money figure
    return True


# Category grouping for the outline (by code/name heuristics)
_NET_CODES = {'NET', 'NETPAY', 'NET_PAY', 'NETSALARY', 'TAKEHOME', 'TAKE_HOME'}


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
    # validation_status (stored) → a coarse health score for the switcher rings,
    # so the config gallery stays a single cheap query (no per-config recompute).
    # A real validation verdict wins; when it's still 'pending' we fall back on the
    # lifecycle state so an active, working config doesn't read as 0/unhealthy.
    _VSTATUS_SCORE = {'passed': 96, 'warning': 70, 'failed': 34}
    _STATE_SCORE = {'active': 90, 'validated': 84, 'testing': 55, 'draft': 22, 'archived': 12}

    @api.model
    def _config_score(self, config):
        return (self._VSTATUS_SCORE.get(config.validation_status)
                or self._STATE_SCORE.get(config.state, 0))

    @api.model
    def get_config_list(self):
        configs = self.env['hr.formula.config'].search([], order='sequence, id desc')
        out = []
        for c in configs:
            out.append({
                'id': c.id,
                'name': c.name,
                'code': c.code or '',
                'country': c.country_code or '',
                'state': c.state,
                'rule_count': len(c.rule_ids),
                # --- richer fields for the Config Switcher gallery ---
                'currency': c.currency_id.name or '',
                'cycle_type': c.cycle_type or 'regular',
                'active': bool(c.active),
                'validation_status': c.validation_status or 'pending',
                'score': self._config_score(c),
                'sample_count': len(c.sample_data_ids),
                'is_branch': bool(c.parent_branch_id),
                'is_variant': bool(c.master_config_id),
                'is_master': bool(c.variant_ids),
                'updated': fields.Date.to_string(c.write_date) if c.write_date else '',
            })
        return out

    @api.model
    def _pick_config(self, config_id=None):
        Config = self.env['hr.formula.config']
        if config_id:
            c = Config.browse(int(config_id))
            if c.exists():
                return c
        # prefer an active config with rules, else newest with rules, else newest.
        # Order by sequence FIRST so a "featured" config (low sequence — e.g. the
        # demo's Retail division) lands by default instead of whatever has the
        # highest id (a 250-column scale-test would otherwise win). Ties fall back
        # to newest id — bit-identical to the old behaviour when no sequence is set.
        c = Config.search([('state', '=', 'active'), ('rule_ids', '!=', False)],
                          order='sequence, id desc', limit=1)
        if c:
            return c
        c = Config.search([('rule_ids', '!=', False)], order='sequence, id desc', limit=1)
        return c or Config.search([], order='sequence, id desc', limit=1)

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
        every existing member column (matches the engine's range expansion).
        String literals are masked first so '=IF(D2="X2",…)' never reports a
        phantom X reference (WP-L review: stage_paste false-rejected such
        formulas as 'Unknown column(s): X')."""
        f = re.sub(r'"[^"]*"', ' ', formula or '')
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

        # F15 — note badges per component (one query, tallied in Python)
        note_by_rule = defaultdict(lambda: {'count': 0, 'review_open': 0})
        for n in self.env['hr.formula.rule.note'].search([('config_id', '=', config.id)]):
            d = note_by_rule[n.rule_id.id]
            d['count'] += 1
            if n.is_review and not n.resolved:
                d['review_open'] += 1

        components = []
        for r in rules:
            components.append({
                'id': r.id,
                'col': r.column_letter or '?',
                'code': r.code or '',
                # F111: sequence = display order (letters are frozen identities);
                # category_id drives the grid's category band strip + grouping.
                'sequence': r.sequence or 0,
                'category_id': r.category_id.id or False,
                'note_count': note_by_rule[r.id]['count'],
                'review_open': note_by_rule[r.id]['review_open'],
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
                # B2 — branch lineage (drives the header chip + Branches overlay)
                'is_branch': bool(config.parent_branch_id),
                'parent_id': config.parent_branch_id.id or False,
                'parent_name': config.parent_branch_id.name or '',
                'branch_state': config.branch_state or 'open',
                'branch_count': len(config.child_branch_ids.filtered(
                    lambda b: b.branch_state == 'open')),
                # B5 — scheme-variant lineage (header chip + Variants overlay)
                'is_master': bool(config.variant_ids),
                'is_variant': bool(config.master_config_id),
                'master_id': config.master_config_id.id or False,
                'master_name': config.master_config_id.name or '',
                'variant_count': len(config.variant_ids),
                'override_count': len([c for c in (config.variant_override_codes or '').split(',') if c.strip()]),
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
    def _shift_rows(self, formula, to_row):
        """WP-L / S-L1 — rewrite every cell-ref ROW digit in ``formula`` to
        ``to_row`` (column letters + $ absolutes preserved). Thin wrapper over
        the pure engine helper so W41 (shift OUT: row 2 → sheet row N at export)
        and W17 (normalize IN: any row → 2 at paste) share ONE regex + literal
        mask — never two (S-I1 / D-J1). String literals are masked first."""
        from odoo.addons.pb_hr_payroll_formula.formula_engine import cell_refs
        return cell_refs.shift_rows(formula, to_row)

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

    def _run_tests_after_save(self, config, changed_codes=None):
        """W82 — re-run a config's sample tests once after a save operation and
        return the compact verdict for the studio's test chip. Never raises: a
        broken test run must not sink the save it rides on."""
        if not config or not config.exists():
            return {'has_tests': False, 'total': 0, 'passed': 0,
                    'failed': 0, 'pending': 0, 'failures': []}
        try:
            return config.run_sample_tests(changed_codes=changed_codes)
        except Exception as e:
            _logger.warning("run_sample_tests failed for config %s: %s", config.id, e)
            return {'has_tests': False, 'total': 0, 'passed': 0,
                    'failed': 0, 'pending': 0, 'failures': []}

    @api.model
    def bulk_save_formulas(self, items, reason='fill', note=False):
        """Persist several formulas at once. ``items`` = ``[{rule_id, formula}, ...]``.

        ``reason`` selects the F7 version-row reason for the whole batch — one of
        the batch-write reasons (``fill`` for drag-fill, ``bulk`` for find/replace,
        W14/TA.5). Any other value is coerced to ``fill`` so a bad caller can never
        mislabel history. ``note`` (e.g. ``find/replace: q → r``) is stamped on
        every version row. A shared ``formula_version_seen`` set keeps the batch to
        exactly N rows, one reason (C4), even though each rule is written twice
        (excel_formula is versioned, python_formula is not)."""
        reason = reason if reason in ('fill', 'bulk') else 'fill'
        Rule = self.env['hr.formula.rule']
        seen = set()
        saved = 0
        config = False
        changed_codes = []
        for it in (items or []):
            rule = Rule.browse(int(it.get('rule_id')))
            if not rule.exists() or rule.column_type != 'formula':
                continue
            config = rule.config_id
            column_map = {r.column_letter: r.code for r in config.rule_ids if r.column_letter}
            # F7: N formulas → N version rows, one reason, one shared seen-set (C4)
            ctx = {'formula_version_reason': reason, 'formula_version_seen': seen}
            if note:
                ctx['formula_version_note'] = note
            rule = rule.with_context(**ctx)
            try:
                rule.excel_formula = it.get('formula') or ''
                rule.python_formula = rule._convert_excel_to_python(rule.excel_formula, column_map)
                rule.is_valid = True
                rule.validation_message = ''
                saved += 1
                if rule.code:
                    changed_codes.append(rule.code)
            except Exception as e:
                _logger.debug("bulk_save_formulas skip %s: %s", rule.id, e)
        # W82: one test run for the whole batch (C4 one-batch rule), not per item.
        tests = self._run_tests_after_save(config, changed_codes)
        return {'ok': True, 'saved': saved, 'tests': tests}

    # ------------------------------------------------------------------
    # W17 smart paste — the ONE server ladder (D-L5): normalize + validate
    # ------------------------------------------------------------------
    @api.model
    def stage_paste(self, config_id, entries=None):
        """W17 (D-L5) — read-only. ``entries`` = ``[{col, text}]`` (a horizontal
        run mapped from the pasted clipboard). Returns
        ``{ok, entries:[{col, normalized, valid, msg}]}``. NOTHING is written; the
        client stages ``normalized`` as the ghost, so what you see is exactly what
        a later ``bulk_save_formulas`` commits — one ladder, no preview/commit
        divergence (the S-I1 live-proven bug class)."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False}
        by_col = {r.column_letter: r for r in config.rule_ids if r.column_letter}
        out = []
        for e in (entries or []):
            col = (e.get('col') or '').upper()
            text = (e.get('text') or '').strip()
            norm, valid, msg = self._normalize_paste_entry(col, text, config, by_col)
            out.append({'col': col, 'normalized': norm, 'valid': valid, 'msg': msg})
        return {'ok': True, 'entries': out}

    @api.model
    def _normalize_paste_entry(self, col, text, config, by_col):
        """Normalize + validate ONE pasted cell. Returns ``(normalized, valid,
        msg)``. Only base FORMULA columns are valid targets; a plain number is
        refused (constants live in their own row — v1 formulas-only); row digits
        are rewritten to the canonical row 2 (``B5*C5`` → ``B2*C2``, S-L1); then
        unknown column letters are named and the formula is run through the
        existing validate path (BRACKET-expanded)."""
        target = by_col.get(col)
        if not target or target.column_type != 'formula':
            return text, False, _("%s is not a formula column.") % (col or '?')
        if not text:
            return text, False, _("Empty cell.")
        # A plain number (no letters, no leading '=') — constants aren't pasted.
        if not text.startswith('=') and not re.search(r'[A-Za-z]', text):
            return text, False, _("Constants are edited in their own row.")
        # Normalize every row digit to the single grid formula row (row 2),
        # keeping the leading '=' (add one if the paste dropped it).
        norm = self._shift_rows(text, 2)
        if norm and not norm.startswith('='):
            norm = '=' + norm
        # Unknown letters → invalid, named (mirrors the drag-fill validity gate).
        refs = self._expand_refs(norm, by_col)
        unknown = sorted(c for c in refs if c not in by_col)
        if unknown:
            return norm, False, _("Unknown column(s): %s") % ', '.join(unknown)
        ok, vmsg = self._check_formula(config, norm, exclude_id=target.id)
        if not ok:
            return norm, False, vmsg or _("Invalid formula.")
        return norm, True, ''

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
        return {'ok': True, 'tests': self._run_tests_after_save(config, [rule.code])}

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
                'is_valid': bool(rule.is_valid),
                'tests': self._run_tests_after_save(rule.config_id, [rule.code])}

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
    # B3 — Release bundles + sign-off (a query over F7 versions)
    # ==================================================================
    def _last_milestone(self, config):
        return self.env['hr.formula.config.milestone'].sudo().search(
            [('config_id', '=', config.id)], order='milestone_date desc, id desc', limit=1)

    def _seal_milestone(self, config, name):
        """Record a milestone carrying the config's version high-water mark — the
        max ``hr.formula.rule.version`` id at seal time. This is the exact,
        collision-free boundary for 'changed since this milestone' (W86): unlike
        ``milestone_date`` (second-precision, so it can't be separated from edits
        sealed in the same second) the id boundary is unambiguous even when the
        seal and its edits share one transaction — the one-action-rollback case."""
        Ver = self.env['hr.formula.rule.version'].sudo()
        last = Ver.search([('config_id', '=', config.id)], order='id desc', limit=1)
        return self.env['hr.formula.config.milestone'].sudo().create({
            'config_id': config.id, 'name': name,
            'milestone_date': fields.Datetime.now(),
            'version_hwm': last.id if last else 0})

    def _config_version_hwm(self, config):
        """The current max version id for a config (the 'now' boundary)."""
        last = self.env['hr.formula.rule.version'].sudo().search(
            [('config_id', '=', config.id)], order='id desc', limit=1)
        return last.id if last else 0

    def _ms_hwm(self, ms):
        """Version-id boundary for a milestone: its stored hwm, or — for a legacy
        milestone sealed before W86 — the max version id at-or-before its
        timestamp (reliable there because legacy releases were sealed in a
        SEPARATE request from their edits, so no same-second collision)."""
        if not ms:
            return 0
        if ms.version_hwm is not None and ms.version_hwm >= 0:
            return ms.version_hwm
        last = self.env['hr.formula.rule.version'].sudo().search(
            [('config_id', '=', ms.config_id.id),
             ('create_date', '<=', ms.milestone_date)], order='id desc', limit=1)
        return last.id if last else 0

    def _formula_at_ver(self, rule, from_hwm):
        """The rule's Excel formula in effect just after version boundary
        ``from_hwm`` — the earliest version for this rule with id > from_hwm (its
        OUTGOING snapshot = the live state at that boundary); none → current.
        ``from_hwm`` 0 = start of history (the original formula)."""
        ver = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id), ('id', '>', from_hwm)], order='id asc', limit=1)
        return (ver.excel_formula if ver else rule.excel_formula) or ''

    def _constant_at_ver(self, rule, from_hwm):
        """The rule's ``constant_value`` in effect just after version boundary
        ``from_hwm`` (from the same OUTGOING snapshot as ``_formula_at_ver``)."""
        ver = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id), ('id', '>', from_hwm)], order='id asc', limit=1)
        if ver:
            try:
                return float(json.loads(ver.snapshot_json or '{}').get('constant_value') or 0.0)
            except Exception:
                pass
        return rule.constant_value or 0.0

    def _changes_between_ver(self, config, from_hwm, to_hwm=None):
        """Rules whose Excel formula OR constant differs between two version
        boundaries (D-C5). ``from_hwm`` 0 = start of history; ``to_hwm`` None =
        the live current state. Replaces the timestamp comparison so a milestone
        can never lose an edit to second-granularity (W86)."""
        Ver = self.env['hr.formula.rule.version'].sudo()
        changed = []
        for rule in config.rule_ids:
            old_f = self._formula_at_ver(rule, from_hwm)
            cur_f = self._formula_at_ver(rule, to_hwm) if to_hwm else (rule.excel_formula or '')
            old_c = self._constant_at_ver(rule, from_hwm)
            cur_c = self._constant_at_ver(rule, to_hwm) if to_hwm else (rule.constant_value or 0.0)
            f_changed = (old_f or '') != (cur_f or '')
            c_changed = abs((old_c or 0.0) - (cur_c or 0.0)) > 1e-9
            if not f_changed and not c_changed:
                continue
            dom = [('rule_id', '=', rule.id), ('id', '>', from_hwm)]
            if to_hwm:
                dom.append(('id', '<=', to_hwm))
            v = Ver.search(dom, order='id desc', limit=1)
            changed.append({
                'rule_id': rule.id, 'code': rule.code or '',
                'name': (rule.salary_rule_id.name if rule.salary_rule_id else False) or rule.name or '',
                'col': rule.column_letter or '', 'group': _group_for(rule),
                'type': rule.column_type,
                'old_formula': old_f, 'cur_formula': cur_f,
                'old_constant': old_c, 'cur_constant': cur_c,
                'formula_changed': f_changed, 'constant_changed': c_changed,
                'reason': v.reason if v else 'edit',
                'runs': self._token_diff_runs(self._tokenize_text(old_f), self._tokenize_text(cur_f))
                        if f_changed else [],
            })
        return changed

    def _formula_original(self, rule):
        """The rule's formula at the very start of its history — the earliest
        version's OUTGOING snapshot (each row is pre-edit), else the current if
        it was never edited. Used when there is no prior milestone to anchor to."""
        first = self.env['hr.formula.rule.version'].sudo().search(
            [('rule_id', '=', rule.id)], order='create_date asc, seq asc', limit=1)
        return (first.excel_formula if first else rule.excel_formula) or ''

    def _changes_between(self, config, from_when, to_when):
        """Rules whose formula differs between two instants (each read from the
        F7 version snapshots via _formula_at). ``from_when`` None = the start of
        history (original formula); ``to_when`` None = the live current formula."""
        changed = []
        for rule in config.rule_ids:
            old = self._formula_at(rule, from_when) if from_when else self._formula_original(rule)
            cur = self._formula_at(rule, to_when) if to_when else (rule.excel_formula or '')
            if (old or '') == (cur or ''):
                continue
            # most recent version reason for this rule inside the window (why it changed)
            dom = [('rule_id', '=', rule.id)]
            if from_when:
                dom.append(('create_date', '>=', from_when))
            if to_when:
                dom.append(('create_date', '<', to_when))
            v = self.env['hr.formula.rule.version'].sudo().search(
                dom, order='create_date desc, seq desc', limit=1)
            changed.append({
                'rule_id': rule.id, 'code': rule.code or '',
                'name': (rule.salary_rule_id.name if rule.salary_rule_id else False) or rule.name or '',
                'col': rule.column_letter or '', 'group': _group_for(rule),
                'old_formula': old, 'cur_formula': cur,
                'reason': v.reason if v else 'edit',
                'runs': self._token_diff_runs(self._tokenize_text(old), self._tokenize_text(cur)),
            })
        return changed

    def _draft_release_narrative(self, config, changes):
        """A prose changelog — LLM if available, else a deterministic template."""
        if not changes:
            return _("No formula changes since the last milestone.")
        # deterministic fallback (also the LLM's structured source)
        reason_label = {'edit': 'edited', 'bulk': 'bulk-edited', 'fill': 'drag-filled',
                        'import': 'imported', 'restore': 'restored', 'rename': 'renamed',
                        'lifecycle': 'lifecycle', 'legislation': 'legislation pack'}
        lines = ['- %s (%s): %s' % (c['name'], c['col'], reason_label.get(c['reason'], 'edited'))
                 for c in changes]
        fallback = _("This release updates %s component(s):\n%s") % (len(changes), '\n'.join(lines))
        try:
            summary = '\n'.join('%s [%s] %s → %s' % (c['col'], c['reason'],
                                                     (c['old_formula'] or '(none)'),
                                                     (c['cur_formula'] or '(none)'))
                                for c in changes)
            msgs = [
                {'role': 'system', 'content':
                 "You are a payroll release manager. Write a concise, professional changelog "
                 "(3-6 short bullet points, plain business language, no code) summarising these "
                 "payroll formula changes for a sign-off reviewer. Do not invent numbers."},
                {'role': 'user', 'content': "Config: %s\nChanges:\n%s" % (config.name, summary)},
            ]
            out = self._llm_chat(msgs)
            return (out or '').strip() or fallback
        except Exception:
            return fallback

    @api.model
    def release_preview(self, config_id=None):
        """The pending release: everything changed since the last milestone, with
        diffs and a drafted changelog. Nothing is written."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        last = self._last_milestone(config)
        # id boundary (W86) so a constant-only change (legislation pack) is
        # releasable AND rollback-able (D-C5), with no second-granularity loss.
        from_hwm = self._ms_hwm(last)
        changes = self._changes_between_ver(config, from_hwm, None)
        return {
            'ok': True,
            'config': {'id': config.id, 'name': config.name, 'state': config.state},
            'from_milestone': ({'id': last.id, 'name': last.name,
                                'date': fields.Datetime.to_string(last.milestone_date)}
                               if last else None),
            'change_count': len(changes),
            'changes': changes,
            'narrative': self._draft_release_narrative(config, changes),
            'can_edit': self._can_edit(),
        }

    @api.model
    def release_approve(self, config_id, narrative=None):
        """Sign off the pending release: seal an immutable milestone and record
        the release (with its F7 version rows for provenance)."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to sign off releases.")}
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        last = self._last_milestone(config)
        from_hwm = self._ms_hwm(last)
        changes = self._changes_between_ver(config, from_hwm, None)
        if not changes:
            return {'ok': False, 'reason': 'no_changes',
                    'msg': _("There are no changes to release since the last milestone.")}
        Release = self.env['hr.formula.release']
        n = Release.search_count([('config_id', '=', config.id)]) + 1
        # Seal at the current version high-water mark (W86) so a later rollback of
        # this release reads an exact 'from' boundary — see _seal_milestone.
        to_ms = self._seal_milestone(config, _("Release v%s") % n)
        vdom = [('config_id', '=', config.id), ('id', '>', from_hwm)]
        versions = self.env['hr.formula.rule.version'].sudo().search(vdom)
        rel = Release.create({
            'name': _("Release v%s") % n,
            'config_id': config.id,
            'from_milestone_id': last.id if last else False,
            'to_milestone_id': to_ms.id,
            'narrative': (narrative or '').strip() or self._draft_release_narrative(config, changes),
            'change_count': len(changes),
            'version_ids': [(6, 0, versions.ids)],
        })
        return {'ok': True, 'release_id': rel.id, 'change_count': len(changes)}

    @api.model
    def list_releases(self, config_id=None):
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'releases': []}
        rels = self.env['hr.formula.release'].search([('config_id', '=', config.id)])
        # W86 — only the latest release is rollback-eligible (D-C4); flag it so the
        # UI shows the Rollback button on exactly one row.
        latest = self._last_release(config)
        return {'ok': True, 'latest_id': latest.id or False, 'can_edit': self._can_edit(),
                'releases': [{
                    'id': r.id, 'name': r.name,
                    'approved_by': r.approved_by_id.name or '',
                    'approved_date': fields.Datetime.to_string(r.approved_date) if r.approved_date else '',
                    'change_count': r.change_count,
                    'narrative': r.narrative or '',
                    'from': r.from_milestone_id.name or '(start)',
                    'to': r.to_milestone_id.name or '',
                    'is_latest': r.id == latest.id,
                } for r in rels]}

    @api.model
    def release_detail(self, release_id):
        """Re-derive a past release's diffs from its two milestone boundaries."""
        rel = self.env['hr.formula.release'].browse(int(release_id))
        if not rel.exists():
            return {'ok': False}
        from_hwm = self._ms_hwm(rel.from_milestone_id)
        to_hwm = self._ms_hwm(rel.to_milestone_id) if rel.to_milestone_id else None
        changes = self._changes_between_ver(rel.config_id, from_hwm, to_hwm)
        return {'ok': True, 'name': rel.name, 'narrative': rel.narrative or '',
                'approved_by': rel.approved_by_id.name or '',
                'approved_date': fields.Datetime.to_string(rel.approved_date) if rel.approved_date else '',
                'change_count': len(changes), 'changes': changes}

    # ==================================================================
    # W86 — One-action rollback (revert the latest release atomically)
    # ==================================================================
    # Rollback of release vN ≡ restore the config to milestone `from` of vN
    # (D-C4). It is itself a versioned + released event (reason='restore', a new
    # milestone + audit release row) so history is never rewritten and a second
    # rollback round-trips cleanly. Constants are reverted too (D-C5): a
    # legislation pack edits `constant_value`, so a formula-only rollback would
    # silently keep a new SI cap.
    def _last_release(self, config):
        return self.env['hr.formula.release'].search(
            [('config_id', '=', config.id)], order='approved_date desc, id desc', limit=1)

    def _restore_rule_state(self, rule, excel_formula, constant_value):
        """Write a past (formula, constant) back onto a live rule. Mirrors
        ``restore_version``'s python-rebuild + validity check for the formula path
        (``pb_formula_studio.py`` restore) and ADDS the constant path (net-new,
        D-C5). A restored formula that no longer converts RAISES here so the
        caller's savepoint aborts loudly — never a half-applied rollback (C7)."""
        vals = {}
        if rule.column_type == 'formula':
            column_map = {r.column_letter: r.code for r in rule.config_id.rule_ids if r.column_letter}
            py = rule._convert_excel_to_python(excel_formula or '', column_map)   # may raise → savepoint aborts
            ok, msg = self._check_formula(rule.config_id, excel_formula or '', exclude_id=rule.id)
            vals.update({'excel_formula': excel_formula or '', 'python_formula': py,
                         'is_valid': ok, 'validation_message': '' if ok else msg})
        elif excel_formula is not None:
            vals['excel_formula'] = excel_formula or ''
        if constant_value is not None:
            vals['constant_value'] = constant_value
        if vals:
            rule.write(vals)

    def _rollback_guard(self, rel):
        """D-C4 eligibility: only the latest release, and only when nothing is
        unreleased (else 'rollback of vN' is ambiguous). Returns {ok[, reason,
        msg]}."""
        config = rel.config_id
        latest = self._last_release(config)
        if not latest or rel.id != latest.id:
            return {'ok': False, 'reason': 'not_latest',
                    'msg': _("Only the latest release can be rolled back.")}
        to_hwm = self._ms_hwm(rel.to_milestone_id)
        unreleased = self._changes_between_ver(config, to_hwm, None)
        if unreleased:
            return {'ok': False, 'reason': 'unreleased',
                    'msg': _("Release or discard the current changes first "
                             "(%d unreleased change(s)).") % len(unreleased)}
        return {'ok': True}

    def _rollback_overrides(self, changes):
        """Split a change list into the formula + constant overrides that seed a
        simulate-before-apply run (the rollback previews its OLD state)."""
        formula_overrides = {c['code']: c['old_formula']
                             for c in changes if c['formula_changed'] and c['code']}
        value_overrides = {c['code']: c['old_constant']
                           for c in changes if c['constant_changed'] and c['code']}
        return formula_overrides, value_overrides

    @api.model
    def rollback_preview(self, release_id):
        """What rolling back a release would revert: eligibility (+ block reason),
        the formula/constant change list, and the simulate overrides (D-C6).
        Nothing is written."""
        rel = self.env['hr.formula.release'].browse(int(release_id))
        if not rel.exists():
            return {'ok': False}
        config = rel.config_id
        guard = self._rollback_guard(rel)
        from_hwm = self._ms_hwm(rel.from_milestone_id)
        changes = self._changes_between_ver(config, from_hwm, None)
        formula_overrides, value_overrides = self._rollback_overrides(changes)
        return {
            'ok': True,
            'eligible': guard['ok'],
            'block_reason': '' if guard['ok'] else guard.get('msg', ''),
            'release': {'id': rel.id, 'name': rel.name, 'narrative': rel.narrative or '',
                        'approved_by': rel.approved_by_id.name or '',
                        'approved_date': fields.Datetime.to_string(rel.approved_date)
                                         if rel.approved_date else ''},
            'change_count': len(changes),
            'changes': changes,
            'formula_overrides': formula_overrides,
            'value_overrides': value_overrides,
            'can_edit': self._can_edit(),
        }

    @api.model
    def rollback_simulate_prepare(self, release_id, limit=None):
        """Seed a simulation with the rollback's OLD formulas + constants and
        return the payslip work-list (drive it via the shared simulate_batch /
        simulate_result RPCs). Shows the org-wide impact before Apply arms."""
        rel = self.env['hr.formula.release'].browse(int(release_id))
        if not rel.exists():
            return {'ok': False}
        config = rel.config_id
        from_hwm = self._ms_hwm(rel.from_milestone_id)
        changes = self._changes_between_ver(config, from_hwm, None)
        formula_overrides, value_overrides = self._rollback_overrides(changes)
        Sim = self.env['hr.formula.simulation']
        created = Sim.sim_create(config.id, overrides=formula_overrides,
                                 value_overrides=value_overrides)
        if not created.get('ok'):
            return created
        prep = Sim.sim_prepare(created['sim_id'], limit=limit)
        prep.update({'ok': True, 'headline': created.get('headline'),
                     'overrides': created.get('overrides', 0)})
        return prep

    @api.model
    def rollback_apply(self, release_id):
        """Revert the latest release atomically (S-C1). Restores every changed
        rule's formula AND constant to its at-`from`-milestone value in one
        savepoint (all-or-nothing), records a 'Rollback of vN' milestone + audit
        release row, and re-runs the sample tests (W82 — a rollback is a save)."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to roll back releases.")}
        rel = self.env['hr.formula.release'].browse(int(release_id))
        if not rel.exists():
            return {'ok': False, 'msg': _('Release not found')}
        config = rel.config_id
        guard = self._rollback_guard(rel)
        if not guard['ok']:
            return guard
        from_hwm = self._ms_hwm(rel.from_milestone_id)
        changes = self._changes_between_ver(config, from_hwm, None)
        if not changes:
            return {'ok': False, 'reason': 'nothing', 'msg': _('Nothing to roll back.')}
        seen = set()
        pre_hwm = self._config_version_hwm(config)     # id boundary before the restore writes
        ctx = dict(formula_version_reason='restore',
                   formula_version_note=_('Rollback %s') % rel.name,
                   formula_version_seen=seen)
        try:
            with self.env.cr.savepoint():
                for ch in changes:
                    rule = self.env['hr.formula.rule'].browse(ch['rule_id']).with_context(**ctx)
                    self._restore_rule_state(rule, ch['old_formula'], ch['old_constant'])
        except Exception as e:
            _logger.warning("rollback_apply failed on %s: %s", config.code, e)
            return {'ok': False, 'msg': str(e)}
        # audit: the rollback IS a release (D-C6) — milestone + release row, from
        # the rolled-back release's `to` up to the new rollback milestone. The
        # provenance rows are exactly the restore versions just created (id > the
        # pre-restore boundary), and _seal_milestone stamps the new milestone at
        # the post-restore hwm so rolling back THIS rollback reads a clean
        # boundary — the double-rollback round-trip (D-C4).
        versions = self.env['hr.formula.rule.version'].sudo().search(
            [('config_id', '=', config.id), ('id', '>', pre_hwm)])
        to_ms = self._seal_milestone(config, _('Rollback of %s') % rel.name)
        Release = self.env['hr.formula.release']
        audit = Release.create({
            'name': _('Rollback of %s') % rel.name,
            'config_id': config.id,
            'from_milestone_id': rel.to_milestone_id.id if rel.to_milestone_id else False,
            'to_milestone_id': to_ms.id,
            'narrative': self._draft_release_narrative(config, changes),
            'change_count': len(changes),
            'version_ids': [(6, 0, versions.ids)],
        })
        tests = self._run_tests_after_save(config)
        return {'ok': True, 'restored': len(seen), 'release_id': audit.id, 'tests': tests}

    # ==================================================================
    # W97 — Period comparison (read-only chunked aggregation of two payruns)
    # ==================================================================
    @api.model
    def compare_runs(self, config_id=None):
        """The payslip runs comparable for a config: those carrying this config's
        formula slips, newest period first. Feeds the two run pickers."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'runs': []}
        slips = self.env['hr.payslip'].sudo().search([
            ('formula_config_id', '=', config.id),
            ('calculation_method', '=', 'formula'),
            ('payslip_run_id', '!=', False)])
        counts = defaultdict(int)
        for s in slips:
            counts[s.payslip_run_id.id] += 1
        runs = self.env['hr.payslip.run'].sudo().browse(list(counts.keys())).exists()
        items = sorted(([{
            'id': r.id, 'name': r.name or '',
            'date_start': str(r.date_start or ''), 'date_end': str(r.date_end or ''),
            'slips': counts.get(r.id, 0),
        } for r in runs]), key=lambda x: (x['date_start'], x['name']), reverse=True)
        return {'ok': True, 'config': {'id': config.id, 'name': config.display_name},
                'runs': items,
                'currency': config.currency_id.symbol if config.currency_id else ''}

    @api.model
    def compare_prepare(self, config_id, run_a_id, run_b_id):
        """Create a comparison and return the matched slip-pair work-list to drive
        through it in chunks (mirrors simulate_prepare)."""
        Cmp = self.env['hr.formula.period.comparison']
        created = Cmp.cmp_create(config_id, run_a_id, run_b_id)
        if not created.get('ok'):
            return created
        prep = Cmp.cmp_prepare(created['cmp_id'])
        prep.update({'ok': True, 'headline': created.get('headline')})
        return prep

    @api.model
    def compare_batch(self, payload):
        return self.env['hr.formula.period.comparison'].cmp_batch(payload or {})

    @api.model
    def compare_result(self, cmp_id):
        return self.env['hr.formula.period.comparison'].cmp_finalize(cmp_id)

    @api.model
    def compare_drop(self, cmp_id):
        cmp = self.env['hr.formula.period.comparison'].browse(int(cmp_id))
        cmp.cmp_drop()
        return {'ok': True}

    # ==================================================================
    # W95 (WP-H) — component budgets (vs-actual variance in the compare view)
    # Reads are open; writes are manager-gated (D-H2), same split as snippets.
    # ==================================================================
    def _budget_payload(self, b):
        return {'id': b.id, 'name': b.name or '',
                'period_label': b.period_label or '', 'note': b.note or '',
                'line_count': len(b.line_ids)}

    @api.model
    def budget_list(self, config_id=None):
        """Budgets authored for a config, newest first. Feeds the budget picker."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'budgets': []}
        budgets = self.env['hr.formula.budget'].search(
            [('config_id', '=', config.id)], order='id desc')
        return {'ok': True, 'config': {'id': config.id, 'name': config.display_name},
                'budgets': [self._budget_payload(b) for b in budgets],
                'can_edit': self._can_edit(),
                'currency': config.currency_id.symbol if config.currency_id else ''}

    @api.model
    def budget_get(self, config_id, budget_id=None):
        """Editor payload: every config component (code, name, group) with its
        current budget amount, PLUS orphan budget lines whose code no longer
        exists in the config (D-H2 honesty — surfaced, never dropped). A falsy
        ``budget_id`` returns a blank editor over the config's components."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        try:
            if not config.exists():
                return {'ok': False}
            config.check_access('read')
        except AccessError:
            return {'ok': False, 'msg': _('No access to this configuration.')}
        amounts = {}
        budget = None
        if budget_id:
            budget = self.env['hr.formula.budget'].browse(int(budget_id)).exists()
            if budget:
                for l in budget.line_ids:
                    if l.code:
                        amounts[l.code] = l.amount
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        rule_codes = set()
        components = []
        for r in rules:
            if not r.code:
                continue
            rule_codes.add(r.code)
            components.append({
                'code': r.code,
                'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code,
                'group': _group_for(r),
                'type': r.column_type,
                'amount': amounts.get(r.code, 0.0),
            })
        orphans = []
        for code, amt in amounts.items():
            if code not in rule_codes:
                orphans.append({'code': code, 'amount': amt})
        orphans.sort(key=lambda o: o['code'])
        return {
            'ok': True,
            'budget': (self._budget_payload(budget) if budget else None),
            'components': components,
            'orphans': orphans,
            'can_edit': self._can_edit(),
            'currency': config.currency_id.symbol if config.currency_id else '',
        }

    @api.model
    def budget_seed_from_run(self, config_id, run_id):
        """Per-component actual sums for a run keyed by code (D-H2 Seed-from-run).
        Pure read of stored slips via the engine helper — open to all."""
        sums = self.env['hr.formula.period.comparison'].run_component_sums(config_id, run_id)
        return {'ok': True, 'amounts': sums}

    @api.model
    def budget_save(self, vals):
        """Create/replace a budget from the editor (manager-gated). The client
        sends the FULL desired line set (config amounts + any kept orphans); the
        server validates every value (numeric, |v| <= 1e12 — same rule as W49)
        and replaces line_ids wholesale so removed rows disappear atomically."""
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can edit budgets.')}
        config = self.env['hr.formula.config'].browse(int(vals.get('config_id') or 0))
        if not config.exists():
            return {'ok': False, 'msg': _('Configuration not found.')}
        name = (vals.get('name') or '').strip()
        if not name:
            return {'ok': False, 'msg': _('A budget needs a name.')}
        # Validate lines: {code: amount}. Reject non-numeric / absurd values loudly.
        raw = vals.get('lines') or {}
        clean = {}
        for code, amount in (raw.items() if isinstance(raw, dict) else []):
            code = (str(code) or '').strip()
            if not code:
                continue
            n = self._as_num(amount)
            if n is None:
                return {'ok': False, 'msg': _('Budget amount for %s is not a number.') % code}
            if abs(n) > 1e12:
                return {'ok': False, 'msg': _('Budget amount for %s is out of range.') % code}
            clean[code] = n
        Budget = self.env['hr.formula.budget']
        bid = vals.get('id')
        head = {'name': name, 'config_id': config.id,
                'period_label': (vals.get('period_label') or '').strip(),
                'note': (vals.get('note') or '').strip()}
        if bid:
            budget = Budget.browse(int(bid))
            if not budget.exists():
                return {'ok': False, 'msg': _('Budget not found.')}
            budget.write(head)
            budget.line_ids.unlink()
        else:
            budget = Budget.create(head)
        Line = self.env['hr.formula.budget.line']
        for code, amount in clean.items():
            Line.create({'budget_id': budget.id, 'code': code, 'amount': amount})
        return {'ok': True, 'budget': self._budget_payload(budget)}

    @api.model
    def budget_delete(self, budget_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can delete budgets.')}
        budget = self.env['hr.formula.budget'].browse(int(budget_id))
        if budget.exists():
            budget.unlink()
        return {'ok': True}

    @api.model
    def budget_prepare(self, config_id, budget_id, run_b_id):
        """Create a budget-vs-actual comparison and return the B-slip work-list to
        drive in chunks — parallels ``compare_prepare`` (only side B chunks)."""
        Cmp = self.env['hr.formula.period.comparison']
        created = Cmp.cmp_create_budget(config_id, budget_id, run_b_id)
        if not created.get('ok'):
            return created
        prep = Cmp.cmp_prepare(created['cmp_id'])
        prep.update({'ok': True, 'headline': created.get('headline')})
        return prep

    # ==================================================================
    # W48 — Payrun anomaly narration (deterministic-first, LLM-polished)
    # ==================================================================
    @api.model
    def narrate_comparison(self, cmp_id, lang='en'):
        """TD.2 — narrate a finished period comparison. The deterministic blocks
        (D-D2) are always the floor; an LLM rewrite for fluency is served ONLY if
        every money-scale number in it exists in the fold (invented figures →
        deterministic text). No AI key / any error → deterministic (C1)."""
        cmp = self.env['hr.formula.period.comparison'].browse(int(cmp_id))
        if not cmp.exists():
            return {'ok': False}
        lang = lang if lang in ('en', 'vi') else 'en'
        det = cmp.narrate(lang)
        det_blocks = det['blocks']
        try:
            allowed = cmp.narrate_allowed_numbers()
            sys_lang = 'Vietnamese' if lang == 'vi' else 'English'
            system = (
                "You are PayAI, a payroll analyst. Rewrite the given factual bullet points into a "
                "concise, fluent %s narrative of 3-6 sentences in plain business language. You MUST NOT "
                "invent, alter, round differently, or drop any number, employee name, component code, or "
                "date — reuse them exactly. Reply STRICT JSON: {\"narrative\": \"...\"}." % sys_lang)
            user = json.dumps({'facts': det['facts'], 'sentences': det_blocks}, ensure_ascii=False)
            out = self._llm_chat(
                [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                json_mode=True)
            polished = (out or {}).get('narrative') if isinstance(out, dict) else None
            if polished and polished.strip() and _narr_numbers_ok(polished, allowed):
                return {'ok': True, 'blocks': [polished.strip()], 'source': 'ai',
                        'lang': lang, 'deterministic': det_blocks}
        except Exception as e:
            _logger.info("narrate_comparison LLM fallback: %s", e)
        return {'ok': True, 'blocks': det_blocks, 'source': 'deterministic', 'lang': lang}

    # ==================================================================
    # B6 — Bureau cockpit (read-only multi-config health board)
    # ==================================================================
    @api.model
    def bureau_board(self):
        """One health card per configuration the user can see: Phase-1 score,
        F13 open problems, B3 pending changes, employee coverage, lifecycle
        state. Read-only aggregation — nothing is written."""
        Config = self.env['hr.formula.config']
        configs = Config.search([], order='company_id, name')
        Rel = self.env['hr.formula.release']
        cards = []
        for c in configs:
            try:
                prob = self.get_problems(c.id)
            except Exception:
                prob = {'count': 0, 'counts': {'error': 0, 'warning': 0, 'hint': 0}}
            last = self._last_milestone(c)
            when = last.milestone_date if last else False
            try:
                pending = len(self._changes_between(c, when, None))
            except Exception:
                pending = 0
            cards.append({
                'id': c.id, 'name': c.name,
                'company': c.company_id.name if c.company_id else '',
                'division': getattr(c, 'pb_division', False) or '',
                'cycle_type': c.cycle_type or 'regular', 'state': c.state,
                'score': self._score(c),
                'rule_count': len(c.rule_ids),
                'problem_counts': prob.get('counts', {'error': 0, 'warning': 0, 'hint': 0}),
                'problem_count': prob.get('count', 0),
                'pending_changes': pending,
                'release_count': Rel.search_count([('config_id', '=', c.id)]),
                'employees': self._config_employee_count(c),
                # --- identity fields the Config Switcher gallery also renders ---
                'code': c.code or '',
                'country': c.country_code or '',
                'currency': c.currency_id.name or '',
                'active': bool(c.active),
                'sample_count': len(c.sample_data_ids),
                'is_branch': bool(c.parent_branch_id),
                'is_variant': bool(c.master_config_id),
                'is_master': bool(c.variant_ids),
            })
        # rank so the boards needing attention (errors, pending, low score) float up
        cards.sort(key=lambda k: (
            -(k['problem_counts'].get('error', 0)),
            -k['pending_changes'],
            k['score'],
        ))
        return {'ok': True, 'cards': cards, 'can_edit': self._can_edit(),
                'company': self.env.company.name}

    @api.model
    def bureau_clone(self, config_id, name=None):
        """Template-clone a configuration (rules + rate tables + samples) as a new
        draft — the B6 'roll out a validated scheme' primitive."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to clone configurations.")}
        src = self.env['hr.formula.config'].browse(int(config_id))
        if not src.exists():
            return {'ok': False}
        base_code = (src.code or 'CFG')
        existing = set(self.env['hr.formula.config'].search([]).mapped('code'))
        code, i = base_code + '_COPY', 1
        while code in existing:
            i += 1
            code = '%s_COPY%s' % (base_code, i)
        new = src.copy({
            'name': (name or '').strip() or (_("%s (copy)") % src.name),
            'code': code, 'state': 'draft',
        })
        return {'ok': True, 'config_id': new.id, 'name': new.name}

    # ==================================================================
    # B4 — Legislation packs (roll a statutory change across every config)
    # ==================================================================
    def _legis_constant(self, config, code):
        """The constant rule in `config` matching `code` (case-insensitive)."""
        if not code:
            return self.env['hr.formula.rule']
        cu = code.strip().upper()
        return config.rule_ids.filtered(
            lambda r: r.column_type == 'constant' and (r.code or '').upper() == cu)[:1]

    @staticmethod
    def _legis_eq(a, b):
        # constant_value is stored at 6 decimals — compare at that precision.
        return round(a or 0.0, 6) == round(b or 0.0, 6)

    def _legis_pack_payload(self, pack):
        sel = dict(pack._fields['country_code'].selection)
        return {
            'id': pack.id, 'name': pack.name,
            'country_code': pack.country_code, 'country': sel.get(pack.country_code, ''),
            'version': pack.version, 'authority': pack.authority or '',
            'effective_date': fields.Date.to_string(pack.effective_date) if pack.effective_date else '',
            'state': pack.state, 'description': pack.description or '',
            'item_count': len(pack.item_ids),
        }

    def _legis_eval(self, pack, config):
        """Per-item comparison of a pack against one config: what each statutory
        value is now vs what the pack sets it to. Unmatched codes (constants the
        config doesn't have) are surfaced as matched=False, never mutated."""
        rows = []
        for it in pack.item_ids.sorted(key=lambda i: i.sequence):
            rule = self._legis_constant(config, it.code)
            row = {'code': it.code, 'label': it.label, 'target': it.value,
                   'number_format': it.number_format or 'currency',
                   'note': it.note or '', 'matched': bool(rule)}
            if rule:
                cur = rule.constant_value or 0.0
                row.update({'rule_id': rule.id, 'current': cur,
                            'changed': not self._legis_eq(cur, it.value),
                            'delta': (it.value or 0.0) - cur})
            else:
                row.update({'rule_id': False, 'current': None, 'changed': False, 'delta': 0.0})
            rows.append(row)
        return rows

    def _legis_status(self, rows):
        matched = [r for r in rows if r['matched']]
        if not matched:
            return 'na'
        return 'drift' if any(r['changed'] for r in matched) else 'aligned'

    @api.model
    def legislation_packs(self):
        """Every pack the user can see, with a coverage roll-up over the configs
        in scope (aligned / needs-update / not-applicable). Read-only."""
        packs = self.env['hr.formula.legislation.pack'].search([])
        configs = self.env['hr.formula.config'].search([])
        out = []
        for p in packs:
            aligned = drift = na = 0
            for c in configs:
                st = self._legis_status(self._legis_eval(p, c))
                aligned += st == 'aligned'
                drift += st == 'drift'
                na += st == 'na'
            d = self._legis_pack_payload(p)
            d.update({'aligned': aligned, 'drift': drift, 'na': na})
            out.append(d)
        # newest-effective first, drafts (pending rollouts) surfaced above published
        out.sort(key=lambda k: (0 if k['state'] == 'draft' else 1, k['country'],
                                k['effective_date']), reverse=False)
        return {'ok': True, 'packs': out, 'can_edit': self._can_edit(),
                'company': self.env.company.name, 'config_count': len(configs)}

    @api.model
    def legislation_detail(self, pack_id):
        pack = self.env['hr.formula.legislation.pack'].browse(int(pack_id))
        if not pack.exists():
            return {'ok': False}
        items = [{
            'code': it.code, 'label': it.label, 'value': it.value,
            'number_format': it.number_format or 'currency', 'note': it.note or '',
        } for it in pack.item_ids.sorted(key=lambda i: i.sequence)]
        apps = self.env['hr.formula.legislation.application'].search(
            [('pack_id', '=', pack.id)], limit=50)
        return {'ok': True, 'pack': self._legis_pack_payload(pack), 'items': items,
                'applications': [{
                    'config': a.config_id.name or '', 'by': a.applied_by_id.name or '',
                    'date': fields.Datetime.to_string(a.applied_date) if a.applied_date else '',
                    'item_count': a.item_count,
                } for a in apps],
                'can_edit': self._can_edit()}

    @api.model
    def legislation_coverage(self, pack_id):
        """Per-config board for one pack: which configs are aligned, which need
        the update (and by how many values), which don't carry these codes."""
        pack = self.env['hr.formula.legislation.pack'].browse(int(pack_id))
        if not pack.exists():
            return {'ok': False}
        configs = self.env['hr.formula.config'].search([])
        board = []
        for c in configs:
            rows = self._legis_eval(pack, c)
            matched = [r for r in rows if r['matched']]
            changed = [r for r in matched if r['changed']]
            board.append({
                'config_id': c.id, 'name': c.name, 'state': c.state,
                'status': self._legis_status(rows),
                'matched': len(matched), 'changed': len(changed),
                'employees': self._config_employee_count(c),
                'diffs': changed,
            })
        rank = {'drift': 0, 'aligned': 1, 'na': 2}
        board.sort(key=lambda b: (rank[b['status']], -b['changed'], b['name']))
        summary = {
            'aligned': sum(b['status'] == 'aligned' for b in board),
            'drift': sum(b['status'] == 'drift' for b in board),
            'na': sum(b['status'] == 'na' for b in board),
            'employees_affected': sum(b['employees'] for b in board if b['status'] == 'drift'),
        }
        return {'ok': True, 'pack': self._legis_pack_payload(pack),
                'board': board, 'summary': summary, 'can_edit': self._can_edit()}

    @api.model
    def legislation_diff(self, pack_id, config_id):
        """Full per-item diff of a pack against one config (matched + unmatched)."""
        pack = self.env['hr.formula.legislation.pack'].browse(int(pack_id))
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not pack.exists() or not config.exists():
            return {'ok': False}
        rows = self._legis_eval(pack, config)
        return {'ok': True, 'config': {'id': config.id, 'name': config.name},
                'rows': rows, 'changed': sum(1 for r in rows if r['changed']),
                'can_edit': self._can_edit()}

    @api.model
    def legislation_apply(self, pack_id, config_id=None, config_ids=None):
        """Apply a pack to one config or a set: write each drifted statutory
        constant (F7-versioned, reason='legislation'), seal a B3 milestone, and
        log the application. Configs already aligned are skipped, not touched."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to apply legislation packs.")}
        pack = self.env['hr.formula.legislation.pack'].browse(int(pack_id))
        if not pack.exists():
            return {'ok': False}
        if config_ids:
            targets = self.env['hr.formula.config'].browse([int(i) for i in config_ids])
        elif config_id:
            targets = self.env['hr.formula.config'].browse(int(config_id))
        else:
            return {'ok': False, 'msg': _("No target configuration given.")}
        targets = targets.exists()
        Milestone = self.env['hr.formula.config.milestone'].sudo()
        App = self.env['hr.formula.legislation.application']
        results = []
        for c in targets:
            rows = self._legis_eval(pack, c)
            changed = [r for r in rows if r['matched'] and r['changed']]
            if not changed:
                results.append({'config_id': c.id, 'name': c.name, 'changed': 0, 'skipped': True})
                continue
            seen = set()
            for r in changed:
                rule = self.env['hr.formula.rule'].browse(r['rule_id'])
                rule.with_context(formula_version_reason='legislation',
                                  formula_version_note='%s %s' % (pack.name, pack.version),
                                  formula_version_seen=seen).constant_value = r['target']
            ms = Milestone.record(c, _("Applied %s %s") % (pack.name, pack.version))
            App.create({'pack_id': pack.id, 'config_id': c.id,
                        'item_count': len(changed), 'milestone_id': ms.id})
            results.append({'config_id': c.id, 'name': c.name,
                            'changed': len(changed), 'skipped': False})
        return {'ok': True, 'results': results,
                'total_changed': sum(r['changed'] for r in results),
                'configs_touched': sum(1 for r in results if not r['skipped'])}

    # ==================================================================
    # B2 — Config branches (fork a live config, edit safely, merge back)
    # ==================================================================
    def _branch_value_map(self, config):
        """The mergeable rules of a config keyed by code — formula rules carry a
        formula, constants carry a value. Inputs/others are not merged."""
        out = {}
        for r in config.rule_ids:
            if r.column_type in ('formula', 'constant') and r.code:
                out[r.code.upper()] = r
        return out

    def _branch_row(self, code, brule, prule, fork_when):
        """One diff row between a branch rule (brule) and its parent rule (prule);
        either may be None for add/remove. Carries a token diff for formulas and
        a conflict flag when the parent moved on this rule since the fork."""
        rule = brule or prule
        kind = 'constant' if rule.column_type == 'constant' else 'formula'
        row = {
            'code': code,
            'name': (rule.salary_rule_id.name if rule.salary_rule_id else False) or rule.name or code,
            'col': (brule or prule).column_letter or '',
            'kind': kind, 'group': _group_for(rule), 'conflict': False,
        }
        if kind == 'formula':
            old = (prule.excel_formula or '') if prule else ''
            new = (brule.excel_formula or '') if brule else ''
            row.update({'old_formula': old, 'cur_formula': new,
                        'runs': self._token_diff_runs(self._tokenize_text(old),
                                                      self._tokenize_text(new))})
            if brule and prule and fork_when:
                at_fork = self._formula_at(prule, fork_when)
                row['conflict'] = (at_fork or '') != (prule.excel_formula or '')
        else:
            row.update({'old_value': (prule.constant_value if prule else None),
                        'new_value': (brule.constant_value if brule else None),
                        'number_format': (brule or prule).number_format or 'currency'})
        return row

    def _branch_diff_rows(self, branch):
        """changed / added / removed rows for a branch vs its parent (by code)."""
        parent = branch.parent_branch_id
        if not parent:
            return {'changed': [], 'added': [], 'removed': []}
        fork_when = branch.fork_milestone_id.milestone_date if branch.fork_milestone_id else False
        pmap = self._branch_value_map(parent)
        bmap = self._branch_value_map(branch)
        changed, added = [], []
        for code, brule in bmap.items():
            prule = pmap.get(code)
            if not prule:
                added.append(self._branch_row(code, brule, None, fork_when))
                continue
            same = (brule.column_type == 'constant'
                    and round(brule.constant_value or 0.0, 6) == round(prule.constant_value or 0.0, 6)) \
                or (brule.column_type != 'constant'
                    and (brule.excel_formula or '') == (prule.excel_formula or ''))
            if not same:
                changed.append(self._branch_row(code, brule, prule, fork_when))
        removed = [self._branch_row(code, None, prule, fork_when)
                   for code, prule in pmap.items() if code not in bmap]
        return {'changed': changed, 'added': added, 'removed': removed}

    def _branch_payload(self, b):
        d = self._branch_diff_rows(b)
        return {
            'id': b.id, 'name': b.name, 'state': b.state,
            'branch_state': b.branch_state or 'open',
            'note': b.branch_note or '',
            'created': fields.Datetime.to_string(b.create_date) if b.create_date else '',
            'created_by': b.create_uid.name or '',
            'employees': self._config_employee_count(b),
            'changed': len(d['changed']), 'added': len(d['added']),
            'removed': len(d['removed']),
            'conflicts': sum(1 for r in d['changed'] if r['conflict']),
        }

    @api.model
    def list_branches(self, config_id=None):
        """Branches of the current config (and, if it IS a branch, its parent)."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'branches': []}
        branches = config.child_branch_ids.filtered(lambda b: b.branch_state != 'discarded')
        return {
            'ok': True,
            'config': {'id': config.id, 'name': config.name,
                       'is_branch': bool(config.parent_branch_id),
                       'parent_id': config.parent_branch_id.id or False,
                       'parent_name': config.parent_branch_id.name or '',
                       'branch_state': config.branch_state or 'open'},
            'branches': [self._branch_payload(b) for b in branches.sorted(key=lambda x: x.id, reverse=True)],
            'can_edit': self._can_edit(),
        }

    @api.model
    def branch_create(self, config_id, name=None, note=None):
        """Fork a config into a draft branch and anchor a fork milestone on the
        parent (the reference point for later conflict detection)."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to create branches.")}
        parent = self.env['hr.formula.config'].browse(int(config_id))
        if not parent.exists():
            return {'ok': False}
        if parent.parent_branch_id:
            return {'ok': False, 'msg': _("You can only branch a mainline configuration, not a branch.")}
        base_code = parent.code or 'CFG'
        existing = set(self.env['hr.formula.config'].with_context(active_test=False)
                       .search([]).mapped('code'))
        code, i = base_code + '_BR', 1
        while code in existing:
            i += 1
            code = '%s_BR%s' % (base_code, i)
        fork = self.env['hr.formula.config.milestone'].sudo().record(
            parent, _("Branched: %s") % ((name or '').strip() or _("branch")))
        branch = parent.copy({
            'name': (name or '').strip() or (_("%s — branch") % parent.name),
            'code': code, 'state': 'draft',
            'parent_branch_id': parent.id, 'branch_state': 'open',
            'branch_note': (note or '').strip() or False,
            'fork_milestone_id': fork.id,
        })
        return {'ok': True, 'branch_id': branch.id, 'name': branch.name}

    @api.model
    def branch_diff(self, branch_id):
        branch = self.env['hr.formula.config'].browse(int(branch_id))
        if not branch.exists() or not branch.parent_branch_id:
            return {'ok': False}
        d = self._branch_diff_rows(branch)
        return {'ok': True,
                'branch': {'id': branch.id, 'name': branch.name,
                           'branch_state': branch.branch_state or 'open'},
                'parent': {'id': branch.parent_branch_id.id, 'name': branch.parent_branch_id.name},
                'changed': d['changed'], 'added': d['added'], 'removed': d['removed'],
                'conflicts': sum(1 for r in d['changed'] if r['conflict']),
                'can_edit': self._can_edit()}

    @api.model
    def branch_merge(self, branch_id, narrative=None):
        """Write the branch's changed formulas/values back onto the parent
        (F7 reason='merge'), then seal a release. Added/removed components are
        reported but not auto-applied (a formula change is the safe 90% case)."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to merge branches.")}
        branch = self.env['hr.formula.config'].browse(int(branch_id))
        if not branch.exists() or not branch.parent_branch_id:
            return {'ok': False}
        if branch.branch_state == 'merged':
            return {'ok': False, 'msg': _("This branch has already been merged.")}
        parent = branch.parent_branch_id
        d = self._branch_diff_rows(branch)
        if not d['changed']:
            return {'ok': False, 'reason': 'no_changes',
                    'msg': _("This branch has no formula changes to merge.")}
        pmap = self._branch_value_map(parent)
        column_map = {r.column_letter: r.code for r in parent.rule_ids if r.column_letter}
        seen = set()
        merged = 0
        for row in d['changed']:
            prule = pmap.get(row['code'])
            if not prule:
                continue
            prule = prule.with_context(formula_version_reason='merge',
                                       formula_version_note=_("Merged from %s") % branch.name,
                                       formula_version_seen=seen)
            if row['kind'] == 'constant':
                prule.constant_value = row.get('new_value') or 0.0
            else:
                prule.excel_formula = row.get('cur_formula') or ''
                prule.python_formula = prule._convert_excel_to_python(prule.excel_formula, column_map)
            merged += 1
        branch.branch_state = 'merged'
        rel = self.release_approve(parent.id, (narrative or '').strip()
                                   or _("Merged branch “%s” — %s component(s)") % (branch.name, merged))
        return {'ok': True, 'merged': merged,
                'skipped_added': len(d['added']), 'skipped_removed': len(d['removed']),
                'conflicts': sum(1 for r in d['changed'] if r['conflict']),
                'release_id': rel.get('release_id') if isinstance(rel, dict) else False,
                'parent_id': parent.id, 'parent_name': parent.name}

    @api.model
    def branch_discard(self, branch_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to discard branches.")}
        branch = self.env['hr.formula.config'].browse(int(branch_id))
        if not branch.exists() or not branch.parent_branch_id:
            return {'ok': False}
        branch.write({'branch_state': 'discarded', 'state': 'archived', 'active': False})
        return {'ok': True}

    # ==================================================================
    # B5 — Scheme variants (one master → many synced variants)
    # ==================================================================
    def _variant_overrides(self, variant):
        return set(c.strip().upper() for c in (variant.variant_override_codes or '').split(',') if c.strip())

    def _variant_same(self, vrule, mrule):
        if vrule.column_type == 'constant':
            return round(vrule.constant_value or 0.0, 6) == round(mrule.constant_value or 0.0, 6)
        return (vrule.excel_formula or '') == (mrule.excel_formula or '')

    def _variant_rows(self, variant):
        """Rows where a variant differs from its master OR is locally overridden.
        old = master value, new = variant value (so the diff reads master→variant)."""
        master = variant.master_config_id
        if not master:
            return {'changed': [], 'added': [], 'removed': []}
        ov = self._variant_overrides(variant)
        mmap = self._branch_value_map(master)
        vmap = self._branch_value_map(variant)
        changed = []
        for code, vrule in vmap.items():
            mrule = mmap.get(code)
            if not mrule:
                continue  # variant-only components surface under 'added'
            same = self._variant_same(vrule, mrule)
            overridden = code in ov
            if same and not overridden:
                continue  # in sync, nothing to show
            row = self._branch_row(code, vrule, mrule, False)  # brule=variant, prule=master
            row['overridden'] = overridden
            row['drift'] = (not same) and (not overridden)
            changed.append(row)
        added = [self._branch_row(c, vmap[c], None, False) for c in vmap if c not in mmap]
        removed = [self._branch_row(c, None, mmap[c], False) for c in mmap if c not in vmap]
        return {'changed': changed, 'added': added, 'removed': removed}

    def _variant_payload(self, v):
        rows = self._variant_rows(v)
        drift = sum(1 for r in rows['changed'] if r.get('drift'))
        return {
            'id': v.id, 'name': v.name, 'state': v.state,
            'employees': self._config_employee_count(v),
            'overrides': len(self._variant_overrides(v)), 'drift': drift,
            'added': len(rows['added']), 'removed': len(rows['removed']),
            'in_sync': drift == 0 and not rows['added'] and not rows['removed'],
        }

    @api.model
    def list_variants(self, config_id=None):
        """The variant relationships around the current config — its variants if
        it's a master, or its master + siblings if it's a variant."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        role = 'variant' if config.master_config_id else 'master'
        if role == 'variant':
            master = config.master_config_id
            variants = master.variant_ids
        else:
            master = config
            variants = config.variant_ids
        return {
            'ok': True, 'role': role,
            'current_id': config.id,
            'master': {'id': master.id, 'name': master.name, 'state': master.state},
            'variants': [self._variant_payload(v) for v in variants.sorted(key=lambda x: x.id)],
            'can_edit': self._can_edit(),
        }

    @api.model
    def variant_create(self, master_id, name=None, note=None):
        """Materialize a new variant of a master scheme (a draft copy that will
        be kept in sync). You cannot make a variant of a variant."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to create variants.")}
        master = self.env['hr.formula.config'].browse(int(master_id))
        if not master.exists():
            return {'ok': False}
        if master.master_config_id:
            return {'ok': False, 'msg': _("You can only create a variant of a master scheme, not of another variant.")}
        base_code = master.code or 'CFG'
        existing = set(self.env['hr.formula.config'].with_context(active_test=False)
                       .search([]).mapped('code'))
        code, i = base_code + '_V', 1
        while code in existing:
            i += 1
            code = '%s_V%s' % (base_code, i)
        variant = master.copy({
            'name': (name or '').strip() or (_("%s — variant") % master.name),
            'code': code, 'state': 'draft',
            'master_config_id': master.id, 'variant_override_codes': False,
        })
        return {'ok': True, 'variant_id': variant.id, 'name': variant.name}

    @api.model
    def variant_diff(self, variant_id):
        variant = self.env['hr.formula.config'].browse(int(variant_id))
        if not variant.exists() or not variant.master_config_id:
            return {'ok': False}
        rows = self._variant_rows(variant)
        return {'ok': True,
                'variant': {'id': variant.id, 'name': variant.name},
                'master': {'id': variant.master_config_id.id, 'name': variant.master_config_id.name},
                'changed': rows['changed'], 'added': rows['added'], 'removed': rows['removed'],
                'drift': sum(1 for r in rows['changed'] if r.get('drift')),
                'overrides': sum(1 for r in rows['changed'] if r.get('overridden')),
                'can_edit': self._can_edit()}

    def _variant_sync_one(self, variant):
        """Pull every non-overridden master component into the variant (only when
        it actually differs, to avoid version noise). Overrides are preserved."""
        master = variant.master_config_id
        if not master:
            return {'synced': 0, 'preserved': 0}
        ov = self._variant_overrides(variant)
        mmap = self._branch_value_map(master)
        vmap = self._branch_value_map(variant)
        column_map = {r.column_letter: r.code for r in variant.rule_ids if r.column_letter}
        seen = set()
        synced = 0
        for code, vrule in vmap.items():
            mrule = mmap.get(code)
            if not mrule or code in ov or self._variant_same(vrule, mrule):
                continue
            v = vrule.with_context(formula_version_reason='sync',
                                   formula_version_note=_("Synced from master %s") % master.name,
                                   formula_version_seen=seen)
            if vrule.column_type == 'constant':
                v.constant_value = mrule.constant_value or 0.0
            else:
                v.excel_formula = mrule.excel_formula or ''
                v.python_formula = v._convert_excel_to_python(v.excel_formula, column_map)
            synced += 1
        return {'synced': synced, 'preserved': len(ov & set(vmap.keys()))}

    @api.model
    def variant_sync(self, variant_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to sync variants.")}
        variant = self.env['hr.formula.config'].browse(int(variant_id))
        if not variant.exists() or not variant.master_config_id:
            return {'ok': False}
        r = self._variant_sync_one(variant)
        r.update({'ok': True, 'name': variant.name})
        return r

    @api.model
    def variant_push(self, master_id=None):
        """Push the master to every variant at once — the 'edit once, roll to all'
        primitive. Each variant keeps its own overrides."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to push to variants.")}
        config = self._pick_config(master_id)
        master = config.master_config_id or config
        if not master.variant_ids:
            return {'ok': False, 'msg': _("This scheme has no variants to push to.")}
        results = [dict(self._variant_sync_one(v), variant_id=v.id, name=v.name)
                   for v in master.variant_ids]
        return {'ok': True, 'results': results,
                'total_synced': sum(r['synced'] for r in results),
                'variants': len(results)}

    @api.model
    def variant_toggle_override(self, variant_id, code, on):
        """Protect (on) or release (off) a component from master sync."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to change overrides.")}
        variant = self.env['hr.formula.config'].browse(int(variant_id))
        if not variant.exists() or not variant.master_config_id:
            return {'ok': False}
        ov = self._variant_overrides(variant)
        cu = (code or '').strip().upper()
        if not cu:
            return {'ok': False}
        if on:
            ov.add(cu)
        else:
            ov.discard(cu)
        variant.variant_override_codes = ','.join(sorted(ov)) or False
        return {'ok': True, 'overrides': sorted(ov)}

    @api.model
    def variant_detach(self, variant_id):
        """Sever a variant from its master (it becomes a standalone mainline
        config; its current components are frozen as-is)."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to detach variants.")}
        variant = self.env['hr.formula.config'].browse(int(variant_id))
        if not variant.exists() or not variant.master_config_id:
            return {'ok': False}
        variant.write({'master_config_id': False, 'variant_override_codes': False})
        return {'ok': True}

    # ==================================================================
    # B7 — Client review portal (read-only trust surface via a token link)
    # ==================================================================
    def _review_url(self, token):
        base = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        return '%s/formula/review/%s' % (base, token)

    def _review_fmt(self, v, nf, cur):
        """Format a value by its number_format for the read-only page."""
        if v is None:
            return ''
        try:
            v = float(v)
        except (TypeError, ValueError):
            return str(v)
        if nf == 'percentage':
            return ('%g%%' % round(v * 100, 4))
        if nf == 'integer':
            return '{:,.0f}'.format(v)
        if nf == 'number':
            return '{:,.2f}'.format(v)
        return '%s%s' % (cur, '{:,.0f}'.format(v))

    def _review_preview(self, config):
        """A sample payslip preview for the review page — every appears-on-payslip
        component with its computed value, grouped Earnings / Deductions / Totals."""
        sample = config.sample_data_ids[:1]
        cur = config.currency_id.symbol if config.currency_id else '₫'
        if not sample:
            return {'ok': False, 'currency': cur, 'earnings': [], 'deductions': [], 'totals': [], 'sample_name': ''}
        try:
            inputs = json.loads(sample.input_values_json or '{}')
            vals = sample._evaluate_rules_with_dependencies(inputs)
        except Exception:
            inputs, vals = {}, {}
        earnings, deductions, totals = [], [], []
        for r in config.rule_ids.sorted(key=lambda x: x.sequence):
            if not r.appears_on_payslip:
                continue
            code = r.code
            v = vals.get(code)
            if v is None and r.column_type == 'constant':
                v = r.constant_value
            if v is None and r.column_type == 'input':
                v = inputs.get(code)
            try:
                v = float(v or 0)
            except (TypeError, ValueError):
                v = 0.0
            grp = _group_for(r)
            nf = r.number_format or 'currency'
            line = {'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or code,
                    'value': v, 'display': self._review_fmt(v, nf, cur)}
            if grp == 'Deductions':
                deductions.append(line)
            elif grp == 'Totals':
                totals.append(line)
            else:
                earnings.append(line)
        return {'ok': True, 'currency': cur, 'sample_name': sample.name or '',
                'earnings': earnings, 'deductions': deductions, 'totals': totals}

    def _review_components(self, config):
        """Read-only component catalogue grouped for the client."""
        out = []
        cur = config.currency_id.symbol if config.currency_id else '₫'
        for r in config.rule_ids.sorted(key=lambda x: x.sequence):
            if r.column_type not in ('formula', 'constant', 'input'):
                continue
            nf = r.number_format or 'currency'
            out.append({
                'col': r.column_letter or '', 'code': r.code or '',
                'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code,
                'type': r.column_type, 'group': _group_for(r),
                'formula': (r.excel_formula or '') if r.column_type == 'formula' else '',
                'value_display': self._review_fmt(r.constant_value, nf, cur) if r.column_type == 'constant' else '',
            })
        return out

    def _review_payload(self, share):
        """Everything the read-only review page renders — computed server-side."""
        config = share.config_id
        release = None
        if share.release_id and share.release_id.exists():
            rel = share.release_id
            release = {
                'id': rel.id, 'name': rel.name,
                'narrative': rel.narrative or '',
                'change_count': rel.change_count,
                'approved_by': rel.approved_by_id.name or '',
                'date': fields.Datetime.to_string(rel.approved_date) if rel.approved_date else '',
            }
        comments = [{
            'author_name': c.author_name, 'side': c.author_side,
            'body': c.body or '',
            'date': fields.Datetime.to_string(c.create_date) if c.create_date else '',
        } for c in share.comment_ids]
        country = dict(config._fields['country_code'].selection).get(config.country_code, '')
        return {
            'token': share.token,
            'config': {
                'name': config.name, 'country': country,
                'state': config.state, 'code': config.code or '',
                'component_count': len(config.rule_ids),
                'employees': self._config_employee_count(config),
                'score': self._score(config),
            },
            'client_name': share.client_name or '',
            'components': self._review_components(config),
            'preview': self._review_preview(config),
            'release': release,
            'signed_off': share.signed_off,
            'signed_off_name': share.signed_off_name or '',
            'signed_off_date': fields.Datetime.to_string(share.signed_off_date) if share.signed_off_date else '',
            'comments': comments,
            'company': (config.company_id.name if config.company_id else '') or 'Payobook',
        }

    # ---- share management (cockpit side) ----
    def _share_payload(self, s):
        if s.signed_off:
            status = 'signed'
        elif not s.active:
            status = 'revoked'
        elif s.expiry and s.expiry < fields.Datetime.now():
            status = 'expired'
        elif s.view_count:
            status = 'viewed'
        else:
            status = 'active'
        return {
            'id': s.id, 'token': s.token, 'url': self._review_url(s.token),
            'client_name': s.client_name or '', 'note': s.note or '',
            'release': s.release_id.name or '', 'release_id': s.release_id.id or False,
            'status': status, 'view_count': s.view_count or 0,
            'last_viewed': fields.Datetime.to_string(s.last_viewed) if s.last_viewed else '',
            'signed_off_name': s.signed_off_name or '',
            'signed_off_date': fields.Datetime.to_string(s.signed_off_date) if s.signed_off_date else '',
            'comment_count': len(s.comment_ids),
            'created': fields.Datetime.to_string(s.create_date) if s.create_date else '',
        }

    @api.model
    def create_review_share(self, config_id, release_id=None, client_name='', note=''):
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to share configurations.")}
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        vals = {'config_id': config.id, 'client_name': (client_name or '').strip(),
                'note': (note or '').strip()}
        if release_id:
            vals['release_id'] = int(release_id)
        share = self.env['hr.formula.review.share'].create(vals)
        return {'ok': True, 'share': self._share_payload(share)}

    @api.model
    def list_review_shares(self, config_id=None):
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'shares': []}
        shares = self.env['hr.formula.review.share'].with_context(active_test=False).search(
            [('config_id', '=', config.id)])
        releases = self.env['hr.formula.release'].search([('config_id', '=', config.id)])
        return {'ok': True, 'shares': [self._share_payload(s) for s in shares],
                'releases': [{'id': r.id, 'name': r.name} for r in releases],
                'can_edit': self._can_edit()}

    @api.model
    def revoke_review_share(self, share_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to revoke shares.")}
        share = self.env['hr.formula.review.share'].browse(int(share_id))
        if not share.exists():
            return {'ok': False}
        share.active = False
        return {'ok': True}

    # ---- portal actions (called by the public controller, token-validated) ----
    def _review_share_for(self, token):
        share = self.env['hr.formula.review.share'].sudo().search([('token', '=', token)], limit=1)
        return share if (share and share._is_live()) else self.env['hr.formula.review.share']

    @api.model
    def review_signoff(self, token, name):
        share = self._review_share_for(token)
        if not share or not share.release_id:
            return {'ok': False}
        share._record_signoff(name)
        self.env['hr.formula.review.comment'].sudo().create({
            'share_id': share.id, 'author_name': (name or '').strip() or _('Client'),
            'author_side': 'client',
            'body': _("✔ Signed off release “%s”.") % (share.release_id.name or ''),
        })
        return {'ok': True}

    @api.model
    def review_comment(self, token, name, body, side='client'):
        share = self._review_share_for(token)
        body = (body or '').strip()
        if not share or not body:
            return {'ok': False}
        self.env['hr.formula.review.comment'].sudo().create({
            'share_id': share.id, 'author_name': (name or '').strip() or _('Client'),
            'author_side': 'bureau' if side == 'bureau' else 'client', 'body': body,
        })
        return {'ok': True}

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
    # B8 — What-if sliders + cost projection (thin UI over F8's overlay sim)
    # ==================================================================
    @api.model
    def whatif_components(self, config_id=None):
        """The constant components a slider can vary (rates / multipliers / caps)."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        consts = [r for r in config.rule_ids.sorted(key=lambda r: r.sequence)
                  if r.column_type == 'constant' and r.code]
        items = [{
            'code': r.code,
            'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code,
            'col': r.column_letter or '',
            'value': r.constant_value or 0.0,
            'number_format': r.number_format or 'number',
            'group': _group_for(r),
        } for r in consts]
        return {'ok': True, 'components': items,
                'currency': config.currency_id.symbol if config.currency_id else '₫',
                'can_edit': self._can_edit()}

    @api.model
    def whatif_prepare(self, config_id, target_code, new_value, limit=None):
        """Create a what-if sim (a constant swapped to new_value) and return the
        payslip work-list. Pass a small ``limit`` for the interactive sampled
        feel; omit it for the exhaustive commit run (D-B8)."""
        Sim = self.env['hr.formula.simulation']
        created = Sim.sim_create(config_id, value_overrides={target_code: float(new_value)})
        if not created.get('ok'):
            return created
        prep = Sim.sim_prepare(created['sim_id'], limit=limit)
        config = self._pick_config(config_id)
        hr = config.rule_ids.filtered(lambda r: r.code == created.get('headline'))[:1]
        prep.update({
            'ok': True, 'headline': created.get('headline'),
            'headline_name': (hr.salary_rule_id.name if hr and hr.salary_rule_id else False)
                             or (hr.name if hr else '') or created.get('headline'),
            'sampled': bool(limit),
        })
        return prep

    @api.model
    def whatif_batch(self, payload):
        return self.env['hr.formula.simulation'].sim_batch(payload or {})

    @api.model
    def whatif_result(self, sim_id):
        return self.env['hr.formula.simulation'].sim_finalize(sim_id)

    @api.model
    def whatif_drop(self, sim_id):
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
        code = rule.code or ''
        tests = self._run_tests_after_save(config, [code] if code else None)
        sc.unlink()
        return {'ok': True, 'rule_id': rule.id, 'code': code, 'formula': formula,
                'tests': tests}

    @api.model
    def discard_scenario(self, scenario_id):
        sc = self.env['hr.formula.scenario'].browse(int(scenario_id))
        if sc.exists():
            sc.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # W104 — snippet library (reusable Excel fragments). CRUD only; the
    # ${CODE} → column-letter resolution happens client-side at insertion
    # time (D-F8). Writes are manager-guarded like every other studio write.
    # ------------------------------------------------------------------
    def _snippet_payload(self, s):
        return {
            'id': s.id, 'name': s.name or '', 'category': s.category or 'other',
            'body': s.body or '', 'description': s.description or '',
            'sequence': s.sequence, 'company_id': s.company_id.id or False,
        }

    @api.model
    def list_snippets(self):
        # shared library (no company) + this company's private snippets
        domain = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]
        snips = self.env['hr.formula.snippet'].search(domain)
        return [self._snippet_payload(s) for s in snips]

    @api.model
    def save_snippet(self, vals):
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can edit snippets.')}
        name = (vals.get('name') or '').strip()
        body = (vals.get('body') or '').strip()
        if not name or not body:
            return {'ok': False, 'msg': _('A snippet needs a name and a body.')}
        data = {
            'name': name, 'body': body,
            'category': vals.get('category') or 'other',
            'description': (vals.get('description') or '').strip(),
        }
        if vals.get('sequence') is not None:
            try:
                data['sequence'] = int(vals['sequence'])
            except (TypeError, ValueError):
                # C7: reject loudly, never silently drop a field the caller sent
                return {'ok': False, 'msg': _('Sequence must be a whole number.')}
        Snip = self.env['hr.formula.snippet']
        sid = vals.get('id')
        if sid:
            rec = Snip.browse(int(sid))
            if not rec.exists():
                return {'ok': False, 'msg': _('Snippet not found.')}
            rec.write(data)
        else:
            rec = Snip.create(data)
        return {'ok': True, 'snippet': self._snippet_payload(rec)}

    @api.model
    def delete_snippet(self, snippet_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can delete snippets.')}
        rec = self.env['hr.formula.snippet'].browse(int(snippet_id))
        if rec.exists():
            rec.unlink()
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
    def _slot_formula(self, formula, by_col, by_code):
        """W52 (D-J2): normalize an ``excel_formula`` to its logical skeleton.

        Strip ``=``, uppercase, drop whitespace, then replace every COMPONENT
        REFERENCE — cell-letter form (``A1``/``X2``), bare column letter
        (``A``/``X``), or code form (``BASIC``/``TXBASE``), resolved
        letter-first-then-code exactly like the engine — with positional slots
        ``§1, §2…`` in order of first occurrence. Numeric literals, operators,
        function names and string literals survive verbatim, so two formulas
        collide iff they are identical modulo which components they reference (a
        differing constant ⇒ different skeleton ⇒ no false group).

        Returns ``(slotted_str, n_refs)`` where ``n_refs`` is the count of
        distinct references (0 ⇒ no component logic to share). Pure text — never
        evaluates anything (TJ.2: zero evaluation in the path)."""
        f = (formula or '').strip()
        if f.startswith('='):
            f = f[1:]
        f = f.upper()
        # Mask string literals (content-sensitive, letter-free placeholder) so a
        # differing string still differs, but its letters are never slotted.
        def _mask(m):
            h = int(hashlib.md5(m.group(0).encode('utf-8')).hexdigest()[:8], 16)
            return '\x01%d\x01' % h
        f = re.sub(r'"[^"]*"', _mask, f)
        f = re.sub(r'\s+', '', f)
        slots = {}
        order = []

        def _rep(m):
            tok = m.group(0)
            # A function call — identifier immediately followed by '(' — is never
            # a component reference (protects a component coded like a function).
            if m.end() < len(f) and f[m.end()] == '(':
                return tok
            cell = re.match(r'^([A-Z]+)\d+$', tok)
            key = None
            if cell:
                letter = cell.group(1)
                if letter in by_col:
                    key = 'C:' + letter
            elif tok in by_col:          # bare column letter — resolve letter first
                key = 'C:' + tok
            elif tok in by_code:         # …then code (engine order)
                key = 'K:' + tok
            if key is None:
                return tok               # function/keyword/unknown → verbatim
            if key not in slots:
                slots[key] = len(order) + 1
                order.append(key)
            return '\xa7%d' % slots[key]

        # [A-Z][A-Z0-9]* (not [A-Z]+\d*) so an interior-digit code like T2X
        # stays ONE token instead of mis-splitting into T2 + X.
        slotted = re.sub(r'[A-Z][A-Z0-9]*', _rep, f)
        return slotted, len(order)

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

        def _add(kind, severity, title, detail, rule=None, col=None, note_id=None):
            problems.append({
                'key': '%s:%s' % (kind, note_id or (rule.id if rule else (col or len(problems)))),
                'kind': kind,
                'severity': severity,
                'title': title,
                'detail': detail,
                'rule_id': rule.id if rule else False,
                'col': (rule.column_letter if rule else col) or '',
                'code': (rule.code if rule else '') or '',
                'note_id': note_id or False,
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
        # D-J6: literals sitting inside a detected (consistent) progressive
        # IF-chain span are explained by the pending W54 simplify suggestion —
        # one cause, one card — so suppress the magic hint for exactly those
        # tokens. Detection is the cheap parse-only pass (no evaluation), so
        # get_problems stays eval-free.
        chains = self._detect_chains(rules)
        suppress = {}
        for r in rules:
            res = chains.get(r.id)
            if not res or not res.get('consistent'):
                continue
            s, e = res['span']
            span_txt = self._strip_for_lint((r.excel_formula or '')[s:e])
            suppress[r.id] = set(re.findall(r'(?<![A-Za-z0-9._])\d+(?:\.\d+)?', span_txt))
        from collections import Counter
        counter = Counter()
        rules_for_lit = {}
        for r in rules:
            if r.column_type != 'formula' or not r.excel_formula:
                continue
            seen_here = set()
            _drop = suppress.get(r.id, ())
            for tok in re.findall(r'(?<![A-Za-z0-9._])\d+(?:\.\d+)?', self._strip_for_lint(r.excel_formula)):
                if tok in _drop:
                    continue
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

        # 3c) W52 — duplicate-logic groups (D-J2). Token-normalized skeleton
        # hash; groups of >=2 formula components that are identical modulo which
        # components they reference. Detection only (v1) — extracting a shared
        # component changes downstream reference semantics, a human decision.
        # Zero evaluation, no LLM.
        by_code = {r.code: r for r in rules if r.code}
        dupe_groups = defaultdict(list)
        for r in rules:
            if r.column_type != 'formula' or not (r.excel_formula or '').strip():
                continue
            slotted, n_refs = self._slot_formula(r.excel_formula, by_col, by_code)
            if n_refs < 1:
                continue    # a formula referencing no component shares no logic
            h = hashlib.sha1(slotted.encode('utf-8')).hexdigest()
            dupe_groups[h].append(r)
        for members in dupe_groups.values():
            if len(members) < 2:
                continue
            members = sorted(members, key=lambda r: (r.sequence, r.id))
            cols = ', '.join('%s (%s)' % (m.column_letter or '?', m.code or '—')
                             for m in members)
            _add('dupe', 'hint',
                 _("%s components share this logic") % len(members),
                 _("These calculated components are identical apart from which "
                   "components they reference: %s. Consider a single shared "
                   "component — the references would change, so this is a manual "
                   "decision.") % cols,
                 rule=members[0])

        # 4) totals that are not shown on the payslip ----------------------
        for r in rules:
            if (r.column_type == 'formula' and _group_for(r) == 'Totals'
                    and not r.appears_on_payslip):
                _add('offpayslip', 'warning',
                     _("%s (%s) is a total but hidden") % (r.name or '', r.column_letter),
                     _("This looks like a total or net figure yet it is not shown on "
                       "the payslip. Employees will not see it."),
                     rule=r)

        # 5b) W83 — untested formula components (absence of a test is a smell,
        # not an error → hint tier). Reuses the deterministic coverage graph.
        cov = self.get_test_coverage(config.id)
        for u in cov.get('untested', []):
            rr = by_col.get(u.get('col'))
            if not rr:
                continue
            _add('untested', 'hint',
                 _("%s (%s) has no test") % (rr.name or '', rr.column_letter),
                 _("No sample asserts an expected value for this calculated "
                   "component (and nothing that is asserted depends on it) — "
                   "its result is unverified."),
                 rule=rr)

        # 5) open review notes (F15) — a note flagged for review stays in the
        # rail until someone resolves it (resolving keeps it in history).
        rule_by_id = {r.id: r for r in rules}
        for n in self.env['hr.formula.rule.note'].search(
                [('config_id', '=', config.id), ('is_review', '=', True),
                 ('resolved', '=', False)]):
            rr = rule_by_id.get(n.rule_id.id)
            if not rr:
                continue
            _add('note', 'warning',
                 _("Review note · %s (%s)") % (rr.name or '', rr.column_letter),
                 (n.body or '').strip()[:180], rule=rr, note_id=n.id)

        order = {'error': 0, 'warning': 1, 'hint': 2}
        problems.sort(key=lambda p: (order.get(p['severity'], 9),
                                     self._col_num(p.get('col') or 'ZZ')))
        counts = {'error': 0, 'warning': 0, 'hint': 0}
        for p in problems:
            counts[p['severity']] = counts.get(p['severity'], 0) + 1
        return {'ok': True, 'count': len(problems), 'counts': counts,
                'problems': problems}

    # ==================================================================
    # WP-J — W54 Simplification suggestions (detect → prove → offer → apply)
    # ==================================================================
    @api.model
    def _detect_chains(self, rules):
        """Shared cheap pass (D-J1): run the pure ``if_chain`` detector over each
        formula rule — parse + consistency ONLY, no evaluation. Returns
        ``{rule.id: detect_result}`` for rules whose ``excel_formula`` IS a
        progressive IF-chain (consistent or irregular). Used by BOTH the D-J6
        magic-hint suppression and the W54 suggestion RPC, so chain detection
        lives in one place."""
        from odoo.addons.pb_hr_payroll_formula.formula_engine import if_chain
        out = {}
        for r in rules:
            if r.column_type != 'formula' or not (r.excel_formula or '').strip():
                continue
            res = if_chain.detect(r.excel_formula)
            if res:
                out[r.id] = res
        return out

    @api.model
    def _rate_table_name(self, rule):
        return _("%s — rate table") % (rule.name or rule.code or rule.column_letter)

    @api.model
    def _gen_rate_table_code(self, config, rule):
        """C5-safe (D-J4): letters/digits only, deduped against existing rate
        table AND component codes. Reuses the WP-E `_dedupe_code_c5` deduper —
        one source, no logic fork."""
        existing = {(t.code or '').upper() for t in config.rate_table_ids if t.code}
        existing |= {(r.code or '').upper() for r in config.rule_ids if r.code}
        base = re.sub(r'[^A-Z0-9]', '', (rule.code or 'RATE').upper()) or 'RATE'
        if base[0].isdigit():
            base = 'R' + base
        base = (base + 'RATE')[:40]
        Wiz = self.env['hr.formula.multisheet.import.wizard']
        return Wiz._dedupe_code_c5(base, existing)

    @api.model
    def _find_reusable_table(self, config, brackets, eps=0.5):
        """A rate table in ``config`` whose brackets equal ``brackets`` (lowers
        within ``eps``, rates within 1e-9), else False. C7 honesty — the offer
        says which existing table it would reuse rather than minting a twin."""
        want = sorted((float(lo), float(ra)) for lo, ra in brackets)
        for t in config.rate_table_ids:
            got = sorted((b.lower, b.rate) for b in t.line_ids)
            if len(got) != len(want):
                continue
            if all(abs(g[0] - w[0]) <= eps and abs(g[1] - w[1]) <= 1e-9
                   for g, w in zip(got, want)):
                return t
        return False

    @api.model
    def _resolve_driver_rule(self, config, driver_text):
        """The single component a chain's driver references (cell-letter form
        ``AB2``, bare column letter, or code — engine order), or False for a
        COMPOUND driver expression (``MIN(A,B)``, operators). Only a single
        component can carry injected edge probes (D-J3)."""
        t = re.sub(r'\s+', '', (driver_text or '')).upper()
        m = re.fullmatch(r'([A-Z]+)(\d+)?', t)
        if not m:
            return False    # compound expression → probes not injectable
        by_col = {r.column_letter: r for r in config.rule_ids if r.column_letter}
        by_code = {r.code: r for r in config.rule_ids if r.code}
        letters = m.group(1)
        if m.group(2) is not None:          # cell form LETTERS+digits
            return by_col.get(letters) or False
        return by_col.get(letters) or by_code.get(letters) or False

    @api.model
    def _probe_edges(self, brackets):
        """Every bracket lower bound plus one synthetic edge just inside the top
        band — so each boundary is probed at −1/0/+1 (D-J3). For the VN PIT that
        is 8 edges × 3 = 24 probes."""
        lowers = sorted(float(lo) for lo, _ in brackets)
        if not lowers:
            return []
        step = (lowers[-1] - lowers[-2]) if len(lowers) > 1 else 1.0
        return lowers + [lowers[-1] + max(1.0, step)]

    def _eq_delta(self, rule, values, original, draft):
        """|original(values) − draft(values)| through the REAL evaluator
        (_run_formula overlay, no persistence — C12). None if either side fails
        to evaluate."""
        try:
            a = rule._run_formula(values, original, write_diagnostics=False)
            b = rule._run_formula(values, draft, write_diagnostics=False)
            return abs(float(a) - float(b))
        except Exception:
            return None

    @api.model
    def _equivalence_check(self, rule, brackets, driver_text, span_start, span_end):
        """D-J3 gate: prove the BRACKET rewrite evaluates identically to the
        original on every sample row (confirmed or not) PLUS synthetic edge
        probes when the driver is a single component. The draft INLINES the exact
        Excel the committed table will emit (``compile_brackets_excel``), so the
        proof matches the apply. Read-only."""
        from odoo.addons.pb_hr_payroll_formula.models.formula_rate_table import (
            compile_brackets_excel,
        )
        EPS = 0.005
        original = rule.excel_formula or ''
        compiled = compile_brackets_excel(brackets, driver_text)
        draft = original[:span_start] + '(' + compiled + ')' + original[span_end:]

        max_delta = 0.0
        samples_total = samples_matched = 0
        for smp in rule.config_id.sample_data_ids:
            try:
                # readonly=True — this runs from the Problems rail on every
                # panel open; sample-value acquisition must never stamp
                # write_date on production rules (M2, WP-J review).
                vals = smp._evaluate_rules_with_dependencies(
                    smp.get_input_values(), readonly=True)
            except Exception:
                continue
            d = self._eq_delta(rule, vals, original, draft)
            if d is None:
                continue
            samples_total += 1
            max_delta = max(max_delta, d)
            if d < EPS:
                samples_matched += 1

        drule = self._resolve_driver_rule(rule.config_id, driver_text)
        driver_kind = 'compound'
        probes_total = probes_matched = 0
        if drule:
            driver_kind = 'input' if drule.column_type == 'input' else 'computed'
            for edge in self._probe_edges(brackets):
                for x in (edge - 1.0, edge, edge + 1.0):
                    d = self._eq_delta(rule, {drule.code: x}, original, draft)
                    if d is None:
                        continue
                    probes_total += 1
                    max_delta = max(max_delta, d)
                    if d < EPS:
                        probes_matched += 1

        evidence = samples_total + probes_total
        ok = bool(evidence > 0
                  and samples_matched == samples_total
                  and probes_matched == probes_total)
        return {
            'ok': ok, 'driver_kind': driver_kind, 'max_delta': max_delta,
            'samples_total': samples_total, 'samples_matched': samples_matched,
            'probes_total': probes_total, 'probes_matched': probes_matched,
        }

    @api.model
    def get_simplify_suggestions(self, config_id=None):
        """W54 (D-J3): detect progressive IF-chains, PROVE equivalence to a
        ``BRACKET`` rewrite through the real evaluator, and return offers.
        Read-only — nothing is persisted. Consistent+equivalent chains carry
        ``can_apply``; irregular or unproven chains are LISTED with a reason,
        never offered a rewrite (C7).

        Shape: ``{ok, suggestions: [{rule_id, col, code, name, consistent,
        can_apply, driver, driver_kind, span, brackets, table:{code,name,reuse,
        reuse_of}, equivalence:{…}, before, after, reason}]}``"""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'suggestions': []}
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        chains = self._detect_chains(rules)
        rule_by_id = {r.id: r for r in rules}
        suggestions = []
        for rid, res in chains.items():
            rule = rule_by_id[rid]
            brackets = [(b['lower'], b['rate']) for b in res['brackets']]
            driver_text = res['driver']
            s, e = res['span']
            item = {
                'rule_id': rid, 'col': rule.column_letter or '', 'code': rule.code or '',
                'name': rule.name or rule.column_letter or '',
                'consistent': bool(res.get('consistent')),
                'driver': driver_text, 'span': [s, e],
                'brackets': res['brackets'], 'before': rule.excel_formula or '',
            }
            if not res.get('consistent'):
                item.update({'can_apply': False, 'reason': res.get('reason'),
                             'driver_kind': None, 'equivalence': None,
                             'table': None, 'after': None})
                suggestions.append(item)
                continue
            reuse = self._find_reusable_table(config, brackets)
            tcode = reuse.code if reuse else self._gen_rate_table_code(config, rule)
            after = (rule.excel_formula[:s]
                     + 'BRACKET(%s,%s)' % (tcode, driver_text)
                     + rule.excel_formula[e:])
            eq = self._equivalence_check(rule, brackets, driver_text, s, e)
            item.update({
                'can_apply': eq['ok'],
                'driver_kind': eq['driver_kind'],
                'equivalence': {k: eq[k] for k in (
                    'samples_total', 'samples_matched', 'probes_total',
                    'probes_matched', 'max_delta')},
                'table': {'code': tcode,
                          'name': reuse.name if reuse else self._rate_table_name(rule),
                          'reuse': bool(reuse),
                          'reuse_of': reuse.code if reuse else None},
                'after': after,
                'reason': None if eq['ok'] else (
                    _("No evidence to prove equivalence — the config has no "
                      "usable samples and the driver is not probeable — not "
                      "offered.")
                    if (eq['samples_total'] + eq['probes_total']) == 0 else
                    _("Could not prove the rewrite is equivalent (max Δ %.4f) "
                      "— not offered.") % eq['max_delta']),
            })
            suggestions.append(item)
        return {'ok': True, 'suggestions': suggestions}

    @api.model
    def simplify_apply(self, rule_id):
        """W54 apply (D-J3/D-J4): create-or-reuse the rate table, rewrite ONLY
        the detected span to ``BRACKET(code, driver)`` (wrapper survives
        verbatim), stamp version reason ``refactor`` (C4), and re-run W82 tests
        (a refactor is a save). Atomic — table + rewrite in one savepoint.
        Manager-gated; re-proves equivalence defensively before touching data."""
        from odoo.addons.pb_hr_payroll_formula.formula_engine import if_chain
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False, 'msg': _("Component not found.")}
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to edit this configuration.")}
        config = rule.config_id
        res = if_chain.detect(rule.excel_formula or '')
        if not res or not res.get('consistent'):
            return {'ok': False, 'msg': _("This formula is no longer a consistent progressive chain.")}
        brackets = [(b['lower'], b['rate']) for b in res['brackets']]
        driver_text = res['driver']
        s, e = res['span']
        eq = self._equivalence_check(rule, brackets, driver_text, s, e)
        if not eq['ok']:
            return {'ok': False,
                    'msg': _("Could not prove the rewrite is equivalent — not applied.")}
        original = rule.excel_formula
        with self.env.cr.savepoint():
            reuse = self._find_reusable_table(config, brackets)
            if reuse:
                table, reused = reuse, True
            else:
                table = self.env['hr.formula.rate.table'].create({
                    'name': self._rate_table_name(rule),
                    'code': self._gen_rate_table_code(config, rule),
                    'config_id': config.id,
                    'line_ids': [(0, 0, {'lower': lo, 'rate': ra}) for lo, ra in brackets],
                })
                reused = False
            new_formula = (original[:s] + 'BRACKET(%s,%s)' % (table.code, driver_text)
                           + original[e:])
            rule.with_context(formula_version_reason='refactor').write(
                {'excel_formula': new_formula})
        tests = config.run_sample_tests(changed_codes={rule.code})
        return {'ok': True, 'reused': reused, 'table_code': table.code,
                'brackets': len(brackets), 'new_formula': new_formula,
                'tests': tests,
                'msg': (_("Reused rate table %s.") % table.code if reused
                        else _("Created rate table %s (%s brackets).")
                        % (table.code, len(brackets)))}

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
    # F10 — Unified Mapping Canvas (adapter 1: mid→end cycle mapping)
    # ------------------------------------------------------------------
    def _cycle_pair(self, config):
        """Given any config, resolve its (mid_cycle, end_cycle) sibling pair.
        Pairs by pb_division (the pb_* demo world) else structure_id, within the
        same company. Returns (mid, end) records or (empty, empty)."""
        Config = self.env['hr.formula.config']
        empty = Config.browse()
        ct = config.cycle_type
        if ct not in ('mid_cycle', 'end_cycle'):
            return empty, empty
        want = 'end_cycle' if ct == 'mid_cycle' else 'mid_cycle'
        dom = [('cycle_type', '=', want), ('id', '!=', config.id)]
        if config.company_id:
            dom.append(('company_id', '=', config.company_id.id))
        cands = Config.search(dom)
        sibling = empty
        div = getattr(config, 'pb_division', False)
        if div:
            sibling = cands.filtered(lambda c: getattr(c, 'pb_division', False) == div)[:1]
        if not sibling and config.structure_id:
            sibling = cands.filtered(lambda c: c.structure_id.id == config.structure_id.id)[:1]
        if not sibling and cands:
            # name-prefix heuristic: everything before the em/en dash
            def prefix(n):
                return re.split(r'[—–-]', n or '', 1)[0].strip().lower()
            p = prefix(config.name)
            sibling = cands.filtered(lambda c: prefix(c.name) == p)[:1]
        if not sibling:
            return empty, empty
        return (config, sibling) if ct == 'mid_cycle' else (sibling, config)

    def _mc_item(self, rule):
        """One MappingCanvas item — payroll-agnostic {id, label, sublabel, meta}."""
        return {
            'id': rule.id,
            'label': (rule.salary_rule_id.name if rule.salary_rule_id else False) or rule.name or rule.code or '(unnamed)',
            'sublabel': rule.code or '',
            'meta': {'col': rule.column_letter or '', 'type': rule.column_type or '',
                     'group': _group_for(rule)},
        }

    @api.model
    def mapping_canvas_data(self, config_id=None):
        """Feed the cycle-mapping surface: left = mid-cycle components, right =
        end-cycle components, wires = accepted mappings + proposed suggestions."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'reason': 'no_config'}
        mid, end = self._cycle_pair(config)
        if not (mid and end):
            return {'ok': False, 'reason': 'no_pair',
                    'config': {'id': config.id, 'name': config.name,
                               'cycle_type': config.cycle_type}}
        left = [self._mc_item(r) for r in mid.rule_ids.sorted(key=lambda r: r.sequence)]
        right = [self._mc_item(r) for r in end.rule_ids.sorted(key=lambda r: r.sequence)]
        Mapping = self.env['hr.payroll.cycle.component.mapping']
        Sug = self.env['hr.payroll.cycle.mapping.suggestion']
        base = [('mid_cycle_config_id', '=', mid.id), ('end_cycle_config_id', '=', end.id)]
        wires = []
        for m in Mapping.search(base):
            wires.append({'id': 'm%s' % m.id, 'kind': 'mapping', 'ref': m.id,
                          'leftId': m.mid_component_id.id, 'rightId': m.end_component_id.id,
                          'state': 'accepted'})
        for s in Sug.search(base + [('state', '=', 'proposed')]):
            wires.append({'id': 's%s' % s.id, 'kind': 'suggestion', 'ref': s.id,
                          'leftId': s.mid_component_id.id, 'rightId': s.end_component_id.id,
                          'state': 'suggested',
                          'confidence': round(s.confidence or 0.0, 4),
                          'reason': s.match_reason or ''})
        return {
            'ok': True,
            'mid': {'id': mid.id, 'name': mid.name},
            'end': {'id': end.id, 'name': end.name},
            'left': left, 'right': right, 'wires': wires,
            'left_title': mid.name, 'right_title': end.name,
            'subtitle': _("Carry values from %s into %s") % (mid.name, end.name),
            'supports_suggest': True,
            'can_edit': self._can_edit(),
        }

    @api.model
    def mapping_suggest(self, config_id=None):
        """(Re)generate proposed suggestions for the config's cycle pair."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        mid, end = self._cycle_pair(config)
        if not (mid and end):
            return {'ok': False, 'reason': 'no_pair'}
        wiz = self.env['hr.payroll.cycle.component.mapping.wizard'].create({
            'mid_cycle_config_id': mid.id, 'end_cycle_config_id': end.id})
        wiz.action_suggest_mappings()
        return self.mapping_canvas_data(config.id)

    @api.model
    def mapping_accept(self, suggestion_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        s = self.env['hr.payroll.cycle.mapping.suggestion'].browse(int(suggestion_id))
        if not s.exists():
            return {'ok': False}
        s.action_accept()
        return {'ok': True}

    @api.model
    def mapping_reject(self, suggestion_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        s = self.env['hr.payroll.cycle.mapping.suggestion'].browse(int(suggestion_id))
        if s.exists():
            s.action_reject()
        return {'ok': True}

    @api.model
    def mapping_create(self, config_id, mid_component_id, end_component_id):
        """Draw a wire = create a mapping between a mid and an end component."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        config = self._pick_config(config_id)
        mid, end = self._cycle_pair(config) if config else (None, None)
        if not (mid and end):
            return {'ok': False, 'reason': 'no_pair'}
        Mapping = self.env['hr.payroll.cycle.component.mapping']
        midc = self.env['hr.formula.rule'].browse(int(mid_component_id))
        endc = self.env['hr.formula.rule'].browse(int(end_component_id))
        if midc.config_id != mid or endc.config_id != end:
            return {'ok': False, 'msg': _("Components must belong to the paired configs.")}
        # respect the one-mid-one-end uniqueness: drop any existing wire on either side
        Mapping.search([('mid_cycle_config_id', '=', mid.id), ('end_cycle_config_id', '=', end.id),
                        '|', ('mid_component_id', '=', midc.id),
                        ('end_component_id', '=', endc.id)]).unlink()
        Mapping.create({'mid_cycle_config_id': mid.id, 'end_cycle_config_id': end.id,
                        'mid_component_id': midc.id, 'end_component_id': endc.id})
        return {'ok': True}

    @api.model
    def mapping_delete(self, mapping_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        m = self.env['hr.payroll.cycle.component.mapping'].browse(int(mapping_id))
        if m.exists():
            m.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # F10 adapter 2 — API/integration field mapping (source fields → inputs)
    # ------------------------------------------------------------------
    @staticmethod
    def _norm(s):
        return re.sub(r'[^a-z0-9]', '', (s or '').lower())

    @api.model
    def _dt_label(self, data_type):
        """The human label of a data type, from the store's OWN selection — the
        one list `hr.integration.endpoint` imports rather than retyping."""
        if not data_type:
            return ''
        sel = dict(self.env['hr.api.data.store']._fields['data_type'].selection)
        return sel.get(data_type, data_type)

    @staticmethod
    def _as_id(value):
        """An id from an arrival CONTEXT, or 0.

        `pb_connector`/`pb_endpoint`/`pb_config` are written into a context by
        whoever built the link and read back out of the browser, so they are
        not guaranteed to be numbers — a hand-built or stale deep link can
        carry a name, a list, or `None`. `int()` on that is a 500 on a screen
        whose whole job is to be the friendly front door, so it is asked
        politely and answered with "nothing was specified" (which the caller
        then reports through `fell_back` rather than swallowing).
        """
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _sample_text(value):
        """A sample value as one short, printable line.

        "What the data actually looks like" is the whole point of the second
        line under a source field, so a dict or a 400-character blob has to
        become something a 340px column can show. Trimmed rather than dropped:
        an elided value still tells the reader the shape of what arrives.
        """
        if value is None or value is False or value == '':
            return ''
        if isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, ensure_ascii=False, default=str)
            except Exception:
                value = str(value)
        text = str(value).strip().replace('\n', ' ')
        return text if len(text) <= 48 else text[:45] + '…'

    @api.model
    def _config_for_connector(self, connector_id):
        """The scheme this connector feeds most, or 0.

        `_api_active_connector` answers the mirror question (given a config,
        which connector) and this is the same arithmetic run the other way, for
        the deep link that names a connector and no scheme. Ties go to the
        lowest config id so the answer is STABLE — a resolver that returns a
        different scheme on alternate clicks is worse than one that returns a
        plain default.
        """
        FM = self.env['hr.integration.field.mapping']
        counts = defaultdict(int)
        for m in FM.search([('connector_id', '=', self._as_id(connector_id))]):
            cfg = m.target_rule_id.config_id
            if cfg:
                counts[cfg.id] += 1
        if not counts:
            return 0
        return max(sorted(counts), key=lambda cid: counts[cid])

    @api.model
    def mapping_pickers(self, arrival=None):
        """Everything the Mapping Studio's FROM/TO pickers offer, in one call.

        Read with the CALLER's own rights — `search([])` applies the record
        rules, which is the same scope `pb.integrations._readable_connectors`
        settles on, and for the same reason: the honest answer to "which
        connectors are there" is "the ones you may read". A caller with no
        read ACL at all gets the ORM's own AccessError; this method does not
        catch it into a plausible-looking empty list.

        It also RESOLVES the arrival context, and reports what it could not
        honour. A deep link that silently lands on a different scheme is the
        worst bug class this codebase has (W76.3, W117): the reader believes
        the header. So an unresolvable `config_id` falls back AND says so in
        `defaults.fell_back`, which the studio renders as a visible notice.
        """
        arrival = dict(arrival or {})
        Conn = self.env['hr.integration.connector']
        Config = self.env['hr.formula.config']

        cons = Conn.search([], order='name')
        # ONE search and ONE batched compute for every feed on the board. Read
        # per connector, `_compute_counts` would run its three `_read_group`s
        # once per row — twenty-five connectors is seventy-five queries for a
        # dropdown (W53's shape: the payload a picker needs is one query, not
        # one query per option).
        by_conn_eps = defaultdict(list)
        all_eps = self._api_endpoints(cons) if cons else None
        for e in (all_eps or []):
            by_conn_eps[e.connector_id.id].append({
                'id': e.id, 'name': e.name or e.code or '',
                'code': e.code or '', 'data_type': e.data_type or '',
                'data_type_label': self._dt_label(e.data_type),
                'mapping_count': e.mapping_count,
                'staged': e.staged_count, 'synced': e.synced_count,
                'last_sync': fields.Datetime.to_string(e.last_sync) if e.last_sync else '',
                'status': e.last_sync_status or '',
            })
        connectors = [{
            'id': c.id, 'name': c.name or '—',
            'type': c.connector_type or '',
            'status': c.connection_status or 'disconnected',
            'mapping_count': len(c.field_mapping_ids),
            'last_sync': fields.Datetime.to_string(c.last_sync) if c.last_sync else '',
            'endpoints': by_conn_eps.get(c.id, []),
        } for c in cons]

        configs = []
        for cfg in Config.search([], order='sequence, id desc'):
            rules = cfg.rule_ids
            configs.append({
                'id': cfg.id, 'name': cfg.name or '—', 'code': cfg.code or '',
                'country': cfg.country_code or '', 'state': cfg.state or '',
                'active': bool(cfg.active),
                'column_count': len(rules),
                'input_count': len(rules.filtered(lambda r: r.column_type == 'input')),
            })

        Batch = self.env['hr.payroll.import.batch']
        batches = [{'id': b.id, 'name': b.name or '—'}
                   for b in Batch.search([], order='id desc', limit=60)]

        # ---- arrival resolution ------------------------------------------
        fell_back = []
        by_conn = {c['id']: c for c in connectors}
        cid = self._as_id(arrival.get('connector_id'))
        if cid and cid not in by_conn:
            fell_back.append('connector')
            cid = 0
        cfg_id = self._as_id(arrival.get('config_id'))
        if cfg_id and cfg_id not in {c['id'] for c in configs}:
            fell_back.append('config')
            cfg_id = 0
        if not cfg_id and cid:
            # A link that arrives naming a CONNECTOR and no scheme is the board
            # card's "6 mappings" being clicked. Landing on the default scheme
            # then answers "0 mapped" to a user who clicked the number six —
            # the board and the studio contradicting each other on the very
            # click that joins them. So the scheme is resolved to the one this
            # connector actually feeds.
            cfg_id = self._config_for_connector(cid)
        if not cfg_id:
            cfg = self._pick_config(None)
            cfg_id = cfg.id if cfg else 0
        if not cid:
            conn = self._api_active_connector(Config.browse(cfg_id))
            cid = conn.id if conn else 0
        if cid and cid not in by_conn:
            # `_api_active_connector` counts mappings and browses the winner by
            # id, so it can name a connector the record rules hide from this
            # caller. The picker must never open on an option it does not list.
            cid = connectors[0]['id'] if connectors else 0
        eid = self._as_id(arrival.get('endpoint_id'))
        ep_ids = {e['id'] for e in (by_conn.get(cid, {}).get('endpoints') or [])}
        if eid and eid not in ep_ids:
            fell_back.append('endpoint')
            eid = 0

        return {
            'ok': True,
            'connectors': connectors, 'configs': configs, 'batches': batches,
            'defaults': {'connector_id': cid, 'endpoint_id': eid,
                         'config_id': cfg_id, 'fell_back': fell_back},
            'can_edit': self._can_edit(),
        }

    def _api_active_connector(self, config, connector_id=None):
        Conn = self.env['hr.integration.connector']
        if connector_id:
            c = Conn.browse(int(connector_id))
            return c if c.exists() else Conn.browse()
        input_ids = config.rule_ids.filtered(lambda r: r.column_type == 'input').ids
        FM = self.env['hr.integration.field.mapping']
        # the connector with the most mappings already targeting this config's inputs
        maps = FM.search([('target_rule_id', 'in', input_ids)])
        if maps:
            counts = defaultdict(int)
            for m in maps:
                counts[m.connector_id.id] += 1
            best = max(counts, key=counts.get)
            return Conn.browse(best)
        # else a connector referenced by an input rule, else the first connector
        for r in config.rule_ids:
            if getattr(r, 'integration_connector_id', False):
                return r.integration_connector_id
        return Conn.search([], limit=1)

    def _api_endpoints(self, connectors):
        """These connectors' feeds, or `None` on a database that has no feeds
        TABLE yet.

        Cycle 1's degrade rail, reused verbatim: the addons tree is SHARED by
        every database on the box and the schema is created by each database's
        own upgrade, so `'hr.integration.endpoint' in self.env` is True in the
        gap between the two and a query would raise `UndefinedTable` — which,
        caught, still leaves the whole request's transaction aborted. `None`
        (not an empty recordset) so a caller can tell "this database has no
        feeds table" from "this connector has no feeds" (W79).
        """
        if 'hr.integration.endpoint' not in self.env:
            return None
        EP = self.env['hr.integration.endpoint']
        if not EP._schema_ready():
            return None
        return EP.search([('connector_id', 'in', connectors.ids)])

    @api.model
    def api_mapping_data(self, config_id=None, connector_id=None, endpoint_id=None):
        """The API board, optionally narrowed to ONE feed.

        Integrations Cycle 2 gave the connector's feeds an axis of their own.
        Passing `endpoint_id` narrows the LEFT column to the fields that feed
        actually delivers and the wires to the mappings that name it — with one
        deliberate exception: a mapping drawn before feeds existed carries no
        `endpoint_id`, and dropping it here would make an operator's existing
        work disappear the first time they picked a feed. Those legacy wires
        are kept, and their source paths are added to the left column under an
        "Unassigned" group, so the board says where they came from instead of
        silently losing them (W79: absent must not be indistinguishable from
        broken).
        """
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'reason': 'no_config'}
        Conn = self.env['hr.integration.connector']
        conn = self._api_active_connector(config, connector_id)
        contexts = [{'id': c.id, 'name': c.name} for c in Conn.search([], order='name')]
        if not conn:
            return {'ok': False, 'reason': 'no_connector', 'contexts': contexts}
        FM = self.env['hr.integration.field.mapping']
        eps = self._api_endpoints(conn)
        ep = None
        ep_wanted = self._as_id(endpoint_id)
        if ep_wanted and eps is not None:
            cand = eps.filtered(lambda e: e.id == ep_wanted)
            ep = cand[:1] or None
        endpoints = [{'id': e.id, 'name': e.name or e.code or '', 'code': e.code or '',
                      'data_type': e.data_type or '',
                      'data_type_label': self._dt_label(e.data_type),
                      'mapping_count': e.mapping_count, 'staged': e.staged_count,
                      'synced': e.synced_count,
                      'last_sync': fields.Datetime.to_string(e.last_sync) if e.last_sync else '',
                      'status': e.last_sync_status or ''}
                     for e in (eps or [])]
        try:
            fields_ = FM.get_available_source_fields(
                conn.id, ep.data_type if ep else None,
                ep.id if ep else None) or []
        except Exception as e:
            # The `except` stays — a board that renders with an empty FROM
            # column beats a 500 — but it no longer stays SILENT. Cycle 6 shipped
            # an AttributeError inside discovery and this branch turned it into
            # nothing at all: no error, no log line, a column of zero fields,
            # and the honesty banner underneath still counting fifteen mappings
            # as unresolvable. It took a live browser pass to find, because a
            # swallowed exception has no other symptom (W40's shape, W152).
            _logger.warning(
                "Source-field discovery failed for connector %s (feed %s): "
                "%s: %s — the FROM column will render empty.",
                conn.id, (ep.code if ep else 'all'), type(e).__name__, e)
            fields_ = []
        ep_group = (ep.name or ep.code) if ep else ''
        # Integrations Cycle 6 — every card says where it came from. `prov` is
        # promoted to a top-level key rather than buried in `meta` because the
        # canvas renders a chip from it on every row, and `meta` is the bag of
        # things only the transform popover reads.
        left = [{'id': 'f:' + f['path'], 'label': f.get('label') or f['path'],
                 'sublabel': f['path'],
                 'sample': self._sample_text(f.get('sample')),
                 'group': ep_group,
                 'prov': f.get('provenance') or 'live',
                 'provKind': f.get('catalog_kind') or '',
                 'drift': bool(f.get('expected_missing')),
                 'note': f.get('notes') or '',
                 'meta': {'type': f.get('type') or '', 'sample': f.get('sample')}}
                for f in fields_]
        input_rules = config.rule_ids.filtered(lambda r: r.column_type == 'input') \
            .sorted(key=lambda r: r.sequence)
        right = [{'id': r.id, 'label': (r.name or r.code), 'sublabel': r.code or '',
                  'meta': {'col': r.column_letter or '', 'type': 'input'}}
                 for r in input_rules]
        # accepted wires = persisted field mappings on this connector → these inputs
        wires = []
        mapped_paths, mapped_rules = set(), set()
        dom = [('connector_id', '=', conn.id),
               ('target_rule_id', 'in', input_rules.ids)]
        if ep:
            # this feed's own mappings, PLUS the ones that predate feeds
            dom = dom + ['|', ('endpoint_id', '=', ep.id), ('endpoint_id', '=', False)]
        present = {i['id'] for i in left}
        for m in FM.search(dom):
            lid = 'f:' + (m.source_field or '')
            wires.append({'id': 'm%s' % m.id, 'kind': 'mapping', 'ref': m.id,
                          'leftId': lid, 'rightId': m.target_rule_id.id,
                          'state': 'accepted',
                          'transform': self._transform_payload(m)})   # W62 (D-I2)
            if ep and lid not in present:
                # a legacy (or foreign-feed) wire whose source is not in this
                # feed's field list — shown, and labelled for what it is
                left.append({'id': lid, 'label': (m.source_field_label
                                                  or m.source_field or lid),
                             'sublabel': m.source_field or '',
                             'sample': self._sample_text(m.source_sample_value),
                             'group': _("Unassigned"),
                             'prov': 'mapping', 'provKind': '', 'drift': False,
                             'note': '', 'meta': {'type': ''}})
                present.add(lid)
            mapped_paths.add(m.source_field or '')
            mapped_rules.add(m.target_rule_id.id)
        # suggested wires = best name match between an unmapped source field and an
        # unmapped input rule (computed live, not persisted)
        rule_norms = [(r, self._norm(r.code), self._norm(r.name)) for r in input_rules
                      if r.id not in mapped_rules]
        for f in fields_:
            path = f['path']
            if path in mapped_paths:
                continue
            fn = self._norm(path)
            fl = self._norm(f.get('label'))
            best, conf = None, 0.0
            for r, rc, rn in rule_norms:
                if not rc:
                    continue
                if fn == rc or fl == rc:
                    c = 1.0
                elif rc and (rc in fn or fn in rc):
                    c = 0.85
                elif rn and (rn == fn or rn in fn or fn in rn):
                    c = 0.8
                else:
                    c = 0.0
                if c > conf:
                    best, conf = r, c
            if best and conf >= 0.8 and best.id not in mapped_rules:
                wires.append({'id': 'sug:%s>%s' % (path, best.id), 'kind': 'suggestion',
                              'ref': None, 'source': path,
                              'leftId': 'f:' + path, 'rightId': best.id,
                              'state': 'suggested', 'confidence': round(conf, 2),
                              'reason': _('Name match')})
                mapped_rules.add(best.id)   # one suggestion per input rule
        return {
            'ok': True, 'left': left, 'right': right, 'wires': wires,
            'left_title': '%s · source fields' % conn.name,
            'right_title': '%s · inputs' % config.name,
            'subtitle': _("Map %s fields onto this scheme's input components") % conn.name,
            'supports_suggest': False,
            'contexts': contexts, 'context_id': conn.id,
            'endpoints': endpoints, 'endpoint_id': ep.id if ep else False,
            'source_summary': self._source_summary(conn, ep, fields_),
            'can_edit': self._can_edit(),
        }

    def _source_summary(self, conn, ep, fields_):
        """What the FROM column's sub-line is entitled to say.

        Cycle 5's sub-line read `206 fields · never synced`, and both halves
        were true while the sentence as a whole was a lie: the 206 were Odoo's,
        and the reader had every reason to think they were Zoho's. The rule now
        is that the count and its ORIGIN have to agree, so the origin is
        computed here — beside the list it describes — rather than inferred in
        the browser from a number.

        `fetch` is a capability, not a credential: it is three booleans and a
        sentence, and no value of `api_key`, `password` or either token can
        reach this payload (`_has_credentials` sudo-reads them and returns a
        bool).
        """
        counts = {}
        for f in fields_:
            counts[f.get('provenance') or 'live'] = \
                counts.get(f.get('provenance') or 'live', 0) + 1
        drift = len([f for f in fields_ if f.get('expected_missing')])
        try:
            cap = conn.field_fetch_capability()
        except Exception:                 # pragma: no cover — older server
            cap = {'mode': None, 'ready': False, 'reason': ''}
        return {
            'total': len(fields_),
            'live': counts.get('live', 0),
            'catalog': counts.get('catalog', 0),
            'odoo': counts.get('odoo', 0),
            'drift': drift,
            'vendor': conn.name or '',
            'feed': (ep.name or ep.code) if ep else '',
            'last_sync': (fields.Datetime.to_string(ep.last_sync)
                          if (ep and ep.last_sync) else ''),
            'ever_synced': bool(
                self.env['hr.api.data.store'].search_count(
                    [('connector_id', '=', conn.id)])),
            'fetch_mode': cap.get('mode') or '',
            'fetch_ready': bool(cap.get('ready')),
            'fetch_reason': cap.get('reason') or '',
        }

    # `_infer_source_type`'s vocabulary is not the mapping's. The store infers
    # `string/integer/float/boolean/date/datetime/list`; the field carries
    # `string/number/integer/float/date/datetime/boolean/currency`. `list` and
    # anything unrecognised fall through to no opinion rather than to a wrong
    # one — `source_data_type` decides whether `preview_transform` parses the
    # sample as a float, so a guess here is a preview that disagrees with sync.
    _SRC_TYPE = {'string': 'string', 'integer': 'integer', 'float': 'float',
                 'boolean': 'boolean', 'date': 'date', 'datetime': 'datetime'}

    def _discovered_sample(self, conn, path, endpoint=None):
        """What the board is already showing for `path`, as writable vals.

        Returns `{}` when the field is not in the discovered set (a template
        line naming a path this connector has never delivered, say) — an absent
        sample is the honest answer, and `preview_transform` already has a
        first-class "no sample stored" branch for it.
        """
        FM = self.env['hr.integration.field.mapping']
        try:
            fields_ = FM.get_available_source_fields(
                conn.id, endpoint.data_type if endpoint else None,
                endpoint.id if endpoint else None) or []
        except Exception:
            return {}
        found = next((f for f in fields_ if f.get('path') == path), None)
        if not found:
            return {}
        vals = {}
        text = self._sample_text(found.get('sample'))
        if text:
            vals['source_sample_value'] = text
        t = self._SRC_TYPE.get(found.get('type'))
        if t:
            vals['source_data_type'] = t
        return vals

    @api.model
    def api_mapping_create(self, config_id, connector_id, source_field,
                           target_rule_id, endpoint_id=None):
        """Draw an API wire, stamped with the feed it was drawn on.

        `endpoint_id` is validated against THIS connector's feeds rather than
        trusted: an id from the browser that named another connector's feed
        would file the mapping under a feed that cannot produce it, and every
        count on both screens would then be wrong in a way nothing errors on.
        """
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        src = source_field[2:] if (source_field or '').startswith('f:') else source_field
        FM = self.env['hr.integration.field.mapping']
        rule = self.env['hr.formula.rule'].browse(int(target_rule_id))
        conn = self.env['hr.integration.connector'].browse(int(connector_id))
        if not (rule.exists() and conn.exists()):
            return {'ok': False}
        vals = {'connector_id': conn.id, 'source_field': src,
                'target_rule_id': rule.id,
                'source_field_label': (src or '').replace('_', ' ').title()}
        ep_wanted = self._as_id(endpoint_id)
        ep = None
        if ep_wanted:
            eps = self._api_endpoints(conn)
            ep = (eps.filtered(lambda e: e.id == ep_wanted)[:1]
                  if eps is not None else None)
            if ep:
                vals['endpoint_id'] = ep.id
        # The board ALREADY knows what this field looks like — every left card
        # prints its sample. Dropping it on create left the new wire with an
        # empty `source_sample_value`, so the very next thing a user does —
        # open the transform popover — answered "No sample value stored" about
        # a field whose sample is on screen two inches to the left. Found on
        # the live pass. One lookup per create, which is a user action and the
        # same call the board makes on every read.
        vals.update(self._discovered_sample(conn, src, ep))
        # one source→one input per connector: drop existing on either side
        FM.search(['&', ('connector_id', '=', conn.id),
                   '|', ('source_field', '=', src), ('target_rule_id', '=', rule.id)]).unlink()
        FM.create(vals)
        return {'ok': True}

    @api.model
    def api_mapping_delete(self, mapping_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        m = self.env['hr.integration.field.mapping'].browse(int(mapping_id))
        if m.exists():
            m.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # W62 — transforms on the wire (surface + edit + live-preview the transforms
    # that ALREADY run at sync time). API adapter ONLY — cycle wires carry no
    # transform (D-I1: live payruns bypass cycle-mapping records, so a cycle
    # transform would apply to imports but not to live runs — a C7 trap).
    # ------------------------------------------------------------------
    @staticmethod
    def _transform_payload(m):
        """Compact transform descriptor for an accepted API wire (D-I2). The badge
        glyph is rendered client-side from type/value/decimals so the popover's live
        preview updates without a round-trip."""
        return {
            'type': m.transformation_type or 'direct',
            'value': m.transformation_value or 0.0,
            'decimals': m.transformation_decimals if m.transformation_decimals is not None else 2,
            'python': m.transformation_type == 'python',
            'error': bool(m.has_transform_error),
            'error_msg': m.transform_error_msg or '',
            'sample': m.source_sample_value or '',
        }

    @api.model
    def api_transform_preview(self, mapping_id, draft_vals):
        """Evaluate a DRAFT transform against the mapping's sample value WITHOUT
        writing (D-I3). preview == what the sync path produces — they are the same
        engine function. Reads are open; the preview never mutates."""
        m = self.env['hr.integration.field.mapping'].browse(int(mapping_id or 0)).exists()
        if not m:
            return {'ok': False, 'error': _("Mapping not found.")}
        return m.preview_transform(draft_vals or {})

    @api.model
    def api_transform_save(self, mapping_id, vals):
        """Persist a transform edit (D-I3). Manager-gated; whitelisted to
        type/value/decimals ONLY — `transformation_code` is NEVER writable here (the
        canvas must not grow a code-authoring surface, D-I2/D-I3). Returns the fresh
        transform payload so the badge re-renders."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("Only managers can edit transforms.")}
        m = self.env['hr.integration.field.mapping'].browse(int(mapping_id or 0)).exists()
        if not m:
            return {'ok': False, 'msg': _("Mapping not found.")}
        vals = dict(vals or {})
        t = vals.get('transformation_type') or 'direct'
        allowed = {'direct', 'multiply', 'divide', 'add', 'subtract',
                   'round', 'abs', 'default_if_empty'}
        if t not in allowed:
            # python (and anything unknown) is not editable on the canvas
            return {'ok': False, 'msg': _("This transform type can only be edited in "
                                          "the backend form.")}
        data = {'transformation_type': t}
        if 'transformation_value' in vals:
            try:
                data['transformation_value'] = float(vals.get('transformation_value') or 0.0)
            except (TypeError, ValueError):
                return {'ok': False, 'msg': _("Factor / value must be a number.")}
        if 'transformation_decimals' in vals:
            try:
                data['transformation_decimals'] = int(vals.get('transformation_decimals') or 0)
            except (TypeError, ValueError):
                return {'ok': False, 'msg': _("Decimals must be a whole number.")}
        # switching AWAY from python (or off an errored op) clears the stale error flag
        if m.has_transform_error:
            data['has_transform_error'] = False
            data['transform_error_msg'] = False
        m.write(data)
        return {'ok': True, 'transform': self._transform_payload(m)}

    # ------------------------------------------------------------------
    # W65 — mapping templates (save a board as a named, reusable template and
    # apply it across configs/connectors — the bureau workflow). New lean
    # user-template models (D-I5); the vendor-seeded hr.integration.mapping.template
    # is untouched. Templates store CODES/PATHS, never ids, so they apply across
    # configs. Company-scoped from day one — no W104 snippet gap.
    # ------------------------------------------------------------------
    def _tmpl_can_delete(self, tpl):
        """Managers can delete shared templates and their own company's; a
        non-shared template from ANOTHER company is un-deletable (server-side)."""
        if not self._can_edit():
            return False
        return (not tpl.company_id) or tpl.company_id.id == self.env.company.id

    @api.model
    def mapping_template_list(self, adapter=None):
        """Visible templates = shared (no company) + this company's. Reads are open."""
        Tpl = self.env['hr.formula.mapping.template']
        domain = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]
        if adapter in ('api', 'cycle'):
            domain = [('adapter', '=', adapter)] + domain
        out = []
        for t in Tpl.search(domain):
            out.append({'id': t.id, 'name': t.name or '', 'adapter': t.adapter,
                        'connector_type': t.connector_type or '',
                        'shared': not t.company_id,
                        'line_count': len(t.line_ids),
                        'can_delete': self._tmpl_can_delete(t)})
        return {'ok': True, 'templates': out, 'can_edit': self._can_edit()}

    @api.model
    def mapping_template_save(self, config_id, adapter, name):
        """Snapshot the CURRENT accepted wires of a board into a named template
        (D-I6). API boards carry transforms; cycle boards carry pairs only (D-I1).
        Manager-gated; always company-scoped to self.env.company."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("Only managers can save templates.")}
        name = (name or '').strip()
        if not name:
            return {'ok': False, 'msg': _("Give the template a name.")}
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'msg': _("No configuration.")}
        lines, connector_type = [], False
        if adapter == 'api':
            conn = self._api_active_connector(config)
            if not conn:
                return {'ok': False, 'msg': _("No connector to snapshot.")}
            connector_type = conn.connector_type or False
            input_ids = config.rule_ids.filtered(lambda r: r.column_type == 'input').ids
            FM = self.env['hr.integration.field.mapping']
            for m in FM.search([('connector_id', '=', conn.id),
                                ('target_rule_id', 'in', input_ids)]):
                if not (m.source_field and m.target_rule_id.code):
                    continue
                lines.append((0, 0, {
                    'source_key': m.source_field,
                    'target_code': m.target_rule_id.code,
                    'transformation_type': m.transformation_type or 'direct',
                    'transformation_value': m.transformation_value or 0.0,
                    'transformation_decimals': m.transformation_decimals
                        if m.transformation_decimals is not None else 2,
                    'sequence': m.sequence or 10,
                }))
        elif adapter == 'cycle':
            mid, end = self._cycle_pair(config)
            if not (mid and end):
                return {'ok': False, 'msg': _("No paired cycle configuration to snapshot.")}
            Mapping = self.env['hr.payroll.cycle.component.mapping']
            for m in Mapping.search([('mid_cycle_config_id', '=', mid.id),
                                    ('end_cycle_config_id', '=', end.id)]):
                if not (m.mid_component_id.code and m.end_component_id.code):
                    continue
                lines.append((0, 0, {'source_key': m.mid_component_id.code,
                                     'target_code': m.end_component_id.code}))
        else:
            return {'ok': False, 'msg': _("Unknown adapter.")}
        if not lines:
            return {'ok': False, 'msg': _("Nothing mapped to save yet.")}
        tpl = self.env['hr.formula.mapping.template'].create({
            'name': name, 'adapter': adapter, 'connector_type': connector_type,
            'company_id': self.env.company.id, 'line_ids': lines,
        })
        return {'ok': True, 'template_id': tpl.id, 'line_count': len(lines)}

    @api.model
    def mapping_template_apply(self, template_id, config_id, connector_id=None):
        """Apply a template to a board by matching lines on code/path (D-I6). NEVER
        overwrites an existing wire (skip + report) and never deletes anything.
        Returns {applied, skipped_existing, unmatched_sources, unmatched_targets}."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("Only managers can apply templates.")}
        tpl = self.env['hr.formula.mapping.template'].browse(int(template_id or 0)).exists()
        if not tpl:
            return {'ok': False, 'msg': _("Template not found.")}
        # visibility guard — server-side, not just UI (D-I5)
        if tpl.company_id and tpl.company_id.id != self.env.company.id:
            return {'ok': False, 'msg': _("This template belongs to another company.")}
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'msg': _("No configuration.")}
        applied, skipped, un_src, un_tgt = [], [], [], []
        if tpl.adapter == 'api':
            conn = self._api_active_connector(config, connector_id)
            if not conn:
                return {'ok': False, 'msg': _("No connector on this board.")}
            FM = self.env['hr.integration.field.mapping']
            input_rules = config.rule_ids.filtered(lambda r: r.column_type == 'input')
            code_to_rule = {r.code: r for r in input_rules if r.code}
            try:
                avail = {f['path'] for f in (FM.get_available_source_fields(conn.id) or [])}
            except Exception:
                avail = set()
            existing = FM.search([('connector_id', '=', conn.id),
                                  ('target_rule_id', 'in', input_rules.ids)])
            used_src = {m.source_field for m in existing}
            used_tgt = {m.target_rule_id.id for m in existing}
            for ln in tpl.line_ids:
                rule = code_to_rule.get(ln.target_code)
                src_ok = ln.source_key in avail
                if not src_ok:
                    un_src.append(ln.source_key)
                if not rule:
                    un_tgt.append(ln.target_code)
                if not (rule and src_ok):
                    continue
                if ln.source_key in used_src or rule.id in used_tgt:
                    skipped.append({'source': ln.source_key, 'target': ln.target_code})
                    continue
                FM.create({'connector_id': conn.id, 'source_field': ln.source_key,
                           'target_rule_id': rule.id,
                           'source_field_label': (ln.source_key or '').replace('_', ' ').title(),
                           'transformation_type': ln.transformation_type or 'direct',
                           'transformation_value': ln.transformation_value or 0.0,
                           'transformation_decimals': ln.transformation_decimals
                               if ln.transformation_decimals is not None else 2})
                used_src.add(ln.source_key)
                used_tgt.add(rule.id)
                applied.append({'source': ln.source_key, 'target': ln.target_code})
        elif tpl.adapter == 'cycle':
            mid, end = self._cycle_pair(config)
            if not (mid and end):
                return {'ok': False, 'msg': _("This configuration has no paired cycle to apply to.")}
            Mapping = self.env['hr.payroll.cycle.component.mapping']
            mid_by_code = {r.code: r for r in mid.rule_ids if r.code}
            end_by_code = {r.code: r for r in end.rule_ids if r.code}
            existing = Mapping.search([('mid_cycle_config_id', '=', mid.id),
                                      ('end_cycle_config_id', '=', end.id)])
            used_mid = {m.mid_component_id.id for m in existing}
            used_end = {m.end_component_id.id for m in existing}
            for ln in tpl.line_ids:
                midc = mid_by_code.get(ln.source_key)
                endc = end_by_code.get(ln.target_code)
                if not midc:
                    un_src.append(ln.source_key)
                if not endc:
                    un_tgt.append(ln.target_code)
                if not (midc and endc):
                    continue
                if midc.id in used_mid or endc.id in used_end:
                    skipped.append({'source': ln.source_key, 'target': ln.target_code})
                    continue
                Mapping.create({'mid_cycle_config_id': mid.id, 'end_cycle_config_id': end.id,
                                'mid_component_id': midc.id, 'end_component_id': endc.id})
                used_mid.add(midc.id)
                used_end.add(endc.id)
                applied.append({'source': ln.source_key, 'target': ln.target_code})
        else:
            return {'ok': False, 'msg': _("Unknown template adapter.")}
        return {'ok': True, 'applied': applied, 'skipped_existing': skipped,
                'unmatched_sources': sorted(set(un_src)),
                'unmatched_targets': sorted(set(un_tgt))}

    @api.model
    def mapping_template_delete(self, template_id):
        """Manager-gated + company-scope server-side check (D-I5): a non-shared
        template from another company is un-deletable here."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("Only managers can delete templates.")}
        tpl = self.env['hr.formula.mapping.template'].browse(int(template_id or 0)).exists()
        if not tpl:
            return {'ok': True}
        if not self._tmpl_can_delete(tpl):
            return {'ok': False, 'msg': _("This template belongs to another company "
                                          "and can't be deleted here.")}
        tpl.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # F10 adapter 3 — import column mapping (Excel columns → inputs)
    # ------------------------------------------------------------------
    def _import_batch_columns(self, batch):
        """Distinct column keys from the batch's first import line (the parsed
        header→value dict), preserving order."""
        line = self.env['hr.payroll.import.line'].search([('batch_id', '=', batch.id)], limit=1)
        if line and line.raw_data_json:
            try:
                return list(json.loads(line.raw_data_json).keys())
            except Exception:
                pass
        return []

    @api.model
    def import_mapping_data(self, config_id=None, batch_id=None):
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'reason': 'no_config'}
        Batch = self.env['hr.payroll.import.batch']
        batches = Batch.search([], order='id desc')
        contexts = [{'id': b.id, 'name': b.name} for b in batches]
        batch = Batch.browse(int(batch_id)) if batch_id else Batch.browse()
        if not batch:
            batch = (batches.filtered(lambda b: b.formula_config_id.id == config.id and b.import_line_ids)[:1]
                     or batches.filtered(lambda b: b.import_line_ids)[:1] or batches[:1])
        if not batch:
            return {'ok': False, 'reason': 'no_batch', 'contexts': contexts}
        cols = self._import_batch_columns(batch)
        left = [{'id': 'c:' + c, 'label': c, 'sublabel': '', 'meta': {}} for c in cols]
        input_rules = config.rule_ids.filtered(lambda r: r.column_type == 'input') \
            .sorted(key=lambda r: r.sequence)
        right = [{'id': r.id, 'label': (r.name or r.code), 'sublabel': r.code or '',
                  'meta': {'col': r.column_letter or '', 'type': 'input'}} for r in input_rules]
        col_set = set(cols)
        wires, mapped_rules = [], set()
        for r in input_rules:
            dsf = r.data_source_field
            if dsf and dsf in col_set:
                wires.append({'id': 'im%s' % r.id, 'kind': 'mapping', 'ref': r.id,
                              'leftId': 'c:' + dsf, 'rightId': r.id, 'state': 'accepted'})
                mapped_rules.add(r.id)
        # suggestions: best name/code match between an unmapped column and input
        rule_norms = [(r, self._norm(r.code), self._norm(r.name)) for r in input_rules
                      if r.id not in mapped_rules]
        used = set(mapped_rules)
        for c in cols:
            cn = self._norm(c)
            best, conf = None, 0.0
            for r, rc, rn in rule_norms:
                if r.id in used:
                    continue
                if rc and (cn == rc):
                    x = 1.0
                elif rc and (rc in cn or cn in rc):
                    x = 0.85
                elif rn and (cn == rn or rn in cn or cn in rn):
                    x = 0.8
                else:
                    x = 0.0
                if x > conf:
                    best, conf = r, x
            if best and conf >= 0.8:
                wires.append({'id': 'sug:%s>%s' % (c, best.id), 'kind': 'suggestion',
                              'ref': None, 'source': c, 'leftId': 'c:' + c, 'rightId': best.id,
                              'state': 'suggested', 'confidence': round(conf, 2), 'reason': _('Name match')})
                used.add(best.id)
        return {
            'ok': True, 'left': left, 'right': right, 'wires': wires,
            'left_title': '%s · columns' % batch.name,
            'right_title': '%s · inputs' % config.name,
            'subtitle': _("Map imported columns from %s onto this scheme's inputs") % batch.name,
            'supports_suggest': False,
            'contexts': contexts, 'context_id': batch.id,
            'can_edit': self._can_edit(),
        }

    @api.model
    def import_mapping_create(self, config_id, batch_id, column, target_rule_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        col = column[2:] if (column or '').startswith('c:') else column
        rule = self.env['hr.formula.rule'].browse(int(target_rule_id))
        if not rule.exists():
            return {'ok': False}
        rule.write({'data_source_field': col})
        return {'ok': True}

    @api.model
    def import_mapping_delete(self, rule_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if rule.exists():
            rule.write({'data_source_field': False})
        return {'ok': True}

    # ------------------------------------------------------------------
    # F10 adapter 4 — Employee → scheme assignment (departments → schemes)
    # ------------------------------------------------------------------
    @api.model
    def scheme_mapping_data(self, config_id=None, context_id=None):
        config = self._pick_config(config_id)
        Emp = self.env['hr.employee']
        Dept = self.env['hr.department']
        Config = self.env['hr.formula.config']
        Assign = self.env['hr.formula.scheme.assignment']
        # LEFT = departments that actually have employees (with coverage counts)
        counts = {}
        for d in Dept.search([]):
            n = Emp.search_count([('department_id', '=', d.id)])
            if n:
                counts[d.id] = n
        depts = Dept.browse(sorted(counts, key=lambda i: -counts[i]))
        left = [{'id': d.id, 'label': d.name or '(dept)',
                 'sublabel': '%s employees' % '{:,}'.format(counts[d.id]),
                 'meta': {'count': counts[d.id]}} for d in depts]
        # RIGHT = the primary payroll schemes (active, not the mid-cycle advance)
        schemes = Config.search([('state', '=', 'active'),
                                 ('cycle_type', '!=', 'mid_cycle')], order='name')
        scheme_ids = set(schemes.ids)
        assigns = Assign.search([('config_id', 'in', schemes.ids)])
        cov = defaultdict(int)
        wires = []
        for a in assigns:
            if a.department_id and a.config_id.id in scheme_ids:
                wires.append({'id': 'sa%s' % a.id, 'kind': 'mapping', 'ref': a.id,
                              'leftId': a.department_id.id, 'rightId': a.config_id.id,
                              'state': 'accepted'})
                cov[a.config_id.id] += counts.get(a.department_id.id, 0)
        right = [{'id': c.id, 'label': c.name,
                  'sublabel': (('%s covered' % '{:,}'.format(cov[c.id])) if cov[c.id]
                               else (c.country_code or 'scheme')),
                  'meta': {'coverage': cov[c.id]}} for c in schemes]
        return {
            'ok': True, 'left': left, 'right': right, 'wires': wires,
            'left_title': 'Employee segments (departments)',
            'right_title': 'Payroll schemes',
            'subtitle': _("Assign employee segments to the payroll scheme that pays them"),
            'supports_suggest': False,
            'contexts': [], 'context_id': False,
            'can_edit': self._can_edit(),
        }

    @api.model
    def scheme_mapping_create(self, config_id, context_id, department_id, target_config_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        Assign = self.env['hr.formula.scheme.assignment']
        dept = self.env['hr.department'].browse(int(department_id))
        cfg = self.env['hr.formula.config'].browse(int(target_config_id))
        if not (dept.exists() and cfg.exists()):
            return {'ok': False}
        # one scheme per department: drop this department's other assignments
        Assign.search([('department_id', '=', dept.id)]).unlink()
        Assign.create({'department_id': dept.id, 'config_id': cfg.id})
        return {'ok': True}

    @api.model
    def scheme_mapping_delete(self, assignment_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        a = self.env['hr.formula.scheme.assignment'].browse(int(assignment_id))
        if a.exists():
            a.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # Employee/Contract field mapping adapter — folds the old standalone
    # "Employee/Contract Mapping" list into the canvas. LEFT = the config's
    # components; RIGHT = a curated set of writable, scalar employee/contract
    # fields (+ on-demand search); wires persist to hr.payslip.import.mapping.
    # ------------------------------------------------------------------
    _EC_TTYPES = ('char', 'text', 'float', 'monetary', 'integer', 'boolean', 'date', 'datetime', 'selection')
    _EC_MODEL_LABEL = {'hr.contract': 'Contract', 'hr.employee': 'Employee'}
    _EC_CURATED = {
        'hr.contract': ['wage', 'wage_type', 'hourly_wage', 'date_start', 'date_end', 'trial_date_end', 'notes'],
        'hr.employee': ['barcode', 'identification_id', 'passport_id', 'registration_number', 'job_title',
                        'work_email', 'work_phone', 'mobile_phone', 'marital', 'children', 'km_home_work',
                        'account_number', 'bank_name'],
    }

    @api.model
    def _ec_field_item(self, fld):
        return {'id': 'f:%s:%s' % (fld.model, fld.name),
                'label': fld.field_description or fld.name, 'sublabel': self._EC_MODEL_LABEL.get(fld.model, fld.model),
                'meta': {'model': fld.model, 'field': fld.name, 'ttype': fld.ttype}}

    @api.model
    def _ec_right_items(self, q=''):
        # field metadata is model schema (no employee PII); sudo so non-admin
        # payroll staff can see the target field list. Writes stay _can_edit-gated.
        IMF = self.env['ir.model.fields'].sudo()
        items = []
        for model in ('hr.contract', 'hr.employee'):
            dom = [('model', '=', model), ('store', '=', True), ('readonly', '=', False),
                   ('ttype', 'in', list(self._EC_TTYPES))]
            if q:
                dom += ['|', ('name', 'ilike', q), ('field_description', 'ilike', q)]
            else:
                dom += [('name', 'in', self._EC_CURATED.get(model, []))]
            for f in IMF.search(dom, order='field_description', limit=60):
                items.append(self._ec_field_item(f))
        return items

    @api.model
    def employee_mapping_data(self, config_id=None, context_id=None):
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'reason': 'no_config'}
        q = context_id.strip().lower() if isinstance(context_id, str) else ''
        left = [self._mc_item(r) for r in config.rule_ids.sorted(key=lambda r: r.sequence)]
        right = self._ec_right_items(q)
        present = {i['id'] for i in right}
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        wires = []
        for m in Mapping.search([('salary_structure_id', '=', config.id)]):
            if not (m.component_id and m.target_model_id and m.target_field_id):
                continue
            rid = 'f:%s:%s' % (m.target_model_id.model, m.target_field_id.name)
            wires.append({'id': 'em%s' % m.id, 'kind': 'mapping', 'ref': m.id,
                          'leftId': m.component_id.id, 'rightId': rid, 'state': 'accepted'})
            # a wired field must appear in RIGHT even when not in the curated/search set
            if rid not in present:
                fld = self.env['ir.model.fields'].sudo().search(
                    [('model', '=', m.target_model_id.model), ('name', '=', m.target_field_id.name)], limit=1)
                if fld:
                    right.append(self._ec_field_item(fld))
                    present.add(rid)
        return {
            'ok': True, 'left': left, 'right': right, 'wires': wires,
            'left_title': config.name, 'right_title': 'Employee / contract fields',
            'subtitle': _("Copy component results onto employee & contract fields"),
            'supports_suggest': False, 'contexts': [], 'context_id': False,
            'can_edit': self._can_edit(),
        }

    @api.model
    def ec_search_fields(self, query, config_id=None):
        """Autocomplete for the Employee/Contract tab: any writable scalar
        hr.employee / hr.contract field matching the query, so a user can append
        a field beyond the curated set and wire it. Metadata read via _ec_right_items
        (sudo'd)."""
        q = (query or '').strip().lower()
        if len(q) < 2:
            return {'ok': True, 'fields': []}
        return {'ok': True, 'fields': self._ec_right_items(q)[:40]}

    @api.model
    def ec_model_fields(self, model):
        """All writable scalar fields for ONE model (hr.employee | hr.contract),
        for the Employee/Contract browse dropdowns. Metadata only — sudo'd like
        _ec_right_items; writes still go through employee_mapping_create/delete."""
        if model not in ('hr.employee', 'hr.contract'):
            return {'ok': False, 'fields': []}
        IMF = self.env['ir.model.fields'].sudo()
        dom = [('model', '=', model), ('store', '=', True), ('readonly', '=', False),
               ('ttype', 'in', list(self._EC_TTYPES))]
        flds = IMF.search(dom, order='field_description')
        return {'ok': True, 'fields': [self._ec_field_item(f) for f in flds]}

    @api.model
    def employee_mapping_create(self, config_id, context_id, component_id, target_spec):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        config = self._pick_config(config_id)
        parts = (target_spec or '').split(':')
        if not config or len(parts) != 3 or parts[0] != 'f':
            return {'ok': False}
        model, fname = parts[1], parts[2]
        comp = self.env['hr.formula.rule'].browse(int(component_id))
        mdl = self.env['ir.model'].sudo().search([('model', '=', model)], limit=1)
        fld = self.env['ir.model.fields'].sudo().search([('model', '=', model), ('name', '=', fname)], limit=1)
        if not (comp.exists() and mdl and fld):
            return {'ok': False}
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        # 1:1 on both sides within this config — drop any existing on either end
        Mapping.search(['&', ('salary_structure_id', '=', config.id),
                        '|', ('component_id', '=', comp.id),
                        '&', ('target_model_id', '=', mdl.id), ('target_field_id', '=', fld.id)]).unlink()
        Mapping.create({'salary_structure_id': config.id, 'component_id': comp.id,
                        'target_model_id': mdl.id, 'target_field_id': fld.id})
        return {'ok': True}

    @api.model
    def employee_mapping_delete(self, mapping_id):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        m = self.env['hr.payslip.import.mapping'].sudo().browse(int(mapping_id))
        if m.exists():
            m.unlink()
        return {'ok': True}

    # ------------------------------------------------------------------
    # B1 — Execution replay (step through a payslip's computation)
    # ------------------------------------------------------------------
    @api.model
    def replay_trace(self, config_id=None, sample_id=None):
        """Re-evaluate one sample's inputs and emit an ORDERED trace — one entry
        per formula component in dependency order, each recording the input
        values it read and the value it produced. Generated on demand, never
        persisted (D-B1)."""
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        by_col = self._col_to_rule(rules)
        by_code = {r.code: r for r in rules if r.code}
        samples = [{'id': s.id, 'name': s.name} for s in config.sample_data_ids]
        sid = int(sample_id) if sample_id else (samples[0]['id'] if samples else False)
        if not sid:
            return {'ok': False, 'reason': 'no_sample', 'samples': samples}
        sample = self.env['hr.formula.sample.data'].browse(sid)
        try:
            inputs = json.loads(sample.input_values_json or '{}')
        except Exception:
            inputs = {}

        # seed results (code-keyed, like the engine) with inputs + constants
        results = dict(inputs)
        seeded = []
        for r in rules:
            if r.column_type == 'constant':
                results[r.code] = r.constant_value or 0.0
            elif r.column_type == 'input' and r.code not in results:
                results[r.code] = r.default_value or 0.0
        for r in rules:
            if r.column_type in ('input', 'constant') and r.column_letter:
                seeded.append({'col': r.column_letter, 'code': r.code or '',
                               'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code,
                               'type': r.column_type,
                               'value': self._as_num(results.get(r.code)),
                               'number_format': r.number_format or 'currency'})

        # formula rules in execution order (dependencies first)
        intel = self.get_intelligence(config.id)
        order_cols = [c for c in intel.get('execution_order', []) if c in by_col]

        steps = []
        for col in order_cols:
            r = by_col.get(col)
            if not r or r.column_type != 'formula':
                continue
            refs = self._expand_refs(r.excel_formula, by_col)
            in_vals = []
            for c in sorted(refs, key=self._col_num):
                rr = by_col.get(c)
                if rr:
                    in_vals.append({'col': c, 'code': rr.code or '',
                                    'name': (rr.salary_rule_id.name if rr.salary_rule_id else False) or rr.name or rr.code,
                                    'value': self._as_num(results.get(rr.code)),
                                    'number_format': rr.number_format or 'currency'})
            try:
                val = r.evaluate(results)
            except Exception:
                val = 0.0
            results[r.code] = val
            steps.append({
                'col': r.column_letter, 'code': r.code or '',
                'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code,
                'group': _group_for(r),
                'excel_formula': r.excel_formula or '',
                'tokens': self._tokenize(r, by_col),
                'inputs': in_vals,
                'result': self._as_num(val),
                'is_deduction': _group_for(r) == 'Deductions',
                'number_format': r.number_format or 'currency',
            })
        return {
            'ok': True,
            'config': {'id': config.id, 'name': config.name,
                       'currency': config.currency_id.symbol if config.currency_id else '₫'},
            'samples': samples, 'sample_id': sid,
            'seeded': seeded, 'steps': steps,
            'can_edit': self._can_edit(),
        }

    @api.model
    def _as_num(self, v):
        try:
            return round(float(v or 0.0), 4)
        except (TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------
    # F9 — Payslip Studio
    # ------------------------------------------------------------------
    _SECTION_COLORS = ['slate', 'indigo', 'emerald', 'amber', 'rose', 'sky', 'violet']

    def _payslip_comp(self, r, values):
        """One payslip line payload (value comes from the live preview)."""
        return {
            'id': r.id,
            'col': r.column_letter or '',
            'code': r.code or '',
            'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code or '(unnamed)',
            'group': _group_for(r),
            'type': r.column_type or '',
            'number_format': r.number_format or 'currency',
            'visibility': r.visibility_rule or 'always',
            'payslip_sequence': r.payslip_sequence or 0,
            'is_deduction': _group_for(r) == 'Deductions',
            'value': values.get(r.column_letter),
        }

    @api.model
    def payslip_studio_data(self, config_id=None, sample_id=None):
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        Section = self.env['hr.payslip.config']
        sections = Section.search([('salary_structure_id', '=', config.id)], order='sequence, id')
        samples = [{'id': s.id, 'name': s.name} for s in config.sample_data_ids]
        sid = int(sample_id) if sample_id else (samples[0]['id'] if samples else False)
        values = self._compute(config, sid).get('values', {}) if sid else {}

        payslip_rules = [r for r in rules if r.appears_on_payslip]
        by_sec = defaultdict(list)
        tray = []
        for r in payslip_rules:
            if r.payslip_identifier:
                by_sec[r.payslip_identifier.id].append(r)
            else:
                tray.append(r)
        sec_payload = []
        for s in sections:
            comps = sorted(by_sec.get(s.id, []),
                           key=lambda r: (r.payslip_sequence or 0, r.sequence))
            sec_payload.append({
                'id': s.id, 'identifier': s.identifier or '',
                'label': s.label or s.identifier or '', 'label_vi': s.label_vi or '',
                'sequence': s.sequence, 'color_key': s.color_key or 'slate',
                'collapse_when_empty': bool(s.collapse_when_empty),
                'components': [self._payslip_comp(r, values) for r in comps],
            })
        tray_sorted = sorted(tray, key=lambda r: r.sequence)
        return {
            'ok': True,
            'config': {'id': config.id, 'name': config.name,
                       'currency': config.currency_id.symbol if config.currency_id else '₫'},
            'sections': sec_payload,
            'tray': [self._payslip_comp(r, values) for r in tray_sorted],
            'samples': samples, 'sample_id': sid,
            'colors': self._SECTION_COLORS,
            'theme': {
                'accent': config.theme_accent or 'slate',
                'font': config.theme_font or 'system',
                'show_logo': bool(config.theme_show_logo),
                'has_logo': bool(config.theme_logo),
            },
            'accent_hex': self._ACCENT_HEX,
            'can_edit': self._can_edit(),
        }

    # W73 — accent palette hex (the LOCKED sc-* keys; mirrors payslip.scss +
    # hr_payslip_formula._THEME_ACCENT_HEX so preview and print never drift).
    _ACCENT_HEX = {
        'slate': '#64748B', 'indigo': '#5A4BB0', 'emerald': '#059669',
        'amber': '#D97706', 'rose': '#E11D48', 'sky': '#0284C7', 'violet': '#7C3AED',
    }

    @api.model
    def save_payslip_theme(self, config_id, vals):
        """W73 (D-L7) — persist payslip theme fields (manager-gated). Only the
        four whitelisted brand tokens are writable; accent/font are validated
        against the LOCKED selections so no free hex/font ever lands."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("You do not have permission to edit this configuration.")}
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        vals = vals or {}
        clean = {}
        # Loud reject, never silent coercion (C7): a client sending '#ff0000'
        # has a bug — quietly saving 'slate' would hide it.
        if 'accent' in vals:
            if vals['accent'] not in self._ACCENT_HEX:
                return {'ok': False,
                        'msg': _("Unknown accent %r — the palette is locked.") % vals['accent']}
            clean['theme_accent'] = vals['accent']
        if 'font' in vals:
            if vals['font'] not in ('system', 'serif', 'mono'):
                return {'ok': False,
                        'msg': _("Unknown font %r — choose system, serif or mono.") % vals['font']}
            clean['theme_font'] = vals['font']
        if 'show_logo' in vals:
            clean['theme_show_logo'] = bool(vals['show_logo'])
        if 'logo' in vals:
            # '' / False clears the brand logo (falls back to company logo).
            clean['theme_logo'] = vals['logo'] or False
        if clean:
            config.write(clean)
        return {'ok': True, 'theme': {
            'accent': config.theme_accent or 'slate',
            'font': config.theme_font or 'system',
            'show_logo': bool(config.theme_show_logo),
            'has_logo': bool(config.theme_logo),
        }}

    @api.model
    def move_component(self, rule_id, section_id, ordered_ids):
        """Place a component into a section (or the tray when section_id is falsy)
        and renumber that target's lines from ordered_ids — one RPC covers both a
        cross-section move and a within-section reorder."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        Rule = self.env['hr.formula.rule']
        rule = Rule.browse(int(rule_id))
        if not rule.exists():
            return {'ok': False}
        sec = int(section_id) if section_id else False
        vals = {'payslip_identifier': sec, 'appears_on_payslip': True}
        rule.write(vals)
        # renumber the whole target list so drag order persists deterministically
        for i, rid in enumerate(ordered_ids or []):
            r = Rule.browse(int(rid))
            if r.exists():
                r.write({'payslip_identifier': sec, 'payslip_sequence': (i + 1) * 10})
        return {'ok': True}

    @api.model
    def create_section(self, config_id, label=None):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False}
        Section = self.env['hr.payslip.config']
        existing = Section.search([('salary_structure_id', '=', config.id)])
        base = (label or 'Section').strip()
        ident = re.sub(r'[^A-Za-z0-9]', '', base).upper()[:16] or 'SECTION'
        codes = set(existing.mapped('identifier'))
        code, n = ident, 1
        while code in codes:
            n += 1
            code = '%s%s' % (ident, n)
        seq = (max(existing.mapped('sequence') or [0]) + 10) if existing else 10
        color = self._SECTION_COLORS[len(existing) % len(self._SECTION_COLORS)]
        s = Section.create({'salary_structure_id': config.id, 'identifier': code,
                            'label': base, 'sequence': seq, 'color_key': color})
        return {'ok': True, 'section_id': s.id}

    @api.model
    def update_section(self, section_id, vals):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        s = self.env['hr.payslip.config'].browse(int(section_id))
        if not s.exists():
            return {'ok': False}
        allowed = {k: v for k, v in (vals or {}).items()
                   if k in ('label', 'label_vi', 'color_key', 'collapse_when_empty')}
        if allowed:
            s.write(allowed)
        return {'ok': True}

    @api.model
    def delete_section(self, section_id):
        """Delete a section; its components fall back to the tray (unassigned)."""
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        s = self.env['hr.payslip.config'].browse(int(section_id))
        if not s.exists():
            return {'ok': False}
        self.env['hr.formula.rule'].search([('payslip_identifier', '=', s.id)]).write(
            {'payslip_identifier': False})
        s.unlink()
        return {'ok': True}

    @api.model
    def reorder_sections(self, config_id, ordered_ids):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        Section = self.env['hr.payslip.config']
        for i, sid in enumerate(ordered_ids or []):
            s = Section.browse(int(sid))
            if s.exists():
                s.write({'sequence': (i + 1) * 10})
        return {'ok': True}

    @api.model
    def set_component_visibility(self, rule_id, visibility_rule):
        if not self._can_edit():
            return {'ok': False, 'msg': _("No permission.")}
        if visibility_rule not in ('always', 'when_nonzero', 'never'):
            return {'ok': False}
        r = self.env['hr.formula.rule'].browse(int(rule_id))
        if r.exists():
            r.write({'visibility_rule': visibility_rule})
        return {'ok': True}

    # ------------------------------------------------------------------
    # F15 — Comments & annotations
    # ------------------------------------------------------------------
    def _note_payload(self, n):
        return {
            'id': n.id,
            'body': n.body or '',
            'author': n.author_id.name or '',
            'is_review': bool(n.is_review),
            'resolved': bool(n.resolved),
            'date': fields.Datetime.to_string(n.create_date) if n.create_date else '',
            'resolved_by': n.resolved_by_id.name or '',
            'is_mine': n.author_id.id == self.env.user.id,
        }

    @api.model
    def list_notes(self, rule_id):
        notes = self.env['hr.formula.rule.note'].search([('rule_id', '=', int(rule_id))])
        return {'ok': True,
                'notes': [self._note_payload(n) for n in notes],
                'open_reviews': sum(1 for n in notes if n.is_review and not n.resolved)}

    @api.model
    def post_note(self, rule_id, body, is_review=False):
        if not (body or '').strip():
            return {'ok': False}
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        if not rule.exists():
            return {'ok': False}
        self.env['hr.formula.rule.note'].create({
            'rule_id': rule.id, 'body': body.strip(), 'is_review': bool(is_review)})
        return self.list_notes(rule.id)

    @api.model
    def resolve_note(self, note_id):
        n = self.env['hr.formula.rule.note'].browse(int(note_id))
        if n.exists():
            n.action_resolve()
        return {'ok': True}

    @api.model
    def reopen_note(self, note_id):
        n = self.env['hr.formula.rule.note'].browse(int(note_id))
        if n.exists():
            n.action_reopen()
        return {'ok': True}

    @api.model
    def delete_note(self, note_id):
        n = self.env['hr.formula.rule.note'].browse(int(note_id))
        if n.exists() and (n.author_id.id == self.env.user.id or self._can_edit()):
            n.unlink()
        return {'ok': True}

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
        # F111: no explicit letter — create() freezes the next permanent letter
        # (max+1, never reused). sequence lands at the end of the grid...
        Rule = self.env['hr.formula.rule']
        rule = Rule.create({
            'config_id': config.id,
            'name': vals.get('name') or 'New Component',
            'code': code,
            'column_type': vals.get('column_type') or 'formula',
            'excel_formula': vals.get('excel_formula') or '',
            'constant_value': vals.get('constant_value') or 0.0,
            'sequence': (max(config.rule_ids.mapped('sequence') or [0]) + 10),
        })
        # ...then, if the grid is grouped by category, slot it at the end of its
        # own category band rather than the far right (T111.5 / D111.4).
        cat = rule.category_id.id or 0
        siblings = [r for r in config.rule_ids.sorted(key=lambda r: r.sequence) if r.id != rule.id]
        if cat and any((r.category_id.id or 0) == cat for r in siblings):
            last = max(i for i, r in enumerate(siblings) if (r.category_id.id or 0) == cat)
            ordered = siblings[:]
            ordered.insert(last + 1, rule)
            before = {r.id: r.column_letter for r in config.rule_ids}
            for i, r in enumerate(ordered):
                target = (i + 1) * 10
                if r.sequence != target:
                    r.with_context(skip_formula_version=True).sequence = target
            Rule._assert_letters_frozen(config, before)
        return {'ok': True, 'rule_id': rule.id}

    @api.model
    def group_columns_by_category(self, config_id):
        """F111/T111.4 — one batched sequence rewrite that groups every column
        by category. Category order = first appearance (stable); within a
        category the current manual order is preserved (stable sort). Letters
        are frozen, so nothing about computation changes — display only."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False}
        before = {r.id: r.column_letter for r in config.rule_ids}
        ordered = config.rule_ids.sorted(key=lambda r: r.sequence)
        cat_order, seen = {}, 0
        for r in ordered:
            key = r.category_id.id or 0
            if key not in cat_order:
                cat_order[key] = seen
                seen += 1
        grouped = sorted(ordered, key=lambda r: (cat_order[r.category_id.id or 0], r.sequence))
        for i, rule in enumerate(grouped):
            target = (i + 1) * 10
            if rule.sequence != target:
                rule.with_context(skip_formula_version=True).sequence = target
        self.env['hr.formula.rule']._assert_letters_frozen(config, before)
        return self.get_studio_data(config_id)

    @api.model
    def reorder_component(self, config_id, drag_id, before_id=None):
        """F111/T111.3 — move a column so it sits just before `before_id` (or to
        the end when None). Display-only: renumber `sequence`; letters stay
        frozen, so no formula reference is ever re-pointed."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False}
        drag_id = int(drag_id)
        drag = config.rule_ids.filtered(lambda r: r.id == drag_id)
        if not drag:
            return {'ok': False}
        order = [r for r in config.rule_ids.sorted(key=lambda r: r.sequence) if r.id != drag_id]
        idx = len(order)
        if before_id:
            idx = next((i for i, r in enumerate(order) if r.id == int(before_id)), len(order))
        order.insert(idx, drag)
        before = {r.id: r.column_letter for r in config.rule_ids}
        for i, r in enumerate(order):
            target = (i + 1) * 10
            if r.sequence != target:
                r.with_context(skip_formula_version=True).sequence = target
        self.env['hr.formula.rule']._assert_letters_frozen(config, before)
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
        """Preview when no expected; pending when the baseline is unconfirmed
        (W84 — matches run_sample_tests); else the model's validation_status."""
        if not (s.expected_values_json and s.expected_values_json not in ('{}', '')):
            return 'preview'
        if not s.expected_confirmed:
            return 'pending'
        return s.validation_status or 'pending'

    def _sample_row(self, s):
        return {
            'id': s.id, 'name': s.name or '(unnamed)',
            'source_type': s.source_type or 'manual',
            'verdict': self._sample_verdict(s),
            'has_expected': bool(s.expected_values_json and s.expected_values_json not in ('{}', '')),
            'expected_confirmed': bool(s.expected_confirmed),
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

    # ==================================================================
    # W98 (WP-H) — offer calculator: evaluate hypothetical inputs through the
    # LIVE config with ZERO records created. Read-only; open to everyone (D-H6).
    # ==================================================================
    @api.model
    def offer_calc(self, config_id, inputs):
        """Evaluate a hypothetical employee's inputs through the live config and
        return the full component breakdown — no records created (D-H4, in-memory
        ``Sample.new`` on the SAME evaluator previews/tests use, C5). Reports
        headline NET + per-group subtotals only; NEVER a fabricated employer cost
        (D-H4/C7). Validates inputs like W49: known input codes, numeric,
        |v| <= 1e12."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        try:
            if not config.exists():
                return {'ok': False, 'msg': _('Configuration not found.')}
            rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        except AccessError:
            # cross-company probe: fail closed AND gracefully (review minor) —
            # the record rule already blocked the read before any sudo work.
            return {'ok': False, 'msg': _('No access to this configuration.')}
        input_codes = {r.code for r in rules if r.column_type == 'input' and r.code}
        clean = {}
        for code, v in (inputs or {}).items():
            code = str(code)
            if code not in input_codes:
                return {'ok': False, 'msg': _('Unknown input: %s') % code}
            n = self._as_num(v)
            if n is None:
                # _as_num refuses BOTH text and NaN/Inf. Only genuine text may
                # pass through — a value that PARSES numeric but was refused
                # (e.g. "1e400" -> inf) is out of range, not a department name.
                looks_numeric = isinstance(v, (int, float))
                if not looks_numeric and isinstance(v, str):
                    try:
                        float(v.strip())
                        looks_numeric = True
                    except (TypeError, ValueError):
                        pass
                if looks_numeric:
                    return {'ok': False, 'msg': _('Input %s is out of range.') % code}
                # Text input column (e.g. an employee name / department the config
                # carries as an input) — pass it through to the evaluator as-is.
                # Only NUMERIC inputs are range-checked; text inputs are legitimate
                # and must not reject the whole offer (C7 — degrade visibly).
                clean[code] = v
            elif abs(n) > 1e12:
                return {'ok': False, 'msg': _('Input %s is out of range.') % code}
            else:
                clean[code] = n
        # In-memory evaluation — zero rows. Evaluate under sudo so the engine's
        # eval-diagnostic writes on the rules (the same side-effect every preview
        # performs) succeed for READ-ONLY users too (D-H6 — offer calc is a
        # calculator open to everyone; it creates no data, only the internal
        # diagnostic bookkeeping the eval path already does). This avoids touching
        # the eval path itself (D-H7) while honoring D-H6's read-only guarantee.
        sample = self.env['hr.formula.sample.data'].sudo().new({'config_id': config.id})
        try:
            values = sample._evaluate_rules_with_dependencies(clean)
        except Exception as e:
            _logger.warning("offer_calc eval failed: %s", e)
            return {'ok': False, 'msg': _('Could not evaluate this offer.')}

        def _num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return 0.0

        rows = []
        subtotals = {}
        for r in rules:
            if not r.code:
                continue
            grp = _group_for(r)
            val = _num(values.get(r.code, 0.0))
            rows.append({
                'col': r.column_letter or '?', 'code': r.code,
                'name': (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code,
                'group': grp, 'type': r.column_type, 'value': round(val, 2),
                'appears_on_payslip': bool(r.appears_on_payslip),
                'number_format': r.number_format or 'number',
            })
            if grp != 'Inputs':                    # Inputs excluded from subtotals (D-H4)
                subtotals[grp] = subtotals.get(grp, 0.0) + val

        # headline net — same heuristic as the comparison (_pick_headline_code)
        net_code = self.env['hr.formula.period.comparison'].new(
            {'config_id': config.id})._pick_headline_code() or ''
        net_value = round(_num(values.get(net_code, 0.0)), 2) if net_code else 0.0

        order = ['Earnings', 'Deductions', 'Totals']
        sub_list = [{'group': g, 'value': round(subtotals[g], 2)}
                    for g in order if g in subtotals]
        for g, v in subtotals.items():
            if g not in order:
                sub_list.append({'group': g, 'value': round(v, 2)})

        return {
            'ok': True,
            'config': {'id': config.id, 'name': config.display_name},
            'currency': config.currency_id.symbol if config.currency_id else '',
            'rows': rows,
            'net_code': net_code, 'net_value': net_value,
            'subtotals': sub_list,
        }

    @api.model
    def offer_sample_inputs(self, sample_id):
        """The input values of an existing sample — copied into the offer form by
        the "start from sample" picker (D-H5). Read of stored JSON only."""
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if not s.exists():
            return {'ok': False, 'inputs': {}}
        try:
            # samples carry no company/record rule of their own — gate through
            # the parent config's rule instead (review minor: no cross-company
            # sample reads through this new RPC).
            s.config_id.check_access('read')
        except AccessError:
            return {'ok': False, 'inputs': {}}
        try:
            vals = json.loads(s.input_values_json or '{}')
        except Exception:
            vals = {}
        return {'ok': True, 'inputs': vals}

    # ------------------------------------------------------------------
    # W83 — test coverage (deterministic, three-valued; NEVER evaluates a
    # formula — pure metadata over the dependency graph + sample JSONs).
    # ------------------------------------------------------------------
    def _coverage_info(self, r):
        return {'rule_id': r.id, 'col': r.column_letter or '',
                'code': r.code or '', 'name': r.name or '(unnamed)'}

    @api.model
    def get_test_coverage(self, config_id=None):
        """Which formula components the samples DO / DON'T exercise (D-G1/D-G2).

        Three-valued per formula component:

        * **asserted** — >=1 active CONFIRMED sample carries a non-null expected
          value for its code (the W82 testable rule, formula_config_tests.py:95,
          plus the D-G3 confirmation gate — unconfirmed baselines don't count).
        * **exercised** — not asserted, but on the upstream dependency closure of
          an asserted component (its value feeds an assertion), via the
          ``_normalized_dep_cols`` edges — the same graph get_intelligence walks.
        * **untested** — neither.

        Coverage ``pct`` = asserted / formula-components. Inputs/constants are
        excluded from the % but any that no asserted formula transitively reads
        are returned as ``orphan_inputs``. This method reads only stored JSON +
        dependency metadata — it NEVER calls ``_compute_results``.
        """
        config = self._pick_config(config_id)
        if not config:
            return {'ok': False, 'pct': 0, 'formula_total': 0,
                    'asserted': [], 'exercised': [], 'untested': [],
                    'orphan_inputs': []}
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        by_col = {r.column_letter: r for r in rules if r.column_letter}
        deps = self._normalized_dep_cols(rules)   # {rule.id: {source_col, ...}}
        formula_rules = [r for r in rules
                         if r.column_type == 'formula' and r.column_letter]

        # asserted codes: any active sample with a non-null expected for that
        # code AND a CONFIRMED baseline — an unconfirmed generated sample is a
        # hypothesis (D-G3) and must not raise coverage while the chip says
        # pending (review finding, WP-G).
        asserted_codes = set()
        for s in config.sample_data_ids:
            if not s.expected_confirmed:
                continue
            try:
                exp = json.loads(s.expected_values_json or '{}')
            except Exception:
                exp = {}
            if isinstance(exp, dict):
                for code, v in exp.items():
                    if v is not None:
                        asserted_codes.add(code)

        asserted = [r for r in formula_rules if r.code and r.code in asserted_codes]
        asserted_cols = {r.column_letter for r in asserted}

        # upstream closure: walk each asserted rule's dependency SOURCES,
        # transitively, over the same edges the evaluator resolves.
        closure = set()
        stack = list(asserted_cols)
        while stack:
            col = stack.pop()
            if col in closure:
                continue
            closure.add(col)
            rr = by_col.get(col)
            if rr:
                for d in deps.get(rr.id, ()):  # empty for input/constant rules
                    if d not in closure:
                        stack.append(d)

        exercised = [r for r in formula_rules
                     if r.column_letter not in asserted_cols
                     and r.column_letter in closure]
        untested = [r for r in formula_rules
                    if r.column_letter not in asserted_cols
                    and r.column_letter not in closure]
        orphan = [r for r in rules
                  if r.column_type in ('input', 'constant') and r.column_letter
                  and r.column_letter not in closure]

        n = len(formula_rules)
        pct = int(round(len(asserted) / n * 100)) if n else 0
        return {
            'ok': True, 'pct': pct, 'formula_total': n,
            'asserted': [self._coverage_info(r) for r in asserted],
            'exercised': [self._coverage_info(r) for r in exercised],
            'untested': [self._coverage_info(r) for r in untested],
            'orphan_inputs': [self._coverage_info(r) for r in orphan],
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
            'expected_confirmed': bool(s.expected_confirmed),
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

    # openpyxl number formats (S-L1 gotcha): openpyxl format strings, NOT Odoo's.
    # VND currency has no minor units ⇒ '#,##0'; percentage values are stored as
    # FRACTIONS (0.05) so Excel's '0.00%' displays 5.00% correctly — never
    # pre-multiply by 100.
    _XLSX_NUMFMT = {
        'currency': '#,##0',
        'integer': '#,##0',
        'percentage': '0.00%',
        'number': '#,##0.00',
    }

    @api.model
    def export_living_workbook(self, config_id):
        """W41 — a config becomes a *living* ``.xlsx`` (D-L1/D-L2/D-L3).

        Sheet 1 "Payroll": xlsx column position = the component's frozen
        ``column_letter`` (1:1 — this is what makes the stored ``=A2+AB2``
        formulas real, Excel-evaluable formulas). Row 1 = localized component
        name, row 2 = code (a second header row, machine-matchable), data rows
        from row 3 = one per sample. Input cells carry the sample's input value
        (else ``default_value``); constant cells carry ``constant_value``;
        formula cells carry the REAL formula — ``BRACKET(...)`` expanded out via
        ``expand_brackets`` (Excel has no BRACKET) and the row digits shifted
        2 → the data row (S-L1). A trailing "Sample" meta column follows the last
        component letter (a leading column would break the 1:1 letter mapping).
        Sheet 2 "Rate Tables" renders each table + a named range per table.
        Read-only; read access suffices (no manager gate, D-L3)."""
        import base64
        import io
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
            from openpyxl.workbook.defined_name import DefinedName
        except Exception:
            return {'ok': False, 'msg': 'openpyxl is not available on the server.'}
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': 'Configuration not found'}
        RateTable = self.env['hr.formula.rate.table']

        rules = c.rule_ids.sorted(key=lambda r: r.sequence)
        placed = [r for r in rules if r.column_letter]
        if not placed:
            return {'ok': False, 'msg': 'This configuration has no components to export.'}
        # xlsx column index = the frozen letter's ordinal (D-L1: 1:1, never by
        # sequence — a reordered config keeps letters as identities, F111).
        col_of = {r.id: self._col_num(r.column_letter) for r in placed}

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Payroll'
        head_fill = PatternFill('solid', fgColor='EEF0FB')
        head_font = Font(bold=True, color='241F52')
        code_font = Font(italic=True, color='6B7280', size=9)
        right = Alignment(horizontal='right')

        # ---- two header rows (name / code) + meta header ------------------
        for r in placed:
            col = col_of[r.id]
            name = (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code or ''
            h1 = ws.cell(row=1, column=col, value=name)
            h1.fill = head_fill
            h1.font = head_font
            h2 = ws.cell(row=2, column=col, value=r.code or '')
            h2.fill = head_fill
            h2.font = code_font
            ws.column_dimensions[get_column_letter(col)].width = 16
        # Sample names + notes live on the Info SHEET, never on Payroll — a
        # trailing meta column re-imports as a phantom SAMPLE component and the
        # 0-sample note as a phantom header (WP-L review Minor 3).

        # ---- data rows: one per sample (row 3 = first sample) -------------
        samples = list(c.sample_data_ids)
        note = ''
        if not samples:
            # C7 — a 0-sample config still exports a usable, LOUD row of defaults.
            note = 'No samples configured — one row of Default Values shown.'

        def _emit_row(sheet_row, input_by_code, sample_name):
            for r in placed:
                col = col_of[r.id]
                cell = ws.cell(row=sheet_row, column=col)
                if r.column_type == 'formula':
                    expanded = RateTable.expand_brackets(r.excel_formula or '', c)
                    text = (expanded or '').strip()
                    if text:
                        if not text.startswith('='):
                            text = '=' + text
                        cell.value = self._shift_rows(text, sheet_row)
                    else:
                        cell.value = 0
                elif r.column_type == 'constant':
                    cell.value = r.constant_value or 0.0
                else:  # input
                    raw = input_by_code.get(r.code) if r.code else None
                    if raw is None or raw == '':
                        raw = r.default_value or 0.0
                    cell.value = raw
                cell.number_format = self._XLSX_NUMFMT.get(r.number_format or 'currency', '#,##0.00')
                if r.column_type != 'formula':
                    cell.alignment = right
            row_names.append((sheet_row, sample_name))

        row_names = []
        if samples:
            for i, s in enumerate(samples):
                _emit_row(3 + i, s.get_input_values(), s.name or ('Sample %d' % (i + 1)))
        else:
            _emit_row(3, {}, '(defaults — no samples)')

        ws.freeze_panes = 'A3'                      # header + code rows frozen

        # ---- Info sheet: sample names per data row + loud notes ------------
        info = wb.create_sheet('Info')
        info.cell(row=1, column=1, value='Payroll row').font = head_font
        info.cell(row=1, column=2, value='Sample').font = head_font
        info.column_dimensions['A'].width = 12
        info.column_dimensions['B'].width = 30
        for i, (sheet_row, sample_name) in enumerate(row_names):
            info.cell(row=2 + i, column=1, value=sheet_row)
            info.cell(row=2 + i, column=2, value=sample_name)
        if note:
            info.cell(row=len(row_names) + 3, column=1, value=note).font = Font(
                bold=True, color='B45309')

        # ---- Sheet 2: Rate Tables (reference) + named ranges (D-L2) --------
        tables = [t for t in c.rate_table_ids if t.code]
        if tables:
            rs = wb.create_sheet('Rate Tables')
            rs.cell(row=1, column=1, value='Code').font = head_font
            rs.cell(row=1, column=2, value='Name').font = head_font
            rs.cell(row=1, column=3, value='From').font = head_font
            rs.cell(row=1, column=4, value='Rate').font = head_font
            for cc in ('A', 'B', 'C', 'D'):
                rs.column_dimensions[cc].width = 18
            row = 2
            for t in tables:
                brackets = t.line_ids.sorted(key=lambda b: b.lower)
                first_row = row
                for b in brackets:
                    rs.cell(row=row, column=1, value=t.code)
                    rs.cell(row=row, column=2, value=t.name or '')
                    fc = rs.cell(row=row, column=3, value=b.lower or 0.0)
                    fc.number_format = '#,##0'
                    rc = rs.cell(row=row, column=4, value=b.rate or 0.0)
                    rc.number_format = '0.00%'
                    row += 1
                if not brackets:
                    rs.cell(row=row, column=1, value=t.code)
                    rs.cell(row=row, column=2, value=t.name or '')
                    row += 1
                # Named range over this table's From/Rate block (cosmetic/
                # reference — the compiled formulas do NOT use it, D-L2).
                safe = re.sub(r'[^A-Za-z0-9]', '', (t.code or '')) or 'TABLE'
                ref = "'Rate Tables'!$C$%d:$D$%d" % (first_row, max(first_row, row - 1))
                try:
                    wb.defined_names[safe] = DefinedName(safe, attr_text=ref)
                except Exception:  # pragma: no cover — older openpyxl API
                    try:
                        wb.defined_names.append(DefinedName(safe, attr_text=ref))
                    except Exception:
                        pass

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        code = (c.code or c.name or 'config').strip().replace(' ', '_')
        return {
            'ok': True,
            'file_b64': base64.b64encode(out.read()).decode(),
            'filename': '%s_living.xlsx' % code,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'note': note,
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

    # ------------------------------------------------------------------
    # W84 — boundary-value test generation (engine does the work; these are
    # thin studio wrappers). Generation + confirm are manager-gated writes.
    # ------------------------------------------------------------------
    @api.model
    def boundary_candidates(self, config_id):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'candidates': [], 'reachable': 0, 'unreachable': 0}
        return c.boundary_candidates()

    @api.model
    def generate_boundary_samples(self, config_id, picks, base_sample_id=None):
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': _('Configuration not found')}
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can generate test samples.')}
        try:
            r = c.generate_boundary_samples(picks or [], base_sample_id)
        except Exception as e:
            _logger.warning("generate_boundary_samples failed on %s: %s", c.id, e)
            return {'ok': False, 'msg': str(e).splitlines()[0] if str(e) else 'Could not generate.'}
        r['samples'] = [self._sample_row(x) for x in c.sample_data_ids]
        return r

    @api.model
    def confirm_sample_expected(self, sample_id):
        """Flip one generated sample's baseline to confirmed and re-run the chip
        (W84/D-G3). Manager-gated like every studio write."""
        s = self.env['hr.formula.sample.data'].browse(int(sample_id))
        if not s.exists():
            return {'ok': False}
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can confirm baselines.')}
        s.expected_confirmed = True
        detail = self.get_sample_detail(s.id)
        detail['tests'] = self._run_tests_after_save(s.config_id)
        return detail

    @api.model
    def confirm_all_samples(self, config_id):
        """Confirm every unconfirmed baseline in the config, then re-run the chip."""
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False}
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can confirm baselines.')}
        unconf = c.sample_data_ids.filtered(lambda x: not x.expected_confirmed)
        n = len(unconf)
        if unconf:
            unconf.expected_confirmed = True
        return {'ok': True, 'confirmed': n,
                'samples': [self._sample_row(x) for x in c.sample_data_ids],
                'tests': self._run_tests_after_save(c)}

    # ------------------------------------------------------------------
    # W49 — AI-proposed sample profiles (LLM proposes INPUTS; the engine
    # computes the truth — the LLM never supplies an output, so the
    # number-invention bug class is excluded by construction, D-G5).
    # ------------------------------------------------------------------
    @staticmethod
    def _as_num(v):
        try:
            n = float(v)
        except (TypeError, ValueError):
            return None
        if n != n or n in (float('inf'), float('-inf')):   # NaN/Inf guard
            return None
        return n

    @api.model
    def ai_propose_samples(self, config_id):
        """Ask the LLM for <=8 realistic INPUT profiles, hard-validate every one
        (unknown code / non-numeric / |v|>1e12 → rejected + reported), and return
        the survivors for the user to accept. No key / LLM error → {ok:False}."""
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'reason': _('Configuration not found.')}
        inputs = [r for r in c.rule_ids.sorted(key=lambda r: r.sequence)
                  if r.column_type == 'input' and r.code]
        if not inputs:
            return {'ok': False, 'reason': _('This configuration has no input components.')}
        input_codes = {r.code for r in inputs}

        # min/max observed across existing samples (helps the model stay realistic)
        obs = {}
        for s in c.sample_data_ids:
            try:
                iv = json.loads(s.input_values_json or '{}')
            except Exception:
                iv = {}
            if not isinstance(iv, dict):
                continue
            for code, v in iv.items():
                n = self._as_num(v)
                if n is None:
                    continue
                lo, hi = obs.get(code, (n, n))
                obs[code] = (min(lo, n), max(hi, n))
        schema = [{'code': r.code, 'name': r.name or r.code,
                   'default': r.default_value or 0.0,
                   'min_observed': obs.get(r.code, (None, None))[0],
                   'max_observed': obs.get(r.code, (None, None))[1]}
                  for r in inputs]

        system = (
            "You are PayAI, generating realistic payroll TEST INPUT profiles. "
            "You are given the input components of a salary configuration. Propose "
            "diverse, plausible employee profiles (e.g. junior, senior, part-time, "
            "high earner, edge cases). Reply with STRICT JSON only, shaped exactly:\n"
            '{"profiles":[{"name":"<short label>","inputs":{"<CODE>":<number>},'
            '"rationale":"<one sentence>"}]}\n'
            "Rules: use ONLY the given component codes as keys; every value MUST be a "
            "plain number (no %, no text, no formulas). NEVER include output, computed, "
            "or expected values — inputs only. At most 8 profiles."
        )
        user = ("Input components:\n" + json.dumps(schema, ensure_ascii=False)
                + "\n\nPropose up to 8 realistic, diverse input profiles.")
        try:
            data = self._llm_chat(
                [{'role': 'system', 'content': system},
                 {'role': 'user', 'content': user}], json_mode=True)
        except LLMUnavailable as e:
            return {'ok': False, 'reason': _('AI is unavailable: %s') % e}

        profiles = data.get('profiles') if isinstance(data, dict) else None
        if not isinstance(profiles, list):
            return {'ok': False, 'reason': _('AI returned an unexpected response shape.')}

        accepted, rejected = [], []
        for p in profiles[:8]:
            if not isinstance(p, dict):
                continue
            name = (str(p.get('name') or 'Profile').strip() or 'Profile')[:80]
            raw = p.get('inputs')
            if not isinstance(raw, dict) or not raw:
                rejected.append({'name': name, 'reason': 'no inputs'})
                continue
            clean, bad = {}, None
            for k, v in raw.items():
                if k not in input_codes:
                    bad = 'unknown code %s' % k
                    break
                n = self._as_num(v)
                if n is None:
                    bad = 'non-numeric %s' % k
                    break
                if abs(n) > 1e12:
                    bad = 'value out of range for %s' % k
                    break
                clean[k] = n
            if bad:
                rejected.append({'name': name, 'reason': bad})
                continue
            accepted.append({'name': name, 'inputs': clean,
                             'rationale': (str(p.get('rationale') or '').strip())[:200]})
        return {'ok': True, 'proposals': accepted, 'rejected': rejected}

    @api.model
    def create_ai_samples(self, config_id, proposals):
        """Turn accepted AI proposals into generated + unconfirmed samples with an
        engine-computed baseline (manager-gated). Re-validates every value — never
        trusts the client echo (D-G5)."""
        c = self.env['hr.formula.config'].browse(int(config_id))
        if not c.exists():
            return {'ok': False, 'msg': _('Configuration not found')}
        if not self._can_edit():
            return {'ok': False, 'msg': _('Only managers can add test samples.')}
        input_codes = {r.code for r in c.rule_ids
                       if r.column_type == 'input' and r.code}
        created = 0
        rejected = 0
        for p in (proposals or []):
            if not isinstance(p, dict):
                rejected += 1
                continue
            raw = p.get('inputs') or {}
            # D-G5: one invalid entry rejects the WHOLE row — creating a sample
            # from the surviving keys would differ from what the user accepted.
            clean = {}
            bad = not isinstance(raw, dict) or not raw
            for k, v in (raw.items() if isinstance(raw, dict) else []):
                n = self._as_num(v)
                if k not in input_codes or n is None or abs(n) > 1e12:
                    bad = True
                    break
                clean[k] = n
            if bad or not clean:
                rejected += 1
                continue
            name = (str(p.get('name') or 'AI profile').strip() or 'AI profile')[:80]
            desc = 'AI-proposed profile: ' + (str(p.get('rationale') or '').strip())[:180]
            c._create_generated_sample(clean, name, desc)
            created += 1
        return {'ok': True, 'created': created, 'rejected': rejected,
                'samples': [self._sample_row(x) for x in c.sample_data_ids],
                'tests': self._run_tests_after_save(c)}

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

    # Built-in starter entries. The legacy 'vn_standard' set predates the F113
    # converter contract (its codes SI_EMP/TOTAL_DED carry underscores but are
    # only ever referenced by column letter, so they are safe) — it is kept as
    # code, byte-identical, and is NOT a registry record. All richer, contract-
    # clean country packs come from hr.formula.config.template (F113).
    _BUILTIN_TEMPLATES = [
        {'key': 'vn_standard', 'name': 'Vietnam Standard', 'country': 'VN',
         'flag': '🇻🇳', 'version': 'legacy', 'builtin': True, 'certified': False,
         'effective_date': False, 'refs': [],
         'desc': '10 components pre-wired: Basic, allowances, SI/HI/UI, Gross & Net — VN statutory rates.',
         'components': [], 'rate_tables': [],
         'preview': [{'col': 'A', 'name': 'Basic Salary', 'f': 'input'},
                     {'col': 'B', 'name': 'Housing Allowance', 'f': '= Basic × 20%'},
                     {'col': 'E', 'name': 'Gross Salary', 'f': '= A+B+C+D'},
                     {'col': 'J', 'name': 'Net Salary', 'f': '= Gross − Deductions'}]},
        {'key': 'blank', 'name': 'Blank canvas', 'country': False,
         'flag': '', 'version': '', 'builtin': True, 'certified': False,
         'effective_date': False, 'refs': [], 'components': [], 'rate_tables': [],
         'desc': 'Start empty and build components one by one — or ask PayAI to draft them.',
         'preview': []},
    ]

    @api.model
    def wizard_templates(self):
        """Starter templates for the create-config wizard: the built-in legacy
        set + every installed F113 country pack (hr.formula.config.template,
        excluding superseded versions). Each registry entry carries the picker
        UX payload (T113.7): country/flag/version/effective date, the full
        component + rate-table preview, and legislation references."""
        out = [dict(t) for t in self._BUILTIN_TEMPLATES]
        if 'hr.formula.config.template' not in self.env:
            return out
        try:
            # savepoint: if the registry table doesn't exist yet (deploy
            # window — new code, base module not upgraded), the failed
            # statement must not poison the cursor; the built-in entries keep
            # the create wizard alive regardless.
            with self.env.cr.savepoint():
                templates = self.env['hr.formula.config.template'].sudo().search(
                    [('state', '!=', 'superseded')],
                    order='country_code, sequence, effective_date desc')
                templates.mapped('code')  # force the fetch inside the savepoint
        except Exception:
            _logger.exception("F113: template registry unavailable — "
                              "serving built-in templates only")
            return out
        for tpl in templates:
            comps = tpl._components()
            preview = []
            for c in comps:
                if c.get('type') == 'input':
                    f = 'input'
                elif c.get('type') == 'constant':
                    f = 'constant'
                else:
                    f = (c.get('excel_formula') or '').lstrip('=') or 'formula'
                preview.append({'col': c.get('column_letter') or '',
                                'name': c.get('name') or c.get('code'), 'f': f})
            out.append({
                'key': tpl.code, 'name': tpl.name, 'country': tpl.country_code,
                'flag': tpl.flag or '', 'version': tpl.version,
                'effective_date': tpl.effective_date and str(tpl.effective_date) or False,
                'state': tpl.state, 'certified': tpl.state == 'certified',
                'builtin': False,
                'desc': tpl.description or '',
                'components': [{'code': c.get('code'), 'name': c.get('name'),
                               'type': c.get('type'), 'category': c.get('category'),
                               'col': c.get('column_letter') or ''} for c in comps],
                'rate_tables': [{'code': rt.get('code'), 'name': rt.get('name'),
                                'brackets': rt.get('brackets') or []}
                               for rt in tpl._rate_tables()],
                'refs': tpl._legislation_refs(),
                'preview': preview[:8],
            })
        return out

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
        creation wizard and the cockpit 'Use Vietnam Standard' resume CTA.

        Routing (F113): the built-in 'vn_standard' set stays a hardcoded code
        path (guaranteed byte-identical to pre-F113); 'blank' seeds nothing; any
        other key is looked up in the hr.formula.config.template registry and
        materialised by its own seeder (categories, rate tables, frozen letters,
        B4-resolved statutory constants, sample tests)."""
        if key and key not in ('vn_standard', 'blank'):
            Template = self.env['hr.formula.config.template']
            # never materialise a superseded structure — the picker hides
            # them, so a stale bookmarked/scripted key must not bypass that
            tpl = Template.sudo().search([
                ('code', '=', key), ('state', '!=', 'superseded')], limit=1)
            if tpl:
                tpl.seed_config(cfg)
                return
            _logger.warning("F113: unknown or superseded template key '%s' — "
                            "seeding blank", key)
            return
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
