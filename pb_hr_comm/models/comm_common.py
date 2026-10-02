# -*- coding: utf-8 -*-
"""The words, the dials and the handful of helpers every file here needs.

WHY A COMMON FILE AT ALL. Two facades, an approval adapter, the sender, the
nightly nudge and the calendar all need the same three things: the group names,
the switches with their defaults, and the helpers that stop a sentence reading
like a machine wrote it. Copied around they drift, and a plural that says
"1 person(s)" in one place and "1 person" in another is worse than either on
its own (ledger R46).
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the tiers
#: THREE RUNGS, AND THE RESPONSIBLE IS NOT ON ANY OF THEM. The person whose
#: name is on an announcement may be a plant manager or an office lead who
#: holds no HR permission at all, and handing them a group would hand them
#: every announcement in the company. The record rule carries them instead —
#: "the posts I am responsible for" is a domain, and a domain is the right
#: tool for a permission granted by a RECORD rather than by a group (R157).
GROUP_USER = 'pb_hr_comm.group_comm_user'
GROUP_MANAGER = 'pb_hr_comm.group_comm_manager'
GROUP_ADMIN = 'pb_hr_comm.group_comm_admin'
ALL_GROUPS = (GROUP_USER, GROUP_MANAGER, GROUP_ADMIN)

# --------------------------------------------------------------- the dials
#: EVERY SWITCH DEFAULTS IN CODE and the `post_init_hook` merely materialises
#: the row so an administrator can find it. A `noupdate="1"` record for a
#: switch freezes whatever value a test run happened to leave behind, because
#: the next upgrade never corrects it. Every reader still goes through
#: `flag()`/`number()`, so a database with no row at all behaves identically —
#: the rows exist to be FOUND.
P_SEND_MAIL = 'pb_hr_comm.send_mail'
P_SIGNOFF = 'pb_hr_comm.signoff'
P_EDIT_WINDOW = 'pb_hr_comm.edit_window_days'
P_BURST_CAP = 'pb_hr_comm.burst_cap'
P_NUDGE_DAYS = 'pb_hr_comm.nudge_days'
P_ROW_LIMIT = 'pb_hr_comm.row_limit'

DEFAULTS = {
    # ON. An announcement that is written, agreed and scheduled and then does
    # not go out is the one failure this module must not have — and the switch
    # is here for a company mid-rollout that wants the calendar before it
    # wants the post. Off, the job still says what it WOULD have sent, on the
    # record and in the log (R54).
    P_SEND_MAIL: '1',
    # OFF, and this is the owner's ruling. Most companies do not ask anybody
    # to agree a canteen notice, and a route that ships on would put every
    # announcement in somebody's inbox from the first morning. A company that
    # wants a second pair of eyes turns it on and the same published route
    # picks it up with nothing else to set up.
    P_SIGNOFF: '0',
    # TWO DAYS. Up to two days before it goes out the person responsible can
    # still change anything; inside that window only the HR lead can, and the
    # change is written into the post's own history. The number is a dial
    # because "how late is too late" is a company's word and not ours.
    P_EDIT_WINDOW: '2',
    # HOW MANY EMAILS ONE TICK OF THE SENDER MAY QUEUE. Five hundred is a
    # notification; four and a half thousand in one breath is an incident, and
    # the difference has to be a number somebody chose. Past it the rest go on
    # the next tick, ten minutes later, and nobody is missed — the delivery
    # rows are what makes that safe (see `pb.hr.comm.delivery`).
    P_BURST_CAP: '500',
    # HOW MANY DAYS BEFORE IT GOES OUT the person responsible is reminded.
    # Two, which is the same two the edit window uses on purpose: the nudge
    # arrives on the last day they can still change it themselves, and it says
    # so.
    P_NUDGE_DAYS: '2',
    # A CAP THAT IS RIGHT FOR A SCREEN IS A BUG IN A JOB (R76). This one is a
    # page size for the calendar and nothing else reads it; the sender has its
    # own rail above.
    P_ROW_LIMIT: '400',
}


# =========================================================================
#  What an announcement IS, in the words on the screen
# =========================================================================
#: HOW FAR A POST HAS GOT.
#:
#: `sending` is a real status and not a flicker: an announcement to four and a
#: half thousand people takes several ticks of the sender, and a board that
#: cannot show "this one is going out right now" is a board somebody presses
#: twice. `cancelled` is the end of the road for one that was stopped, and it
#: is deliberately a STATUS rather than an archive flag — a post that simply
#: disappears is a post somebody goes looking for.
POST_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Waiting on the HR lead'),
    ('scheduled', 'Scheduled'),
    ('sending', 'Going out now'),
    ('sent', 'Sent'),
    ('cancelled', 'Cancelled'),
]
POST_STATE_LABEL = dict(POST_STATES)

#: The states in which an announcement has not gone out yet and can still be
#: changed by somebody. Leaving this set is what "too late" means.
POST_OPEN = ('draft', 'submitted', 'scheduled')

#: The states in which the post is the sender's business and nobody else's.
POST_CLOSED = ('sending', 'sent', 'cancelled')

#: Problem first (R113): what somebody has to DO about it, worst first. Used
#: by every surface that sorts a list of posts, so the calendar, the side list
#: and the Home card can never disagree about which row matters most. Never
#: order by the Selection column itself — that sorts the stored string, which
#: is alphabetical order pretending to be lifecycle order (R50).
POST_RANK = {
    'submitted': 0,     # somebody is waiting to be asked
    'draft': 1,         # written and never scheduled
    'scheduled': 2,     # on its way
    'sending': 3,       # going out right now
    'sent': 4,
    'cancelled': 5,
}

#: The chip colour for each status, so three surfaces cannot disagree.
POST_TONE = {
    'draft': 'wait',
    'submitted': 'wait',
    'scheduled': 'go',
    'sending': 'go',
    'sent': 'ok',
    'cancelled': 'off',
}

#: WHO AN ANNOUNCEMENT IS FOR. Four kinds because four is what actually
#: happens, and because the sentence a person reads is different for each.
AUDIENCE_KINDS = [
    ('everyone', 'Everybody in this company'),
    ('department', 'Certain parts of the business'),
    ('job', 'People doing certain jobs'),
    ('country', 'Every company in this country'),
]
AUDIENCE_LABEL = dict(AUDIENCE_KINDS)

#: HOW OFTEN IT COMES ROUND. `none` is spelled out as "Just once" because a
#: picker whose first option is the word "none" is a picker written by a
#: programmer.
RECURRENCES = [
    ('none', 'Just once'),
    ('weekly', 'Every week'),
    ('monthly', 'Every month'),
    ('yearly', 'Every year'),
]
RECURRENCE_LABEL = dict(RECURRENCES)

#: The content of an announcement — the fields an approver is agreeing to and
#: the fields the edit window protects. Named once here because the write
#: guard, the revision stamp and the "what changed" chatter line all read it.
CONTENT_FIELDS = (
    'subject', 'body_html', 'poster_ids', 'template_id', 'audience_kind',
    'department_ids', 'job_ids', 'send_at', 'company_id', 'recurrence',
    'recur_until',
)


# ------------------------------------------------------------- the helpers
def leg(env, label, fn):
    """One piece of paperwork, inside its own SAVEPOINT (R131).

    A TRY/EXCEPT IS NOT ENOUGH WHEN THE THING THAT FAILED REACHED THE
    DATABASE. Postgres aborts the whole transaction on an error and catching
    the exception in Python does not revive it: every statement after it fails
    too, INCLUDING the write the paperwork was about. That is how a post ends
    up reading "Sent" on the board with not one email queued, and a cheerful
    warning in the log as the only trace.
    """
    try:
        with env.cr.savepoint():
            return fn()
    except Exception:                   # noqa: BLE001 — paperwork never fails
        _logger.warning('pb_hr_comm: %s failed', label, exc_info=True)
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


def counted(count, one, many):
    """"1 person" and "3 people", never "1 person(s)" (R46).

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


