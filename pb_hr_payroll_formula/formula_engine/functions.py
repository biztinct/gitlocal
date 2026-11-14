# -*- coding: utf-8 -*-
"""The ONE list of functions a scheme formula can use (WDGAP PR-A).

Before this table there were five lists and they disagreed: the converter's
``function_map`` (what actually computes), ``FormulaValidator`` and
``FormulaParser`` (which accepted TODAY, NOW, LEFT, IFS … that compute
nothing), a hard-coded 16-name strip in ``hr.formula.rule.validate_formula``
(which called YEAR or ROUNDUP an "invalid column reference"), and the formula
bar's own list (which offered all of the above). A formula using an offered
but unconverted function silently became 0 on the payslip.

Everything is now DERIVED from ``_TABLE`` below — clone of the table-driven
precedent ``rule_formula._TABLE``:

* ``converter_function_map()`` — the converter's regex -> emitted-helper map
  (order preserved: the first 25 entries are the pre-PR-A map, byte for byte);
* ``FUNCTION_NAMES`` — what the validators accept and what the list offers;
* ``function_list()`` — the formula bar / Studio palette (served by RPC);
* ``problems()`` — the save-time check (unknown name, TODAY/NOW, arity).

Pure Python, stdlib only (plus Odoo's lazy translation when Odoo is there), so
the bare-``python3`` batteries load it the same way Odoo does.

Help lines and refusals are product voice: plain words, never the platform's
name (white-label rule).
"""
import difflib
import re

try:  # Odoo present: messages translate in the caller's language
    from odoo.tools.translate import LazyTranslate
    _lt = LazyTranslate(__name__)
except ImportError:  # bare python3 (batteries, standalone tests)
    class _Plain(str):
        """English stand-in for a lazy translation."""

    def _lt(source, *args, **kwargs):
        if args:
            return _Plain(source % args)
        if kwargs:
            return _Plain(source % kwargs)
        return _Plain(source)


#: Unlimited arity marker.
MANY = None

