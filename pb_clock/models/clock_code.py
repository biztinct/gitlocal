# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""One rule for comparing clock numbers (WFSETUP P10b, owner ruling R8).

A clock sends the number a person is enrolled under on the machine. Some
machines drop leading zeros ("12") while the person's badge ID keeps them
("012"). R8: matching ignores leading zeros, everywhere a clock number is
compared — the clock matcher (`pb.clock.pairing._code_index`), the
"match numbers" screen (`pb.clock.lens`) and the late / overtime rules
(`pb_attendance_policy` `_policy_calculate`).

Exact equality is always tried first; the zero-free form only decides a
number nothing matched exactly, and two people sharing one zero-free form are
never picked between.

Plain stdlib on purpose (no `odoo` import): the rule is testable on its own.
"""

#: How many leading zeros the variant set adds. Badge IDs on the reference
#: tenant carry one; four is the `_suggest` precedent (`clock_lens.py`).
MAX_EXTRA_ZEROS = 4


def norm(code):
    """The comparable form of a clock number.

    Trimmed; a number made only of digits loses its leading zeros ("0012" ->
    "12", "000" -> "0"); anything else is returned trimmed and unchanged.
    """
    value = (code or '').strip()
    if value and value.isdigit():
        return value.lstrip('0') or '0'
    return value


def variants(code):
    """Every spelling that has the same comparable form as `code`, bounded.

    `{code, core} ∪ {'0' * k + core | k = 1..MAX_EXTRA_ZEROS}` for a digit
    number; `{code}` otherwise. Used to search stored values with an `in`
    domain, so a clock that ADDS zeros is found as well as one that drops them.
    """
    value = (code or '').strip()
    if not value:
        return set()
    if not value.isdigit():
        return {value}
    core = norm(value)
    out = {value, core}
    out.update(('0' * k) + core for k in range(1, MAX_EXTRA_ZEROS + 1))
    return out
