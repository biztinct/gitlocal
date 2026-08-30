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
KIND_DECIMAL = 'decimal'
KIND_INTEGER = 'integer'
KIND_QUANTITY = 'quantity'
KIND_RATE = 'rate'
KIND_IDENTIFIER = 'identifier'
KIND_TEXT = 'text'
KIND_DATE = 'date'
KIND_BOOLEAN = 'boolean'

KINDS = (KIND_MONEY, KIND_DECIMAL, KIND_INTEGER, KIND_QUANTITY, KIND_RATE,
         KIND_IDENTIFIER, KIND_TEXT, KIND_DATE, KIND_BOOLEAN)

#: Kinds the engine may do arithmetic on. THIS SET IS THE ONE DEFINITION of
#: "may meet float()" — the wire, the resolver, the payslip-line rail and the
#: migration's direction rule all key off it. Adding `text`, `identifier`,
#: `date` or `boolean` here restores the exact defect this module exists to
#: remove (C18.116/117).
NUMERIC_KINDS = frozenset((KIND_MONEY, KIND_DECIMAL, KIND_INTEGER,
                           KIND_QUANTITY, KIND_RATE))

#: Kinds that round to a whole number after coercion, so a field a person
#: declared to be a count never renders as `2.0000001`.
WHOLE_KINDS = frozenset((KIND_INTEGER,))

#: What net pay does with a component, when it does anything at all.
_PAY_ROLES = frozenset(('earning', 'deduction', 'net', 'employer_cost', 'mixed'))

#: The one role that measures nothing, and so may sit on any kind of value.
ROLE_INFO = 'info'

#: Kinds a MONEY role may be attached to.
#:
#: A component counted in hours, days or percent cannot be added to net pay or
#: taken off it. ABM proved the point: nine `quantity` components (Standard
#: Working Hour, Actual Working Hours, OT 1.5/2/3 Hours, Night shift hour…) and
#: one `text` component carried `net_role='earning'`, because the net-role
#: classifier walks the scheme's formula graph and found a path from each of
#: them to net pay. The path is real. The ARITHMETIC is not — hours reach net
#: pay as a multiplier and a divisor,
#:
#:     ACTUBASISALA = ROUND(BASESALARY / STANWORKHOUR * ACTUWORKHOUR, 0)
#:
#: not as an addend. They SCALE the money; they are not a share of it. Only the
#: Subtotal flag kept them out of the money measures, so those figures were
#: right by accident: untick one component and hours start being added to gross
#: pay. `pb_source_atlas._MONEY_ROLES` had already written this down for its own
#: totals; nothing else in the engine knew it.
#:
#: `decimal` and `integer` stay in deliberately. An unlabelled number carries no
#: claim about what it counts, and refusing it a money role would demote real
#: allowances that nobody has typed yet. The gate exists to stop what is KNOWN
#: not to be money, not to demand proof that something is.
#:
#: Same determinant as everything else in this module: what a value IS governs
#: what may be done with it (C18.129).
MONEY_ROLE_KINDS = frozenset((KIND_MONEY, KIND_DECIMAL, KIND_INTEGER))


def role_is_allowed(kind, role):
    """May a component of this value kind carry this pay role?

    Permissive at both ends on purpose. `info` and "no role decided yet" are
    always allowed, and a component with no declared kind is never pre-judged —
    a gate that fires on absence of evidence would fire on every fresh scheme.
    """
    if not role or role == ROLE_INFO or role not in _PAY_ROLES:
        return True
    if not kind:
        return True
    return kind in MONEY_ROLE_KINDS


def allowed_roles(kind, roles):
    """The subset of `roles` this value kind may carry, order preserved."""
    return [r for r in roles if role_is_allowed(kind, r)]


def gate_role(kind, role):
    """The role a component may actually carry, given its value kind.

    Returns `(role, demoted)`. `demoted` is True when a money role was asked
    for and refused, so the caller can say WHY rather than silently substitute.
    """
    if role_is_allowed(kind, role):
        return role, False
    return ROLE_INFO, True

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


