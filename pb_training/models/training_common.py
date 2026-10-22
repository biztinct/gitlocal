# -*- coding: utf-8 -*-
"""The words, the dials and the handful of helpers every file here needs.

WHY A COMMON FILE AT ALL. Two facades, a portal controller, a gate on somebody
else's controller and a white-label hook all need the same three things: the
group names, the switches with their defaults, and the two helpers that stop a
sentence reading like a machine wrote it. Copied around they drift, and a
plural that says "1 lesson(s)" in one place and "1 lesson" in another is worse
than either on its own (R46).
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the tiers
GROUP_USER = 'pb_training.group_training_user'
GROUP_MANAGER = 'pb_training.group_training_manager'
GROUP_ADMIN = 'pb_training.group_training_admin'
ALL_GROUPS = (GROUP_USER, GROUP_MANAGER, GROUP_ADMIN)

# --------------------------------------------------------------- the dials
#: EVERY SWITCH DEFAULTS IN CODE, and the `post_init_hook` merely materialises
#: the row so an administrator can see and edit it. A `noupdate="1"` record for
#: a switch freezes whatever value a test run happened to leave behind, because
#: the next upgrade never corrects it — which is why P3-P5 and A1 all kept
#: their switches out of the data file. Everything below still reads through
#: `flag()`/`number()`, so a database with no row at all behaves identically.
P_STOCK_PAGES = 'pb_training.stock_pages_internal_only'
P_COMPLETION_MAIL = 'pb_training.completion_mail'
P_UNENROL_ON_FAIL = 'pb_training.unenrol_on_failed_test'
P_PEOPLE_LIMIT = 'pb_training.people_limit'
P_COURSE_LIMIT = 'pb_training.course_limit'

# ------------------------------------------------------------------ E2 dials
P_REMINDERS = 'pb_training.reminders'
P_DAY1_AUTO = 'pb_training.day1_auto'
P_MANAGER_DAYS = 'pb_training.manager_escalate_days'
P_HR_DAYS = 'pb_training.hr_escalate_days'
P_DEFAULT_DUE = 'pb_training.default_due_days'
P_REMINDER_CAP = 'pb_training.reminder_cap'
P_ASSIGN_LIMIT = 'pb_training.assignment_limit'
P_BULK_CAP = 'pb_training.bulk_assign_cap'

# ------------------------------------------------------------------ E3 dials
P_CLAIM_OVER = 'pb_training.claim_over_allowance'
P_CLAIM_LIMIT = 'pb_training.claim_limit'
P_PACK = 'pb_training.report_pack'
P_PACK_PERIOD = 'pb_training.report_pack_period'
#: DELIBERATELY NOT IN `DEFAULTS`. `set_param(key, '')` DELETES the row on this
#: build, so an empty-string default cannot be materialised and a hook that
#: tried would write it, find it missing on the next read and write it again
#: for ever. Both are read through `text()`, which falls back in code; the
#: address is typed by whoever wants the pack and the stamp is written by the
#: job itself.
P_PACK_EMAIL = 'pb_training.report_pack_email'
P_PACK_STAMP = 'pb_training.report_pack_last'

# ------------------------------------------------------- LEARNING L1 dials
P_RENEW_BEFORE = 'pb_training.renew_before_days'
P_CERT_REMINDERS = 'pb_training.cert_reminders'
P_CERT_MANAGER_DAYS = 'pb_training.cert_manager_days'

# ------------------------------------------------------- LEARNING L2 dials
P_ENFORCE_CAP = 'pb_training.enforce_cap'
#: `pb_training.pack.<cc>.<company_id>` = '1' while a country pack is on for
#: that company ('0' once it has been switched off — never '', which deletes
#: the row on this build).
P_PACK_SWITCH = 'pb_training.pack.%s.%s'

# ------------------------------------------------------- LEARNING L5 dials
P_REREAD_CAP = 'pb_training.reread_cap'
P_FEEDBACK_ON = 'pb_training.feedback_on'
P_FOLLOWUP_ON = 'pb_training.followup_on'
P_FOLLOWUP_DAYS = 'pb_training.followup_days'

DEFAULTS = {
    # ON. The pages that came with the content engine are a PUBLIC WEB SITE
    # with a course catalogue, a member leaderboard and a public profile per
    # person. An employee's training is none of those things, and today
    # `/slides` answers 200 to anybody on the internet. Off, the stock pages
    # come back exactly as they were — which is what makes this a switch and
    # not a deletion.
    P_STOCK_PAGES: '1',
    # OFF. The content engine can send a "you finished the course" email per
    # course from a template nobody here has written. Until somebody has
    # written one, a silent finish is better than a branded one, so the
    # facade's "New course" door leaves that template empty while this is off.
    P_COMPLETION_MAIL: '0',
    # OFF. The test engine's own join takes somebody OFF the course when they
    # fail their last go and emails them a template nobody here has written
    # (see `survey_user_ext.py`). That is right for a company selling
    # certifications and wrong for a company training its staff: the course
    # vanishes off their page, taking the lessons they did finish with it.
    P_UNENROL_ON_FAIL: '0',
    # A cap that is right for a SCREEN is a bug in a JOB (R76). These two are
    # screen caps and they are dials rather than literals so a company with
    # five thousand people can widen the people picker without a deploy.
    P_PEOPLE_LIMIT: '40',
    P_COURSE_LIMIT: '200',
    # ON. The chasing is the whole point of an assignment: a due date nobody
    # is reminded of is a wish. It is a switch because a company mid-rollout
    # may not want the first night to write to four thousand people, and a
    # switch that is off SAYS so on the board (R54).
    P_REMINDERS: '1',
    # OFF until somebody points it at a real course. On, a new joiner's
    # checklist assigns the day-one courses by itself; off, the step settles
    # with a note saying what it WOULD have assigned, so the first night after
    # an install never emails anybody.
    P_DAY1_AUTO: '0',
    # How long a thing may be overdue before the chase widens. Two days to
    # their manager, five to the HR lead — both dials, because a company that
    # trains people monthly and one that trains them yearly do not mean the
    # same thing by "late".
    P_MANAGER_DAYS: '2',
    P_HR_DAYS: '5',
    # A fortnight is the default answer to "by when", and it is only a
    # default: every assignment carries its own date.
    P_DEFAULT_DUE: '14',
    # A CAP THAT IS RIGHT FOR A SCREEN IS A BUG IN A JOB (R76), so the job's
    # cap is its own dial and it is a safety rail rather than a page size: it
    # exists so a misconfigured schedule cannot mail the whole company twice.
    # The job logs honestly when it hits it.
    P_REMINDER_CAP: '400',
    # Screen caps.
    P_ASSIGN_LIMIT: '400',
    P_BULK_CAP: '200',
    # OFF. A training allowance is a budget, and a claim over it is a
    # conversation rather than a form. On, the HR lead may agree one anyway and
    # the claim carries a line saying they did — which is the honest version of
    # a rule people go round: the money still needs a name against it.
    P_CLAIM_OVER: '0',
    # A screen cap.
    P_CLAIM_LIMIT: '200',
    # OFF, and it ships off ON PURPOSE (R54). The pack is an email to an
    # address nobody has typed yet, so the first night after an install would
    # otherwise send a spreadsheet of the company's training figures to
    # whatever the fallback happened to be. Off, the job still runs, still
    # builds the numbers and LOGS what it would have sent.
    P_PACK: '0',
    # `weekly` or `monthly`. Monthly, because training is a slow number: a
    # week of it is mostly noise and a month of it is a picture.
    P_PACK_PERIOD: 'monthly',
    # LEARNING L1. How long before a certificate runs out the refresher course
    # is put on the person by itself, and the window a certificate counts as
    # "about to run out" in. Sixty days is two monthly cycles: long enough to
    # do a course, short enough that nobody forgets why they were put on it.
    P_RENEW_BEFORE: '60',
    # ON. The certificate ladder (60 / 30 / 7 days and the day itself to the
    # person, 14 days to their manager, the HR lead on the day). It still
    # only runs while `pb_training.reminders` is on — one master switch.
    P_CERT_REMINDERS: '1',
    # When the manager hears about a certificate running out.
    P_CERT_MANAGER_DAYS: '14',
    # LEARNING L2. The most courses the morning job puts on people in one
    # run because a required course is missing. A safety rail, not a page
    # size: a rule pointed at the wrong audience cannot enrol the whole
    # company in one night. The log says so when it bites.
    P_ENFORCE_CAP: '500',
    # LEARNING L5. How many people one "Publish a new version" press resets
    # and puts on a re-read; the rest are picked up by the morning job. A
    # safety rail: a course everybody finished cannot mail the company in
    # one press.
    P_REREAD_CAP: '500',
    # ON. Finishing a course asks the person two ratings and one line
    # ("Was it useful?", "Would you recommend it?", "What would you
    # change?"), once, by email and on their own page.
    P_FEEDBACK_ON: '1',
    # ON. A set number of days after somebody finishes a course their
    # manager is asked whether their work has changed. One question set,
    # one email.
    P_FOLLOWUP_ON: '1',
    P_FOLLOWUP_DAYS: '30',
}

# =========================================================================
#  E2 — what an assignment IS, in the words on the screen
# =========================================================================
#: WHY somebody was put on a course. It is not decoration: the reason decides
#: whether the trial period waits for it, whether the day-one rules made it,
#: and what the chasing email says.
ASSIGN_REASONS = [
    ('day_one', 'Day one'),
    ('probation', 'Trial period'),
    ('compliance', 'Compliance'),
    ('adhoc', 'One-off'),
    ('leadership', 'Leadership programme'),
    # LEARNING L1: put on by itself because a certificate is running out.
    ('renewal', 'Renewal'),
    # LEARNING L2: put on because a required-training rule says they must
    # hold it and they do not (or it is about to run out).
    ('required', 'Required'),
    # LEARNING L5: a course they had finished was published again as a new
    # version, and they are asked to read the changed parts.
    ('reread', 'Changed course'),
]
ASSIGN_REASON_LABEL = dict(ASSIGN_REASONS)

#: HOW FAR IT HAS GOT. Every one of these is written by the same method, so
#: the board, the employee's page and the nightly job can never disagree.
ASSIGN_STATES = [
    ('assigned', 'Not started'),
    ('in_progress', 'Under way'),
    ('overdue', 'Overdue'),
    ('excused', 'More time agreed'),
    ('done', 'Finished'),
]
ASSIGN_STATE_LABEL = dict(ASSIGN_STATES)

#: The states that still need doing. An assignment leaves this set exactly
#: once, when the course is finished — which is what makes "one open
#: assignment per person per course" a rule somebody can understand.
ASSIGN_OPEN = ('assigned', 'in_progress', 'overdue', 'excused')

#: Why somebody is asking for more time. Three answers and an "anything else",
#: because a list that cannot say "something else" is a list people lie to.
DELAY_KINDS = [
    ('sick', 'I have been off sick'),
    ('emergency', 'A family or personal emergency'),
    ('other', 'Something else'),
]
DELAY_KIND_LABEL = dict(DELAY_KINDS)

DELAY_STATES = [
    ('draft', 'Not sent yet'),
    ('submitted', 'Waiting on their manager'),
    ('approved', 'More time agreed'),
    ('refused', 'Turned down'),
]
DELAY_STATE_LABEL = dict(DELAY_STATES)

# =========================================================================
#  E3 — a training cost somebody paid, and the money coming back
# =========================================================================
#: HOW FAR THE ASKING HAS GOT. This is the APPROVAL ladder and nothing else —
#: the chain drives it and `biz.approval.chain.mixin` refuses a bare write to
#: it, which is what stops a "mark it agreed" button ever appearing by
#: accident. Whether the money has actually moved is a SECOND column
#: (`fulfilment`), exactly as `pb.incentive` keeps them apart: one field trying
#: to say both is how a screen ends up unable to show an agreed claim that
#: nobody has paid, which is the single most useful row on it.
CLAIM_STATES = [
    ('draft', 'Not sent yet'),
    ('submitted', 'Waiting on the HR lead'),
    ('approved', 'Agreed'),
    ('refused', 'Turned down'),
]
CLAIM_STATE_LABEL = dict(CLAIM_STATES)

#: WHERE THE MONEY HAS GOT TO. Mirrors the award's own column, because it IS
#: the award's own column — a claim that has been agreed becomes an award, and
#: this follows it rather than guessing.
CLAIM_FULFILMENT = [
    ('pending', 'Agreed, waiting for a pay run'),
    ('queued', 'In a pay run'),
    ('paid', 'Paid'),
]
CLAIM_FULFILMENT_LABEL = dict(CLAIM_FULFILMENT)

#: The kind of award a training claim becomes. Added to `pb.incentive.kind` by
#: `incentive_ext.py` so the ONE money door (`pb.oneoff.feed`) carries it with
#: no new code of its own — a reimbursement is a one-off amount somebody
#: agreed to pay, which is precisely what that table is.
INCENTIVE_KIND_TRAINING = 'training'

#: How the pack comes round.
PACK_PERIODS = [
    ('weekly', 'Every week'),
    ('monthly', 'Every month'),
]

#: Who a compliance schedule is for.
SCHEDULE_AUDIENCES = [
    ('company', 'Everybody in one company'),
    ('department', 'One part of the business'),
    ('job', 'Everybody doing one job'),
    ('everyone', 'Everybody, in every company'),
]

# =========================================================================
#  LEARNING L5 — outside courses, course requests, follow-ups
# =========================================================================
#: What kind of outside course it is, in the words on the card.
OUTSIDE_KINDS = [
    ('online', 'Online'),
    ('classroom', 'In a classroom'),
    ('exam', 'An exam or licence'),
]
OUTSIDE_KIND_LABEL = dict(OUTSIDE_KINDS)

#: What somebody is asking to take: one of our courses, one from the outside
#: list, or something they found themselves (free text and a link).
REQUEST_KINDS = [
    ('ours', 'One of our courses'),
    ('outside', 'An outside course'),
    ('other', 'Something else'),
]
REQUEST_KIND_LABEL = dict(REQUEST_KINDS)

#: HOW FAR A COURSE REQUEST HAS GOT. `submitted → approved / refused` is the
#: route's; `taken`, `claimed` and `cancelled` are the request's own.
REQUEST_STATES = [
    ('draft', 'Not sent yet'),
    ('submitted', 'Waiting for a decision'),
    ('approved', 'Agreed'),
    ('refused', 'Turned down'),
    ('taken', 'Taken'),
    ('claimed', 'Claimed back'),
    ('cancelled', 'Cancelled'),
]
REQUEST_STATE_LABEL = dict(REQUEST_STATES)
REQUEST_OPEN = ('draft', 'submitted', 'approved')

#: The manager's 30-day question set.
FOLLOWUP_STATES = [
    ('planned', 'Planned'),
    ('sent', 'Waiting on the manager'),
    ('answered', 'Answered'),
    ('skipped', 'Skipped'),
]
FOLLOWUP_STATE_LABEL = dict(FOLLOWUP_STATES)

#: The most days a delay request may ask for in one go. Longer than this and
#: the honest answer is a new due date typed by the training team, not an
#: extension nobody can read the end of.
DELAY_MAX_DAYS = 90

# ------------------------------------------------------------- the choices
#: What a lesson IS, in the words on the screen. The stored values are the
#: content engine's own `slide_category`; only the words are ours.
LESSON_KINDS = {
    'video': 'Video',
    'document': 'Document',
    'article': 'Reading',
    'infographic': 'Picture',
    'quiz': 'Quick questions',
    'certification': 'Test',
}

#: The icon each kind is drawn with, from the shared `ic()` registry.
LESSON_ICONS = {
    'video': 'play',
    'document': 'fileText',
    'article': 'bookOpen',
    'infographic': 'eye',
    'quiz': 'checkCheck',
    'certification': 'graduationCap',
}

#: THE ONE CATEGORY THAT IS NOT A LESSON. A certification slide is the test at
#: the end; counting it among the lessons would mean the test unlocks only
#: after the test has been passed.
TEST_CATEGORY = 'certification'

#: Where the test stands, for the chip on a course tile.
TEST_LOCKED = 'locked'
TEST_READY = 'ready'
TEST_PASSED = 'passed'
TEST_FAILED = 'failed'
TEST_NONE = 'none'


# ------------------------------------------------------------- the helpers
def leg(env, label, fn):
    """One piece of paperwork, inside its own SAVEPOINT (R131).

    A try/except IS NOT ENOUGH when the thing that failed reached the
    database: Postgres aborts the whole transaction and every statement after
    it fails too, including the write the paperwork was about.
    """
    try:
        with env.cr.savepoint():
            return fn()
    except Exception:                   # noqa: BLE001 — paperwork never fails
        _logger.warning('pb_training: %s failed', label, exc_info=True)
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


def money_words(env, amount, currency=None):
    """An amount as PLAIN TEXT — "5,000,000 ₫" — never as markup.

    `ir.qweb.field.monetary.value_to_html` answers a `<span>` (R137), which is
    right inside a rendered report and is the report's own source code the
    moment it lands in a sentence a board prints with `t-esc`. `formatLang`
    answers the same number as text.
    """
    try:
        from odoo.tools.misc import formatLang
        return formatLang(env, float(amount or 0.0),
                          currency_obj=currency or env.company.currency_id)
    except Exception:                       # noqa: BLE001 — a sentence is safe
        return '%s' % (amount or 0)


def text(env, key, default=''):
    """A switch whose value is WORDS, not a number and not a yes/no.

    `set_param(key, '')` deletes the row on this build, so a key whose honest
    default is "nothing has been typed here yet" cannot live in `DEFAULTS` and
    has to fall back in code. Read through here so every caller falls back the
    same way.
    """
    raw = env['ir.config_parameter'].sudo().get_param(key, default)
    return (str(raw) if raw else str(default or '')).strip()


def counted(count, one, many):
    """"1 lesson" and "3 lessons", never "1 lesson(s)" (R46).

    Both words are passed in whole so a translator gets a sentence rather than
    a frame with a hole in it (R117).
    """
    return one if count == 1 else many


def fold(text):
    """Accent-blind text for a search box.

    Postgres on this build has no `unaccent` extension (R78) and most people
    on this database have an accent in their name, so the folding happens in
    Python. `đ` carries no combining mark, so NFKD leaves it and it is mapped
    by hand (R28).
    """
    if not text:
        return ''
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(ch for ch in out if not unicodedata.combining(ch))
    return out.replace('đ', 'd').replace('Đ', 'D').lower()


def as_id(value):
    """A record argument arrives over the wire as a plain integer (R43).

    Every public method that takes "a record" coerces at the door, so an RPC
    caller and an in-process caller reach the same code.
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