# name -> (kind, emitted python, min args, max args, category, signature,
#          help line, example)
#
# kind:
#   'call'    — converted by the generic ``\bNAME\(`` -> emitted helper pass
#   'special' — converted by a dedicated pass of the converter (VLOOKUP is
#               resolved to a column of the same scheme; BRACKET is expanded
#               from the scheme's band tables before anything else runs)
#   'literal' — TRUE() / FALSE()
#
# ORDER IS LOAD-BEARING for the 'call' rows: it is the order the converter
# applies the patterns in. The first 25 rows are the pre-PR-A ``function_map``
# exactly; new functions are appended after them.
_TABLE = (
    ('SUM', 'call', 'sum([', 1, MANY, 'math', 'SUM(a, b, …)',
     _lt("Adds the values up."), '=SUM(BASIC, ALLOWANCE)'),
    ('AVERAGE', 'call', 'self._avg([', 1, MANY, 'math', 'AVERAGE(a, b, …)',
     _lt("The average of the values (a zero counts)."), '=AVERAGE(MONTH1, MONTH2, MONTH3)'),
    ('MIN', 'call', 'min([', 1, MANY, 'math', 'MIN(a, b, …)',
     _lt("The smallest of the values."), '=MIN(BASIC, CAP)'),
    ('MAX', 'call', 'max([', 1, MANY, 'math', 'MAX(a, b, …)',
     _lt("The largest of the values."), '=MAX(0, TAXABLE)'),
    ('ABS', 'call', 'abs(', 1, 1, 'math', 'ABS(x)',
     _lt("Drops the minus sign."), '=ABS(DEDUCTION)'),
    ('ROUND', 'call', 'self._round(', 1, 2, 'math', 'ROUND(x, places)',
     _lt("Rounds to the given number of decimal places; a half rounds away from zero."),
     '=ROUND(BASIC * 8%, 0)'),
    ('IF', 'call', 'self._if(', 2, 3, 'logic', 'IF(test, then, otherwise)',
     _lt("Gives one value when the test is true and another when it is not."),
     '=IF(DAYSWORKED > 0, BASIC, 0)'),
    ('IFERROR', 'call', 'self._iferror(', 2, 2, 'logic', 'IFERROR(value, fallback)',
     _lt("The value, or the fallback when it cannot be worked out (for example a division by zero)."),
     '=IFERROR(BASIC / DAYS, 0)'),
    ('ISBLANK', 'call', 'self._isblank(', 1, 1, 'logic', 'ISBLANK(x)',
     _lt("True when the value is empty."), '=IF(ISBLANK(BANKACC), 1, 0)'),
    ('AND', 'call', 'all([', 1, MANY, 'logic', 'AND(test, test, …)',
     _lt("True only when every test is true."), '=IF(AND(GRADE = "A", DAYSWORKED > 20), 500, 0)'),
    ('OR', 'call', 'any([', 1, MANY, 'logic', 'OR(test, test, …)',
     _lt("True when any test is true."), '=IF(OR(REGION = "HN", REGION = "HCM"), 1, 0)'),
    ('NOT', 'call', 'self._not(', 1, 1, 'logic', 'NOT(test)',
     _lt("The opposite of the test."), '=IF(NOT(ISBLANK(BONUS)), BONUS, 0)'),
    ('COUNTA', 'call', 'self._counta([', 1, MANY, 'math', 'COUNTA(a, b, …)',
     _lt("How many of the values are filled in."), '=COUNTA(CHILD1, CHILD2, CHILD3)'),
    ('POWER', 'call', 'pow(', 2, 2, 'math', 'POWER(x, n)',
     _lt("x raised to the power n."), '=POWER(1.05, YEARS)'),
    ('SQRT', 'call', 'math.sqrt(', 1, 1, 'math', 'SQRT(x)',
     _lt("The square root."), '=SQRT(AREA)'),
    ('CEILING', 'call', 'self._ceiling(', 1, 2, 'math', 'CEILING(x, step)',
     _lt("Rounds up to a multiple of the step."), '=CEILING(PAY, 1000)'),
    ('FLOOR', 'call', 'self._floor(', 1, 2, 'math', 'FLOOR(x, step)',
     _lt("Rounds down to a multiple of the step."), '=FLOOR(PAY, 1000)'),
    ('SUMIF', 'call', 'self._sumif(', 2, 3, 'math', 'SUMIF(value, match, amount)',
     _lt("The amount when the value matches, otherwise 0 (one person at a time)."),
     '=SUMIF(REGION, "HN", ALLOWANCE)'),
    ('SUMIFS', 'call', 'self._sumifs(', 1, MANY, 'math', 'SUMIFS(amount, value, match, …)',
     _lt("The amount when every value matches, otherwise 0 (one person at a time)."),
     '=SUMIFS(ALLOWANCE, REGION, "HN", GRADE, "A")'),
    ('ROW', 'call', 'self._row(', 0, 1, 'math', 'ROW()',
     _lt("The row number; in a scheme this is always 1."), '=ROW()'),
    ('SUBTOTAL', 'call', 'self._subtotal(', 2, MANY, 'math', 'SUBTOTAL(kind, a, b, …)',
     _lt("A total of the values: kind 9 adds them up, 1 averages, 4 the largest, 5 the smallest."),
     '=SUBTOTAL(9, BASIC, ALLOWANCE)'),
    ('MOD', 'call', 'self._mod(', 2, 2, 'math', 'MOD(x, divisor)',
     _lt("What is left over after dividing."), '=MOD(DAYS, 7)'),
    ('SIGN', 'call', 'self._sign(', 1, 1, 'math', 'SIGN(x)',
     _lt("1 when positive, -1 when negative, 0 when zero."), '=SIGN(ADJUSTMENT)'),
    ('ROUNDUP', 'call', 'self._roundup(', 1, 2, 'math', 'ROUNDUP(x, places)',
     _lt("Rounds away from zero."), '=ROUNDUP(HOURS, 0)'),
    ('ROUNDDOWN', 'call', 'self._rounddown(', 1, 2, 'math', 'ROUNDDOWN(x, places)',
     _lt("Rounds toward zero."), '=ROUNDDOWN(HOURS, 0)'),
    # ---- WDGAP PR-A ----------------------------------------------------------
    ('INT', 'call', 'self._int(', 1, 1, 'math', 'INT(x)',
     _lt("Rounds down to a whole number (INT(-1.5) is -2)."), '=INT(HOURS / 8)'),
    ('DATE', 'call', 'self._date(', 3, 3, 'date', 'DATE(year, month, day)',
     _lt("Makes a date. The last day of the pay period is DATE(PAYYEAR, PAYMONTH, ENDDAY)."),
     '=DATE(PAYYEAR, PAYMONTH, ENDDAY)'),
    ('YEAR', 'call', 'self._year(', 1, 1, 'date', 'YEAR(date)',
     _lt("The year of a date; 0 when the date is empty."), '=YEAR(JOINDATE)'),
    ('MONTH', 'call', 'self._month(', 1, 1, 'date', 'MONTH(date)',
     _lt("The month of a date (1 to 12); 0 when the date is empty."), '=MONTH(JOINDATE)'),
    ('DAY', 'call', 'self._day(', 1, 1, 'date', 'DAY(date)',
     _lt("The day of the month of a date; 0 when the date is empty."), '=DAY(JOINDATE)'),
    ('DAYS', 'call', 'self._days(', 2, 2, 'date', 'DAYS(end, start)',
     _lt("The number of days from the start date to the end date."),
     '=DAYS(DATE(PAYYEAR, PAYMONTH, ENDDAY), JOINDATE)'),
    ('DATEDIF', 'call', 'self._datedif(', 3, 3, 'date', 'DATEDIF(start, end, "Y")',
     _lt('Whole years ("Y"), months ("M") or days ("D") between two dates; "YM", "MD" and "YD" leave out the years or months.'),
     '=DATEDIF(JOINDATE, DATE(PAYYEAR, PAYMONTH, ENDDAY), "Y")'),
    ('EDATE', 'call', 'self._edate(', 2, 2, 'date', 'EDATE(date, months)',
     _lt("The same day a number of months later (or earlier, with a minus)."),
     '=EDATE(JOINDATE, 2)'),
    ('EOMONTH', 'call', 'self._eomonth(', 2, 2, 'date', 'EOMONTH(date, months)',
     _lt("The last day of the month, a number of months later (0 = the same month)."),
     '=EOMONTH(JOINDATE, 0)'),
    # ---- handled by dedicated converter passes --------------------------------
    ('VLOOKUP', 'special', '', 3, 4, 'lookup', 'VLOOKUP(value, A2:C2, column, 0)',
     _lt("Reads another column of this scheme for the same person."),
     '=VLOOKUP(CODE, A2:C2, 3, 0)'),
    ('BRACKET', 'special', '', 2, 2, 'lookup', 'BRACKET(table, amount)',
     _lt("Works out an amount from one of this scheme's band tables (for example income tax bands)."),
     '=BRACKET(PITTABLE, TAXABLE)'),
    ('TRUE', 'literal', '', 0, 0, 'logic', 'TRUE()',
     _lt("Yes (counts as 1)."), '=IF(ISBLANK(BONUS), FALSE(), TRUE())'),
    ('FALSE', 'literal', '', 0, 0, 'logic', 'FALSE()',
     _lt("No (counts as 0)."), '=IF(ISBLANK(BONUS), FALSE(), TRUE())'),
)

