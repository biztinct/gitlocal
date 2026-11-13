# -*- coding: utf-8 -*-
"""The vocabulary this module shares, in one place.

Same discipline as `pb_lifecycle/models/lifecycle_common.py`,
`pb_onboarding/models/onboarding_common.py` and
`pb_offboarding/models/offboarding_common.py`: a selection list or a parameter
name restated in two files is two lists the day one of them changes, and the
screens then disagree about what a trial period IS.
"""

# ------------------------------------------------------------ where they stand
#: THE FIELD IS `hr.employee.pb_probation_state` AND THESE ARE ITS VALUES.
#: P6 (performance improvement) and P10 (contract lifecycle) both read it, so
#: the spelling is a contract rather than a preference.
#:
#: `na` is not a hole in the data — it is a real answer, and the honest one for
#: a contractor or a student who never had a trial period to be in.
PROBATION_STATES = [
    ('in_probation', 'In probation'),
    ('passed', 'Passed'),
    ('extended', 'Extended'),
    ('failed', 'Not passed'),
    ('na', 'Not applicable'),
]
PROBATION_STATE_LABEL = dict(PROBATION_STATES)

#: The two states that mean "this person is still being looked at". Everything
#: on the Probation lens, and every trigger the daily job makes, works off this
#: tuple rather than off a repeated `in ('in_probation', 'extended')`.
PROBATION_LIVE = ('in_probation', 'extended')

#: An employment type that never has a trial period on this build. `intern` is
#: not one of Odoo 19's own values (they are employee / worker / student /
#: trainee / contractor / freelance) but it is kept here because a tenant can
#: add to that selection and "intern" is the word they add.
NON_STAFF_TYPES = ('contractor', 'freelance', 'student', 'trainee', 'intern')

# --------------------------------------------------------------- the review
#: The seven stops a review makes. Deliberately linear: a review that can be in
#: two places at once is a review nobody can say the state of out loud.
REVIEW_STATES = [
    ('scheduled', 'Scheduled'),
    ('nomination', 'Peers being chosen'),
    ('feedback', 'Feedback running'),
    ('consolidation', 'Consolidating'),
    ('one_on_one', 'Manager 1:1'),
    ('verdict', 'Awaiting decision'),
    ('closed', 'Closed'),
]
REVIEW_STATE_LABEL = dict(REVIEW_STATES)

#: The states in which a review is still work. A second trigger for the same
#: person finds one of these and adds nothing (R30).
REVIEW_OPEN = ('scheduled', 'nomination', 'feedback', 'consolidation',
               'one_on_one', 'verdict')

#: What a review is FOR. `conversion` is shipped and not used — P10 reuses this
#: whole machine for turning a fixed-term contract into a permanent one, and
#: every method here is written against this field rather than against the word
#: "probation" so that phase passes one argument instead of forking a model.
REVIEW_KINDS = [
    ('probation', 'Probation'),
    ('conversion', 'Conversion'),
]
REVIEW_KIND_LABEL = dict(REVIEW_KINDS)

VERDICTS = [
    ('pass', 'Confirm them'),
    ('extend', 'Extend the trial'),
    ('fail', 'Do not confirm'),
]
VERDICT_LABEL = dict(VERDICTS)

#: How many colleagues a review asks. Fewer than three and one bad week decides
#: somebody's job; more than five and nobody answers because everybody assumes
#: somebody else will.
MIN_NOMINEES = 3
MAX_NOMINEES = 5

#: What the peers are asked. Four ratings and two comments, and the wording is
#: about WORK rather than about personality — "did they do what they said they
#: would" is answerable by a colleague; "are they a good fit" is not.
PEER_QUESTIONS = [
    {'key': 'quality', 'type': 'rating',
     'label': 'The quality of their work'},
    {'key': 'reliability', 'type': 'rating',
     'label': 'Doing what they said they would, when they said'},
    {'key': 'teamwork', 'type': 'rating',
     'label': 'Working with the people around them'},
    {'key': 'learning', 'type': 'rating',
     'label': 'Picking things up and asking when they are stuck'},
    {'key': 'strengths', 'type': 'text',
     'label': 'What have they been good at?'},
    {'key': 'improve', 'type': 'text',
     'label': 'What would you like to see more of from them?'},
]

