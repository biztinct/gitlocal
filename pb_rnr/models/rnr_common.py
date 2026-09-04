# -*- coding: utf-8 -*-
"""Shared vocabulary for pb_rnr — groups, switches, labels, small helpers.

One file, so the facade, the models, the two crons, the digest and the portal
controller read the SAME constant rather than five spellings of it (the reason
`comp_common` and `pip_common` exist).

THE WORDS ON SCREEN ARE HERE TOO. "Praise", "value", "story", "winner". Never
"nomination record", "chain state", "config parameter" — the screens this module
ships are read by everybody in the company, not by an administrator.
"""

import logging
import unicodedata

from odoo import _

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- the ladder
#: Recognition is not payroll and it is not the lifecycle. It gets its own two
#: tiers, granted by name — the same call P6 and P7 made, for the same reason:
#: praise carries opinions about people, and "they can already see the joining
#: checklist" is not a reason to hand those over.
GROUP_USER = 'pb_rnr.group_rnr_user'
GROUP_MANAGER = 'pb_rnr.group_rnr_manager'

# ---------------------------------------------------------------- the dials
#: Every switch defaults IN CODE. A `noupdate="1"` record for a switch freezes
#: whatever a test run left behind, because the next upgrade never corrects it.
P_DIGEST_MAIL = 'pb_rnr.digest_mail'          # send the monthly mood board
P_DIGEST_TEST = 'pb_rnr.digest_test_email'    # send it to ONE address instead
P_DIGEST_STAMP = 'pb_rnr.digest_last_month'   # the month already sent
P_ANNIV_MAIL = 'pb_rnr.anniv_mail'            # congratulate the person
P_MANAGER_MAIL = 'pb_rnr.manager_mail'        # the Monday heads-up to managers
P_THANKS_MAIL = 'pb_rnr.thanks_mail'          # tell the nominee they were praised
P_HR_ALERT_MAIL = 'pb_rnr.hr_alert_mail'      # tell HR a nomination arrived
P_HR_ALERT_TO = 'pb_rnr.hr_alert_email'       # where that alert goes
P_EMPLOYEE_VIEW = 'pb_rnr.employee_view'      # /my/recognition
P_AWARD_KIND = 'pb_rnr.award_kind'            # which kind of award a prize is

#: Defaults. EVERY SWITCH THAT SENDS SHIPS OFF. The first night after an install
#: must not email four and a half thousand people about a demo (R54: a switch
#: that is off and does not say so is reported as broken, so every screen and
#: every job that depends on one says which way it is set, with the number it
#: would have sent).
DEFAULTS = {
    P_DIGEST_MAIL: '0',
    P_DIGEST_TEST: '',
    P_DIGEST_STAMP: '',
    P_ANNIV_MAIL: '0',
    P_MANAGER_MAIL: '0',
    P_THANKS_MAIL: '0',
    P_HR_ALERT_MAIL: '0',
    P_HR_ALERT_TO: '',
    P_EMPLOYEE_VIEW: '1',
    P_AWARD_KIND: 'spot',
}

#: A ceiling on one job's mail burst. Past it the messages are skipped and
#: REPORTED rather than queued — 200 messages is a notification, 4,500 is an
#: incident, and the difference has to be a number somebody chose
#: (`publish_notify`'s `_MAIL_CAP`, same value, same reason).
MAIL_CAP = 200


def param(env, key):
    """The raw string of a switch, with this module's default behind it."""
    val = env['ir.config_parameter'].sudo().get_param(key, DEFAULTS.get(key, ''))
    return '' if val is False else str(val)


def flag(env, key):
    """A switch as a boolean. '0', '', 'false' and 'no' are all off."""
    return param(env, key).strip().lower() not in ('', '0', 'false', 'no', 'off')


def set_param(env, key, value):
    env['ir.config_parameter'].sudo().set_param(key, value)


# ------------------------------------------------------------------- states
#: THE LADDER. Two hands before praise is public: the person's own manager, who
#: knows whether the story is true, and then HR, who decides whether it is
#: recognised, paid for, or neither.
NOMINATION_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'With their manager'),
    ('manager', 'With HR'),
    ('done', 'Decided'),
    ('refused', 'Not this time'),
]
NOMINATION_STATE_LABEL = dict(NOMINATION_STATES)