FUNCTION_NAMES = frozenset(row[0] for row in _TABLE)

#: Functions whose ARGUMENTS are dates. Inside them a component that holds a
#: date (an ISO text such as 2024-01-15, or a date) is read as that date
#: rather than as the 0 an ordinary sum would see (``excel_semantics.date_operand``).
DATE_ARGUMENT_HELPERS = (
    'self._year(', 'self._month(', 'self._day(', 'self._days(',
    'self._datedif(', 'self._edate(', 'self._eomonth(',
)

#: Names added by WDGAP PR-A. The converter's code pass leaves one of THESE
#: alone when it is directly followed by "(" even if a component carries the
#: same code (a scheme may already have a component coded DAY or DAYS). Older
#: names keep their old treatment exactly — no stored formula may change.
NEW_IN_PRA = frozenset(('INT', 'DATE', 'YEAR', 'MONTH', 'DAY', 'DAYS',
                        'DATEDIF', 'EDATE', 'EOMONTH'))

_PERIOD_EXAMPLE = 'DATE(PAYYEAR, PAYMONTH, ENDDAY)'

#: Spreadsheet functions that are refused on save with a reason of their own.
REFUSED = {
    'TODAY': _lt("TODAY() can't be used in a formula. A payslip must give the same answer whenever it is worked out. Use the pay period instead, for example DATE(PAYYEAR, PAYMONTH, ENDDAY)."),
    'NOW': _lt("NOW() can't be used in a formula. A payslip must give the same answer whenever it is worked out. Use the pay period instead, for example DATE(PAYYEAR, PAYMONTH, ENDDAY)."),
}

#: Codes a NEW component may not take: every function name, and the refused ones.
RESERVED_CODE_NAMES = FUNCTION_NAMES | frozenset(REFUSED)

