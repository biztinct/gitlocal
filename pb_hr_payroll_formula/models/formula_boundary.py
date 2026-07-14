# -*- coding: utf-8 -*-
"""W84 — Boundary-value test generation (deterministic, LLM-free core).

For every edge the formulas actually branch on — a rate-table bracket lower or a
``<ref> <op> <number>`` comparison threshold — we manufacture edge−1 / edge / edge+1
sample rows so the W82 test chip verifies the code AT the boundary, not just around
it. Extraction is honest about reach (D-G4): an edge whose operand is a computed
component is LISTED but flagged ``reachable=False`` — never silently dropped (C7).

Generated rows are ``source_type='generated'`` + ``expected_confirmed=False`` so they
count as *pending* in ``run_sample_tests`` until a human confirms the characterization
baseline (D-G3) — a generated sample can NEVER move the chip's passed/failed counts.

The schema lives here (via ``_inherit``) so the base sample model stays untouched and
the whole W84 surface is one file. Engine-only — no studio dependency (C1).
"""
import json
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Cap one generation run (D-G4). Above this, the remainder is reported loudly.
_GEN_CAP = 60

# S-G1 — a comparison threshold: <ref> op <number> OR <number> op <ref>.
# op ∈ > >= < <= = <>. Refs are 1-3 letter-led identifiers; row digits are
# stripped by the caller before this runs (A2 -> A), so a ref never carries one.
_CMP_RE = re.compile(
    r'(?<![\w.])([A-Za-z][A-Za-z0-9]*)\s*(>=|<=|<>|>|<|=)\s*(-?\d+(?:\.\d+)?)'
    r'|(-?\d+(?:\.\d+)?)\s*(>=|<=|<>|>|<|=)\s*([A-Za-z][A-Za-z0-9]*)(?![\w.])')


def _kv(x):
    """CODE=VALUE stamp component — compact, integral-when-possible."""
    x = float(x)
    return str(int(x)) if x == int(x) else repr(round(x, 6))


