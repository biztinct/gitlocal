# -*- coding: utf-8 -*-
"""The decisions behind a notice and a release list, lifted out to be tested.

Same reason as `sync_rules.py` (rail R6): everything this feature DOES happens
on another database, and a test that mocked the write would only assert that
the mock was called. So the judgements — is this message sendable, what does
its window say in words, which ten releases does a customer get to read — are
pure functions here, and the call sites in `service.py` are left holding a read
and a write.

NOTHING HERE IMPORTS ODOO. That is the point: the file is reachable from a
plain unit test with no registry, and it cannot grow a database access by
accident.
"""
from datetime import date, datetime, timedelta

#: The two kinds of message the platform can put at the top of a customer's
#: screen, and they are two because they mean different things to the reader.
#: `maintenance` = something is about to happen to your service. `info` = here
#: is something you should know. Anything else is refused rather than guessed.
NOTICE_KINDS = ('maintenance', 'info')

#: How many releases a customer's "What's new" page carries. Ten is about two
#: months of shipping — far enough back to answer "when did that change?" and
#: short enough that the page is still one screen of scrolling.
RELEASE_HISTORY = 10

#: Longest a title / body may be. Not a security boundary (the platform owner
#: is the only person who can send one) — a LAYOUT boundary: the title sits on
#: one line of a bar that also has to hold a time range.
MAX_TITLE = 90
MAX_TEXT = 400

_STAMP = '%Y-%m-%d %H:%M:%S'


def parse_stamp(v):
    """A datetime out of whatever the screen sent. None when there is nothing.

    Accepts a `datetime`, `YYYY-MM-DD HH:MM:SS`, the browser's
    `YYYY-MM-DDTHH:MM` (what an `<input type="datetime-local">` produces), and
    a bare date. Raises `ValueError` on anything else, because a window nobody
    can read is worse than no window.
    """
    if v in (None, '', False):
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    s = str(v).strip().replace('T', ' ')
    if len(s) == 16:
        s += ':00'
    if len(s) == 10:
        s += ' 00:00:00'
    return datetime.strptime(s[:19], _STAMP)


def fmt_stamp(d):
    """A datetime as the framework's own string, or '' for nothing."""
    return d.strftime(_STAMP) if isinstance(d, datetime) else ''


def notice_payload(kind, title, text, starts_at, ends_at, notice_id):
    """The exact dict that will be written on every customer's database.

    Raises `ValueError` with a sentence a person can act on. The caller turns
    that into the screen's own error; nothing here knows what a UserError is.

    THE TITLE IS THE ONLY REQUIRED PART. A bar with no title is a coloured
    stripe: it tells the reader something is different and nothing else.
    """
    kind = (kind or '').strip()
    if kind not in NOTICE_KINDS:
        raise ValueError("Pick whether this is a planned update or information.")
    title = (title or '').strip()
    if not title:
        raise ValueError("Give the message a title — it is the line people read.")
    if len(title) > MAX_TITLE:
        raise ValueError(
            "The title is %d characters; keep it under %d so it fits on one "
            "line of the bar." % (len(title), MAX_TITLE))
    text = (text or '').strip()
    if len(text) > MAX_TEXT:
        raise ValueError(
            "The message is %d characters; keep it under %d — this is a bar at "
            "the top of a page, not an email." % (len(text), MAX_TEXT))
    starts = parse_stamp(starts_at)
    ends = parse_stamp(ends_at)
    if starts and ends and ends <= starts:
        raise ValueError("The message has to finish after it starts.")
    nid = (str(notice_id or '').strip())
    if not nid:
        raise ValueError("A message needs an identity so a reader who hides it "
                         "still sees the next one.")
    return {
        'id': nid,
        'kind': kind,
        'title': title,
        'text': text,
        'starts_at': fmt_stamp(starts),
        'ends_at': fmt_stamp(ends),
    }


def render_range(starts, ends, now=None):
    """"tonight 22:00–01:00" — the window, said the way a person would say it.

    The PLATFORM's clock, and the platform owner is the only reader of this
    one: it fills the sentence on his own confirmation ("this reaches 1
    customer, tonight 22:00–01:00"). The customer's bar renders the same window
    in the customer's own browser clock, which is the only place their offset
    is known.

    Returns '' when there is no window at all, so a caller can leave the line
    out rather than print an empty one.
    """
    a = parse_stamp(starts) if not isinstance(starts, datetime) else starts
    b = parse_stamp(ends) if not isinstance(ends, datetime) else ends
    now = now or datetime.now()
    if not a and not b:
        return ''
    if not a:
        return "until %s" % b.strftime('%H:%M')
    day = (a.date() - now.date()).days
    if not b:
        if day == 0:
            return "from %s today" % a.strftime('%H:%M')
        if day == 1:
            return "from %s tomorrow" % a.strftime('%H:%M')
        return "from %s %s" % (a.strftime('%a'), a.strftime('%H:%M'))
    # 18:00 is when a payroll office is empty, which is when every window the
    # owner has ever scheduled starts.
    if day == 0 and a.hour >= 18:
        return "tonight %s–%s" % (a.strftime('%H:%M'), b.strftime('%H:%M'))
    if day == 0 and a.date() == b.date():
        return "today %s–%s" % (a.strftime('%H:%M'), b.strftime('%H:%M'))
    if day == 1:
        return "tomorrow %s–%s" % (a.strftime('%H:%M'), b.strftime('%H:%M'))
    if a.date() == b.date():
        return "%s %s–%s" % (a.strftime('%a'), a.strftime('%H:%M'),
                             b.strftime('%H:%M'))
    return "%s %s – %s %s" % (a.strftime('%a'), a.strftime('%H:%M'),
                              b.strftime('%a'), b.strftime('%H:%M'))


def default_window(now=None):
    """The window the composer opens on: now → six hours' time.

    Not midnight-to-midnight and not a blank pair of boxes. Most messages are
    sent about something happening within the working day, and a box already
    holding a sensible answer is the difference between a control somebody uses
    and one they skip.
    """
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    return fmt_stamp(now), fmt_stamp(now + timedelta(hours=6))


def releases_list(all_releases, limit=RELEASE_HISTORY):
    """The last ten releases, newest first, as the customer's page reads them.

    `all_releases` is `[{'name', 'date', 'notes'}]` in any order. Sorted on the
    date and then on the name, both descending, so two releases cut on the same
    day (`2026.09.03` and `2026.09.03-2`) come out in the order they happened —
    the suffix sorts after the bare name, which is why the sort is reversed on
    the name too.

    Notes are trimmed; a release with none keeps the key with an empty string
    so the page never has to test for its absence.
    """
    rows = []
    for r in (all_releases or ()):
        if not isinstance(r, dict):
            continue
        name = (r.get('name') or '').strip()
        if not name:
            continue
        rows.append({
            'name': name,
            'date': (str(r.get('date') or '')).strip()[:10],
            'notes': (r.get('notes') or '').strip(),
        })
    rows.sort(key=lambda r: (r['date'], r['name']), reverse=True)
    return rows[:max(0, int(limit))]
