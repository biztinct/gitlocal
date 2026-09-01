# -*- coding: utf-8 -*-
"""The words, the caps and the small helpers every file here shares.

One module, one vocabulary. A budget TYPE is spelled the same on the model, in
the spreadsheet, on the lens and in the PDF, because three spellings of the same
idea is how a filter quietly matches nothing.
"""

import logging
import unicodedata

from odoo import _

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the types
#: What a budget is FOR. Manpower is what payroll pays; the other two are what
#: HR and the office spend, which payroll facts know nothing about.
BUDGET_TYPES = [
    ('manpower', 'People'),
    ('hr_ops', 'HR operations'),
    ('admin', 'Admin'),
]
TYPE_KEYS = tuple(k for k, _l in BUDGET_TYPES)

#: Where a row's BUDGET figure came from. The SPENT figure's provenance is a
#: different question and is answered by `pb_actual_synced_on` (payroll) or by
#: the expense rows that roll into it.
SOURCES = [
    ('upload', 'Uploaded'),
    ('auto', 'Auto actuals'),
    ('manual', 'Entered by hand'),
]

#: The measure the Cost Explorer's `cost` lens sums, verbatim
#: (`pb_explorer/models/pb_explorer.py:73`). Restated here rather than imported
#: because it is a CONTRACT between two modules: if the Explorer ever changes
#: what "total cost" means, this list must be changed deliberately and the
#: budget's history re-read, not silently follow it.
COST_CATEGORY_TYPES = ('basic', 'allowance', 'employer_cost')

# ---------------------------------------------------------------- the caps
#: Rows the board will read. A cap that is right for a SCREEN is a bug in a
#: CRON (R76), so every cap here is a PARAMETER with a default and the jobs
#: pass `None`.
BOARD_ROW_CAP = 4000
EXPENSE_ROW_CAP = 2000
#: How far back the actuals job re-reads. Eighteen months covers a fiscal year
#: plus the tail of the one before it.
ACTUALS_MONTHS = 18

# ------------------------------------------------------------- the switches
#: Defaults live in CODE, never in a `noupdate="1"` record — a shipped record
#: freezes whatever value a test run left behind, because the next upgrade never
#: corrects it (the call P3–P8 all made).
DEFAULTS = {
    'pb_budget.fy_start_month': '1',
    'pb_budget.actuals_months': str(ACTUALS_MONTHS),
    'pb_budget.auto_actuals': '1',
}


def param(env, key, default=None):
    """A config parameter, with this module's own default behind it."""
    raw = env['ir.config_parameter'].sudo().get_param(key)
    if raw in (None, False, ''):
        raw = DEFAULTS.get(key, default)
    return raw


def param_int(env, key, default=0):
    try:
        return int(str(param(env, key, default)).strip())
    except (TypeError, ValueError):
        return default


def flag(env, key):
    return str(param(env, key, '0')).strip().lower() in ('1', 'true', 'yes', 'on')


def counted(n, one, many):
    """"1 department" / "4 departments" — never "1 department(s)" (R46)."""
    return one if n == 1 else many % n


def fold(text):
    """Accents folded, never stripped (R28/R78).

    Postgres on this box has no `unaccent`, and most of the people and a good
    few of the departments on this tenant carry an accent, so every match this
    module makes on a name is made in Python over folded text.
    """
    if not text:
        return ''
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(c for c in out if not unicodedata.combining(c))
    # Vietnamese `đ` carries no combining mark, so NFKD leaves it alone.
    out = out.replace('đ', 'd').replace('Đ', 'D')
    return out.strip().lower()


def type_label(key):
    for k, lbl in BUDGET_TYPES:
        if k == key:
            return _(lbl)
    return key or ''


def safe(fn, default=None, what='a piece of the budget board'):
    """Every independent probe gets its OWN try/except — never a shared one."""
    try:
        return fn()
    except Exception as e:                      # noqa: BLE001
        _logger.debug('pb_budget: %s could not be read: %s', what, e)
        return default