#: WHAT WAS DECIDED. Deliberately a second column and not more states on the
#: chain: the chain answers "how far did it get", this answers "what came of
#: it", and one field trying to say both is how a board ends up unable to show
#: praise that was agreed but not paid for.
OUTCOMES = [
    ('recognised', 'Recognised'),
    ('awarded', 'Cash awarded'),
    ('declined', 'Not this time'),
]
OUTCOME_LABEL = dict(OUTCOMES)

#: The outcomes that may be seen by somebody who is not HR and not the writer.
PUBLIC_OUTCOMES = ('recognised', 'awarded')

CYCLE_STATES = [
    ('open', 'Collecting'),
    ('selecting', 'Choosing the winners'),
    ('closed', 'Closed'),
]
CYCLE_STATE_LABEL = dict(CYCLE_STATES)

CELEBRATION_KINDS = [
    ('birthday', 'Birthday'),
    ('anniversary', 'Work anniversary'),
    ('manager_week', "A manager's week ahead"),
]

#: Token names a value may be painted in. NOT hex: a value that carries a colour
#: the token sheet does not know would be a hard-coded colour in the database,
#: and the whole palette would then have two owners.
VALUE_COLORS = [
    ('primary', 'Indigo'),
    ('cyan', 'Teal'),
    ('green', 'Green'),
    ('amber', 'Amber'),
    ('rose', 'Rose'),
    ('slate', 'Slate'),
]
VALUE_COLOR_KEYS = [k for k, _lbl in VALUE_COLORS]

#: THE SAME COLOURS, AS LITERALS, FOR EMAIL ONLY.
#: An email has no stylesheet and no custom properties — every colour in one is
#: an inline hex or it is nothing. These are the pbim token values written out
#: once, here, so a mail body never invents a colour of its own. On screen the
#: token is always used and this map is never touched.
VALUE_HEX = {
    'primary': ('#6355C7', '#F1EFFC'),
    'cyan': ('#0E7490', '#E6F6FA'),
    'green': ('#15803D', '#E9F7EE'),
    'amber': ('#B45309', '#FDF3E3'),
    'rose': ('#BE123C', '#FCEDF1'),
    'slate': ('#475569', '#EEF1F5'),
}


def value_hex(color):
    """(ink, background) for a value's colour, in an email."""
    return VALUE_HEX.get(color or 'primary', VALUE_HEX['primary'])


# ------------------------------------------------------------------ helpers
def counted(n, one, many):
    """"1 story" / "3 stories" — never "3 story(s)" (R46)."""
    return '%s %s' % (n, one if n == 1 else many)


def initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    if not parts:
        return '?'
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()


MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']


def day_label(day, with_year=False):
    """"14 September" — a day somebody can picture, never "2026-09-14".

    Written out rather than passed through `format_date` so the answer is the
    same on the page, in the email and in the sentence beside them.
    """
    if not day:
        return ''
    out = '%s %s' % (day.day, MONTHS[day.month - 1])
    return '%s %s' % (out, day.year) if with_year else out


def excerpt(text, limit=180):
    """A story, shortened for a card, cut at a word and never mid-word."""
    raw = ' '.join((text or '').split())
    if len(raw) <= limit:
        return raw
    cut = raw[:limit].rsplit(' ', 1)[0]
    return '%s…' % cut


def fold(text):
    """Accent-folded lowercase, for a search that a Vietnamese name survives.

    NFKD plus a hand map for `đ`, which carries no combining mark and so
    survives an NFKD pass untouched (R28 — worth doing the same way everywhere).
    """
    raw = (text or '').replace('đ', 'd').replace('Đ', 'D')
    return ''.join(c for c in unicodedata.normalize('NFKD', raw)
                   if not unicodedata.combining(c)).lower()


def greeting_name(name):
    """What to call somebody at the top of an email. The last word of a
    Vietnamese name is the given name; for a Western name it is the surname, so
    the whole name is safer than a guess that is wrong half the time."""
    return (name or '').strip() or _('there')
