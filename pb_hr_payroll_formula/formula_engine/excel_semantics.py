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
    # WDGAP PR-A — dates as Excel serial numbers, and INT
    'excel_int', 'to_serial', 'date_operand', 'serial_to_ymd', 'ymd_to_serial',
    'excel_date', 'excel_year', 'excel_month', 'excel_day', 'excel_days',
    'excel_datedif', 'excel_edate', 'excel_eomonth',
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
# INT and dates (WDGAP PR-A)
# ---------------------------------------------------------------------------
#
# A date inside a formula is an EXCEL SERIAL NUMBER in the 1900 date system —
# the same number Excel shows when a date cell is formatted as a number — so a
# workbook formula gives the same answer here. Serial 1 is 1 Jan 1900 and, as
# in Excel, serial 60 is the 29 Feb 1900 that never existed (Excel kept Lotus
# 1-2-3's leap-year bug); from 1 Mar 1900 (serial 61) on, serials count real
# days.
#
# Blank, unreadable or out-of-range dates make a date function answer 0 (Excel
# would say 1900 or #VALUE!/#NUM!): ``IF(YEAR(x)=0, …)`` is the documented test
# for "no date", and none of these functions ever raises.

import datetime as _dt

_SERIAL_BASE_EARLY = _dt.date(1899, 12, 31)   # serials 1..59
_SERIAL_BASE = _dt.date(1899, 12, 30)         # serials 61..
_SERIAL_MAX = 2958465                         # 31 Dec 9999
_ISO_DATE_RE = re.compile(r'^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ][0-9:.]+)?\s*$')


def excel_int(number):
    """Excel INT — rounds DOWN toward minus infinity: INT(-1.5) = -2."""
    n = coerce_number(number)
    if n is None or math.isnan(n) or math.isinf(n):
        return 0
    return math.floor(n)


def ymd_to_serial(year, month, day):
    """Excel DATE's arithmetic: month and day may overflow either way
    (DATE(2024, 13, 1) is 1 Jan 2025, DATE(2024, 3, 0) is 29 Feb 2024).
    Returns None when the result is outside 1900-01-00 … 9999-12-31."""
    year, month, day = int(year), int(month), int(day)
    if 0 <= year < 1900:
        year += 1900                       # Excel: DATE(24, 1, 1) is 1924
    years, month0 = divmod(month - 1, 12)
    year += years
    if year < 1900 or year > 9999:
        return None
    first = _dt.date(year, month0 + 1, 1)
    if first < _dt.date(1900, 3, 1):
        first_serial = (first - _SERIAL_BASE_EARLY).days
    else:
        first_serial = (first - _SERIAL_BASE).days
    serial = first_serial + day - 1
    if serial < 0 or serial > _SERIAL_MAX:
        return None
    return serial


def serial_to_ymd(serial):
    """(year, month, day) of a serial ≥ 1, Excel's phantom 29 Feb 1900 included."""
    serial = int(serial)
    if serial == 60:
        return 1900, 2, 29
    if serial < 60:
        d = _SERIAL_BASE_EARLY + _dt.timedelta(days=serial)
    else:
        d = _SERIAL_BASE + _dt.timedelta(days=serial)
    return d.year, d.month, d.day


def _date_to_serial(d):
    if isinstance(d, _dt.datetime):
        d = d.date()
    return ymd_to_serial(d.year, d.month, d.day)


def to_serial(value):
    """A date function's argument as a whole serial number, or None for blank,
    unreadable or out of range. Accepts a serial (the time of day is dropped),
    a date / datetime, an ISO text (2024-01-15, 2024-01-15 08:00:00) or a
    number written as text."""
    try:
        if value is None or value is False or value == '':
            return None
        if isinstance(value, (_dt.date, _dt.datetime)):
            serial = _date_to_serial(value)
        elif isinstance(value, str):
            match = _ISO_DATE_RE.match(value)
            if match:
                y, m, d = (int(g) for g in match.groups())
                serial = _date_to_serial(_dt.date(y, m, d))   # invalid day -> ValueError
            else:
                number = coerce_number(value)
                if number is None:
                    return None
                serial = math.floor(number)
        else:
            number = coerce_number(value)
            if number is None or math.isnan(number) or math.isinf(number):
                return None
            serial = math.floor(number)
    except (ValueError, TypeError, OverflowError):
        return None
    if serial is None or serial < 1 or serial > _SERIAL_MAX:
        return None
    return serial


