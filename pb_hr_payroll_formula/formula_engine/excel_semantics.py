# -*- coding: utf-8 -*-
"""Excel semantics — the single source of truth for Excel-compatible math.

Both evaluation paths (``hr.formula.rule._run_formula`` and
``FormulaEvaluator.evaluate_single``) delegate here so they can never drift
apart again. Every function mirrors documented Excel behaviour:

- ROUND is half-AWAY-FROM-ZERO (Python's built-in round() is banker's
  rounding — round-half-even — which silently loses/gains units on .5
  boundaries: round(2.5) == 2 in Python, 3 in Excel).
- ROUNDUP always moves away from zero, ROUNDDOWN always toward zero
  (math.ceil/math.floor get both wrong for negative numbers, and
  float-multiply tricks corrupt exact values like ROUNDUP(1.2, 1)).
- CEILING/FLOOR take a *significance* argument (round to a multiple),
  they are not 1-argument math.ceil/math.floor.
- Text comparison is case-insensitive ("ct" = "CT" is TRUE in Excel).

All implementations use decimal.Decimal(str(x)) so binary-float artifacts
(2.675 stored as 2.67499999…) round the way a spreadsheet user expects.
"""

import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_UP, ROUND_DOWN

__all__ = [
    'coerce_value', 'coerce_number',
    'excel_round', 'excel_roundup', 'excel_rounddown',
    'excel_ceiling', 'excel_floor',
    'excel_if', 'excel_iferror', 'excel_not', 'excel_streq',
    'excel_isblank', 'is_blank_value',
    'sum_list', 'min_list', 'max_list', 'avg_list', 'counta_list',
    'assert_safe_expression', 'UnsafeFormulaError',
]


# ---------------------------------------------------------------------------
# Value coercion (shared by both evaluation paths)
# ---------------------------------------------------------------------------

def coerce_number(value):
    """Convert a value to float for numeric functions; None if non-numeric.

    Handles thousands separators / decimal marks ("1.234.567", "1,5") and
    trailing-% strings ("8%" -> 0.08). Booleans map to 1.0/0.0 like Excel.
    """
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        import numbers
        if isinstance(value, numbers.Number):
            return float(value)
    except Exception:
        pass
    if isinstance(value, str):
        cleaned = value.strip().replace(' ', '')
        if not cleaned:
            return None
        is_percent = False
        if cleaned.endswith('%'):
            cleaned = cleaned[:-1]
            is_percent = True
        try:
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if all(len(p) == 3 for p in parts[1:]):
                    cleaned = ''.join(parts)
                else:
                    cleaned = cleaned.replace(',', '.')
            elif '.' in cleaned:
                parts = cleaned.split('.')
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    cleaned = ''.join(parts)
            number = float(cleaned)
            if is_percent:
                number = number / 100
            return number
        except (ValueError, TypeError):
            return None
    return None


def coerce_value(value):
    """Arithmetic-context coercion used to build the ``values`` eval dict.

    - None/empty -> 0
    - numbers kept as-is
    - numeric strings ("1.234,50", "8%") -> float
    - non-numeric strings -> 0 (string comparisons read ``raw_values``)
    """
    if value is None or value == '':
        return 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        number = coerce_number(value)
        return number if number is not None else 0
    return 0


def is_blank_value(value):
    """True when a raw value should be treated as blank (Excel-empty)."""
    if value is None or value == '':
        return True
    if isinstance(value, str) and value.strip() in ('', '0', '0.0', '0.00'):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Rounding family (Decimal-based, Excel semantics)
# ---------------------------------------------------------------------------

def _to_decimal(number):
    if isinstance(number, Decimal):
        return number
    n = coerce_number(number)
    if n is None:
        n = 0.0
    try:
        return Decimal(str(n))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def excel_round(number, digits=0):
    """Excel ROUND — half away from zero. ROUND(2.5,0)=3, ROUND(-2.5,0)=-3,
    ROUND(12500,-3)=13000."""
    d = _to_decimal(number)
    q = Decimal(1).scaleb(-int(digits))
    return float(d.quantize(q, rounding=ROUND_HALF_UP))


def excel_roundup(number, digits=0):
    """Excel ROUNDUP — away from zero. ROUNDUP(-1.2,0)=-2, ROUNDUP(1.2,1)=1.2."""
    d = _to_decimal(number)
    q = Decimal(1).scaleb(-int(digits))
    return float(d.quantize(q, rounding=ROUND_UP))


def excel_rounddown(number, digits=0):
    """Excel ROUNDDOWN — toward zero. ROUNDDOWN(-1.8,0)=-1."""
    d = _to_decimal(number)
    q = Decimal(1).scaleb(-int(digits))
    return float(d.quantize(q, rounding=ROUND_DOWN))


