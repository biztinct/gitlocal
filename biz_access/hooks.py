# -*- coding: utf-8 -*-
"""What this module does before it loads, and what it offers an application.

TWO JOBS, AND THEY ARE NOT RELATED.

  1. **`pre_init_hook` — the re-homing.** This module was EXTRACTED from a
     product module (ACCESS P6). On every database where that product module is
     already installed, the roles, abilities, hand-overs, their views, their
     record rules and the "access team" permission already exist, and every one
     of them is written down in `ir_model_data` as belonging to the OLD module.
     If nothing moved those rows, the install below would create a SECOND copy
     of each — a second access-team permission with nobody in it, a second set
     of rules — and the old copies would be swept away as stale at the end of
     the upgrade.

     So the very first thing that happens, before this module's own models are
     reflected and before a single data file is read, is a rename of the OWNER
     of those rows. `pre_init_hook` is the only place that can run: it fires on
     INSTALL, before `registry.load()` and before any data file, whereas a
     migration script only ever runs on an UPGRADE and would be too late.

     It is a no-op on a database that never had the product module — which is
     exactly what a fresh install of this module alone is.

  2. **The catalogue registry.** This module seeds NOTHING. It knows nothing
     about payroll, or people, or budgets, or what an ability should be called
     — those are the application's words. An application registers a seeding
     callable, and `ensure_catalogue()` runs whatever is registered. A database
     with only this module on it has a working, empty Access home, which is the
     honest answer rather than a board full of somebody else's vocabulary.

`ensure_bundles()` is here rather than in an application because it is not
about any catalogue: it gives a role somebody made BY HAND an ability of its
own, so nothing is left with an empty bundle. That is a fact about the model,
not about a product.
"""

import logging
import re
import unicodedata

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

#: The module these records used to belong to. Named once.
LEGACY_MODULE = 'pb_vendor_access'

# =============================================================================
# EVERY RECORD THAT MOVED, BY NAME.
#
# An explicit list and never a pattern, because the module it came from still
# owns records whose names start the same way — the vendor register's own views
# and rules live beside these — and a pattern that took one of those with it
# would leave the other module's data belonging to this one.
# =============================================================================
MOVED_XMLIDS = (
    # the permission
    'group_access_manager',
    # the record rules that are about roles and hand-overs themselves
    'rule_delegation_company',
    'rule_profile_visible',
    'rule_profile_access_team_all',
    'rule_delegation_mine',
    'rule_delegation_access_team_all',
    # the model access lines
    'access_pb_role_ability_user',
    'access_pb_role_ability_access_manager',
    'access_pb_role_profile_user',
    'access_pb_role_profile_access_manager',
    'access_pb_access_delegation_user',
    'access_pb_access_delegation_access_manager',
    # the job that takes an ended hand-over back
    'cron_access_auto_revert',
    # the two hand-over mails
    'mail_template_delegation_handed',
    'mail_template_delegation_ended',
    # the plain fallback screens
    'view_pb_role_profile_list',
    'view_pb_role_profile_search',
    'view_pb_role_profile_form',
    'view_pb_role_ability_list',
    'view_pb_role_ability_form',
    'view_pb_access_delegation_list',
    'view_pb_access_delegation_form',
    'view_pb_access_delegation_search',
    'view_pb_sidebar_item_list_roles',
    'view_pb_sidebar_item_form_roles',
    # the doors
    'action_pb_role_profile',
    'action_pb_access_delegation',
    'action_pb_access_board',
)

#: The models whose definition moved. Their `model_…`, `field_…` and
#: `constraint_…` rows are written by the framework rather than by a data file,
#: so they are matched by shape instead of by name.
MOVED_MODELS = (
    'pb.role.profile',
    'pb.role.ability',
    'pb.access.delegation',
    'pb.access',
)

#: The one field this module adds to somebody else's model.
MOVED_FIELDS = (
    ('pb.sidebar.item', 'role_ids'),
)