#: The rating keys, in the order the report shows them. Derived from the list
#: above so the two can never drift apart.
PEER_RATING_KEYS = [q['key'] for q in PEER_QUESTIONS if q['type'] == 'rating']
PEER_QUESTION_LABEL = {q['key']: q['label'] for q in PEER_QUESTIONS}

#: Registered into `pb.journey.task._automation_handlers()`, which P3 built as
#: a METHOD rather than a module-level dict precisely so a later module could
#: add to it without the two of them fighting over who wrote last.
AUTOMATION_KEYS = [
    ('probation_review', 'Start the probation review'),
]
AUTOMATION_KEY_LABEL = dict(AUTOMATION_KEYS)

# ------------------------------------------------------------- config params
P_PROBATION_MAIL = 'pb_probation.probation_mail'
P_DURATION_MONTHS = 'pb_probation.duration_months'
P_LEAD_DAYS = 'pb_probation.evaluation_lead_days'
P_FEEDBACK_DAYS = 'pb_probation.feedback_window_days'
P_GRACE_DAYS = 'pb_probation.extension_grace_days'
P_EXTENSION_MONTHS = 'pb_probation.default_extension_months'
P_AUTO_TRIGGER = 'pb_probation.auto_trigger'
P_TRIGGER_CAP = 'pb_probation.trigger_cap'
P_REMIND_FAR = 'pb_probation.remind_days_far'
P_REMIND_NEAR = 'pb_probation.remind_days_near'
P_HOURLY_ALERTS = 'pb_probation.hourly_alerts'
P_BACKFILL_DONE = 'pb_probation.backfill_done'

DEFAULTS = {
    P_PROBATION_MAIL: '1',
    P_DURATION_MONTHS: '2',
    P_LEAD_DAYS: '21',
    P_FEEDBACK_DAYS: '3',
    P_GRACE_DAYS: '1',
    P_EXTENSION_MONTHS: '1',
    # OFF on install, deliberately. The daily job would otherwise open a review
    # for every trial period that is already inside its lead time the first
    # night after somebody installed a module — which on a database with a few
    # hundred joiners is a few hundred emails nobody asked for. The first run
    # COUNTS and logs instead, and an administrator turns it on once they have
    # read the number. (The Probation lens has the same switch on it in words.)
    P_AUTO_TRIGGER: '0',
    # And even switched on, one night never opens more than this many. A
    # backlog worked through over three nights is a backlog; three hundred at
    # once is an incident.
    P_TRIGGER_CAP: '20',
    P_REMIND_FAR: '15',
    P_REMIND_NEAR: '5',
    P_HOURLY_ALERTS: '1',
}

#: The tiers. A trial period is not a separate permission from the rest of the
#: employee lifecycle — the board lives INSIDE the Lifecycle hub and answers a
#: question about the same people — so this reuses P0's ladder rather than
#: minting a sixth one nobody would know to grant. (P3 and P4 made the same
#: call for the same reason.)
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
    """Vietnamese names put the given name LAST — "Bùi Anh Tâm" is Tâm."""
    parts = [p for p in (name or '').split() if p]
    return parts[-1] if parts else ''


def counted(count, one, many):
    """"1 peer" / "3 peers" — never "3 peer(s)" (R46)."""
    return '%s %s' % (count, one if count == 1 else many)


def joined_sentence(items, limit=3):
    """"A, B and 4 more" — a list a person can read, never a raw repr."""
    items = [str(i) for i in items if i]
    if not items:
        return ''
    if len(items) <= limit:
        if len(items) == 1:
            return items[0]
        return '%s and %s' % (', '.join(items[:-1]), items[-1])
    return '%s and %s more' % (', '.join(items[:limit]), len(items) - limit)


def add_months(day, months):
    """The same day, `months` later — clamped to the end of a short month.

    31 January plus one month is 28 February, not "31 February" and not an
    exception. Written out rather than pulled from `dateutil` because a trial
    end date is the kind of thing somebody reads off a screen and checks, and a
    dependency on somebody else's rounding rule is a dependency nobody can see.
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
