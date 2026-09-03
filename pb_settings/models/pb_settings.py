# -*- coding: utf-8 -*-
"""The Settings hub's only server call: does this action exist here?

The hub itself is chrome — it owns no data, writes nothing, and every card on it
is a door to something that already exists. The one question it cannot answer in
the browser is whether an ACTION XMLID resolves on this database: a client action
can be probed against the JS registry (a module that is not installed did not
ship its JS), but an `ir.actions.act_window` leaves no trace in the browser at
all.

That question matters because of W79: a resolver with a swallowing fallback makes
a DEAD entry indistinguishable from an ABSENT one. A card pointing at a deleted
or never-installed action renders normally, answers a click with nothing, and
logs nothing — five of exactly that shape survived in `hr.flow.wizard` until P7
went looking. So the hub asks, and hides what is not there.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# The descriptor in settings_hub.js names 6 action xmlids today. The cap is a
# bound on a list a caller controls, not a guess at the descriptor's size — a
# forged call may not turn one RPC into an unbounded ir.model.data walk.
_MAX_PROBE = 50
#: Same idea for the gate call: a bound on a list the caller controls.
_MAX_CATEGORIES = 40
_MAX_CARDS = 20

#: The permission that means "this person runs the platform, not a tenant".
SYSTEM_GROUP = 'base.group_system'

# =============================================================================
# THE PLATFORM-ONLY SET (ACCESS P5, Rail C).
#
# This product runs one database per customer, and the person who administers a
# customer's own application is NOT the person who runs the platform. Almost
# everything behind the cog belongs to the customer: how pay is calculated, what
# the structures are, which connected systems feed it, who holds which role.
# Three things do not, and they are named here rather than left to a list of
# permission groups in the browser:
#
#   * **Companies & Tenants** — the legal entities and the fleet of customer
#     databases. The fleet is the platform's own; the companies screen can only
#     be written by a system administrator, so offering it to anybody else is a
#     door that can only make an access dialog.
#   * **Users & permission groups** — the raw membership table. Roles are how
#     access is given on this product, and the Access home is where that
#     happens; the raw table is the platform's own tool for the day something
#     has gone wrong with it.
#   * **Payroll defaults** — a `res.config.settings` screen, which Odoo grants
#     to system administrators alone. It also carries the links that switch
#     developer mode on, which Rail A exists to make impossible.
#
# THE DIFFERENCE FROM EVERY OTHER GATE IN THIS FILE IS THE DIRECTION IT FAILS
# IN. The rest of the hub fails OPEN on purpose (an unresolvable permission
# means the module is not installed, and reading that as "denied" hides a
# category for the wrong reason). These three fail CLOSED: anything but a proven
# system administrator is refused, including a caller whose payload has been
# edited in the browser, because the answer does not depend on the payload.
# =============================================================================
PLATFORM_ONLY_CATEGORIES = ('org', 'roles', 'payroll')

#: Native actions that belong to whoever runs the platform, wherever a category
#: puts them. Card-level as well as category-level, because the Navigation
#: category is REPLACED on databases that have the Access home — its lens is
#: everybody's business who may edit a gate, and the raw list views behind it
#: are not.
PLATFORM_ONLY_ACTIONS = (
    'base.action_res_users',
    'base.action_res_company_form',
    'om_hr_payroll.action_hr_payroll_configuration',
    'pb_sidebar.action_pb_sidebar_item',
    'pb_sidebar.action_pb_sidebar_section',
)

#: Cockpits that are the platform's own.
PLATFORM_ONLY_TAGS = ('pb_tenants',)


class PbSettings(models.AbstractModel):
    _name = 'pb.settings'
    _description = 'Payobook settings hub'

    @api.model
    def resolve_actions(self, xmlids):
        """`{xmlid: bool}` — which of these action xmlids exist here.

        Read-only by construction: `env.ref` with `raise_if_not_found=False` is
        the whole method. No sudo (there is nothing to escalate — existence of an
        xmlid is not a permission), no create, no write, no unlink. Whether the
        CALLER may open what it names is the action's own question and stays
        with the action; this one only stops the hub from offering a door that
        was never built.

        Anything that is not a string is skipped rather than raising: the caller
        is a template descriptor, and one malformed entry must not take the whole
        Settings hub down with it.
        """
        out = {}
        for xmlid in (xmlids or [])[:_MAX_PROBE]:
            if not isinstance(xmlid, str) or '.' not in xmlid:
                continue
            out[xmlid] = bool(self.env.ref(xmlid, raise_if_not_found=False))
        return out

    # =========================================================== Rail C
    @api.model
    def resolve_gates(self, categories):
        """Who may see which category, answered here rather than in the browser.

        The hub has always worked out visibility in the browser, and for most of
        it that is the right place: it is chrome, it owns no data, and every
        door it draws keeps its own permissions. But three of its categories are
        the PLATFORM's rather than the customer's (see the block above), and
        "the browser decides" is not an answer that survives somebody editing
        the browser. So the question is asked of the server, and for those three
        the server does not consult the payload at all.

        `categories` is the descriptor, trimmed to what this call needs::

            [{'key': 'org',
              'groups': ['base.group_system'],
              'cards': [{'id': 'tenants', 'tag': 'pb_tenants'},
                        {'id': 'companies', 'xmlid': 'base.action_…'}]}]

        and the answer is::

            {'is_system': False,
             'categories': {'org': False, 'formula': True, …},
             'cards': {'org:tenants': False, 'formula:studio': True, …}}

        THREE RULES, IN THIS ORDER.

          1. A system administrator sees everything. Nothing below can take a
             category away from the person who runs the platform.
          2. A platform-only category, or a card naming a platform-only action
             or cockpit, is refused. This is the only decision in the hub that
             ignores what the caller sent, and it is the point of the method.
          3. Everything else keeps the rule the hub has always had: no
             permissions named means everybody, otherwise ANY ONE of them is
             enough, and a permission this database has never heard of is read
             as "the module is not installed" and does not deny anything.

        Read-only by construction — `has_group` and a name comparison. It
        decides what is OFFERED, never what is allowed: what somebody may
        actually do behind a door is still the door's own business.
        """
        is_system = self.env.user.has_group(SYSTEM_GROUP)
        out_cats, out_cards = {}, {}
        for cat in (categories or [])[:_MAX_CATEGORIES]:
            if not isinstance(cat, dict):
                continue
            key = cat.get('key')
            if not isinstance(key, str) or not key:
                continue
            out_cats[key] = ((is_system or self._gate_category(key, cat))
                             and self._gate_feature(cat))
            for card in (cat.get('cards') or [])[:_MAX_CARDS]:
                if not isinstance(card, dict) or not card.get('id'):
                    continue
                out_cards['%s:%s' % (key, card['id'])] = (
                    (is_system or self._gate_card(card))
                    and self._gate_feature(card))
        return {'is_system': is_system,
                'categories': out_cats,
                'cards': out_cards}

    def _gate_category(self, key, descriptor):
        """Rule 2 then rule 3, for one category. Never called for an administrator."""
        if key in PLATFORM_ONLY_CATEGORIES:
            return False
        groups = [g for g in (descriptor.get('groups') or [])
                  if isinstance(g, str) and '.' in g]
        if not groups:
            return True
        return any(self._holds(g) for g in groups)

    # ============================================ FLEET P4 — is it sold here?
    #
    # A FOURTH RULE, AND IT IS THE ONLY ONE AN ADMINISTRATOR DOES NOT ESCAPE.
    # Rules 1-3 are about PERMISSION: who may use a screen, and a system
    # administrator may use all of them. This one is about whether the company
    # has the thing at all — and if they have not bought Insights, the person
    # who administers their database has not bought it either. Offering it to
    # them is offering a door into a product that is not there, and the one
    # person who will then telephone about it.
    #
    # IT IS STILL NOT A SECURITY CONTROL. It takes a card off a screen. What
    # somebody may read behind that card is decided by the roles they hold,
    # exactly as before, and nothing here changes it.
    #
    # Asked of the SERVER because the browser's answer can be edited, and
    # because a card that is switched off must not be offered by a hub whose
    # descriptor somebody has rewritten in a console. FAILS OPEN in the two
    # ways that matter: a database with no Platform Link has no answer and
    # keeps every card, and a feature key nobody has defined is not a reason to
    # hide anything.
    def _gate_feature(self, descriptor):
        key = descriptor.get('feature')
        if not isinstance(key, str) or not key:
            return True
        if 'pb.tenancy' not in self.env:
            return True
        try:
            on, mode, _text = self.env['pb.tenancy'].feature_state(key)
        except Exception:                               # noqa: BLE001
            _logger.warning('pb_settings: could not read the feature switches; '
                            'every card stays visible', exc_info=True)
            return True
        # `lock` is the browser's job: the hub draws the padlock and answers the
        # click. The server only refuses what should not be on the screen at
        # all.
        return bool(on) or mode == 'lock'

    def _gate_card(self, card):
        """Is this one door the platform's own? Never called for an administrator."""
        tag = card.get('tag')
        if isinstance(tag, str) and tag in PLATFORM_ONLY_TAGS:
            return False
        xmlid = card.get('xmlid')
        if isinstance(xmlid, str) and xmlid in PLATFORM_ONLY_ACTIONS:
            return False
        return True

    def _holds(self, xmlid):
        """Does the reader hold this permission?

        FAILS OPEN, and only in the one direction the hub has always failed
        open in: a group xmlid that does not resolve means the module shipping
        it is not on this database, and a category hidden for that reason is
        hidden for the wrong one. The platform-only set above never reaches
        here — it is decided before any permission is looked at — so this
        cannot be used to widen anything that matters.

        THE EXISTENCE CHECK IS SEPARATE FROM THE MEMBERSHIP CHECK, AND A TEST
        FOUND OUT WHY. `has_group` answers a plain False for a name this
        database has never heard of — it does not raise — so a `try/except`
        around it reads "the module is not installed" as "the reader is not in
        it", which is the exact confusion the fail-open rule exists to prevent.
        So the name is resolved first, and only a name that RESOLVES is asked
        about membership.
        """
        try:
            group = self.env.ref(xmlid, raise_if_not_found=False)
        except ValueError:
            group = None
        if not group:
            _logger.info(
                'pb_settings: the %s permission is not on this database — the '
                'category naming it is left visible', xmlid)
            return True
        try:
            return self.env.user.has_group(xmlid)
        except (ValueError, KeyError):
            return True