# --------------------------------------------------------------------------
# Coercion
# --------------------------------------------------------------------------
def wants_number(kind):
    """Whether a value of this kind may be put through ``float()``.

    One function, so the wire, the resolver, the payslip-line rail and the
    migration cannot drift into four opinions about the same question.
    """
    return (kind or KIND_MONEY) in NUMERIC_KINDS


def apply_kind(kind, number):
    """Final shaping of an already-coerced number for its kind.

    Only `integer` does anything today: a field a person declared to be a whole
    number must not come back as `2.0000001` because a transform divided it.
    """
    if kind in WHOLE_KINDS:
        try:
            return float(round(float(number)))
        except (TypeError, ValueError):
            return number
    return number


# --------------------------------------------------------------------------
# Payroll signals — components the RUN has to act on
# --------------------------------------------------------------------------
#: Values that mean "this person has left". Accent-folded and upper-cased before
#: matching, so "Nghỉ việc" and "NGHI VIEC" are one entry.
LEFT_STATUS_WORDS = frozenset((
    'RESIGNED', 'TERMINATED', 'INACTIVE', 'LEFT', 'EXITED', 'SEPARATED',
    'RETIRED', 'DISMISSED', 'ENDED', 'CLOSED',
    # RD60 — a spreadsheet names the PERSON, not the event: the reference
    # tenant's own file says RESIGNEE. Left out, it read as unrecognised
    # wording, which this table (rightly) treats as "still employed" — so a
    # leaver came back into the run ticked by default.
    'RESIGNEE', 'RESIGNATION',
    'NGHI VIEC', 'DA NGHI', 'THOI VIEC',
))

#: Values that mean "still employed".
ACTIVE_STATUS_WORDS = frozenset((
    'ACTIVE', 'EMPLOYED', 'WORKING', 'CURRENT', 'PROBATION', 'ONBOARD',
    'DANG LAM VIEC', 'CHINH THUC', 'THU VIEC',
))

_STATUS_LABEL_RE = re.compile(r'\bSTATUS\b|\bSTATE\b')
#: A label alone is far too weak — "Residency Status", "Approval Status" and
#: "Marital Status" all match it, and picking one of those as the component that
#: decides who gets paid would be a serious wrong answer. Either the label says
#: EMPLOYMENT, or the values themselves are in the employment vocabulary.
_EMPLOYMENT_LABEL_RE = re.compile(r'\bEMPLOY\w*\b|\bEMP\b|\bSTAFF\b|\bWORKER\b')
_HOURS_LABEL_RE = re.compile(
    r'\b(?:ACTUAL|WORKED|ACTU)\w*\b[A-Z ]*\bHOUR')


def is_left_status(value):
    """True when this employment-status value means the person has left.

    Unknown wording is NOT "left". A person wrongly kept in a run is a payslip
    somebody deletes; a person wrongly dropped is somebody who does not get
    paid, and only one of those is recoverable.
    """
    if value is None or value is False:
        return False
    folded = normalize_header(str(value)).upper().strip()
    if not folded:
        return False
    if folded in ACTIVE_STATUS_WORDS:
        return False
    return folded in LEFT_STATUS_WORDS


def suggest_payroll_signal(code='', name='', sample_values=None, quantity=False):
    """``'employment_status'``, ``'worked_hours'`` or ``None`` — a SUGGESTION.

    Nothing acts on this without a person confirming it, because acting on it
    decides whether somebody is paid.
    """
    label = normalize_header('%s %s' % (name or '', code or '')).upper()
    values = [v for v in (sample_values or []) if not is_blank_sample(v)]

    if _STATUS_LABEL_RE.search(label):
        known = [v for v in values
                 if normalize_header(str(v)).upper().strip()
                 in (LEFT_STATUS_WORDS | ACTIVE_STATUS_WORDS)]
        # Values in the employment vocabulary settle it. Failing that, the label
        # has to say EMPLOYMENT — "Residency Status" and "Approval Status" say
        # nothing about whether somebody still works here.
        if known or (not values and _EMPLOYMENT_LABEL_RE.search(label)):
            return 'employment_status'

    if _HOURS_LABEL_RE.search(label) and (quantity or not values
                                          or all(_coerce_number(str(v)) is not None
                                                 for v in values)):
        return 'worked_hours'
    return None
