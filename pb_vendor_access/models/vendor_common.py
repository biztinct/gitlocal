# -*- coding: utf-8 -*-
"""The words, the caps, the switches and the small helpers this module shares.

One module, one vocabulary. A vendor TYPE is spelled the same on the model, on
the board, in the spreadsheet and in the mail, because three spellings of one
idea is how a filter quietly matches nothing (R27/R80).

Two rules from the ledger are wired in here rather than repeated in six files:

  * **R76 — a cap that is right for a SCREEN is a bug in a CRON.** Every cap
    below is a DEFAULT, every reader takes it as a PARAMETER, and the jobs pass
    `None`.
  * **R92 — a swallowed exception logged at DEBUG is invisible on a live
    server.** `safe()` returns its default and says so at WARNING with the
    traceback.
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ the words
#: What kind of outside party this is. The blueprint's list, verbatim.
VENDOR_TYPES = [
    ('recruitment', 'Recruitment'),
    ('learning', 'Learning & training'),
    ('assessment', 'Assessments & tests'),
    ('benefits', 'Benefits & insurance'),
    ('it', 'IT & software'),
    ('services', 'Services'),
    ('committee', 'Committee / statutory'),
    ('other', 'Other'),
]
VENDOR_TYPE_KEYS = tuple(k for k, _l in VENDOR_TYPES)

#: Where an agreement is in its life. Computed from the dates and the renewal
#: flag — never typed, so it can never disagree with the calendar.
AGREEMENT_STATES = [
    ('draft', 'Not started'),
    ('running', 'Running'),
    ('expiring', 'Ending soon'),
    ('expired', 'Ended'),
    ('renewed', 'Replaced by a newer one'),
]

#: The areas a role profile can belong to. They are the words on the rail, not
#: the names of modules.
PROFILE_AREAS = [
    ('payroll', 'Payroll'),
    ('people', 'People'),
    ('lifecycle', 'Lifecycle'),
    ('money', 'Money & budgets'),
    ('system', 'System'),
]

DELEGATION_KINDS = [
    ('temporary', 'For a while'),
    ('permanent', 'For good'),
]

DELEGATION_STATES = [
    ('draft', 'Draft'),
    ('active', 'Active'),
    ('expired', 'Ended'),
    ('revoked', 'Taken back'),
]

# =============================================================================
# THE ABSOLUTE. Nothing in this module may ever put anybody into one of these.
#
# `base.group_system` and `base.group_erp_manager` are the keys to the whole
# database — the settings screens, every model's ACL, the ability to install
# code. A "temporary hand-over" of one of those is not a hand-over, it is a
# permanent change of who owns the system, and a screen that makes it a
# two-click action is a screen that will eventually be used for that.
#
# Belt AND braces, exactly as the handover asks: the seeded catalogue does not
# contain them, `pb.role.profile` refuses to be created or written pointing at
# one, and both facades check again before they apply anything.
# =============================================================================
FORBIDDEN_GROUP_XMLIDS = (
    'base.group_system',
    'base.group_erp_manager',
)

# ------------------------------------------------------------------- the caps
VENDOR_ROW_CAP = 800
AGREEMENT_ROW_CAP = 2000
DELEGATION_ROW_CAP = 500
#: Holders shown per profile on the roles board. A profile held by four
#: thousand people is a fact, not a list, and the board says the number.
HOLDER_CAP = 40
PICKER_CAP = 20

# --------------------------------------------------------------- the switches
#: Defaults live in CODE, never in a `noupdate="1"` record — a shipped record
#: freezes whatever value a test run left behind, because the next upgrade
#: never corrects it (the call P3-P10 all made).
DEFAULTS = {
    #: How many days before an agreement ends we start saying so.
    'pb_vendor_access.renewal_horizon_days': '45',
    #: Are the nightly agreement mails switched on? Shipped ON: unlike a job
    #: that opens a review on somebody, this one only ever tells the person who
    #: already owns the contract that it is about to run out (R54's shape, the
    #: gentler side of it).
    'pb_vendor_access.alerts_enabled': '1',
    #: Are the delegation mails switched on?
    'pb_vendor_access.delegation_mail': '1',
    #: How many mails one run of a job may send. A burst cap, not a filter:
    #: whatever is left is reported and picked up on the next run.
    'pb_vendor_access.mail_burst': '80',
}


def param(env, key, default=None):
    """A config parameter, with this module's own default behind it."""
    raw = env['ir.config_parameter'].sudo().get_param(key)
    if raw in (None, False, ''):
        raw = DEFAULTS.get(key, default)
    return raw


