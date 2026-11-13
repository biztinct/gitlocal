"""Start on a schedule — the date maths (WORKFLOW-2 P5a).

Pure functions, no models: the worker, the "Next 5 starts" preview and the
tests all use exactly these (one implementation).

A schedule (inside a definition's ``trigger`` when ``kind == 'schedule'``)::

    {'every': 'day' | 'week' | 'month' | 'year' | 'once',
     'at': 'HH:MM',                 # company time
     'weekdays': [0..6],            # week: Monday = 0
     'day': 1..31 | 'last',         # month, year: "31" in a 30-day month = last day
     'month': 1..12,                # year
     'date': 'YYYY-MM-DD',          # once
     'working_days': bool,          # a start on a non-working day moves to the next working day
     'starts': 'process' | 'each_record'}

Times are the company's (its working calendar's time zone). A local time that
does not exist on the day the clocks go forward starts an hour later; a local
time that happens twice on the day they go back starts once (the first time).
Catch-up is the worker's business: it asks for the starts between the last
look and now, and starts only the latest one.
"""
import calendar as _calendar
import re
from datetime import date, datetime, time, timedelta

import pytz

from odoo.tools.translate import LazyTranslate

#: P5b: every sentence below is a lazy translation; the caller passes the
#: language (`lang`), and no language means English, as before.
_lt = LazyTranslate(__name__)

EVERY = ('day', 'week', 'month', 'year', 'once')
STARTS = ('process', 'each_record')
AT = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
DAY_NAMES = (_lt('Monday'), _lt('Tuesday'), _lt('Wednesday'), _lt('Thursday'), _lt('Friday'),
             _lt('Saturday'), _lt('Sunday'))
MONTH_NAMES = (_lt('January'), _lt('February'), _lt('March'), _lt('April'), _lt('May'), _lt('June'),
               _lt('July'), _lt('August'), _lt('September'), _lt('October'), _lt('November'),
               _lt('December'))
#: The short month in "Once, on 20 Nov 2026" (English: the first three letters).
MONTH_SHORT = (_lt('Jan'), _lt('Feb'), _lt('Mar'), _lt('Apr'), _lt('May'), _lt('Jun'),
               _lt('Jul'), _lt('Aug'), _lt('Sep'), _lt('Oct'), _lt('Nov'), _lt('Dec'))
#: How far back the worker looks for a missed start (it only ever starts the
#: latest one, so this only has to be longer than any gap between two starts).
LOOKBACK_DAYS = 400
#: How far a "working days only" start may move forward.
SHIFT_DAYS = 14
#: Each-record starts per tick (handover: default 500).
FAN_OUT_CAP = 500


def fresh(has_record):
    return {'every': 'week', 'at': '09:00', 'weekdays': [0], 'day': 1, 'month': 1,
            'date': '', 'working_days': False,
            'starts': 'each_record' if has_record else 'process'}


def _t(lang, text, **args):
    """A lazy sentence in `lang` (None or en_US: the English source,
    unchanged), filled with `args`."""
    out = text._translate(lang) if lang and lang != 'en_US' else text._source
    return out % args if args else out


