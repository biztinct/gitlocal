# -*- coding: utf-8 -*-
"""The transformation rule's EXCEL lane — bracket refs over `excel_semantics`.

Integrations Cycle 8. A transformation rule has three lanes: guided steps (no
code at all), this one, and the legacy advanced lane. This module is the
second, and it exists so that a payroll manager who thinks in spreadsheets can
write

    [totalWorkedHours]/3600 + HOURS([paidLeaveHours])

and get the same number the guided steps produce — with the SAME arithmetic the
rest of the product uses.

WHY THIS IS NOT A SECOND EVALUATOR. Every operation below delegates to
`excel_semantics`: the rounding family, the list aggregates, text equality,
IFERROR, the coercions and `assert_safe_expression`. What is written here is
only the part `excel_semantics` cannot know about — how a *record dict* becomes
a value (`[bracket]` refs) and how a call tree becomes a Python expression. The
column-oriented converter in `hr.formula.rule._convert_excel_to_python` cannot
be reused: it resolves A1/B2 cell references and column ranges against a
`hr.formula.config`, and a transformation rule has neither a grid nor columns.

THE REFERENCE RULE. `[Some Field]` reads the record dict:

  1. the EXACT key, as the API spells it — always tried first, because two
     Zoho fields have been seen to differ only in case;
  2. failing that, a case-insensitive / space-and-underscore-insensitive match,
     so `[actual pay hour]` finds `Actual_Pay_Hour`. A novice who reads a label
     off the screen should not have to know which of the two it was.

An unresolvable reference is a COMPILE error, not a silent zero: the name is
checked against the field catalogue before a rule can be saved, and a formula
that survived that check but cannot resolve at run time is a real change in the
payload, which is the kind of thing `last_error` exists to say out loud.

LAZINESS. `IF` and `IFERROR` take lambdas, so the branch that is not chosen is
never evaluated. `excel_semantics.excel_iferror` already accepts a callable for
exactly this reason; `_lazy_if` is a three-line ternary beside it rather than a
second implementation of anything. Eager branches would make
`IF([h]=0, 0, 100/[h])` raise on every zero row and drop it from the aggregate
— a wrong answer that looks like a right one.
"""

import re

from . import excel_semantics
from .excel_semantics import (
    UnsafeFormulaError, assert_safe_expression, avg_list, coerce_number,
    counta_list, excel_ceiling, excel_floor, excel_iferror, excel_isblank,
    excel_not, excel_round, excel_rounddown, excel_roundup, excel_streq,
    max_list, min_list, sum_list,
)

__all__ = [
    'Cell', 'RuleFormulaError', 'compile_rule_formula', 'eval_rule_formula',
    'resolve_ref', 'FUNCTION_HELP', 'SUPPORTED_FUNCTIONS',
]


class RuleFormulaError(ValueError):
    """A formula that cannot be compiled. The message is written for a human —
    it is printed in the composer's proof rail and returned by the save
    refusal, so it names the token rather than the traceback."""


# ---------------------------------------------------------------------------
# Reference resolution — a record dict is not a spreadsheet row
# ---------------------------------------------------------------------------

def _norm(key):
    """A field name reduced to what a human would call 'the same name'."""
    return re.sub(r'[\s_.\-]+', '', str(key or '')).casefold()


