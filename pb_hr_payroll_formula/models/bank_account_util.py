# -*- coding: utf-8 -*-
"""Bank-account value hygiene — the one place that decides what an imported
account number actually IS.

Like `column_role_classifier`, this is DELIBERATELY plain Python: no `odoo`
import, no model, stdlib only. The import batch, the studio and the test table in
`tests/test_bank_account_util.py` all share one answer, and that table can be run
with a bare `python3` without a database.

The problem it exists for: a spreadsheet is the worst possible carrier for an
account number. `0071000123456` is a *string* whose first character is load-bearing,
and every path that touches it wants to turn it into a number:

  * a cell typed as General turns `0071000123456` into the float 71000123456.0 and
    the leading zeros are gone before the file ever reaches us;
  * a long enough number is re-displayed as `1.23456789012E+11`, and if that text
    is what we are handed, the digits BEYOND the twelfth no longer exist anywhere;
  * a human types `007-100 0123 456` with grouping dashes and a non-breaking space
    pasted out of a bank's web page.

Only the third of those is recoverable, so only the third is repaired. The other
two are reported as damage — never guessed at. Writing a wrong account number into
a payroll system is the one failure in this file that costs real money, so the rule
is: repair formatting, refuse to invent digits.
"""

import re

# Floats are exact integers only below 2**53. Above it, `%d` prints digits that the
# float does not actually carry — a plausible-looking, wrong account number.
_FLOAT_EXACT_LIMIT = 2 ** 53

# Separators a human (or a bank's website) puts INSIDE an account number. Space,
# NBSP, narrow NBSP, the three dash variants Excel likes, and the thin space.
_SEPARATORS = (' ', ' ', ' ', ' ', '\t', '-', '‐', '‑',
               '‒', '–', '—', '.', '_', '/')

# What a cleaned account number may consist of. Alphanumeric rather than digits:
# IBANs ("VN82BFTV0071…") and several Asian formats carry letters, and rejecting
# them would be a worse bug than the one this guards against.
_ACC_RE = re.compile(r'^[0-9A-Za-z]+$')

# Scientific notation as a STRING — "1.23456789012E+11". By the time a cell reads
# like this the trailing digits are gone, and `float()`-ing it would manufacture a
# twelve-digit number that looks entirely reasonable.
_SCI_RE = re.compile(r'^[+-]?\d+(\.\d+)?[eE][+-]?\d+$')


def sanitize_acc_number(raw):
    """``(account_number, damaged)`` for one raw spreadsheet value.

    ``account_number`` is a clean string, or ``None``. ``damaged`` is True only when
    there WAS a value and it cannot be trusted — an empty cell is absent, not
    damaged, and must not raise a warning on every employee who has no bank row.

    Rules, in order:

      * blank / None                      → (None, False)
      * bool                              → (None, False)   (never an account)
      * int                               → its digits
      * float, integer-valued, < 2**53    → its digits ('%d', never `str()`, which
                                            would append the `.0`)
      * float, anything else              → (None, True)
      * str in scientific notation        → (None, True)
      * str, separators stripped, alnum   → itself, leading zeros intact
      * str, anything else left           → (None, True)

    A string is NEVER int-cast. That is the whole point of the function.
    """
    if raw is None or isinstance(raw, bool):
        return None, False

    if isinstance(raw, int):
        return str(raw), False

    if isinstance(raw, float):
        if raw != raw or raw in (float('inf'), float('-inf')):   # NaN / inf
            return None, True
        if not raw.is_integer():
            return None, True
        if abs(raw) >= _FLOAT_EXACT_LIMIT:
            return None, True
        return '%d' % int(raw), False

    text = str(raw).strip()
    if not text:
        return None, False

    if _SCI_RE.match(text.replace(' ', '').replace(' ', '')):
        return None, True

    for sep in _SEPARATORS:
        text = text.replace(sep, '')
    if not text:
        return None, False
    if not _ACC_RE.match(text):
        return None, True
    return text, False


def sanitize_bank_text(raw):
    """A bank name / holder name / BIC as a plain trimmed string, or None.

    Floats reach here too (a bank whose name is "1234" is a real thing in the
    Vietnamese exports), so an integer-valued float loses its `.0` the same way an
    account number does — `str(1234.0)` on a payslip is the sort of detail that
    makes a whole import look untrustworthy.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, float) and raw.is_integer() and abs(raw) < _FLOAT_EXACT_LIMIT:
        raw = int(raw)
    text = str(raw).strip()
    return text or None


def acc_numbers_match(left, right):
    """Compare two account numbers the way a human would: on their sanitized form,
    case-insensitively (IBAN letters are conventionally upper-case but arrive both
    ways). Damaged values never match anything, including each other."""
    a, a_bad = sanitize_acc_number(left)
    b, b_bad = sanitize_acc_number(right)
    if a_bad or b_bad or not a or not b:
        return False
    return a.upper() == b.upper()
