# -*- coding: utf-8 -*-
"""The vocabulary this module shares, in one place.

Same discipline as `pb_lifecycle/models/lifecycle_common.py` and
`pb_probation/models/probation_common.py`: a selection list or a parameter name
restated in two files is two lists the day one of them changes, and the screens
then disagree about what an improvement plan IS.
"""

# ------------------------------------------------------------------- the case
#: The seven stops a plan makes. Linear on purpose, and the first two are the
#: whole argument of this module: a REQUEST is not a plan, and COACHING is not
#: a plan either. Most of these should end at `coaching` without a letter ever
#: being written, and the board is built so that reads as success rather than
#: as an abandoned record.
PIP_STATES = [
    ('requested', 'Requested'),
    ('coaching', 'Coaching'),
    ('active', 'Plan running'),
    ('evaluation', 'Being evaluated'),
    ('passed', 'Completed successfully'),
    ('failed', 'Not successful'),
    ('terminated', 'Closed — left the company'),
]
PIP_STATE_LABEL = dict(PIP_STATES)

#: The states in which a plan is still work. A second request for the same
#: person finds one of these and adds nothing (R30's shape).
PIP_OPEN = ('requested', 'coaching', 'active', 'evaluation')

#: The states in which the person themselves has a page worth reading. A
#: request nobody has taken up yet is deliberately NOT one of them — telling
#: somebody "your manager has asked HR about you" before HR has even read it
#: would be the cruellest possible use of this module.
PIP_EMPLOYEE_VISIBLE = ('active', 'evaluation')

#: How often the check-ins land.
CHECKIN_FREQS = [
    ('weekly', 'Every week'),
    ('biweekly', 'Every two weeks'),
]
CHECKIN_FREQ_LABEL = dict(CHECKIN_FREQS)
CHECKIN_FREQ_DAYS = {'weekly': 7, 'biweekly': 14}

#: Where each objective stands. `on_track` is the default because a plan that
#: opens with everything "at risk" is a plan nobody believes in.
OBJECTIVE_STATES = [
    ('on_track', 'On track'),
    ('at_risk', 'At risk'),
    ('met', 'Met'),
    ('not_met', 'Not met'),
]
OBJECTIVE_STATE_LABEL = dict(OBJECTIVE_STATES)

#: The two ways a plan can end by decision.
VERDICTS = [
    ('pass', 'Completed successfully'),
    ('fail', 'Not successful'),
]
VERDICT_LABEL = dict(VERDICTS)
VERDICT_STATE = {'pass': 'passed', 'fail': 'failed'}

#: What the manager is asked at the end, BESIDE the per-objective ratings that
#: are generated from the plan itself. Two questions, both about work.
EVAL_QUESTIONS = [
    {'key': 'overall', 'type': 'rating',
     'label': 'Overall, where are they now against where the plan needed '
              'them to be'},
    {'key': 'evidence', 'type': 'text',
     'label': 'What have you actually seen change?'},
    {'key': 'support', 'type': 'text',
     'label': 'What support did they get, and what would you do differently?'},
]

#: The prefix an objective question carries in the evaluation form, so the
#: verdict wizard can put the answer back beside the objective it belongs to.
EVAL_OBJECTIVE_PREFIX = 'obj_'

# ---------------------------------------------------------------- the letters
#: The letter a started plan prepares. There is exactly one — the pass and fail
#: outcomes are a conversation and a note on the record, not a second letter, on
#: purpose: a "you completed your improvement plan" letter filed in somebody's
#: documents forever is a punishment for having succeeded.
LETTER_PIP = 'pb_pip.letter_template_pip'

# ------------------------------------------------------------- config params
P_PIP_MAIL = 'pb_pip.pip_mail'
P_MANAGER_SEES_OWN = 'pb_pip.manager_sees_own'
P_EMPLOYEE_VIEW = 'pb_pip.employee_view'
P_DEFAULT_WEEKS = 'pb_pip.default_weeks'
P_MISSED_DAYS = 'pb_pip.missed_checkin_days'
P_AUTO_TERMINATE = 'pb_pip.auto_terminate'

DEFAULTS = {
    P_PIP_MAIL: '1',
    # ON, and the two of them are the D5 ruling in code: the person sees their
    # own plan and acknowledges it, and their manager can see the request they
    # themselves raised. Both are one row away from off for a company whose
    # lawyers say otherwise.
    P_MANAGER_SEES_OWN: '1',
    P_EMPLOYEE_VIEW: '1',
    P_DEFAULT_WEEKS: '6',
    # A check-in nobody held two days after it was planned is the strongest
    # single signal that a plan is drifting, and the earliest one available.
    P_MISSED_DAYS: '2',
    # ON, unlike P5's trigger. This one only ever CLOSES something: a person
    # who has resigned should not still be on an improvement plan, and the
    # first night after install has nothing to do because it fires on an
    # approval rather than on a scan.
    P_AUTO_TERMINATE: '1',
}

# ---------------------------------------------------------------- the tiers
#: THIS MODULE HAS ITS OWN LADDER, and that is the single most important
#: decision in the phase.
#:
#: P3, P4 and P5 all rode P0's lifecycle tiers, correctly: a joining checklist,
#: a leaving checklist and a trial period are the same question about the same
#: people, and a fourth ladder would have been a group nobody knew to grant.
#:
#: An improvement plan is NOT that question. A lifecycle administrator looks
#: after arrivals and departures for a whole company; knowing which four people
#: in it are on an improvement plan is a different piece of information with a
#: different blast radius, and "they could already see the joining checklists"
#: is not a reason to hand it over. So there is no `implied_ids` from any
#: lifecycle group into either of these, in either direction, and access is
#: granted by name.
GROUP_USER = 'pb_pip.group_pip_user'
GROUP_HEAD = 'pb_pip.group_pip_head'

#: Every internal user. The requesting manager's one door.
GROUP_INTERNAL = 'base.group_user'


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
    """"1 objective" / "3 objectives" — never "3 objective(s)" (R46)."""
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
