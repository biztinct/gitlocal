# -*- coding: utf-8 -*-
"""One way to turn a lazy translation into text: in the ASKER's language.

`str(_lt(...))` guesses the language from the call stack and logs a warning
when it cannot (no request in a test, a cron). The runner knows exactly whose
words these are, so it sets the language once per request and every card
string goes through `T()`.

P4 — the same language decides how numbers, months and times are WRITTEN on a
card: a Vietnamese reader gets "500.000", "tháng 12 năm 2031" and
"12/10/2026 14:05" — the way every other Payobook screen writes them for them.
"""
import calendar
import contextvars

_LANG = contextvars.ContextVar('payai_lang', default='')


def set_lang(lang):
    return _LANG.set(lang or 'en_US')


def reset_lang(token):
    _LANG.reset(token)


def lang():
    """The asker's language code ('en_US' when nobody set one)."""
    return _LANG.get() or 'en_US'


def is_vi(code=None):
    return (code or lang()).startswith('vi')


def T(value):
    """Text for a lazy translation (asker's language) or any other value."""
    if hasattr(value, '_translate'):
        return value._translate(lang())
    return str(value)


def EN(value):
    """The English source of a lazy translation — for what only the model
    reads (the tools schema stays English, P4 non-goal)."""
    if hasattr(value, '_translate'):
        return value._translate('en_US')
    return str(value)


def num(value, decimals=0):
    """1,234,567 (English) / 1.234.567 (Vietnamese); `decimals` places."""
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return str(value)
    text = ('{:,.%df}' % int(decimals)).format(value)
    if is_vi():
        text = text.replace(',', '\0').replace('.', ',').replace('\0', '.')
    return text


def short_amount(value):
    """'18.6 bn' / '4.2 m' (English) — '18,6 tỷ' / '4,2 triệu' (Vietnamese)."""
    a = abs(float(value or 0.0))
    vi = is_vi()
    for size, en_word, vi_word in ((1e9, 'bn', 'tỷ'), (1e6, 'm', 'triệu')):
        if a >= size:
            body = ('%.1f' % (a / size)).rstrip('0').rstrip('.')
            if vi:
                body = body.replace('.', ',')
            return '%s %s' % (body, vi_word if vi else en_word)
    return num(a)


def month_label(start, code=None):
    """'December 2031' / 'tháng 12 năm 2031' for a date's month."""
    if is_vi(code):
        return 'tháng %d năm %d' % (start.month, start.year)
    return '%s %s' % (calendar.month_name[start.month], start.year)


def stamp(when):
    """A card's time: '12 Oct 2026 14:05' / '12/10/2026 14:05'."""
    if is_vi():
        return when.strftime('%d/%m/%Y %H:%M')
    return when.strftime('%d %b %Y %H:%M')