def _balanced(s):
    """True iff parentheses in ``s`` are balanced and never dip negative."""
    depth = 0
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _split_first_comma(s):
    """Split ``s`` at its first TOP-LEVEL comma → (before, after)."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            return s[:i], s[i + 1:]
    return s, ''


def _bracket_span(s, open_paren):
    """Given the index of a ``(`` in ``s``, return the index of its matching
    ``)`` (or -1 if unbalanced)."""
    depth = 0
    for i in range(open_paren, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


class HrFormulaSampleDataBoundary(models.Model):
    """Schema for W84/W49 generated samples (D-G3)."""
    _inherit = 'hr.formula.sample.data'

    # C9: 'set default' is honorable because the base field defines
    # default='manual'; the added value falls back to it on selection removal.
    source_type = fields.Selection(
        selection_add=[('generated', 'Generated')],
        ondelete={'generated': 'set default'})

    # Default True so EVERY pre-existing sample keeps its current standing;
    # generated rows are created False (a hypothesis until a human confirms it).
    expected_confirmed = fields.Boolean(
        string='Baseline Confirmed', default=True,
        help="A generated sample's expected values are a characterization "
             "hypothesis until confirmed. Unconfirmed testable samples count as "
             "PENDING in the test chip — never passed/failed (D-G3).")

    # 'CODE=VALUE' stamp of the boundary dimension this row pins — used to dedupe
    # a re-run of the same generation against existing ACTIVE generated samples.
    boundary_key = fields.Char(string='Boundary Key', index=True)


class HrFormulaConfigBoundary(models.Model):
    _inherit = 'hr.formula.config'

    # ------------------------------------------------------------------
    # reference resolution (letter-first-then-code — same as the evaluator)
    # ------------------------------------------------------------------
    def _resolve_single_ref(self, val, by_col, by_code):
        """Resolve ``val`` to a rule IFF it is a SINGLE component reference
        (optionally paren-wrapped). Returns the rule or None (a compound
        expression is not a single dimension we can pin)."""
        v = (val or '').strip()
        while len(v) >= 2 and v[0] == '(' and v[-1] == ')' and _balanced(v[1:-1]):
            v = v[1:-1].strip()
        v = re.sub(r'(?<![\w])([A-Za-z]{1,3})\d+(?![\w])', r'\1', v)  # A2 -> A
        if re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', v or ''):
            return by_col.get(v) or by_code.get(v)
        return None

    def _bracket_calls(self, rules, table_code):
        """Every ``BRACKET(table_code, expr)`` call in the config's formulas →
        list of ``(rule, expr_string)``. Balanced-paren aware."""
        pat = re.compile(r'\bBRACKET\s*\(', re.IGNORECASE)
        tc = (table_code or '').upper()
        out = []
        for r in rules:
            if r.column_type != 'formula' or not r.excel_formula:
                continue
            s = r.excel_formula
            for m in pat.finditer(s):
                end = _bracket_span(s, m.end() - 1)
                if end == -1:
                    continue
                code, val = _split_first_comma(s[m.end():end])
                if (code or '').strip().upper() == tc:
                    out.append((r, val.strip()))
        return out

    def _strip_bracket_spans(self, formula):
        """Blank every ``BRACKET(...)`` span (replaced by spaces, indices
        preserved) so the threshold scan never double-counts an edge already
        owned by the rate-table source (S-G1 GOTCHA)."""
        pat = re.compile(r'\bBRACKET\s*\(', re.IGNORECASE)
        s = formula
        while True:
            m = pat.search(s)
            if not m:
                return s
            end = _bracket_span(s, m.end() - 1)
            if end == -1:
                end = len(s) - 1     # unbalanced — blank to the end, defensively
            s = s[:m.start()] + (' ' * (end - m.start() + 1)) + s[end + 1:]

    # ------------------------------------------------------------------
    # candidate extraction (D-G4) — both sources engine-side, honest reach
    # ------------------------------------------------------------------
    def _rate_table_candidates(self, rules):
        """Source 1 — every bracket lower of every rate table. The generation
        dimension is the BRACKET call's ``expr`` when it is a single input ref;
        otherwise the edge is LISTED reachable=False (operand is computed)."""
        by_col = {r.column_letter: r for r in rules if r.column_letter}
        by_code = {r.code: r for r in rules if r.code}
        out = []
        for t in self.rate_table_ids:
            if not t.code:
                continue
            calls = self._bracket_calls(rules, t.code)
            input_rule = formula_rule = None
            for rule, val in calls:
                dep = self._resolve_single_ref(val, by_col, by_code)
                if dep is not None and dep.column_type == 'input':
                    input_rule, formula_rule = dep, rule
                    break
            reachable = input_rule is not None
            if not reachable and calls:
                formula_rule = calls[0][0]
            if not calls:
                reason = "no formula calls BRACKET(%s, …)" % t.code
            elif not reachable:
                reason = "operand is computed — set inputs to hit this edge manually"
            else:
                reason = ""
            for lower in sorted({b.lower for b in t.line_ids}):
                out.append({
                    'source': 'table',
                    'table_code': t.code,
                    'formula_code': formula_rule.code if formula_rule else '',
                    'input_code': input_rule.code if reachable else '',
                    'edge': float(lower),
                    'reachable': reachable,
                    'reason': reason,
                    'label': "BRACKET %s lower %s" % (t.code, _kv(lower)),
                })
        return out

    def _threshold_candidates(self, rules):
        """Source 2 — ``<ref> op <number>`` comparison thresholds in each formula
        (S-G1). Ref resolving to an input → reachable; to a formula/constant →
        listed reachable=False. BRACKET spans are stripped first (no double-count)."""
        by_col = {r.column_letter: r for r in rules if r.column_letter}
        by_code = {r.code: r for r in rules if r.code}
        out = []
        for r in rules:
            if r.column_type != 'formula' or not r.excel_formula:
                continue
            # scan the ORIGINAL excel_formula; strip BRACKET spans, then strip
            # cell-row digits (A2 -> A) so 'A2>26' resolves ref=A, not A2.
            f = self._strip_bracket_spans(r.excel_formula)
            f = re.sub(r'(?<![\w])([A-Za-z]{1,3})\d+(?![\w])', r'\1', f)
            for m in _CMP_RE.finditer(f):
                if m.group(1):
                    ref, op, num = m.group(1), m.group(2), m.group(3)
                else:
                    num, op, ref = m.group(4), m.group(5), m.group(6)
                dep = by_col.get(ref) or by_code.get(ref)   # letter first, then code
                if not dep:
                    continue
                reachable = dep.column_type == 'input'
                out.append({
                    'source': 'threshold',
                    'formula_code': r.code or '',
                    'input_code': dep.code if reachable else '',
                    'ref': dep.code or ref,
                    'edge': float(num),
                    'reachable': reachable,
                    'reason': "" if reachable
                    else "operand is a %s — set inputs to hit this edge manually" % dep.column_type,
                    'label': "%s %s %s" % (dep.code or ref, op, _kv(float(num))),
                })
        return out

    def boundary_candidates(self):
        """All boundary edges the formulas branch on, deduped and ordered
        (reachable first). Pure metadata — never evaluates a formula."""
        self.ensure_one()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)
        cands = self._rate_table_candidates(rules) + self._threshold_candidates(rules)
        seen = set()
        out = []
        for c in cands:
            if c['reachable']:
                k = ('r', c['input_code'], round(c['edge'], 6))
            else:
                k = ('u', c.get('input_code') or c.get('ref') or '',
                     c.get('formula_code') or '', c.get('table_code') or '',
                     round(c['edge'], 6))
            if k in seen:
                continue
            seen.add(k)
            out.append(c)
        out.sort(key=lambda c: (0 if c['reachable'] else 1,
                                c.get('input_code') or c.get('ref') or '', c['edge']))
        for i, c in enumerate(out):
            c['key'] = 'c%d' % i
        return {'ok': True, 'candidates': out,
                'reachable': sum(1 for c in out if c['reachable']),
                'unreachable': sum(1 for c in out if not c['reachable'])}

    # ------------------------------------------------------------------
    # generation (D-G4) — characterization baseline via the C5 path
    # ------------------------------------------------------------------
    def _create_generated_sample(self, inputs, name, description, boundary_key=None):
        """Create one ``generated`` + ``expected_confirmed=False`` sample whose
        expected baseline is the CURRENT engine output for ``inputs``. Shared by
        W84 (boundary) and W49 (AI). The expected is characterization — a
        hypothesis — never confirmed here (D-G3/D-G5)."""
        self.ensure_one()
        Sample = self.env['hr.formula.sample.data']
        s = Sample.create({
            'config_id': self.id,
            'name': name,
            'source_type': 'generated',
            'expected_confirmed': False,
            'boundary_key': boundary_key or False,
            'description': description or '',
            'input_values_json': json.dumps(inputs),
        })
        # create ran _compute_results (depends input_values_json) via the
        # C5-sanctioned _evaluate_rules_with_dependencies path → seed expected
        # from that engine output.
        s.expected_values_json = s.computed_values_json or '{}'
        return s

    def generate_boundary_samples(self, picks, base_sample_id=None):
        """Generate edge−1 / edge / edge+1 rows for each reachable ``pick``
        (``{input_code, edge, label}``). Base inputs are cloned from
        ``base_sample_id`` (default: first sample), overriding only the boundary
        dimension. Deduped by ``boundary_key`` against existing ACTIVE generated
        samples; skips are reported. Capped at 60 created per run (C7/C8)."""
        self.ensure_one()
        Sample = self.env['hr.formula.sample.data']
        by_code_input = {r.code: r for r in self.rule_ids
                         if r.column_type == 'input' and r.code}

        base = Sample.browse(int(base_sample_id)) if base_sample_id else Sample
        if not (base and base.exists() and base.config_id == self):
            base = self.sample_data_ids[:1]
        try:
            base_inputs = json.loads(base.input_values_json or '{}') if base else {}
        except Exception:
            base_inputs = {}
        if not isinstance(base_inputs, dict):
            base_inputs = {}

        existing = {s.boundary_key for s in self.sample_data_ids
                    if s.source_type == 'generated' and s.boundary_key}

        created = skipped = capped = 0
        for p in (picks or []):
            code = (p or {}).get('input_code')
            if not code or code not in by_code_input:
                continue                       # only reachable input dimensions
            try:
                edge = float(p.get('edge'))
            except (TypeError, ValueError):
                continue
            src = p.get('label') or p.get('source') or 'boundary'
            for delta, tag in ((-1, '−1'), (0, '0'), (1, '+1')):
                val = edge + delta
                key = '%s=%s' % (code, _kv(val))
                if key in existing:
                    skipped += 1
                    continue
                if created >= _GEN_CAP:
                    capped += 1
                    continue
                inputs = dict(base_inputs)
                inputs[code] = val
                self._create_generated_sample(
                    inputs, 'Edge %s (%s)' % (key, tag),
                    'Boundary sample from %s' % src, boundary_key=key)
                existing.add(key)
                created += 1
        return {'ok': True, 'created': created, 'skipped': skipped, 'capped': capped}
