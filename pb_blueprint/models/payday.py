# -*- coding: utf-8 -*-
"""When people actually get paid — the arithmetic, with nothing else in it.

"The last working day of the month" is a promise a payroll makes to people who
have rent to pay, and it is not the last day of the month: it steps back over
weekends and over the days the country takes off. This works that out and
nothing else — no records, no company, no database — so it can be tested
against a calendar somebody can check by hand.

``workdays`` is a set of weekday numbers where **Monday is 0**, matching the
company's own working calendar. ``holidays`` is a set of ``date`` objects.
"""
import calendar as _calendar
from datetime import date, timedelta

#: The payday rules a configuration can choose between.
PAYDAY_RULES = ('second_last_working', 'last_working', 'fixed')

#: The cut-off rules — the day approved inputs stop counting for this run.
#:
#: DELIBERATELY THE SAME THREE SHAPES AS A PAYDAY, because it is the same kind
#: of promise and it sits in the same row on the screen. It used to be a bare
#: day number, which has two faults a rule does not: a person could type 31,
#: which does not exist in February, April, June, September or November; and a
#: cut-off that lands on a Sunday is a deadline nobody can meet.
CUTOFF_RULES = ('last_working', 'before_payday', 'fixed')

#: The most working days before payday a cut-off may be set. Twenty is about a
#: month of them — past that the cut-off has walked into the previous run.
MAX_DAYS_BEFORE = 20

#: Monday to Friday — what a company with no working calendar of its own is
#: assumed to work, because saying nothing is worse than saying "weekends only".
DEFAULT_WORKDAYS = frozenset({0, 1, 2, 3, 4})


def is_working(day, workdays=None, holidays=None):
    """True when ``day`` is a day this company works."""
    workdays = workdays if workdays else DEFAULT_WORKDAYS
    if day.weekday() not in workdays:
        return False
    return day not in (holidays or frozenset())


def step_back(day, workdays=None, holidays=None, limit=62):
    """The first working day on or before ``day``, or None."""
    for _i in range(limit):
        if is_working(day, workdays, holidays):
            return day
        day = day - timedelta(days=1)
    return None


def payday_for(rule, day, year, month, workdays=None, holidays=None):
    """``(payday, skipped_weekends, skipped_holidays)`` — or ``(None, 0, 0)``.

    ``rule`` is one of :data:`PAYDAY_RULES`. ``day`` matters only for ``fixed``,
    where a day beyond the end of a short month becomes that month's last day —
    "the 31st" in a 30-day month means the 30th, not a date that does not exist.

    The two counts are what was STEPPED OVER on the way to the answer, so the
    screen can say "weekends and one public holiday skipped" and be believed.
    """
    last = _calendar.monthrange(year, month)[1]
    if rule == 'fixed':
        start = date(year, month, min(max(int(day or 1), 1), last))
    else:
        start = date(year, month, last)

    first = step_back(start, workdays, holidays)
    if first is None:
        return None, 0, 0
    target = first
    if rule == 'second_last_working':
        earlier = step_back(first - timedelta(days=1), workdays, holidays)
        if earlier is None:
            return None, 0, 0
        target = earlier

    weekends = holiday_count = 0
    cursor = start
    while cursor > target:
        if cursor.weekday() not in (workdays if workdays else DEFAULT_WORKDAYS):
            weekends += 1
        elif cursor in (holidays or frozenset()):
            holiday_count += 1
        cursor -= timedelta(days=1)
    return target, weekends, holiday_count


def working_days_before(day, count, workdays=None, holidays=None, limit=200):
    """The working day ``count`` working days before ``day``, or None.

    ``count`` is counted in WORKING days, not calendar days, because that is
    what a payroll team means by "three days before payday" — three days it can
    actually work in. Counting calendar days would put a Friday payday's
    three-day cut-off on the Tuesday in one month and swallow a long weekend in
    the next, and neither the screen nor the person could say which.

    ``day`` itself is pulled back to a working day first, so a count of zero
    means "the last working day on or before payday" rather than a Sunday.
    """
    left = max(int(count or 0), 0)
    cursor = step_back(day, workdays, holidays)
    if cursor is None:
        return None
    for _i in range(limit):
        if left <= 0:
            return cursor
        cursor = step_back(cursor - timedelta(days=1), workdays, holidays)
        if cursor is None:
            return None
        left -= 1
    return None


def cutoff_for(rule, day, days_before, payday, year, month,
               workdays=None, holidays=None):
    """The date approved inputs close on, or None.

    ``rule`` is one of :data:`CUTOFF_RULES`. Every shape lands on a working
    day — a deadline on a day the company is shut is not a deadline — and the
    fixed shape is capped at the 28th so it exists in February too.

    ``payday`` matters only for ``before_payday`` and is the date
    :func:`payday_for` already worked out, never a second guess at it.
    """
    last = _calendar.monthrange(year, month)[1]
    if rule == 'before_payday':
        if not payday:
            return None
        return working_days_before(payday, days_before, workdays, holidays)
    if rule == 'fixed':
        capped = min(max(int(day or 1), 1), min(28, last))
        return step_back(date(year, month, capped), workdays, holidays)
    return step_back(date(year, month, last), workdays, holidays)


def next_month(year, month):
    """The month after this one, as ``(year, month)``."""
    return (year + 1, 1) if month == 12 else (year, month + 1)
