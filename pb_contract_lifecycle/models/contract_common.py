# -*- coding: utf-8 -*-
"""The vocabulary this module shares, in one place.

Same discipline as `pb_lifecycle/models/lifecycle_common.py` and
`pb_probation/models/probation_common.py`: a selection list or a parameter name
restated in two files is two lists the day one of them changes, and the screens
then disagree about what a contract decision IS.

THE ONE RULE THIS WHOLE MODULE IS BUILT AROUND (ruling D1). An extension and a
conversion create a NEW contract, linked to the old one, carrying the old one's
terms with new dates on it. Nothing here ever stretches an existing contract's
`date_end`, and nothing here ever writes a wage onto a contract that already
exists. The only in-place employment write RIZE allows is the probation trial
end date, and that belongs to P5.
"""

from datetime import timedelta

# ---------------------------------------------------------------- what a review is
#: The six places a contract decision can be. Deliberately linear apart from the
#: two side-trips (an extension waiting for a manager, an evaluation running),
#: both of which come back to `decide` if they do not finish.
REVIEW_STATES = [
    ('upcoming', 'Waiting'),
    ('decide', 'Decision needed'),
    ('extension', 'Extension requested'),
    ('conversion', 'Evaluation running'),
    ('done', 'Decided'),
    ('lapsed', 'Ended undecided'),
]
REVIEW_STATE_LABEL = dict(REVIEW_STATES)

#: The states in which a decision is still owed. A second trigger for the same
#: contract finds one of these and adds nothing (R30).
REVIEW_OPEN = ('upcoming', 'decide', 'extension', 'conversion')

#: The states in which somebody still has to press something. Used by the
#: escalations, which must not chase a decision that is already being worked on
#: by a manager (extension) or by a review panel (conversion).
REVIEW_WAITING = ('upcoming', 'decide')

DECISIONS = [
    ('terminate', 'Let it end'),
    ('extend', 'Extend it'),
    ('convert', 'Make it permanent'),
]
DECISION_LABEL = dict(DECISIONS)

# ------------------------------------------------------------- what somebody is
#: The employment types this build knows, after this module adds `intern`.
#: `hr.version.employee_type` is the field and `hr.employee.employee_type` is a
#: non-stored related onto it (R14), so the selection is extended THERE and the
#: employee's own field follows.
EMPLOYEE_TYPE_LABEL = {
    'employee': 'Permanent',
    'worker': 'Worker',
    'student': 'Student',
    'trainee': 'Trainee',
    'intern': 'Intern',
    'contractor': 'Contractor',
    'freelance': 'Freelancer',
}

#: Who this board is about beside the people whose contract has an end date.
#: An intern with no end date on their contract is still an intern, and leaving
#: them off the board is how somebody ends up permanent by accident.
NON_PERMANENT_TYPES = ('intern', 'contractor', 'freelance', 'student',
                       'trainee')

#: The words a contract type or a contract name uses for each employment type,
#: lowest-priority first so a later match wins. Used ONLY by the backfill and by
#: the arrival path — never to decide anything at read time, because a guess
#: dressed up as a fact is the thing this module exists to replace.
TYPE_WORDS = (
    ('worker', ('worker', 'labour', 'labor', 'công nhân')),
    ('student', ('student', 'thesis', 'sinh viên')),
    ('trainee', ('trainee', 'apprentice', 'apprenticeship', 'học việc')),
    ('freelance', ('freelance', 'freelancer')),
    # NOT "fixed-term". A fixed-term EMPLOYEE is an employee — the whole point
    # of this module is that a permanent member of staff can be on an agreement
    # with a date on it — and typing them as a contractor would move them out
    # of the headcount and out of the trial-period rules. The live backfill
    # retyped a test employee on a contract called "P10 fixed-term — …" and
    # that was the tell. The "Fixed-term contractor" contract type still
    # matches, on the word "contractor" that is actually in it.
    ('contractor', ('contractor', 'subcontractor', 'sub-contractor',
                    'consultant', 'outsourced', 'agency')),
    ('intern', ('intern', 'internship', 'thực tập')),
)

#: The two contract types this module wants to exist. `Intern` is usually
#: already there — the standard `hr` module seeds twelve types including it —
#: so it is ENSURED rather than seeded, by name, once, and a database that
#: already has one keeps the one it has.
CONTRACT_TYPE_INTERN = 'Intern'
CONTRACT_TYPE_FIXED_TERM = 'Fixed-term contractor'

