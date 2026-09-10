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


def next_month(year, month):
    """The month after this one, as ``(year, month)``."""
    return (year + 1, 1) if month == 12 else (year, month + 1)