def issues(s, has_record, lang=None):
    """[(code, text)] for a schedule; empty when it is complete. With
    `has_record` None the "what it starts for" check is left to the caller,
    which knows the record type."""
    if not isinstance(s, dict):
        return [('schedule_missing', _t(lang, _lt('Choose when this workflow starts.')))]
    out = []
    every = s.get('every')
    if every not in EVERY:
        out.append(('schedule_every', _t(lang, _lt('Choose how often it starts.'))))
    if not isinstance(s.get('at'), str) or not AT.match(s.get('at') or ''):
        out.append(('schedule_time', _t(lang, _lt('Choose a start time.'))))
    if every == 'week':
        days = s.get('weekdays')
        if not isinstance(days, list) or not days or any(type(d) is not int or not 0 <= d <= 6 for d in days):
            out.append(('schedule_weekdays', _t(lang, _lt('Choose at least one day of the week.'))))
    if every in ('month', 'year'):
        day = s.get('day')
        if day != 'last' and (type(day) is not int or not 1 <= day <= 31):
            out.append(('schedule_day', _t(lang, _lt('Choose a day of the month.'))))
    if every == 'year' and (type(s.get('month')) is not int or not 1 <= s['month'] <= 12):
        out.append(('schedule_month', _t(lang, _lt('Choose a month.'))))
    if every == 'once':
        try:
            date.fromisoformat(str(s.get('date') or ''))
        except ValueError:
            out.append(('schedule_date', _t(lang, _lt('Choose the date it starts.'))))
    if 'working_days' in s and type(s['working_days']) is not bool:
        out.append(('schedule_working', _t(lang, _lt('Choose whether it starts on working days only.'))))
    starts = s.get('starts')
    if starts not in STARTS or (has_record is not None and (starts == 'each_record') != bool(has_record)):
        out.append(('schedule_starts', _t(lang, _lt('Choose what it starts for: a new process, or each matching record.'))
                    if not has_record else _t(lang, _lt('A workflow on records starts once for each matching record.'))))
    return out


def _last_day(year, month):
    return _calendar.monthrange(year, month)[1]


def _day_of(s, year, month):
    """The day number in that month: "last", or the day capped at the
    month's last day ("31st" in April = 30 April, 29 February in a common
    year = 28 February)."""
    last = _last_day(year, month)
    return last if s.get('day') == 'last' else min(int(s.get('day') or 1), last)


def fires_on(s, d):
    every = s.get('every')
    if every == 'day':
        return True
    if every == 'week':
        return d.weekday() in (s.get('weekdays') or [])
    if every == 'month':
        return d.day == _day_of(s, d.year, d.month)
    if every == 'year':
        return d.month == s.get('month') and d.day == _day_of(s, d.year, d.month)
    if every == 'once':
        return str(d) == str(s.get('date') or '')
    return False


def _at(s):
    hour, minute = (int(x) for x in str(s.get('at') or '09:00').split(':'))
    return time(hour, minute)


def _shift(d, working):
    """The first working day on or after `d` (at most SHIFT_DAYS on)."""
    for offset in range(SHIFT_DAYS + 1):
        candidate = d + timedelta(days=offset)
        if working(candidate):
            return candidate
    return None