def param_int(env, key, default=0):
    try:
        return int(str(param(env, key, default)).strip())
    except (TypeError, ValueError):
        return default


def flag(env, key):
    return str(param(env, key, '0')).strip().lower() in ('1', 'true', 'yes', 'on')


def counted(n, one, many):
    """"1 agreement" / "4 agreements" — never "1 agreement(s)" (R46)."""
    return one if n == 1 else many % n


def fold(text):
    """Accents folded, never stripped (R28/R78).

    Postgres on this box has no `unaccent` extension and most of the people on
    this tenant carry an accent in their name, so every match this module makes
    on a name is made in Python over folded text.
    """
    if not text:
        return ''
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(c for c in out if not unicodedata.combining(c))
    # Vietnamese `đ` carries no combining mark, so NFKD leaves it alone.
    out = out.replace('đ', 'd').replace('Đ', 'D')
    return out.strip().lower()


def type_label(key, env=None):
    """The word for a vendor type, translated where there is an env to ask.

    Module-level `_()` has no language to work in and logs "no translation
    language detected" on every call, so the environment is passed rather than
    assumed — `env._()` is Odoo 19's own form for exactly this.
    """
    for k, lbl in VENDOR_TYPES:
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''


def state_label(key, env=None):
    for k, lbl in AGREEMENT_STATES:
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''


def area_label(key, env=None):
    for k, lbl in PROFILE_AREAS:
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''


def safe(fn, default=None, what='a piece of this screen'):
    """Every independent probe gets its OWN try/except — never a shared one.

    And it says so at WARNING with the traceback (R92): a swallowed failure
    logged at DEBUG is invisible on a live server, which is how a job that half
    worked came to report a cheerful small number.
    """
    try:
        return fn()
    except Exception:                           # noqa: BLE001
        _logger.warning('pb_vendor_access: %s could not be read', what,
                        exc_info=True)
        return default


def forbidden_group_ids(env):
    """The ids of the groups nothing here may ever hand out.

    Resolved by xmlid and tolerant of one being absent — a database without
    `base.group_erp_manager` is not a database where the refusal should stop
    working for the other one.
    """
    out = set()
    for xmlid in FORBIDDEN_GROUP_XMLIDS:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            out.add(rec.id)
    return out


def implied_closure(groups):
    """Every permission these permissions actually carry, themselves included.

    A group that IMPLIES the administrator permission hands over the same
    database as the administrator permission does, so every check in this module
    that used to look at one group now looks at the whole closure. On this build
    `res.groups.all_implied_ids` is that closure and it is REFLEXIVE — it
    contains the group itself — so the field answers the question directly. The
    hand walk below is there for a build where the field is not, because a rail
    that silently stops checking is worse than no rail.
    """
    if not groups:
        return groups
    groups = groups.sudo()
    if 'all_implied_ids' in groups._fields:
        try:
            return groups | groups.all_implied_ids
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb_vendor_access: all_implied_ids could not be read — '
                'walking implied_ids by hand instead', exc_info=True)
    seen = groups
    frontier = groups
    while frontier:
        frontier = frontier.implied_ids - seen
        seen |= frontier
    return seen


def forbidden_in_closure(groups, env):
    """The forbidden permissions these permissions reach, if any.

    Returns a `res.groups` recordset so the caller can name them in the refusal
    — "it would carry X" is a sentence somebody can act on, and "no" is not.
    """
    empty = env['res.groups'].browse()
    forbidden = forbidden_group_ids(env)
    if not forbidden or not groups:
        return empty
    try:
        return implied_closure(groups).filtered(lambda g: g.id in forbidden)
    except Exception:                           # noqa: BLE001
        # R92 — and this one is load-bearing: a check that cannot be made must
        # be reported, never treated as a pass.
        _logger.warning(
            'pb_vendor_access: the forbidden-permission check could not be '
            'made for %s', groups.ids, exc_info=True)
        return env['res.groups'].browse(
            [gid for gid in groups.ids if gid in forbidden])
