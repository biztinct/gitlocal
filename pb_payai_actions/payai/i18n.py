# -*- coding: utf-8 -*-
"""One way to turn a lazy translation into text: in the ASKER's language.

`str(_lt(...))` guesses the language from the call stack and logs a warning
when it cannot (no request in a test, a cron). The runner knows exactly whose
words these are, so it sets the language once per request and every card
string goes through `T()`.
"""
import contextvars

_LANG = contextvars.ContextVar('payai_lang', default='')


def set_lang(lang):
    return _LANG.set(lang or 'en_US')


def reset_lang(token):
    _LANG.reset(token)


def T(value):
    """Text for a lazy translation (asker's language) or any other value."""
    if hasattr(value, '_translate'):
        return value._translate(_LANG.get() or 'en_US')
    return str(value)
