# -*- coding: utf-8 -*-
"""What the pay period itself answers, without anybody typing it.

THE BUG THIS EXISTS TO CLOSE. A yearly payment is written as "if the month
being paid is 12, pay it, otherwise nothing" — a thirteenth-month bonus, a
service award, an annual allowance. The month it compares against is an INPUT
component, `PAYMONTH`, and until now nothing filled it in. It was not read off
the payslip, no transformation could produce it (they do arithmetic on numbers,
not dates), and unless somebody remembered to put a column called "month" in
every pay-data file it fell to its default of 1.

So every one of those payments compared 1 against 12, took the zero leg, and
paid nothing — silently, correctly according to the formula, and wrongly
according to the person who wrote it. Nothing on any screen could show it,
because the component HAD a value and the formula DID run.

THE PERIOD IS A FACT, NOT A PREFERENCE. A pay run for October is a pay run for
October; no source of truth outside the run has a better answer than the run's
own dates. That is why this is a source of its own rather than a default: a
default is what you fall back to when nobody said, and here the run has said.

IT ONLY EVER FILLS WHAT NOTHING ELSE FILLED. It is the last rung, below every
declared source, so a scheme that maps `PAYMONTH` to a spreadsheet column or a
feed keeps doing exactly that — including when somebody deliberately pays a
December bonus in a January run and says so in the file. This can therefore
only ever replace the hard-coded default, which is the value that was wrong.

DELIBERATELY PLAIN PYTHON — no ``odoo`` import, stdlib only, exactly like
``input_provenance`` and ``component_code`` — so the bare-``python3`` regression
battery can exercise it without a database.

Nothing here raises. It runs inside a payroll computation; a period it cannot
read must leave the component exactly as it found it and let the run finish.
"""

import datetime

#: The codes a pay period can answer, and what each one means.
#:
#: Matched on the component's CODE, upper-cased and stripped, because that is
#: what the formulas reference — `IF(PAYMONTH=12,…)` names the code and nothing
#: else. A scheme that calls the component something else in its own language
#: still writes `PAYMONTH` in the formula, so the code is the only stable key.
#:
#:   PAYMONTH  month the period ENDS in, 1-12
#:   PAYYEAR   year the period ENDS in, e.g. 2026
#:   PAYDAYS   calendar days in the period, both ends INCLUSIVE
#:   STDDAYS   standard working days this run is paid against (see below)
#:   STARTDAY  day of month the period starts on, 1-31
#:   ENDDAY    day of month the period ends on, 1-31
#:
#: Every code is underscore-free, six to twelve characters, and can never equal
#: a column letter — the settled converter floors (RUNSRC ledger §1.3).
#:
#: NO DATE IS EVER EXPOSED AS AN EXCEL SERIAL. `YEAR`/`MONTH`/`DAY`/`DATE` are
#: in the parser's and validator's allowed-name lists but are NOT implemented in
#: the evaluator or in `excel_semantics`, so a serial would be a number no
#: formula in this product could take apart. The period therefore answers
#: pre-decomposed numbers and nothing else.
PERIOD_CODES = ('PAYMONTH', 'PAYYEAR', 'PAYDAYS', 'STDDAYS',
                'STARTDAY', 'ENDDAY')

#: The `via` these values are recorded under. `src` is 'period'.
PERIOD_VIA = 'pay_period'


def _as_date(value):
    """A ``date`` from whatever the caller had, or ``None``. Never raises.

    The ORM hands us `datetime.date`; a wizard or a JSON round trip hands us an
    ISO string; a blank field hands us ``False``. All three reach here.
    """
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.date.fromisoformat(value.strip()[:10])
        except Exception:                           # noqa: BLE001
            return None
    return None


def default_standard_work_days(date_from, date_to):
    """Mon-Fri days between the two dates, both ends inclusive. ``None`` when
    either date is missing or the period runs backwards.

    THE ONE DEFINITION. The owner ruled on this before any code was written:
    the default standard working days of a run is the plain Monday-to-Friday
    count of its own period. Not a holiday-calendar subtraction — that is only
    ever as good as a list nobody maintains — and not a per-scheme constant.
    A month with public holidays is adjusted BY HAND on the run, which is the
    whole point of storing the number instead of computing it.

    Nothing else in this codebase may count working days; everything that needs
    the default calls this.
    """
    start = _as_date(date_from)
    end = _as_date(date_to)
    if not start or not end or end < start:
        return None
    total = (end - start).days + 1
    whole_weeks, remainder = divmod(total, 7)
    days = whole_weeks * 5
    first_weekday = start.weekday()                 # Monday is 0
    for offset in range(remainder):
        if (first_weekday + offset) % 7 < 5:
            days += 1
    return float(days)