def minutes(hours):
    """The content engine keeps a duration in HOURS, as a float.

    Nobody says "0.25 hours" out loud, and a screen that prints it is a screen
    written by a programme. Rounded to the nearest minute, and zero is an
    absence rather than a duration — a lesson nobody has timed says nothing at
    all rather than "0 min".
    """
    try:
        mins = int(round(float(hours or 0.0) * 60))
    except (TypeError, ValueError):
        return 0
    return max(mins, 0)


def tr(env, source, *args):
    """A constant sentence in the reader's language (LEARNING L1, ledger LN10).

    The words below used to be English constants. `env._()` reads the
    language off the environment it is given and the module off the caller,
    so the board, the portal pages and My learning say them in Vietnamese to
    a Vietnamese reader. With no environment — the mail templates' own
    computes, which render one whole English body — the English stands, so an
    email is never half one language and half the other.

    The `.po` carries every source below as an `odoo-python` entry against
    this file; a word that is not there simply stays English.
    """
    if env is None:
        return source % args if args else source
    try:
        return env._(source, *args)
    except Exception:                       # noqa: BLE001 — a word is not fatal
        return source % args if args else source


def reason_word(env, key):
    """Why somebody was put on a course, in the reader's language."""
    label = ASSIGN_REASON_LABEL.get(key or '', '')
    return tr(env, label) if label else ''