#: The many-to-many tables this module now owns. They matter because a module
#: uninstall DROPS the relation tables registered to it, and these two carry
#: what every role is made of and which entries it opens.
MOVED_RELATIONS = (
    'pb_role_ability_group_rel',
    'pb_role_profile_ability_rel',
    'pb_role_profile_group_rel',
    'pb_sidebar_item_role_rel',
    'pb_access_delegation_profile_rel',
    'pb_access_delegation_applied_rel',
)


def _module_id(cr, name):
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", (name,))
    row = cr.fetchone()
    return row[0] if row else None


def pre_init_hook(env):
    """Re-home what this module took over. Safe to run on a database that never
    had the module it was taken out of — it simply finds nothing.

    Every statement is guarded by `module = <the old one>`, so it can only ever
    move a row the old module owns, and it is idempotent: a second run finds
    nothing left to move.
    """
    if not isinstance(env, api.Environment):        # pragma: no cover
        env = api.Environment(env, SUPERUSER_ID, {})
    cr = env.cr

    cr.execute("SELECT 1 FROM ir_module_module WHERE name = %s AND state IN "
               "('installed', 'to upgrade', 'to remove')", (LEGACY_MODULE,))
    if not cr.fetchone():
        _logger.info(
            'biz_access: nothing to re-home — this database has never had %s '
            'installed', LEGACY_MODULE)
        return

    # ------------------------------------------------------- the named records
    cr.execute("""
        UPDATE ir_model_data SET module = 'biz_access'
         WHERE module = %s AND name IN %s
    """, (LEGACY_MODULE, tuple(MOVED_XMLIDS)))
    named = cr.rowcount

    # -------------------------------------- the model, field and constraint ids
    model_names = [n.replace('.', '_') for n in MOVED_MODELS]
    like_field = ['field_%s__%%' % n for n in model_names]
    like_constraint = ['constraint_%s_%%' % n for n in model_names]
    cr.execute("""
        UPDATE ir_model_data SET module = 'biz_access'
         WHERE module = %s
           AND (name IN %s
                OR name LIKE ANY(%s)
                OR name LIKE ANY(%s))
    """, (LEGACY_MODULE,
          tuple('model_%s' % n for n in model_names),
          like_field, like_constraint))
    technical = cr.rowcount

    # ------------------------------------ the one field on somebody else's model
    borrowed = 0
    for model, field in MOVED_FIELDS:
        cr.execute("""
            UPDATE ir_model_data SET module = 'biz_access'
             WHERE module = %s AND name = %s
        """, (LEGACY_MODULE, 'field_%s__%s' % (model.replace('.', '_'), field)))
        borrowed += cr.rowcount

    # ------------------------------------- the tables an uninstall would drop
    new_id = _module_id(cr, 'biz_access')
    old_id = _module_id(cr, LEGACY_MODULE)
    relations = constraints = 0
    if new_id and old_id:
        cr.execute("""
            UPDATE ir_model_relation SET module = %s
             WHERE module = %s AND name IN %s
        """, (new_id, old_id, MOVED_RELATIONS))
        relations = cr.rowcount
        cr.execute("""
            UPDATE ir_model_constraint SET module = %s
             WHERE module = %s
               AND model IN (SELECT id FROM ir_model WHERE model IN %s)
        """, (new_id, old_id, MOVED_MODELS))
        constraints = cr.rowcount

    _logger.info(
        'biz_access: re-homed from %s — %s named records, %s model/field/'
        'constraint ids, %s borrowed field(s), %s relation tables, %s table '
        'constraints', LEGACY_MODULE, named, technical, borrowed, relations,
        constraints)


# =============================================================================
# THE CATALOGUE REGISTRY.
#
# An application registers ONE callable that seeds its own roles and abilities.
# It is called with an env and must be safe to run again — every seeding routine
# in this family is idempotent by construction rather than by a stamp, because
# it runs on a fresh install, on an upgrade, and on a database somebody restored
# from a backup taken in between.
# =============================================================================
_PROVIDERS = []