# ------------------------------------------------------------- config params
P_MAIL = 'pb_contract_lifecycle.contract_mail'
P_LEAD_DAYS = 'pb_contract_lifecycle.lead_days'
P_APPROVE_DAYS = 'pb_contract_lifecycle.approve_days'
P_EXTENSION_MONTHS = 'pb_contract_lifecycle.default_extension_months'
P_AUTO_TRIGGER = 'pb_contract_lifecycle.auto_trigger'
P_TRIGGER_CAP = 'pb_contract_lifecycle.trigger_cap'
P_NAG_DAYS = 'pb_contract_lifecycle.nag_days'
P_BACKFILL_DONE = 'pb_contract_lifecycle.backfill_done'

DEFAULTS = {
    P_MAIL: '1',
    # Two months. The blueprint's number, and the reason for it: a decision
    # about somebody's contract that is taken in its last fortnight is a
    # decision the calendar took.
    P_LEAD_DAYS: '60',
    # How long a manager has to approve an extension before it is escalated.
    P_APPROVE_DAYS: '5',
    P_EXTENSION_MONTHS: '12',
    # OFF on install, deliberately, exactly as P5's is (R54). The first night
    # after somebody installs a module must not open a review and email a
    # manager for every contract already inside its lead time. Switched off,
    # the daily job COUNTS them and writes the number in the log; the lens says
    # the same number on screen; an administrator turns it on.
    P_AUTO_TRIGGER: '0',
    # And even switched on, one night never opens more than this many.
    P_TRIGGER_CAP: '20',
    # Inside this many days of the end, HR is nudged every day.
    P_NAG_DAYS: '7',
}

#: The tiers. A contract decision is not a separate permission from the rest of
#: the employee lifecycle — this board lives INSIDE the Lifecycle hub and asks a
#: question about the same people — so this reuses P0's ladder rather than
#: minting a seventh one nobody would know to grant. P3, P4 and P5 all made the
#: same call for the same reason.
GROUP_USER = 'pb_lifecycle.group_lifecycle_user'
GROUP_MANAGER = 'pb_lifecycle.group_lifecycle_manager'
GROUP_ADMIN = 'pb_lifecycle.group_lifecycle_admin'


def param(env, name, default=None):
    """One config-parameter read, with the module's own default behind it."""
    return env['ir.config_parameter'].sudo().get_param(
        name, DEFAULTS.get(name) if default is None else default)


def flag(env, name):
    """A config parameter read as a switch. Anything but 0/false is on."""
    raw = param(env, name)
    return str(raw).strip() not in ('0', 'false', 'False', '', 'None')


def number(env, name, fallback):
    try:
        return int(str(param(env, name)).strip())
    except (TypeError, ValueError):
        return fallback


def counted(count, one, many):
    """"1 contract" / "3 contracts" — never "3 contract(s)" (R46)."""
    return '%s %s' % (count, one if count == 1 else many)


def first_name(name):
    """Vietnamese names put the given name LAST — "Bùi Anh Tâm" is Tâm."""
    parts = [p for p in (name or '').split() if p]
    return parts[-1] if parts else ''


def initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?')
            + (parts[-1][0] if len(parts) > 1 else '')).upper()


def add_months(day, months):
    """The same day, `months` later — clamped to the end of a short month.

    Written out rather than pulled from `dateutil` for the reason P5 wrote it
    out: a contract end date is the kind of thing somebody reads off a screen
    and checks, and a dependency on somebody else's rounding rule is a
    dependency nobody can see. 31 January plus one month is 28 February, not
    "31 February" and not an exception.
    """
    if not day:
        return day
    months = int(months or 0)
    year = day.year + (day.month - 1 + months) // 12
    month = (day.month - 1 + months) % 12 + 1
    last = [31,
            29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
            else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return day.replace(year=year, month=month, day=min(day.day, last))


def term_end(start, months):
    """The last day of a term of `months` that begins on `start`.

    NOT `add_months(start, months)`. A twelve-month contract beginning on
    1 November 2026 ends on 31 October 2027, and the next one begins on
    1 November — `add_months` alone would end it on 1 November 2027 and the
    next term would start on the 2nd, so every renewal walks a day further
    from the anniversary it is supposed to keep. Found on the first live
    extension, which came back a day long.
    """
    if not start:
        return start
    return add_months(start, months) - timedelta(days=1)


def type_from_words(*texts):
    """The employment type a piece of text is talking about, or ''.

    Used by the backfill and by the arrival path only. Later entries in
    `TYPE_WORDS` win, so "Intern" beats "fixed-term" in a string that somehow
    contains both — an intern on a fixed-term contract is an intern.
    """
    blob = ' '.join(str(t or '') for t in texts).lower()
    if not blob.strip():
        return ''
    found = ''
    for kind, words in TYPE_WORDS:
        if any(word in blob for word in words):
            found = kind
    return found
