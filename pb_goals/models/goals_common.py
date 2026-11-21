# -*- coding: utf-8 -*-
"""The words, the dials and the handful of helpers every file here needs.

WHY A COMMON FILE AT ALL. Two facades, a portal controller, an approval
adapter, a journey handler and the nightly job all need the same three things:
the group names, the switches with their defaults, and the helpers that stop a
sentence reading like a machine wrote it. Copied around they drift, and a
plural that says "1 goal(s)" in one place and "1 goal" in another is worse
than either on its own (R46).
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the tiers
#: THE LADDER IS THREE RUNGS AND A MANAGER IS NOT ON IT. A line manager holds
#: no goals group by definition — they are somebody's manager, not somebody in
#: HR — and the record rule carries them instead. Handing every manager in the
#: company a group would be handing them the whole company's goals.
GROUP_USER = 'pb_goals.group_goals_user'
GROUP_MANAGER = 'pb_goals.group_goals_manager'
GROUP_ADMIN = 'pb_goals.group_goals_admin'
ALL_GROUPS = (GROUP_USER, GROUP_MANAGER, GROUP_ADMIN)

# --------------------------------------------------------------- the dials
#: EVERY SWITCH DEFAULTS IN CODE and the `post_init_hook` merely materialises
#: the row so an administrator can find it. A `noupdate="1"` record for a
#: switch freezes whatever value a test run happened to leave behind, because
#: the next upgrade never corrects it. Every reader still goes through
#: `flag()`/`number()`/`text()`, so a database with no row at all behaves
#: identically — the rows exist to be FOUND.
P_KICKOFF_AUTO = 'pb_goals.kickoff_auto'
P_REMINDERS = 'pb_goals.reminders'
P_SLA_DAYS = 'pb_goals.sla_days'
P_ESCALATE_DAYS = 'pb_goals.escalate_days'
P_MANAGER_MAIL = 'pb_goals.manager_mail'
P_SUBMISSION_DAYS = 'pb_goals.submission_days'
P_ROW_LIMIT = 'pb_goals.row_limit'
P_REMINDER_CAP = 'pb_goals.reminder_cap'
P_BULK_CAP = 'pb_goals.bulk_cap'
#: ------------------------------------------------------------------ B2
#: The year AFTER the goals are agreed: the monthly conversation, the two
#: reviews, and the day the year is scored and put away.
P_CHECKINS = 'pb_goals.checkins'
P_CHECKIN_DAY = 'pb_goals.checkin_day'
P_MID_YEAR_MIN_MONTHS = 'pb_goals.mid_year_min_months'
P_YEAR_END_MIN_MONTHS = 'pb_goals.year_end_min_months'
P_YEAREND_MAIL = 'pb_goals.yearend_mail'
P_REVIEW_LEAD_DAYS = 'pb_goals.review_lead_days'
#: DELIBERATELY NOT IN `DEFAULTS`. `set_param(key, '')` DELETES the row on this
#: build, so an empty-string default cannot be materialised: a hook that tried
#: would write it, find it missing on the next read and write it again for
#: ever. Read through `text()`, which falls back in code — empty means "use the
#: company's own email address", which is the honest default.
P_HR_SENDER = 'pb_goals.hr_sender'

DEFAULTS = {
    # ON, and it is the one automatic switch in this module that ships on.
    # Every other automation here writes to a crowd; this one only ever
    # touches ONE new joiner at a time, on their own second day, and the
    # thing it makes is an empty goal sheet addressed to them. The first
    # night after an install cannot therefore surprise anybody.
    P_KICKOFF_AUTO: '1',
    # ON. The chasing is the whole point of a deadline: a date nobody is
    # reminded of is a wish. It is a switch because a company mid-rollout may
    # not want the first night to write to everybody, and a switch that is off
    # SAYS so on the board (R54).
    P_REMINDERS: '1',
    # THE ROUTE'S OWN SLA, not a cron of ours. `route(due_days=…)` sets when a
    # rung falls due and the engine's `escalate_cron` widens the chase after
    # `late.escalate_days`. Five working days to read somebody's goals and two
    # more before the HR lead hears about it.
    P_SLA_DAYS: '5',
    P_ESCALATE_DAYS: '2',
    # ON. The route already puts the request in the manager's inbox; this is
    # the courtesy email beside it, for a manager who lives in their mail.
    P_MANAGER_MAIL: '1',
    # A fortnight to write your goals. Every cycle carries its own figure and
    # this is only the number a new cycle starts with.
    P_SUBMISSION_DAYS: '14',
    # A CAP THAT IS RIGHT FOR A SCREEN IS A BUG IN A JOB (R76). These two are
    # separate dials on purpose: the first is a page size, the second is a
    # safety rail so a misconfigured deadline cannot mail the whole company
    # twice. The job logs honestly when it hits it.
    P_ROW_LIMIT: '400',
    P_REMINDER_CAP: '400',
    # How many goal sheets one press of "Open it for everyone" may make. A
    # rail rather than a page size — the button says how many it would make
    # before it makes any (R54).
    P_BULK_CAP: '2000',
    # ------------------------------------------------------------------ B2
    # ON. A goal year without a monthly conversation is a spreadsheet that
    # gets opened twice. The job only ever makes ONE row a month per agreed
    # sheet and writes to the two people who are already having the
    # conversation, so the first night after an upgrade cannot surprise a
    # company: it makes this month's rows and stops.
    P_CHECKINS: '1',
    # The day of the month the conversation is planned for. The 25th is late
    # enough that the month has happened and early enough that somebody can
    # still do something about it.
    P_CHECKIN_DAY: '25',
    # HOW LONG SOMEBODY HAS TO HAVE BEEN HERE for a review to be fair. Both
    # are counted from the day their goals actually start covering — the
    # later of their joining day and the day the year began. Three months is
    # the shipped answer and it is a dial, because "fair" is a company's
    # word and not ours.
    P_MID_YEAR_MIN_MONTHS: '3',
    P_YEAR_END_MIN_MONTHS: '3',
    # ON. The one email at the end of the year that says what the score was.
    P_YEAREND_MAIL: '1',
    # How many days before a review's date it appears on people's screens and
    # starts being chased.
    P_REVIEW_LEAD_DAYS: '30',
}

# =========================================================================
#  What a goal cycle IS, in the words on the screen
# =========================================================================
CYCLE_STATES = [
    ('draft', 'Being set up'),
    ('open', 'Open'),
    ('closed', 'Closed'),
]
CYCLE_STATE_LABEL = dict(CYCLE_STATES)

#: HOW FAR A PERSON'S GOAL SHEET HAS GOT.
#:
#: `returned` and `refused` are separate on purpose and the difference is
#: whether there is anything left to do: a sheet sent back is a sheet somebody
#: is expected to fix, and a sheet turned down is finished. One column trying
#: to say both is how a board ends up unable to show the single most useful row
#: on it — the person whose goals came back a week ago and who has not touched
#: them since.
#: `closed` (B2) is the end of the road and is deliberately a STATUS rather
#: than an archive flag: "this year is finished and scored" is a thing a board
#: has to be able to show, and a row that simply disappears is a row somebody
#: goes looking for.
SET_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Waiting on their manager'),
    ('manager_ok', 'Waiting on the HR lead'),
    ('locked', 'Agreed and locked'),
    ('returned', 'Sent back'),
    ('refused', 'Turned down'),
    ('closed', 'Finished for the year'),
]
SET_STATE_LABEL = dict(SET_STATES)

#: The states in which the employee may still edit their own goals. Leaving
#: this set is what "locked" means, and it is the only rule the portal has.
SET_EDITABLE = ('draft', 'returned')

#: The states that still need somebody to do something. A board that ranks the
#: PROBLEM first (R113) ranks over this order and not over the spelling of the
#: state — ordering by a Selection column sorts the stored string, which is
#: alphabetical and never lifecycle order (R50).
SET_OPEN = ('draft', 'returned', 'submitted', 'manager_ok')

#: Problem first: what somebody is waiting on, worst first. Used by every
#: surface that sorts a list of goal sheets, so the board, the drawer and the
#: nightly job can never disagree about which row matters most.
SET_RANK = {
    'returned': 0,      # sent back and nobody has picked it up
    'draft': 1,         # never sent in
    'submitted': 2,     # waiting on a manager
    'manager_ok': 3,    # waiting on the HR lead
    'refused': 4,
    'locked': 5,        # nothing to do
    'closed': 6,        # the year is over
}

#: The states in which a goal sheet is LIVE — agreed, not yet put away. This is
#: the set the monthly conversation, the two reviews and the scoring all ask
#: about, and it is written once here so four files cannot disagree about what
#: "running" means.
SET_RUNNING = ('locked',)


# =========================================================================
#  B2 — the year after the goals are agreed
# =========================================================================
#: THE MONTHLY CONVERSATION. `missed` is a real outcome and not an error: a
#: month nobody talked is a fact a manager's own record should carry, and a row
#: that quietly stays "planned" for ever is a row that says nothing at all.
CHECKIN_STATES = [
    ('planned', 'Planned'),
    ('done', 'Done'),
    ('missed', 'Missed'),
]
CHECKIN_STATE_LABEL = dict(CHECKIN_STATES)

#: The two moments in a year when somebody sits down and scores the goals.
REVIEW_KINDS = [
    ('mid_year', 'Half-way review'),
    ('year_end', 'End-of-year review'),
]
REVIEW_KIND_LABEL = dict(REVIEW_KINDS)

REVIEW_STATES = [
    ('planned', 'Planned'),
    ('done', 'Done'),
]
REVIEW_STATE_LABEL = dict(REVIEW_STATES)

#: WHAT SOMEBODY IS ASKING TO CHANGE. Four kinds because four is what actually
#: happens, and because the sentence a manager reads is different for each: a
#: goal that has been overtaken is DROPPED, a new priority is ADDED, a target
#: that moved is EDITED, and a re-prioritised year is a REWEIGHT.
CHANGE_KINDS = [
    ('edit', 'Change a goal'),
    ('add', 'Add a goal'),
    ('drop', 'Drop a goal'),
    ('reweight', 'Change the weights'),
]
CHANGE_KIND_LABEL = dict(CHANGE_KINDS)

CHANGE_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Waiting on their manager'),
    ('manager_ok', 'Waiting on the HR lead'),
    ('approved', 'Agreed and carried out'),
    ('refused', 'Turned down'),
]
CHANGE_STATE_LABEL = dict(CHANGE_STATES)

#: Problem first again (R113): what somebody has to DO about it, worst first.
CHANGE_RANK = {
    'submitted': 0,
    'manager_ok': 1,
    'draft': 2,
    'refused': 3,
    'approved': 4,
}

#: The states a change request is still travelling in.
CHANGE_OPEN = ('draft', 'submitted', 'manager_ok')

#: HOW A KEY RESULT IS SCORED, and the words for each number. Nought to five
#: and never a bare number: "3" means nothing on a screen, and a translator
#: handed an integer has nothing to translate. The scale matches the
#: self-rating's five rungs on purpose — the employee said "On track" in
#: April and the manager says "On track" in March, and the two words are the
#: same word.
SCORES = [
    ('0', 'Not done'),
    ('1', 'Well below'),
    ('2', 'Below'),
    ('3', 'On track'),
    ('4', 'Above'),
    ('5', 'Well above'),
]
SCORE_LABEL = dict(SCORES)

#: The highest a key result can score. Named rather than written as a 5 in six
#: files, because the band table and the sentence that explains it both quote
#: it.
SCORE_MAX = 5.0

#: How somebody rates their own chances, and the words for each. One to five
#: and never a number on its own: "3" means nothing on a screen, and a
#: translator handed a bare integer has nothing to translate.
RATINGS = [
    ('1', 'Well below'),
    ('2', 'Below'),
    ('3', 'On track'),
    ('4', 'Above'),
    ('5', 'Well above'),
]
RATING_LABEL = dict(RATINGS)

#: The weights on one person's goals have to add up to exactly this. It is a
#: constant rather than a literal sprinkled through four files, because the
#: sentence that refuses a manager quotes it.
WEIGHT_TOTAL = 100

#: The most goals one person may have in one cycle. Not a permission — a
#: kindness: twelve goals is not a plan, it is a list, and a sheet with
#: twenty on it cannot have meaningful weights.
MAX_GOALS = 12

#: The most key results one goal may carry, same reasoning.
MAX_KRS = 8


# ------------------------------------------------------------- the helpers
def leg(env, label, fn):
    """One piece of paperwork, inside its own SAVEPOINT (R131).

    A TRY/EXCEPT IS NOT ENOUGH WHEN THE THING THAT FAILED REACHED THE
    DATABASE. Postgres aborts the whole transaction on an error and catching
    the exception in Python does not revive it: every statement after it fails
    too, INCLUDING the write the paperwork was about. That is how a record
    ends up reading "approved" in one place and "waiting" in another for ever,
    with nothing but a cheerful warning in the log.
    """
    try:
        with env.cr.savepoint():
            return fn()
    except Exception:                   # noqa: BLE001 — paperwork never fails
        _logger.warning('pb_goals: %s failed', label, exc_info=True)
        return False


def flag(env, key, default=None):
    """A switch, read as a switch and never as a truthy string."""
    raw = env['ir.config_parameter'].sudo().get_param(
        key, DEFAULTS.get(key) if default is None else default)
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def number(env, key, default=0):
    raw = env['ir.config_parameter'].sudo().get_param(
        key, DEFAULTS.get(key, default))
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return int(default)


def text(env, key, default=''):
    """A switch whose value is WORDS, not a number and not a yes/no."""
    raw = env['ir.config_parameter'].sudo().get_param(key, default)
    return (str(raw) if raw else str(default or '')).strip()


def counted(count, one, many):
    """"1 goal" and "3 goals", never "1 goal(s)" (R46).

    Both words are passed in whole so a translator gets a sentence rather than
    a frame with a hole in it (R117).
    """
    return one if count == 1 else many


def fold(value):
    """Accent-blind text for a search box.

    Postgres on this build has no `unaccent` extension (R78) and most people
    on this database have an accent in their name, so the folding happens in
    Python. `đ` carries no combining mark, so NFKD leaves it and it is mapped
    by hand (R28).
    """
    if not value:
        return ''
    out = unicodedata.normalize('NFKD', str(value))
    out = ''.join(ch for ch in out if not unicodedata.combining(ch))
    return out.replace('đ', 'd').replace('Đ', 'D').lower()


def as_id(value):
    """A record argument arrives over the wire as a plain integer (R43).

    Every public method that takes "a record" coerces at the door, so an RPC
    caller and an in-process caller reach the same code — including the ones a
    phase writes for itself (R52).
    """
    if not value:
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(value.id)
    except (AttributeError, TypeError, ValueError):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def due_words(due, today):
    """"Due today", "3 days left", "8 days overdue" — the sentence, whole.

    THE WHOLE SENTENCE AND NEVER A FRAME WITH A NUMBER IN IT (R117): "%s days
    left" is ungrammatical for exactly one of its values, and a translator
    handed the frame and the number separately cannot fix a plural they were
    never given. There are five outcomes and each one is written out.
    """
    if not due:
        return ''
    days = (due - today).days
    if days == 0:
        return 'Due today'
    if days == 1:
        return '1 day left'
    if days > 1:
        return '%s days left' % days
    if days == -1:
        return '1 day overdue'
    return '%s days overdue' % (-days)


def days_over(due, today):
    """How many days late, or 0 for something that is not late yet."""
    if not due:
        return 0
    return max((today - due).days, 0)


def weight_sentence(total):
    """Why a manager cannot approve yet, with the arithmetic in the words.

    "Weights add up to 90, not 100" is a sentence somebody can act on. "Invalid
    weight total" is a sentence somebody has to ask about.
    """
    return ("The weights add up to %(have)s, not %(want)s. Change them on the "
            "goals so they total %(want)s, then agree it." % {
                'have': int(round(total or 0)), 'want': WEIGHT_TOTAL})
