# -*- coding: utf-8 -*-
"""Operand context — *how* a formula uses a reference, not merely *whether* it does.

`hr.formula.rule.formula_dependencies` answers "which columns does this formula
name?". That is the question the engine's topological order needs, and it is the
wrong question for "is this column a number?", because both halves of

    =IF(F5="La Nga", 0, (X5/AB5*AD5))

are usage. `F5` is compared against a string literal; `X5` is divided. A payroll
column that is only ever compared to text IS text — ABM's `LOCATION` is read
exactly this way, and storing it as a float made `IF(F5="La Nga", …)` false for
every employee on every run, in silence.

So this module answers the finer question: for each reference in one Excel
formula, which KINDS of operator are applied to it.

    arith   — an arithmetic operator or a numeric aggregate consumes it
    strcmp  — it is compared for (in)equality against a string literal
    numcmp  — it is compared against a number, or ordered (< <= > >=)
    textfn  — a text function consumes it

Only `arith` is evidence of a number. `numcmp` is deliberately weaker: `BS5>0`
tells you the author expected an orderable value, which a date also is.

DELIBERATELY plain Python — no `odoo` import, stdlib only — for the same reason
`column_role_classifier` is: the migration, the batch, the studio RPC and a bare
`python3` test table all share one answer. See C12 in the conventions ledger.

Bias: when a reference carries BOTH `arith` and `strcmp`, the caller resolves it
as numeric. A column wrongly kept numeric is the behaviour that already ships; a
pay component wrongly turned into text would stop arithmetic that works today.
"""

import re

# --------------------------------------------------------------------------
# Contexts
# --------------------------------------------------------------------------
CTX_ARITH = 'arith'
CTX_STRCMP = 'strcmp'
CTX_NUMCMP = 'numcmp'
CTX_TEXTFN = 'textfn'

CONTEXTS = (CTX_ARITH, CTX_STRCMP, CTX_NUMCMP, CTX_TEXTFN)

# Functions whose every argument is consumed as a number. IF/IFERROR/AND/OR are
# NOT here on purpose: `IF(F5="La Nga", 0, X5/AB5)` consumes F5 as text and X5 as
# a number, so the branch — not the function — decides.
_NUMERIC_FUNCTIONS = (
    'SUM', 'SUMIF', 'SUMIFS', 'AVERAGE', 'AVERAGEIF', 'MIN', 'MAX', 'ROUND',
    'ROUNDUP', 'ROUNDDOWN', 'ABS', 'CEILING', 'FLOOR', 'INT', 'TRUNC', 'POWER',
    'SQRT', 'PRODUCT', 'MOD', 'SUMPRODUCT',
)

# Functions that consume their argument as text.
_TEXT_FUNCTIONS = (
    'LEFT', 'RIGHT', 'MID', 'LEN', 'TRIM', 'UPPER', 'LOWER', 'PROPER',
    'CONCATENATE', 'CONCAT', 'TEXT', 'SUBSTITUTE', 'EXACT', 'FIND', 'SEARCH',
)

# A reference: a column letter run, optionally $-anchored and row-suffixed
# (`F5`, `$BS5`, `AB`), or a component CODE (`BASESALARY`). Both spellings occur
# in the wild — an imported scheme says `=C3`, a hand-written one says `=DOJ` —
# and `formula_dependencies` already keeps both, so this does too.
#
# The letter run must be MAXIMAL. An earlier draft capped it at three (the
# column-letter width) and read `BASESALARY` as `BAS` + `ESA` + `LAR` + `Y`,
# four references none of which exists. The guards on both sides are what make
# it maximal; `normalize_ref` is what strips the row suffix afterwards.
_REF = r'(?<![A-Z0-9$])\$?[A-Z]+\$?\d*(?![A-Z0-9])'
_REF_RE = re.compile(_REF)

_STRING_LITERAL_RE = re.compile(r'"([^"]|"")*"')
_FUNC_CALL_RE = re.compile(r'\b([A-Z][A-Z0-9.]*)\s*\(')

# Operators, LONGEST FIRST so `<=` is never read as `<` followed by `=`.
_OPERATORS = ('<=', '>=', '<>', '<', '>', '=', '+', '-', '*', '/', '^', '&')
_ARITH_OPS = frozenset(('+', '-', '*', '/', '^'))
_EQ_OPS = frozenset(('=', '<>'))
_ORDER_OPS = frozenset(('<', '<=', '>', '>='))


def normalize_ref(ref):
    """`$BS5` -> `BS`, `AB5` -> `AB`, `BASESALARY` -> `BASESALARY`.

    The row suffix is noise: `formula_dependencies` keeps both `BP` and `BP5`
    for the same column, and a caller matching against `column_letter` wants the
    letters alone. A CODE (three or more characters, and not a pure letter run
    with a trailing row number) is returned as it stands.
    """
    if not ref:
        return ''
    token = str(ref).replace('$', '').strip().upper()
    if not token:
        return ''
    match = re.fullmatch(r'([A-Z]{1,3})(\d+)?', token)
    if match:
        return match.group(1)
    return token


def _blank_out(text, spans):
    """Replace each (start, end) span with spaces, preserving every offset."""
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for i in range(start, min(end, len(chars))):
            chars[i] = ' '
    return ''.join(chars)


def _mask_function_names(text):
    """Blank out function NAMES so `SUM(` cannot be read as a reference.

    Only the name is blanked; the parenthesis and the arguments stay exactly
    where they were, because `_argument_spans` walks this same string by offset.
    """
    spans = [(m.start(1), m.end(1)) for m in _FUNC_CALL_RE.finditer(text)]
    return _blank_out(text, spans)