def period_values(date_from=None, date_to=None, std_days=None):
    """``{code: value}`` the period answers, or ``{}`` when it cannot.

    THE MONTH IS THE MONTH THE PERIOD ENDS IN. An ordinary run from the 1st to
    the 31st of October ends in October and there is nothing to decide. A
    mid-cycle run from the 26th of September to the 25th of October is the
    October pay run — that is the month it is FOR, the month it is paid in and
    the month its filings belong to — so the end date is the one that answers
    `PAYMONTH`, `PAYYEAR` and `ENDDAY`. `date_from` answers `STARTDAY`, and the
    two together answer `PAYDAYS` and `STDDAYS`.

    ``date_from`` alone is used only when there is no end date at all, which is
    a payslip somebody is still building rather than one being paid; the codes
    that need both dates simply go unanswered.

    ``std_days`` is what somebody SAID the standard working days are — the
    number typed on the run or on the pay-data load. Anything missing, zero or
    negative means nobody said, and the Mon-Fri default answers instead. Zero
    is never taken at face value: a run paid against zero standard days divides
    by zero in every daily-rate formula in the product.
    """
    start = _as_date(date_from)
    end = _as_date(date_to)
    anchor = end or start
    if not anchor:
        return {}

    answers = {
        'PAYMONTH': float(anchor.month),
        'PAYYEAR': float(anchor.year),
    }
    if start:
        answers['STARTDAY'] = float(start.day)
    if end:
        answers['ENDDAY'] = float(end.day)
    if start and end and end >= start:
        answers['PAYDAYS'] = float((end - start).days + 1)

    said = None
    try:
        said = float(std_days) if std_days is not None else None
    except Exception:                               # noqa: BLE001
        said = None
    if said is not None and said > 0:
        answers['STDDAYS'] = said
    else:
        fallback = default_standard_work_days(start, end)
        if fallback is not None:
            answers['STDDAYS'] = fallback
    return answers


def fill_period_inputs(values, unresolved, date_from=None, date_to=None,
                       std_days=None):
    """Fill the period's codes into ``values``, and say which ones were filled.

    ``unresolved`` is the set of codes that reached the end of the walk with no
    source — the caller already knows them, and passing them in is what keeps
    this from having to re-decide anything. Returns the codes it actually
    filled, so the caller can write their provenance without guessing.

    A code the scheme does not have is not invented: only keys already present
    in ``values`` are written, so this can never add a component to a run. And
    only codes in ``unresolved`` are written, so this can never beat a
    spreadsheet column, a feed, a record, a rule output or a contract
    component. It is the last rung and it stays the last rung.
    """
    filled = []
    try:
        answers = period_values(date_from, date_to, std_days)
    except Exception:                               # noqa: BLE001
        return filled
    for code, value in answers.items():
        if code in values and code in unresolved:
            values[code] = value
            filled.append(code)
    return filled


#: The same six answers, spelled the way a TRANSFORMATION RULE names things.
#:
#: RUNSRC D1. A pay component is addressed by its CODE, which is upper case
#: because that is what an Excel formula writes. A transformation rule is a
#: different namespace with a different convention: its python lane already
#: carries `period_start` and `period_end` in lower snake_case, and a rule that
#: had to write `PAYMONTH` beside `period_end` would be advertising an
#: implementation detail — two casings for one idea, in one dict, is how a
#: person learns to distrust both.
#:
#: Derived from `PERIOD_CODES`, never retyped, so a seventh code can only ever
#: exist in both places or in neither.
NAMESPACE_NAMES = tuple(code.lower() for code in PERIOD_CODES)


def namespace_values(date_from=None, date_to=None, std_days=None):
    """``{lower_case_name: value}`` for a transformation rule's namespace.

    Exactly `period_values`, re-keyed. A code the period cannot answer is
    ABSENT rather than zero, for the reason `period_values` states: a run paid
    against zero standard days divides by zero in every daily-rate formula in
    the product, and a rule that reads a missing name gets blank — which the
    aggregates already skip — instead of a number nobody said.
    """
    try:
        answers = period_values(date_from, date_to, std_days)
    except Exception:                               # noqa: BLE001
        return {}
    return {code.lower(): value for code, value in answers.items()}


def fill_wired_inputs(values, unresolved, wires, date_from=None, date_to=None,
                      std_days=None):
    """Fill the components somebody WIRED to the pay run. Returns the pairs.

    RUNSRC C1, and the reason it exists: `fill_period_inputs` above matches on
    the component's CODE, which reaches a component coded `PAYMONTH` and
    nothing else. The standard-working-days component on a real Vietnamese
    scheme is coded in Vietnamese, and renaming a live component's code
    rewrites every formula that references it — so the run's numbers were
    unreachable to exactly the schemes that needed them. A person draws a wire
    instead, and this is the rung that honours it.

    ``wires`` is ``[(component_code, period_key)]`` — what
    `hr.formula.rule.pay_run_wires()` returns. Everything that made
    `fill_period_inputs` safe is preserved here, deliberately and for the same
    reasons:

      * only a code ALREADY IN ``values`` is written, so a wire can never add a
        component to a run;
      * only a code in ``unresolved`` is written, so a wire can never beat a
        spreadsheet column, a feed, a record or a contract line — the run is
        the last rung and stays the last rung;
      * nothing raises.

    A code this fills is REMOVED from ``unresolved`` before it is returned, so
    that a component coded (say) `STDDAYS` but wired to `PAYMONTH` keeps the
    month it was wired to: what a person stated beats what a code happens to
    spell. That is the only ordering question the two rungs can disagree on.

    Returns ``[(code, period_key)]`` rather than just the codes, because the
    caller writes the provenance key from the period key and should not have to
    look it up again.
    """
    filled = []
    try:
        answers = period_values(date_from, date_to, std_days)
    except Exception:                               # noqa: BLE001
        return filled
    if not answers:
        return filled
    for pair in (wires or ()):
        try:
            code, period_key = pair
        except Exception:                           # noqa: BLE001
            continue
        if not code or not period_key:
            continue
        if code not in values or code not in unresolved:
            continue
        if period_key not in answers:
            continue
        values[code] = answers[period_key]
        try:
            unresolved.discard(code)
        except Exception:                           # noqa: BLE001
            pass
        filled.append((code, period_key))
    return filled
