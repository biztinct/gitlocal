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

#: The codes a pay period can answer, and what each one means.
#:
#: Matched on the component's CODE, upper-cased and stripped, because that is
#: what the formulas reference — `IF(PAYMONTH=12,…)` names the code and nothing
#: else. A scheme that calls the component something else in its own language
#: still writes `PAYMONTH` in the formula, so the code is the only stable key.
PERIOD_CODES = ('PAYMONTH',)

#: The `via` these values are recorded under. `src` is 'period'.
PERIOD_VIA = 'pay_period'


def period_values(date_from=None, date_to=None):
    """``{code: value}`` the period answers, or ``{}`` when it cannot.

    THE MONTH IS THE MONTH THE PERIOD ENDS IN. An ordinary run from the 1st to
    the 31st of October ends in October and there is nothing to decide. A
    mid-cycle run from the 26th of September to the 25th of October is the
    October pay run — that is the month it is FOR, the month it is paid in and
    the month its filings belong to — so the end date is the one that answers.

    ``date_from`` is used only when there is no end date at all, which is a
    payslip somebody is still building rather than one being paid.
    """
    day = date_to or date_from
    month = getattr(day, 'month', None)
    if not month:
        return {}
    return {'PAYMONTH': float(month)}


def fill_period_inputs(values, unresolved, date_from=None, date_to=None):
    """Fill the period's codes into ``values``, and say which ones were filled.

    ``unresolved`` is the set of codes that reached the end of the walk with no
    source — the caller already knows them, and passing them in is what keeps
    this from having to re-decide anything. Returns the codes it actually
    filled, so the caller can write their provenance without guessing.

    A code the scheme does not have is not invented: only keys already present
    in ``values`` are written, so this can never add a component to a run.
    """
    filled = []
    try:
        answers = period_values(date_from, date_to)
    except Exception:                               # noqa: BLE001
        return filled
    for code, value in answers.items():
        if code in values and code in unresolved:
            values[code] = value
            filled.append(code)
    return filled