def when_words(when, now):
    """"In 3 hours", "tomorrow", "in 6 days" — the sentence, whole.

    THE WHOLE SENTENCE AND NEVER A FRAME WITH A NUMBER IN IT (R117): "%s hours"
    is ungrammatical for exactly one of its values, and a translator handed the
    frame and the number separately cannot fix a plural they were never given.
    Every outcome is written out.
    """
    if not when or not now:
        return ''
    seconds = (when - now).total_seconds()
    if seconds < 0:
        return 'Due now'
    minutes = int(seconds // 60)
    if minutes < 1:
        return 'In a minute'
    if minutes < 60:
        return 'In 1 minute' if minutes == 1 else 'In %s minutes' % minutes
    hours = int(minutes // 60)
    if hours < 24:
        return 'In 1 hour' if hours == 1 else 'In %s hours' % hours
    days = int(hours // 24)
    if days == 1:
        return 'Tomorrow'
    return 'In %s days' % days


def company_tz(env, company=None):
    """The zone a company works in, or the reader's if it has not said.

    Odoo keeps "when this company works" on its working calendar, which is
    also where the time zone lives — `res.company` has no zone of its own
    (checked, not assumed).
    """
    try:
        zone = (company or env.company).resource_calendar_id.tz or ''
    except Exception:                   # noqa: BLE001 — a company is optional
        zone = ''
    return zone or env.user.tz or 'UTC'


def company_dt(env, when, company=None):
    """A stored UTC moment as the wall clock of the company it belongs to.

    THE GRID AND THE DRAWER HAVE TO AGREE. A calendar that puts an
    announcement on Friday in the reader's zone and then tells them it goes
    out at a time in the company's is two answers to one question on one
    screen — and across a date line it is two different days.
    """
    if not when:
        return None
    try:
        import pytz
        return pytz.UTC.localize(when).astimezone(
            pytz.timezone(company_tz(env, company))).replace(tzinfo=None)
    except Exception:                   # noqa: BLE001 — a bad zone is not fatal
        return when


def company_words(env, when, company=None):
    """The same sentence, in the COMPANY's own working time.

    TWO DIFFERENT READERS NEED TWO DIFFERENT ANSWERS and pretending otherwise
    is how one screen disagrees with another. An EMAIL is read by one person,
    so it says the time in THEIR zone. A shared surface — the calendar drawer,
    the approval drawer, the announcement's own history — is read by several
    people in several countries about one moment that belongs to the company
    publishing it, so it says the company's own time and everybody sees the
    same sentence.

    Found live: the history said "goes out at 9:59 pm" (the responsible
    person's Sydney evening) directly above a panel saying "1:59 pm" (the
    reader's), about the same announcement.

    The company's zone is its working calendar's — which is where Odoo keeps
    "when this company works" — and it falls back to the reader's.
    """
    if not when:
        return ''
    return local_words(env, when, tz_name=company_tz(env, company))


def local_words(env, when, user=None, tz_name=None):
    """"Friday 18 September at 5:00 pm" — in the READER's own time.

    FOUND LIVE, AND IT IS THE DEFECT THIS HELPER EXISTS FOR. A datetime is
    stored in UTC and printed by `fields.Datetime.to_string` in UTC, so a
    reminder to a Vietnamese reader about an announcement going out at five in
    the afternoon said "2026-09-18 10:57:24" — which is the right moment
    written in the wrong time zone and in a shape nobody says out loud. Seven
    hours is enough to be a different working day.

    So every sentence a person reads about WHEN something happens goes through
    here: the reminder email, the refusal when the window has closed, the
    history lines, and the drawer. The screens that draw a grid already do
    their own conversion (`context_timestamp`), which is the same trip made
    for a different purpose.
    """
    if not when:
        return ''
    reader = user or env.user
    zone = tz_name or ((reader.tz or env.user.tz or 'UTC') if reader
                       else 'UTC')
    try:
        import pytz
        local = pytz.UTC.localize(when).astimezone(pytz.timezone(zone))
    except Exception:                   # noqa: BLE001 — a bad tz is not fatal
        local = when
    hour = local.hour % 12 or 12
    part = 'am' if local.hour < 12 else 'pm'
    return '%s %s %s at %s:%02d %s' % (
        local.strftime('%A'), local.day, local.strftime('%B'), hour,
        local.minute, part)


def date_words(day):
    """"26 September 2026" — a day a person reads, never `2026-09-26`.

    An ISO date is unambiguous and is the right thing in a column; inside a
    sentence it is a machine talking, and on a screen beside `d MMM y` dates it
    is a second date format on one page (R108).
    """
    if not day:
        return ''
    return '%s %s %s' % (day.day, day.strftime('%B'), day.year)


def day_label(day):
    """"14 September" — the day and the month, and never a year.

    The one place a year matters is a work anniversary, and that number comes
    from the celebration engine's own window rather than from a date.
    """
    if not day:
        return ''
    return '%s %s' % (day.day, day.strftime('%B'))
