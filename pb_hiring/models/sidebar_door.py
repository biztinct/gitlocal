# -*- coding: utf-8 -*-
"""THE LEFT-MENU DOOR TO HIRING, for everybody the board itself lets in.

Found live on 2026-10-03: the Talent lead and a line manager who raises
hiring requests were both admitted by the Hiring board (`pb.hiring.can_open`)
and both had NO way to it on the left menu. The Lifecycle entry — the hub the
Hiring lens lives in — is gated on `hr.group_hr_user` plus a role lane, and a
talent lead holds only the hiring tier; a line manager holds neither, because
"function head" is a fact of the org chart, not a group (see
`pb.hiring.requisition._can_raise`). The only way in was ⌘K, from a landing
screen with no search bar on it.

So the Lifecycle entry asks the board's own question before it hides itself.
One question, asked of the same method the hub's tab asks — the menu and the
tab cannot disagree about who gets in. Inside the hub every other lens still
asks its own question, so a talent lead sees the Hiring tab and nothing else.

ORDER. This override must sit OUTSIDE `biz_access` (whose role lane answers
without calling `super()` when an entry carries roles, which Lifecycle does),
hence `biz_access` in the manifest's depends. A company feature switch still
wins: an entry the company has switched off stays off for a hiring person too.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

LIFECYCLE_ITEM = 'pb_lifecycle.item_lifecycle'


class PbSidebarItem(models.Model):
    _inherit = 'pb.sidebar.item'

    def _state_for(self, item, is_admin, user_groups):
        visible, locked = super()._state_for(item, is_admin, user_groups)
        if visible:
            return visible, locked
        door = self.env.ref(LIFECYCLE_ITEM, raise_if_not_found=False)
        if not door or item.id != door.id or not self._pb_hiring_admits():
            return visible, locked
        if 'pb.tenancy' in self.env and item.feature_key:
            on, mode, _text = self.env['pb.tenancy'].feature_state(item.feature_key)
            if not on:
                return (True, True) if mode == 'lock' else (False, False)
        return True, False

    def _pb_hiring_admits(self):
        """Would the Hiring board open for the person this menu is drawn for?

        `visibility_for(user)` draws SOMEBODY ELSE's menu (the Access home's
        person passport), so the person comes from the context it sets, never
        blindly from `env.uid`."""
        uid = self.env.context.get('pb_sidebar_uid') or self.env.uid
        try:
            return bool(self.env['pb.hiring'].with_user(uid).can_open())
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: the Lifecycle door could not ask the '
                            'Hiring board about user %s', uid, exc_info=True)
            return False

    @api.model
    def visibility_for(self, user):
        return super(PbSidebarItem, self.with_context(
            pb_sidebar_uid=user.id)).visibility_for(user)