def to_utc(local_naive, tz):
    """A wall-clock time in `tz` as naive UTC. Exists twice → the first;
    does not exist → an hour later (pytz's standard-time reading)."""
    try:
        aware = tz.localize(local_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        aware = tz.localize(local_naive, is_dst=True)
    except pytz.exceptions.NonExistentTimeError:
        aware = tz.normalize(tz.localize(local_naive, is_dst=False))
    return aware.astimezone(pytz.utc).replace(tzinfo=None)


def _zone(tzname):
    try:
        return pytz.timezone(tzname or 'UTC')
    except pytz.exceptions.UnknownTimeZoneError:
        return pytz.utc


def _local_date(utc_naive, tz):
    return pytz.utc.localize(utc_naive).astimezone(tz).date()


def _starts_on_days(s, first, last, working=None):
    """{start day: base day} for base days in [first, last] (a start moved to
    a working day keeps the earliest base day that moved there)."""
    out = {}
    d = first
    while d <= last:
        if fires_on(s, d):
            day = _shift(d, working) if (working and s.get('working_days')) else d
            if day is not None and day not in out:
                out[day] = d
        d += timedelta(days=1)
    return out


def ticks(s, tzname, after_utc, until_utc, working=None):
    """Every start in (after_utc, until_utc], oldest first, as naive UTC."""
    if not s or after_utc is None or until_utc <= after_utc:
        return []
    tz = _zone(tzname)
    first = max(_local_date(after_utc, tz), _local_date(until_utc, tz) - timedelta(days=LOOKBACK_DAYS)) \
        - timedelta(days=SHIFT_DAYS + 1)
    last = _local_date(until_utc, tz) + timedelta(days=1)
    at = _at(s)
    out = []
    for day in sorted(_starts_on_days(s, first, last, working)):
        moment = to_utc(datetime.combine(day, at), tz)
        if after_utc < moment <= until_utc:
            out.append(moment)
    return out


def next_ticks(s, tzname, from_utc, count=5, working=None, horizon_days=1500):
    """The next `count` starts strictly after `from_utc` (naive UTC)."""
    if not s:
        return []
    tz = _zone(tzname)
    at = _at(s)
    start = _local_date(from_utc, tz) - timedelta(days=SHIFT_DAYS + 1)
    out = []
    window = 62
    first = start
    while len(out) < count and (first - start).days < horizon_days:
        last = first + timedelta(days=window)
        for day in sorted(_starts_on_days(s, first, last, working)):
            moment = to_utc(datetime.combine(day, at), tz)
            if moment > from_utc and moment not in out:
                out.append(moment)
        first = last + timedelta(days=1)
        if s.get('every') == 'once' and first > date.fromisoformat(str(s.get('date') or '1970-01-01')) + timedelta(days=SHIFT_DAYS + 1):
            break
    return sorted(out)[:count]


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return '%d%s' % (n, suffix)


def words(s, lang=None):
    """"Every Monday at 9:00", "On the last day of each month at 17:30",
    "Once, on 20 Nov 2026 at 8:00", "… , or the next working day" — in
    `lang` (None: English)."""
    text = _words(s, lang)
    if isinstance(s, dict) and s.get('working_days') and s.get('every') in EVERY and s['every'] != 'day':
        text = _t(lang, _lt('%(when)s, or the next working day'), when=text)
    return text


def _words(s, lang=None):
    if not isinstance(s, dict) or s.get('every') not in EVERY:
        return _t(lang, _lt('On a schedule'))
    at = str(s.get('at') or '09:00')
    hour, minute = at.split(':') if ':' in at else ('9', '00')
    at = '%d:%s' % (int(hour), minute)
    every = s['every']
    if every == 'day':
        if s.get('working_days'):
            return _t(lang, _lt('Every working day at %(time)s'), time=at)
        return _t(lang, _lt('Every day at %(time)s'), time=at)
    if every == 'week':
        days = sorted(set(d for d in (s.get('weekdays') or []) if type(d) is int and 0 <= d <= 6))
        if days == [0, 1, 2, 3, 4]:
            return _t(lang, _lt('Every weekday at %(time)s'), time=at)
        if len(days) == 7:
            return _t(lang, _lt('Every day at %(time)s'), time=at)
        names = [_t(lang, DAY_NAMES[d]) for d in days] or [_t(lang, DAY_NAMES[0])]
        named = names[0] if len(names) == 1 else _t(
            lang, _lt('%(days)s and %(last)s'), days=', '.join(names[:-1]), last=names[-1])
        return _t(lang, _lt('Every %(days)s at %(time)s'), days=named, time=at)
    if every == 'month':
        if s.get('day') == 'last':
            return _t(lang, _lt('On the last day of each month at %(time)s'), time=at)
        day = int(s.get('day') or 1)
        # `nth` is the English ordinal ("21st"); a translation may use the
        # plain number (`day`) instead
        return _t(lang, _lt('On the %(nth)s of each month at %(time)s'), nth=ordinal(day), day=day, time=at)
    if every == 'year':
        known = type(s.get('month')) is int and 1 <= s['month'] <= 12
        month = _t(lang, MONTH_NAMES[int(s.get('month') or 1) - 1] if known else MONTH_NAMES[0])
        if s.get('day') == 'last':
            return _t(lang, _lt('Every year on the last day of %(month)s at %(time)s'), month=month, time=at)
        return _t(lang, _lt('Every year on %(day)s %(month)s at %(time)s'),
                  day=int(s.get('day') or 1), month=month, time=at)
    try:
        d = date.fromisoformat(str(s.get('date') or ''))
        return _t(lang, _lt('Once, on %(day)s %(month)s %(year)s at %(time)s'),
                  day=d.day, month=_t(lang, MONTH_SHORT[d.month - 1]), year=d.year, time=at)
    except ValueError:
        return _t(lang, _lt('Once'))
