# -*- coding: utf-8 -*-
"""The words, the dials and the two helpers every file here needs.

WHY A COMMON FILE AT ALL. Six models, a facade, a portal controller and a
daily job all need the same three things: the group names, the switches with
their defaults, and the two helpers that stop a sentence reading like a
machine wrote it. Copied around they drift; a plural that says "1 role(s)"
in one place and "1 role" in another is worse than either on its own (R46).
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the tiers
GROUP_USER = 'pb_hiring.group_hiring_user'
GROUP_MANAGER = 'pb_hiring.group_hiring_manager'
GROUP_ADMIN = 'pb_hiring.group_hiring_admin'
ALL_GROUPS = (GROUP_USER, GROUP_MANAGER, GROUP_ADMIN)

# --------------------------------------------------------------- the dials
#: Every switch defaults IN CODE. A `noupdate="1"` record for a switch freezes
#: whatever value a test run happened to leave behind, because the next
#: upgrade never corrects it (the reason P3-P5 all kept their switches out of
#: the data file). The data file ships only the NUMBERS, which are dials
#: somebody tunes rather than switches somebody flips.
P_PLATFORM_MAIL = 'pb_hiring.platform_mail'
P_REFERRAL_AUTO = 'pb_hiring.referral_auto'
P_NOTIFY_MAIL = 'pb_hiring.notify_mail'
P_REFERRAL_MAIL = 'pb_hiring.referral_mail'
P_JD_REMINDER_DAYS = 'pb_hiring.jd_reminder_days'
P_RECRUITER_NUDGE_DAYS = 'pb_hiring.recruiter_nudge_days'

DEFAULTS = {
    # OFF. An advert that leaves the building the first time somebody presses
    # a button is an advert nobody agreed to send. The pack is built either
    # way and a human pushes it.
    P_PLATFORM_MAIL: '0',
    P_REFERRAL_AUTO: '1',
    P_NOTIFY_MAIL: '1',
    P_REFERRAL_MAIL: '1',
    P_JD_REMINDER_DAYS: '3',
    P_RECRUITER_NUDGE_DAYS: '3',
}

# ------------------------------------------------------------- the choices
ROLE_TYPES = [
    ('new_role', 'A role that did not exist before'),
    ('growth', 'One more of a role we already have'),
    ('replacement', 'Replacing somebody who has left'),
    ('sensitive_replacement', 'Replacing somebody quietly'),
]

#: The one role type that must never open itself to referrals: the person
#: being replaced is usually still at their desk.
SENSITIVE_TYPES = ('sensitive_replacement',)

REQUISITION_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Sent in'),
    ('manager_ok', 'Manager agreed'),
    ('hr_ok', 'HR agreed'),
    ('open', 'Open for candidates'),
    ('filled', 'Filled'),
    ('closed', 'Closed'),
    ('refused', 'Not approved'),
]

#: The statuses after which nothing is still being asked for.
REQUISITION_LIVE = ('draft', 'submitted', 'manager_ok', 'hr_ok', 'open')

BUDGET_STATUS = [
    ('unknown', 'No budget set'),
    ('within', 'Within budget'),
    ('over', 'Over budget'),
]

JD_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Sent for agreement'),
    ('approved', 'Agreed'),
    ('refused', 'Not agreed'),
]

STEP_KINDS = [
    ('screen', 'A first look at the CV'),
    ('call', 'A phone call'),
    ('interview', 'An interview'),
    ('test', 'A test or an exercise'),
    ('panel', 'A panel'),
    ('final', 'The final conversation'),
    ('other', 'Something else'),
]

REFERRAL_STATES = [
    ('received', 'Received'),
    ('in_progress', 'Being looked at'),
    ('hired', 'Joined us'),
    ('not_this_time', 'Not this time'),
]

POSTING_STATES = [
    ('ready', 'Ready to send'),
    ('sent', 'Sent'),
]

SCREEN_TAGS = [
    ('shortlisted', 'Shortlisted'),
    ('rejected', 'Not this time'),
    ('future_fit', 'Worth keeping in touch with'),
    ('other_role', 'Better suited to another role'),
]


# ------------------------------------------------------------- the helpers
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
    """"1 role" and "3 roles", never "1 role(s)" (R46).

    Both words are passed in whole so a translator gets a sentence rather
    than a frame with a hole in it (R117).
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


def excerpt(text, limit=240):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + '…'