def _argument_spans(text, function_names):
    """Character spans covered by the arguments of the named functions.

    Nested calls are included in the enclosing span, which is what we want:
    `SUM(A1, ROUND(B1))` consumes B1 as a number just as much as A1.
    """
    spans = []
    for match in _FUNC_CALL_RE.finditer(text):
        if match.group(1) not in function_names:
            continue
        depth = 0
        start = match.end()          # first char after '('
        for i in range(match.end() - 1, len(text)):
            char = text[i]
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    spans.append((start, i))
                    break
        else:
            spans.append((start, len(text)))
    return spans


def _op_before(text, index):
    """``(operator, start)`` immediately left of ``index``, skipping spaces."""
    i = index - 1
    while i >= 0 and text[i] == ' ':
        i -= 1
    if i < 0:
        return None, -1
    for op in _OPERATORS:
        start = i - len(op) + 1
        if start >= 0 and text[start:i + 1] == op:
            return op, start
    return None, -1


def _op_after(text, index):
    """``(operator, end)`` immediately right of ``index``, skipping spaces."""
    i = index
    while i < len(text) and text[i] == ' ':
        i += 1
    if i >= len(text):
        return None, -1
    for op in _OPERATORS:
        if text.startswith(op, i):
            return op, i + len(op)
    return None, -1


def _operand_is_literal(original, masked, index, forward):
    """Was the operand on the far side of an operator a STRING literal?

    Literals are blanked to spaces in ``masked`` but still present in
    ``original`` at the same offsets, so a run of spaces in the masked text
    whose original text starts with a quote is exactly a string literal. This is
    what tells `F5="La Nga"` (text) from `BS5>0` (a number).
    """
    step = 1 if forward else -1
    i = index
    while 0 <= i < len(masked) and masked[i] == ' ':
        if original[i] == '"':
            return True
        i += step
    return False


def operand_contexts(excel_formula):
    """``{REF: set(contexts)}`` for one Excel formula.

    Keys are normalised by :func:`normalize_ref`, so `F5`, `$F5` and `F` all
    land on `F`. An empty or unparseable formula yields ``{}`` — never an
    exception, because this runs inside a stored compute over every rule in
    every scheme.
    """
    out = {}
    if not excel_formula:
        return out
    try:
        source = str(excel_formula).upper()

        # Blank the literals IN PLACE — same length, same offsets — so a literal
        # like "A+B" cannot manufacture a phantom reference or a phantom
        # arithmetic hit, while `_operand_is_literal` can still see that a
        # literal is what stood there.
        masked = _blank_out(
            source,
            [(m.start(), m.end()) for m in _STRING_LITERAL_RE.finditer(source)])

        # Argument spans are read BEFORE the function names are masked (masking
        # first is what made `SUM(AE5:AX5)` invisible in the first draft), and
        # the ref scan is read AFTER, so `SUM(` is never itself a reference.
        numeric_spans = _argument_spans(masked, _NUMERIC_FUNCTIONS)
        text_spans = _argument_spans(masked, _TEXT_FUNCTIONS)
        scan = _mask_function_names(masked)

        def add(key, ctx):
            if key:
                out.setdefault(key, set()).add(ctx)

        for match in _REF_RE.finditer(scan):
            start, end = match.start(), match.end()
            key = normalize_ref(match.group(0))
            if not key:
                continue

            # ---- operator adjacency, both sides -------------------------
            # Adjacency rather than one regex over the pair, because a regex
            # consumes the operator it matches: in `X5/AB5*AD5` the `X5/` match
            # eats the `/`, the `AB5*` match eats the `*`, and AD5 — the whole
            # reason this function exists — falls out of the scan entirely.
            for op, pos, forward in ((_op_before(scan, start)[0],
                                      _op_before(scan, start)[1], False),
                                     (_op_after(scan, end)[0],
                                      _op_after(scan, end)[1], True)):
                if op is None:
                    continue
                if op in _ARITH_OPS:
                    add(key, CTX_ARITH)
                elif op in _ORDER_OPS:
                    add(key, CTX_NUMCMP)
                elif op in _EQ_OPS:
                    far = pos + len(op) if not forward else pos
                    if _operand_is_literal(source, scan, far if forward else pos - 1,
                                           forward):
                        add(key, CTX_STRCMP)
                    else:
                        add(key, CTX_NUMCMP)

            # ---- consumed by a typed function ---------------------------
            if any(s <= start and end <= e for s, e in numeric_spans):
                add(key, CTX_ARITH)
            if any(s <= start and end <= e for s, e in text_spans):
                add(key, CTX_TEXTFN)
    except Exception:       # noqa: BLE001 — a stored compute must never raise
        return out
    return out


def merge_contexts(target, addition):
    """Fold one formula's contexts into a scheme-wide accumulator, in place."""
    for ref, contexts in (addition or {}).items():
        target.setdefault(ref, set()).update(contexts)
    return target


def serialize(contexts):
    """``{'F': {'strcmp'}}`` -> ``'F:strcmp'``, stable and diffable.

    Stored on the rule as a plain Char so a migration, a test and a person
    reading the database all see the same thing without a JSON parse.
    """
    parts = []
    for ref in sorted(contexts or {}):
        for ctx in sorted(contexts[ref]):
            parts.append('%s:%s' % (ref, ctx))
    return ','.join(parts)


def deserialize(text):
    """Inverse of :func:`serialize`. A malformed entry is skipped, not fatal."""
    out = {}
    for chunk in (text or '').split(','):
        chunk = chunk.strip()
        if not chunk or ':' not in chunk:
            continue
        ref, _, ctx = chunk.partition(':')
        ref, ctx = ref.strip(), ctx.strip()
        if ref and ctx in CONTEXTS:
            out.setdefault(ref, set()).add(ctx)
    return out
