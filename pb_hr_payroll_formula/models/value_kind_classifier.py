# -*- coding: utf-8 -*-
"""Value-kind classification — "what IS this value?", as distinct from "what is
this column FOR?" (`column_role_classifier`) and "what does net pay do with it?"
(`formula_net_role`).

Three questions, three classifiers, one field each. They read one another's
answers; none of them writes another's field.

Why this one exists
-------------------
A payroll column arriving from a connected system passed through two layers that
each guessed whether it was a number, and both failed toward ``float()``. On
ABM's live June 2026 run that turned ``"Ho Chi Minh Branch"`` into ``0.0`` — and
that column is read by the scheme's own ``IF(F5="La Nga", …)``, so the comparison
was false for every employee, silently, on every run.

The determinant is NOT "is it used in a formula": ``F5="La Nga"`` and
``X5/AB5`` are both usage. It is which OPERATOR is applied, which
`formula_operand_context` answers, plus the shape of the values themselves.

DELIBERATELY plain Python — no `odoo` import, stdlib only (C12), so the batch,
the migration, the studio RPC and a bare `python3` test table share one answer.
Everything the ladder needs is passed IN; nothing is looked up.

Bias
----
The default is ``money``, which is what a payroll column already behaves as, so a
scheme that never runs this classifier is byte-identical. But where the ladder
must guess between "number" and "text" for a NON-payroll column, it picks text:
the old default's failure mode was destroying the value, and text's failure mode
is a value that looks slightly wrong and can be corrected. Always fail toward
keeping the data.
"""

import datetime
import re

from .column_role_classifier import (
    _LEADING_ZERO_INT_RE,
    _coerce_number,
    is_blank_sample,
    is_texty_sample,
    normalize_header,
)
from .formula_operand_context import (
    CTX_ARITH,
    CTX_NUMCMP,
    CTX_STRCMP,
    CTX_TEXTFN,
)

# --------------------------------------------------------------------------
# Kinds
# --------------------------------------------------------------------------
KIND_MONEY = 'money'
KIND_QUANTITY = 'quantity'
KIND_RATE = 'rate'
KIND_IDENTIFIER = 'identifier'
KIND_TEXT = 'text'
KIND_DATE = 'date'
KIND_BOOLEAN = 'boolean'

KINDS = (KIND_MONEY, KIND_QUANTITY, KIND_RATE, KIND_IDENTIFIER,
         KIND_TEXT, KIND_DATE, KIND_BOOLEAN)

#: Kinds the engine may do arithmetic on. Everything else passes through the
#: wire and the resolver untouched.
NUMERIC_KINDS = frozenset((KIND_MONEY, KIND_QUANTITY, KIND_RATE))

#: What net pay does with a component, when it does anything at all.
_PAY_ROLES = frozenset(('earning', 'deduction', 'net', 'employer_cost', 'mixed'))

#: Roles whose values name something rather than measure it.
_NAMING_ROLES = frozenset(('identity', 'bank'))

_YES_NO = frozenset((
    'YES', 'NO', 'Y', 'N', 'TRUE', 'FALSE', '1', '0',
    'CO', 'KHONG',          # Vietnamese "có" / "không", accent-folded
))

_DATE_PATTERNS = (
    '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d',
    '%d.%m.%Y', '%d %b %Y', '%d %B %Y',
)

# Label words that say "this number is a name". Conservative on purpose: an
# insurance book number and a tax code are digits nobody should ever sum, but
# "Number of Dependants" is a count, so NUMBER alone must not be enough.
_IDENTIFIER_LABEL_RE = re.compile(
    r'\b(?:CODE|ID|IDENT\w*|REFERENCE|REF|ACCOUNT|ACCT|IBAN|BIC|SWIFT|'
    r'PASSPORT|LICEN[CS]E|REGISTRATION|SERIAL|BARCODE|MSNV)\b'
)
_IDENTIFIER_PHRASE_RE = re.compile(
    r'\b(?:BOOK|CARD|TAX|PIT|SOCIAL|INSURANCE|POLICY|CONTRACT|INVOICE|BANK)\b'
    r'[A-Z ]*\bN(?:O|UMBER|BR)\b'
)
_COUNT_LABEL_RE = re.compile(r'\bNUMBER OF\b|\bNO\. OF\b|\bCOUNT\b|\bQTY\b')

