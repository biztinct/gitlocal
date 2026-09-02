# -*- coding: utf-8 -*-
"""The words, the caps, the switches and the small helpers this module shares.

ONE MODULE, ONE VOCABULARY. An area is spelled the same on the model, on the
board and in the audit trail, because three spellings of one idea is how a
filter quietly matches nothing.

THIS FILE IS PRODUCT-NEUTRAL ON PURPOSE. Nothing here names a product, an
industry or a screen that belongs to one application. Everything an application
wants to add — the areas roles are grouped under, the permission groups that
count as "may manage access here" — arrives through a REGISTRATION CALL made by
the application's own module at import time. A registry rather than an import,
because the dependency only ever runs one way: the application knows about
access management, and access management knows nothing about the application.

Two rules carried over from the module this was extracted from:

  * **A cap that is right for a SCREEN is a bug in a CRON.** Every cap below is
    a DEFAULT, every reader takes it as a PARAMETER, and the jobs pass `None`.
  * **A swallowed exception logged at DEBUG is invisible on a live server.**
    `safe()` returns its default and says so at WARNING with the traceback.
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# =============================================================================
# THE AREAS ROLES ARE GROUPED UNDER — A REGISTRY, NOT A LIST.
#
# An area is a word from the application's own left menu ("Payroll", "Money &
# budgets"), so this module cannot know them and must not invent them. It ships
# ONE neutral area so that a database with nothing but this module installed has
# a working board rather than a Selection field with no options, and an
# application replaces that list wholesale by registering its own.
# =============================================================================
#: What a database with no application on top of it offers.
NEUTRAL_AREA = ('general', 'General')

_AREAS = []
_DEFAULT_AREA = None


def register_areas(pairs, default=None):
    """An application says which areas its roles are grouped under.

    Called at import time from the application's own module. The first
    registration REPLACES the neutral default rather than adding to it: an
    application that has said "Payroll, People, Money" does not also want a
    stray "General" on its board. Registering the same key twice keeps the first
    label, so two modules of one product cannot fight over a word.
    """
    global _DEFAULT_AREA
    seen = {key for key, _label in _AREAS}
    for key, label in pairs or ():
        if key not in seen:
            _AREAS.append((key, label))
            seen.add(key)
    if default and default in seen:
        _DEFAULT_AREA = default
    return list(_AREAS)


def profile_areas():
    """Every area a role or an ability may belong to, in registration order."""
    return list(_AREAS) if _AREAS else [NEUTRAL_AREA]


def default_area():
    """The one a new role starts in."""
    if _DEFAULT_AREA:
        return _DEFAULT_AREA
    return profile_areas()[0][0]


def area_label(key, env=None):
    """The word for an area, translated where there is an env to ask.

    Module-level `_()` has no language to work in and logs "no translation
    language detected" on every call, so the environment is passed rather than
    assumed — `env._()` is the framework's own form for exactly this.
    """
    for k, lbl in profile_areas():
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''


# =============================================================================
# WHO MAY MANAGE SOMEBODY ELSE'S ACCESS — ALSO A REGISTRY.
#
# This module ships its own "access team" permission and nothing else. An
# application whose own administrator tier should also be able to give and take
# roles registers that permission here; it is never hard-coded, because the next
# application will have a different one and a gate that drifts from the facade's
# produces a door that can only make an access dialog.
# =============================================================================
#: Who may open the board at all. Everybody with a login, because the "hand my
#: access over" half is for everybody by requirement — somebody going on leave
#: should not have to ask an administrator to arrange cover.
BOARD_GROUPS = ['base.group_user']

#: Who may grant and remove on somebody else's behalf.
MANAGE_GROUPS = ['biz_access.group_access_manager']


def register_manager_groups(*xmlids):
    """An application adds its own administrator tier to the manage gate."""
    for xmlid in xmlids:
        if xmlid and xmlid not in MANAGE_GROUPS:
            MANAGE_GROUPS.append(xmlid)
    return list(MANAGE_GROUPS)


def register_board_groups(*xmlids):
    """An application widens who may open the board at all. Rarely needed."""
    for xmlid in xmlids:
        if xmlid and xmlid not in BOARD_GROUPS:
            BOARD_GROUPS.append(xmlid)
    return list(BOARD_GROUPS)


# ------------------------------------------------------------------ the words
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
# Belt AND braces: no catalogue an application seeds may contain them (there is
# a test that walks the whole implied closure and fails if one is reachable),
# `pb.role.profile` and `pb.role.ability` refuse to be created or written
# pointing at one, and the facade checks again before it applies anything.
# =============================================================================
FORBIDDEN_GROUP_XMLIDS = (
    'base.group_system',
    'base.group_erp_manager',
)

# ------------------------------------------------------------------- the caps
DELEGATION_ROW_CAP = 500
#: Holders shown per profile on the roles board. A profile held by four
#: thousand people is a fact, not a list, and the board says the number.
HOLDER_CAP = 40
PICKER_CAP = 20
#: People listed in the People lens at once. A list of two hundred colleagues
#: is already longer than anybody scrolls; past it, the search box is the
#: answer, and the lens says so rather than truncating in silence.
PEOPLE_CAP = 200

# --------------------------------------------------------------- the switches
#: Defaults live in CODE, never in a `noupdate="1"` record — a shipped record
#: freezes whatever value a test run left behind, because the next upgrade
#: never corrects it.
DEFAULTS = {
    #: Are the hand-over mails switched on?
    'biz_access.delegation_mail': '1',
    #: How long a hand-over runs for when nobody says otherwise.
    'biz_access.default_window_days': '14',
}


def param(env, key, default=None, defaults=None):
    """A config parameter, with the calling module's own default behind it."""
    raw = env['ir.config_parameter'].sudo().get_param(key)
    if raw in (None, False, ''):
        raw = (DEFAULTS if defaults is None else defaults).get(key, default)
    return raw


def param_int(env, key, default=0, defaults=None):
    try:
        return int(str(param(env, key, default, defaults)).strip())
    except (TypeError, ValueError):
        return default


def flag(env, key, defaults=None):
    return str(param(env, key, '0', defaults)).strip().lower() in (
        '1', 'true', 'yes', 'on')


def counted(n, one, many):
    """"1 role" / "4 roles" — never "1 role(s)"."""
    return one if n == 1 else many % n


def fold(text):
    """Accents folded, never stripped.

    Not every database has an `unaccent` extension and plenty of people carry an
    accent in their name, so every match this module makes on a name is made in
    Python over folded text.
    """
    if not text:
        return ''
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(c for c in out if not unicodedata.combining(c))
    # Vietnamese `đ` carries no combining mark, so NFKD leaves it alone.
    out = out.replace('đ', 'd').replace('Đ', 'D')
    return out.strip().lower()


def safe(fn, default=None, what='a piece of this screen'):
    """Every independent probe gets its OWN try/except — never a shared one.

    And it says so at WARNING with the traceback: a swallowed failure logged at
    DEBUG is invisible on a live server, which is how a job that half worked
    came to report a cheerful small number.
    """
    try:
        return fn()
    except Exception:                           # noqa: BLE001
        _logger.warning('biz_access: %s could not be read', what, exc_info=True)
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
                'biz_access: all_implied_ids could not be read — walking '
                'implied_ids by hand instead', exc_info=True)
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
        # And this one is load-bearing: a check that cannot be made must be
        # reported, never treated as a pass.
        _logger.warning(
            'biz_access: the forbidden-permission check could not be made '
            'for %s', groups.ids, exc_info=True)
        return env['res.groups'].browse(
            [gid for gid in groups.ids if gid in forbidden])