_CATEGORY_LABELS = {
    'math': _lt("Numbers"),
    'logic': _lt("Conditions"),
    'date': _lt("Dates"),
    'lookup': _lt("Look up"),
}
CATEGORY_ORDER = ('math', 'logic', 'date', 'lookup')


def rows():
    """The table as dicts (untranslated lazy help), in table order."""
    out = []
    for name, kind, emit, lo, hi, cat, sig, help_line, example in _TABLE:
        out.append({'name': name, 'kind': kind, 'emit': emit, 'min_args': lo,
                    'max_args': hi, 'category': cat, 'signature': sig,
                    'help': help_line, 'example': example})
    return out


def converter_function_map():
    """``{regex: emitted helper}`` for the converter's generic function pass."""
    return {r'\b%s\(' % name: emit
            for name, kind, emit, *_rest in _TABLE if kind == 'call'}


def converter_special_names():
    """Names the converter handles in a dedicated pass (not the generic map)."""
    return frozenset(name for name, kind, *_rest in _TABLE if kind != 'call')


def function_list(translate=str):
    """What the formula bar and the Studio palette offer — every row of the
    table, nothing else. ``translate`` turns a lazy text into the reader's
    language (``env._`` inside Odoo)."""
    out = []
    for row in rows():
        out.append({
            'name': row['name'],
            'category': row['category'],
            'category_label': translate(_CATEGORY_LABELS[row['category']]),
            'signature': row['signature'],
            'help': translate(row['help']),
            'example': row['example'],
        })
    return out


# ---------------------------------------------------------------------------
# The save-time check
# ---------------------------------------------------------------------------

_STRING_RE = re.compile(r'"(?:[^"]|"")*"')
_CALL_RE = re.compile(r'(?<![A-Za-z0-9_.$])([A-Za-z_][A-Za-z0-9_.]*)\s*\(')


def _blank_strings(formula):
    return _STRING_RE.sub('""', formula or '')


def _args_of(text, open_index):
    """Number of top-level arguments of the call whose "(" is at open_index,
    or None when the bracket never closes."""
    depth, count, saw = 0, 0, False
    for i in range(open_index, len(text)):
        ch = text[i]
        if ch == '(':
            depth += 1
            if depth == 1:
                continue
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return (count + 1) if saw else 0
        if depth == 1 and ch == ',':
            count += 1
            saw = True
        elif depth >= 1 and not ch.isspace():
            saw = True
    return None


def function_calls(formula):
    """[(NAME, argument count or None)] for every call in the formula, in
    order. Quoted text is not read (a job title can contain brackets)."""
    text = _blank_strings(formula)
    calls = []
    for match in _CALL_RE.finditer(text):
        name = match.group(1).upper()
        calls.append((name, _args_of(text, match.end() - 1)))
    return calls


def nearest(name):
    """The supported function whose name is closest to ``name``, or ''."""
    hits = difflib.get_close_matches(name.upper(), sorted(FUNCTION_NAMES), n=1, cutoff=0.6)
    return hits[0] if hits else ''


def problems(formula):
    """Every reason a NEW formula is refused on save, as lazy texts.

    * TODAY() / NOW() — refused with their own sentence;
    * a name that is not in the table — named, with the nearest one offered;
    * a known function with the wrong number of values.

    Stored formulas are never re-checked by this: it runs only where a person
    saves a formula.
    """
    out, seen = [], set()
    by_name = {row[0]: row for row in _TABLE}
    for name, nargs in function_calls(formula):
        if name in seen:
            continue
        if name in REFUSED:
            seen.add(name)
            out.append(REFUSED[name])
            continue
        row = by_name.get(name)
        if row is None:
            seen.add(name)
            suggestion = nearest(name)
            if suggestion:
                out.append(_lt("%(name)s is not a function formulas can use. Did you mean %(suggestion)s?",
                               name=name, suggestion=suggestion))
            else:
                out.append(_lt("%(name)s is not a function formulas can use. The function list shows the ones that work.",
                               name=name))
            continue
        lo, hi = row[3], row[4]
        if nargs is not None and (nargs < lo or (hi is not MANY and nargs > hi)):
            seen.add(name)
            out.append(_lt("%(name)s has the wrong number of values. Write it like this: %(example)s",
                           name=name, example=row[8].lstrip('=')))
    return out


def refusal(formula, translate=str):
    """The plain sentence(s) refusing ``formula`` on save, or ''."""
    return ' '.join(translate(p) for p in problems(formula))
