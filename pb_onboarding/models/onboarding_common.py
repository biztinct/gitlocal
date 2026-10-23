# -*- coding: utf-8 -*-
"""The vocabulary the onboarding module shares, in one place.

Same discipline as `pb_lifecycle/models/lifecycle_common.py`: a selection list
or a parameter name restated in two files is two lists the day one of them
changes, and the screens then disagree about what a new joiner IS.
"""

# ---------------------------------------------------------------- automation
#: The steps that run THEMSELVES on their due date. A step declares which
#: handler it wants with `automation_key`; anything else with a kind of
#: 'email' or 'letter' falls back to the generic sender.
#:
#: P4-P7 add to this dict from their own modules by overriding
#: `pb.journey.task._automation_handlers()` — the key is the contract, not this
#: file. Registered by P3:
#:
#:    credentials  tell the joiner their sign-in is ready (P1's send_credentials)
#:    poster       the welcome card, mailed to their new team
#:    day1_ics     the day-one introduction, with a calendar invitation attached
#:    buddy_invite the manager's nudge to nominate a buddy
#:    asset_laptop the laptop request that was raised when the journey opened
AUTOMATION_KEYS = [
    ('credentials', 'Send sign-in details'),
    ('poster', 'Send the welcome card'),
    ('day1_ics', 'Send the day-one invitation'),
    ('buddy_invite', 'Ask the manager for a buddy'),
    ('asset_laptop', 'Laptop request'),
]

AUTOMATION_KEY_LABEL = dict(AUTOMATION_KEYS)

# ------------------------------------------------------------------ eligibility
#: A candidate buddy is offered with one of three verdicts. `fail` is never
#: silently hidden — a person is shown WITH the reason, because "why can't I
#: pick Lan?" is the question the dialog exists to answer.
ELIGIBILITY_LEVELS = [
    ('pass', 'Good fit'),
    ('warn', 'Worth a look'),
    ('fail', 'Not eligible'),
]

#: Employment kinds that are not a full-time colleague. `employee_type` is
#: barely filled in on this database, so an EMPTY value is treated as
#: full-time and warned about rather than refused (a rule that refuses on
#: missing data refuses everybody).
NON_STAFF_TYPES = ('contractor', 'intern', 'freelance')

# -------------------------------------------------------------------- pulses
DAY_MARKS = [('7', 'Day 7'), ('30', 'Day 30'), ('60', 'Day 60')]
DAY_MARK_LABEL = dict(DAY_MARKS)
DAY_MARK_OFFSET = {'7': 7, '30': 30, '60': 60}

PULSE_STATES = [
    ('planned', 'Planned'),
    ('sent', 'Sent'),
    ('answered', 'Answered'),
    ('cancelled', 'Cancelled'),
]

#: 1 and 2 out of 5 are the scores that put a name in front of HR the same day.
PULSE_RED_MAX = 2

# ------------------------------------------------------------- config params
#: Every one of these has a working default. None of them has to be set for
#: the module to behave; all of them can be turned off in one row.
P_POSTER_MAIL = 'pb_onboarding.poster_mail'
P_PULSE_MAIL = 'pb_onboarding.pulse_mail'
P_BUDDY_MAIL = 'pb_onboarding.buddy_mail'
P_AUTO_STEPS = 'pb_onboarding.auto_steps'
P_POSTER_CAP = 'pb_onboarding.poster_cap'
P_ORIENT_FREQ = 'pb_onboarding.orientation_freq'
P_ORIENT_WEEKDAY = 'pb_onboarding.orientation_weekday'
P_BUDDY_DAYS = 'pb_onboarding.buddy_connect_days'
P_BUDDY_COUNT = 'pb_onboarding.buddy_connect_count'
P_BUDDY_TENURE = 'pb_onboarding.buddy_tenure_months'
P_DAY1_HOUR = 'pb_onboarding.day1_hour'

DEFAULTS = {
    P_POSTER_MAIL: '1',
    P_PULSE_MAIL: '1',
    P_BUDDY_MAIL: '1',
    P_AUTO_STEPS: '1',
    P_POSTER_CAP: '60',
    P_ORIENT_FREQ: 'biweekly',
    P_ORIENT_WEEKDAY: '1',          # 0 = Monday, so 1 = Tuesday
    P_BUDDY_DAYS: '14',
    P_BUDDY_COUNT: '6',             # every two weeks for three months
    P_BUDDY_TENURE: '6',
    P_DAY1_HOUR: '9',               # 09:00 local, the introduction meeting
}

#: The tiers. Onboarding is not a separate permission from the rest of the
#: employee lifecycle — the board lives INSIDE the Lifecycle hub and answers
#: the same question the Journeys board does — so it reuses P0's ladder rather
#: than minting a fourth one nobody would know to grant.
GROUP_USER = 'pb_lifecycle.group_lifecycle_user'
GROUP_MANAGER = 'pb_lifecycle.group_lifecycle_manager'
GROUP_ADMIN = 'pb_lifecycle.group_lifecycle_admin'


def param(env, name, default=None):
    """One config-parameter read, with the module's own default behind it."""
    raw = env['ir.config_parameter'].sudo().get_param(
        name, DEFAULTS.get(name) if default is None else default)
    return raw

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

    Every greeting in this module goes through here, so the day a tenant
    somewhere else wants the western order it is one function, not forty
    templates. Same choice `pb_lifecycle`'s token page already made.
    """
    parts = [p for p in (name or '').split() if p]
    return parts[-1] if parts else ''
