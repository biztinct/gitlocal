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
}

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


def duration_words(mins):
    """"12 min", "1 hr", "1 hr 20 min" — and '' for a lesson nobody timed."""
    if not mins:
        return ''
    if mins < 60:
        return '%s min' % mins
    hrs, rest = divmod(mins, 60)
    if not rest:
        return '%s hr' % hrs
    return '%s hr %s min' % (hrs, rest)