_RATE_LABEL_RE = re.compile(r'\b(?:RATE|PERCENT\w*|PCT|RATIO|FACTOR|COEFFICIENT)\b')


# --------------------------------------------------------------------------
# Value shape
# --------------------------------------------------------------------------
def looks_like_a_date(value):
    """True when this value is a date, or a string spelling one.

    Not `dateutil`: a permissive parser reads "11450" as a year and an employee
    code becomes a date. Only the explicit patterns above count.
    """
    if isinstance(value, (datetime.datetime, datetime.date)):
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) < 6:
        return False
    for pattern in _DATE_PATTERNS:
        try:
            datetime.datetime.strptime(text, pattern)
            return True
        except ValueError:
            continue
    return False


def _is_yes_no(value):
    if value is None or isinstance(value, bool):
        return isinstance(value, bool)
    folded = normalize_header(str(value)).upper().replace(' ', '')
    return folded in _YES_NO


def _is_pure_digits(value):
    return bool(re.fullmatch(r'[0-9]{4,}', str(value).strip()))


def sample_shape(values):
    """What a column's OBSERVED values look like, as counts.

    Callers pass raw source material — `hr_payroll_import_line.raw_data_json` —
    NEVER `formula_input_values`, which is downstream of the coercion this whole
    module exists to undo and would only confirm its own damage (C18.118).
    """
    kept = [v for v in (values or []) if not is_blank_sample(v)]
    shape = {
        'n': len(kept), 'texty': 0, 'dates': 0, 'leading_zero': 0,
        'pure_digits': 0, 'numeric': 0, 'yes_no': 0,
    }
    for value in kept:
        if looks_like_a_date(value):
            shape['dates'] += 1
        if _is_yes_no(value):
            shape['yes_no'] += 1
        if is_texty_sample(value):
            shape['texty'] += 1
        text = str(value).strip()
        if _LEADING_ZERO_INT_RE.match(text.replace(' ', '')):
            shape['leading_zero'] += 1
        if _is_pure_digits(text):
            shape['pure_digits'] += 1
        if _coerce_number(text) is not None:
            shape['numeric'] += 1
    return shape


def _all(shape, key):
    return bool(shape['n']) and shape[key] == shape['n']