def excel_ceiling(number, significance=1):
    """Excel CEILING(number, significance) — round up to a multiple of
    significance. CEILING(147,100)=200, CEILING(-2.5,2)=-2 (toward +inf
    divided semantics match math.ceil on the quotient)."""
    sig = _to_decimal(significance)
    if sig == 0:
        return 0.0
    d = _to_decimal(number)
    return float(math.ceil(d / sig) * sig)


def excel_floor(number, significance=1):
    """Excel FLOOR(number, significance) — round down to a multiple of
    significance. FLOOR(147,100)=100."""
    sig = _to_decimal(significance)
    if sig == 0:
        return 0.0
    d = _to_decimal(number)
    return float(math.floor(d / sig) * sig)


# ---------------------------------------------------------------------------
# Logic / text
# ---------------------------------------------------------------------------

def excel_if(condition, true_val, false_val=0):
    """Eager IF fallback. The converter rewrites IF() into a lazy Python
    ternary; this survives only for legacy cached python_formula strings."""
    return true_val if condition else false_val


def excel_iferror(value, error_value):
    """Excel IFERROR. The converter wraps the first argument in a lambda so
    evaluation errors (#DIV/0!, TypeError…) are actually catchable — exactly
    what Excel does. Plain (already-evaluated) values are still accepted for
    legacy cached formulas."""
    if callable(value):
        try:
            value = value()
        except Exception:
            return error_value
    if value is None or value == '':
        return error_value
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return error_value
    return value


def excel_not(value):
    """Excel NOT as a call (converter maps NOT( -> self._not( so that
    NOT(x)*5 keeps call precedence — Python's `not` operator binds looser
    than `*` and silently computes not(x*5))."""
    return not value


def excel_streq(left, right):
    """Excel text equality: case-insensitive, whitespace-trimmed.
    =IF(D1="ct") is TRUE for "CT" in Excel."""
    if left is None:
        left = ''
    if right is None:
        right = ''
    return str(left).strip().casefold() == str(right).strip().casefold()


def excel_isblank(value):
    """Excel ISBLANK."""
    return value in (None, '')


# ---------------------------------------------------------------------------
# List aggregates (ignore non-numeric members, like Excel over text cells)
# ---------------------------------------------------------------------------

def _as_list(values_list):
    if values_list is None:
        return []
    if not isinstance(values_list, (list, tuple)):
        return [values_list]
    return list(values_list)


def sum_list(values_list):
    total = 0.0
    for value in _as_list(values_list):
        number = coerce_number(value)
        if number is not None:
            total += number
    return total


def min_list(values_list):
    numbers = [coerce_number(v) for v in _as_list(values_list)]
    numbers = [v for v in numbers if v is not None]
    return min(numbers) if numbers else 0.0


def max_list(values_list):
    numbers = [coerce_number(v) for v in _as_list(values_list)]
    numbers = [v for v in numbers if v is not None]
    return max(numbers) if numbers else 0.0


def avg_list(values_list):
    """Excel AVERAGE — includes zeros (a 0 salary is a value, not a gap);
    ignores only non-numeric members."""
    numbers = [coerce_number(v) for v in _as_list(values_list)]
    numbers = [v for v in numbers if v is not None]
    return sum(numbers) / len(numbers) if numbers else 0


def counta_list(values_list):
    return len([v for v in _as_list(values_list) if v not in (None, '')])


# ---------------------------------------------------------------------------
# Eval hardening
# ---------------------------------------------------------------------------

class UnsafeFormulaError(Exception):
    pass


_STRING_LITERAL_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")

# The converter only ever emits: values/raw_values lookups, self._helper
# calls, math.*, the whitelisted builtins, lambda (for IFERROR), numbers and
# operators. Anything below can therefore never appear legitimately outside
# a string literal — its presence means formula text is trying to reach the
# ORM / interpreter internals through eval().
_FORBIDDEN_RE = re.compile(
    r"__"
    r"|\b(env|sudo|unlink|browse|search|search_count|read|write|create|copy"
    r"|mapped|filtered|sorted_by|with_context|with_user|with_company|cr|registry"
    r"|exec|eval|compile|open|input|breakpoint|globals|locals|vars|dir"
    r"|getattr|setattr|delattr|object|super|bytes|bytearray|memoryview"
    r"|import|importlib|subprocess|os|sys)\b"
)


def assert_safe_expression(python_code):
    """Reject converted expressions containing tokens the converter never
    emits (string literals are stripped first, so text like ="env" is fine).
    Raises UnsafeFormulaError — callers surface it as a normal loud
    evaluation error on the rule."""
    stripped = _STRING_LITERAL_RE.sub('', python_code or '')
    match = _FORBIDDEN_RE.search(stripped)
    if match:
        raise UnsafeFormulaError(
            "Formula contains a forbidden token %r and was not evaluated."
            % match.group(0)
        )