class Cell(str):
    """One record field, behaving the way a spreadsheet cell behaves.

    A payload is not a spreadsheet: `totalWorkedHours` arrives as the STRING
    `"36000"`, and `[totalWorkedHours]/3600` has to mean 10 rather than raise.
    Excel solves this by having one value that reads as text in a text context
    and as a number in an arithmetic one, and this is that value.

    It subclasses `str` on purpose rather than wrapping: every helper in
    `excel_semantics` already knows what to do with a string (`coerce_number`
    handles thousands separators, decimal marks and trailing `%`), so the
    delegation stays real instead of becoming a second set of conversions that
    can drift. What is overridden is only the arithmetic and the comparisons,
    where `str`'s own meaning (concatenate, repeat, compare alphabetically) is
    the wrong one and is wrong SILENTLY: `"9" > "10"` is True for a string.
    """

    __slots__ = ()
    __hash__ = str.__hash__

    @staticmethod
    def of(value):
        if value is None or value is False:
            return Cell('')
        if value is True:
            return Cell('1')
        return Cell(value if isinstance(value, str) else str(value))

    @property
    def n(self):
        """This cell in an arithmetic context. Blank and unreadable are 0,
        exactly as `coerce_value` defines it for the rest of the product."""
        return excel_semantics.coerce_value(str(self))

    @staticmethod
    def _num(other):
        if isinstance(other, Cell):
            return other.n
        return excel_semantics.coerce_value(other)

    def __add__(self, other):
        return self.n + self._num(other)

    def __radd__(self, other):
        return self._num(other) + self.n

    def __sub__(self, other):
        return self.n - self._num(other)

    def __rsub__(self, other):
        return self._num(other) - self.n

    def __mul__(self, other):
        return self.n * self._num(other)

    def __rmul__(self, other):
        return self._num(other) * self.n

    def __truediv__(self, other):
        return self.n / self._num(other)

    def __rtruediv__(self, other):
        return self._num(other) / self.n

    def __pow__(self, other):
        return self.n ** self._num(other)

    def __rpow__(self, other):
        return self._num(other) ** self.n

    def __neg__(self):
        return -self.n

    def __float__(self):
        return float(self.n)

    def _both_numeric(self, other):
        mine = coerce_number(str(self))
        theirs = coerce_number(str(other) if isinstance(other, Cell) else other)
        if mine is None or theirs is None:
            return None
        return mine, theirs

    def __eq__(self, other):
        pair = self._both_numeric(other)
        if pair is not None:
            return pair[0] == pair[1]
        return excel_streq(str(self), '' if other is None else other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def _cmp(self, other, op):
        pair = self._both_numeric(other)
        if pair is None:
            return False        # a text value never sorts into a > test
        return op(pair[0], pair[1])

    def __lt__(self, other):
        return self._cmp(other, lambda a, b: a < b)

    def __le__(self, other):
        return self._cmp(other, lambda a, b: a <= b)

    def __gt__(self, other):
        return self._cmp(other, lambda a, b: a > b)

    def __ge__(self, other):
        return self._cmp(other, lambda a, b: a >= b)


def resolve_ref(row, name):
    """`[name]` against one record dict. Exact key first, then normalised.

    Returns `(value, found)`. The caller decides what an absent field means —
    inside an aggregate it is "this row has nothing to contribute", which is
    not the same as zero.
    """
    if not isinstance(row, dict):
        return None, False
    if name in row:
        return row[name], True
    target = _norm(name)
    for key, value in row.items():
        if _norm(key) == target:
            return value, True
    return None, False


# ---------------------------------------------------------------------------
# The function table — every entry delegates to excel_semantics
# ---------------------------------------------------------------------------

def _lazy_if(condition, true_branch, false_branch=0):
    """Excel IF with unevaluated branches (see the module docstring)."""
    chosen = true_branch if condition else false_branch
    return chosen() if callable(chosen) else chosen


def _hours(value):
    """`HOURS("7:30")` -> 7.5. The one conversion a spreadsheet cannot express.

    Zoho's attendance summary returns paid leave as an "H:MM" STRING beside a
    worked total that is an integer count of seconds — the pair that made
    WORKEDHRS a python rule in the first place. Anything that is already a
    number is passed through as hours, so `HOURS(2)` is two hours.

    Malformed text is 0, not an error: the legacy code guarded both parses with
    `isdigit` and let a bad value contribute nothing while the rest of the day
    still counted. Changing that would change payslips.
    """
    if value is None or value == '':
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    parts = text.split(':')
    # `isdigit` on both halves, exactly as the legacy WORKEDHRS did, so this
    # helper and the guided lane's `hours:minutes` step agree on every value
    # including the malformed ones. A negative is NOT accepted here — the
    # legacy did not accept one either, and "worked minus two hours" is a
    # payload defect, not a number to carry into a payslip.
    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
        return int(parts[0].strip()) + int(parts[1].strip()) / 60.0
    number = coerce_number(text)
    return float(number) if number is not None else 0.0


def _minutes(value):
    """`MINUTES(90)` -> 1.5 hours."""
    number = coerce_number(value)
    return (number / 60.0) if number is not None else 0.0


def _seconds(value):
    """`SECONDS(37800)` -> 10.5 hours."""
    number = coerce_number(value)
    return (number / 3600.0) if number is not None else 0.0


def _number(value):
    """`NUMBER("1.234,50")` -> 1234.5, blank -> 0. `coerce_number`'s thousands
    and percent handling, exposed by name so a formula can say what it means."""
    number = coerce_number(value)
    return float(number) if number is not None else 0.0


def _f_sum(*args):
    return sum_list(list(args))


def _f_min(*args):
    return min_list(list(args))


def _f_max(*args):
    return max_list(list(args))


def _f_avg(*args):
    return avg_list(list(args))


def _f_count(*args):
    return counta_list(list(args))


def _f_and(*args):
    return all(bool(a) for a in args)


def _f_or(*args):
    return any(bool(a) for a in args)


def _f_int(value):
    number = coerce_number(value)
    return float(int(number)) if number is not None else 0.0


def _f_abs(value):
    number = coerce_number(value)
    return abs(number) if number is not None else 0.0


# name in a formula -> (python name in the eval namespace, one-line help).
# The help text is served to the composer's hint bar, so it is product voice
# and it never names the platform.
_TABLE = {
    'SUM':        ('_f_sum',        'SUM(a, b, …) — adds the values up'),
    'MIN':        ('_f_min',        'MIN(a, b, …) — the smallest value'),
    'MAX':        ('_f_max',        'MAX(a, b, …) — the largest value'),
    'AVERAGE':    ('_f_avg',        'AVERAGE(a, b, …) — the mean of the values'),
    'COUNT':      ('_f_count',      'COUNT(a, b, …) — how many are filled in'),
    'ROUND':      ('excel_round',   'ROUND(x, n) — to n decimals, half away from zero'),
    'ROUNDUP':    ('excel_roundup', 'ROUNDUP(x, n) — always away from zero'),
    'ROUNDDOWN':  ('excel_rounddown', 'ROUNDDOWN(x, n) — always toward zero'),
    'CEILING':    ('excel_ceiling', 'CEILING(x, step) — up to a multiple of step'),
    'FLOOR':      ('excel_floor',   'FLOOR(x, step) — down to a multiple of step'),
    'ABS':        ('_f_abs',        'ABS(x) — drops the minus sign'),
    'INT':        ('_f_int',        'INT(x) — the whole-number part'),
    'IF':         ('_lazy_if',      'IF(test, then, else) — pick one of two'),
    'IFERROR':    ('excel_iferror', 'IFERROR(x, fallback) — a value, or the fallback if it fails'),
    'NOT':        ('excel_not',     'NOT(test) — the opposite'),
    'AND':        ('_f_and',        'AND(a, b, …) — true only if all are true'),
    'OR':         ('_f_or',         'OR(a, b, …) — true if any is true'),
    'EXACT':      ('excel_streq',   'EXACT(a, b) — do these two read the same?'),
    'ISBLANK':    ('excel_isblank', 'ISBLANK(x) — is this empty?'),
    'HOURS':      ('_hours',        'HOURS("7:30") — hours-and-minutes text as hours'),
    'MINUTES':    ('_minutes',      'MINUTES(90) — a number of minutes as hours'),
    'SECONDS':    ('_seconds',      'SECONDS(37800) — a number of seconds as hours'),
    'NUMBER':     ('_number',       'NUMBER(text) — read text as a number, blank as 0'),
}

SUPPORTED_FUNCTIONS = tuple(sorted(_TABLE))
FUNCTION_HELP = [{'name': name, 'help': _TABLE[name][1]}
                 for name in SUPPORTED_FUNCTIONS]

# Lambdas may only be emitted BY the converter (IF / IFERROR branches), never
# written by a user — `lambda` in the source text is refused before conversion.
_EVAL_GLOBALS = {
    '__builtins__': {},
    '_f_sum': _f_sum, '_f_min': _f_min, '_f_max': _f_max, '_f_avg': _f_avg,
    '_f_count': _f_count, '_f_and': _f_and, '_f_or': _f_or,
    '_f_int': _f_int, '_f_abs': _f_abs,
    '_lazy_if': _lazy_if, '_hours': _hours, '_minutes': _minutes,
    '_seconds': _seconds, '_number': _number,
    'excel_round': excel_round, 'excel_roundup': excel_roundup,
    'excel_rounddown': excel_rounddown, 'excel_ceiling': excel_ceiling,
    'excel_floor': excel_floor, 'excel_iferror': excel_iferror,
    'excel_not': excel_not, 'excel_streq': excel_streq,
    'excel_isblank': excel_isblank,
}


# ---------------------------------------------------------------------------
# The converter
# ---------------------------------------------------------------------------

_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
_BRACKET_RE = re.compile(r'\[([^\[\]]*)\]')
_IDENT_CALL_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(')
_BARE_NAME_RE = re.compile(r'(?<![A-Za-z0-9_."\'])([A-Za-z_][A-Za-z0-9_]*)')
_MASK_RE = re.compile(r'\x00S(\d+)\x00')
_REF_RE = re.compile(r'\x00R(\d+)\x00')

# Anything here is refused before a single character is converted. The
# converted output is checked AGAIN by `assert_safe_expression` — this pass is
# about the SOURCE text, which is what the user actually typed and therefore
# what the refusal message has to be able to quote.
_SOURCE_FORBIDDEN = re.compile(
    r'__|\blambda\b|\bimport\b|\bexec\b|\beval\b|\bclass\b|\bdef\b|;|=>|\bfor\b|\bwhile\b')


def _split_args(text):
    """Top-level comma split, respecting parentheses. Strings are masked by the
    time this runs, so a comma inside quotes cannot reach it."""
    args, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            args.append(text[start:i])
            start = i + 1
    args.append(text[start:])
    return [a.strip() for a in args]


def _match_paren(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    raise RuleFormulaError("This formula has an unclosed bracket.")


def _convert_calls(text):
    """Rewrite every `NAME(...)` into its python helper, recursively.

    Left to right, innermost resolved by recursion on the argument text — so
    `ROUND(SUM([a],[b]), 2)` converts both levels and `IF` gets its branches
    wrapped in lambdas at whatever depth it appears.
    """
    out = []
    i = 0
    while i < len(text):
        match = _IDENT_CALL_RE.search(text, i)
        if not match:
            out.append(text[i:])
            break
        out.append(text[i:match.start()])
        name = match.group(1)
        open_index = match.end() - 1
        close_index = _match_paren(text, open_index)
        inner = text[open_index + 1:close_index]
        upper = name.upper()
        if upper not in _TABLE:
            raise RuleFormulaError(
                "%s is not a function this rule can use. The ones it "
                "understands are: %s." % (name, ', '.join(SUPPORTED_FUNCTIONS)))
        args = [_convert_calls(a) for a in _split_args(inner)] if inner.strip() else []
        if upper == 'IF':
            if not 2 <= len(args) <= 3:
                raise RuleFormulaError(
                    "IF needs a test and a value, and may take a second value: "
                    "IF(test, then, else).")
            branches = ['lambda: (%s)' % a for a in args[1:]]
            rendered = '_lazy_if(%s)' % ', '.join([args[0]] + branches)
        elif upper == 'IFERROR':
            if len(args) != 2:
                raise RuleFormulaError(
                    "IFERROR needs a value and a fallback: IFERROR(x, 0).")
            rendered = 'excel_iferror(lambda: (%s), %s)' % (args[0], args[1])
        else:
            rendered = '%s(%s)' % (_TABLE[upper][0], ', '.join(args))
        out.append(rendered)
        i = close_index + 1
    return ''.join(out)


def compile_rule_formula(text, known_paths=None):
    """`"[a]/3600 + HOURS([b])"` -> `(code_object, [refs])`.

    `known_paths` is the field catalogue. When it is given, every reference
    must resolve against it — that is the check `rule_save` runs so a formula
    naming a field the source does not have is refused at SAVE time rather than
    discovered as a zero three payslips later. Matching is by the same
    normalisation `resolve_ref` uses at run time, so the two can never disagree.

    Raises `RuleFormulaError` (a human sentence) or `UnsafeFormulaError`.
    """
    raw = (text or '').strip()
    if not raw:
        raise RuleFormulaError("This formula is empty.")
    if raw.startswith('='):
        raw = raw[1:].strip()
    if '&' in raw:
        raise RuleFormulaError(
            "Joining text with & is not supported here — this rule has to "
            "produce a number.")
    if _SOURCE_FORBIDDEN.search(raw):
        raise RuleFormulaError(
            "This formula uses something that is not allowed in a rule. Use "
            "the fields, the operators + - * / and the listed functions.")

    # 1. mask string literals so nothing below can see inside them
    literals = []

    def _mask(match):
        literals.append(match.group(0))
        return '\x00S%d\x00' % (len(literals) - 1)

    masked = _STRING_RE.sub(_mask, raw)

    # 2. bracket references -> their own masks, so an API field called
    #    `Sum of hours` cannot be mistaken for the SUM function
    refs = []

    def _mask_ref(match):
        name = match.group(1).strip()
        if not name:
            raise RuleFormulaError("There is an empty [ ] in this formula.")
        refs.append(name)
        return '\x00R%d\x00' % (len(refs) - 1)

    masked = _BRACKET_RE.sub(_mask_ref, masked)
    if '[' in masked or ']' in masked:
        raise RuleFormulaError(
            "A field reference has a bracket missing — write it as [Field name].")

    # 3. Excel-only operators. `=` is comparison here and there are no
    #    assignments in an expression, so a single `=` is always `==`.
    masked = masked.replace('<>', '!=')
    masked = masked.replace('^', '**')
    masked = re.sub(r'(?<![<>!=])=(?!=)', '==', masked)

    # 4. functions
    converted = _convert_calls(masked)

    # 5. anything still looking like a bare name is a typo — a user who meant a
    #    field wrote it without brackets, and that is worth saying plainly
    #    rather than letting `assert_safe_expression` answer with a token dump.
    for match in _BARE_NAME_RE.finditer(_REF_RE.sub('0', _MASK_RE.sub('0', converted))):
        word = match.group(1)
        if word in _EVAL_GLOBALS or word == 'lambda':
            continue
        raise RuleFormulaError(
            "%s is not a field or a function. A field is written in square "
            "brackets, like [%s]." % (word, word))

    # 6. unmask — refs become the run-time lookup, literals come back verbatim
    converted = _REF_RE.sub(lambda m: '_ref(%d)' % int(m.group(1)), converted)
    converted = _MASK_RE.sub(lambda m: literals[int(m.group(1))], converted)

    assert_safe_expression(converted)

    if known_paths is not None:
        catalog = {_norm(p) for p in known_paths}
        unknown = [r for r in refs if _norm(r) not in catalog]
        if unknown:
            raise RuleFormulaError(
                "This source does not have a field called %s."
                % ', '.join('[%s]' % u for u in sorted(set(unknown))))

    try:
        code = compile(converted, '<rule formula>', 'eval')
    except SyntaxError as error:
        raise RuleFormulaError(
            "This formula could not be read (%s). Check the brackets and the "
            "operators." % (error.msg or 'syntax error'))
    return code, refs


def eval_rule_formula(code, refs, row):
    """Evaluate a compiled rule formula against ONE record dict.

    A reference the row does not carry reads as blank (`''`), which
    `coerce_number` turns into nothing and the aggregates then skip — the same
    leniency the guided lane applies, so a payload that lost a field degrades
    identically down both lanes.
    """
    def _ref(index):
        value, _found = resolve_ref(row, refs[index])
        return Cell.of(value)

    namespace = dict(_EVAL_GLOBALS)
    namespace['_ref'] = _ref
    result = eval(code, namespace)  # noqa: S307 — hardened above, empty builtins
    # A transformation rule produces a NUMBER. `IF(...)` can hand back a raw
    # cell and `EXACT(...)` a boolean, so the last step is the same coercion
    # the guided lane applies to a step value — and `None` for something that
    # is not a number at all, which the aggregates then skip rather than
    # turning into a zero nobody asked for (W139's instinct, one layer down).
    if isinstance(result, bool):
        return 1.0 if result else 0.0
    number = coerce_number(str(result) if isinstance(result, Cell) else result)
    return float(number) if number is not None else None
