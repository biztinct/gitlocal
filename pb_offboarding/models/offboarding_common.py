# -*- coding: utf-8 -*-
"""The vocabulary this module shares, in one place.

Same discipline as `pb_lifecycle/models/lifecycle_common.py` and
`pb_onboarding/models/onboarding_common.py`: a selection list or a parameter
name restated in two files is two lists the day one of them changes, and the
screens then disagree about what an exit IS.
"""

# ------------------------------------------------------------------ the exit
#: The four desks a leaver has to be signed off by. The order is the order they
#: are worked in and the order the four lights read on the board, so it is a
#: `sequence` in everything but name — never sorted alphabetically, which would
#: put Admin first and Finance (the one that actually holds the money) third.
CLEARANCE_DEPTS = [
    ('it', 'IT'),
    ('hr', 'HR'),
    ('finance', 'Finance'),
    ('admin', 'Admin'),
]
CLEARANCE_DEPT_LABEL = dict(CLEARANCE_DEPTS)
CLEARANCE_ORDER = [d for d, _label in CLEARANCE_DEPTS]

CLEARANCE_STATES = [
    ('pending', 'Waiting'),
    ('cleared', 'Cleared'),
    ('na', 'Not needed'),
]
CLEARANCE_STATE_LABEL = dict(CLEARANCE_STATES)

KT_STATES = [
    ('todo', 'To do'),
    ('in_progress', 'In progress'),
    ('done', 'Handed over'),
]
KT_STATE_LABEL = dict(KT_STATES)

#: The resignation ladder. `withdrawn` and `refused` are both terminal, and
#: both are reached by an explicit act — nothing here ever expires into them.
RESIGNATION_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'With the manager'),
    ('manager_ok', 'With HR'),
    ('approved', 'Approved'),
    ('refused', 'Not accepted'),
    ('withdrawn', 'Withdrawn'),
]
RESIGNATION_STATE_LABEL = dict(RESIGNATION_STATES)

#: The states a resignation may still be taken back from. Once HR has approved
#: it, the departure date is on the person's record, the leaving checklist is
#: running and other people have started work off the back of it — taking it
#: back at that point is a conversation, not a button.
RESIGNATION_WITHDRAWABLE = ('draft', 'submitted', 'manager_ok')
RESIGNATION_OPEN = ('draft', 'submitted', 'manager_ok')

RESIGNATION_SOURCES = [
    ('portal', 'Employee page'),
    ('manual', 'Entered by HR'),
    ('zoho', 'Connected system'),
]

# ---------------------------------------------------------------- automation
#: Registered by this phase into `pb.journey.task._automation_handlers()`,
#: which P3 built as a METHOD rather than a module-level dict precisely so a
#: later module could add to it without the two of them fighting over who
#: wrote last.
#:
#:    experience_letter  prepare and email the experience letter
#:    ff_cover           the covering letter for the final settlement, once it
#:                       has actually been closed
#:    farewell           the note to the team on the last day (switched off
#:                       until somebody turns it on)
#:    postexit_doc       remind whoever owns it what still has to be filed
AUTOMATION_KEYS = [
    ('experience_letter', 'Send the experience letter'),
    ('ff_cover', 'Send the settlement letter'),
    ('farewell', 'Send the farewell note'),
    ('postexit_doc', 'Remind about the post-exit documents'),
]
AUTOMATION_KEY_LABEL = dict(AUTOMATION_KEYS)

# ------------------------------------------------------------- config params
#: Every one of these has a working default in `DEFAULTS`. None of them has to
#: be set for the module to behave.
P_NOTICE_DAYS = 'pb_offboarding.notice_days'
P_KT_PING_DAYS = 'pb_offboarding.kt_ping_days'
P_KT_PING_MAIL = 'pb_offboarding.kt_ping_mail'
P_RESIGN_MAIL = 'pb_offboarding.resign_mail'
P_EXIT_FEEDBACK_MAIL = 'pb_offboarding.exit_feedback_mail'
P_EXIT_FEEDBACK_DAYS = 'pb_offboarding.exit_feedback_days'
P_FAREWELL_MAIL = 'pb_offboarding.farewell_mail'
P_FAREWELL_CAP = 'pb_offboarding.farewell_cap'

#: Who signs each clearance off. Empty means "work it out from the lifecycle
#: roles", which is what `pb.journey.case._resolve_assignee` already does — so
#: a tenant that has never opened the settings still gets a name on every row.
P_DEPT_USER = {
    'it': 'pb_offboarding.it_user_id',
    'hr': 'pb_offboarding.hr_user_id',
    'finance': 'pb_offboarding.finance_user_id',
    'admin': 'pb_offboarding.admin_user_id',
}

DEFAULTS = {
    P_NOTICE_DAYS: '30',
    P_KT_PING_DAYS: '15',
    P_KT_PING_MAIL: '1',
    P_RESIGN_MAIL: '1',
    P_EXIT_FEEDBACK_MAIL: '1',
    P_EXIT_FEEDBACK_DAYS: '21',
    # OFF, deliberately. A farewell note goes to a whole team, and a broadcast
    # that arrives because somebody installed a module is a broadcast nobody
    # chose. The step is left for a person until this is switched on, and the
    # log says which switch stopped it.
    P_FAREWELL_MAIL: '0',
    # Past this many colleagues the farewell is NOT sent and the log says so
    # (P3's welcome-card discipline: sixty people is a note, six hundred is an
    # incident, and the difference has to be a number somebody chose).
    P_FAREWELL_CAP: '60',
}

#: The tiers. Offboarding is not a separate permission from the rest of the
#: employee lifecycle — the board lives INSIDE the Lifecycle hub and answers a
#: question about the same cases — so it reuses P0's ladder rather than minting
#: a fifth one nobody would know to grant. (P3 made the same call for exactly
#: the same reason.)
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


def initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?')
            + (parts[-1][0] if len(parts) > 1 else '')).upper()


def first_name(name):
    """Vietnamese names put the given name LAST — "Bùi Anh Tâm" is Tâm.

    Every greeting in this module goes through here, the same helper P3 uses,
    so the day a tenant somewhere else wants the western order it is one
    function rather than forty templates.
    """
    parts = [p for p in (name or '').split() if p]
    return parts[-1] if parts else ''


def joined_sentence(items, limit=3):
    """"A, B and 4 more" — a list a person can read, never a raw repr.

    Every blocker message and every board tooltip in this module goes through
    here, so a settlement refused for eleven reasons says so in a sentence
    instead of printing eleven lines into a dialog.
    """
    items = [str(i) for i in items if i]
    if not items:
        return ''
    if len(items) <= limit:
        if len(items) == 1:
            return items[0]
        return '%s and %s' % (', '.join(items[:-1]), items[-1])
    return '%s and %s more' % (', '.join(items[:limit]), len(items) - limit)