def date_operand(value, raw=None):
    """A component reference INSIDE a date function's arguments.

    ``value`` is what ordinary arithmetic sees (``values``: a date text there
    is 0); ``raw`` is the value as it arrived (``raw_values``). When the raw
    value is a date — an ISO text or a date object — its serial is used;
    otherwise the ordinary value is, unchanged. Outside date functions the
    converter never emits this, so a date component still reads 0 there.
    """
    if isinstance(raw, (_dt.date, _dt.datetime)) or (
            isinstance(raw, str) and _ISO_DATE_RE.match(raw)):
        serial = to_serial(raw)
        return serial if serial is not None else 0
    return value


def _guard(fn):
    """Date functions answer 0 rather than raise (blank or unreadable input)."""
    def wrapper(*args):
        try:
            result = fn(*args)
        except Exception:   # noqa: BLE001 — the documented contract is "0, never raises"
            return 0
        return 0 if result is None else result
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _whole(value):
    """Excel truncates the number arguments of DATE/EDATE/EOMONTH toward zero."""
    number = coerce_number(value)
    if number is None:
        number = 0.0
    return int(number)


@_guard
def excel_date(year, month, day):
    """Excel DATE(year, month, day) -> serial."""
    return ymd_to_serial(_whole(year), _whole(month), _whole(day))


@_guard
def excel_year(date_value):
    serial = to_serial(date_value)
    return serial_to_ymd(serial)[0] if serial else 0


@_guard
def excel_month(date_value):
    serial = to_serial(date_value)
    return serial_to_ymd(serial)[1] if serial else 0


@_guard
def excel_day(date_value):
    serial = to_serial(date_value)
    return serial_to_ymd(serial)[2] if serial else 0


@_guard
def excel_days(end_date, start_date):
    """Excel DAYS(end, start) = end − start in days (negative when the end
    is earlier). 0 when either date is blank."""
    end, start = to_serial(end_date), to_serial(start_date)
    if end is None or start is None:
        return 0
    return end - start


def _months_between(sy, sm, sd, ey, em, ed):
    months = (ey - sy) * 12 + (em - sm)
    if ed < sd:
        months -= 1
    return months


@_guard
def excel_datedif(start_date, end_date, unit):
    """Excel DATEDIF(start, end, unit) with units Y, M, D, YM, MD, YD.

    0 when either date is blank, when the start is after the end (Excel:
    #NUM!) or for an unknown unit. "MD" follows Excel's own documented
    arithmetic (it can give odd answers when the start day is past the end of
    the month before the end date — Microsoft warns about it too)."""
    start, end = to_serial(start_date), to_serial(end_date)
    if start is None or end is None or start > end:
        return 0
    unit = str(unit or '').strip().upper()
    sy, sm, sd = serial_to_ymd(start)
    ey, em, ed = serial_to_ymd(end)
    if unit == 'D':
        return end - start
    if unit == 'M':
        return _months_between(sy, sm, sd, ey, em, ed)
    if unit == 'Y':
        return _months_between(sy, sm, sd, ey, em, ed) // 12
    if unit == 'YM':
        return _months_between(sy, sm, sd, ey, em, ed) % 12
    if unit == 'MD':
        if ed >= sd:
            return ed - sd
        return end - ymd_to_serial(ey, em - 1, sd)
    if unit == 'YD':
        anniversary = ymd_to_serial(ey, sm, sd)
        if anniversary > end:
            anniversary = ymd_to_serial(ey - 1, sm, sd)
        return end - anniversary
    return 0


def _add_months(serial, months, end_of_month):
    y, m, d = serial_to_ymd(serial)
    years, month0 = divmod(m - 1 + months, 12)
    y, m = y + years, month0 + 1
    if y < 1900 or y > 9999:
        return None
    last = ymd_to_serial(y, m + 1, 0)       # day 0 of next month = last day
    if end_of_month:
        return last
    first = ymd_to_serial(y, m, 1)
    return min(first + d - 1, last)


@_guard
def excel_edate(start_date, months):
    """Excel EDATE — same day n months on; clipped to the month's last day
    (EDATE(31 Jan 2024, 1) = 29 Feb 2024)."""
    serial = to_serial(start_date)
    if serial is None:
        return 0
    return _add_months(serial, _whole(months), end_of_month=False)


@_guard
def excel_eomonth(start_date, months):
    """Excel EOMONTH — last day of the month n months on."""
    serial = to_serial(start_date)
    if serial is None:
        return 0
    return _add_months(serial, _whole(months), end_of_month=True)


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