# --------------------------------------------------------------------------
# The ladder
# --------------------------------------------------------------------------
def classify_value_kind(code='', name='', column_role='payroll', net_role='',
                        column_type='input', contexts=(), quantity=False,
                        vendor_type='', sample_values=None,
                        appears_on_payslip=False):
    """Return ``(kind, reason)`` for one component. First hit wins.

    `contexts` is the union, over EVERY formula in the scheme, of the operator
    contexts applied to this component's code or column letter — see
    :func:`formula_operand_context.operand_contexts`.

    The caller supplies `quantity` (from `formula_net_role.looks_like_a_quantity`)
    rather than this module importing it, because that module is a model file and
    this one must stay `odoo`-free.
    """
    contexts = set(contexts or ())
    shape = sample_shape(sample_values)
    label = normalize_header('%s %s' % (name or '', code or '')).upper()

    # --- 2. DIRECT evidence of arithmetic ----------------------------------
    # A computed or constant column is arithmetic by construction; so is
    # anything an operator adds, multiplies or divides. These two are the only
    # signals strong enough to outrank the values themselves.
    #
    # This rung outranks the text rung ONLY on `arith`. A bare reference with no
    # operator context is noise — `formula_dependencies` holds column LETTERS,
    # so a coincidental single-letter match is common — and letting noise reach
    # here is exactly how LOCATION would classify as money again.
    if column_type in ('formula', 'constant'):
        return _numeric_kind(quantity, label, 'a computed column is arithmetic')
    if CTX_ARITH in contexts:
        return _numeric_kind(
            quantity, label,
            'a formula does arithmetic on it'
            + (' (it is also compared as text somewhere — arithmetic wins)'
               if CTX_STRCMP in contexts else ''))

    # --- 3. compared as text, never counted --------------------------------
    if contexts and not contexts - {CTX_STRCMP, CTX_TEXTFN}:
        if _all(shape, 'yes_no'):
            return KIND_BOOLEAN, 'a formula compares it against a yes/no value'
        if _all(shape, 'dates'):
            return KIND_DATE, 'a formula compares it, and every value is a date'
        return KIND_TEXT, 'a formula compares it against text, never counts it'

    # --- 3b. unanimous values outrank a DERIVED role -----------------------
    # `net_role` is itself a classification, read off the net-pay formula graph;
    # the values are the thing itself. ABM's SHUIPARTICIP carries net_role
    # 'earning' and 152 values reading "YES" — letting the derived signal win
    # would turn the one text component that works today back into 0.0.
    if _all(shape, 'yes_no'):
        return KIND_BOOLEAN, 'every value seen is yes or no'
    if _all(shape, 'dates'):
        return KIND_DATE, 'every value seen is a date'
    if _all(shape, 'texty') and not shape['leading_zero']:
        return KIND_TEXT, 'every value seen is text'

    # --- 4. a declared role in net pay -------------------------------------
    if net_role in _PAY_ROLES:
        return _numeric_kind(quantity, label,
                             'net pay treats it as %s' % net_role)

    # --- 5. it names something ---------------------------------------------
    if column_role in _NAMING_ROLES:
        if shape['n'] and shape['texty'] and not shape['leading_zero'] \
                and not shape['pure_digits']:
            return KIND_TEXT, '%s column whose values are words' % column_role
        return KIND_IDENTIFIER, '%s column — it names, it never counts' % column_role

    # --- 6. the connected system says so -----------------------------------
    if vendor_type in ('date', 'datetime'):
        return KIND_DATE, 'the connected system declares it a date'
    if vendor_type == 'boolean':
        return KIND_BOOLEAN, 'the connected system declares it a yes/no'

    # --- 6a. leading zeros ---------------------------------------------------
    if shape['leading_zero']:
        return KIND_IDENTIFIER, 'values carry leading zeros, which only a name does'
    if _all(shape, 'texty'):
        return KIND_TEXT, 'every value seen is text'

    # --- 6b. the label says the digits are a name --------------------------
    # An insurance book number and a tax code are digits nobody should sum, and
    # nothing in their VALUES says so. A person can override; the audit lists it.
    if _all(shape, 'pure_digits') and CTX_ARITH not in contexts \
            and not appears_on_payslip and not _COUNT_LABEL_RE.search(label) \
            and (_IDENTIFIER_LABEL_RE.search(label)
                 or _IDENTIFIER_PHRASE_RE.search(label)):
        return KIND_IDENTIFIER, 'its name says the digits are a reference, not an amount'

    # --- 7/8. defaults ------------------------------------------------------
    if column_role and column_role != 'payroll':
        return KIND_TEXT, '%s column with no arithmetic behind it' % column_role
    return KIND_MONEY, 'no signal — money by policy'


def _numeric_kind(quantity, label, reason):
    if _RATE_LABEL_RE.search(label or ''):
        return KIND_RATE, reason
    if quantity:
        return KIND_QUANTITY, reason
    return KIND_MONEY, reason


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------
def contradictions(kind, values):
    """Values that the declared `kind` cannot be true of.

    Used by the read-only audit, so it is deliberately narrow: it reports only
    what is certainly wrong, never what merely looks unusual.
    """
    bad = []
    for value in (values or []):
        if is_blank_sample(value):
            continue
        text = str(value).strip()
        if kind in NUMERIC_KINDS:
            if _coerce_number(text) is None:
                bad.append(value)
        elif kind == KIND_DATE:
            if not looks_like_a_date(value):
                bad.append(value)
        elif kind == KIND_BOOLEAN:
            if not _is_yes_no(value):
                bad.append(value)
    return bad
