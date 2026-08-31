# -*- coding: utf-8 -*-
"""A calendar invitation, as bytes.

Owner ruling D3: a lifecycle meeting is an EMAIL WITH AN .ICS ATTACHMENT. No
external calendar is integrated, nothing is synchronised, and there is no second
place a meeting can exist and disagree with the first.

Deliberately a pure function of its arguments — no `self`, no environment, no
record — so P3 onwards can attach an invitation from anywhere and the whole
thing is testable without a database.
"""

import re
from datetime import datetime, timedelta


def _esc(text):
    """RFC 5545 §3.3.11 text escaping: backslash, semicolon, comma, newline."""
    out = (text or '')
    out = out.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,')
    return out.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')


def _stamp(value):
    """A naive UTC datetime as an iCalendar UTC timestamp."""
    if isinstance(value, str):
        value = datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
    return value.strftime('%Y%m%dT%H%M%SZ')


def _fold(line):
    """Lines are folded at 75 octets (RFC 5545 §3.1); a reader that does not
    fold produces a file some clients quietly refuse."""
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return line
    parts, chunk = [], b''
    for ch in line:
        enc = ch.encode('utf-8')
        if len(chunk) + len(enc) > 73:
            parts.append(chunk.decode('utf-8'))
            chunk = b''
        chunk += enc
    parts.append(chunk.decode('utf-8'))
    return '\r\n '.join(parts)


def build_ics(summary, dt_start, dt_end=None, organizer=None, attendees=None,
              description='', location='', uid=None):
    """Return a single-event iCalendar file as bytes.

    `dt_start` / `dt_end` are naive UTC datetimes (what the ORM stores) or the
    strings the ORM reads back. `dt_end` defaults to an hour after the start,
    which is what a check-in is unless somebody says otherwise.
    """
    if isinstance(dt_start, str):
        dt_start = datetime.strptime(dt_start[:19], '%Y-%m-%d %H:%M:%S')
    if not dt_end:
        dt_end = dt_start + timedelta(hours=1)
    now = datetime.utcnow()
    safe_uid = re.sub(r'[^A-Za-z0-9@._-]', '', uid or '') or (
        '%s@payobook' % _stamp(now))

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Payobook//Lifecycle//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:REQUEST',
        'BEGIN:VEVENT',
        'UID:%s' % safe_uid,
        'DTSTAMP:%s' % _stamp(now),
        'DTSTART:%s' % _stamp(dt_start),
        'DTEND:%s' % _stamp(dt_end),
        'SUMMARY:%s' % _esc(summary),
    ]
    if description:
        lines.append('DESCRIPTION:%s' % _esc(description))
    if location:
        lines.append('LOCATION:%s' % _esc(location))
    if organizer:
        lines.append('ORGANIZER:mailto:%s' % organizer)
    for who in (attendees or []):
        if who:
            lines.append(
                'ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:%s' % who)
    lines += ['STATUS:CONFIRMED', 'END:VEVENT', 'END:VCALENDAR']
    return ('\r\n'.join(_fold(line) for line in lines) + '\r\n').encode('utf-8')
