# -*- coding: utf-8 -*-
"""Single source of truth for expected-vs-computed comparison (F6).

Extracted from ``hr.formula.sample.data._compute_validation`` so sample
validation and Shadow Parallel Runs share ONE numeric-coercion semantics. The
coercion is a strict superset of the original ``_coerce_number`` (plain
``float()``): it additionally tolerates the thousands/decimal separators and
currency glyphs that appear in real client Excel exports — but any value the
original coerced to a number still coerces to the *same* number, so existing
sample verdicts are unchanged (regression-checked on the VN demo).

``compare_values`` reports cell mismatches under an ABSOLUTE per-component
tolerance (the right semantics for cell-by-cell payroll migration: "±1 currency
unit"). Sample validation keeps its own percentage-based verdict — only the
coercion is shared.
"""
import re

# strip a leading currency symbol / trailing % and surrounding whitespace
_CURRENCY_RE = re.compile(r'^[\s ]*[₫$€£¥₹]?[\s ]*')
_TRAILING_RE = re.compile(r'[\s %]*$')


def coerce_number(value):
    """Best-effort numeric coercion. Returns a float or None (None == "not a
    number", never a silent 0). Handles ints/floats, bare numeric strings, and
    the common Excel-export string forms ``"1,234.5"`` / ``"1.234,5"`` /
    ``"₫ 2,405,236"`` / ``"12%"``. A blank/empty value is None (missing)."""
    if value is None:
        return None
    if isinstance(value, bool):          # guard: bool is an int subclass
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    s = value.strip()
    if not s:
        return None
    # plain path first — matches the original float() behaviour exactly
    try:
        return float(s)
    except ValueError:
        pass
    # strip currency glyph / percent / spaces, then reconcile separators
    s = _CURRENCY_RE.sub('', s)
    s = _TRAILING_RE.sub('', s)
    s = s.replace(' ', '').replace(' ', '')
    if not s:
        return None
    has_comma, has_dot = ',' in s, '.' in s
    if has_comma and has_dot:
        # the LAST separator is the decimal point; the other groups thousands
        if s.rfind(',') > s.rfind('.'):        # 1.234,56  -> European
            s = s.replace('.', '').replace(',', '.')
        else:                                  # 1,234.56  -> US
            s = s.replace(',', '')
    elif has_comma:
        # comma only: decimal if it looks like one (single, 1-2 trailing digits)
        if re.fullmatch(r'-?\d+,\d{1,2}', s):
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')             # thousands grouping
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def default_tolerance(number_format):
    """Per-format default absolute tolerance (D6.5). Currency rounds to ±1 unit,
    percentages to ±0.0001, counts/integers must be exact."""
    if number_format == 'percentage':
        return 0.0001
    if number_format == 'integer':
        return 0.0
    if number_format == 'currency':
        return 1.0
    return 0.5


def compare_values(expected, computed, tolerance):
    """Return ``[{'code','expected','computed','delta'}]`` for MISMATCHES only.

    ``tolerance``: ``{code_or_'*': abs_tolerance}``. A non-numeric expected value
    is skipped (we don't invent a comparison). A missing/non-numeric COMPUTED
    value for a numeric expected IS a mismatch (``delta=None``) — silence is the
    enemy: a broken component must not read as a matched 0."""
    out = []
    for code, exp_raw in (expected or {}).items():
        exp = coerce_number(exp_raw)
        if exp is None:
            continue                     # non-numeric expected: skip, don't guess
        comp = coerce_number((computed or {}).get(code))
        tol = tolerance.get(code, tolerance.get('*', 0.5)) if tolerance else 0.5
        if comp is None or abs(comp - exp) > tol:
            out.append({
                'code': code,
                'expected': exp,
                'computed': comp,
                'delta': None if comp is None else round(comp - exp, 6),
            })
    return out