def state_word(env, key):
    """How far an assignment has got, in the reader's language."""
    label = ASSIGN_STATE_LABEL.get(key or '', '')
    return tr(env, label) if label else ''


def reason_choices(env):
    return [{'key': k, 'label': tr(env, v)} for k, v in ASSIGN_REASONS]


def state_choices(env):
    return [{'key': k, 'label': tr(env, v)} for k, v in ASSIGN_STATES]


def duration_words(mins, env=None):
    """"12 min", "1 hr", "1 hr 20 min" — and '' for a lesson nobody timed."""
    if not mins:
        return ''
    if mins < 60:
        return tr(env, '%s min', mins)
    hrs, rest = divmod(mins, 60)
    if not rest:
        return tr(env, '%s hr', hrs)
    return tr(env, '%s hr %s min', hrs, rest)


def due_words(due, today, env=None):
    """"Due today", "3 days left", "8 days overdue" — the sentence, whole.

    THE WHOLE SENTENCE AND NEVER A FRAME WITH A NUMBER IN IT (R117): "%s days
    left" is ungrammatical for exactly one of its values, and a translator
    handed the frame and the number separately cannot fix a plural they were
    never given. There are five outcomes here and each one is written out.
    """
    if not due:
        return ''
    days = (due - today).days
    if days == 0:
        return tr(env, 'Due today')
    if days == 1:
        return tr(env, '1 day left')
    if days > 1:
        return tr(env, '%s days left', days)
    if days == -1:
        return tr(env, '1 day overdue')
    return tr(env, '%s days overdue', -days)


def days_over(due, today):
    """How many days late, or 0 for something that is not late yet."""
    if not due:
        return 0
    return max((today - due).days, 0)
