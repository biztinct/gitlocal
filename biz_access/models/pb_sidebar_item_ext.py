# -*- coding: utf-8 -*-
"""A left-menu entry can be opened by a ROLE, not only by a permission group.

WHY THIS FILE IS HERE AND NOT IN `pb_sidebar`. The left menu is a generic thing:
sections, entries, an icon, an action and the permissions that open them. Roles
are this module's idea. So the left menu keeps knowing nothing about roles, and
this module — which already depends on it — teaches one field and one extra
clause to the rule. A build without the Access home has a left menu that behaves
exactly as it always did, with no dead column and no dormant code.

THE RULE IS STILL DECIDED IN ONE PLACE (ledger C1). `pb.sidebar.item._state_for`
is that place, and this is an override of it rather than a second answer beside
it. Everything that asks "can they see this" — the real menu on every page load,
the person passport, the Screens lens, the "see it as…" spectacles — goes
through the same method and therefore through this clause too. That is the whole
reason the role lane is a `super()` call and not a helper somebody has to
remember to call.

  * An entry with NEITHER permissions NOR roles on it is open to everybody, and
    that answer belongs to the left menu, so this override hands it straight
    back with `super()`.
  * An entry that names ROLES is gated even when it names no permission —
    otherwise "only the access team opens Settings" would silently mean
    "everybody opens Settings", which is the one direction a gate must never
    fail in.
  * The two lanes are an OR. Somebody with the old permission still gets in;
    somebody with the role gets in as well. That is deliberate and it is what
    makes re-gating a live menu safe: nobody loses a door on the day the roles
    arrive.

HOLDING A ROLE MEANS HOLDING ALL OF IT (ledger A3, and the same arithmetic the
board's holder counts use). A role is a BUNDLE; somebody with two of its three
permissions cannot do the job its sentence describes, so they are not a holder
and the entry does not open for them. `user_groups` is already the TRANSITIVE
set — `_access_of` hands back `all_group_ids` — so a ladder is counted properly
without another closure walk here.

AN ARCHIVED ROLE OPENS NOTHING. It is not a permission any more; it is a row
somebody put away. An entry gated only on one is therefore reachable by nobody
but an administrator, and the Screens lens says so in those words rather than
letting it quietly fall back to "everybody" — a gate that widens when its role
is archived would be a gate that fails open.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PbSidebarItem(models.Model):
    _inherit = 'pb.sidebar.item'

    role_ids = fields.Many2many(
        'pb.role.profile', 'pb_sidebar_item_role_rel', 'item_id', 'profile_id',
        string='Roles that open it',
        help='Anybody who holds one of these roles in full can open this '
             'entry. It is read together with the permissions above: either '
             'one is enough.')

    # ------------------------------------------------------------------ the rule
    def _gate_roles_raw(self, item):
        """Every role written on this entry, archived ones INCLUDED.

        THE DIFFERENCE BETWEEN THIS AND `_gate_roles` IS THE WHOLE ARCHIVED-ROLE
        QUESTION, AND A TEST FOUND IT. "Is this entry gated at all" and "who can
        get through the gate" are two questions, and answering the first with
        the ACTIVE list makes archiving the last role on an entry open that
        entry to the entire company — the rule underneath is "no permissions and
        no roles means everybody". So the first question counts what is WRITTEN
        DOWN, and only the second one drops what has been put away.
        """
        if 'role_ids' not in item._fields:
            return self.env['pb.role.profile'].browse()
        try:
            return item.sudo().with_context(active_test=False).role_ids
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_access: the roles on left-menu entry %s could not '
                'be read — it is treated as having none', item.id,
                exc_info=True)
            return self.env['pb.role.profile'].browse()

    def _gate_roles(self, item):
        """The roles that open this entry — archived ones left out.

        `sudo()` because the caller may be asking about somebody else and the
        role catalogue carries a record rule of its own; which roles gate an
        entry is a fact about the MENU, not about the reader.

        THE `filtered('active')` IS LOAD-BEARING AND WAS FOUND BY A TEST. A
        many-to-many is read straight off its relation table, so `active_test`
        does NOT keep archived rows out of it — a role somebody had put away
        went on opening its entry, which is a gate quietly outliving the
        decision to retire it. Filtering here is the only place that has to
        remember.

        The read is guarded because a build mid-upgrade can have the column
        before it has the table behind it.
        """
        try:
            return item.sudo().with_context(
                active_test=False).role_ids.filtered('active')
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_access: the roles on left-menu entry %s could not '
                'be read — it is treated as having none', item.id,
                exc_info=True)
            return self.env['pb.role.profile'].browse()

    def _holds_any_role(self, roles, user_groups):
        """Does this person hold ANY of these roles, in full?

        A role with nothing in it is held by NOBODY — never by everybody, which
        is what an empty subset test would otherwise say and what would turn a
        half-written role into an open door.
        """
        held = set(user_groups.ids)
        for role in roles:
            groups = role.sudo().group_ids
            if groups and set(groups.ids) <= held:
                return True
        return False

    def _state_for(self, item, is_admin, user_groups):
        """(visible, locked) — the left menu's own rule, plus the role lane.

        The `super()` call is not a formality: when an entry names no roles at
        all this method must answer EXACTLY what the left menu answers, and the
        surest way to guarantee that is to let the left menu answer it.

        WHICH ROLES ARE WRITTEN DOWN decides whether the left menu's own rule
        applies; which of them are still ACTIVE decides who gets through. Asking
        one list both questions is how archiving the last role on an entry would
        hand that entry to the whole company.
        """
        if not self._gate_roles_raw(item):
            return super()._state_for(item, is_admin, user_groups)

        if is_admin:
            return True, False
        if item.groups_id and bool(item.groups_id & user_groups):
            return True, False
        if self._holds_any_role(self._gate_roles(item), user_groups):
            return True, False
        if item.restricted:
            return True, True
        return False, False