def register_catalogue(fn, name=None):
    """An application says how to seed its own roles and abilities."""
    key = name or getattr(fn, '__module__', '') + '.' + getattr(
        fn, '__name__', repr(fn))
    for existing_key, _existing in _PROVIDERS:
        if existing_key == key:
            return _PROVIDERS
    _PROVIDERS.append((key, fn))
    return _PROVIDERS


def catalogue_providers():
    return list(_PROVIDERS)


def ensure_catalogue(env):
    """Seed whatever the applications on this database have registered.

    On a database with nothing but this module installed there is nothing
    registered, and an EMPTY Access home is the right answer: this module has no
    vocabulary of its own to offer and inventing one would put words on somebody
    else's screen.
    """
    ran = []
    for key, fn in _PROVIDERS:
        try:
            fn(env)
            ran.append(key)
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_access: the "%s" catalogue could not be seeded', key,
                exc_info=True)
    linked = ensure_bundles(env)
    _logger.info(
        'biz_access: catalogue — %s application catalogue(s) run, %s role(s) '
        'written down as bundles of what they already carried',
        len(ran), linked)
    return {'providers': ran, 'linked': linked}


def _slug(text, fallback='ability'):
    """A stable key out of a name an administrator typed.

    Accents folded rather than stripped: "Chế độ" must not become "ch-", which
    is a key that collides with the next three roles like it.
    """
    raw = unicodedata.normalize('NFKD', str(text or ''))
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    raw = raw.replace('đ', 'd').replace('Đ', 'D')
    raw = re.sub(r'[^a-zA-Z0-9]+', '-', raw).strip('-').lower()
    return raw or fallback


def ensure_bundles(env):
    """Give every remaining role an ability, so nothing is left unbundled.

    An application's catalogue covers the roles it seeded. An administrator may
    have added their own before bundles existed — one name, one permission — and
    that role would otherwise have an EMPTY bundle, which the board reads as
    "nobody holds this" for something several people plainly hold. So each one
    gets an ability of its own, wrapping exactly the permission it already
    carried, named after the role because that is the only honest sentence
    available for it.

    It changes nobody's permissions. It writes down, in the new shape, what the
    old shape already said.
    """
    Profile = env['pb.role.profile'].sudo().with_context(active_test=False)
    Ability = env['pb.role.ability'].sudo().with_context(active_test=False)
    orphans = Profile.search(
        [('ability_ids', '=', False), ('group_id', '!=', False)])
    linked = 0
    for profile in orphans:
        key = 'role-%s-%s' % (_slug(profile.name, 'role'), profile.id)
        # Found by its own key and by nothing else. Reusing "an ability that
        # happens to contain this permission" would attach the OTHER
        # permissions in it too, and a migration that widens somebody's access
        # is the one outcome this module refuses everywhere.
        ability = Ability.search([('technical_key', '=', key)], limit=1)
        try:
            if not ability:
                ability = Ability.create({
                    'technical_key': key,
                    'name': profile.name or key,
                    'description': profile.description or '',
                    'area': profile.area,
                    'sequence': profile.sequence or 10,
                    'group_ids': [(6, 0, [profile.group_id.id])],
                })
            profile.write({'ability_ids': [(6, 0, ability.ids)]})
            linked += 1
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_access: the "%s" role could not be given an ability for '
                'the permission it already carried', profile.name,
                exc_info=True)
    if linked:
        _logger.info(
            'biz_access: %s roles outside any seeded catalogue were written '
            'down as bundles of what they already carried', linked)
    return linked


def post_init_hook(env):
    """Odoo 19 hands the hook an `env`. This runs on INSTALL only."""
    if not isinstance(env, api.Environment):        # pragma: no cover
        env = api.Environment(env, SUPERUSER_ID, {})
    ensure_catalogue(env)
